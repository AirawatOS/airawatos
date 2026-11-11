# ADR-0073 — Air Intelligence: a reproducible PM2.5 nowcast/forecast on the H3 baseline

- **Status:** Proposed (2026-09-05)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0060 (L0–L4 ladder + **City Digital Baseline** — the H3-res-9 grid, `observed_at`
  timestep, and the driver→cell→intelligence pipeline this builds on), the **Air Intelligence solution** (the
  existing air vertical: `air-sensors` → `air.sensor_reading`, `station-interpolation` → `air.quality`,
  `air-diagnosis`, `hotspot-detection`, and the Air Action Loop), the **cell-indexer** engine (raster/point → H3
  zonal/IDW — the reusable H3-conversion utility), ADR-0041 (lineage & confidence — the `prov` block every fact
  carries), ADR-0052 (attributed writes), ADR-0070 (uncertainty & publishability — p10/p50/p90 and confidence
  gating), ADR-0029 (decision spine — an *advisory* estimate never auto-acts; the Action Loop decides), the
  **"engines as components"** rule (server-side model logic must be a certified, Studio-editable engine, not host
  code). External anchors: the pasted "air-pollution data platform & modelling" implementation brief
  (H3 feature store → baselines → XGBoost → residual assimilation → GNN); CPCB CAAQMS, CAMS, ERA5, MAIAC AOD,
  Sentinel-5P/TROPOMI, VIIRS FIRMS, EDGAR.

## Context

Delhi's PM2.5 problem is the reference test for the platform's analytical depth. We were handed a thorough,
greenfield modelling brief (its own §24 says: *inspect the existing repo first and adapt to its conventions
rather than forcing the `airq/` layout*). AirawatOS already provides most of that spine — and an **Air
Intelligence solution already exists** — so this ADR is about **enhancing** that vertical, not standing up a
parallel system.

What the platform already gives us, governed, that the brief assumes we must build:

- **H3 res-9** is the canonical grid; the registry key `(id, observed_at)` **is** the brief's
  `(h3_index, timestamp_utc)` hourly key, and `observed_at = period` already drives the City Scan time scrubber.
- **`prov`** on every fact (method, `source_ref`, native resolution, confidence, `observed_at`) **is** the
  provenance contract the brief demands — including "never silently interpolate; represent missingness explicitly."
- **`cell-indexer`** is the raster/point → H3 zonal/IDW aggregation utility (the brief's §5 spatial ops).
- Certified drivers behind the **broker** (idempotent, per-tenant tokens, egress-declared) **are** the "independent
  data drivers" architecture; the **scheduler** + **GEE earth-observation runtime** run them.
- **viz.layer + City Scan** are the output/visualisation surface; **ADR-0070** already defines uncertainty +
  publishability.

Existing air + baseline components we reuse directly: `air-sensors` / `kanpur-idss` (CPCB/OpenAQ/low-cost →
`air.sensor_reading`, the brief's §4.1 ground truth), `station-interpolation` (IDW surface — a Model-0 baseline),
`weather-forecast` (Open-Meteo hourly met), `rainfall-openmeteo`, `landcover`/`landcover-dw`, `population-ghsl`,
`terrain-dem`, `nightlight-viirs`, `osm-roads`, `satellite-lst`, `air-diagnosis`, `hotspot-detection`.

**The gap** is the physically-important atmospheric predictors (regional background, boundary-layer height, AOD,
fire, emissions), the `(h3×hour)` **feature store**, a real **model sequence** (baseline → RF → XGBoost →
residual → GNN) as certified engines, **leave-station-out** validation, and calibrated **uncertainty** — plus a
clean **nowcast vs forecast** split.

## Decision

Enhance the Air Intelligence solution to deliver a reproducible PM2.5 **nowcast** (and later **forecast**) over
the H3-res-9 Delhi baseline, incrementally, baselines-first, with these load-bearing adaptations of the brief to
AirawatOS conventions:

### 1. Feature store = governed registry facts + Parquet materialisation

Each driver writes its per-cell, per-hour signal as a **governed fact** in the registry (provenance kept, one
noun per source). The **`pm25-features` engine** assembles the `(h3×hour)` training/inference matrix by reading
those facts and **materialising to Parquet/DuckDB in the filestore** for heavy historical training — governed
facts in, an efficient columnar training set out. This is the brief's `data/{raw,staged,h3,features}` hierarchy
expressed the AirawatOS way: the registry is the `staged/h3` governed layer; the filestore Parquet is
`features/`. Incremental builds append the new hours; we never regenerate history.

### 2. Every source stays at its native resolution; H3-9 is the join unit, not a resolution claim

Coarse fields (CAMS, ERA5, TROPOMI pixels km-wide) are associated to cells by area-weighted overlap / interpolation
and **carry `source_pixel_id`, `intersection_fraction`, `native_resolution`, `observation_age`** — never upsampled
and relabelled as high-res. **AOD is a feature, not PM2.5.** Missing satellite data is expected and modelled with
explicit availability signals (`aod_available`, `hours_since_last_aod`, …). (Brief §23.)

### 3. Models are certified engines, in sequence — XGBoost is the first production model

`pm25-baseline` (persistence / nearest-station / spatial-mean = reuse `station-interpolation`) → `pm25-model`
(regularised linear → Random Forest **benchmark** → **XGBoost primary**, SHAP top-contributors written onto each
estimate) → `pm25-residual` (XGBoost + IDW/kriging of *recent* station residuals = the nowcast) → later
`pm25-gnn` (H3-adjacency + dynamic wind-aware edges) **only if it beats XGBoost under strict spatial/temporal
holdout**. All Studio-editable engines, not host code.

### 4. Nowcast and forecast are separate

- **Nowcast** ("PM2.5 in every cell now") → enhanced `air.quality` **superseded by** a new `air.pm25_estimate`
  carrying `pm25`, `p10/p50/p90`, `confidence`, `model@version`, and top feature contributors. Rendered as the
  City Scan "Air Quality (PM2.5)" layer with per-cell contributors + confidence (ADR-0070).
- **Forecast** ("next 1–24 h") → `air.pm25_forecast` (per-cell hourly series, like `cell.weather_forecast`),
  XGBoost-on-forecast-met baseline first, GNN+temporal later. Kept in its own engine/pipeline.

### 5. Validation is a first-class engine, and leave-station-out is the acceptance criterion

`pm25-eval` implements temporal holdout, **leave-station-out**, spatial holdout, and event holdout (Diwali /
crop-burning / inversions), reporting RMSE/MAE/R²/bias by PM2.5 band and by station/season/hour/monitor-density.
Explicit **leakage tests** (no future met/satellite/label; rolling features use only data ≤ prediction time) run
in CI. "How well does it predict an unseen monitor?" is the headline metric.

### New governed schemas (propose via governance → steward-approve)

`cell.aod` (AOD mean/std/valid-fraction/qa/age), `air.no2` (TROPOMI column + pixel provenance), `cell.cams`
(regional background pm25/pm10/no2 — coarse), `cell.emissions` (EDGAR, per-sector), `signal.fire` (FIRMS points +
FRP), `air.pm25_estimate` (nowcast + uncertainty + contributors), `air.pm25_forecast` (per-cell hourly). All
`<domain>.<subject>`, `x-kind` measure/event, `prov` required.

### New components

- **Drivers (GEE earth-observation runtime):** `cams-regional` + **ERA5 PBL-height** *(built first — the two
  strongest physical predictors per §23.6/23.7)*, then `maiac-aod` (VIIRS/MODIS), `tropomi-no2`, `firms-fire`,
  `edgar-emissions`. Each implements the existing driver contract (discover/fetch/normalise/to_h3/validate/
  metadata already matches our meta.yaml + broker pattern) and is idempotent.
- **Engines:** `pm25-features` (assemble matrix + lags + H3-neighbour + **wind-aware transport** features for
  fires/roads/industry/regional), `pm25-model` (linear/RF/XGBoost + SHAP + quantiles), `pm25-residual`,
  `pm25-eval`, later `pm25-forecast` / `pm25-gnn`.

### Milestones

- **M1 — foundations:** govern the new schemas; scaffold `pm25-features` + the Parquet materialisation seam;
  confirm Delhi tenant AOI + res-9 grid; wire the reuse list into the Delhi baseline step order. Reuse the
  existing driver/provenance abstractions — no new conventions.
- **M2 — high-lift drivers:** `cams-regional` + **ERA5 PBL height** first, then `maiac-aod`, `firms-fire`.
- **M3 — feature store:** `(h3×hour)` matrix with temporal lags, H3-neighbour, and wind-aware transport features →
  Parquet.
- **M4 — models:** baselines → linear → RF → **XGBoost** (certified engine) + SHAP contributors on each estimate.
- **M5 — validation + uncertainty:** `pm25-eval` (leave-station-out + temporal + spatial + event); quantile
  p10/p50/p90 → `air.pm25_estimate`; enhanced City Scan PM2.5 layer.
- **M6 — nowcast:** `pm25-residual` (XGBoost + station-residual assimilation).
- **M7/M8 — forecast + GNN:** only after the nowcast is robust; GNN must demonstrate a statistically meaningful
  win under spatial holdout before it augments/replaces XGBoost.

## Implementation log

**M1 + the two priority M2 drivers — DELIVERED (2026-09-05), live + verified on `new-delhi` real data.**

- **Schemas governed:** `cell.cams@0.1.0` (regional background pm2.5/pm10/no2/o3/so2, µg/m³) and
  `cell.boundary_layer@0.1.0` (ECMWF PBLH, m) — both `x-kind: measure`, `x-measures-of: space.aoi` (the ADR-0060
  §3a rule for a coarse area field, same as `cell.rainfall`), `prov` required, `additionalProperties:false`,
  `native_resolution_km` carried. Filed via devrick → steward-approved.
- **Sourcing adaptation (deliberate):** the two strongest predictors were built as **keyless host-subprocess
  drivers on Open-Meteo**, not GEE — Open-Meteo's air-quality API *is* CAMS global (~40 km) and its weather API
  serves the ECMWF `boundary_layer_height`. Same real sources the ADR names, no GEE-quota/key friction, and it
  matches the existing `rainfall-openmeteo` / `weather-forecast` precedent. Each samples a coarse grid, fetches
  in one egress call, and assigns every H3 cell its nearest sample carrying `native_resolution_km` + `source_point`
  — never upsampled (§2). The later EO drivers (`maiac-aod`, `tropomi-no2`, `firms-fire`, `edgar-emissions`)
  remain GEE-runtime as planned.
- **`cams-regional` + `era5-pblh`** (`ds:airawat:driver/*`): certified (verified, 13 checks), published @0.1.0,
  installed into `new-delhi`, run → **24,277 `cell.cams` + 24,277 `cell.boundary_layer`** cells for hour
  `2026-09-05T04:00Z`. Sanity: PM2.5 ≈ 21 µg/m³ (monsoon-clean, spatially smooth as a 40 km field should be),
  PBLH ≈ 290–410 m (correctly shallow at 09:30 IST).
- **`pm25-features`** (`ds:airawatdeveloper:engine/pm25-features`): certified (verified, 12 checks), published,
  installed, run → **24,277-row × 12-feature `(h3×hour)` matrix materialised to the filestore** (content-addressed
  blob, NDJSON) joining cell.cams + cell.boundary_layer + cell.rainfall + demographics.population + geo.terrain +
  cell.hydrology. This is the ADR §1 seam ("governed facts in, columnar training set out").
- **Honest gaps (real-or-fail, no fabrication):** (a) `pm25_obs` label column is **null everywhere (0 labelled
  cells)** — Delhi CPCB `air.sensor_reading` ingest needs a real key (matrix is inference-ready, not yet
  trainable); (b) the materialisation is **NDJSON, not Parquet** — the runtime lacks `pyarrow`; the engine already
  branches on `OUT_FORMAT=parquet` and M3 stands up a feature runtime with pyarrow to flip it; (c) single hour
  only (no temporal lags / neighbour / wind features — those are M3).

**M2 — high-lift drivers (in progress, 2026-09-05).**

- **CPCB ground truth — DELIVERED + verified.** `air-sensors` bumped to **0.2.0**: it now implements the CPCB
  CAAQMS (data.gov.in) real source it had declared since 0.1.0 (the broker injects `CPCB_API_KEY` as the
  `api-key` query param; OpenAQ kept as a secondary source; `SOURCE` env selects, default `cpcb,openaq`). Run on
  `new-delhi` → **49 real CPCB stations → `air.sensor_reading`** inside the AOI (scanned 3,521 all-India rows).
  The data.gov.in resource had been re-keyed (`pollutant_avg` → `avg_value`) — fixed, accepting both. Re-running
  `pm25-features` now shows **`labels_present: 49`** — the matrix is trainable. (The tenant's `CPCB_API_KEY` is
  bound to `air-sensors` in Vault, which is why the CPCB path lives there rather than a standalone component —
  Vault secrets are strictly per-(tenant, component), no sharing.)
- **`cell.aod@0.1.0` governed** (measure, `x-measures-of: space.aoi`). **`maiac-aod`** driver (MODIS MAIAC
  `MCD19A2`, 1 km, GEE) built + certified + published + installed, and **run → 19,760 `cell.aod` cells** (AOD
  0.24–0.79, mean 0.33, valid-fraction 0.96 — physical for early-Sep Delhi). Monsoon lesson: a 3-day window
  yielded **zero** cloud-free retrievals (all cells null → 422 on the required `aod`); fixed by (a) skipping
  cells with no valid retrieval — missingness = absence, not a null row — and (b) defaulting `WINDOW_DAYS` to
  **10** (14 gave ~81% coverage). `pm25-features` bumped to **0.1.1** to join `cell.aod`.
- **`air.pm25` feature matrix now carries 14 features** (added `aod`, `aod_valid_fraction`) over 24,277 cells
  with 49 CPCB labels — the M2 data spine is complete and materialised to the filestore.
- **`signal.fire@0.1.0` governed** (event; point + `frp_mw` + confidence + `occurred_at`). **`firms-fire`** driver
  (NASA FIRMS Area API, VIIRS/MODIS NRT → real per-fire FRP) built + certified (verified, 13 checks) + published +
  installed into `new-delhi`. The FIRMS `MAP_KEY` sits in the URL **path**, which the broker's header/query inject
  modes couldn't reach — so a small, general **`as: template`** inject mode was added to the secrets service
  (component sends `{KEY}`, broker substitutes from Vault, audit logs the placeholder path — key never seen/logged;
  unblocks all path-key APIs). **Blocked on one input:** a free NASA FIRMS `MAP_KEY` bound to `firms-fire` in
  Connections. (Zero detections in-window is a valid result, not an error — Delhi's burning season is Oct–Nov.)
- **Two keys to bind** (per-component Vault isolation): GEE service-account key → `maiac-aod`; FIRMS MAP_KEY →
  `firms-fire`. Once set, one run each populates `cell.aod` + `signal.fire`, and a `pm25-features` re-run gains the
  AOD column.

**M3 — feature store (in progress, 2026-09-05).**

- **M3.1 Parquet — DONE.** `pyarrow` added to the runtime-manager (the in-process engine runtime; hot-patched,
  BAKE pending — the engine already falls back to NDJSON if absent). `pm25-features@0.2.0` now writes real
  **Parquet** by default: 24,277×N at **~0.95 MB** vs 10.2 MB NDJSON (~10× smaller, columnar/DuckDB-ready).
- **M3.3 H3-neighbour aggregates — DONE.** Pure in-memory k-ring (k=1) means over the assembled matrix (no extra
  registry reads): `pm25_cams_nbr`, `no2_cams_nbr`, `pblh_m_nbr`, `aod_nbr`. Matrix is now **18 features** (14 base
  + 4 neighbour) over 24,277 cells with 49 CPCB labels.
- **M3.2 temporal lags — DONE (coarse point-series, the chosen design).** `cams-regional`/`era5-pblh` bumped to
  0.2.0: in addition to the per-cell current-hour layer they now write a compact hourly SERIES at the ~25 sample
  cells (hour-keyed `…/cell/cams/series/…` ids, reusing the governed schemas — no new noun; ~1,350 facts/driver
  for ~54 h). `pm25-features@0.3.0` assembles per-cell lags from the NEAREST series anchor: `pm25_cams_lag{1,3,6,24}`
  + `pblh_m_lag{3,24}`. Verified: **all 6 lag cols 24,277/24,277 non-null**, with real diurnal signal (pm25 lag24
  mean 40 vs lag1 20; pblh lag24 758 m afternoon vs lag3 332 m morning).
- **Anthropogenic / land features added (M3.4a) — DONE.** The existing governed baseline layers are strong
  local-emission proxies, so `pm25-features@0.4.0` now also joins `cell.buildings` (built_area_m2 + building_coverage),
  `cell.builtup` (built-up fraction), and `cell.greencover` (green fraction). Verified on new-delhi: builtup_frac
  mean 0.52, greencover 0.12, building_coverage ~0.19 (built_area/coverage null in ~half the cells — those with no
  footprints; honest). **Matrix is now 28 features** (18 base incl. anthropogenic + 4 H3-neighbour + 6 lag), 49 labels.
- **Nightlights — DONE.** `nightlight-viirs` run on new-delhi → `econ.nightlight` (avg_radiance); joined into
  `pm25-features@0.5.0` as `nightlight_radiance` (24,277 cells). **Matrix now 29 features** — the combustion/
  economic-activity proxy the product owner asked for.
- **Road density + building height — DONE at the ingestion layer (the right place).**
  - **Roads:** `osm-roads` already emits `cell.roads` (road_length_m, road_density_km_per_km2, segment_count,
    primary_class) in its PBF pass — it just hadn't been re-run for new-delhi. Re-running populates it; `pm25-features`
    joins `road_length_m` + `road_density`.
  - **Building height:** `cell.buildings@0.2.0` governed with `mean_height_m` + `built_volume_m3`;
    `buildings-openbuildings@0.2.0` now adds the **Open Buildings 2.5D Temporal `building_height`** band to its GEE
    `reduceRegions` (zonal mean over building pixels) — verified realistic (Delhi mean ≈ 5.7 m, ~2 storeys).
    `pm25-features` joins `building_mean_height_m` + `built_volume_m3`. **Matrix → ~33 features.**
  - Two operational notes: (1) after governing a schema *update*, the **kernel caches the version map ~300 s** and
    kept validating against the old version → the height write 422'd; fixed by `POST /v1/registry/schema-cache/refresh`
    (admin) — do this after any in-place schema bump. (2) the OB-Temporal height reduce is **slow** (the full 24k
    backfill takes a long GEE run); acceptable for a one-off baseline, but a future optimization is to pin one recent
    year instead of `.mosaic()` over the whole temporal collection.
- **(superseded) earlier efficiency wall:** aggregating the L1 sets post-hoc through the registry timed out; the
  fix above (emit rollups at ingestion) is why roads/height are done cheaply instead. A post-hoc aggregation
  engine that reads the L1 sets (`geo.osm_feature` roads, `geo.building` footprints) through the registry is
  **not viable**: those are 100k+ facts and a single `resolve` of the scope **timed out at 120 s** (and the
  broker `/v1/query` re-fetches the whole scope per page — O(n²)). The correct fix is to emit the per-cell rollups
  **at ingestion**, where all geometries are already in hand: (a) enhance `osm-roads` to also write `cell.roads`
  (road length/density per H3, weighted by motorized class) in the same PBF pass; (b) for building height, use the
  GEE **Open Buildings 2.5D Temporal** height band in the footprints driver to emit per-cell mean height / built
  volume server-side (task #122). Both are driver enhancements + one re-run each; neither needs a post-hoc scan.
- **M3.4b wind-transport — OPEN (last M3 piece).** Per-cell wind field (dir+speed) + `signal.fire` as an upwind
  FRP-weighted term. Lower urgency: FIRMS returns 0 fires pre-burning-season (0 until Oct–Nov).

**M4 — models (pipeline built + proven, 2026-09-05).** `pm25-model@0.2.0` (engine) reads the **materialised
feature store** — the `air.feature_matrix@0.1.0` manifest `pm25-features@0.7.0` writes → one Parquet blob (33
features incl. lags + H3-neighbour) — instead of rescanning 13 raw scopes (the read-pattern fix; no read-replica
needed). It trains the ADR sequence (baseline_cams / baseline_mean / Ridge / RandomForest / **XGBoost**) with
**leave-one-station-out** CV and exact **TreeSHAP** contributors (xgboost `pred_contribs`, no external shap lib).
`sklearn`+`xgboost` hot-patched into runtime-manager (BAKE into an ML runtime image — see below). Lifecycle proven
end-to-end: govern manifest → certify → publish → install → manifest→Parquet load → train. **Caveat:** a clean
final RMSE table was hard to capture because engines execute **in-process in the shared runtime-manager** — a
slow/stuck run blocks the next and needs a service restart; the fix is a dedicated **ML runtime profile** (M5d), and
with only 49 CPCB labels at one hour this is a *pipeline test*, not a production model (leave-station-out on 49 pts
is high-variance — report CV variance, not point RMSE). Generalisation of the two engines → a self-serve
"train on your governed data" AI-Studio is scoped as tasks #193–196 (see [[ai-studio-train-on-governed-data]]).

**M3.5 — historical label corpus (bootstrap DONE, 2026-09-05).** The M4 bottleneck was *labels*, not features:
49 CPCB points at one hour can't validate anything. `openaq-archive@0.1.0` (driver) walks OpenAQ's **anonymous S3
archive** (`s3://openaq-data-archive`, one gzip-CSV per station per day) for the AOI's stations over a bounded
window and ingests every hourly µg/m³ into `air.sensor_reading` — the **same schema** the live `air-sensors`
driver writes, so `pm25-features` treats archive + live labels identically. First run (station 8118, New Delhi,
`LOCATION_IDS=8118`, `DAYS_BACK=120`): **2,791 REAL hourly PM2.5 readings**, window **2026-05-04..2026-09-01**,
~96% hourly coverage → new-delhi `air.sensor_reading` now **2,840** (49 live CPCB + 2,791 archive), verified
readable by the `pm25-features` reader token, source-attributed (`source=openaq-archive`, `prov.source_ref →
ref.source/openaq`, ODbL-1.0, `s3_key` anchor). Enabling fix: the broker (`secrets.py /fetch`) used to UTF-8-decode
every body → corrupted gzip; it now returns **`body_b64`** (base64) for binary content-types so `.csv.gz` rides
through intact (hot-patched into `airawat-secrets`; **BAKE into the `reference` image**). **Still open before real
supervised M4:** feature↔label **temporal alignment** — the archive gives historical labels, but the feature
drivers write only the latest-hour snapshot; backfill historical features over the same window via the **Open-Meteo
archive/reanalysis API** (CAMS + ERA5 for the exact hours) before leave-station-out / temporal-holdout numbers mean
anything. Scaling the corpus to all Delhi stations is a config-only rerun (drop `LOCATION_IDS` → keyed bbox discovery).

## Constraints (carried from the brief §23, enforced as review gates)

1. H3-9 is the indexing grid, not a physical-resolution claim; retain source resolution + provenance.
2. Do not manufacture spatial detail by resampling coarse fields. **AOD ≠ PM2.5.** Missing satellite data is
   expected and explicitly modelled.
3. Boundary-layer height, humidity, wind, and **regional transport** are first-class; wind direction gates how
   fires/industry/traffic influence a cell.
4. No random-split-only evaluation; **leave-station-out** is an acceptance criterion. **No synthetic substitution**
   — a driver fetches real data or fails loudly (platform rule).
5. XGBoost is the first serious production model; Random Forest is a benchmark; a GNN earns its place only by
   beating XGBoost under rigorous holdout. Estimates are **advisory** — the Action Loop / decision spine acts,
   not the model.

## Consequences

- **Positive:** reuses ~two-thirds of the required drivers + the whole governed spine; each new source is an
  independent, certified, provenance-tracked driver; the model is Studio-editable and explainable; every estimate
  is reproducible and carries uncertainty; the same machinery generalises to any baseline city (not Delhi-hardcoded).
- **Costs / risks:** GEE quota + key handling for the new EO drivers (Vault, per-tenant); the Parquet training
  materialisation is a new artefact class to manage lifecycle for; CPCB access for Delhi needs a real key;
  hourly historical backfill over 24k cells is a genuine data-volume + runtime cost (batch + incremental).
- **Non-goals (now):** the GNN/temporal-Transformer forecast; commercial traffic ingest; sub-hourly modelling.
  These are M7+ and gated on the nowcast being reliable first.

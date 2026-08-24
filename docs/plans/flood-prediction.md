# Plan — Flood Prediction (pluvial) for AirawatOS: capability-tiered forecast + Flood App + AI reformatter

**Status:** active design (parked for build after Nashik baseline settles) · **Owner:** City Scan / Intelligence track
· **Supersedes:** ponding-pluvial-flood-pipeline.md (that doc = the earlier static-index port; folded in here)
· **Relates to:** ADR-0060 (L0–L4 ladder), ADR-0029 (decision spine — AI advises, never decides),
ADR-0058 (interaction receipts / LLM provenance), [city-baseline-wave1-physical-foundation.md](city-baseline-wave1-physical-foundation.md)

> Persisted so the design survives context resets. Read the whole file before building. Three
> deliverables: **(A)** a better, capability-tiered flood-prediction algorithm; **(B)** a **Flood App**
> that lets a city stand up flood data it has; **(C)** a reusable **AI-assisted reformatter** component.

---

## 0. Why change the algorithm

AirOS's stormwater pipeline produces a **standing percentile `risk_score` (0–1)** — a screening index.
It cannot say **how deep**, **when**, or **under which storm**. The upgrade is an **event-based,
rainfall-driven forecast in physical units (water depth over time)** that **uses the data a city
actually has** — buildings, drains, roads, forecast rain — and **degrades gracefully** when a layer
is missing. It plugs into the flood **decision loop that already exists live in Airawat**
(`risk.flood → signal.alert → flood-advisor → case/task/inbox`).

Guiding principle (capability-low / instantiation-high, per ADR-0060): **one algorithm, tiered by
available data.** A city with only terrain still gets a forecast (lower confidence, honestly flagged);
a city that uploads its drainage network gets a real hydraulic result. Every row records which tier
produced it.

---

## A. The better algorithm — capability-tiered rain-on-grid forecast

**Model:** event-based **mass-balance ("bucket") routing** on the H3 grid, stepped over the forecast
horizon and driven by **per-cell forecast rainfall**. Per cell *c*, per timestep Δt (15–60 min over
~48 h):

```
ΔStorage(c) = Rain_in(c,t) + Route_in(c) − Infiltration(c) − Drainage_out(c) − Route_out(c)

  Rain_in       = P(c,t) · A_cell · C_runoff(c)          ← forecast rain × runoff coefficient
  C_runoff      = SCS Curve Number from IMPERVIOUS FRACTION
                    impervious = building_coverage + road_fraction + landcover_impervious   ← BUILDINGS lever #1
  Infiltration  = pervious/green fraction · loss rate    (Horton / CN initial abstraction; soil HSG if available)
  Drainage_out  = capability-tiered sink (see below)      ← DRAINS lever
  Route_out/in  = surface water above the sink spill level flows to the downstream cell on the
                  TERRAIN-CONDITIONED D8 network (already built); roads act as preferential channels
  Depth(c)      = Storage(c) / (A_cell − footprint_area(c))                                   ← BUILDINGS lever #2
                    (buildings shrink the ponding area → water gets DEEPER; height/levels → which floor floods)
```

### The drainage term — three tiers (the heart of "use what's available")

| Tier | Data present | `Drainage_out(c)` | Confidence |
|---|---|---|---|
| **T3 hydraulic** | municipal network + **capacity** (revived `cell.drainage`: `drain_capacity_m3_s`, `design_rainfall_mm_hr`, silt/condition, pumps, outfalls) | `min(storage_rate, Q_drain(c))`, de-rated by `silt_level_pct` / condition / encroachment; routed to outfalls | high |
| **T2 geometry** | **OSM nala/drain linework** (`geo.osm_feature` layer=waterway / `geo.hydro_feature` feature=drain) — *we have this today* | per-cell sink rate ∝ **drain density**, **calibrated** against ground truth; encroachment/known-waterlogging points reduce it | medium |
| **T1 terrain-only** | none | uniform nominal loss + terrain sink model only (≈ today's behaviour) | low (flagged) |

Same shape everywhere; only the drainage term swaps. `method.tier` + `confidence` on every row make
the data-dependence explicit and auditable.

### Outputs
Per cell × timestep: `water_depth_m`, `is_flooded` (depth > threshold), inflow/drainage rates.
Rolled up over the horizon: `peak_depth_m`, `time_to_peak_h`, `duration_h`, `flood_class`,
`dominant_hazard` (ponding / barrier / convergence / runoff — kept from the AirOS join).
**→ animate on the City Scan time-scrubber** (the `observed_at = valid_time` trick already makes the
scrubber play a forward outlook). Then **depth → impact**: people / buildings / roads affected
(the exposure join, now depth-aware instead of percentile-only).

### Physical inputs the model consumes (what each contributes)
- **`cell.terrain` (+ morphometry)** — the sink substrate + D8 routing surface. *(Morphometry driver is the top fidelity lever — see ponding-pluvial doc Appendix A.)*
- **`cell.landcover`** — impervious & pervious fractions → runoff/infiltration.
- **`cell.buildings` / `geo.building`** — footprint coverage → impervious (runoff) **and** ponding-area reduction (depth); height/levels → floor-damage.
- **roads (`geo.osm_feature`)** — impervious + surface-flow channels + embankment barriers (breach detection).
- **drains (tiered, above).**
- **`cell.weather_forecast`** — **the forcing.** Per-cell hourly forecast, ~48 h (Airawat driver `components/drivers/weather-forecast` already writes a per-cell `series:[{t,precip_mm,…}]`). **This is the single missing wire:** the current `flood-risk` engine consumes only a scalar `met.forecast.rainfall_mm`; route the per-cell series in.

### Calibration & validation (makes the tiers trustworthy)
Tune `C_runoff` and the T2/T1 drainage sink rates against ground truth:
- **`signal.report` where `category_hint = waterlogging`** — citizen incidents (AirOS, needs porting).
- **Sentinel-1 SAR `cell.flood`** (`water_fraction`, `change_from_baseline`) — observed standing water (AirOS driver exists, dormant; needs re-activation).
- **`geo.camera`** — visual confirmation at a cell (AirOS, live).
- **Optional ML susceptibility** (RF / logistic) on `{TWI, HAND, sink fill_depth, impervious_frac, drain_density, upslope_area, rain_intensity}` → per-cell flood probability, blended with the physical model. Reuses the existing PM2.5-fusion pattern (RF/XGBoost).

### Plugs into the existing decision loop (zero new plumbing)
Per-cell forecast depth → `risk.flood.score` → existing `0.70` threshold → `signal.alert` →
`platform.subscription` auto-fires `flood-advisor` → `governance.recommendation` (cited to SOP) +
`platform.case`/`task`/`inbox_item`. AI advises; a human authority decides (ADR-0029).

---

## B. Flood App — city sets up flood data it has (like City Setup)

A guided app (mirrors City Setup's readiness panel) that lets a non-technical city operator stand up
flood prediction:

1. **Readiness check** — which input layers exist for this tenant (terrain, landcover, buildings,
   roads, forecast rain, OSM drains) → per-layer status; shows the **tier** the model can run at now.
2. **Provide missing flood data** — upload/enter what isn't auto-available:
   - municipal **drainage network + capacity** (populates revived `cell.drainage` → unlocks **T3**),
   - **encroachment / known-waterlogging points**, historical flood extents / incident records,
   - **design storm**, pump stations, outfalls.
3. **Upload in a specified format** — template download for each governed schema; **user validates a
   preview before commit** (no silent authoritative writes).
4. **Run + view** — triggers the flood pipeline; shows the animated depth forecast + ranked priority
   sites + the confidence/tier badge.

Reuses City Setup patterns already built: server-side **URL fetch** + **512 KB chunk upload** to the
filestore, per-layer progress panel, install-as-grant run authorization.

---

## C. AI-assisted reformatter — a reusable, horizontal component

Cities' data never arrives in our schema. A **general-purpose certified component** ("Schema
Reformatter") reformats an arbitrary input file into a governed target schema, **AI-proposed,
human-validated**. It is NOT flood-specific — City Setup, Data apps, and the Flood App all call it.

- **Interface (on-demand invoke / `platform.interaction`):** request carries
  `{ input_ref: <filestore-id | url>, target_schema: "<schema@version>", output_ref: <filestore-id>, hints? }`.
- **Action:** download input (filestore **or** URL, behind the same SSRF guard as the OSM url-fetch) →
  inspect columns/structure → **LLM proposes a field mapping** to the target schema (Airawat/kimi via
  the LLM gateway) → transform rows → **validate against the schema** (same jsonschema Draft-2020-12
  validator the registry uses) → write reformatted output back to the filestore under `output_ref` →
  return a **mapping report + per-row validation errors**.
- **Human-in-the-loop:** the user **reviews & validates** the mapping/preview before anything is
  ingested. AI proposes, human approves (ADR-0029). The reformatter never writes to the registry
  itself — it only produces a file; ingestion is a separate, explicit step.
- **Provenance:** emits an `interaction.receipt` (LLM egress, ADR-0058); output file records
  source input_ref + model + mapping.
- **Composable:** "give me input file + output file, and the target schema, I hand you back a
  conformant file." Any app orchestrates it via filestore refs.

---

## Grounded data inventory (from the repo scan — what EXISTS vs the GAPS)

**Present & usable now:**
- Terrain (elevation), landcover, per-cell rainfall climatology, buildings (footprint + area; **height/levels in AirOS via Open Buildings Temporal**), roads, hydrology (HAND / flow-accumulation / `flood_susceptibility` in Airawat).
- **OSM drain/nala geometry** — `geo.osm_feature` (layer=waterway: river/stream/canal/**drain**/ditch) + `geo.hydro_feature` (feature_type=drain). *(This is the "we have drainage data" — geometry, T2.)*
- **Per-cell hourly forecast** — Airawat `components/drivers/weather-forecast` writes a per-cell `series` (~48 h). **Exists but not wired to the predictor.**
- **Live flood decision loop** — Airawat `risk.flood → signal.alert → flood-advisor → case/task/inbox`.
- **Time-scrubber** — mature in AirOS `apps/city-explorer/.../TimeSlider.tsx` (daily+hourly, play/animate).

**Gaps to build:**
- **Drainage capacity (T3):** revive AirOS retired `schemas/retired/cell/cell.drainage.schema.json` (`drain_capacity_m3_s`, `design_rainfall_mm_hr`, silt/condition, pumps, outfalls) as a governed schema; **no driver ever populated it** → the Flood App upload path + reformatter fill it.
- **OSM drain extraction in Airawat:** the new platform's OSM drivers capture only roads + point facilities — **no waterway/culvert/storm_drain line extraction**. Extend to capture drains (unlocks T2 automatically). Add `tunnel=culvert` + `man_made=storm_drain` (absent in both repos).
- **The forcing wire:** route per-cell `cell.weather_forecast.series` into the `flood-risk` predictor (today: scalar `met.forecast.rainfall_mm`).
- **The 4 hydrology engines** (terrain-conditioning → flow-balance → flow-routing → the new depth model) ported as certified Airawat components (geospatial runtime).
- **Terrain morphometry driver** (biggest fidelity lever; ponding-pluvial doc Appendix A).
- **Calibration layers** (SAR `cell.flood` re-activation, `signal.report` waterlogging, cameras) — AirOS-only / retired → port.
- **No depth-damage / plinth / ground-floor-elevation / building-use anywhere** — depth→damage stays coarse (count/area/commercial-weighted) until a vulnerability layer is added.

---

## Build slices (when picked up)

1. **Forcing wire (fastest win):** feed per-cell `cell.weather_forecast.series` into the `flood-risk`
   predictor → per-cell, time-varying `risk.flood` driving the existing alert loop. Proves "live."
2. **Reformatter component (C)** — horizontal; unblocks every upload path. Build + certify first.
3. **Drainage:** (a) extend Airawat OSM extraction to drains/canals/culverts → **T2** everywhere for
   free; (b) revive `cell.drainage` schema + Flood-App upload (via reformatter) → **T3**.
4. **Depth model:** port terrain-conditioning + flow-balance + flow-routing, then the new
   **rain-on-grid depth engine** (tiered drainage term) → `cell.flood_forecast` (depth × time).
5. **Flood App (B):** readiness panel + data-setup wizard + animated forecast view.
6. **Calibration:** port SAR `cell.flood` + waterlogging `signal.report`; tune params; optional ML
   susceptibility blend.
7. **Morphometry driver** (fidelity) + depth→damage vulnerability (needs plinth/use data via Flood App).

Log honest limits to LIMITATIONS.md at each slice (esp. tier/confidence of every produced cell).

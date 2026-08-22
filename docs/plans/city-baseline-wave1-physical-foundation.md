# Plan — Complete the City Digital Baseline (Wave 1: Physical Foundation)

**Status:** active · **Owner:** City Setup / City Scan track · **Relates to:** ADR-0060 (City Scan / L0–L4 ladder), ADR-0062/0063 (invocation + governed verbs)

> Persisted so the plan survives context resets. If you're picking this up cold, read this
> whole file before touching the `city-baseline` pipeline.

## The actual product (do not lose this again)

Airawat OS is on-demand public infrastructure: **thousands of cities self-onboard.** A municipal
commissioner registers a ULB → Airawat **automatically pulls the freely-available satellite /
weather / open-API datasets** for that AOI → derives a standardized **Urban Base Model** → emails the
commissioner when the baseline is ready. No procurement, no bespoke IT project. Level 1 must require
**almost zero technical effort from the city** — the commissioner clicks "Set up my city" and Airawat
does the heavy lifting.

**Maturity ladder (progressive, measurable):**
- **L0 Requested** — city identity + boundary + H3 hierarchy + workspace established.
- **L1 Airawat Baseline** — national/open/satellite datasets processed automatically (**this plan**).
- **L2 City Enriched** — city's own authoritative datasets incorporated (supersede/complement, provenance kept).
- **L3 Connected City** — live municipal systems emit data/events.
- **L4 Intelligent City** — predictions, simulations, agents, marketplace solutions run continuously.

**Data architecture (the substrate everything else stands on):**
```
Observation → Feature → Cell → Intelligence → Decision
   L0            L1        L2        L3            L4
raw EO/vectors  buildings  H3-9    risk scores   plans/budgets
DEM/rasters     roads      cells   anomalies     RCP recommendations
municipal data  drainage   ind-    scenarios
                parcels    icators
```

**Non-negotiable architectural rules:**
1. **Do not reduce all source data to one H3 resolution.** Preserve native geometry (L0/L1):
   terrain raster 10–30 m, land cover 10 m, building footprints as polygons, roads/drains as line
   networks, water bodies as polygons. H3 is the *analytical index*, **not the source of truth**.
2. **H3-9 is the canonical national analytical grid** (~0.1 km²/cell) — the default Urban Intelligence
   Cell. Allow H3-8 (city/state dashboards) and H3-10 (neighbourhood detail). *Treat r9 as a starting
   hypothesis to be benchmarked against Indian ward size, not a frozen decision.*
3. **Hydrology and terrain must NOT be aggregated too early.** A drain occupies ~2 % of a 100 m cell
   but matters enormously. Keep flow-direction/accumulation rasters, stream lines, catchment polygons
   at source resolution; summarize *into* H3-9 (min elevation, max flow-accum, fraction low-lying,
   distance-to-primary-drain, catchment_id).
4. **Every derived attribute carries provenance:** `source`, `source_date`, `model_version` /
   `method`, `confidence`, `last_updated`. Government decisions will rely on this; an authoritative
   municipal dataset must be distinguishable from an AI-derived estimate. (Enforced by house rule R5 +
   ADR-0041 lineage; already wired for measures.)
5. **First-class Indian sources:** make Bhuvan / NRSC + open EO (Sentinel-2 10 m, Copernicus/SRTM DEM
   ~30 m, Dynamic World, GHSL/WorldPop) + authoritative state/city data first-class providers — not an
   afterthought behind international datasets.

## Where the automated baseline stands today

The `components/pipelines/city-baseline` pipeline (runs on "Initiate Setup", keyed off `space.aoi`)
currently produces only a **slice of Wave 1**:

| Wave-1 physical layer | Free source | L0/L1 native | L2 (H3-9) | Status |
|---|---|---|---|---|
| Land cover | Dynamic World (GEE) | — | built% / veg% (`cell.builtup`/`cell.greencover`) | ✅ |
| Climate — temperature / heat | Open-Meteo | points (`environment.lst_observation`) | `cell.heat` | ✅ |
| Terrain — elevation + slope | Copernicus DEM (GEE) | — | `geo.terrain` | ✅ elevation+slope (no aspect/flow) |
| Coverage & trust report | — | — | `city.coverage` | ✅ |
| **Roads** | OSM / Overpass | `geo.osm_feature` | road density | 🟡 `osm-roads` driver ready, **NOT wired into baseline** |
| **Hydrology** — flow-accum, drainage, catchments, water bodies, flood-plain | **derive from the DEM already fetched** | streams (lines), catchments/water (polygons) | dist-to-drain, flow-accum, low-lying% | ❌ **biggest gap; the flood substrate** |
| **Buildings** — footprints, density, imperviousness | OSM / Overpass | `geo.building` | building count/density | ❌ no driver |
| **Green/blue infra** — parks, lakes, wetlands, streams | OSM + DW surface water | polygons | blue% | ❌ |
| **Climate — rainfall / ET** | Open-Meteo / ERA5 | points | `cell.rainfall` | ❌ (temperature only) |
| **Urban growth** — 1y/5y change detection | multi-year DW / Landsat | — | built-up change | ❌ |
| **Population density** | GHSL / WorldPop | raster | `cell.population` | ❌ |
| **Critical facilities** — schools/hospitals/utilities | OSM | `geo.facility` | count / accessibility | ❌ |
| **Admin geography** — ward / zone | Bhuvan / city-provided | polygons | `ward_id` tag on cells | 🟡 AOI only, no wards |

## Source: PORT from the legacy AirOS driver library (do not author from scratch)

`Projects/AirOS/jobs/driver/` already has working drivers for nearly every Wave-1 layer, with known
free sources and output schemas. **This is a port, not greenfield.** Inventory (reviewed 2026-08):

| Wave-1 layer | AirOS driver | Free source | Writes today |
|---|---|---|---|
| Hydrology / terrain detail | `geospatial/dem-morphometry` | GEE SRTM 30 m | `cell.terrain_detail` |
| Water bodies | `geospatial/waterbodies` | OSM (PBF/Overpass) | `cell.waterbodies` |
| Buildings | `geospatial/google-open-buildings` | GEE Open Buildings | `cell.buildings` |
| Population | `geospatial/population-ghsl` | GHSL raster | `cell.population` |
| Roads | `infrastructure/osm-roads` · `geospatial/osm-vectors` | Overpass/PBF | `cell.roads` · `geo.osm_feature` |
| Facilities (schools/hospitals) | `infrastructure/osm-social` | Overpass | `cell.social_infra` |
| Utilities | `infrastructure/osm-utilities` | Overpass | `cell.utilities` |
| Rainfall | `satellite/gpm-precipitation` · `weather/open-meteo` | GEE GPM / Open-Meteo | `cell.precipitation` |
| Transit | `geospatial/transit-features` | PBF/Overpass | `geo.transit_feature` · `cell.transit_access` |
| Admin wards | `lgd/ward-sync` | SBM parquet | `lgd.ward` |
| Flood (SAR) | `satellite/sentinel1-flood` | GEE Sentinel-1 | `cell.flood` |
| Flood risk index | `climate/flood-risk` | terrain+water composite | `cell.flood_risk` |

Also available for later waves: air quality (`satellite/{tropomi,maiac-aod}`, `air-quality/station-readings`),
demographics (`census`, `age-distribution`, `socioeconomic`, `housing-quality`), urban-change
(`satellite/alpha-earth-embedding`, `dynamic-world` multi-year), facilities research (`research/facilities`).

**Two things every port must fix (not just copy):**
1. **I/O model** — all 42 AirOS drivers use the old `_common` direct-registry client
   (`BatchClient`/`RegistryClient`/`get_aoi`, reading cells from `cell.h3_metadata`). Re-point to the
   **kernel broker**: `/v1/read` (space.aoi), `/v1/fetch` (egress), `/v1/write`, `X-Run-Token`; enumerate
   cells from the run's `space.aoi` bbox; apply `_common/ids.py`, schema-naming, and the **cross-tenant +
   AOI-membership write guards**. (This is the airawat-driver-porting-plan pattern; `osm-roads` was
   rebuilt this way — it writes native `geo.osm_feature`, unlike the AirOS original's `cell.roads`.)
2. **Native geometry (plan rule #3)** — the AirOS drivers write **H3-only** (`cell.*`). That is exactly
   the "aggregate hydrology/terrain too early" anti-pattern this plan forbids. Each physical port must
   emit **BOTH** L1 native geometry (`geo.*`: stream lines, catchment polygons, building footprints,
   water polygons) **AND** the L2 H3 index (`cell.*`). `osm-vectors`/`transit-features` already emit
   native geometry; DEM-derived hydrology must be extended to emit streams + catchments as `geo.*`.

## Build sequence (each layer = a certified driver wired into `city-baseline`)

Every layer is delivered the way `osm-roads` was: confined component, only I/O is the kernel broker,
keyed off the run's `space.aoi`, deterministic ids via `_common/ids.py`, **cross-tenant + AOI-membership
write guards** (added to `landcover-dw` / `cell-indexer` this session), provenance block on every
measure, real-data-or-fail (no synthetic fallbacks). Wire into the pipeline `steps` so **every future
city gets it automatically.** Port from the AirOS source named above rather than starting blank.

1. **Roads** — wire the ready `osm-roads` driver into `city-baseline`; add the roads layer to City Scan.
   *(Immediate — driver already hardened.)*
2. **Hydrology** — new engine deriving from the Copernicus DEM already pulled: flow-direction →
   flow-accumulation → stream network (lines) + catchments (polygons) + flood-susceptibility. Keep
   native; summarize to H3-9 (`distance_to_drain`, `flow_accum`, `low_lying_fraction`, `catchment_id`).
   Highest architectural value; the substrate flood AI needs.
3. **Buildings** — `osm-buildings` driver (mirror `osm-roads`) → `geo.building` footprints; index to
   `cell.buildings` (count, area, density, imperviousness proxy).
4. **Population** — `population-ghsl` driver → `cell.population` from real GHSL/WorldPop raster.
5. **Critical facilities** — `osm-facilities` driver → `geo.facility` (schools, hospitals, utilities,
   govt); enables exposure + accessibility.
6. **Round out observability** — climate rainfall (Open-Meteo/ERA5 → `cell.rainfall`), green/blue infra
   (OSM water + DW), urban-growth change detection (multi-year DW).
7. **Admin wards** — ward/zone polygons (Bhuvan or city-provided at L2); tag every cell with `ward_id`
   so queries roll up India → State → ULB → Ward → H3-8 → H3-9 → H3-10 → raw geometry.

**Recommended starting point:** #1 Roads (wire ready driver) + #2 Hydrology (derive from the DEM we
already fetch) — the two that complete the core physical skeleton and unlock flood.

## Definition of done for Wave 1

A commissioner clicks "Set up my city" and, with no technical effort, the workspace comes back with:
terrain + slope, **hydrology (catchments/drainage/flood-susceptibility)**, land cover, built-up +
**building footprints**, **roads**, green/blue cover, temperature + **rainfall**, **population**,
**critical facilities**, and admin geography — native geometry preserved, indexed to H3-9, every
attribute carrying source/date/confidence, with a **coverage & trust report** stating what is
authoritative vs AI-derived and where the gaps are. City Scan renders all of it; the marketplace can
then say "these N solutions can run immediately on your data."

## Later waves (out of scope for this plan, recorded so we don't re-derive them)

- **Wave 2 — Climate & environmental observability:** rainfall, LST, heat islands, air quality,
  vegetation health, surface-water change, drought, urban expansion (continuous observation).
- **Wave 3 — People & assets:** population, schools, hospitals, govt buildings, markets, transport
  nodes, water/sewer/electricity where available → exposure calculation.
- **Wave 4 — Service delivery:** water, sanitation, solid waste, roads, streetlights, grievances,
  property tax, building approvals, trade licenses, public health — each event spatially indexed.
- **Wave 5 — Municipal finance:** parcels, assessed values, tax collection, permits, capex/opex, land
  values on the same fabric → spatial public-finance model.

Flagship product = **Airawat City Scan**, not a chatbot: pick any Indian city, minutes later see City
Structure / Natural Systems / Climate / Risk / People / Change / Planning, all API-accessible.

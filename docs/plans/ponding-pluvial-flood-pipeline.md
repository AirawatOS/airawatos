# Plan — Ponding / Pluvial-Flood Pipeline (port from AirOS to AirawatOS)

> **⚠️ Superseded by [flood-prediction.md](flood-prediction.md)** — the capability-tiered predictive
> algorithm, the Flood App, and the AI reformatter. This doc is retained for the AirOS pipeline
> reference and **Appendix A (terrain-morphometry driver requirements)**, which the new plan cites.

**Status:** parked (pick up after Nashik baseline settles) · **Owner:** City Scan / Intelligence track
· **Relates to:** ADR-0060 (L0–L4 ladder), [city-baseline-wave1-physical-foundation.md](city-baseline-wave1-physical-foundation.md)

> Persisted so the plan survives context resets. This is an **L4 (Intelligence)** capability that
> stands on the **L1 (physical)** baseline. Do not start until the raw input layers below exist for
> the target city.

## What this delivers

A per-cell **pluvial (rain-driven) flood-risk** layer — `cell.pluvial_risk` — that identifies
**ponding sites**: cells sitting in a terrain sink where runoff collects, ranked city-wide by
`priority_rank`, each tagged with a `dominant_hazard` (`ponding` / `barrier` / `convergence` /
`runoff`), a `fill_depth_m`, and — for barriers — a `breach_point_h3` (where a culvert/underpass
should convey water through a dammed drainage line). Pluvial only; riverine is a separate model.

This is the **most decision-useful** water product: it turns a hydrology map into a ranked
intervention list ("these 20 cells: N people + M buildings behind an embankment-dammed drain").

## How it works — the 4-stage stormwater pipeline

Ported from AirOS `jobs/pipeline/analytics/` (kept the algorithms; rewrap as certified engines).

```
        RAW PHYSICAL LAYERS (drivers, L1)                        DERIVED (engines, L4)
  cell.precipitation ─┐
  cell.landcover ─────┼──▶ ① flow-balance ─────▶ cell.balance ──────┐   runoff ratio "how flashy"
  cell.terrain ───────┼──▶ ② terrain-conditioning ▶ cell.terrain_conditioned ─┐  ★ SINK DETECTOR
  cell.flood (SAR) ───┤      priority-flood + classify each sink              │
  geo.osm_feature ────┘         spurious / real / barrier                     │
  (roads + rail)                                                              │
  cell.terrain ──────────▶ ③ flow-routing ───────▶ cell.flow ────────────────┤   accumulated_flow + is_sink
  cell.balance ──────────/   D8 steepest-descent accumulation                 │
                                                                  ▼           ▼
  cell.population ───────────────────────────────▶ ④ flood-exposure-join ▶ cell.pluvial_risk
  cell.buildings  ───────────────────────────────/   hazard × exposure → priority_rank
```

- **② terrain-conditioning is the actual ponding detector.** Wang-Liu/Barnes **priority-flood** over
  the H3 elevation surface, detects every raw local minimum, then **classifies** each:
  - `spurious` — fill depth < ~1 m, nothing corroborates → DEM noise → filled.
  - `real` — corroborated by SAR-observed water, `is_depression`, concavity, valley TPI, or a deep
    fill (≥3 m) → **preserved** as a genuine basin.
  - `barrier` — a drainage line **dammed by an embankment** (a major road / rail line crosses the
    sink rim) → **breach candidate**; emits `breach_point_h3` + `breach_depth_m`.
  Writes a *selectively conditioned* elevation (spurious pits filled, real/barrier basins kept) so
  routing runs on a trustworthy surface. Raw `cell.terrain` is never mutated.
- **③ flow-routing** — steepest-descent D8 accumulation on the conditioned surface;
  `accumulated_flow` = local runoff + everything upstream; local minima are `is_sink` (ponding).
- **④ flood-exposure-join** — `hazard` (0.55·pct(accumulated_flow) + 0.45 barrier | 0.30 ponding) ×
  `exposure` (0.55·pct(population) + 0.35·pct(buildings) + commercial boost) → `risk_score`,
  `risk_class`, `priority_rank`, `rationale`.

Both ① and ③ are **recipe-driven** (`balance.recipe`, `routing.recipe`) — the same engines route
energy/pollution/heat with a different source + potential field. Reuse, don't fork.

## Layers required

**Raw physical inputs (7) — must exist first (L1 baseline):**

| Layer | Role | AirOS producer | Nashik status |
|---|---|---|---|
| `cell.terrain` | elevation + morphometry substrate | `geospatial/terrain-dem` | ✅ present (elevation only — see caveat) |
| `cell.flood` | SAR-observed standing water (corroborates *real* sink) | `satellite/sentinel1-flood` | ❌ not ingested |
| `cell.landcover` | impervious fraction → runoff coefficient | `satellite/dynamic-world` | ✅ present |
| `cell.precipitation` | rainfall = source term | `satellite/gpm-precipitation` / rainfall | ✅ rainfall present |
| `geo.osm_feature` (roads + rail) | embankment lines that dam drainage → barrier | osm-vectors | ❌ Roads failed (404) |
| `cell.population` | exposure — who | population-ghsl | ⏳ pending |
| `cell.buildings` | exposure — what | buildings driver | ✅ present |

Plus 2 **recipes** (governed config): `balance.recipe`, `routing.recipe`
(seed via AirOS `scripts/bootstrap/seed_balance.py`, `seed_routing.py` — re-express as governed
`*.recipe` records in AirawatOS).

**Derived (produced by the 4 engines):** `cell.balance` → `cell.terrain_conditioned` → `cell.flow`
→ `cell.pluvial_risk`.

*(Adjacent, simpler: `cell.flood_exposure` — coarse standing susceptibility from elevation-percentile
+ river-proximity + flatness. That's the riverine/screening layer, NOT the ponding model. Already a
candidate for the baseline.)*

## The terrain-morphometry gap (biggest fidelity lever)

The sink classifier is designed to lean on DEM **morphometry** — `is_depression`, `curvature`,
`terrain_position_index`, `flow_accumulation`. But AirOS's `terrain-dem` driver only emits
`mean_elevation_m`, `slope_estimate_deg`, `elevation_range_m` — **it never computes the morphometry**
(the conditioning code even notes `flow_accumulation` is unpopulated). So today the classifier
degrades to fill-depth + SAR water + OSM-embankment signals only.

**A proper terrain-morphometry driver is the single biggest quality improvement.** It also must run
on a **native-resolution raster**, not H3-8 aggregates — H3-8 (~0.7 km cells) destroys the sub-cell
relief that actually causes ponding. Its requirements are captured in
[Appendix A](#appendix-a--terrain-morphometry-driver-requirements) below.

## Work breakdown (when picked up)

1. **Fix Roads** for the target city (barrier detection) — likely the same install-as-grant /
   OSM-asset-bind gap seen in the Nashik build.
2. **Add a Sentinel-1 flood driver** (`cell.flood`) — restores the "observed water" corroborator.
   Optional but high-value.
3. **Terrain-morphometry driver** (Appendix A) — native-res DEM → sinks/curvature/TPI/TWI/HAND →
   aggregate to H3, enrich `cell.terrain`. The fidelity unlock.
4. **Port the 4 analytics engines** as certified AirawatOS components (geospatial runtime where a
   raster stack is needed): terrain-conditioning, flow-balance, flow-routing, flood-exposure-join.
   Preserve `prov.component@version` and Tier-4 conformance samples.
5. **Seed the 2 recipes** as governed records.
6. **viz.layer + City Scan overlay** for `cell.pluvial_risk` (extruded reds; click → dominant hazard
   + rationale + breach point). AirOS reference: `scripts/bootstrap/seed_pluvial_risk.py`.
7. Verify end-to-end on one city; log honest limits to LIMITATIONS.md.

## Appendix A — terrain-morphometry driver requirements

**Input source (pick per maturity tier):**
- **L1 (automatic, free, global):** a native-resolution **DEM raster** for the AOI —
  - **Copernicus GLO-30** (`COPERNICUS/DEM/GLO30`, 30 m) — best free global quality today.
  - **NASADEM** / **SRTM GL1** (30 m) — older, voids over water/steep terrain.
  - **ALOS AW3D30** (30 m) — good alternative.
  Pull via GEE (already wired for other EO layers) or the dataset's S3/HTTP tiles, clipped to AOI.
- **L2 (city-enriched, gold standard for ponding):** a **LiDAR DTM** (1–5 m) if the ULB has one —
  resolves street-level sinks a 30 m DEM cannot see.

**Hard requirement — reproject to a projected metric CRS (UTM zone) before any slope/curvature**, so
gradients are in metres, not degrees. Compute per-pixel, then zonal-aggregate into H3 (keep native-res
sink geometry + the H3 rollup).

**Derived fields it should compute (enrich `cell.terrain`):**
- **Slope** (gradient magnitude) + **aspect**.
- **Curvature** — plan (convergence/divergence; negative = concave = water converges) + profile.
- **Terrain Position Index (TPI)** — cell minus neighbourhood mean; negative = valley/depression → sets `is_depression`, `landform_type`.
- **Topographic Wetness Index (TWI)** = ln(a / tan β) — the classic standing-water/ponding predictor.
- **Flow direction (D8 / D-∞) + flow accumulation** — upslope contributing area (drives routing + barrier signal).
- **Depression detection + fill depth** — priority-flood on the raster (`is_depression`, sink depth).
- **Height Above Nearest Drainage (HAND)** — strong flood/ponding predictor.
- **Landform classification** — geomorphon- or TPI-based (valley / depression / flat / ridge / slope).

**Tooling (geospatial runtime):** `richdem` (fill / flow-accum / curvature), `WhiteboxTools`
(comprehensive geomorphometry incl. HAND, geomorphons), `pysheds`, `gdaldem` (slope/aspect/TRI/TPI),
`rasterio` + `numpy`, `pyproj` (reprojection), `h3` (zonal aggregation). This is a **geospatial /
earth-observation runtime profile** job, not the coordination container.

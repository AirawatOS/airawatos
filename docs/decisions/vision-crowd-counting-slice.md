# Slice: vision-based crowd counting → crush risk

**Status:** Proposed / scaffolded (assign next free ADR number when promoted — do NOT reuse 0077).
**Relates to:** camera media plane (ADR-0077 in docs/decisions, pending renumber → 0078), crowd-safety / crush-risk
(Nashik Kumbh), decision spine (ADR-0029/0046), lineage (ADR-0041/0052).

## Why
The crowd-safety loop today is fed by **numbers**: `kumbh-crowd-sim` synthesises `cell.crowd_density` directly, and
`crush-risk-engine` turns density → `cell.crush_risk`. This slice puts **perception** in front of it — a camera frame
is **counted by AI**, and the count becomes the *same* `cell.crowd_density` the crush-risk loop already consumes.
Nothing downstream changes; we replace the *source* of the density from "a number" to "an image the AI counted."

    image (sim or real camera)  →  media.frame  →  crowd-count (AI)  →  cell.crowd_density  →  crush-risk-engine  →  cell.crush_risk → decision/alert

## Components (each a certified, broker-mediated component; no new downstream)
1. **`crowd-sim-vision`** (driver) — the image front-end for simulation. Per tick, per camera, composes a crowd
   **image** with a controllable headcount `K` (a `crowd_level` config + a surge scenario) and writes it as a
   `media.frame` (bytes → filestore, record cites the file). The ground-truth `K` is stamped in `prov.sim_headcount`
   so we can (a) validate the detector and (b) run the whole loop *before* the model is provisioned. Two image modes:
   `bank` (cycle real crowd photos dropped in `frames/<level>/`) or `composite` (paste person sprites from `sprites/`).
   In production this component simply does not run — real cameras + `rtsp-ingest` write `media.frame` instead.
2. **`crowd-count`** (engine) — the AI. Reads the latest `media.frame` per camera (granted), fetches the bytes via the
   broker, runs **person detection (YOLOv8/RT-DETR, class=person)**, counts, maps camera → H3 cell (from
   `camera.location`), computes `density_sqm = count / coverage_m2`, and writes:
   - `vision.detection` (NEW schema) — per-frame `{frame_ref, camera_ref, count, model, confidence}` — audit/lineage.
   - `cell.crowd_density` — the EXISTING shape `{cell, observed_at, density_sqm, headcount, capacity, prov}` so
     `crush-risk-engine` consumes it unchanged.
   Model unavailable? It falls back to `prov.sim_headcount` from the frame (scaffold mode) and logs it loudly — the
   loop still runs; swap in real weights and it becomes real perception with no other change.
3. **`crush-risk-engine`** — UNCHANGED. It already reads `cell.crowd_density` → density-band rules → `cell.crush_risk`.

## Governance & scale (why AirawatOS)
- Every count is **attributable**: `vision.detection` cites the content-addressed `media.frame` (`file_id` = sha2-256),
  so "the AI counted 812 here" is a replayable, audited fact (ADR-0041/0052), and `cell.crowd_density.prov` records
  `method="vision-count"` + `source_frame`.
- **Human-in-the-loop** stays at the decision spine: crush-risk → recommendation → a person admits → operator task.
- **Tiering for thousands of cameras** (see the vision-AI architecture note): this engine is Tier-1 (cheap detector,
  fans out per camera on a schedule). A Tier-0 health check gates dead feeds; a Tier-2 VLM (Kimi K3) only explains
  escalations. Counting does NOT need a VLM — a YOLO-class detector is the right, cheap tool per frame.

## New schema — `vision.detection` (govern first, additionalProperties:false)
required: `schema,id,camera_ref,frame_ref,count,observed_at,prov`
props: `count:int`, `by_class:{person:int,…}`, `model:str`, `confidence:num`, `boxes:[[x,y,w,h,score]]` (optional),
`camera_ref:id`, `frame_ref:id (→ media.frame)`, `observed_at:str`, `space:{h3}`, `prov:obj`.

## Runtime
`crowd-count` declares an **ML runtime profile** (ADR-0073 tail): python + ultralytics + a pinned YOLOv8n weight as a
bound asset. CPU is fine for a handful of sim cameras (yolov8n ~tens of ms/frame); a GPU profile is the answer at
hundreds+. Weights are a governed component asset, not fetched at runtime.

## Deploy steps (when promoted from scaffold)
1. Govern `vision.detection` (network schema-propose → approve → kernel cache refresh).
2. Certify + install `crowd-sim-vision` (driver) and `crowd-count` (engine) into the demo tenant (nashik); grant
   crowd-count read `device.camera,media.frame` + write `vision.detection,cell.crowd_density`.
3. Bind the YOLO weight asset; add the ML runtime profile.
4. Schedule `crowd-sim-vision` (e.g. every 60s) and `crowd-count` (every 60s) — sim writes frames, count consumes them.
5. crush-risk-engine already scheduled → `cell.crush_risk` + City Scan overlay light up from *counted* images.

## Demo narrative
Dial a camera's `crowd_level` up → the sim frames get denser → **crowd-count detects more people** → `density_sqm`
rises → `crush-risk-engine` flips the cell to elevated/critical → operator gets the alert. Same loop as today, but the
number now comes from an image the AI actually counted — and you can point at the frame it counted.

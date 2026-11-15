# ADR-0134 — Urban visual intelligence benchmark in Model Lab

**Status:** Proposed · **Date:** 2026-11-15
**Builds on:** ADR-0077 (camera media plane), ADR-0126 (field-level protection), ADR-0130 (AI-models gateway),
ADR-0132 (Model Lab across modalities), ADR-0133 (file associations).
**Affects:** `intelligence.eval_case` / `eval_run` / `eval_result` (v0.2.0), `engines/model-eval`, `apps/model-lab`,
the AI-models gateway (image input), a first suite `urban-visual-intelligence`.

---

## Context

A proposal ("Visual Intelligence Benchmark Suite", v0.1) asks for a model-agnostic benchmark that picks, for each
intelligence capability, the cheapest algorithm or pipeline that meets the required accuracy and latency. It
describes 72 tests in 12 categories, from image quality to recommendations, and five entities: suite, test,
dataset, candidate and test run.

The first data is 156 camera snapshots in Files: 48 Kanpur junctions, 1–4 views each (119 fixed "BOX" cameras, 37
PTZ), all taken at about the same time, with no locations, repeats or outcomes.

Model Lab (ADR-0132) already has suites, cases, runs, results, labels that count only after review, and a scorer per
case. It does not yet take images, group cases into tests, or report results by condition.

## Decision

**The benchmark is built into Model Lab, not beside it. The proposal's entities map onto Model Lab's records, a
test is a group of cases with one metric, and the first suite holds only the tests these images can answer.**

### 1. The entities in Model Lab

| Proposal | Model Lab |
|---|---|
| Suite | Suite (`urban-visual-intelligence`), versioned by its cases |
| Test | `test_id` on each case (`A01`, `B03` …): cases with one task, one prompt, one scorer |
| Dataset | The case's `inputs`: file references. Filestore ids are content hashes, so a dataset version is its set of ids |
| Candidate | A run subject (ADR-0132 §2): a model through the gateway, or a component with settings |
| Test run | Run + results, already with output, latency, tokens, served-by and errors per case |

A case is one image under one test. Labels are entered once per image and copied to that image's case in every
test.

### 2. What Phase 1 adds

1. **Images in cases.** `eval_case` v0.2.0 adds `inputs` (`{kind: image, file_id, region?}`), `test_id`, and
   `label_form` (the fields the labelling form shows for that test).
2. **Images reach the model.** The engine reads each image through the platform and sends it as an image part of the
   chat message. For OpenAI-compatible providers the message passes unchanged; the gateway's Anthropic adapter
   converts image parts to Anthropic's format. The engine, not the gateway, reads the file, so the gateway's trusted
   core does no file access (ADR-0130).
3. **Private cases stay in.** Before any call, the engine refuses to send a case marked `private` to a provider not
   marked `hosting: in_house` (ADR-0132 §5), and records the refusal as the result. The camera frames are private
   until a decision says otherwise.
4. **Scorers:**
   - `counts`: per-class count error (MAE), exact-count accuracy and bias;
   - `labels`: F1 over a set of class labels, single- or multi-label, with `uncertain` as an allowed answer;
   - `text`: character error rate and exact match;
   - each returns a 0–1 score for the leaderboard plus its own metrics.
5. **A labelling form in Model Lab:** the image beside the fields its tests need (counts per class, choices, text),
   drafted by a model or a person, counted only after a reviewer saves it.
6. **Results by condition:** cases carry tags (view `box` / `ptz`, lighting, density), and results show each
   metric per tag as well as overall.

### 3. The first suite: `urban-visual-intelligence` v0.1

Only tests that single snapshots can answer with form labels:

| Test | Output | Metric |
|---|---|---|
| A01 Image quality | good / marginal / poor | macro-F1 |
| A02 Lighting and visibility | day / night / glare / haze / low light | F1 |
| A04 Occlusion | vegetation / cable / structure / vehicle / none | F1 |
| A06 Suitability | counting / tracking / static infrastructure | F1 |
| B01 Presence | classes present | F1 |
| B03 Vehicles by class | car, two-wheeler, auto, e-rickshaw, bus, truck, bicycle | count MAE per class |
| B04 Pedestrians | count | MAE |
| C05 On-screen text | timestamp, camera name | CER, exact match |
| E03 Obstruction | road / footpath blocked: yes / no / uncertain | F1, correct "uncertain" |

Tests needing boxes or masks (B05, D01–D04, D07) wait for a drawing tool. Tests needing locations, repeat
observations or outcomes (F, G, H, I, J, K) wait for that data.

### 4. Splits

By junction, never by frame: about one third of junctions for development, the rest held back for scoring. All views
of a junction stay in one split.

## Consequences

- **The benchmark reuses everything Model Lab has:** runs, resume, the Models tab, rescoring and review rules.
- **Hosted models report latency, tokens and price; only models on our hardware can report GPU and CPU time.**
  Results show the two kinds separately.
- **Until the privacy decision, the camera suite runs only on in-house models,** so on staging it cannot run at all.
  That is intended.
- **Detectors must be permissively licensed** (for example RT-DETR, Apache-2.0); AGPL detectors are excluded from a
  hosted platform.

## Decisions needed before Phase 3 (running models)

1. **Privacy route for the camera frames:** the data owner's permission for external evaluation; redacting faces
   and number plates first; or in-house models only.
2. **Labelling:** who reviews, and how many images first (proposed: 60 across about 20 junctions).
3. **Earlier ground-control-point work:** where it is, for test F01.

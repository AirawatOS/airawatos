# ADR-0132 — Model Lab: evaluation across modalities

**Status:** Proposed · **Date:** 2026-11-15
**Builds on:** ADR-0030 (no secrets in components), ADR-0077 (camera media plane), ADR-0126 (field-level protection),
ADR-0129 (no platform provider catalogue), ADR-0130 (trusted core, gateways and components; the AI-models gateway
and DEBT-B71).
**Affects:** the `intelligence.eval_case`, `intelligence.eval_run` and `intelligence.eval_result` schemas (v0.1.0 → v0.2.0),
`engines/model-eval`, `apps/model-lab`, the AI-models gateway's north contract ([GATEWAY-v0.1](../specs/GATEWAY-v0.1.md)).

---

## Context

Model Lab tests language models on the platform's own tasks before they are routed. It is a tenant app
(`apps/model-lab`) and an engine (`engines/model-eval`) over three governed record types:

- `intelligence.eval_case` — one input exactly as the platform sends it, a scorer and an expected answer;
- `intelligence.eval_run` — a suite sent to a list of models through the model-gateway;
- `intelligence.eval_result` — one case × model: output, score, metrics, latency, tokens.

It earned its place on the first suite. On 30 sections of URDPFI Volume I with 71 hand-checked expected norms, it
showed the model in use today finding 34 of the 71, and two alternatives finding 66 and 69. It also caught two
scoring defects (lakh / crore figures, truncated answers) that would otherwise have ranked the models wrongly.

Every part of it is **text-only**:

| Part | Today | Where it stops |
|---|---|---|
| Case input | `messages` — a chat prompt | no image, audio, video or document page |
| Subject | a model name sent to `/v1/complete` | detection, counting and OCR are often a vision model or a whole component, not a chat model |
| Scorer | `norms`, `json_fields`, `contains`, `exact`, `grounded` — code in the engine | no error rate, box overlap, count error, rubric judge or human preference |
| Gateway | chat/completion, embeddings, speech-to-text | no image or video input, no text-to-speech route, one fixed 60 s timeout |
| Labelling | a JSON text box | nobody can label boxes, counts, transcripts or video events in a text box |
| Privacy | `visibility: public | private` on each case | **recorded, not enforced**: nothing stops a private case reaching an outside provider |

The platform's next decisions all need these evaluations:

- the GPU plan's vision, OCR and Indic speech rows;
- urban-scene analysis on city cameras (crowd and vehicle counting, flooding, garbage, encroachment), which feeds the
  crowd-safety loop;
- OCR of the scanned guideline tables where many norms live;
- Kannada and Hindi speech-to-text and text-to-speech;
- reasoning depth for decision recommendations.

## Decision

**Model Lab becomes modality-neutral. A case holds media by reference. A run tests a model or a component under stated
settings. Scorers are named plug-ins. A case's visibility is enforced before any call leaves the platform.**

### 1. Cases carry media by reference

`eval_case` v0.2.0 adds `inputs`, a list of
`{kind: text | image | audio | video | document, file_id, mime, sha256, region?}`:

- `file_id` is a filestore id;
- `region` selects part of a file: a crop box, a page range, or a time window;
- media never goes inline in the record, so a 20-minute clip is one reference.

`messages` stays for text tasks. A chat case may reference inputs from its message parts. Every input's `sha256` is
checked when the case runs, so a case cannot silently change under its label.

Suites are seeded from platform data a tenant already holds:

- camera snapshots and clips (through the ADR-0077 media plane, never an RTSP URL in a case);
- complaint photos;
- scanned PDFs;
- voice notes;
- narration clips.

### 2. A run tests a subject under settings

`eval_run.models` generalises to `subjects`. Each subject is one of:

- `{kind: "model", name, provider?, settings}` — called through the model-gateway, as today;
- `{kind: "component", id, version, settings}` — a component run end to end on the case's inputs, for example
  crowd counting on labelled frames, or document ingest on a scanned PDF. Its declared output is what gets scored.

`settings` holds the knobs a comparison is about: effort or reasoning budget, temperature, image resolution, frames per
second, language hint. The same model under two settings is two subjects in one run. Every result records the
settings it ran with and the model the gateway reports it used.

### 3. The gateway's north contract grows by modality

Within ADR-0130's AI-models gateway. The south adapters translate each operation for their provider.

| Operation | North contract | Note |
|---|---|---|
| Chat with images | image parts in a message (file references, resolved by the gateway) | OpenAI-compatible and Anthropic formats both carry them |
| OCR | a document page in, text or a table out | a vision model with a fixed prompt, or a dedicated OCR model |
| Speech-to-text | add a language hint and word timings | the route exists |
| Text-to-speech | text plus voice in, an audio file reference out | today a driver; becomes a gateway operation |
| Video | frames sampled by the gateway at the case's rate, or native video where the model accepts it | frame sampling works with any image model |

**Timeouts are set per provider and per operation, not fixed at 60 s.** A long OCR page or a video needs minutes.

**Usage reports reasoning tokens separately**, so the cost of thinking is visible per result.

### 4. Scorers are named plug-ins

A scorer is a registered function: `(case, output) → score in [0, 1] + metrics`. The engine dispatches on
`case.scorer`; the leaderboard, results and rescoring do not change. Adding a scorer needs no schema change, because
`scorer` becomes a governed name list rather than a closed enum.

| Task | Scorer | Expected answer |
|---|---|---|
| Speech-to-text | word / character error rate, after Indic script normalisation | transcript |
| OCR | character error rate; table cell accuracy | text or table |
| Object detection | precision / recall at an overlap threshold, or mAP | boxes per class |
| Crowd and vehicle counting | mean absolute and relative count error | count per frame or zone |
| Scene tagging | accuracy / F1 | labels |
| Visual Q&A, scene description | exact / contains, or an AI judge with a rubric | answer and rubric |
| Video events | event F1 within a time tolerance | timestamped events |
| Reasoning | exact or numeric within a tolerance | answer |
| Long answers, recommendations | AI judge with a rubric that checks figures against cited sources | rubric and required figures |
| Text-to-speech, open-ended outputs | pairwise human preference, ranked from the votes | none |

An AI-judge scorer names its judge model and rubric in the case. Each result records both, and the run summary keeps
the judge's agreement with any human-labelled subset.

### 5. Labelling fits the modality, and drafts stay drafts

The case editor becomes one editor per expected-answer type:

- boxes, polygons and click-counts on an image;
- a transcript under an audio player;
- the page image beside an editable text or table;
- events and counts on a video timeline.

Labels may be **drafted** by a model or a person (`expected.draft`). **A draft never scores.** A case becomes
`labelled` only when a reviewer saves it, which is the rule the URDPFI suite already follows.

For subjective outputs, the app adds an A/B view, and the votes are recorded as results.

### 6. Visibility is enforced, not just recorded

- **Before any call, the engine checks each case's visibility against the provider it would reach.** Private cases go
  only to providers running on the tenant's own or the operator's hardware. A private case aimed at an outside
  provider is refused and recorded as refused, never sent.
- **A suite built from camera or complaint media is private by default.** It becomes public only after faces and
  number plates are redacted, and only by an explicit decision on the suite.
- **Media in results is shown under the tenant's existing roles and field protection (ADR-0126).** A result never holds
  a copy of private media, only references.
- **The gateway applies the same check on its side** (ADR-0130: consent and lawful basis on the north contract, the
  open DEBT-B71). The engine's check does not replace the gateway's; it stops a run before it starts.

### 7. Order of work

1. **Foundations:** schema v0.2.0 (`inputs`, `subjects`, `settings`, open scorer names), scorer plug-ins, timeouts per
   provider and operation, and visibility enforcement.
2. **OCR and image Q&A:** the guideline table pages, and a first urban-scene suite from camera snapshots (counting and
   tagging).
3. **Audio:** Kannada and Hindi speech-to-text by error rate; text-to-speech by preference votes.
4. **Reasoning and long answers:** Ask Airawat and decision recommendations against rubrics, at several effort levels.
5. **Video:** frame sampling on existing clips first; native video models when the platform's own GPUs arrive.
6. **Agents and tool use:** scoring the whole trace of a skill run, not only its final answer.

Steps 1 and 2 are the main build. Each later modality is a scorer, an editor and a suite.

## Consequences

- **One harness decides every model choice.** The GPU plan's rows (vision, OCR, speech, the main model) are chosen on
  the platform's own data, with numbers, instead of on public leaderboards.
- **Components can be compared the same way as models.** For example, an in-house crowd counter against a vision
  model asked to count.
- **The schemas move to v0.2.0 through the steward.** v0.1.0 records stay readable: `models` reads as `subjects` of
  kind `model` with no settings.
- **Scorers become shared code that needs review.** A wrong scorer ranks models wrongly, as the lakh / crore defect
  showed. Every scorer ships with tests built from labelled examples.
- **Evaluation spends money on outside providers.** Runs report usage per result. The tenant's cost ceilings (ADR-0130,
  DEBT-B71) apply to evaluation traffic as to any other.
- **Private media never leaves the platform for evaluation.** Until in-house models are hosted, private suites cannot
  run; this is intended.
- **Labelling becomes the bottleneck.** The draft-and-review rule keeps quality, but each modality needs reviewer time.
  That cost is planned per suite, not discovered afterwards.

## Open questions

1. **Do component subjects run in the tenant's sandbox, or in a dedicated evaluation tenant?** A dedicated tenant keeps
   evaluation writes out of operational records.
2. **Who may publish a suite as public across tenants**, for example as a shared benchmark on the network?
3. **Should the AI judge be fixed per suite, or chosen per run?** Fixing it keeps scores comparable over time.
4. **How long are media and results kept?** This is especially relevant to camera footage, under the tenant's
   retention policy.

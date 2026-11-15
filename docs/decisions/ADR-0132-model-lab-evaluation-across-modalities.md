# ADR-0132 — Model Lab: evaluation across modalities

**Status:** Proposed · **Date:** 2026-11-15
**Builds on:** ADR-0077 (camera media plane), ADR-0126 (field-level protection), ADR-0130 (trusted core, gateways and
components; DEBT-B71).
**Affects:** `intelligence.eval_case` / `eval_run` / `eval_result` (v0.1.0 → v0.2.0), `intelligence.provider` (one
field), `engines/model-eval`, `apps/model-lab`, the AI-models gateway's north contract
([GATEWAY-v0.1](../specs/GATEWAY-v0.1.md)).

---

## Context

Model Lab tests models on the platform's own tasks before they are routed. It is an app (`apps/model-lab`) and an
engine (`engines/model-eval`) over three record types: a **case** (an input, a scorer, an expected answer), a **run**
(a suite sent to a list of models through the model-gateway) and a **result** (one case × model).

On its first suite, it showed the model in use today finding 34 of 71 hand-checked URDPFI norms, against 66 and 69
for two alternatives. It also caught two scoring defects that would have ranked the models wrongly.

It is text-only, and the next model choices are not text: vision and OCR, Indic speech, urban-scene analysis on city
cameras, and reasoning depth for recommendations. Each case also records whether it is private, but nothing enforces
it.

## Decision

**A case holds media by reference. A run tests a model or a component. Scorers are plug-ins. Privacy is enforced at
the gateway. The gateway gains only image input.**

### 1. Cases hold media by reference

`eval_case` v0.2.0 adds `inputs`: a list of `{kind: image | audio | video | document, file_id, region?}`.

- `file_id` is a filestore id, which is the content hash, so a labelled case cannot change underneath its label.
- `region` is optional: a crop, a page range, or a time window.
- Camera media enters only through the ADR-0077 media plane, never as a stream URL.

**The engine, not the gateway, prepares inputs for the subject.** A video becomes sampled frames, and a PDF page
becomes an image, at rates the run states. OCR is chat with a page image and a prompt, not a separate operation.

### 2. A run tests a subject

`eval_run.models` becomes `subjects`, each either:

- `{kind: model, name, provider?, settings}`, called through the gateway;
- `{kind: component, id, version, settings}`, for example a crowd counter or the narration driver.

A component under test takes the case's inputs as file references and prints a `RESULT:` line, as engines already do;
the scorer reads that line.

`settings` holds what the comparison is about: effort, temperature, frame rate, resolution, language. The same model
under two settings is two subjects.

Every result records:
- its settings;
- the model the gateway reports it used;
- the host that served it, since a router such as Hugging Face may pick a different partner per call;
- reasoning tokens, separate from answer tokens.

### 3. Scorers are plug-ins

A scorer is a function registered by name: `(case, output) → score in [0, 1] + metrics`. `scorer` is a plain name;
the engine refuses a name it does not know.

Scorers ship one per task as suites need them (Appendix). Each ships with tests drawn from labelled examples.

An **AI-judge** scorer names its judge model and rubric. **The judge may not be a subject of the same run**, because
models favour their own answers.

### 4. Labels: drafts never score

Expected answers are edited in a form that fits the task: boxes and counts on an image, a transcript under an audio
player, a page beside its text or table, events on a video timeline.

A model or a person may **draft** a label. A case is `labelled` only when a reviewer saves it, which is the rule the
URDPFI suite already follows. Subjective outputs (speech, open answers) are scored by **pairwise votes** recorded as
results.

### 5. Privacy is enforced at the gateway

- `intelligence.provider` gains `hosting: in_house | external`.
  - It defaults to `external`.
  - Only the operator may set `in_house`; a tenant cannot.
- **The gateway refuses to send a private case's content to an external provider.** This is the per-call consent check
  ADR-0130 already places in the gateway (DEBT-B71); evaluation is its first user.
- **The engine checks the same rule before a run starts**, so a run that would be refused does not begin.
- **Suites built from camera or complaint media are private.** One becomes public only after faces and number plates
  are redacted, and only by an explicit decision.
- **Results hold references, not copies.** Who may see the media follows the tenant's roles and field protection
  (ADR-0126).

### 6. The gateway gains image input, and nothing else here

- Chat messages may carry image parts as file references. The gateway resolves the references and passes the images
  to the provider adapter.
- Speech-to-text takes a language hint.
- Timeouts are set per provider and operation, instead of a fixed 60 s.

Video, OCR and text-to-speech need no new gateway operation (§1, §2), so no media decoding enters the trusted core.

### Order of work

1. **Foundations:** schema v0.2.0, the `hosting` field and its check, scorer plug-ins, timeouts.
2. **Image and OCR:** guideline table pages, and a first urban-scene suite (counting, tagging).
3. **Audio:** Kannada and Hindi speech-to-text; text-to-speech by votes.
4. **Reasoning and long answers:** Ask Airawat and recommendations against rubrics, at several effort levels.
5. **Video:** sampled frames now; native video models when in-house GPUs arrive.
6. **Agents:** score a skill run's whole trace, not only its answer.

## Consequences

- **Model choices are made on the platform's own data, with numbers.** That covers the GPU plan's rows and components
  against models; public leaderboards stop deciding.
- **The trusted core grows by one input type (images) and one check (hosting).**
- **Schemas go to v0.2.0 through the steward.** A v0.1.0 run reads as model subjects with no settings.
- **Private suites cannot run until in-house models are hosted.** This is intended.
- **Outside providers cost money.** Results report usage, and the tenant's cost ceilings (DEBT-B71) apply.
- **Labelling is the bottleneck.** Reviewer time is planned per suite.

## Open questions

1. **Where do component subjects run:** in the tenant's sandbox, or in an evaluation tenant that keeps their writes out
   of operational records?
2. **Who may share a public suite across tenants as a benchmark?**
3. **Is the judge fixed per suite, so scores stay comparable over time?**
4. **How long are evaluation media kept, camera footage especially?**

## Appendix — scorers by task

| Task | Scorer | Expected answer |
|---|---|---|
| Norm extraction (today) | F1 on values; grounded in the source text | norms |
| Speech-to-text | word / character error rate after Indic normalisation | transcript |
| OCR | character error rate; table cell accuracy | text or table |
| Detection | precision / recall at an overlap threshold | boxes |
| Counting | mean absolute and relative error | counts |
| Tagging | accuracy / F1 | labels |
| Visual Q&A, reasoning | exact / numeric within tolerance, or AI judge with rubric | answer, rubric |
| Video events | event F1 within a time tolerance | timestamped events |
| Long answers | AI judge; figures checked against cited sources | rubric, required figures |
| Speech output, open answers | pairwise votes | none |

# ADR-0089 · Slice 1 — `emits:` / `subscribes:` manifest declaration

Status: Proposed (2026-09-15) · Parent: ADR-0089 (event/message spine)
Goal: make "which events a component publishes / reacts to" a **declared, certified, graph-visible** part of the
manifest — riding the pub-sub spine that ALREADY runs (kernel outbox → `event_relay` → `platform.subscription`
matched by `automation.py`). No new runtime; we formalize + project what's live.

## Background (already live — do not rebuild)
- Kernel emits a `platform.event {subject, subject_schema, tenant, …}` into a durable outbox on **every write**.
- `event_relay` delivers at-least-once (retry + dead-letter).
- `automation.py` matches each event against enabled `platform.subscription` records (**WHEN → THEN**) and fires.

Today subscriptions are hand-created records. This slice lets a component **declare** them in its manifest;
publish/install then **projects** them into `platform.subscription` — same runtime, but the coupling is now
governed, versioned, and visible.

## What we build

### 1. Manifest fields (additive; alongside `calls:`/`implements:`)
```yaml
emits:                                   # events this component causes (documentation + graph edge + certify)
  - news.item                            # a write to this governed schema is an event others can react to
subscribes:
  - on: news.item                        # WHEN a news.item is written…
    when: { field: status, op: eq, value: ingested }   # optional filter (reuses the ADR-0088-S1 predicate grammar)
    then: news-reclassify                # …THEN invoke this verb (a governed interface THIS component implements)
```
- `on:` = a governed **schema** whose write is the trigger (slice 1 keys on the noun, matching the live
  `subject_schema` mechanism; a governed `event`-interface abstraction is a later slice).
- `then:` = a verb the component **implements** (must be in its `verbs:`/`implements:` — you can only make it run
  its own handler).
- `when:` = optional predicate (same safe operator set as `governance.rule`, ADR-0088-S1) — reuse, don't invent.

### 2. Certify checks (network conformance)
- every `emits[i]` and `subscribes[i].on` is a **governed schema**;
- every `subscribes[i].then` is a **governed interface the component implements** (fail-closed, like `calls:`);
- `when` (if present) uses only the allowed operators.

### 3. Projection at install (install = grant, ADR-0035/kernel)
When a component is installed into a tenant, project each `subscribes[i]` into a tenant-scoped
`platform.subscription` record:
```jsonc
{ "schema":"platform.subscription", "id":"ds:<tenant>:subscription/<cid-name>-<i>",
  "enabled": true, "when": { "subject_schema": "news.item", "status": "ingested" },
  "then": { "verb": "news-reclassify", "component": "<cid>" },
  "source": "declared", "component": "<cid>", "version": "<ver>" }
```
- keyed by (component, index) so re-install/upgrade is idempotent (replace, don't duplicate);
- `source:"declared"` distinguishes it from hand-authored subscriptions (which stay untouched);
- uninstall/retire removes the projected records.
No change to `event_relay` or `automation.py` — they already consume `platform.subscription`.

### 4. Solution Studio: render event edges
The graph already shows call edges (ADR-0087 `calls`); add **event edges** from `emits`/`subscribes` so a
solution's reactive wiring is visible (Air Intelligence: `air.quality` write → `alert-eval`; News: `news.item`
→ `news-reclassify`).

## Proof (acceptance criteria)
1. `emits:`/`subscribes:` parse in the manifest; certify enforces the three checks above (governed schemas +
   implemented `then` verb + valid operators); a bad `then` is refused.
2. Take ONE existing hand-authored `platform.subscription` (e.g. the news reclassify trigger) and instead
   **declare** it in the component meta → on install a `source:"declared"` subscription appears → writing a
   matching record fires the verb via the existing relay. Behaviour identical; the trigger now lives in the
   (versioned, certified) component, not as a loose record.
3. Studio shows the event edge for that component.
4. Uninstall removes the projected subscription; hand-authored subscriptions are untouched.

## Out of scope (later slices)
- A governed `event`-interface abstraction over raw schema-writes (richer than `on: <schema>`).
- Idempotency enforcement + dead-letter observability view (ADR-0089 items).
- Moving engine execution out of the BFF process; broker-backed transport.
- Rate/scope caps on fan-out.

## Why this pairs with ADR-0088-S1
S1 of 0088 gives the **decision** primitive (rule → verdict); S1 of 0089 gives the **reaction** primitive
(event → verb). Together they are the two halves of a domain service you can *declare* rather than code: "when X
happens (subscribe), decide with a rule, then act." Both reuse the same predicate grammar and both are pure
formalization over spines that already run — lowest-risk way to start the ADR-0088/0089 convergence.

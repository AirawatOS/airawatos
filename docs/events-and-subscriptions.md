# Events & Subscriptions — reacting when data changes

*How one component triggers work when another writes to the registry — using a governed record, not code.*

The registry isn't just storage; **every write is an event**. This is how the platform stays loosely coupled: a driver ingests data, an engine reacts, a person gets a task — and none of them call each other directly. They're wired together by a small governed record you can read, audit, and change without redeploying anything.

## The one-paragraph model

When a component writes an object, the kernel persists a **`platform.event`** in the *same request* — a durable outbox, so a trigger is never silently dropped. A relay delivers each event **at-least-once** to the **event dispatcher** (the automation service), which matches it against your **`platform.subscription`** records (a **WHEN → THEN** rule) and fires the matched action. No polling loops, no webhooks buried in code — the wiring *is* data.

```
component writes  ──►  kernel emits platform.event (durable outbox)
                                    │  (relay, at-least-once + retry)
                                    ▼
                  event dispatcher: match platform.subscription (WHEN)
                                    │
                                    ▼
                            fire the action (THEN) — a governed verb
```

## Subscribe with a record

A subscription is a `platform.subscription`:

```jsonc
{
  "schema": "platform.subscription",
  "id": "ds:kmc:subscription/air-recommendation-to-action",
  "name": "Air advisory → open action",
  "enabled": true,
  "match":  { "subject_schema": "governance.recommendation",   // WHEN this schema is written…
              "where": { "domain": ["air"] } },                //   …and these fields hold on the object
  "action": { "interface": "<a governed verb>" }               // THEN invoke this (see “governed action” below)
}
```

- **`match.subject_schema`** — the schema whose writes you care about.
- **`match.where`** — optional field conditions on the written object (all must hold). e.g. only high-severity alerts.
- **`action`** — what to run. It receives `{event, subject, subject_ref}` — `subject_ref` is the **id of the object that triggered the run**, so the fired component knows *which* record to act on.

Writing (or editing) a subscription **hot-reloads** the dispatcher — no restart.

## Worked example — the Air Intelligence action loop

The Air Intelligence solution already produces a natural chain:

1. **`air-quality-advisory`** (a skill) reads the PM2.5 grid + rules and writes a **`governance.recommendation`** ("enforce in Ward 7 tonight").
2. That write **emits an event** (`governance.recommendation` is not bulk-guarded — see below).
3. A **subscription** matches it and fires the **`decision-router`**, which opens a `platform.case` + `platform.task` and drops it in the **Inbox** for the responsible official.

So "sensor spike → advisory → an official has a task" happens with **zero glue code** — one `platform.subscription`, auto-wired at install from the `decision-router`'s declared `subscribes:` block (see *"Where you specify this"*).

## The rule that saves you: never subscribe to bulk data

A driver may write **thousands of facts per run**. If every one emitted a trigger, you'd get a flood. So the kernel **suppresses per-write events for a configured set of bulk fact/measure schemas** — `geo.`, `cell.`, `environment.`, `air.quality`, `air.hotspot`, several `welfare.*` fact subtypes, `demographics.`, and more (the `EVENT_SKIP_SCHEMA_PREFIXES` guard — the exact list is deployment-configurable). **Subscriptions never fire on the guarded schemas.**

That is deliberate: **subscriptions are for discrete signals** — an alert, a decision, a recommendation, a single "run complete" record — **not for data floods.**

## "How does an engine know a driver finished?"

Because the driver's data writes are (correctly) silent, you don't listen for them. Three real patterns:

1. **Chain them — pipeline or schedule (most common).** A `pipeline` component runs stages in order (`sense → predict → detect → advise`); the engine is simply the *next stage after* the driver and reads whatever it just wrote. Or the scheduler runs the driver, then the engine, on a cadence. No live "done" ping needed — the engine reads the latest registry state.
2. **Emit one completion record.** If you want event-driven "driver finished → engine runs," have the driver write a **single summary record on a non-bulk schema** at the end of its run (e.g. `air.ingest_run {status: "complete", rows: 8800}`). *That* write emits an event — one per run, not per row — and an engine subscribes to it.
3. **Read the run status.** The scheduler stamps `last_run` / `last_status` / `next_run` onto the component's `platform.schedule` record; an orchestrator can read it.

Rule of thumb: **bulk data → chain by schedule/pipeline; a discrete milestone → emit one record and subscribe.**

## Governed action (why the THEN names a verb, not a URL)

A subscription's action must name a **governed verb** (`action.interface`) — the automation dispatcher resolves it to its bound endpoint via the directory. It may **not** invoke a raw URL, because a hidden webhook would be an ungoverned side-channel. During migration this is enforced in *shadow* (a raw `action.url` still fires, with a warning); the target is *strict* (governed verbs only). So: **make the thing you want to trigger a governed, bound verb**, and name it in the action.

## Where you specify this

- **Recommended — declare `subscribes:` in the component's meta.** A component states the events it reacts to right in its `meta.yaml`, and the platform does the rest:

  ```yaml
  subscribes:
    - on: governance.recommendation      # WHEN this schema is written…
      where: { domain: [air] }           #   …and these fields hold (optional)
      action: decision.route             # THEN invoke this governed, bound verb
  ```

  On **install**, the platform reads that block and **auto-writes the governed `platform.subscription`** for you — you never hand-author the subscription record, and the id is derived from `(component, on)` so re-installing is idempotent. The `action` names a verb that is already governed and bound (see *"Governed action"* above). This is how the Air Intelligence loop is wired: it lives in the `decision-router`'s meta.

- **Also supported — ship a ready-made subscription as a solution *contribution*.** A solution can carry governed records (including `platform.subscription`) that are **materialized into the tenant on install**: they ride as a `__contributions__` asset with `$tenant` placeholders, re-scoped to the installing tenant. Use this when the subscription isn't tied to a single member's meta.

- **In Solution Studio.** Studio edits the **governed data** that drives the platform. Today you author a subscription as either of the above (a member's `subscribes:` block, or a contribution record). A **visual** "Automations" panel — wiring a component's declared `emits`/`subscribes` on a canvas — is the roadmap (the event/message spine); the declared-`subscribes:` half already ships.

## Checklist

1. Is your trigger a **discrete signal**, not bulk data? (If bulk, chain by schedule/pipeline instead.)
2. Make the action's verb **governed and bound**.
3. Declare it: add a `subscribes: [{on, where?, action}]` block to your component's `meta.yaml` — the platform auto-wires the `platform.subscription` at install. (Or ship a ready-made subscription as a solution contribution.)
4. Test: write the trigger object → confirm the action fired (the dispatcher logs `fired <name>`), idempotent on redelivery.

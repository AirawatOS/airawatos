# ADR-0089 — The event/message spine: governed pub-sub, execution isolation, and the scale path

Status: Proposed (2026-09-15)
Related: ADR-0022 (everything-is-a-component) · ADR-0030 (component SDK + broker clean-room) · ADR-0045/0050
(solution runtime + execution engine) · ADR-0052 (attributed writes) · ADR-0058 (interaction contracts /
interfaces) · ADR-0087 (governed bridge) · ADR-0088 (domain-services realization spectrum)

## Context

ADR-0088 covers the **synchronous** lane: an app names a verb, the host routes it to the certified component
that implements it, gets a reply. But most real civic behaviour is **reactive** ("a complaint was filed → open
a case → notify the ward officer") and some is **heavy/long** (recompute a city's exposure). Those don't belong
on a blocking request/reply call.

The platform already has the async substrate — and it is governed and durable. This ADR names it as
first-class, states the scale path, and fixes the two structural limits (in-process engines, Postgres-poll
delivery). It is the async counterpart to ADR-0088.

### What already exists (do NOT rebuild)

- **The registry is an append-only, attributed, bitemporal fact log.** Every write carries a verifiable agent
  (`component:// obo user://`, ADR-0052); `GET /v1/registry/objects/{id}/prov` is the write-attribution trail.
  *The audit log is the registry itself.*
- **Durable outbox.** `kernel _emit_event` persists a `platform.event` (status=pending) in the SAME transaction
  as each registry write — "so no trigger is ever silently dropped."
- **At-least-once relay.** `event_relay.py` drains the outbox, delivers with retry + exponential backoff, and
  dead-letters after N attempts.
- **Subscriptions (WHEN → THEN).** `automation.py` matches each event against `platform.subscription` records
  and fires the actions. This is the flood loop / alert engine / ERP-approval reactive spine today.

This is precisely the OS message-pump + subscription model — governed:

| Windows | Airawat today |
|---|---|
| `PostMessage` (a message) | `platform.event` emitted per registry write |
| message pump | `event_relay` (durable, at-least-once, dead-letter) |
| `WndProc` / subscribe `WM_*` | `platform.subscription` (WHEN event → THEN verb) |
| — | every event attributed + durable; every subscription declared + certified |

## Decision

**Adopt an explicit command/event split, make publish/subscribe a first-class *declared* capability, and set the
execution + transport scale path — without changing the governance model (attributed events, certified
subscriptions).**

### 1. Command vs event — keep the split (CQRS-shaped)
- **Command lane (sync, ADR-0088):** interactive request→reply. Immediate result. Never made async by default.
- **Event lane (async, this ADR):** state changes fan out as events; reactive work subscribes. Decoupled,
  retryable, replayable.
- Rule of thumb: *a user waiting for an answer* = command; *"when X happens, do Y"* = event. A command handler
  MAY emit events (it already does — every write does).

### 2. Publish/subscribe becomes a DECLARED interface (ADR-0058)
Today `platform.event`/`platform.subscription` are schemas + a service. Promote them so a component DECLARES its
event coupling in its manifest, exactly like `calls:` / `implements:` (ADR-0087):
```
emits:      [<event-interface@ver>]     # events this component publishes (e.g. civic.complaint_filed)
subscribes: [{ on: <event-interface@ver>, then: <verb@ver>, filter: {…} }]
```
Effect: "components send messages to each other and subscribe to events" (the OS model) becomes **governed +
visible in the Solution Studio graph** — the certifier checks the events/subscriptions are governed interfaces,
and the graph shows event edges, not just call edges. The workflow lane of ADR-0088 is then just an
event-driven state machine expressed over this spine.

### 3. Execution isolation — move engines out of the BFF process
Today `_load_engine` imports an engine's `run.py` INTO the app-host/scheduler process (fine for trivial confined
engines, wrong for anything hot or heavy). Reactive + heavy work runs via the **broker/worker execution** that
ADR-0030 already provides (Docker-sandboxed, capability-gated), so:
- a hot engine scales horizontally (N workers) without touching the BFF;
- a slow engine cannot block the interactive host;
- backpressure lives at the worker queue, not the kernel.
In-process stays ONLY for L0/L1 trivial confined logic.

### 4. Transport scale path — the outbox is the invariant; delivery is swappable
The **durable outbox stays the source of truth** (transactional with the write). Its *delivery* can evolve
without changing producers or governance:
- **Now:** Postgres-poll relay — correct, simple, fine at current volume.
- **Next:** partition the outbox by tenant/schema; run **N relay workers** (leased/claimed rows) for parallel
  at-least-once delivery + ordering per partition.
- **At scale:** back the transport with a real broker/stream (NATS JetStream / Kafka / Redis Streams). The
  outbox becomes the exactly-once bridge INTO the stream; consumers are governed subscriptions. Events remain
  attributed + signed; subscriptions remain certified. No producer change.

### 5. Big reads → deltas, not 100k-row pulls
Engines that pull whole-tenant datasets synchronously (`kfind limit=100000, timeout=120`) should instead consume
**change events** (subscribe to the schema) or **paged/streamed** reads. Recompute-on-delta replaces
recompute-from-scratch — the event spine is what makes that possible.

## Consequences

- The async model is named, declared, and governed — not folklore living in three services.
- Solution Studio shows both **call edges** (ADR-0088) and **event edges** (this ADR) — the full interaction
  graph of a solution.
- Engines gain isolation + horizontal scale; the interactive host stays thin and fast.
- The transport can grow from Postgres-poll to a broker with zero producer/governance change (outbox invariant).
- Risk: at-least-once means **consumers must be idempotent** — make idempotency a certify-time expectation for
  any `subscribes:` handler (dedupe on event id / subject+version). Ordering is per-partition only; cross-entity
  ordering must not be assumed.
- Risk: event storms / fan-out amplification — subscriptions need rate/scope caps and the dead-letter path must
  be observable (a governed `platform.event` dead-letter view).

## Sequencing

1. **Declare-ify pub/sub:** add `emits:` / `subscribes:` to the manifest + certify checks + render event edges
   in Studio. (No runtime change — it formalizes what the relay/automation already do.)
2. **Idempotency + dead-letter observability:** certify-time idempotency expectation; a governed dead-letter view.
3. **Engine execution isolation:** route `subscribes:` handlers + heavy engines through broker/worker execution
   (ADR-0030), out of the BFF process.
4. **Partitioned relay workers:** parallel at-least-once delivery, ordering per (tenant, schema).
5. **Broker-backed transport (when volume demands):** outbox → stream bridge; consumers unchanged.
6. **Delta-driven engines:** convert the biggest synchronous whole-tenant reads to subscribe-to-delta recompute.

This is the async half of the runtime; together with ADR-0088 (sync domain-service dispatch) and ADR-0087
(governed bridge) it is the complete component-interaction model — call it or subscribe to it, always governed,
always attributed.

# ADR-0120 — Generic Event Plane: Resource, Authority, Event, Subscription, Routing

- Status: **Proposed (design — rev 2, post-review; for a second review before implementation)**
- Date: 2026-10-31
- Companion to: **ADR-0119** (four-plane architecture). This ADR details the machinery that makes event-exchange
  networks (TOP, disease surveillance, …) *configuration* rather than code.
- Substrate: **ADR-0089** (event/message spine — the event store), **ADR-0053** (common resource IDs),
  **ADR-0103** (consent/payload sealing). Authorization via the **CapabilityGrant** model from ADR-0119/D1.
- Rev 2 incorporates an architecture review: one grant mechanism (no second `AuthorityGrant` object), a generic
  typed-predicate expression (not a credential-only manifest reused for events), transaction objects **out** of
  the bitemporal registry, routing-metadata separated from payload, governed receive-capability, endpoint
  bindings instead of raw URLs, deterministic resource selectors, transformation-as-participant, a telemetry
  boundary, and several smaller corrections.

---

## Context

The service-exchange runtime answers *"who may receive this service, having proven what?"* The event plane answers
a different question: *"something happened to a subject — which authorities, by jurisdiction and standing
interest, must learn of it, and may any act?"* The as-built system has none of the primitives for this. This ADR
defines the **minimum generic set** so the event-exchange runtime is domain-blind, and — per review — draws the
storage, routing/payload, authorization, and endpoint boundaries deliberately so sensitive, high-volume,
bounded-retention domains (TOP, disease surveillance) are first-class rather than afterthoughts.

## Decision — the object set and where each lives

Event-plane objects split across **three stores by nature**, consistent with ADR-0119's four planes. Putting
every observation and every fan-out delivery into the bitemporal JSON registry would be an operational and privacy
mistake and would contradict TOP's bounded-retention goal — so transaction objects do **not** live there.

```
GOVERNED REGISTRY (bitemporal, durable, low-volume control/knowledge)
    Resource            EventType           Subscription        EndpointBinding
    (+ CapabilityGrant — from the Trust plane, ADR-0119/D1)

EVENT STORE / MESSAGE SPINE (ADR-0089; high-volume, bounded-retention, transaction-plane)
    EventEnvelope       EventDelivery

IMMUTABLE AUDIT STREAM (Governance; ADR-0119/D9)
    authorization decisions · routing decisions · state transitions
    — metadata + payload HASHES/IDs, NOT duplicated payloads
```

So: **four governed records + two event-store records + the Router**, reusing the Trust-plane CapabilityGrant.
(Rev-1 said "seven objects"; corrected — there is no separate `AuthorityGrant` record.)

### 1. Resource — the thing an event is *about* or *routed by*
`{id:"res:<network>:<type>/<local>", network, resource_type (governed schema), identifiers (ADR-0053 common IDs),
geometry?, parent_resource?, attributes}`. E.g. road segment, intersection, signal, corridor; a
`health.jurisdiction` area.

**Deterministic selector semantics (required before authority resolution is built).** A resource selector is one
of, evaluated with defined rules — no implicit geography:
- **exact** — a specific `res:` id.
- **hierarchy** — a container id *plus an explicit* `include_descendants: true|false`. Authority over
  `corridor-1` applies to `road-segment-1` **only if** the grant's selector says `include_descendants:true`.
  Inheritance is never silent; resolution walks `parent_resource` only when the matching selector opts in.
- **type + jurisdiction** — all resources of type `T` whose jurisdiction (via `identifiers`/`parent_resource`)
  matches `J`.
- **geometry** — point-in / intersects. **Deferred to a later slice**; selectors 1–3 ship first.

**Overlap is expected, not conflict.** City, traffic-police zone and highway-authority jurisdictions may all match
one intersection. The resolver returns **all** matching authorities/subscriptions; it never picks a "winner."

### 2. Authority = a CapabilityGrant with a ResourceScope (terminology, not a new object)
There is **one** grant store, **one** evaluator, **one** revocation path, **one** audit model (ADR-0119/D1). A
CapabilityGrant carries a **typed scope**:
```
CapabilityGrant { grantee, network, capability, scope, constraints, validity, grantor }
scope ∈ { NetworkScope | ResourceScope | CredentialTypeScope | EventTypeScope | ServiceScope | OfferingCategoryScope }
```
"AuthorityGrant" is simply the word we use for a CapabilityGrant whose scope is a `ResourceScope` (one of the
selector shapes above), with a capability like `resource.act:signal-control`.

**Authority ≠ interest.** A grant confers *permission/authority*. It does **not** mean "must hear about." Standing
interest in receiving events is a **Subscription**. If an agency is *mandated* to receive a class of events, that
is a **governance-created mandatory Subscription** (owned/locked by network governance), never a side effect of an
authority grant.

### 3. EventType — the governed shape + rules of a kind of event
`{id:"evt:<network>:<name>", network, version, payload_schema, routing_resource_type (which Resource routing
attaches to), subject_schema? (what the event is about, may differ from the routing resource),
publish_capability, receive_capability, routable_attributes[] (the fields the router/subscriptions may inspect),
default_retention, privacy{identity:none|pseudo|full, minimization}}`.

Two governed rules here matter:
- **The EventType owns the security requirement**, not the subscriber: `publish_capability` **and**
  `receive_capability` are declared on the EventType (or network policy). A Subscription cannot weaken them.
- **`routable_attributes[]` declares what is inspectable** for routing/filtering — the contract that lets
  subscriptions filter and the router resolve authorities **without** reading sealed payload.

### 4. EndpointBinding — a participant-owned, pre-registered delivery destination
`{id, network, owner (participant), kind∈{service,event}, address (url|queue), signing_key, status, rotation}`.
Subscriptions (and service fulfilment) reference a binding by id; **raw URLs never enter via a subscription**. This
keeps SSRF protection, endpoint rotation, identity and signing in one place: `Participant → EndpointBinding →
Subscription`. The same registry eventually serves service fulfilment and event delivery.

### 5. Subscription — scoped, filtered, standing interest (declares *what*, not *how-secured*)
`{id, network, subscriber (participant), event_type, resource_selector, filter (Expression over the EventType's
routable_attributes — ADR-0119/D4), min_confidence?, delivery_binding_ref, status}`.
No `capability_required` field (removed per review) — the Router derives the required `receive_capability` from
the EventType and decides authorization itself.

### 6. EventEnvelope — a published event instance (event store, not registry)
Routing metadata is separated from payload so the router can route sensitive events without inspecting content and
payloads can later be sealed end-to-end (ADR-0103):
```
EventEnvelope {
  id, network, event_type, event_type_version,          // version, not just id — historical events stay unambiguous
  publisher,
  subject,                 // what the event is ABOUT (e.g. a case/person) — may be pseudonymous or sealed
  routing_resources,       // the Resource(s) routing attaches to (e.g. jurisdiction)
  routing_metadata,        // declared routable_attributes ONLY — what the router/subscriptions may inspect
  occurred_at, published_at, expires_at,                 // stale-event rejection matters for traffic
  payload,                 // detail; MAY be sealed end-to-end — the operator need not read it
  provenance, correlation_id, causation_id,
  signature                // publisher-signed; verified like a credential
}
```
`received_at` is stamped by the spine on ingestion (distinct from `occurred_at`/`published_at`).

### 7. EventDelivery — one record per (envelope, subscriber); at-least-once (event store)
`{id, envelope_ref, subscription_ref, status∈{pending,delivered,failed,dead_letter}, attempts, last_error?,
acknowledged_at?}`. **`delivered` means the recipient's endpoint acknowledged *acceptance* of the envelope — not
that the recipient acted on it.** Acting is a separate outcome, modelled as its own event/service transaction, not
conflated with delivery. Delivery runs on the Phase-4 async transaction state machine (retry/timeout/dead-letter).

### 8. Router — the event-exchange runtime
```
publish(envelope):
  1. authenticate        — verify envelope signature; publisher is an approved Member
  2. authorize-publish   — publisher holds a live grant for EventType.publish_capability, in scope
  3. resolve-resources   — envelope.routing_resources → Resource(s) (reject if unknown)
  4. resolve-authorities — CapabilityGrants (ResourceScope) whose selector matches, per §1 semantics (all matches)
  5. resolve-subscriptions — Subscriptions matching event_type + resource_selector + filter(routing_metadata only)
  6. authorize-recipients — each holds EventType.receive_capability (+ ResourceScope authority where required)
  7. fan-out             — one EventDelivery per authorized recipient
  8. deliver             — async via the Phase-4 state machine, to each EndpointBinding (retry, timeout, dead-letter)
  9. audit               — every step to the immutable audit stream (metadata + hashes, not payloads)
```
The router inspects only `routing_metadata`/`routing_resources` — never a sealed payload.

**Symmetry with the service runtime.** Service-exchange = `discover→request→authorize→present→verify→fulfil→
outcome`; event-exchange = `publish→authorize→resolve→route→deliver`. Both authorize via the **same** grant
check, read the **same** Trust+Knowledge registries, audit to the **same** stream, and deliver via the **same**
async state machine. That shared spine makes them two *configurations of one platform*, not two engines.

## Two boundaries the review insisted on (and this ADR adopts)

**Transformations are ordinary participants, not a core primitive.** There is no special Transformation runtime.
A transformation is a participant that *subscribes* to one event, runs a domain algorithm (a component), and
*publishes* another:
```
subscribe: location.observation → [domain algorithm component] → publish: congestion.detected
subscribe: disease.case.reported → [epidemiological component]  → publish: disease.threshold.exceeded
```
The platform supplies only the subscribe/publish primitives; the algorithm stays a component. (ADR-0119/D3 is
amended to this framing.)

**The exchange carries trustworthy institutional events, not raw telemetry.** TOP may emit huge volumes of device
pings. The platform must be *able* to represent an observation event, but must **not** require every GPS ping to
traverse the authority-routing layer:
```
raw observation stream → Traffic-Intelligence Provider (participant) → actionable governed event → Trusted Event Exchange
```
This keeps the shared network optimized for trustworthy institutional exchange and sharply reduces the privacy and
scaling surface.

## How TOP becomes configuration (no core code)

- Resources: `road.segment`, `intersection`, `signal` ingested by a domain **driver** component.
- EventType `congestion.detected`: `routing_resource_type=road.segment`, `publish_capability=event.publish:
  congestion`, `receive_capability=event.receive:congestion`, `routable_attributes=[jurisdiction, level,
  confidence]`.
- Participants/grants: a sensing/intelligence provider (classification `observer`) with `event.publish:congestion`;
  municipality / traffic-police / TMC as authorities with ResourceScope grants over the relevant roads +
  `event.receive:congestion`; each holds a Subscription filtered to its jurisdiction via `routing_metadata`.
- Result: one congestion event routes to three authorities for three reasons — config + schemas + a domain driver,
  **no core edits**.

## Third-network proof correction — subject vs routing resource

A disease **case** is about a case/person (`subject`), but it is routed by **where** it must go
(`routing_resources` = a `health.jurisdiction`). The envelope's `subject`/`routing_resources` split (§6) carries
exactly this. The config uses an aggregate, de-identified routing event — `disease.threshold.exceeded` (produced
by an epidemiological transformation participant) — for institutional routing, keeping individual-case detail in a
sealed `payload`/`subject` rather than in `routing_metadata`. This exercises both patterns (event routing +
service/credential for vaccination/certification) in one network, and demonstrates the privacy boundary.

## Consequences

**Positive:** one grant mechanism; sensitive events route without operator payload access; transaction volume
stays out of the bitemporal registry and honors bounded retention; endpoints are governed (SSRF/rotation/signing
in one place); resource/authority resolution is deterministic and overlap-tolerant; transformations and raw
telemetry stay at the edges as participants. **Costs/risks:** the event store (ADR-0089) must be stood up as a
real store, not the registry; `routable_attributes` discipline must be enforced at publish (a publisher must not
smuggle sensitive data into routing metadata — validated against the EventType); geometry selectors and payload
sealing are later slices. **Sequencing:** Phase 3A/3B of the plan, with the async state machine (Phase 4A) landing
**before** the Router so delivery is never built synchronously-then-replaced.

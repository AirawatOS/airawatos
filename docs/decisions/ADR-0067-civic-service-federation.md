# ADR-0067 — Civic service federation: a network service directory + interaction protocol (Beckn-adapted)

- **Status:** Proposed (2026-08-28)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0023 (federation interaction model — Data/**Requests**/**Events**; this ADR
  builds the Requests/Events half), ADR-0024/0025 (participant message signing + signed catalogs — the trust
  boundary), ADR-0026 (agent = signed scoped delegate; `component:// obo user://`), ADR-0015 (data-at-source
  connectors + `/v1/resolve-ref`), ADR-0045/0050 (solution declaration + execution engine — the provider's
  runtime), ADR-0046/0048 (decision hourglass + Service→Case→Workflow→Task), ADR-0058 (interaction contracts +
  `interaction.receipt`), ADR-0066 (shared network assets). External reference: **Beckn Protocol v2**
  (`beckn.yaml`) — adopted as an *envelope model*, not verbatim.

## Context

We just built **data federation**: a certified component (a unified citizen app / aggregator) can READ and
WRITE another agency tenant's registry rows, gated by that tenant's steward-signed `governance.access_grant`,
attributed `component://<app> obo user://<citizen>`. That is sufficient to **view/update** records across
agencies **when every agency shares the AirawatOS registry substrate**.

It is **not** sufficient for the thing citizens actually want: **transacting a service across agencies** —
apply for a certificate, pay a bill, book a slot, track a grievance — where:

- agencies are **heterogeneous or data-at-source**: an agency may run its own system and expose an *endpoint*,
  not replicate its data into a shared registry;
- the interaction is a **transaction lifecycle**, not CRUD: discover → select → initiate → confirm → status →
  track, with **asynchronous** provider responses;
- the citizen app must **discover** which agency offers a service and **where to deliver** the request, in a
  **standard request format**.

This is the **Requests/Events** half of ADR-0023 (the **Data** half is now the grant lane). It is also exactly
the shape of **UPI / Beckn**: a citizen-facing app (BAP) discovers providers via a **registry**, sends a
structured request to a provider (BPP) **endpoint**, and receives async callbacks. UPI is a *service protocol*,
not a shared database — and that is the missing rail here.

**Why not just adopt Beckn v2 verbatim?** Its envelope (roles, async `action`/`on_action` lifecycle, signed
`context`+`message` split, registry-mediated discovery) is exactly right and battle-tested. But its **domain
vocabulary is commerce** (`intent`, `catalog`, `item`, `order`, `fulfillment`, `billing`, `payment`,
`quote`). Civic services are applications, eligibility, cases, fees, and receipts. We keep Beckn's **structure**
and swap its **nouns**, mapping onto vocabulary we already govern (`governance.*`, `platform.case/task`,
`finance.*`, `interaction.receipt`).

## Decision

Introduce a **civic service-federation layer**: a governed **service directory** at the Network layer + an
**async, signed interaction protocol** (Beckn-adapted) that routes a citizen's service request to the owning
agency's solution endpoint and carries the transaction lifecycle back. It sits **on top of** — and reuses —
the primitives we already have; it does not replace the grant lane.

### 1. Roles (Beckn → Airawat)

| Beckn | Airawat | Who |
|---|---|---|
| **BAP** (app platform) | **Requesting participant** — a certified aggregator app (unified citizen app, call-centre, unified billing) acting `obo` the citizen | e.g. `crowd-command`-class apps |
| **BPP** (provider platform) | **Providing participant** — an agency tenant's **solution** (ADR-0045/0050) that fulfils the service | e.g. a city's water/grievance solution |
| **BG / Registry** | **AirawatNetwork** — the **service directory** + **request gateway/router** | `network` service |

Every actor is an existing **participant with a published signing key** (ADR-0024). Discovery and every
message are **signed**; the gateway verifies against the directory.

### 2. The service directory (network layer)

A governed catalog artifact `network.service_offering`, published by an agency and signed by its steward
(same machinery as `network.data_offering` / schema catalog):

```
network.service_offering {
  offering_id, participant_id, tenant,
  service_id, domain,                      # governed domain vocab (ref.domain): urban, health, mobility, safety…
  title, description,
  interaction: [search, select, init, confirm, status, track, cancel, update, support],  # the lifecycle it supports
  request_schema, response_schema,         # governed schemas for the request/callback bodies (schema catalog)
  endpoint,                                 # WHERE the request is delivered (the solution's inbound URL / connector ref)
  access_mode: on_platform | data_at_source | connector,   # reuses ADR-0015 resolve-ref routing
  eligibility_ref?, fee_ref?, terms, sla_ref, status
}
```

Endpoints: `POST /v1/service-offerings` (publish, steward-gated), `GET /v1/service-offerings` (discover by
domain/service), `POST /v1/service-offerings/resolve`. This generalises the existing offerings registry;
`access_mode` reuses `/v1/resolve-ref`’s local / remote / connector routing (ADR-0015).

### 3. The interaction protocol (async, signed; civic-adapted Beckn)

Message envelope keeps Beckn's `context` + `message` split:

```
{ context: { transaction_id, message_id, action, bap_id, bpp_id, tenant, domain, timestamp, signature },
  message: <action-specific body, validated against the offering's request/response schema> }
```

Lifecycle (each `action` has a matching async `on_<action>` callback):

| Civic action | Purpose | Reuses |
|---|---|---|
| `search` / `on_search` | find services + providers for an intent | the service directory |
| `select` / `on_select` | eligibility + fee quote for a specific service | `eligibility_ref`, `finance.*` |
| `init` / `on_init` | open the application — **creates a `platform.case` at the provider** | ADR-0048 Service→Case |
| `confirm` / `on_confirm` | submit; provider commits + returns a reference | `governance.decision`/`platform.task` on the provider side |
| `status` / `on_status` | current state of the case | provider `platform.case.status` |
| `track` / `support` / `cancel` / `update` | lifecycle management | `platform.task`, receipts |

Rules:
- **Data-at-source by default.** The provider owns the case; the aggregator holds a **transaction handle**
  (`transaction_id` + the provider's case ref), not a copy. Where the citizen also wants the record mirrored
  locally, the aggregator uses the **grant lane** (ADR-this-session) — the two compose.
- **Signed + attributed end-to-end.** Every message is participant-signed (ADR-0024); every provider-side
  side-effect is stamped `component://<provider-solution> obo user://<citizen>` (the delegated attribution we
  built) and gets an `interaction.receipt` (ADR-0058) — so the whole cross-agency transaction is reconstructable.
- **Consent is explicit.** `init` carries the citizen's consent scope; the provider records it. (Per-citizen
  consent is a VC layer, ADR-0049 — see Open questions.)
- **The gateway routes; it does not hold data.** AirawatNetwork verifies signatures, resolves the offering's
  endpoint, forwards the request, and correlates the async callback by `transaction_id`. `POST
  /v1/service/route` (or the inbound gateway) + the existing `/v1/federation/{messages,inbox,events}` hub.

### 4. Vocabulary mapping (Beckn → civic)

`intent → service-intent` · `catalog → service-offering` · `item → service` · `order → application/case
(platform.case)` · `fulfillment → service-delivery` · `billing/payment → fee/payment (finance.*)` ·
`quote → eligibility+fee` · `rating/support → feedback/grievance`. Structure kept; nouns governed via the
schema catalog + `ref.domain`.

## What we REUSE (so this is additive, not a rewrite)

- **Participants + signing keys** (ADR-0024) — actors + message signing.
- **Directory + resolver** — `network.*_offering` registry + `/v1/resolve-ref` connector routing (ADR-0015).
- **Grant lane** (this session) — for any registry data the transaction reads/writes across tenants.
- **Delegated attribution** `component:// obo user://` (this session) — provider-side side-effects.
- **Service→Case→Workflow→Task** (ADR-0048) + **execution engine** (ADR-0050) — the provider's fulfilment.
- **interaction.receipt** (ADR-0058) — per-message provenance; **finance.*** for fees; **governance.decision**
  for admissions.
- The generic **file→list→decide** request pattern + `governance.access_grant` for the provider's onboarding
  of an aggregator (who may call which service).

## Consequences

- A citizen app can offer **one interface across agencies** for real transactions (apply/pay/book/track),
  including **heterogeneous / data-at-source** agencies — the UPI-for-civic-services rail.
- Providers keep **data at source** and their own case state; the network is a **thin signed router**, not a
  data lake.
- Adds an **async protocol surface** + a **gateway/registry role** to operate and secure, and a set of
  **governed message schemas** to maintain. Async correlation (`transaction_id`) and retries/timeouts need care.
- The commerce↔civic vocabulary divergence means we are **Beckn-inspired, not Beckn-conformant** — deliberate;
  an adapter to true Beckn networks is a possible future bridge.

## Alternatives considered

1. **Data federation only** (the grant lane): insufficient — no transaction lifecycle, assumes a shared
   registry, breaks for data-at-source/heterogeneous agencies.
2. **Adopt Beckn v2 verbatim:** right envelope, wrong nouns; forcing civic services into `order/item/payment`
   loses governance semantics (case, eligibility, decision, receipt) we already model.
3. **Point-to-point integrations per agency pair:** no directory, O(n²), no discovery, unsigned — doesn't scale
   to a network.

## Slices (proposed)

- **S1 — Directory + discovery:** `network.service_offering` schema + publish/list/resolve; `search/on_search`.
- **S2 — Open a case:** `init/on_init` → provider creates `platform.case` (ADR-0048), signed + attributed;
  aggregator gets a transaction handle.
- **S3 — Commit + status:** `confirm/on_confirm`, `status/on_status`; `interaction.receipt` per message.
- **S4 — Gateway + signing hardening:** network `/v1/service/route`, signature verification, `transaction_id`
  correlation, retries/timeouts; crypto-verify the calling component identity.
- **S5 — Fee + consent:** `select` eligibility/fee via `finance.*`; per-citizen consent scope on `init`
  (VC layer, ADR-0049).

## Open questions

- **Per-citizen consent** vs the per-component grant we have today — likely a VC/consent credential (ADR-0049)
  the citizen issues to the aggregator, referenced in `init`.
- **True-Beckn bridge:** expose civic services to external Beckn networks (and vice-versa) via an adapter?
- **Discovery trust:** how much the gateway curates/vets `service_offering`s vs open publication.

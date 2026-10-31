# Implementation Plan — Evolving AirawatOS into a generic Trusted Network Platform

- Date: 2026-10-31 (**rev 2, post-review**)
- Governs: **ADR-0119** (four planes + decisions D1–D11) and **ADR-0120 rev 2** (event plane).
- Posture: **evolve, do not restart.** New capability lands behind new module boundaries; no large rewrite of
  `app_host.py` / `network/api.py` (frozen-by-default, shrink opportunistically).
- Rev-2 changes from review: async state machine moved **before** the Router (no synchronous event delivery built
  to be immediately replaced); a shared **AuditEvent contract defined in Phase 1** (storage consolidated later);
  the **WalletProvider interface + credential-codec interface moved early**; **IdentitySource/AssurancePolicy**
  added to Phase 1; acceptance tests updated for three-valued logic, routing-metadata-only filtering, governed
  receive-capability, endpoint bindings, and subject-vs-routing-resource.
- **Review gates:** this doc + the two ADRs are gate #1. Each phase also stops for a detailed design review (object
  schemas + migration runbook) before its code is written.

## The narrowed assignment (scope boundary, verbatim)

> Refactor the domain model so that **Participant Classification, Membership and CapabilityGrant** are independent
> concepts. Introduce first-class **Offering** and **RequirementExpression** primitives. Then design and implement
> the minimum generic **Event Plane** (`Resource`, `CapabilityGrant`-as-authority, `EventType`, `Subscription`,
> `EndpointBinding`, `EventEnvelope`, `EventDelivery`, `Router`). Do not introduce TOP-specific vocabulary into
> core code. Demonstrate **Avsar, TOP and a third test network** entirely through configuration.

## The acceptance invariant (gate on the whole effort)

> Adding a new domain may require new schemas, services, transformations and configuration, but MUST NOT require
> modifying the core network runtime — **nor require new core objects** — merely because the domain has different
> nouns. **A new interaction pattern requires an explicit platform ADR.**

Final proof: **Avsar + TOP + public-health disease surveillance** configured with zero core-runtime edits and zero
new core objects.

---

## Sequencing at a glance

| Phase | Theme (priority #) | Depends on | Headline acceptance |
|---|---|---|---|
| 0 | Design freeze (this doc + ADRs) | — | you approve the design |
| 1 | Trust plane: typed grants, Network≠Tenant, IdentitySource; **+ AuditEvent contract** (1, 2, 10-gap) | 0 | type no longer authorizes; one identity, many networks; every authz decision emits a uniform AuditEvent |
| 2 | RequirementExpression + Offering; **+ WalletProvider & codec interfaces** (4, 5, 6-iface) | 1 | 3-valued eligibility evaluates; discovery by eligibility; wallet backend behind an interface |
| 3A | Event plane control objects (3) | 1 | Resource/EventType/Subscription/EndpointBinding govern; TOP's static config loads |
| 4A | Generic async transaction/delivery state machine (8) | 1 | retry/timeout/dead-letter/idempotency proven on service fulfilment |
| 3B | Router + EventEnvelope + EventDelivery (3) [ADR-0120] | 3A, 4A | **TOP routes an event to N authorities, no core edits**, via the async machine |
| 4B | Operator-neutrality controls (7) | 1–3 | admin self-grant blocked+audited; privileged paths enumerated+audited |
| 5 | Durability + unified audit **backend** (9) | 1–4 | restart loses nothing; Phase-1 AuditEvents queryable from one stream |
| 6 | Additional wallet providers + W3C VC codec (6, 10) | 2 | a second wallet provider + VC 2.0 codec drop in with no call-site change |
| ★ | **Three-network config proof** | 1–4 | **the acceptance invariant, demonstrated** |

Phases 2 and 3A can run in parallel after Phase 1. The key rev-2 ordering: **4A (async) lands before 3B (Router)**
so EventDelivery is never built synchronously then rewritten.

---

## Phase 1 — Trust plane correction *(priorities 1 & 2, + the IdP-registry gap, + the AuditEvent contract)*

Authorization moves from *type-implies-capability* to *explicit typed-scope grant*. Ship behind a migration.

- **1a — Capability catalog + `CapabilityGrant` with typed scopes.** One grant object/store/evaluator/revocation/
  audit; scope ∈ {Network, Resource, CredentialType, EventType, Service, OfferingCategory} (ADR-0119/D1).
- **1b — Split Classification / Membership / Grant.** Classification is descriptive vocab on Membership; strip all
  authorization meaning from type.
- **1c — Authz migration (the cutover).** Back-fill grants from current types (a per-network `type→capabilities`
  map); **dual-run** old (type) and new (grant) checks, log divergences; flip enforcement to grants only at **zero
  divergence**; retire the type check.
- **1d — Network as first-class object.** `Network {id:"net:…"}`; core resolves `network.id` + participant
  identity, not `token.tenant`. One `ParticipantIdentity` → many `Membership`s (tenant backing allowed physically).
- **1e — `IdentitySource` + `AssurancePolicy`** (ADR-0119/D11): governed abstraction only; session assurance feeds
  the Phase-2 evaluator as a `ContextPredicate`. (Real eShram/Aadhaar integration is a separate track.)
- **1f — AuditEvent contract (define now, store-consolidate in Phase 5).** A single uniform record
  `{ts, network, actor, action, capability?, scope?, decision(allow|deny|unknown), subject_hash?, correlation_id,
  explanation}`. **Every** grant change, migration step and authorization decision in Phases 1–4 emits one — so
  Phase 5 consolidates storage, not reinvents records.

**Acceptance (Phase 1):**
- A participant classified `insurer` **cannot** issue a credential until granted `credential.issue:<type>`;
  revoking the grant blocks the next issuance immediately.
- Dual-run divergence report = zero before the enforcement flip; `grep` of core for type-based authorization = zero
  after cutover.
- One organization joins two networks with a single identity; no second org identity is minted.
- Every authz decision in a scripted run appears as a uniform AuditEvent with actor + capability + decision.

**Review checkpoint:** the `type→capabilities` back-fill map, the dual-run/flip runbook, and the frozen AuditEvent
schema — before 1c code.

## Phase 2 — RequirementExpression + Offering *(priorities 4 & 5, + wallet/codec interfaces early)*

- **2a — Expression evaluator (shared library).** Typed predicates (Credential/Event/Resource/Participant/Context)
  + **three-valued logic** `SATISFIED/UNSATISFIED/UNKNOWN`; result `{result, evidence_used, missing, explanation}`
  (ADR-0119/D4). One evaluator; per-type resolvers. Absence of evidence must not satisfy `not`.
- **2b — `Offering` + discovery.** Offering as discovery object; Service as the bound executable capability;
  discovery optionally filters by "I qualify"; `apply` invokes the Service.
- **2c — `WalletProvider` interface + `CurrentManagedWallet` (moved early, ADR-0119/D6).** Issuance/presentation
  call sites depend on the interface; the existing store becomes the default provider. **Additional providers
  (DigiLocker/external/self-custodied) are Phase 6** — but no new code may deepen coupling to the current store.
- **2d — Credential codec interface (early; second codec in Phase 6).** Wrap the native signed-JSON behind a codec
  seam so no new code hardens W3C-vs-native assumptions.

**Acceptance (Phase 2):**
- `all[ worker-registration, any[ platform-work(activeDays>=90), employment(durationMonths>=6) ] ]` returns the
  right `SATISFIED/UNSATISFIED/UNKNOWN`; a missing-evidence case returns **UNKNOWN**, not auto-pass on `not`;
  `missing[]`/`explanation[]` name the gap.
- Discovery returns only offerings whose eligibility the caller satisfies; `apply` routes to the bound service.
- A no-op second WalletProvider stub can be selected without changing issuance/presentation call sites.

## Phase 3A — Event-plane control objects *(priority 3; ADR-0120)*

Govern `Resource` (exact + hierarchy + type+jurisdiction selectors; geometry deferred), `EventType`
(with `publish_capability` **and** `receive_capability` + `routable_attributes`), `Subscription` (no
`capability_required`; references a `delivery_binding_ref`), and `EndpointBinding` (participant-owned, pre-
registered; raw URLs never enter via a subscription). Reuse Phase-1 grants as ResourceScope authorities.

**Acceptance (Phase 3A):** TOP's resources/event-types/subscriptions/bindings load as config; a Subscription cannot
weaken the EventType's governed `receive_capability`; a subscription with a raw URL (no binding ref) is rejected.

## Phase 4A — Generic async transaction/delivery state machine *(priority 8; before the Router)*

`request→ACCEPTED→processing→(status|event)*→COMPLETED|REJECTED` with idempotency keys, retries, timeouts,
duplicate handling, dead-letter, compensation hooks (ADR-0119/D8). Proven first on **service fulfilment**; it is the
substrate the Router's EventDelivery will use.

**Acceptance (Phase 4A):** a dropped external service call retries then dead-letters (never silently lost); a
duplicate request with the same idempotency key does not double-execute.

## Phase 3B — Router + EventEnvelope + EventDelivery *(priority 3; ADR-0120)*

The Router pipeline (authenticate → authorize-publish → resolve-resources → resolve-authorities →
resolve-subscriptions → authorize-recipients → fan-out → deliver → audit). `EventEnvelope` separates
`routing_metadata`/`routing_resources`/`subject` from `payload` and carries `event_type_version` + occurred/
published/received/expires timestamps; it lives in the **ADR-0089 event store**, not the registry. `EventDelivery`
= one per (envelope, subscriber), on the Phase-4A machine; **`delivered` = endpoint acknowledged acceptance**, not
acted-on.

**Acceptance (Phase 3B):**
- **TOP with zero TOP code**: `congestion.detected` on a `road.segment` routes to three authorities by jurisdiction
  + subscription; the router reads only `routing_metadata` (a sealed `payload` is never inspected).
- A publisher lacking `event.publish:congestion` is rejected at step 2; a subscriber lacking `event.receive:
  congestion` never gets an EventDelivery.
- An envelope whose `expires_at` has passed is rejected as stale.
- `grep` of core event-runtime for `traffic|road|congestion|disease` = zero (domain only in config/driver).

## Phase 4B — Operator-neutrality controls *(priority 7)*

Enumerate + audit every privileged-operator access path; constrain governance self-modification (signed
change-request + audit + optional dual-control — **no silent self-grant**); record the payload-sealing roadmap
item (ADR-0103). Target: governing a network must not imply visibility into user transaction payloads.

**Acceptance (Phase 4B):** an admin attempt to self-grant a capability is blocked or forced through an audited
change-request, visible in the AuditEvent stream; the set of privileged payload-access paths is enumerated and each
emits audit.

## Phase 5 — Durability + unified audit backend *(priority 9)*

Resolve the two-store question (move authoritative governance state onto the durable governed registry, or document
why two stores exist + guarantee the network KV's durability — no in-memory authoritative state survives a restart).
Stand up the **audit backend** that consolidates the Phase-1 AuditEvent records into one queryable immutable stream
(metadata + payload hashes, not payloads).

**Acceptance (Phase 5):** a full restart loses no governance/cert/request/grant state; every authz decision and
state transition from Phases 1–4 is queryable from the single stream.

## Phase 6 — Additional wallet providers + W3C VC codec *(priorities 6 & 10)*

With the interfaces already in place (2c/2d): add a second concrete `WalletProvider` (e.g. participant-hosted /
self-custodied / DigiLocker) and **W3C VC 2.0 as a second codec** beside the native signed-JSON.

**Acceptance (Phase 6):** a credential round-trips through both codecs with stable verification; a second wallet
backend works with no change at issuance/presentation call sites.

---

## ★ Three-network configuration proof (closes the invariant)

Gated after 3B (functional) and finalized after 4A/4B (reliable + neutral). Stand up three networks **by config
only** — schemas + network config + optional domain driver/transformation *components* (which are participants),
**zero core-runtime edits and zero new core objects**:

1. **Avsar** (service/credential): worker/employer/insurer participants; offerings; eligibility expressions;
   credential issuance into wallets.
2. **TOP** (event): observer + three authorities over road resources; `congestion.detected` routing by jurisdiction
   + subscription; optional observation→congestion transformation *participant*.
3. **Public-health disease surveillance** (**both** patterns): a lab publishes the de-identified aggregate
   `disease.threshold.exceeded` (produced by an epidemiological transformation participant) with `subject` = the
   case/person (sealed) and `routing_resources` = a `health.jurisdiction` → router resolves the health authority →
   authority invokes a response Service; vaccination/certification run as Offerings issuing Credentials.

**Final gate:** the diff of the core network runtime across standing up all three networks is **empty**, and no new
core object was introduced. Any required core edit/object is a design bug to fix, not a feature.

---

## What this plan deliberately does NOT do yet

- No large rewrite of `app_host.py` / `network/api.py`.
- No exotic cryptographic neutrality (D7 target is explicit+audited+removable, not ZK now).
- No selective-disclosure / ZK predicate proofs (follow-on once the expression evaluator is clean).
- No end-to-end payload sealing yet (the envelope split in 3B makes it *possible*; enabling it is a later slice).
- No eShram/Aadhaar real integration or eKYC de-simulation (separate track; the IdentitySource abstraction here is
  what it will plug into).

## Next step after your review

On approval, for **Phase 1** and before coding it, I will produce: the registry schema definitions for
`CapabilityGrant`/`Network`/`Membership`/`IdentitySource`/`AssurancePolicy`, the frozen **AuditEvent** schema, and
the **authz-migration cutover runbook** (type→capabilities map, dual-run, flip) — for a second design review. Code
begins only after that.

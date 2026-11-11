# ADR-0119 — Trusted Network Platform: Four-Plane Reference Architecture & Core Ontology Corrections

- Status: **Approved as architectural direction (2026-10-31); amended post-review — see Amendments**
- Date: 2026-10-31 (amended 2026-10-31)
- Refines: the architecture framing of **ADR-0118** (which described the platform as "one large runtime"; this ADR
  decomposes it into four orthogonal planes). **ADR-0117** stays valid as the *service-exchange configuration*,
  now expressed through these planes.
- Companion: **ADR-0120** (the generic Event Plane detailed design).
- Driver: an independent architecture review of the as-built system (`docs/REVIEW-PACK-trusted-network-platform.md`,
  2026-10-31) concluded the platform is a credible *generic service/credential core* but **not yet** a generic
  Trusted Network Platform, and proposed ten ontology/engineering corrections and a four-plane abstraction. This
  ADR adopts them as the design direction. **It changes the domain model; it does not restart the codebase.**

---

## Context

The as-built system cleanly separates generic engine/control code from domain content (the kernel and network
authority carry essentially no livelihood-specific logic; native and external participants already share one
service abstraction). But five ontology weaknesses block the leap to a *generic* platform:

1. **Capability is inferred from participant *type*.** "Insurer"/"employer"/"authority" implies what you may do.
   Too weak for a trust network.
2. **Network is modelled as "a tenant carrying `network.admin`."** Convenient operationally; wrong as a domain
   model. An org that joins two networks should not need two organizational identities.
3. **There is no event/resource/authority plane.** Event-exchange networks (TOP) cannot be *configured* — they
   require new code.
4. **Requirements are a flat `required_credentials[]`.** Cannot express real eligibility.
5. **No first-class `Offering`.** Discovery is approximated across `network.service` + `service-offering` +
   workflow requirements.

Plus engineering debt: synchronous-only federation; operator neutrality enforced only at the API layer; a second
authoritative store (network KV) beside the durable registry; no unified audit stream; credentials hardwired to
one on-the-wire format; two large mixed-responsibility files.

## Decision

Adopt a **four-plane reference architecture**. The platform is one system presented as four orthogonal planes;
each network is a *configuration* that uses the planes it needs. Service-exchange (Avsar) and event-exchange (TOP)
are two **runtimes in the Exchange plane** standing on the same Trust, Knowledge and Governance planes — not two
engines.

```
                      ┌───────────────────────── Experience ──────────────────────────┐
                      │  reference apps · Client SDK · portal/front-door · admin & dev  │
                      └───────────────────────────────────────────────────────────────┘
   ┌───────────── TRUST ─────────────┐   ┌─────────── KNOWLEDGE ───────────┐
   │ ParticipantIdentity             │   │ Schema (governed vocab)          │
   │ Network (governed ecosystem obj)│   │ Resource        (ADR-0120)       │
   │ Membership (classification)     │   │ CredentialType / Credential      │
   │ CapabilityGrant (typed scopes)  │   │ EventType       (ADR-0120)       │
   │ IdentitySource · AssurancePolicy│   │ Offering                         │
   └─────────────────────────────────┘   └──────────────────────────────────┘
   ┌──────────── EXCHANGE ───────────┐   ┌─────────── GOVERNANCE ───────────┐
   │ Service-Exchange runtime:       │   │ RequirementExpression evaluator   │
   │  discover→request→present→      │   │  (typed predicates, 3-valued)     │
   │  verify→fulfil→outcome          │   │ Network configuration             │
   │ Event-Exchange runtime (0120):  │   │ Certification & conformance       │
   │  publish→resolve→authorize→     │   │ Versioning                        │
   │  route→deliver                  │   │ Immutable audit stream            │
   │ Presentations · Subscriptions   │   │ Operator-neutrality controls      │
   │ Async transaction state machine │   │                                   │
   │ (EventEnvelope/Delivery live in │   │                                   │
   │  the ADR-0089 event store, not  │   │                                   │
   │  the governed registry)         │   │                                   │
   └─────────────────────────────────┘   └──────────────────────────────────┘
```

**Plane ↔ pattern usage.** Avsar leans on **credentials + offerings + requests** (Knowledge+Exchange over
Trust/Governance). TOP leans on **resources + events + subscriptions + authority** (Knowledge+Exchange over
Trust/Governance). The planes are shared; only the *configuration and the Exchange runtime exercised* differ.

### The ten corrections, as decisions

**D1 — Classification, Membership and CapabilityGrant are independent (Trust plane).** *This is the central
correction; do it first.*
- `ParticipantIdentity` — a stable, network-independent organizational/person identity (keys, directory entry).
- `Classification` — a descriptive, governed vocabulary term *within a network* (`insurer`, `employer`,
  `traffic-authority`, `laboratory`). Carries **no** authorization.
- `Membership` — edge `(participant, network, status∈{pending,approved,suspended,revoked}, classifications[])`.
  Gates belonging, not capability.
- `CapabilityGrant` — `(grantee, network, capability, scope, constraints, validity, grantor)`. Capabilities are
  network-defined strings, e.g. `credential.issue:work-experience`, `event.publish:congestion`,
  `event.subscribe:congestion`, `resource.act:signal-control`, `service.provide:insurance-enrolment`,
  `offering.publish:<category>`. **Scope is a typed value**, not free text:
  `scope ∈ { NetworkScope | ResourceScope | CredentialTypeScope | EventTypeScope | ServiceScope |
  OfferingCategoryScope }`. **Authorization = "holds a live CapabilityGrant for the required capability, in
  scope"**, never "is of type X". Grants are independently, immediately revocable.
  *There is exactly ONE grant object, store, evaluator, revocation path and audit model.* "AuthorityGrant"
  (ADR-0120) is **terminology** for a CapabilityGrant whose scope is a `ResourceScope` — not a second mechanism.
  Authority (a grant = permission) and interest (a Subscription = standing desire to receive) are distinct;
  mandatory receipt is a governance-created mandatory Subscription, never a side effect of a grant.

**D2 — Network is a first-class governed object, distinct from Tenant (Trust/Governance).**
- `Network {id:"net:<slug>", name, charter, governance_tenant, classifications[], capability_catalog[],
  governed(schemas/resources/event_types/offering_categories), identity_sources[], features{}, planes_used[]}`.
- `Tenant` stays the administrative/data workspace (kernel concept, unchanged).
- A `ParticipantIdentity` joins *many* Networks with one identity. **Physical note:** a Network MAY still be
  backed by a tenant initially, but core code resolves `network.id` + participant identity — never
  `token.tenant` — as the network identity. Decoupling the *model* now prevents the convenience from hardening
  into the domain.

**D3 — Build a generic Event Plane, not a TOP implementation (Knowledge/Exchange).** Detailed in **ADR-0120**:
four governed records (`Resource`, `EventType`, `Subscription`, `EndpointBinding`) + two event-store records
(`EventEnvelope`, `EventDelivery`) + a `Router`, reusing the Trust-plane `CapabilityGrant`. No TOP vocabulary in
core. **Transformation is not a core primitive**: a transformation is just a *participant* that subscribes to one
event, runs a domain algorithm (a component), and publishes another (`observation → congestion.detected`;
`disease.case.reported → disease.threshold.exceeded`). The platform supplies only subscribe/publish; the algorithm
stays a component. Raw high-volume telemetry stays at the edge (an intelligence provider turns it into actionable
governed events); the exchange carries trustworthy *institutional* events, not every device ping.

**D4 — RequirementExpression = a generic typed-predicate expression tree with three-valued logic (Governance),
shared by offering eligibility, service authorization, and event-subscription filters.** *(Renamed from
"RequirementManifest"; generalized per review — a credential-only predicate cannot also filter events.)*
```
Expression := all[Expression…] | any[Expression…] | not(Expression) | Predicate
Predicate   := CredentialPredicate | EventPredicate | ResourcePredicate | ParticipantPredicate | ContextPredicate
  CredentialPredicate := { credential_type, issuer?, claim_path, op, value, freshness_days?, assurance_level? }
  EventPredicate      := { field_path, op, value }          // over an EventType's declared routable_attributes
  ResourcePredicate   := { resource_selector | attribute_path, op, value }
  ParticipantPredicate:= { classification? | capability? | membership_status? }
  ContextPredicate    := { jurisdiction? | session_assurance? | time? }
  op ∈ { exists, eq, neq, gte, lte, in }
```
**One evaluator, different predicate resolvers.** It uses **three-valued logic** — `SATISFIED / UNSATISFIED /
UNKNOWN` — because absence of evidence does not prove a negative (failing to find a conviction credential does not
prove no conviction; this matters the instant `not` and `neq` exist). Result:
```json
{ "result": "SATISFIED | UNSATISFIED | UNKNOWN", "evidence_used": [], "missing": [], "explanation": [] }
```
The same tree powers *authorization* ("may proceed"), *discovery* ("offerings I qualify for"), and *event
filtering*. Example that must express: `all[ CredentialPredicate(worker-registration),
any[ CredentialPredicate(platform-work, activeDays>=90), CredentialPredicate(employment, durationMonths>=6) ] ]`.

**D5 — Offering is first-class (Knowledge); Service is the executable capability behind it (Exchange).**
`Offering {id, network, provider, category, title, geography, eligibility:Manifest, service_binding, outputs,
validity, visibility}`. Discovery queries offerings (optionally eligibility-filtered); `apply` invokes the bound
Service. Jobs/training/insurance/benefits/registrations are all Offerings.

**D6 — Wallet is a provider interface, not the current store (Knowledge/Exchange).** Define `WalletProvider`
(`platform-managed | DigiLocker | participant-hosted | self-custodied`). The current platform store becomes the
*default provider* behind the interface. Call sites depend on the interface before anything else couples to the
storage model — otherwise "worker-controlled credentials" silently becomes "operator-held worker credentials."

**D7 — Operator neutrality is explicit, audited, and progressively removable (Governance).** Don't reach for
exotic crypto now. Instead: (a) classify every privileged-operator access path and make it emit audit;
(b) constrain governance self-modification — an admin cannot silently self-grant (governance changes require a
signed change-request, are audited, and support optional dual-control); (c) set the target: *governing a network
must not imply visibility into user transaction payloads*, with envelope/payload sealing on the roadmap.

**D8 — Async federation via a generic transaction state machine (Exchange).** One state machine
`request→ACCEPTED→processing→(status|event)*→COMPLETED|REJECTED` with idempotency keys, retries, timeouts,
duplicate handling, dead-letter and compensation hooks — shared by service fulfilment **and** event delivery.
Async is the normal case for government/insurance/credit workflows.

**D9 — Unify durability and audit (Governance).** Either move authoritative governance state onto the durable
governed registry, or record a very explicit reason two authoritative stores exist and guarantee the KV store's
durability. Add a first-class **immutable audit stream** spanning all planes (authz decisions, grants, issuances,
deliveries) rather than reconstructing audit from scattered tables + provenance.

**D10 — Credential on-the-wire format is a codec, not an assumption (Knowledge).** Keep the native
Ed25519/JCS-signed JSON as one codec; add **W3C VC 2.0 as a second codec** once issuer-trust, schema governance,
revocation, subject binding, wallet portability and presentation semantics are clean. Do **not** embed
W3C-specific assumptions into the kernel. This is an interoperability item, not an architectural one.

**D11 — `IdentitySource` and `AssurancePolicy` are first-class Trust-plane objects (added post-review).** The
as-built system has no IdP registry; external identity plugs in only via the single trusted-issuer map. Model the
*abstraction* now (real eShram/Aadhaar integration stays a separate track):
```
IdentitySource  { id, network, issuer, jwks, assurances_provided[] }       # e.g. eshram → [worker-verified]
AssurancePolicy { id, network, accepts[] }                                 # e.g. worker-basic → [eshram.worker-verified, aadhaar.identity-proofed]
```
A Network references `identity_sources[]` and per-classification/offering `AssurancePolicy`. The session's
assurance (from the IdentitySource that authenticated the principal) becomes a `ContextPredicate` input to the D4
evaluator. This replaces the hardcoded `assurance:A0` and the implicit trust map with governed, configurable
identity acceptance.

**Cross-cutting — module boundaries.** New capability lands behind a new module boundary. No new routes are
appended to `app_host.py` (10k L) or `network/api.py` (3.5k L) merely to add a feature. No large rewrite is
triggered either; the two files are frozen-by-default and shrink opportunistically.

### Acceptance invariant (the test every change is measured against)

> Adding a new domain may require new **schemas, services, transformations and configuration**, but MUST NOT
> require modifying the **core network runtime** merely because the domain has different nouns — **and adding a new
> domain must not require new core *objects* merely because the domain has a new noun. Adding a new interaction
> *pattern* (beyond service-exchange and event-exchange) MUST require an explicit platform ADR.**

The second clause (added post-review) is the guard against erosion: it prevents "just one special object for
health" or "just one special router for transport" from quietly accumulating. A new *noun* is config; a new
*object* or *pattern* is an architectural decision that goes through an ADR.

Operationalized: (a) the core Exchange/Trust/Governance runtime contains **no domain string literals**;
(b) three deliberately different networks — **Avsar** (service/credential), **TOP** (event), **public-health
disease surveillance** (both) — are stood up **by configuration only** (schemas + config + optional domain
*transformation components*, which are participants, not core), with zero edits to core runtime code *and* zero
new core objects.

### Third-network proof — public-health disease surveillance (deliberately unlike the other two)

Exercises **both** patterns in one network, proving they coexist as generic patterns:
- Event pattern: `laboratory` (classification) with `event.publish:disease.case.reported` grant publishes an
  `EventEnvelope` bound to a `health.jurisdiction` `Resource` → Router resolves the jurisdiction's health
  authority (`AuthorityGrant`) and matching `Subscription`s → authority invokes a response `Service` (request
  pattern).
- Service/credential pattern: vaccination/certification run as `Offering`s whose `Service` issues a
  `Credential` into the recipient's wallet.

If this configures with no core edits, service-exchange and event-exchange are demonstrably generic — not an
Avsar engine plus a TOP engine.

## Consequences

**Positive:** authorization becomes explicit and revocable; one org identity across networks; TOP (and arbitrary
event domains) become configuration; eligibility/discovery/authorization share one policy engine; wallet and
credential format become swappable; neutrality becomes auditable and improvable; async + unified audit raise
production-readiness. The already-generic Client SDK surface (`discover/request/wallet/present/verifyPresentation`)
is preserved and extended, not replaced.

**Costs / risks:** a real domain-model migration (type→grant authorization is a breaking change to the authz
path — must ship behind a migration that back-fills grants from existing types before flipping enforcement);
Network-vs-Tenant decoupling touches identity and routing assumptions; the event plane is net-new surface. All are
sequenced in `docs/PLAN-trusted-network-platform-evolution.md` with per-slice acceptance tests, trust-model-first.

**Relationships:** refines ADR-0118; keeps ADR-0117 (service-exchange config) and ADR-0116 (participant≠tenant —
D2 completes it at the domain level); event plane detailed in ADR-0120; reuses ADR-0089 (event/message spine),
ADR-0053 (common resource IDs), ADR-0103 (consent/sealing), ADR-0049 (credentials), ADR-0084 (trust map),
ADR-0063 (interface bindings), ADR-0067 (service gateway), ADR-0112 (embed/Client SDK).

---

## Target object model (the clean end-state these decisions produce)

```
TRUST        ParticipantIdentity · Network · Membership · Classification · CapabilityGrant(typed scope)
             · IdentitySource · AssurancePolicy
KNOWLEDGE    Schema · Resource · CredentialType · Credential · EventType · Offering
GOVERNANCE   RequirementExpression · Policies · Versioning · Conformance · Audit
EXCHANGE     ServiceRequest · Presentation · Subscription · ServiceTransaction · EventEnvelope*
             · EventDelivery* · EndpointBinding · Router · Async-State-Machine        (* = event store, not registry)

Avsar        = Offering + Credential + Request heavy
TOP          = Resource + Event + Subscription + Authority(=ResourceScope grant) heavy
Public health = both
```

## Amendments (2026-10-31, post-approval review)

Direction approved; the following refinements were folded in to keep ADR-0119/0120/plan consistent:
- **D1** — one grant object with **typed scopes**; `AuthorityGrant` is terminology (ResourceScope), not a second
  object; authority ≠ interest (mandatory receipt = governance-created mandatory Subscription).
- **D3** — Transformation is **not** a core primitive but a participant that consumes+publishes; raw telemetry
  stays at the edge; object count corrected (no separate `AuthorityGrant`).
- **D4** — `RequirementManifest` → generic **`RequirementExpression`** with typed predicates (Credential/Event/
  Resource/Participant/Context) and **three-valued logic** (`SATISFIED/UNSATISFIED/UNKNOWN`), resolving the
  earlier credential-only-predicate contradiction with ADR-0120's event filters.
- **D11 (new)** — `IdentitySource` + `AssurancePolicy` added to the Trust plane (the review's IdP-registry gap);
  given a Phase-1 slice in the plan.
- **Invariant** strengthened: new *object* or new *pattern* requires an ADR, not just config.
- Event-plane storage split (EventEnvelope/EventDelivery out of the bitemporal registry) reflected in the diagram;
  full detail in ADR-0120 rev 2.

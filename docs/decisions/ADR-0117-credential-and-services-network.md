# ADR-0117 — The configurable credential-and-services network (Avsar-class networks)

- Status: Proposed (design, rev 2 — incorporates architecture review)
- Date: 2026-10-31
- Scope: this ADR is the **Service-Exchange (credential) configuration/pattern of the generic Trusted Network
  Platform defined in ADR-0118**. ADR-0118 is the umbrella (generic platform + Event-Exchange + Transformation
  patterns + resources/authority/subscriptions); this ADR details the credential/offering/service pattern (Avsar).
- Related: ADR-0116 (participant ≠ tenant · membership + provide/consume + eKYC join),
  ADR-0049 (verifiable credentials: issue/verify/revoke + Document Wallet), ADR-0084 (federated
  trust map / register_issuer), ADR-0112 (participant-embed: citizen auth, PKCE, the SDK basis),
  ADR-0058 (interaction contracts / interfaces = the VERB leg), ADR-0063 (interface bindings:
  verb → endpoint), ADR-0067 (service directory + gateway + consent), ADR-0039 (federated identity),
  ADR-0088 (data-exchange / domain-services realization spectrum), ADR-0028 (civic personas / roles),
  ADR-0056 (decided change-request)

## Context

A ministry wants to launch a network like **Avsar** (a livelihood network for workers): platforms, employers
and workforce intermediaries issue **work-experience / employment credentials** and publish **jobs**; **eShram**
holds the authoritative worker registration (Aadhaar-seeded, 12-digit UAN) and may issue a worker credential;
**ITIs** issue training credentials and publish learning opportunities; **insurers / lenders / benefit
providers** offer services with eligibility rules; and **workers** register, get a **livelihood account +
portable credentials**, discover and avail all of this — in the Avsar portal **or inside whatever app they
already use** (a platform worker app) via a standard SDK.

The wrong way to build this is to *scaffold Avsar*. The right question is: **what generic primitives must the
Airawat Stack expose so an Avsar-class network is purely a configuration** — plug in an identity/assurance source
(Aadhaar), plug in an existing system of record (eShram, a Farmer Registry, NRLM) as a participant, and hand
every agency a standard client SDK. This ADR defines that configuration model. **Avsar is one set of values for
these knobs, not a special-purpose application.**

ADR-0116 established the spine: a network is a tenant with `network.admin`; membership is a tenant-free contract;
an individual can join via eKYC against a trusted identity source, auto-admitted, reusing a single identity +
wallet. This ADR adds the **evidence layer** (credentials), the **offering/eligibility model**, the
**control/data-plane split**, and the **reach** (SDK) — and states them as generic knobs.

> Note on real systems (target vs current): public eShram documentation indicates registration is Aadhaar-seeded,
> issues a UAN, and uses UIDAI for Aadhaar authentication; it exposes scheme discovery and worker services. Whether
> it issues a *standards-based verifiable credential today* is treated here as **target architecture**, not a
> claim about current capability. Aadhaar is an **identity-proofing / authentication** source — not inherently an
> OIDC provider unless an adapter exposes it as one. DigiLocker already provides a government-backed document-wallet
> model (issuers publish authentic documents; users share with permission), which is why the wallet below is an
> **interface**, not an Avsar-owned custodian.

## Decision — the core ontology

A credential-and-services network is one loop over eight generic nouns, riding on shared infrastructure:

```
Participant → Offering → Requirement → Request → Authorization → Evidence → Fulfilment → Outcome/Credential
         (shared infrastructure: identity & assurance · wallet · trust map · gateway · SDK)
```

Everything below is a layer of that ontology. None is domain-specific; a health, procurement, or farmer network
instantiates the same layers with different values.

### 1. Identity & assurance — sources, not one "IdP"
Separate three things that the earlier draft blurred: **identity proofing/authentication**, **participant
identity**, and **credentials**. A network declares the assurance **sources** it trusts and an **assurance
policy** per participant type — never a single hardcoded `verified_by`:

```
identity_sources:
  - id: aadhaar        kind: auth           role: identity proof / authentication
  - id: eshram         kind: registry       role: authoritative worker record · UAN · (may issue a worker credential)
  - id: farmer-reg     kind: registry       role: authoritative farmer record            # another network's source
network.participant_type.worker.identity_assurance:
  policy: worker-basic
  accepts: [ aadhaar-auth, eshram-verified ]     # any acceptable path satisfies the policy
```

Trust in each source is established with the existing handshake (ADR-0084 `register_issuer`). This lets
`Avsar Punjab` verify by eShram, `Avsar Farmers` by a Farmer Registry, `Avsar SHG` by NRLM — the knob, not the
provider, is the abstraction.

### 2. Participants — native OR external, one contract; capability by grant, not by type
A participant is **either** a native platform tenant **or** an external system of record, and the network's
**Network Service Contract is identical** for both. This is a core principle: eShram, a platform, an insurer do
not migrate onto Avsar — Avsar orchestrates them without owning their systems of record.

```
A participant may be realized as:
  1. Native   — the service runs as a platform component (binding: engine:<component_id>)
  2. External — an existing system fulfils the service at a standards-compliant endpoint (binding: endpoint:<url>)
Both expose exactly the same Network Service Contract.
```

**Participant type is vocabulary, not capability.** Types are a governed role vocabulary —
`government-registry · platform · employer · fleet-operator · staffing-provider · training-provider ·
credential-issuer · insurer · lender · benefit-provider · marketplace · worker` — but what a participant may DO
comes from explicit **roles + capability grants**, so one participant can wear several hats:

```
participant: FleetCo
  roles: [ service-provider, credential-issuer ]
  authorized_credentials: [ VehicleAssignmentCredential, WorkEngagementCredential ]
```

The employment relationship can sit anywhere in the chain, so the topology is intermediary-aware:

```
Platform Aggregator ──┬── directly engages worker
                      └── Workforce / Fleet Partner ── Worker
```

### 3. Offering — the first-class unit of what a worker can get
Jobs, training, insurance, loans, benefits, and registrations are **one object**, an **Offering** — not separate
primitives. This is what unifies the network and the SDK.

```
Offering = { id, provider, category, title, description, geography, eligibility(=Requirement), service(ref), validity }
```

### 4. Services vs network primitives — don't conflate business + mechanism
A **Service** is business-facing; the **network primitives** are the mechanisms used to execute it. "90-Day Work
Certification" is a service; `issue` is its *outcome*. "Accident-Insurance Enrolment" is a service; `verify` is a
*step*. So:

```
network.service = { service_id, type, provider, requirements(=Requirement), interface, binding, outputs, lifecycle }

example  service: accident-insurance   provider: insurer-x
         requirements: <manifest, see §5>
         binding: endpoint:https://insurer-x/...     outputs: [ InsuranceCoverageCredential ]   lifecycle: async

NETWORK PRIMITIVES (the governed verbs the gateway speaks):
   discover · request · authorize · present · verify · invoke · issue · status · revoke · audit
```

### 5. Requirement — a Credential/Eligibility Manifest, not a flat list
Eligibility is a nestable boolean of credential predicates with issuer / freshness / assurance / jurisdiction
constraints:

```yaml
requirements:
  all:
    - credential: EshramWorkerCredential
      claims: { registrationStatus: ACTIVE }
    - any:
        - credential: WorkExperienceCredential
          claims: { activeDays: { gte: 90 } }
          issuer: { participant_type: [ platform, employer ] }
          freshness: 180d
          assurance_level: verified
        - credential: EmploymentCredential
          claims: { durationMonths: { gte: 6 } }
    - claim: { age: { gte: 18 } }
    - claim: { occupation: { in: [ "...", "..." ] } }
```

This drives both **eligibility matching** (can this worker get this offering?) and **discovery** (show offerings
the worker already qualifies for).

### 6. Credential vs certificate
Internally everything is a **Credential** — a signed assertion of claims (`EshramWorkerCredential`,
`WorkExperienceCredential`, `WorkEngagementCredential`, `TrainingCredential`, `InsuranceCoverageCredential`,
`RepaymentCredential`, `VehicleAssignmentCredential`). A **certificate** is just one *human-readable rendering* of
a credential. User-facing UX may say "90-day Experience Certificate"; the data model, schemas, and APIs say
*credential*.

### 7. Wallet — an interface, not an Avsar custody
**Credentials remain portable with the worker, independent of the application through which the worker accesses
the network.** The wallet is a provider interface, not an Avsar-owned store:

```
Wallet Provider Interface
   ├── Managed Avsar wallet (ADR-0049)
   ├── DigiLocker
   ├── Participant-hosted wallet
   ├── Third-party wallet
   └── Future self-custodied wallet
```

### 8. Control plane vs data plane — neutrality
Governance and execution are separate planes. A tenant holding `network.admin` administers the **control plane**
but must **not** thereby become a privileged intermediary in every worker transaction (the **data plane**):

```
CONTROL PLANE : network profile · participant registry · trust/authz policies · credential schemas ·
                service & offering definitions · identity-source config · network governance
DATA PLANE    : gateway · discovery · request/invoke · presentation · consent/authorization · verify ·
                issuance · events/callbacks · audit
```

### 9. Fulfilment is async-first
Government, credit and insurance services rarely complete synchronously, so async is first-class:

```
request → ACCEPTED → (participant processing) → status callback/event → COMPLETED | REJECTED → credential if applicable
```

### 10. Network Client SDK — reach, config-driven
A standard client any participant embeds in its own app. It authenticates the worker via the network's assurance
policy, then exposes the **generic** operations — not hardcoded screens — so the network config decides what
appears:

```
network.discover()      network.getOffering(id)      network.apply(offering, presentation)
network.wallet()        network.present(requirement)  network.status(request)
```

## The canonical loop (one machine, every service)

```
            ┌────────────┐     ┌────────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────────────┐
            │  DISCOVER  │ ──► │  REQUEST   │ ──► │    PROVE     │ ──► │  FULFIL   │ ──► │    RECEIVE        │ ─┐
            │  Offering  │     │  Service   │     │ Credentials  │     │Participant│     │ Outcome/Credential│  │
            └────────────┘     └────────────┘     │ + Consent    │     │  System   │     └──────────────────┘  │
                  ▲                                └──────────────┘                                            │
                  └────────────────────────────────────────── next DISCOVER ◄──────────────────────────────────┘
```

The same loop covers: eShram registration → UAN credential · training → skill credential · platform onboarding →
engagement credential · 90 days work → experience credential · insurance enrolment → coverage credential · loan
repayment → repayment credential — and almost any livelihood service.

## What exists vs. what to build (all generic)

**Already generic (ADR-0116 + prior):** network/profile/types + the provide/consume contract · membership +
eKYC auto-admit · trust handshake (plug-in source) · `network.service` with interface + endpoint · gateway +
consent (ADR-0067) · wallet + VC issue/verify/revoke (ADR-0049) · participant portal · apply → provider grant ·
embed auth basis (ADR-0112) · public front door `/t/<network>`.

**To build (generic capabilities, NOT Avsar):**
1. **Identity-assurance policy** — `identity_sources[]` + per-type `identity_assurance.{policy,accepts}` (replaces the single `verified_by`).
2. **Roles + capability grants on participants** — `roles[]` + `authorized_credentials[]`, so capability ≠ type.
3. **Offering** as a first-class governed noun + discovery/eligibility matching.
4. **Service object + the 10 network primitives** — split business service from mechanism; async-first fulfilment (ACCEPTED → status/event → COMPLETED).
5. **Requirement / Eligibility Manifest** — nestable all/any + claim predicates + issuer/freshness/assurance/jurisdiction.
6. **Credential (not certificate)** schemas + wallet **provider interface** (Avsar / DigiLocker / external).
7. **Control-plane / data-plane separation** — the admin tenant is not a transaction intermediary.
8. **Network Client SDK** — `discover / getOffering / apply / wallet / present / status`.

## Consequences

- **Avsar is config, not code.** Stand up an Avsar-class network by: creating the network tenant; declaring its
  identity sources + assurance policies; defining participant types (vocabulary) + roles/capability grants;
  registering participants (native or external, same contract); and publishing offerings whose services use the
  generic verbs + a requirement manifest. The same knobs build any other livelihood/credential network.
- **Existing systems stay where they are.** eShram/NCS/insurers plug in as external participants; the platform
  never reimplements their systems of record.
- **Evidence creates continuity.** Credentials are portable, consented evidence; successful interactions mint new
  credentials, building a worker-controlled livelihood history across networks and apps.
- **Neutral by construction.** The control/data-plane split keeps the network operator from becoming a mandatory
  middleman in every transaction.
- **Open items:** VP / selective-disclosure + holder binding; revocation propagation; consent + metering on
  issue/verify/invoke (ADR-0067 S5 / ADR-0103); offline verification (issuer-key distribution); the async
  callback/event contract; the network-admin UI to configure sources, credential schemas, offerings and the
  service primitives (several are API-settable only today — see ADR-0116 editor gaps).

## Through-line (the architecture we're actually building)

> **Identity and authoritative registries establish who the worker is. Participants join the network under a
> common trust and service contract. Providers publish discoverable offerings with machine-readable eligibility
> requirements. Workers use credentials as portable, consented evidence to access those offerings. Successful
> interactions can generate new credentials, progressively building a worker-controlled livelihood history. The
> Network Client SDK brings the same account, wallet, discovery and service experience into whichever application
> the worker already uses. Avsar is one configuration of these generic network primitives, not a special-purpose
> application.**

## Text diagram

```
 1 · IDENTITY / ASSURANCE SOURCES (plugged in — sources, not one "IdP")

   Aadhaar  ── identity proof / authentication
   eShram   ── worker registration · UAN · authoritative record · (may issue Worker Registration Credential)
   Other    ── additional identity / attribute assurance (Farmer Registry, NRLM, …)

   network type.worker.identity_assurance = { policy: worker-basic, accepts: [ aadhaar-auth, eshram-verified ] }
                                  │  trust via handshake (ADR-0084)
                                  ▼
 2 · CONTROL PLANE  (a tenant with network.admin governs this — NOT a transaction intermediary)
   ╔═══════════════════════════════════════════════════════════════════════════╗
   ║ network profile · participant registry · trust/authz policies · credential  ║
   ║ schemas · service & OFFERING definitions · identity-source config · governance║
   ╚═══════════════════════════════════════════════════════════════════════════╝
                                  │
                                  ▼
 3 · DATA PLANE  (the gateway speaks the network primitives)
   ╔═══════════════════════════════════════════════════════════════════════════╗
   ║ gateway · discover · request/invoke · present · consent/authorize · verify  ║
   ║ · issue · status · events/callbacks · audit                                 ║
   ╚═══════════════════════════════════════════════════════════════════════════╝
        ▲             ▲                  ▲                    ▲
   participant   participant         participant          participant   (native OR external — one contract)
        │             │                  │                    │
 ┌──────┴─────┐ ┌──────┴───────────┐ ┌───┴────────────┐ ┌─────┴──────────┐
 │  eShram    │ │ Platform /        │ │ Training        │ │ Insurer/Lender/ │
 │ (registry) │ │ Employer /        │ │ provider (ITI)  │ │ Benefit         │
 │ roles:[reg,│ │ Workforce interm. │ │ roles:[issuer,  │ │ roles:[provider]│
 │ cred-issuer]│ │ roles:[provider, │ │  provider]      │ │ requires certs  │
 └────────────┘ │  cred-issuer]     │ └─────────────────┘ └─────────────────┘
                │ Aggregator─┬─worker│
                │            └Fleet──worker
                └───────────────────┘

 4 · WORKER  — Livelihood Account + portable credentials (wallet is an INTERFACE)
   Wallet Provider Interface:  [ Avsar | DigiLocker | participant-hosted | external | self-custodied ]
     holds: EshramWorkerCredential · WorkExperienceCredential · TrainingCredential · InsuranceCoverageCredential …

 5 · THE CANONICAL LOOP (one machine, every service)
     DISCOVER(offering) → REQUEST(service) → PROVE(credentials+consent) → FULFIL(participant sys, async)
        → RECEIVE(outcome/credential) → next DISCOVER

 6 · ONBOARD (decoupled from any one source)
     Join Avsar → authenticate / prove identity (per assurance policy) → create Livelihood Account
       → optionally link eShram → fetch/request eShram Worker Credential → Wallet
     (Avsar Punjab: eShram · Avsar Farmers: Farmer Registry · Avsar SHG: NRLM · … — same knob)

 7 · REACH — Network Client SDK, config-driven
     Partner app  ──(SDK, auth per assurance policy)──►  network.discover() · getOffering() · apply() · wallet()
     Same SDK, any agency's app; offerings & services come from the network config.
```

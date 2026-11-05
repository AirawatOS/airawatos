# ADR-0118 — The Trusted Network Platform (generic; Avsar, TOP and similar networks)

- Status: Proposed (design)
- Date: 2026-10-31
- Supersedes-in-scope: ADR-0117 (which becomes the **Service-Exchange configuration** / credential profile of this
  platform — one of three interaction patterns defined here)
- Related: ADR-0116 (participant ≠ tenant · membership), ADR-0089 (event / message spine · emits/subscribes · CQRS),
  ADR-0067 (service directory + gateway + consent), ADR-0058 (interaction contracts / interfaces = verbs),
  ADR-0063 (interface bindings: verb → endpoint), ADR-0084 (federated trust map / register_issuer),
  ADR-0049 (verifiable credentials + wallet), ADR-0112 (embed SDK basis), ADR-0053 (space/geo data taxonomy =
  resources), ADR-0028 (civic personas / roles) + roles-as-governed-vocab, ADR-0103 (per-object sharing + consent),
  ADR-0082 (offline / edge trust), ADR-0096 (platform operator model)

## Context

Avsar (a livelihood network) and **TOP — the Traffic Observation Protocol** (a mobility network) look like different
products:

- **Avsar** connects workers, government registries (eShram), employers, platform aggregators, fleet operators,
  skilling providers, insurers, lenders and benefit providers. Workers discover opportunities, access services, and
  carry **trusted evidence** (registration, skills, work-experience credentials) across institutions.
- **TOP** connects mobility apps, observation providers, intelligence providers, road authorities, traffic police
  and signal operators. **Observations** and **traffic intelligence** move between independently operated systems so
  the right institution can discover, receive and **act** on relevant information. TOP explicitly separates
  observation, intelligence generation and institutional action.

Despite the difference, both need the **same digital infrastructure**: participants establish trusted identities;
declare what they may provide, consume or act upon; describe information with common schemas; are discoverable;
interactions are authorized; information moves between independently operated systems; requests *or events* reach the
right participant; everything is auditable; and **existing systems connect without migrating onto a common
application.**

Therefore the platform must not be an Avsar platform later generalized, nor a traffic platform that happens to
support directories. It is, from the start, a generic **Trusted Network Platform**; the platform knows nothing about
workers, jobs, roads, traffic, insurance or eShram — those are **network-specific configuration** over generic
primitives. ADR-0117 (credential-and-services) is the **Service-Exchange** pattern of this platform; this ADR adds
the **Event-Exchange** and **Transformation** patterns and the primitives (Resource, Authority/Jurisdiction,
Observation, Event, Subscription) they need.

## Decision — the generic platform

> The platform provides **trust, discovery, authorization, evidence exchange, service orchestration and event routing
> between independently operated participants.** Each network *configures* who participates, what roles they perform,
> what resources/subjects exist, what information is exchanged, what services/offerings/events are available, what
> credentials are trusted, who has authority over what, and the governing policies.

### The four questions (the whole model in one frame)

```
WHO?            Participant + Role/Capability + Authority/Jurisdiction
WHAT?           Resource + Credential + Observation + Event
WHAT CAN I DO?  Offering + Service + Subscription
HOW?            Request + Authorization + Evidence/Presentation + Routing + Fulfilment + Outcome
```

### Layered architecture

```
                         TRUSTED NETWORK PLATFORM

 ┌──────────────────────────────────────────────────────────────┐
 │ EXPERIENCE   Reference apps · Client SDK · Participant Portal   │
 │              · Admin / Developer UX                             │
 ├──────────────────────────────────────────────────────────────┤
 │ CONTROL      Network config · Participant registry · Roles &    │
 │ PLANE        capabilities · Credential/Event/Resource schemas · │
 │              Authority & jurisdiction · Offering & service defs ·│
 │              Subscription defs · Trust & authz policies ·        │
 │              Identity sources · Wallet providers · Governance    │
 ├──────────────────────────────────────────────────────────────┤
 │ EXCHANGE     discover · request · events · subscriptions ·      │
 │ RUNTIME      authorize · present · verify · policy-eval ·        │
 │              invoke · route · fulfil · outcomes · issue ·        │
 │              status/revoke · callbacks · audit                   │
 ├──────────────────────────────────────────────────────────────┤
 │ PARTICIPANT  Native components  |  External adapters / Server SDK│
 │ GATEWAY                                                          │
 └───────────────┬───────────────────────────────┬────────────────┘
                 ▼                                 ▼
          Platform services                 Existing systems
```

Native and external implementations are treated **identically** (see §"Native and external"). An existing
government, employer, traffic-control or insurer system does **not** migrate onto the platform — it joins through a
standard participant contract + adapters/SDK.

### Generic primitives

Grouped by the four questions; none is domain-specific.

- **WHO** — **Network** (a governed ecosystem config: `avsar`, `top`). **Participant** (org/system/individual).
  **Role / Capability** — what a participant is *authorized to do* (`service-provider`, `credential-issuer`,
  `credential-verifier`, `event-publisher`, `event-subscriber`, `resource-authority`, `observation-provider`,
  `intelligence-provider`, …). *Classification (“insurer”, “traffic-authority”) describes the org; roles determine
  permissions.* **Authority / Jurisdiction** — *who may do what, for which resource/subject, in which jurisdiction*
  (an authority directory: identity + geography + functional responsibilities + capabilities + endpoints).
- **WHAT** — **Resource** (an entity over which info/responsibility/authority exists: road, segment, intersection,
  signal, corridor; or property, hospital, warehouse, farm — needs common identifiers; ADR-0053). **Credential** (a
  durable signed assertion of claims; a *certificate* is one human rendering of it). **Observation** (contributed
  evidence of state at a point in time; combinable into intelligence). **Event** (a trusted assertion that something
  happened / state changed — distinct from a credential, which is durable).
- **WHAT CAN I DO** — **Offering** (the discoverable unit: job, training, registration, loan, insurance, benefit —
  `{id, provider, category, title, description, geography, eligibility, requirements, service, outputs, validity}`).
  **Service** (an executable business capability: `register-worker`, `enrol-insurance`, `change-signal-timing`,
  `dispatch-response-team`). **Subscription** (an ongoing interest in events, scoped + filtered).
- **HOW** — **Service Request** · **Authorization** (consent / delegated authority / policy basis) ·
  **Presentation** (evidence presented for a purpose) · **Fulfilment** (participant executes) · **Outcome**
  (result; may mint a credential or event) · **Wallet** (an *optional* credential-access interface for an
  individual — see privacy).

### Business services vs. network primitives

A **business service** is domain-facing (`apply-for-job`, `enrol-insurance`, `modify-signal`, `dispatch-officer`).
The **network primitives** are the governed mechanisms the runtime/gateway speaks — one set across all domains:

```
discover · request · authorize · present · verify · publish · subscribe · route · invoke · issue · status · revoke · notify · audit
```

Credential verification/signing and event routing are *primitives*, never business services. This separation lets
one runtime serve very different domains (ADR-0058 interfaces + ADR-0089 event spine supply these verbs).

### Three interaction patterns

**Pattern 1 — Service Exchange** (Avsar's dominant mode; the detail is ADR-0117):
```
DISCOVER(offering) → REQUEST(service) → REQUIREMENTS → AUTHORIZE+PRESENT → VERIFY → FULFIL → OUTCOME → CREDENTIAL/EVENT
```

**Pattern 2 — Event Exchange** (TOP's dominant mode; substrate = ADR-0089):
```
OBSERVE → PUBLISH EVENT → AUTHENTICATE SOURCE → RESOLVE RESOURCE → RESOLVE AUTHORITY
        → RESOLVE SUBSCRIPTIONS → AUTHORIZE → ROUTE → ACT → OUTCOME/AUDIT
```
e.g. an intelligence provider publishes `traffic.congestion.detected` against a road segment; the network checks the
publisher is authorized, resolves which agencies have jurisdiction, finds subscribed+authorized consumers, and routes
the event to the relevant signal operator, traffic police and planning system.

**Pattern 3 — Transformation** (either network): a participant turns one form of evidence into another, without the
platform embedding the domain algorithm:
```
INPUT event/observation → TRANSFORMATION SERVICE → DERIVED event/credential
   TOP:  location observations → intelligence provider → traffic.congestion.detected
   Avsar: credentials + work history → eligibility service → benefit.eligibility.detected
```
This is why TOP can separate observation providers from intelligence providers (phones, transit, CCTV analytics,
academia) that independently contribute observations or derived intelligence.

### Control plane vs. transaction plane (neutrality)

Governance and execution are separate planes. The entity operating the **control plane** (a tenant with
`network.admin`) defines the network but must **not** thereby become a privileged intermediary in every transaction
on the **transaction plane**. Control = config/registry/schemas/policies/authority; Transaction = discovery,
requests, event publication, subscriptions, authorization, presentation, verification, routing, invocation, status,
issuance, callbacks, audit.

### Native and external participants — one contract

```
                         NETWORK SERVICE CONTRACT
                                   │
                    ┌──────────────┴──────────────┐
                  NATIVE                        EXTERNAL
            platform component          existing system via gateway / Server SDK
```
An organisation participates **without replacing its systems**: eShram, a platform, a fleet operator, an insurer, an
ITI — or a traffic-police control room, signal-management system, intelligence provider — remain independently
operated. Agencies may receive information through their existing systems or a simple dashboard, not a common central
app.

### Two SDKs

- **Network Client SDK** — embeds network capabilities in existing user apps:
  `authenticate() · wallet.list() · discover() · getOffering() · request() · authorize() · present() ·
  getRequestStatus() · subscribe()`. Config-driven: for Avsar it surfaces wallet / register-eShram / training /
  insurance / jobs; for another network, entirely different experiences.
- **Participant Server SDK / Network Adapter** — connects existing backends:
  `registerService() · publishOffering() · publishEvent() · receiveRequest() · receiveEvent() ·
  verifyPresentation() · issueCredential() · updateStatus() · completeRequest() · subscribe() ·
  revokeCredential()`. Hides network-level complexity from participant systems.

### Network-level privacy / information minimization

The platform must **not** assume every network needs person-level identity, wallets, or persistent history.

- Avsar needs strong individual control over credentials + disclosure; wallets heavily used.
- TOP intentionally does **not** need the identities of people contributing observations — the objective is
  collective understanding, not tracking individuals/vehicles. Location data stays sensitive even without names, so
  TOP calls for minimum-necessary collection, bounded processing, aggregation, restricted retention, and controls
  against surveillance/profiling.

So wallets, identity, and retention are **per-network policy** (ADR-0103), not a universal model. `features:` on a
network profile toggles wallets / offerings / events / resources / subscriptions / jurisdictions.

## Two worked configurations (illustrative — not build targets)

**Avsar** — people + credentials + opportunities + services:
```yaml
network: { id: avsar }
participants: [ government-registry, platform, employer, fleet-operator, staffing-provider,
                training-provider, insurer, lender, benefit-provider ]
credential_types: [ worker-registration, skill, work-engagement, work-experience, insurance-coverage, repayment ]
offering_categories: [ registration, job, training, insurance, credit, benefit ]
features: { credentials: true, wallets: true, offerings: true, service_requests: true, events: true, subscriptions: optional }
# lifecycle: Discover → Request → Prove → Fulfil → Receive Credential → Discover next
```

**TOP** — resources + observations + events + authorities:
```yaml
network: { id: top }
participants: [ traffic-authority, traffic-police, municipality, road-owner, signal-operator,
                observation-provider, intelligence-provider, traffic-application ]
resources: [ road, road-segment, intersection, signal, corridor ]
event_types: [ location-observation, congestion, queue, incident, travel-time, bottleneck ]
roles: [ observe, publish, transform, subscribe, act ]
features: { wallets: false, offerings: optional, events: true, resources: true, jurisdictions: true, subscriptions: true }
# lifecycle: Observe → Infer → Publish → Resolve Authority → Route → Act → Measure Outcome
```

## What exists vs. what to build

**Already present (reusable substrate):** networks/participants/membership + roles (ADR-0116, roles-as-vocab) ·
interfaces/verbs + bindings (ADR-0058/0063) · gateway + consent (ADR-0067) · **event/message spine** (ADR-0089) ·
trust map (ADR-0084) · credentials + wallet (ADR-0049) · data/space taxonomy for resources (ADR-0053) · embed SDK
basis (ADR-0112) · per-object consent/privacy (ADR-0103) · offline/edge trust for field observations (ADR-0082).

**To build (generic, platform-level — both patterns):**
1. **Resource registry + Authority/Jurisdiction directory** — common identifiers + "who may act on what, where".
2. **Observation + Event + Subscription** as first-class governed nouns; wire the **Event-Exchange** route
   (publish → authenticate → resolve resource/authority/subscriptions → authorize → route → act → audit) on ADR-0089.
3. **Transformation** services (input event/obs → derived event/credential) as a declared service shape.
4. **Expanded network primitives** — add `publish · subscribe · route · notify` to the governed verb set.
5. **Participant Server SDK / Network Adapter** (alongside the Client SDK).
6. **Per-network feature + privacy policy** (`features{}`, retention/minimization) so wallets/identity/history are
   opt-in.
7. (From ADR-0117, still pending) identity-assurance policy · roles+capability grants · Offering noun · service
   object + requirement manifest · credential schemas · wallet provider interface · control/data-plane separation ·
   Client SDK.

## Consequences

- **One infrastructure, many networks.** The same platform supports livelihood, mobility, health, agriculture,
  education and enterprise networks without rebuilding the trust/interoperability layer. Avsar and TOP are
  configurations.
- **Events are first-class, not bolted on.** The Event-Exchange pattern (publish/route/subscribe over ADR-0089) is a
  peer of Service-Exchange; a network uses either or both.
- **Existing systems stay sovereign.** Native/external share one contract; agencies integrate via adapters, not
  migration.
- **Neutral + privacy-respecting by construction.** Control/transaction split keeps the operator out of every
  transaction; per-network privacy policy means a network can run with no person-identity and no wallet (TOP) or with
  strong individual credential control (Avsar).
- **Open items:** the event authorization + routing policy model (publisher-authz, jurisdiction resolution,
  subscriber-authz); resource identifier governance; observation→intelligence provenance + confidence; async/callback
  contract shared by both patterns; retention/minimization enforcement; the admin UX to configure resources,
  authorities, event schemas, subscriptions and privacy policy.

## Unified architecture (both pathways, shared spine)

```
                            NETWORK
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
     PARTICIPANTS           RESOURCES             SCHEMAS
     roles/capabilities     subjects/assets       credentials
     authority              jurisdictions         events / observations
          └────────────────────┼────────────────────┘
                               ▼
                           DISCOVERY
              ┌────────────────┴────────────────┐
              ▼                                  ▼
          OFFERINGS                            EVENTS
          REQUEST                            SUBSCRIBE
          REQUIREMENTS                         ROUTE
          AUTHORIZE                          AUTHORIZE
          EVIDENCE                              ACT
          FULFIL                             OUTCOME
          OUTCOME
          CREDENTIAL

  Both pathways share:  trust · identity · schemas · policies · gateway · authorization · routing · audit · SDKs · adapters
```

## Conclusion

Design from the beginning as a **Trusted Network Platform that enables independently operated participants to
discover one another, establish authority and trust, exchange evidence, offer and consume services, publish and
subscribe to events, and coordinate actions through governed interoperable protocols.** Avsar configures it around
**people + credentials + opportunities + services** (ADR-0117); TOP configures it around **resources + observations
+ events + authorities**; the platform supplies **participants + trust + authority + schemas + discovery +
authorization + exchange + routing + fulfilment + audit.**

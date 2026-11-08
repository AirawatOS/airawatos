# ADR-0130 — Trusted core, gateways and components

**Status:** Proposed · **Date:** 2026-11-08
**Grounded in:** [PROVIDER-INVENTORY](../consolidation/PROVIDER-INVENTORY.md) (every capability that reaches outside
the platform, with its owner, credentials, chooser, pre-call checks and debt — renumbered ids **DEBT-B65–B68**).
Where this ADR's brief contradicted the inventory, the inventory is followed and the difference is flagged
(§ Inventory reconciliation).
**Builds on:** ADR-0030 (no secrets in components), ADR-0050 (decision/workflow execution seam), ADR-0052
(signing), ADR-0063 (governed interfaces), ADR-0068 (pluggable IdP), ADR-0074 (operator-configurable platform
services), ADR-0089 (event/message spine), ADR-0105 (scaling tiers), ADR-0116 (participant ≠ tenant), ADR-0124
(service identities), ADR-0126 (field-level protection), ADR-0127 (one authority model), ADR-0128 (federated
Networks), ADR-0129 (no platform provider catalogue), ADR-0131 (root of trust at install).
**Affects:** PLATFORM (PLT-16–PLT-21), COMPONENT (CMP-5, CMP-6, CMP-7, CMP-11), FOUNDATIONS (FND-8, FND-10),
DECISION (DEC-1), REGISTRY (REG-8, REG-14, REG-18), ARCHITECTURE-FLOWS (door D6), new spec
[GATEWAY-v0.1](../specs/GATEWAY-v0.1.md) (GTW).

---

## Context

The platform grew by accretion: every capability landed in whichever service needed it first. Transactional
email is sent from the Network authority (`network/api.py` `_send_email`); the Telegram webhook and the SMS intake
live in the App Host; model-provider wires live in the model-gateway; the workflow engine and the document
renderer run as platform services or in-process modules; data-source drivers are components but some open their
own sockets (B65–B67); app bundles load maps straight from third-party CDNs in the viewer's browser (B68).

Two consequences follow. First, the **trusted computing base is larger than it needs to be**: code that holds no
authority (a markdown renderer, an SES client, a workflow interpreter) runs with the privileges of the service it
sits in, so every change to it is a change to the TCB. Second, **outside access has no single shape**: some
providers are reached through a gateway with a gate and metering, some through the broker's egress capability,
some directly — and none through a uniform place where grant, consent, cost and audit are enforced.

This ADR draws the line once: what belongs in the core, what is a gateway, what is a component, and what a
provider adapter is.

## Decision

### 1. The test for what belongs in the core

A part of the platform belongs in the **trusted core** if, and only if, at least one holds:

- **(a) It holds authority, facts or keys** — recorded grants and roles, the registry of record, signing and
  encryption keys, principals and credentials.
- **(b) It enforces the rules** — the decision function, the ingress gates, the broker's capability checks, the
  edge's route separation.
- **(c) It is a door to the outside world that needs one platform-wide policy** — a place where every tenant's
  traffic to or from a class of outside party must pass the same grant / consent / limit / audit checks.

**Everything else is a component**: installed, signed, confined, granted only what it declares, replaceable.

Corollaries:
- *Widely used* is not a reason to be core (a renderer every app uses is still a component).
- *Shipped by the platform* is not a reason to be core (system components are platform-shipped but installed and
  confined like any other).
- A component may be **trusted to do a job** by a grant; that does not make it part of the TCB — the core still
  checks every call it makes.
- A door (c) is core; the **provider-specific code behind it is not** (§6, §8).

### 2. Three tiers, every current service placed

| Tier | What it is | Installable? | Replaceable by a tenant? |
|---|---|---|---|
| **Core** | passes the §1 test; the TCB | no | no |
| **Gateways** | core doors (§1c) to one class of outside party, with **pluggable providers** behind a south contract (§6) | no — the gateway is core; its **provider adapters** are components (§8) | the provider: yes (tenant- or operator-chosen) |
| **System components** | platform-shipped functionality that holds no authority of its own | yes (base-OS install, like any component) | yes |

**Internal plumbing** — the scheduler, the runtime manager and the event relay (and the automation dispatcher, see
below) — is **not a gateway**: it talks to no outside party. It decides nothing and holds no authority of its own,
but it **carries other principals' credentials** (run tokens, the launcher secret, the scheduler's service token),
so it stays **inside the core and inside the TCB**. It is placed as a core sub-tier, not as a component.

**Placement of every current service** (local-dev compose services; `services/*`; in-process modules that move):

| Service / module (today) | Tier | Core-test reason / role | Notes |
|---|---|---|---|
| **kernel** (registry, broker, run tokens) | Core | (a) facts + run-token authority; (b) broker capability checks, single registry gate | the broker's `egress()` is the north enforcement point for the data-sources gateway (§6) |
| **identity** (home issuer, principals) | Core | (a) principals, signing keys; (b) the `svc:identity` door | the **home issuer is not swappable** (PLATFORM identity note); external issuers are the identity gateway's providers |
| **network** (authority, tenant records, directory, grants, certify, federation door) | Core | (a) authority + keys; (c) the federation door | its `_send_email` (SES/SMTP) **leaves** for the messaging gateway's south side |
| **app-host** (edge front door, sessions, `/bridge`) | Core | (b) session + front gates; (c) the public client door | its Telegram webhook and SMS/message intake **move** to the channels gateway; `docrender` (in-process today) **moves** out |
| **decision** (decision-record writer) | Core | (b) the one decision function's record writer | stays core even when the workflow engine is a component (§3) |
| **secrets** + **Vault** | Core | (a) keys and credentials | **not a gateway** — Vault is the platform root (ADR-0131), chosen once, never tenant-pluggable |
| **filestore** (the door) | Core | (a) facts (blobs are records, REG-18); (b) the `svc:filestore` gate | the **storage backend** behind the door is operator infrastructure (§6) |
| **nginx** (edge) | Core | (b) route separation; (c) the only host-published door | also the proxy for geo tiles/assets (§6 Geo, B68) |
| **postgres** (fact store) | Core (infrastructure) | (a) facts | operator-provisioned; per-service roles (ARC-3) |
| **service-gateway** (`services/service-gateway`) | Core (scaling tier) | a stateless **read replica tier** of the App Host / Network read paths (ADR-0105) — "a scaling boundary, not a trust boundary" | **not a GTW gateway** despite the name (flagged); forwards the caller's token unchanged |
| **scheduler** | Core — internal plumbing | carries the scheduler token; reads run tokens via the scheduler-only door | not a gateway |
| **runtime-manager** | Core — internal plumbing | places component code; holds the launcher secret | not a gateway; its confinement guarantees are the B51/B52 preconditions (§4) |
| **event-relay** | Core — internal plumbing | drains the durable `platform.event` outbox | not a gateway; **external** webhook delivery is the outbound-webhooks gateway (§6) |
| **automation** (subscription dispatcher) | Core — internal plumbing | dispatches subscription actions to governed interfaces | not in the brief; placed with the event relay. Its **raw-URL action** (shadow default, DEBT-A43) is an unmediated outbound call → must go through the outbound-webhooks gateway (flagged) |
| **model-gateway** | Gateway — **AI** | (c) | provider wires `_openai`/`_anthropic`/`_stt` become south adapters |
| **notify** | Gateway — **Messaging** (north) | (c) for messaging | its inbox delivery is the gateway's **built-in internal provider** — not an external provider (inventory §4) |
| **mospi-gateway** (`services/mospi-gateway`) | **Provider adapter** (component class, §8) — data sources | none of §1 — a single-provider protocol shim (legacy TLS renegotiation for MoSPI) | flagged: named "gateway" but it is one provider's south adapter |
| **workflow** (engine) | System component | holds no authority: it orchestrates steps under the caller's grants | decision records and order signing stay core (§3) |
| **docrender** (in-process in app-host today) | System component | renders untrusted markdown; holds nothing | the App Host still applies output sanitisation + CSP at the door (PLT-14, DEBT-B50) |
| templates, workflow definitions (`platform.workflow`), scheduled jobs (`platform.schedule`) | System components (data + packs) | governed records and packs, no authority | shipped as base-OS packs; the scheduler (plumbing) executes schedules |
| `mail-engine`, `telegram-concierge`, `git-publisher`, drivers (~48), `rtsp-ingest` | Components (already) | — | `telegram-concierge`, `git-publisher`, drivers and `rtsp-ingest` are **provider adapters** in §8's sense |

### 3. Decision records stay core, even when the workflow engine is a component

The workflow engine moves out of the core (§2); **the record of who decided what does not**. The split:

- **Core keeps:** the one decision function (FND-12), the **writer of `governance.decision`** (the decision
  service today), and **signing of `governance.order`**. Signing needs a key, which is a §1(a) reason, so the
  component cannot hold it. Decision records are written only by the core, for allow **and** deny (DEC-1, DEC-6),
  and are never edited (DEC-5).
- **The workflow component keeps:** interpreting a `platform.workflow` declaration, creating tasks, routing them
  to roles, and rolling step completion up. It runs under its own run token and the grants of the caller who
  started it.
- **The seam:** when a step needs a decision, the workflow component **asks the core decision function**, which
  checks the deciding principal's recorded authority, writes the decision record and returns its id. The
  component references that id; it never writes `governance.decision` itself. To issue an order, the component
  asks the core to sign one; the core refuses unless the order cites a decision record it holds.
- **Enforcement (to build):** the kernel refuses a `governance.decision` or `governance.order` write that arrives
  under a component run token **even if the component declared it and a tenant granted it**. Those schemas go on a
  **core-reserved list** the install grant can never cover. Today only the generic rule exists: an *undeclared*
  write is refused by the steward-grant check (proven in slice-1e Phase 15). That rule is not enough, because a
  workflow component could declare these writes. The reserved list is a precondition for moving the workflow
  engine out (§4).
- **Consequence:** replacing or upgrading the workflow engine can never change what a decision record says, who
  it names as the authority, or whether one is written. An AI or automation step can only recommend; the record
  names the human or recorded authority who decided (DEC-12).

### 4. Preconditions before anything leaves the core

Nothing listed in §2 as *moves out* (workflow engine, docrender, provider wires, the email sender, the channel
intakes) leaves the core until these are **closed** (not deferred):

| Precondition | Debt | Why it gates the move |
|---|---|---|
| **Confinement of the default runtime** | **DEBT-B51** | an in-process component inherits the host's environment; moving code out of a service into an unconfined component would *widen* its reach, not narrow it |
| **Egress policy for placed containers** | **DEBT-B52** | a component on the flat internal network can reach any service directly; the move only shrinks the TCB if the component can reach nothing but its declared doors |
| **Signing and provenance of component versions** | **DEBT-B23** (with A67, B54–B56) | code that leaves the core must still be the code that was reviewed: publisher-signed, content-pinned, digest verified at every launch |
| **Core-reserved schemas** (§3) | new, recorded with the Layer 7 moves | workflow cannot write decision records or orders even if granted |

The moves are added to **FIX-PLAN Layer 7** as one item ("ADR-0130 core → component moves") whose exit is
gated on these four. Until then the code stays where it is; this ADR changes placement, not deployment.

### 5. Effect on the trusted computing base

**What stays in the TCB:** kernel; identity; network (authority, directory, federation door); App Host (front
door, sessions, output sanitisation); the decision function and its record writer; Vault + secrets; the filestore
door; the edge; the fact store; the internal plumbing (scheduler, runtime manager, event relay, automation); the
**gateway cores** (the north/south enforcement points — §6), and the service-gateway read tier.

**What leaves, and the burden that goes with it.** Leaving the TCB does not make code unaccountable; the burden
moves from "reviewed as part of the core" to "proven as a component":

| Leaves the core | Today it runs as | After the move it needs | Review burden moves to |
|---|---|---|---|
| workflow engine | its own service with a service principal | its own **run token** (per install), declared reads/writes, a grant; **no** decision/order writes (§3) | listing conformance + the tenant's install grant; the decision function's review stays core |
| docrender | an in-process module of the App Host | a confined component with **no** network and no secrets (pure transform) | listing conformance; the App Host's sanitisation + CSP is still core-reviewed (B50) |
| templates, workflow definitions, scheduled jobs | baked into images / seeded | **signed packs** (B23) installed per tenant | the pack's publisher signature and the governed-vocabulary check |
| SES/SMTP sender (network) | inside the Network authority — with its keys in the same process | a **messaging provider adapter**: own run identity, Vault credential delivered per call, egress to named provider hosts only | south-side conformance (GTW) + the tenant's choice; the Network loses an outbound mail client from its TCB |
| `_openai` / `_anthropic` / `_stt` wires | inside the model-gateway | **AI provider adapters** | south-side conformance; the gateway core keeps consent/cost/audit |
| Telegram webhook parsing, SMS/message intake | inside the App Host | **channel provider adapters** (south receive side) | per-provider signature verification moves into the adapter; tenant binding and the rate-limited door stay core |
| `mospi-gateway` | a standalone service with a relaxed TLS option | a **data-source provider adapter** | the TLS exception becomes a declared, reviewed adapter property, not a service setting |

**What the core gains** (and must be reviewed as core): the gateway north/south contracts and their enforcement
(§6), **network-enforced declared egress** for adapters (§8), verification of adapter signatures at launch, and
the core-reserved-schema check (§3).

**Net effect.** The TCB loses every piece of provider-specific code and every authority-free interpreter. It gains
a small number of uniform enforcement points. Each departing piece pays with its own identity (a run token, not a
service principal), a signature (B23) and confinement (B51/B52). The **identity burden** is the main cost: the
platform goes from about a dozen service principals to one run identity per installed component per tenant. That
is why run-token expiry and audience (DEBT-B53) belong with the move, not after it.

### 6. Gateways: two versioned contracts, checks enforced between them

Every gateway exposes **two contracts, versioned independently**:

- **NORTH** — the provider-neutral contract callers use (components through the kernel broker, the App Host, core
  services). Callers name a **capability and an operation**, never a vendor.
- **SOUTH** — the contract a **provider adapter** implements (§8), or that a remote provider participant speaks
  over the federation door.

**Between them the gateway core enforces, on every call, in order:** caller authentication (an audience-bound token
or run token); the **grant** (recorded, FND-3); **consent or lawful basis** when personal data crosses (the
two-key rule, PLT-20); **rate and cost limits** (tenant-set ceilings, operator ceilings for shared
installations); then the adapter call; then **audit, metering with provider and version** (PLT-21) and a
**decision record** for allow and deny (DEC-1). **Data minimisation:** the south payload carries only the fields
that operation's south schema names. **Providers cannot bypass the checks:** an adapter has no route to anything
but the gateway's south endpoint and its declared provider destinations, which the network enforces (§8). It never
receives the caller's token, other tenants' data, or any Vault access beyond the provider credential the gateway
hands it for that call. The detailed rules are in [GATEWAY-v0.1](../specs/GATEWAY-v0.1.md) (GTW).

**Every inventoried capability, placed** (inventory row numbers in brackets):

| Gateway | Capabilities | Provider chosen by | Status today (inventory) |
|---|---|---|---|
| **Messaging** | email [3], inbox / notify [4], SMS/USSD outbound, federated mail [7], Telegram outbound [5] | tenant (email: per-tenant sender secret; platform mail such as join verification uses the authority tenant's sender) | email working (SES/SMTP or dev-echo) but **no rate limit, consent or audit**; notify internal only; **outbound SMS not built**; federated mail working over the federation door; Telegram reply sent by the `telegram-concierge` adapter |
| **Conversation channels (inbound)** | Telegram inbound [5], SMS/USSD/message intake [6] incl. **DEBT-B64**; future WhatsApp, IVR | tenant (Telegram); **operator** for the SMS gateway today | the south side receives provider callbacks; the north side delivers **authenticated, tenant-bound** messages. Telegram works without a rate limit on the public door (**DEBT-B46**); the SMS gateway uses one operator secret in Vault (**DEBT-B64**, target per-provider per-tenant signed webhooks) |
| **AI models** | chat / completion + embeddings [1], speech-to-text [2] | tenant (sets key) over governance-recorded `intelligence.provider` records | working; **no consent, cost cap or rate limit** (inventory C-1 → **DEBT-B71**); STT falls back to an ungoverned bootstrap env provider (inventory C-2 → **DEBT-B72**) |
| **Data sources** | drivers [8], cameras / RTSP [9], Earth observation [8] | tenant (installs the driver, sets the key) | working in the confined path; **DEBT-B65** (Earth Engine SDK opens its own sockets), **DEBT-B66** (RTSP dialled directly by ffmpeg), **DEBT-B67** (in-process runtime skips `broker.egress()`); B51/B52 |
| **Identity** | external identity providers [10], verifiable credentials [11] | **tenant** registers its own external identity provider; the **operator sets the floor** (infrastructure policy only — decided 2026-11-08, see § Resolved questions); VC issuance by the issuer tenant | working (reference IdP + Keycloak; native Ed25519 VCs). Today the operator configures issuers (inventory §10) — the tenant-registration path is to build. The **home issuer stays core** — only *external* issuers are providers |
| **Payments** | — [16] | tenant | **not built**: build to the contract (north: quote / authorise / capture / refund / status; south: provider adapter). ADR-0067 fee-quote + consent stays a declarative record |
| **Outbound webhooks** | delivery to tenant-supplied URLs [17] | tenant | **not built** (event-relay is internal only): build to the contract. The automation raw-URL action (DEBT-A43) is moved behind it |
| **Geo** | maps / basemap / 3D tiles [15], geocoding [18] | tenant | tiles and JS load **browser-direct from CDNs** (**DEBT-B68**); geocoding is local-first. Target: assets self-hosted or **proxied through the edge**, never browser-direct; a content security policy enforces it |

**Operator infrastructure — chosen once per installation, not per tenant:**

| Infrastructure | Status today (inventory) |
|---|---|
| **File storage** (behind the core filestore door) — encrypted, **tenant-scoped** blobs | local disk volume; S3 backlog (REG-18); **DEBT-B49** (no owning-tenant scope on the blob key); blob encryption is the ADR-0126 next slice |
| **Git hosting** | GitHub via the `git-publisher` engine. **Inventory: chosen per tenant/project** (ADR-0083, per-project `credential_ref`), not per installation. Flagged; kept per the inventory (open question 1) |

**Vault / secrets is core, not a gateway** (inventory row 13: hardcoded backend).

### Inventory reconciliation (where the brief and the inventory differ — the inventory is followed)

1. **Inbox / notify is not an external provider** (inventory §4: internal only). It is the messaging gateway's
   north door with a built-in internal provider.
2. **Outbound SMS is not built.** The inventory's SMS row is inbound only. The messaging gateway's SMS operation
   is build-to-contract.
3. **Federated mail is not a third-party provider.** Its peers are other AirawatOS participants over the Network's
   signed relay (inventory §7). The messaging north contract can address a federated recipient, but the south
   side is the **federation door (core)**, not an installable adapter.
4. **External identity providers are operator-configured today** (inventory §10, ADR-0068). The target is
   tenant-chosen with an operator floor. **Resolved 2026-11-08** (§ Resolved questions, 1); the inventory remains
   the record of the current state.
5. **Git hosting is chosen per tenant/project** (inventory §14), not per installation as the brief stated. Kept
   per the inventory (open question 1).
6. **Inventory summary rows 6 and 13 were stale.** Row 6 still said the SMS gateway uses an env literal (it
   moved to Vault in slice-1c-iv step 4, B64). Row 13 cited the `SECRETS_INTERNAL` literal, retired in
   slice-1c-iii. Both corrected in the inventory with this ADR.
7. **Inventory C-1 / C-2 were never in the DEBT-REGISTER,** although the inventory said they had been folded in.
   A bare `C-#` also collides with the `DEBT-C#` family (ID-SCHEME). They are registered as **DEBT-B71** (AI: no
   consent, cost or rate limit) and **DEBT-B72** (ungoverned STT bootstrap provider).
8. **The inventory omits three things the placement needs:** the automation raw-URL action (an unmediated outbound
   call, DEBT-A43), `services/service-gateway` (a read-scaling tier, core), and `services/mospi-gateway` (a
   provider adapter).

### 8. Provider adapters are a component class, installable from the marketplace

> §7 is the [GATEWAY-v0.1](../specs/GATEWAY-v0.1.md) spec (GTW) and its FIX-PLAN entries; it has no section of its
> own here.

- **An adapter is a component** of a new class, `adapter`, bound to one gateway profile and one south contract
  major. It is **signed and content-pinned** (B23), **confined** (B51/B52), and **listed in the marketplace only if
  it passes that gateway's south conformance suite** (GTW-12). Passing is the listing requirement; there is
  **no platform-approved catalogue and no platform approval or veto** (ADR-0129 Decision 6).
- **Declared outbound access only.** The adapter declares the provider destinations it may reach (named hosts and
  ports, e.g. `earthengine.googleapis.com:443`, a camera's RTSP endpoint), and nothing else. The declaration is
  **shown to the chooser at install** and **enforced by the network**: the runtime gives the adapter's container an
  egress allow-list of exactly those destinations plus the gateway's south endpoint. Code-level checks are not
  enough, because libraries and tools that open their own connections bypass them: the Earth Engine SDK
  (**DEBT-B65**), ffmpeg dialling RTSP (**DEBT-B66**), raw `urllib` on the in-process path (**DEBT-B67**).
- **Gateways are never installable.** Only the adapters behind them are.
- **Remote providers.** A provider may instead be a **remote participant** reached over the federation door,
  speaking the same south contract, its messages signed by its registered key (FED5). The gateway applies the same
  GTW-4/5/6 checks; the provider's own conformance is its provider-role conformance (PTC-11).
- **Who installs which adapters:**

  | Chosen by the **tenant** | Chosen by the **operator** (once per installation) |
  |---|---|
  | messaging, AI models, payments, identity, conversation channels, data-source drivers, geo | file storage, git hosting |

  **Identity providers** are tenant-chosen with an operator floor. Today they are operator-configured (inventory
  §10); the change is decided, not yet built (§ Resolved questions, 1).
- **Preconditions** before any adapter is installable from the marketplace: **B23** (signing/provenance), **B51 +
  B52** (confinement), **network-enforced declared egress** (GTW-11), and the **GTW conformance suite** (GTW-12).
  These go into **FIX-PLAN Layer 7**.

## Consequences

- The TCB shrinks to authority, enforcement and doors (§5). Provider-specific code is no longer reviewed as core
  but proven per listing.
- Every outside call has one shape: north → checks → south → audit/decision record. The current inconsistency
  (email unaudited, AI without consent or cost limits, SDK egress unseen) becomes a set of named gaps against one
  contract (GATEWAY-v0.1 status lines).
- New core work: versioned north/south contracts, network-enforced egress per adapter, a core-reserved schema list,
  signature verification at adapter launch, and the GTW conformance suites.
- Identity cost: one run identity per installed component and adapter per tenant, which needs short-lived,
  audience-bound run tokens (DEBT-B53).
- `services/` (service-gateway, mospi-gateway) no longer maps to a single tier. The REPO-RESTRUCTURE-PROPOSAL's
  `gateways/` tier should hold the gateway cores. service-gateway belongs with the core read tier and mospi-gateway
  with the adapters (components).

## Open questions

1. **Git hosting: operator infrastructure or tenant/project choice?** The inventory shows per-project choice
   (ADR-0083). The brief proposed operator infrastructure. Per-project credentials favour tenant choice, while a
   single audited egress point favours the operator.
3. **Federated mail placement.** Its south side is the core federation door. Should the messaging north contract
   cover federated recipients, or should federated mail stay a Network operation?
4. **SMS/USSD gateway chooser.** Operator today (one gateway per installation). Target per-tenant providers
   (DEBT-B64) — is an operator-level default kept as a convenience (allowed by ADR-0129)?
5. **Core-reserved schemas.** Which schemas are on the list beyond `governance.decision` and `governance.order`
   (e.g. `governance.role_assignment`, `governance.access_grant`)?

## Resolved questions

1. **External identity providers — tenant-chosen; the operator sets the floor** *(decided 2026-11-08)*.
   - A **tenant may register its own identity provider** (its login system, an OIDC provider, a state identity
     service). Registration is a tenant-admin act, recorded as a governed binding.
   - The provider's **issuer is pinned to that tenant only**. A token from it that names another tenant is
     rejected, and **it can never confer platform roles**: any roles it asserts are stripped. That is FND-15 as
     enforced today (`authn.register_issuer` pins the tenant; `verify` rejects a mismatch and strips roles). Authority
     still comes only from recorded grants (FND-1/FND-3).
   - The **operator sets infrastructure policy only**: for example a minimum assurance level, protocol and
     algorithm requirements (OIDC with signed ID tokens, no `alg:none`, the alg↔kty match), key-rotation and JWKS
     pinning rules, and residency. The policy is applied equally to every tenant. There is **no per-provider approval
     or veto**, consistent with ADR-0128 (each home issuer trusted only for its own participants) and ADR-0129
     Decision 6 (tenants choose; the platform sets infrastructure policy).
   - The **home issuer stays core** and is not swappable. A tenant's provider is an *external* issuer behind the
     identity gateway.
   - Today the operator configures issuers (inventory §10). Tenant self-registration under the operator floor is
     the change, tracked in FIX-PLAN Layer 6.

## Spec changes if accepted

| Spec | Change |
|---|---|
| GATEWAY (new) | GTW-1–GTW-14 + profiles (this ADR, §6–§8) |
| PLATFORM | PLT-16 points to GATEWAY-v0.1; PLT-17 as restated by ADR-0129 (infrastructure policy only); PLT-18 credentials per GTW-8; PLT-20/PLT-21 realised by GTW-4/GTW-5 |
| COMPONENT | new component class `adapter` (south contract major, declared destinations); listing requirement = GTW south conformance; CMP-11 declared egress enforced by the network |
| DECISION | DEC-1 extended to every gateway call; the core-reserved schema list (governance.decision / governance.order not writable under a component run token) |
| ARCHITECTURE-FLOWS | door D6 split: provider gateways (GTW) vs the service-gateway read tier; adapters' declared egress as flow-map edges |
| FIX-PLAN | Layer 2 (file storage, B49), Layer 5 (B68), Layer 6 (gateways), Layer 7 (moves + adapters) |

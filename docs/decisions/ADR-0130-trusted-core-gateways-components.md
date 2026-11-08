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

# PARTICIPANT-v0.1 — Participants: identity, authentication, serving, issuing, events, protocol

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**, the conformance-derived rule × environment matrix (`conformance/run.py --matrix` → `conformance/build_matrix.py`; design: [STATUS-MATRIX-DESIGN.md](STATUS-MATRIX-DESIGN.md)). The inline **Status:** lines below are kept for prose and rationale and may lag; the matrix is authoritative for covered rules (uncovered rules show **NO TEST** there, not an implied status).

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (identity vs authority, external-issuer scoping FND-15), [[NETWORK-v0.1]]
(membership, capabilities NET-9, Service publish NET-10, exchange), [[OFFERINGS-v0.1]] (offerings OFF-1–OFF-12),
[[DECISION-v0.1]] (decision records), [[ACCOUNT-v0.1]] (wallet, presentation ACC-W3), [[REGISTRY-v0.1]]
(platform-signed directory, signatures). A **participant** is a member organisation that holds identity on the
Network and may **serve** (fulfil requests), **issue** (credentials), **emit/consume events**, and **offer**
things — all through one signed, governed protocol. This spec governs how a participant proves who it is and
how it interacts; **what** it may do is the capability grants (NET-9) and offering terms (OFFERINGS).

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM. **Note:** the exchange flow (ADR-0067) and the Build SDK exist today **under legacy
authorization** (the pre-ADR-0124/0127 grant model), so several rules are "mechanism PARTIAL, authorization
migrating".

---

## Participant rules

### PTC-1 — Registration in the hosting Network's directory
A participant **registers** in the hosting Network's registry (ADR-0128, FEDERATION FED3) with a **participant
ID**, the **role(s)** sought, its **public keys** (kept in the host's platform-signed directory), and its
**conformance status**. Its **service accounts** (daemons/gateways acting for it) exist **under that
participant identity**, not as free-standing principals. Registration works for all three member modes
(same-installation tenant, other-installation tenant, own system via the Participant SDK) — the Network records
the participant; it does not create the tenant/login/node.
- **Status: PARTIAL.** The participant directory + platform-signed entries exist (ADR-0039 federated identity,
  ADR-0084 local-OS participant, ADR-0117 credential/services network); dedicated **service accounts under the
  participant** are partly modelled (ADR-0124 service principals) but not uniformly tied to a participant
  directory entry.
- **Refs:** ADR-0039, ADR-0084, ADR-0117; ADR-0124 (service principals); REGISTRY REG-8 (signatures). PTC-2.

### PTC-2 — Authentication is identity only
A participant **authenticates by identity, never by asserting authority**: either **signed requests** (its
directory key signs) or **scoped-issuer tokens** bound to it (FOUNDATIONS **FND-15**). A token that claims a
tenant/role outside the issuer's recorded binding is rejected and self-asserted roles are stripped.
- **Status: PARTIAL.** Participant message signing exists (Ed25519 + X25519, participant-message-signing);
  FND-15 issuer-scoping is held at the Network trust boundary (`authn.register_issuer`/`verify`), but the kernel
  still trusts issuer+role at some admin gates (debt DEBT-B1).
- **Refs:** FOUNDATIONS FND-1/FND-15; participant-message-signing; ADR-0117/0119; debt DEBT-B1. PTC-5.

### PTC-3 — Registering a Service
Registering a Service records its **catalog interface, endpoint, version, and data use**, and **requires the
matching `service.provide` grant** (NETWORK NET-10). A participant may register only Services it is granted to
provide.
- **Status: PARTIAL.** Service directory + publish-as-service exist (ADR-0067 S1, W5; NETWORK NET-10) with
  interface/endpoint/version; **data-use** declaration is PLANNED (ties to OFFERINGS OFF-3/OFF-11).
- **Refs:** ADR-0067 S1; NETWORK NET-10; interface-bindings-conformance (ADR-0090); OFFERINGS OFF-3. PTC-4.

### PTC-4 — Offerings per OFFERINGS
What a participant offers — Service, Benefit, Information — and its terms, eligibility, fulfilment and
settlement follow **[[OFFERINGS-v0.1]]** (OFF-1–OFF-12). This spec does not restate them.
- **Status: PARTIAL.** Services are the built kind (ADR-0067); Benefit/Information PLANNED (OFFERINGS).
- **Refs:** OFFERINGS OFF-1–OFF-12. PTC-3, PTC-10.

### PTC-5 — Inbound requests: Network-signed, decision-referenced
An inbound request is **signed by the Network** and carries a **decision reference** (and a **consent
reference** when it touches personal data). The provider **verifies** the signature and references, **may
refuse on business grounds**, and **never widens access** beyond what the decision/consent authorises.
- **Status: PARTIAL.** The governed bridge + provider-side fulfilment (ADR-0067 S4; data-exchange governed
  bridge; signed-relay endpoints) carry the request; **decision-reference** and **consent-reference** on the
  inbound request are PLANNED (DECISION records + ADR-0127 consent), and "never widen" is the F-model
  (fail-closed FND-8) rather than a verified reference today. Exchange runs under legacy authorization.
- **Refs:** ADR-0067 S4; data-exchange-network (governed bridge); DECISION DEC-1/DEC-2; ADR-0127 (consent ref);
  FOUNDATIONS FND-8. PTC-2, PTC-6.

### PTC-6 — Signed responses and fulfilment evidence
A participant returns **signed responses** and records **fulfilment evidence** (what was done, under which
decision) that the requester and the Network can verify.
- **Status: PARTIAL.** Signed relay + receipts exist (ADR-0067 S3; participant-message-signing); durable
  **fulfilment evidence** joined to the decision is partial (receipts in-memory/ring in places).
- **Refs:** ADR-0067 S3; participant-message-signing; DECISION DEC-2; OFFERINGS OFF-8. PTC-5.

### PTC-7 — Credential issuance
Issuing a credential requires an **`issue` grant for that credential type**, is **signed with the participant
key**, and its **revocation status is published** so verifiers can check it.
- **Status: PARTIAL.** VC issue/verify/revoke is live with native Ed25519 (ADR-0049; worker-career-passport
  proves a multi-issuer chain); a **per-credential-type `issue` grant** gate is PLANNED (issuance is gated to
  a member of the issuing tenant today, not a typed grant).
- **Refs:** ADR-0049 (Document Wallet & VCs), ADR-0117 (credential network); NETWORK NET-9 (`issue` grant,
  PLANNED); REGISTRY REG-8. PTC-8.

### PTC-8 — Presentation verification
Verifying a presented credential checks **holder, recipient and purpose** (ACCOUNT **ACC-W3** presentation
binding) — a presentation is bound to who presents it, to whom, and for what.
- **Status: PARTIAL.** Credential verification is live (ADR-0049; cross-state verify example); **presentation
  binding** (holder/recipient/purpose, ACC-W3) is **(to confirm)** against the live verify path.
- **Refs:** ADR-0049; ACCOUNT ACC-W3; cross-state-credential-verification. PTC-7.

### PTC-9 — Events
A participant **publishes only event types it is granted**, a **subscription is interest, not authority**
(subscribing never confers access), and events carry **idempotency keys** so a redelivery is not double-counted.
- **Status: PLANNED.** The event/message spine is Proposed (ADR-0089) and the generic event plane is a config
  umbrella (ADR-0120); granted-publish, interest-only-subscription and idempotency keys are **not built**.
- **Refs:** event-message-spine (ADR-0089, Proposed); generic-event-plane (ADR-0120); NETWORK NET-9 (event
  capability). PTC-10.

### PTC-10 — Settlement references reported
Where an interaction has a settlement, the participant **reports the settlement reference** so it can be
matched to the payment rail (OFFERINGS **OFF-8**).
- **Status: PLANNED.** No settlement model/rail integration yet (OFFERINGS OFF-8; COMPONENT CMP-18).
- **Refs:** OFFERINGS OFF-8; COMPONENT CMP-18; HRT fund-flow (precedent). PTC-4.

### PTC-11 — Per-role conformance before activation
A participant is **activated for a role only after it passes the conformance suite for that role** (provider,
issuer, funder, consumer channel — ADR-0128, FEDERATION FED4), plus a **health check** for the interfaces it
serves. Conformance status is recorded on the participant record (PTC-1) and activation gates on it.
- **Status: PARTIAL.** A black-box service test suite exists (github.com/AirawatOS/tests) and interface
  conformance (ADR-0090 R3b) can run a suite against a candidate; **conformance-gated activation** (no
  activation until green) is PLANNED.
- **Refs:** service-test-suite; interface-bindings-conformance (ADR-0090 R3b); COMPONENT CMP-15 (listing
  checks). PTC-3.

### PTC-12 — Public, versioned protocol; SDK optional; never `/bridge`
The participant protocol is **public and versioned**; the **SDK is optional** (a convenience over the wire
protocol, never required); participants **never use the host's `/bridge/*` routes** (those are the app-host's
internal surface, not the federation protocol).
- **Status: PARTIAL / VIOLATED.** The Build SDK exists (build-sdk-and-studio-redesign) and the exchange wire
  endpoints exist (ADR-0067); but there is **no single published, versioned participant protocol** distinct
  from the app-host `/bridge/*` surface — first-party apps and tools reach the platform **through `/bridge/*`
  today (VIOLATED for the "never /bridge" rule)**, and the public protocol + version negotiation are PLANNED.
- **Refs:** build-sdk-and-studio-redesign; ADR-0067 (wire exchange); data-exchange-network; app-host bridge
  surface. CLIENT C-protocol.

---

## Summary of status

| Rule | Topic | Status | Key refs / debt |
|---|---|---|---|
| PTC-1 | identity + keys in platform-signed directory | PARTIAL | ADR-0039/0084/0117; ADR-0124 |
| PTC-2 | authentication = identity only (FND-15) | PARTIAL | participant-message-signing; FND-15; DEBT-B1 |
| PTC-3 | register a Service (interface/endpoint/version/data-use; provide grant) | PARTIAL | ADR-0067; NET-10; ADR-0090 |
| PTC-4 | offerings per OFFERINGS | PARTIAL | OFFERINGS OFF-1–OFF-12 |
| PTC-5 | inbound Network-signed request + decision/consent ref; never widen | PARTIAL | ADR-0067 S4; data-exchange; ADR-0127 |
| PTC-6 | signed responses + fulfilment evidence | PARTIAL | ADR-0067 S3; DEC-2; OFF-8 |
| PTC-7 | credential issuance (issue grant/type, signed, revocation published) | PARTIAL | ADR-0049/0117; NET-9 |
| PTC-8 | presentation verification (holder/recipient/purpose ACC-W3) | PARTIAL | ADR-0049; ACC-W3 |
| PTC-9 | events (granted types; interest≠authority; idempotency) | PLANNED | ADR-0089/0120 |
| PTC-10 | settlement references reported | PLANNED | OFF-8; CMP-18 |
| PTC-11 | health + conformance before activation | PARTIAL | service-test-suite; ADR-0090 |
| PTC-12 | public versioned protocol; SDK optional; never /bridge | PARTIAL/VIOLATED | build-sdk; ADR-0067; /bridge surface |

**Tally:** 0 IN PLACE, **9 PARTIAL** (PTC-1–PTC-8, PTC-11), **2 PLANNED** (PTC-9, PTC-10), **1 PARTIAL/VIOLATED** (PTC-12 —
first-party reaches the platform via `/bridge/*`, and no public versioned participant protocol exists yet).
The exchange (ADR-0067) and credential (ADR-0049) mechanisms are live but under **legacy authorization**;
PTC-2/PTC-5 migrate to the FND-15 + ADR-0127 model as the grant/consent cutover lands.

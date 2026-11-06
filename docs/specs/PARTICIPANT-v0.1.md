# PARTICIPANT-v0.1 — Participants: identity, authentication, serving, issuing, events, protocol

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (identity vs authority, external-issuer scoping F15), [[NETWORK-v0.1]]
(membership, capabilities N9, Service publish N10, exchange), [[OFFERINGS-v0.1]] (offerings O1–O12),
[[DECISION-v0.1]] (decision records), [[ACCOUNT-v0.1]] (wallet, presentation W3), [[REGISTRY-v0.1]]
(platform-signed directory, signatures). A **participant** is a member organisation that holds identity on the
Network and may **serve** (fulfil requests), **issue** (credentials), **emit/consume events**, and **offer**
things — all through one signed, governed protocol. This spec governs how a participant proves who it is and
how it interacts; **what** it may do is the capability grants (N9) and offering terms (OFFERINGS).

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM. **Note:** the exchange flow (ADR-0067) and the Build SDK exist today **under legacy
authorization** (the pre-ADR-0124/0127 grant model), so several rules are "mechanism PARTIAL, authorization
migrating".

---

## Participant rules

### PP1 — Registration in the hosting Network's directory
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
- **Refs:** ADR-0039, ADR-0084, ADR-0117; ADR-0124 (service principals); REGISTRY R8 (signatures). PP2.

### PP2 — Authentication is identity only
A participant **authenticates by identity, never by asserting authority**: either **signed requests** (its
directory key signs) or **scoped-issuer tokens** bound to it (FOUNDATIONS **F15**). A token that claims a
tenant/role outside the issuer's recorded binding is rejected and self-asserted roles are stripped.
- **Status: PARTIAL.** Participant message signing exists (Ed25519 + X25519, participant-message-signing);
  F15 issuer-scoping is held at the Network trust boundary (`authn.register_issuer`/`verify`), but the kernel
  still trusts issuer+role at some admin gates (debt B1).
- **Refs:** FOUNDATIONS F1/F15; participant-message-signing; ADR-0117/0119; debt B1. PP5.

### PP3 — Registering a Service
Registering a Service records its **catalog interface, endpoint, version, and data use**, and **requires the
matching `service.provide` grant** (NETWORK N10). A participant may register only Services it is granted to
provide.
- **Status: PARTIAL.** Service directory + publish-as-service exist (ADR-0067 S1, W5; NETWORK N10) with
  interface/endpoint/version; **data-use** declaration is PLANNED (ties to OFFERINGS O3/O11).
- **Refs:** ADR-0067 S1; NETWORK N10; interface-bindings-conformance (ADR-0090); OFFERINGS O3. PP4.

### PP4 — Offerings per OFFERINGS
What a participant offers — Service, Benefit, Information — and its terms, eligibility, fulfilment and
settlement follow **[[OFFERINGS-v0.1]]** (O1–O12). This spec does not restate them.
- **Status: PARTIAL.** Services are the built kind (ADR-0067); Benefit/Information PLANNED (OFFERINGS).
- **Refs:** OFFERINGS O1–O12. PP3, PP10.

### PP5 — Inbound requests: Network-signed, decision-referenced
An inbound request is **signed by the Network** and carries a **decision reference** (and a **consent
reference** when it touches personal data). The provider **verifies** the signature and references, **may
refuse on business grounds**, and **never widens access** beyond what the decision/consent authorises.
- **Status: PARTIAL.** The governed bridge + provider-side fulfilment (ADR-0067 S4; data-exchange governed
  bridge; signed-relay endpoints) carry the request; **decision-reference** and **consent-reference** on the
  inbound request are PLANNED (DECISION records + ADR-0127 consent), and "never widen" is the F-model
  (fail-closed F8) rather than a verified reference today. Exchange runs under legacy authorization.
- **Refs:** ADR-0067 S4; data-exchange-network (governed bridge); DECISION D1/D2; ADR-0127 (consent ref);
  FOUNDATIONS F8. PP2, PP6.

### PP6 — Signed responses and fulfilment evidence
A participant returns **signed responses** and records **fulfilment evidence** (what was done, under which
decision) that the requester and the Network can verify.
- **Status: PARTIAL.** Signed relay + receipts exist (ADR-0067 S3; participant-message-signing); durable
  **fulfilment evidence** joined to the decision is partial (receipts in-memory/ring in places).
- **Refs:** ADR-0067 S3; participant-message-signing; DECISION D2; OFFERINGS O8. PP5.

### PP7 — Credential issuance
Issuing a credential requires an **`issue` grant for that credential type**, is **signed with the participant
key**, and its **revocation status is published** so verifiers can check it.
- **Status: PARTIAL.** VC issue/verify/revoke is live with native Ed25519 (ADR-0049; worker-career-passport
  proves a multi-issuer chain); a **per-credential-type `issue` grant** gate is PLANNED (issuance is gated to
  a member of the issuing tenant today, not a typed grant).
- **Refs:** ADR-0049 (Document Wallet & VCs), ADR-0117 (credential network); NETWORK N9 (`issue` grant,
  PLANNED); REGISTRY R8. PP8.

### PP8 — Presentation verification
Verifying a presented credential checks **holder, recipient and purpose** (ACCOUNT **W3** presentation
binding) — a presentation is bound to who presents it, to whom, and for what.
- **Status: PARTIAL.** Credential verification is live (ADR-0049; cross-state verify example); **presentation
  binding** (holder/recipient/purpose, W3) is **(to confirm)** against the live verify path.
- **Refs:** ADR-0049; ACCOUNT W3; cross-state-credential-verification. PP7.

### PP9 — Events
A participant **publishes only event types it is granted**, a **subscription is interest, not authority**
(subscribing never confers access), and events carry **idempotency keys** so a redelivery is not double-counted.
- **Status: PLANNED.** The event/message spine is Proposed (ADR-0089) and the generic event plane is a config
  umbrella (ADR-0120); granted-publish, interest-only-subscription and idempotency keys are **not built**.
- **Refs:** event-message-spine (ADR-0089, Proposed); generic-event-plane (ADR-0120); NETWORK N9 (event
  capability). PP10.

### PP10 — Settlement references reported
Where an interaction has a settlement, the participant **reports the settlement reference** so it can be
matched to the payment rail (OFFERINGS **O8**).
- **Status: PLANNED.** No settlement model/rail integration yet (OFFERINGS O8; COMPONENT CP18).
- **Refs:** OFFERINGS O8; COMPONENT CP18; HRT fund-flow (precedent). PP4.

### PP11 — Per-role conformance before activation
A participant is **activated for a role only after it passes the conformance suite for that role** (provider,
issuer, funder, consumer channel — ADR-0128, FEDERATION FED4), plus a **health check** for the interfaces it
serves. Conformance status is recorded on the participant record (PP1) and activation gates on it.
- **Status: PARTIAL.** A black-box service test suite exists (github.com/AirawatOS/tests) and interface
  conformance (ADR-0090 R3b) can run a suite against a candidate; **conformance-gated activation** (no
  activation until green) is PLANNED.
- **Refs:** service-test-suite; interface-bindings-conformance (ADR-0090 R3b); COMPONENT CP15 (listing
  checks). PP3.

### PP12 — Public, versioned protocol; SDK optional; never `/bridge`
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
| PP1 | identity + keys in platform-signed directory | PARTIAL | ADR-0039/0084/0117; ADR-0124 |
| PP2 | authentication = identity only (F15) | PARTIAL | participant-message-signing; F15; B1 |
| PP3 | register a Service (interface/endpoint/version/data-use; provide grant) | PARTIAL | ADR-0067; N10; ADR-0090 |
| PP4 | offerings per OFFERINGS | PARTIAL | OFFERINGS O1–O12 |
| PP5 | inbound Network-signed request + decision/consent ref; never widen | PARTIAL | ADR-0067 S4; data-exchange; ADR-0127 |
| PP6 | signed responses + fulfilment evidence | PARTIAL | ADR-0067 S3; D2; O8 |
| PP7 | credential issuance (issue grant/type, signed, revocation published) | PARTIAL | ADR-0049/0117; N9 |
| PP8 | presentation verification (holder/recipient/purpose W3) | PARTIAL | ADR-0049; W3 |
| PP9 | events (granted types; interest≠authority; idempotency) | PLANNED | ADR-0089/0120 |
| PP10 | settlement references reported | PLANNED | O8; CP18 |
| PP11 | health + conformance before activation | PARTIAL | service-test-suite; ADR-0090 |
| PP12 | public versioned protocol; SDK optional; never /bridge | PARTIAL/VIOLATED | build-sdk; ADR-0067; /bridge surface |

**Tally:** 0 IN PLACE, **9 PARTIAL** (PP1–PP8, PP11), **2 PLANNED** (PP9, PP10), **1 PARTIAL/VIOLATED** (PP12 —
first-party reaches the platform via `/bridge/*`, and no public versioned participant protocol exists yet).
The exchange (ADR-0067) and credential (ADR-0049) mechanisms are live but under **legacy authorization**;
PP2/PP5 migrate to the F15 + ADR-0127 model as the grant/consent cutover lands.

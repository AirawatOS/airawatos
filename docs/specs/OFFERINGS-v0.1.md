# OFFERINGS-v0.1 — Services, Benefits, Information: terms, eligibility, fulfilment, settlement

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (authority, consent F13, delegation F17), [[REGISTRY-v0.1]] (records,
provenance, erasure), [[DECISION-v0.1]] (decision records D1–D12), [[NETWORK-v0.1]] (capabilities N9, Service
publish N10, directory visibility N12), [[POLICY-v0.1]] (eligibility/automation rule language), [[COMPONENT-v0.1]]
(CP18 price/settlement). Cites a rule rather than re-deriving it.

An **offering** is a thing a participant offers to others through the Network: a **Service** (an action
performed on request), a **Benefit** (a disbursement to an eligible person, funded by someone), or
**Information** (governed data made available under terms). This spec governs how offerings are **published**,
their **terms**, who is **eligible**, how they are **fulfilled** per kind, and how **settlement** is recorded.

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM.

---

## Offering rules

### O1 — Three kinds, published under a provide grant
An offering is one of **Service**, **Benefit**, or **Information**. Publishing any offering requires a
**`*.provide` grant** for its capability (NETWORK N9/N10): a participant may offer only what the Network has
granted it to provide.
- **Status: PARTIAL.** Services publish under a `service.provide` grant and appear in the directory
  (ADR-0067 S1–S5; NETWORK N10). **Benefit** and **Information** as first-class offering kinds are PLANNED;
  today a benefit is modelled ad hoc in the welfare spine and information-sharing rides the cross-tenant
  aggregator read lane.
- **Refs:** NETWORK N9/N10, ADR-0067 (service directory), welfare-spine (ADR-0069), cross-tenant-aggregator-lane.

### O2 — Lifecycle and versioned terms
An offering moves through **draft → published → suspended → withdrawn**. **Terms are versioned**; an existing
**commitment keeps the version of the terms it was made under** — a later terms version never silently
re-prices or re-scopes a commitment already made.
- **Status: PARTIAL.** Offering/service records exist with publish; the **draft/suspended/withdrawn** lifecycle
  and **versioned terms with commitment-version-pinning** are PLANNED (listing version immutability exists for
  components, COMPONENT CP16, but offering-terms versioning is not built).
- **Refs:** ADR-0067; COMPONENT CP16 (version immutability precedent); REGISTRY R3 (versions not edits). O3.

### O3 — Terms
An offering's **terms** state: **price or free**; the **payer or funder**; **payment timing**; **refunds**;
**service levels**; **data use**; **licence**.
- **Status: PARTIAL.** `component.contract` carries price/SLA (ADR-0046..0050); **payer-vs-funder**, **payment
  timing**, **refunds**, **data-use** and **licence** terms are PLANNED. No settlement model yet (O8, CP18).
- **Refs:** component-contracts (ADR-0027/0046); COMPONENT CP18; O8. Data-use terms → O11, POLICY.

### O4 — Eligibility is a policy with a decision record
Who may receive an offering is decided by a **POLICY** ([[POLICY-v0.1]]); every eligibility determination
produces a **decision record** (DECISION D1/D2) with per-clause reasons (D8).
- **Status: PLANNED.** Offering-scope/`scope_map` exists at service apply, but eligibility as a **governed
  policy + decision record** is PLANNED (depends on POLICY-v0.1 and the rule engine, ADR-0088).
- **Refs:** POLICY PL1–PL4; DECISION D1/D2/D8; rule-engine (ADR-0088); offering scope_map. O11.

### O5 — Service fulfilment
A **Service** is fulfilled through the **call + provide grants**: the requester holds `service.call`, the
provider holds `service.provide`, and the gateway mediates the governed interaction; a receipt/decision records
the outcome.
- **Status: PARTIAL (most-built kind).** ADR-0067 S1–S5 are live: init → provider case → confirm/status +
  receipt → gateway + provider-side fulfilment → fee quote + consent. Grant-pinning + no-wildcard (N9) are
  (to confirm).
- **Refs:** ADR-0067 S1–S5; NETWORK N9/N10; DECISION D2 (receipt). N9 (to confirm) wildcard ban.

### O6 — Benefit fulfilment (funded, sanctioned, disbursed)
A **Benefit** is fulfilled: **eligibility** (O4) → **sanction** by a **named human** or an **approved
automation policy** (DECISION **D12**) → a **disbursement instruction to the payment rail** → an **optional
credential** issued to the recipient. **Publishing a Benefit requires a funding envelope**: a **funder**
holding the Network's **`fund` grant** records the envelope (**amount, scheme, rules, period**); the
**implementer publishes under its `*.provide` grant referencing the envelope**; **every sanction draws the
envelope down and cannot exceed it**.
- **Status: PLANNED.** The welfare spine (ADR-0069) models goal-anchored objectives and the
  recommendation→funded-project chain (ADR-0071/0072) models ministry/state/city funding, but the
  **funding-envelope record + draw-down-cannot-exceed enforcement**, the **sanction (D12) → rail disbursement
  instruction** path, and **benefit credentials** are not built as an offering kind.
- **Refs:** DECISION D12 (automated/sanctioned decisions re a person); welfare-spine ADR-0069;
  recommendation-to-funded-project ADR-0071; federated-program-funding ADR-0072; VC issuance (ADR-0049); O8
  (settlement), CP18. `fund` grant → NETWORK N9.

### O7 — Information fulfilment
**Information** is fulfilled as **scoped, time-limited access under consent**: the consumer gets a bounded,
expiring read of the governed data, gated by the subject's consent for personal data (O11) and by the
provider's grant otherwise.
- **Status: PLANNED/PARTIAL.** The cross-tenant aggregator READ lane (grant-gated, read-only, with
  attribution) exists; **time-limited** scoping and **consent-gated** personal-information access as an
  offering are PLANNED (per-object consent exists as a primitive, ADR-0103).
- **Refs:** cross-tenant-aggregator-lane; ADR-0103 (consent/sharing); attribution-source-disclosure; REGISTRY
  R6 (read authority), R18 (files as records). O11.

### O8 — Commitment, fulfilment evidence, settlement; matched to the rail
Each offering use records a **commitment**, **fulfilment evidence**, and a **settlement record**. Settlement is
**matched to the payment rail's reference**; a **mismatch is recorded as an exception**, never silently
reconciled. Money moves on the rail; the registry records obligations and their settlement (COMPONENT CP18).
- **Status: PLANNED.** No settlement model, rail integration, or exception records exist; metering is partial
  (ADR-0049 Part D).
- **Refs:** COMPONENT CP18; DECISION D2; metering (ADR-0049 Part D); O3. HRT fund-flow (finance.fund_flow) is a
  precedent for fund movement records.

### O9 — Visibility
An offering's **visibility follows NETWORK N12** (directory visibility): who can discover it is governed, not
ambient.
- **Status: PARTIAL.** Service directory visibility exists (N12); per-kind visibility for Benefit/Information
  PLANNED.
- **Refs:** NETWORK N12; ADR-0067 (directory). O1.

### O10 — Suspend on grant or membership lapse
An offering is **suspended automatically when the provider's `*.provide` grant or its membership lapses** — a
participant cannot keep offering on a revoked grant or after leaving.
- **Status: PLANNED.** NETWORK N9 says a grant is inactive while its holder is not an active member
  **(to confirm)**; cascading that to **auto-suspend the offering** is PLANNED.
- **Refs:** NETWORK N9 (grant-inactive-on-non-membership, to confirm); PLATFORM P13 (suspension); O2. A18.

### O11 — Personal data only under purpose-matched consent
Any offering that touches **personal data** may do so **only under a consent whose purpose matches the use**;
a purpose mismatch is a refusal. The provider is recorded as a data processor where applicable (PLATFORM P20).
- **Status: PLANNED.** Consent-granted-by-subject is decided (ADR-0125, F13) but enforcement is pending and
  embed consent is written unbound (`service:"*"`, debt B12); purpose-matching is not built.
- **Refs:** ADR-0125 (consent), F13; PLATFORM P20 (processor); DECISION D7 (personal data by reference); debt
  B12 (unbound consent). FOUNDATIONS §3 two-key rule; ADR-0127.

### O12 — Contest and refunds
A person may **contest** an offering outcome and seek **refunds** through the **DECISION D11 contest flow**: a
recorded challenge, a re-decision by an authorised decider, and a settlement adjustment where upheld.
- **Status: PLANNED.** DECISION D11 (contest flow) is itself PLANNED; refund settlement depends on O8.
- **Refs:** DECISION D11 (contest), D6 (denials recorded); O8 (settlement adjustment); O3 (refund terms).

---

## Summary of status

| Rule | Kind/topic | Status | Key refs / debt |
|---|---|---|---|
| O1 | three kinds; provide grant | PARTIAL | N9/N10; ADR-0067 |
| O2 | lifecycle + versioned terms | PARTIAL | CP16; R3 |
| O3 | terms | PARTIAL | ADR-0046; CP18 |
| O4 | eligibility = policy + decision | PLANNED | POLICY; D1/D8; ADR-0088 |
| O5 | service fulfilment | PARTIAL | ADR-0067 S1–S5 |
| O6 | benefit: envelope → sanction(D12) → rail → credential | PLANNED | ADR-0069/0071/0072; D12 |
| O7 | information: scoped, time-limited, consent | PLANNED/PARTIAL | aggregator lane; ADR-0103; R18 |
| O8 | commitment/evidence/settlement; rail match | PLANNED | CP18; ADR-0049 Part D |
| O9 | visibility per N12 | PARTIAL | N12 |
| O10 | suspend on grant/membership lapse | PLANNED | N9; P13; A18 |
| O11 | personal data = purpose-matched consent | PLANNED | ADR-0125; P20; B12; ADR-0127 |
| O12 | contest + refunds (D11) | PLANNED | D11; O8 |

**Tally:** 0 IN PLACE, **5 PARTIAL** (O1, O2, O3, O5, O9; O7 part), **7 PLANNED** (O4, O6, O7, O8, O10, O11,
O12). Services (O5) are the most-built kind (ADR-0067); Benefits and Information are specified here ahead of
the build. Settlement (O8) and the funding envelope (O6) are the load-bearing unbuilt pieces.

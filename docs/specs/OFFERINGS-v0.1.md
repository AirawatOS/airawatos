# OFFERINGS-v0.1 — Services, Benefits, Information: terms, eligibility, fulfilment, settlement

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (authority, consent FND-13, delegation FND-17), [[REGISTRY-v0.1]] (records,
provenance, erasure), [[DECISION-v0.1]] (decision records DEC-1–DEC-12), [[NETWORK-v0.1]] (capabilities NET-9, Service
publish NET-10, directory visibility NET-12), [[POLICY-v0.1]] (eligibility/automation rule language), [[COMPONENT-v0.1]]
(CMP-18 price/settlement). Cites a rule rather than re-deriving it.

An **offering** is a thing a participant offers to others through the Network: a **Service** (an action
performed on request), a **Benefit** (a disbursement to an eligible person, funded by someone), or
**Information** (governed data made available under terms). This spec governs how offerings are **published**,
their **terms**, who is **eligible**, how they are **fulfilled** per kind, and how **settlement** is recorded.

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM.

---

## Offering rules

### OFF-1 — Three kinds, published under a provide grant
An offering is one of **Service**, **Benefit**, or **Information**. Publishing any offering requires a
**`*.provide` grant** for its capability (NETWORK NET-9/NET-10): a participant may offer only what the Network has
granted it to provide.
- **Status: PARTIAL.** Services publish under a `service.provide` grant and appear in the directory
  (ADR-0067 S1–S5; NETWORK NET-10). **Benefit** and **Information** as first-class offering kinds are PLANNED;
  today a benefit is modelled ad hoc in the welfare spine and information-sharing rides the cross-tenant
  aggregator read lane.
- **Refs:** NETWORK NET-9/NET-10, ADR-0067 (service directory), welfare-spine (ADR-0069), cross-tenant-aggregator-lane.

### OFF-2 — Lifecycle and versioned terms
An offering moves through **draft → published → suspended → withdrawn**. **Terms are versioned**; an existing
**commitment keeps the version of the terms it was made under** — a later terms version never silently
re-prices or re-scopes a commitment already made.
- **Status: PARTIAL.** Offering/service records exist with publish; the **draft/suspended/withdrawn** lifecycle
  and **versioned terms with commitment-version-pinning** are PLANNED (listing version immutability exists for
  components, COMPONENT CMP-16, but offering-terms versioning is not built).
- **Refs:** ADR-0067; COMPONENT CMP-16 (version immutability precedent); REGISTRY REG-3 (versions not edits). OFF-3.

### OFF-3 — Terms
An offering's **terms** state: **price or free**; the **payer or funder**; **payment timing**; **refunds**;
**service levels**; **data use**; **licence**.
- **Status: PARTIAL.** `component.contract` carries price/SLA (ADR-0046..0050); **payer-vs-funder**, **payment
  timing**, **refunds**, **data-use** and **licence** terms are PLANNED. No settlement model yet (OFF-8, CMP-18).
- **Refs:** component-contracts (ADR-0027/0046); COMPONENT CMP-18; OFF-8. Data-use terms → OFF-11, POLICY.

### OFF-4 — Eligibility is a policy with a decision record
Who may receive an offering is decided by a **POLICY** ([[POLICY-v0.1]]); every eligibility determination
produces a **decision record** (DECISION DEC-1/DEC-2) with per-clause reasons (DEC-8).
- **Status: PLANNED.** Offering-scope/`scope_map` exists at service apply, but eligibility as a **governed
  policy + decision record** is PLANNED (depends on POLICY-v0.1 and the rule engine, ADR-0088).
- **Refs:** POLICY POL-1–POL-4; DECISION DEC-1/DEC-2/DEC-8; rule-engine (ADR-0088); offering scope_map. OFF-11.

### OFF-5 — Service fulfilment
A **Service** is fulfilled through the **call + provide grants**: the requester holds `service.call`, the
provider holds `service.provide`, and the gateway mediates the governed interaction; a receipt/decision records
the outcome.
- **Status: PARTIAL (most-built kind).** ADR-0067 S1–S5 are live: init → provider case → confirm/status +
  receipt → gateway + provider-side fulfilment → fee quote + consent. Grant-pinning + no-wildcard (NET-9) are
  (to confirm).
- **Refs:** ADR-0067 S1–S5; NETWORK NET-9/NET-10; DECISION DEC-2 (receipt). NET-9 (to confirm) wildcard ban.

### OFF-6 — Benefit fulfilment (funded, sanctioned, disbursed)
A **Benefit** is fulfilled: **eligibility** (OFF-4) → **sanction** by a **named human** or an **approved
automation policy** (DECISION **DEC-12**) → a **disbursement instruction to the payment rail** → an **optional
credential** issued to the recipient. **Publishing a Benefit requires a funding envelope**: a **funder**
holding the Network's **`fund` grant** records the envelope (**amount, scheme, rules, period**); the
**implementer publishes under its `*.provide` grant referencing the envelope**; **every sanction draws the
envelope down and cannot exceed it**.
- **Status: PLANNED.** The welfare spine (ADR-0069) models goal-anchored objectives and the
  recommendation→funded-project chain (ADR-0071/0072) models ministry/state/city funding, but the
  **funding-envelope record + draw-down-cannot-exceed enforcement**, the **sanction (DEC-12) → rail disbursement
  instruction** path, and **benefit credentials** are not built as an offering kind.
- **Refs:** DECISION DEC-12 (automated/sanctioned decisions re a person); welfare-spine ADR-0069;
  recommendation-to-funded-project ADR-0071; federated-program-funding ADR-0072; VC issuance (ADR-0049); OFF-8
  (settlement), CMP-18. `fund` grant → NETWORK NET-9.

### OFF-7 — Information fulfilment
**Information** is fulfilled as **scoped, time-limited access under consent**: the consumer gets a bounded,
expiring read of the governed data, gated by the subject's consent for personal data (OFF-11) and by the
provider's grant otherwise.
- **Status: PLANNED/PARTIAL.** The cross-tenant aggregator READ lane (grant-gated, read-only, with
  attribution) exists; **time-limited** scoping and **consent-gated** personal-information access as an
  offering are PLANNED (per-object consent exists as a primitive, ADR-0103).
- **Refs:** cross-tenant-aggregator-lane; ADR-0103 (consent/sharing); attribution-source-disclosure; REGISTRY
  REG-6 (read authority), REG-18 (files as records). OFF-11.

### OFF-8 — Commitment, fulfilment evidence, settlement; matched to the rail
Each offering use records a **commitment**, **fulfilment evidence**, and a **settlement record**. Settlement is
**matched to the payment rail's reference**; a **mismatch is recorded as an exception**, never silently
reconciled. Money moves on the rail; the registry records obligations and their settlement (COMPONENT CMP-18).
- **Status: PLANNED.** No settlement model, rail integration, or exception records exist; metering is partial
  (ADR-0049 Part D).
- **Refs:** COMPONENT CMP-18; DECISION DEC-2; metering (ADR-0049 Part D); OFF-3. HRT fund-flow (finance.fund_flow) is a
  precedent for fund movement records.

### OFF-9 — Visibility
An offering's **visibility follows NETWORK NET-12** (directory visibility): who can discover it is governed, not
ambient.
- **Status: PARTIAL.** Service directory visibility exists (NET-12); per-kind visibility for Benefit/Information
  PLANNED.
- **Refs:** NETWORK NET-12; ADR-0067 (directory). OFF-1.

### OFF-10 — Suspend on grant or membership lapse
An offering is **suspended automatically when the provider's `*.provide` grant or its membership lapses** — a
participant cannot keep offering on a revoked grant or after leaving.
- **Status: PLANNED.** NETWORK NET-9 says a grant is inactive while its holder is not an active member
  **(to confirm)**; cascading that to **auto-suspend the offering** is PLANNED.
- **Refs:** NETWORK NET-9 (grant-inactive-on-non-membership, to confirm); PLATFORM PLT-13 (suspension); OFF-2. DEBT-A18.

### OFF-11 — Personal data only under purpose-matched consent
Any offering that touches **personal data** may do so **only under a consent whose purpose matches the use**;
a purpose mismatch is a refusal. The provider is recorded as a data processor where applicable (PLATFORM PLT-20).
- **Status: PLANNED.** Consent-granted-by-subject is decided (ADR-0125, FND-13) but enforcement is pending and
  embed consent is written unbound (`service:"*"`, debt DEBT-B12); purpose-matching is not built.
- **Refs:** ADR-0125 (consent), FND-13; PLATFORM PLT-20 (processor); DECISION DEC-7 (personal data by reference); debt
  DEBT-B12 (unbound consent). FOUNDATIONS §3 two-key rule; ADR-0127.

### OFF-12 — Contest and refunds
A person may **contest** an offering outcome and seek **refunds** through the **DECISION DEC-11 contest flow**: a
recorded challenge, a re-decision by an authorised decider, and a settlement adjustment where upheld.
- **Status: PLANNED.** DECISION DEC-11 (contest flow) is itself PLANNED; refund settlement depends on OFF-8.
- **Refs:** DECISION DEC-11 (contest), DEC-6 (denials recorded); OFF-8 (settlement adjustment); OFF-3 (refund terms).

---

## Summary of status

| Rule | Kind/topic | Status | Key refs / debt |
|---|---|---|---|
| OFF-1 | three kinds; provide grant | PARTIAL | NET-9/NET-10; ADR-0067 |
| OFF-2 | lifecycle + versioned terms | PARTIAL | CMP-16; REG-3 |
| OFF-3 | terms | PARTIAL | ADR-0046; CMP-18 |
| OFF-4 | eligibility = policy + decision | PLANNED | POLICY; DEC-1/DEC-8; ADR-0088 |
| OFF-5 | service fulfilment | PARTIAL | ADR-0067 S1–S5 |
| OFF-6 | benefit: envelope → sanction(DEC-12) → rail → credential | PLANNED | ADR-0069/0071/0072; DEC-12 |
| OFF-7 | information: scoped, time-limited, consent | PLANNED/PARTIAL | aggregator lane; ADR-0103; REG-18 |
| OFF-8 | commitment/evidence/settlement; rail match | PLANNED | CMP-18; ADR-0049 Part D |
| OFF-9 | visibility per NET-12 | PARTIAL | NET-12 |
| OFF-10 | suspend on grant/membership lapse | PLANNED | NET-9; PLT-13; DEBT-A18 |
| OFF-11 | personal data = purpose-matched consent | PLANNED | ADR-0125; PLT-20; DEBT-B12; ADR-0127 |
| OFF-12 | contest + refunds (DEC-11) | PLANNED | DEC-11; OFF-8 |

**Tally:** 0 IN PLACE, **5 PARTIAL** (OFF-1, OFF-2, OFF-3, OFF-5, OFF-9; OFF-7 part), **7 PLANNED** (OFF-4, OFF-6, OFF-7, OFF-8, OFF-10, OFF-11,
OFF-12). Services (OFF-5) are the most-built kind (ADR-0067); Benefits and Information are specified here ahead of
the build. Settlement (OFF-8) and the funding envelope (OFF-6) are the load-bearing unbuilt pieces.

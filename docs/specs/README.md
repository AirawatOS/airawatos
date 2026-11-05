# AirawatOS v0.1 specs — index

The eleven **v0.1 specifications** that define AirawatOS: what the platform guarantees, stated as numbered
rules with a per-rule **status** (IN PLACE / PARTIAL / VIOLATED / PLANNED / TO CONFIRM) and debt references to
`../consolidation/DEBT-REGISTER.md`. The specs are the contract; the code is measured against them, and the
conformance plan (`../conformance/PLAN.md`) turns each rule into a black-box test (TESTABLE NOW / EXPECTED-FAIL
/ NEEDS-CREDENTIALS / NEEDS-BUILD).

**How to read a status:** these are **honest** specs — most rules are PARTIAL or PLANNED today. A rule is not a
claim that the feature is built; it is the decided target plus where the live system stands against it.

## The layering (who depends on whom)

```
FOUNDATIONS  — the authority model + principles F1–F17 (everything assumes this)
   │
   ├── REGISTRY   — records: identity, time, read/write authority, provenance, erasure, files
   ├── DECISION   — the decision record every authorization leaves behind
   ├── NETWORK    — networks, membership, capabilities (grants), exchange
   ├── ACCOUNT    — person accounts, consent, wallet
   ├── CLIENT     — client apps, tokens, the public client protocol
   └── PLATFORM   — install, platform authority, tenants, onboarding, shared services/providers
          │
          ├── COMPONENT    — build / run / share / list executable capability (uses REGISTRY, NETWORK, PLATFORM)
          ├── POLICY       — the governed rule language (eligibility, consent, automation, limits, grants)
          ├── OFFERINGS    — Service / Benefit / Information (uses NETWORK, DECISION, POLICY, PLATFORM)
          └── PARTICIPANT  — how a member proves identity and interacts (uses NETWORK, OFFERINGS, ACCOUNT, DECISION)
```

FOUNDATIONS is assumed by all. REGISTRY/DECISION/NETWORK/ACCOUNT/CLIENT/PLATFORM are the core planes.
COMPONENT, POLICY, OFFERINGS and PARTICIPANT sit on top and cite the core.

## The specs

| Spec | Rules | Purpose | Status (tally) |
|---|---|---|---|
| [[FOUNDATIONS-v0.1]] | F1–F17 | The authority model: identity carries no authority; authority only from recorded grants; fail-closed, issuer-scoped, audited. The ground every other spec assumes; now carries the **two-key rule** for personal data (§3). | mostly PARTIAL; **F4/F16 VIOLATED** (prod-pointing defaults, tenant-as-authority); the governing gap is token/tenant-name authority (B1/B2) |
| [[REGISTRY-v0.1]] | R1–R18 | The governed registry: permanent ids, versions-not-edits, bitemporal time, read/write authority (R5/R6), provenance, signatures, schemas-as-records, audit, erasure (R14), encryption (R17), **files-are-records (R18)**. | 4 IN PLACE, 6 PARTIAL, 3 VIOLATED (R6/R13/R15), 4 PLANNED (R14/R16/R17/R18), 1 TO CONFIRM |
| [[DECISION-v0.1]] | D1–D12 | What every authorization/decision must leave behind: replayable, authority-named, never-edited, denials recorded, personal-data-by-reference, reasons, contest (D11), automated decisions (D12). | 1 IN-PLACE-leaning, 4 PARTIAL, 3 VIOLATED (D1/D4/D6), rest PLANNED |
| [[NETWORK-v0.1]] | N1–N12 | Networks: identity, lifecycle, membership, **capabilities/grants (N9)** now extended to **data** per ADR-0127, Service publish (N10), directory visibility (N12), exchange. | 0 IN PLACE, 6 PARTIAL, 2 VIOLATED (N6/N7), rest PLANNED |
| [[ACCOUNT-v0.1]] | A1–A9, W1–W4 | Person accounts, identity binding/assurance, consent (holder-granted, wallet-signed), assisted access (F17), and the separate replaceable **wallet** (now also signs self-asserted claims → POLICY). | mostly PARTIAL/PLANNED (consent enforcement + wallet binding pending) |
| [[CLIENT-v0.1]] | C1–C6 | Client apps and the **public client protocol**: registered clients with recorded scopes, short-lived app-addressed tokens + consent refs, anti-enumeration, the operations grammar. | mostly PARTIAL (citizen-auth S1 live; token/consent binding to-confirm) |
| [[PLATFORM-v0.1]] | P1–P21 | Platform lifecycle: install minimum, **platform.authority** (recorded, SoD), tenants + **verification status (P9)**, onboarding, administration, public front door, and **shared services/providers (P16–P21)**. | 0 IN PLACE, 10 PARTIAL, 1 VIOLATED (**P4**), 8 PLANNED |
| [[COMPONENT-v0.1]] | CP1–CP18 | Components as code + manifest; the **private / sharing / marketplace** lanes: declaration-bounded runs, run-token = declaration ∩ authority, broker-only I/O, certified cross-tenant sharing, listing checks, versioned listings, settlement. | 0 IN PLACE, 11 PARTIAL, 6 PLANNED |
| [[OFFERINGS-v0.1]] | O1–O12 | **Service / Benefit / Information** offerings: versioned terms, eligibility-as-policy, per-kind fulfilment (service grants; benefit funding-envelope → sanction → rail; information scoped+consented), settlement matched to the rail, contest/refunds. | 0 IN PLACE, 5 PARTIAL, 7 PLANNED (Services most-built) |
| [[POLICY-v0.1]] | PL1–PL8 | One **governed rule language** for eligibility, consent conditions, automation, spending limits and grant conditions: typed trees (no code), typed facts (+ wallet-signed self-asserted), deterministic, reasons, minimum disclosure, governed function catalog, publish-time tests. | 0 IN PLACE, 4 PARTIAL (rule engine live), 4 PLANNED |
| [[PARTICIPANT-v0.1]] | PP1–PP12 | How a member proves identity (directory keys, identity-only auth F15) and **interacts**: register Services, serve Network-signed decision-referenced requests (never widening access), issue credentials, verify presentations, emit/consume events, report settlement, and speak one **public versioned protocol** (never `/bridge`). | 0 IN PLACE, 9 PARTIAL, 2 PLANNED, 1 PARTIAL/VIOLATED (PP12) |

## Cross-cutting threads

- **Authority is one model** (ADR-0127): services and data both use CapabilityGrants; **personal data needs
  grant + consent** (the two-key rule, FOUNDATIONS §3; NETWORK N9; OFFERINGS O11; POLICY PL2). `access_grant`
  becomes a Kernel-derived artefact — debt A18.
- **Everything decidable is a decision record** (DECISION) with plain-language reasons (D8) and a contest path
  (D11); automated decisions about a person are D12.
- **Nothing runs or shares without a grant** (NETWORK N9): components (COMPONENT), offerings (OFFERINGS) and
  participants (PARTICIPANT) all gate on it; the dev-tenant shortcuts are transitional (debt A28/A50, retired
  by COMPONENT CP2/CP8).
- **Files, policies and providers are governed too** — REGISTRY R18 (files-are-records), POLICY (the rule
  language), PLATFORM P16–P21 (capabilities via gateways, never vendors).

## Related

- Debt register: `../consolidation/DEBT-REGISTER.md` (A-series transitional mechanisms, B-series invariant
  violations). Conformance plan: `../conformance/PLAN.md`. Design notes:
  `../consolidation/KERNEL-MEDIATED-FILES-DESIGN.md`, `../consolidation/FILESTORE-CALLER-INVENTORY.md`,
  `../consolidation/PIPELINE-PROOF-FINDINGS.md`. ADRs: `../decisions/`.

# AirawatOS v0.1 specs — index

*New here? Start with [../PRIMER.md](../PRIMER.md); engineers continue with [../AIRAWAT-FOR-ENGINEERS.md](../AIRAWAT-FOR-ENGINEERS.md) and [GLOSSARY.md](GLOSSARY.md).*

The twelve **v0.1 specifications** that define AirawatOS: what the platform guarantees, stated as numbered
rules with a per-rule **status** (IN PLACE / PARTIAL / VIOLATED / PLANNED / TO CONFIRM) and debt references to
`../consolidation/DEBT-REGISTER.md`. The specs are the contract; the code is measured against them, and the
conformance plan (`../conformance/PLAN.md`) turns each rule into a black-box test (TESTABLE NOW / EXPECTED-FAIL
/ NEEDS-CREDENTIALS / NEEDS-BUILD).

**How to read a status:** these are **honest** specs — most rules are PARTIAL or PLANNED today. A rule is not a
claim that the feature is built; it is the decided target plus where the live system stands against it.

## The layering (who depends on whom)

```
FOUNDATIONS  — the authority model + principles FND-1–FND-17 (everything assumes this)
   │
   ├── REGISTRY   — records: identity, time, read/write authority, provenance, erasure, files
   ├── DECISION   — the decision record every authorization leaves behind
   ├── NETWORK    — networks, membership, capabilities (grants), exchange
   ├── FEDERATION — cross-installation: hosted Networks, participant registration, signed requests (ADR-0128)
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
| [[FOUNDATIONS-v0.1]] | FND-1–FND-17 | The authority model: identity carries no authority; authority only from recorded grants; fail-closed, issuer-scoped, audited. The ground every other spec assumes; now carries the **two-key rule** for personal data (§3). | 17 rules — 10 PARTIAL, 6 VIOLATED (FND-1/FND-3/FND-7/FND-8/FND-9/FND-16), 1 NOT BUILT (FND-17); the governing gaps are token/tenant-name authority (DEBT-B1/DEBT-B2) and prod-pointing/fail-open defaults (FND-16) |
| [[REGISTRY-v0.1]] | REG-1–REG-18 | The governed registry: permanent ids, versions-not-edits, bitemporal time, read/write authority (REG-5/REG-6), provenance, signatures, schemas-as-records, audit, erasure (REG-14), encryption (REG-17), **files-are-records (REG-18)**. | 4 IN PLACE, 6 PARTIAL, 3 VIOLATED (REG-6/REG-13/REG-15), 4 PLANNED (REG-14/REG-16/REG-17/REG-18), 1 TO CONFIRM |
| [[DECISION-v0.1]] | DEC-1–DEC-12 | What every authorization/decision must leave behind: replayable, authority-named, never-edited, denials recorded, personal-data-by-reference, reasons, contest (DEC-11), automated decisions (DEC-12). | 12 rules — 1 IN-PLACE-leaning, 4 PARTIAL, 4 VIOLATED (DEC-1/DEC-4/DEC-6/DEC-12), 3 PLANNED (DEC-7/DEC-10/DEC-11) |
| [[NETWORK-v0.1]] | NET-1–NET-12 | Networks: identity, lifecycle, membership, **capabilities/grants (NET-9)** now extended to **data** per ADR-0127, Service publish (NET-10), directory visibility (NET-12), exchange. | 0 IN PLACE, 6 PARTIAL, 2 VIOLATED (NET-6/NET-7), rest PLANNED |
| [[ACCOUNT-v0.1]] | ACC-1–ACC-9, ACC-W1–ACC-W4 | Person accounts, identity binding/assurance, consent (holder-granted, wallet-signed), assisted access (FND-17), and the separate replaceable **wallet** (now also signs self-asserted claims → POLICY). | mostly PARTIAL/PLANNED (consent enforcement + wallet binding pending) |
| [[CLIENT-v0.1]] | CLI-1–CLI-6 | Client apps and the **public client protocol**: registered clients with recorded scopes, short-lived app-addressed tokens + consent refs, anti-enumeration, the operations grammar. | mostly PARTIAL (citizen-auth S1 live; token/consent binding to-confirm) |
| [[PLATFORM-v0.1]] | PLT-1–PLT-21 | Platform lifecycle: install minimum, **platform.authority** (recorded, SoD), tenants + **verification status (PLT-9)**, onboarding, administration, public front door, and **shared services/providers (PLT-16–PLT-21)**. | 0 IN PLACE, 10 PARTIAL, 1 VIOLATED (**PLT-4**), 8 PLANNED |
| [[COMPONENT-v0.1]] | CMP-1–CMP-18 | Components as code + manifest; the **private / sharing / marketplace** lanes: declaration-bounded runs, run-token = declaration ∩ authority, broker-only I/O, certified cross-tenant sharing, listing checks, versioned listings, settlement. | 18 rules — 0 IN PLACE, 13 PARTIAL, 5 PLANNED |
| [[OFFERINGS-v0.1]] | OFF-1–OFF-12 | **Service / Benefit / Information** offerings: versioned terms, eligibility-as-policy, per-kind fulfilment (service grants; benefit funding-envelope → sanction → rail; information scoped+consented), settlement matched to the rail, contest/refunds. | 0 IN PLACE, 5 PARTIAL, 7 PLANNED (Services most-built) |
| [[POLICY-v0.1]] | POL-1–POL-8 | One **governed rule language** for eligibility, consent conditions, automation, spending limits and grant conditions: typed trees (no code), typed facts (+ wallet-signed self-asserted), deterministic, reasons, minimum disclosure, governed function catalog, publish-time tests. | 0 IN PLACE, 4 PARTIAL (rule engine live), 4 PLANNED |
| [[FEDERATION-v0.1]] | FED1–FED8 | **Networks are federated** (ADR-0128): a Network is hosted by a governing tenant on some installation; members are participants in one of three modes (same-install tenant, other-install tenant, own system via the Participant SDK); cross-installation requests are signed by registered keys, each home issuer trusted only for its own participants; directory-of-Networks / root-of-trust deferred (FED8). | 0 IN PLACE, 2 PARTIAL, 6 PLANNED (model decided; cross-install wiring is the backlog) |
| [[PARTICIPANT-v0.1]] | PTC-1–PTC-12 | How a member proves identity (directory keys, identity-only auth FND-15) and **interacts**: register Services, serve Network-signed decision-referenced requests (never widening access), issue credentials, verify presentations, emit/consume events, report settlement, and speak one **public versioned protocol** (never `/bridge`). | 0 IN PLACE, 9 PARTIAL, 2 PLANNED, 1 PARTIAL/VIOLATED (PTC-12) |

## Cross-cutting threads

- **Authority is one model** (ADR-0127): services and data both use CapabilityGrants; **personal data needs
  grant + consent** (the two-key rule, FOUNDATIONS §3; NETWORK NET-9; OFFERINGS OFF-11; POLICY POL-2). `access_grant`
  becomes a Kernel-derived artefact — debt DEBT-A18.
- **Everything decidable is a decision record** (DECISION) with plain-language reasons (DEC-8) and a contest path
  (DEC-11); automated decisions about a person are DEC-12.
- **Nothing runs or shares without a grant** (NETWORK NET-9): components (COMPONENT), offerings (OFFERINGS) and
  participants (PARTICIPANT) all gate on it; the dev-tenant shortcuts are transitional (debt DEBT-A28/DEBT-A50, retired
  by COMPONENT CMP-2/CMP-8).
- **Files, policies and providers are governed too** — REGISTRY REG-18 (files-are-records), POLICY (the rule
  language), PLATFORM PLT-16–PLT-21 (capabilities via gateways, never vendors).

## Status lag vs local-dev (documented status trails what local-dev now proves)

Per-rule status in these specs reflects the **overall/production** posture, which is deliberately conservative.
A few rules are **already demonstrated on the local-dev stack** (ADR-0122 cutover + the fresh-install test) but
their spec status is **left unchanged** here because production/EC2 has not cut over. Listed, not changed:

| Rule | Documented status | Proven on local-dev | Why the status is not raised yet |
|---|---|---|---|
| **FND-11** (SoD + last-holder floor) | PARTIAL ("platform.authority still tenant-based") | `platform.authority` seeded via the governance path (ADR-0122 first-holder); SoD + last-holder enforced in the Trust plane | EC2/production still runs `PLATFORM_AUTHORITY_MODE=shadow`; raise when it cuts over |
| **PLT-4** (platform tenant confers nothing) | VIOLATED (DEBT-B2) | `is_platform_authority` = recorded `platform.authority` role only, no tenant fallback (`PLATFORM_AUTHORITY_MODE=enforce`); conformance PLT-4 passes | same production cutover; DEBT-B2 open until EC2 enforces |
| **PLT-5** (platform.authority recorded, SoD, never-zero) | PARTIAL | conformance PLT-5 passes (grant-without-CR refused; last-holder revoke refused) | depends on the same cutover + break-glass (PLT-5a) still PLANNED |
| **NET-3** (network.admin is a role, not platform authority) | PARTIAL | conformance NET-3 passes (admin is a plain `network.admin`, authority is a separate recorded role) | holds on local-dev; legacy network gates (DEBT-A14) remain in the general posture |

These stay at their conservative status until the same enforcement is live in production; local-dev is the
proof that the target is reachable, not that it is universally in force. (See also the **NET-5 ↔ ADR-0116 open
decision** flagged in NETWORK-v0.1 §NET-5.)

## Related

- Debt register: `../consolidation/DEBT-REGISTER.md` (A-series transitional mechanisms, B-series invariant
  violations). Conformance plan: `../conformance/PLAN.md`. Design notes:
  `../consolidation/KERNEL-MEDIATED-FILES-DESIGN.md`, `../consolidation/FILESTORE-CALLER-INVENTORY.md`,
  `../consolidation/PIPELINE-PROOF-FINDINGS.md`. ADRs: `../decisions/`.

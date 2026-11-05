# POLICY-v0.1 — The governed policy language (eligibility, consent, automation, limits, grants)

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (authority, minimum-disclosure), [[REGISTRY-v0.1]] (schemas as records,
versioning), [[DECISION-v0.1]] (deterministic/replayable D3, reasons D8), [[ACCOUNT-v0.1]] (wallet-signed
claims W3/W4). One **policy language** underlies eligibility (OFFERINGS O4), consent conditions, automation
policies (DECISION D12), spending limits and grant conditions — so every "who may / under what conditions"
question is answered the same auditable way.

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM.

---

## Policy rules

### PL1 — Typed rule trees, not code
A policy is a **typed tree of rules** — conditions over named facts combining to a result — **never arbitrary
code**. It is data an authorised person can read, diff and govern, not a program.
- **Status: PARTIAL.** The rule engine (ADR-0088 S1) evaluates governed `governance.policy_rule` records
  (ruleset + facts → matching `then` effects + a trace) — a typed, no-code evaluator. A single **typed tree**
  schema spanning all policy uses (below) is PLANNED; today it is per-domain rule rows.
- **Refs:** rule-engine (ADR-0088 S1); REGISTRY R2 (schema-governed). PL6.

### PL2 — Facts: verified credentials, pinned records, request context (+ self-asserted where allowed)
A policy evaluates over **facts** drawn only from **verified credentials**, **pinned records** (addressed by
id+version), and the **request context**. **Self-asserted facts** are allowed **only where a policy explicitly
accepts them for named facts**: the claim is **signed by the person's wallet key** (ACCOUNT), the decision
**labels the fact self-asserted**, and the policy may attach **lower limits, later verification, sampling
audits and clawback terms**. **Verified evidence upgrades** a self-asserted fact.
- **Status: PLANNED.** The rule engine takes a facts bag today, but **fact provenance typing** (credential /
  pinned-record / context / self-asserted), wallet-signed self-assertion, and the self-asserted labelling +
  lower-limit/verify-later/clawback machinery are not built.
- **Refs:** ACCOUNT W3/W4 (wallet-signed, selective disclosure), A7; DECISION D7 (personal by reference);
  REGISTRY R1 (pinned ids). OFFERINGS O4/O11; PL4.

### PL3 — Governed, versioned, deterministic
Policies are **governed records** and **versioned**; **evaluation is deterministic and replayable** (DECISION
D3) — the same policy version over the same facts always yields the same result.
- **Status: PARTIAL.** `governance.policy_rule` is governed and versioned; deterministic evaluation holds for
  the current engine. End-to-end **replay from a decision record to the exact policy version + facts** is
  (to confirm), tied to DECISION D3.
- **Refs:** DECISION D3 (replayable); REGISTRY R3 (versions); rule-engine. PL8.

### PL4 — Per-clause results with evidence and plain-language reasons
Evaluation returns a **per-clause result** — which clauses passed/failed, the **evidence** each used, and a
**plain-language reason** (DECISION D8) the subject can read.
- **Status: PARTIAL.** The engine returns a trace of fired rules; **per-clause evidence** and **subject-facing
  plain-language reasons** (D8) are PLANNED.
- **Refs:** DECISION D8 (reason codes + subject access); rule-engine trace. OFFERINGS O4/O12.

### PL5 — Minimum disclosure
A policy requests and records **only the minimum facts** needed for the decision (ACCOUNT **W4** selective
disclosure); it never pulls more personal data than the clauses evaluated require.
- **Status: PLANNED.** Selective disclosure (W4) is specified but wallet/VC presentation is not wired into
  policy evaluation; minimum-disclosure is not enforced at evaluation.
- **Refs:** ACCOUNT W4; FOUNDATIONS (minimum disclosure); DECISION D7. PL2.

### PL6 — One language, reused everywhere
The **same policy language** expresses **eligibility** (OFFERINGS O4), **consent conditions**, **automation
policies** (DECISION D12), **spending limits**, and **grant conditions** — one grammar, many uses, so each is
governed and audited identically.
- **Status: PARTIAL.** The rule engine is already the shared evaluator for several policy kinds
  (data-visibility, access classification, thresholds — ADR-0088); extending the SAME language to consent
  conditions, D12 automation, spending limits and grant conditions is PLANNED.
- **Refs:** ADR-0088 (generic evaluator); OFFERINGS O4/O6; DECISION D12; NETWORK N9 (grant conditions). PL1.

### PL7 — Extensions via a governed function catalog
Where a clause needs a computation beyond the base grammar, it calls a **function from a governed catalog** —
extensions are **governed records**, not inline code, so the language stays typed and auditable.
- **Status: PLANNED.** No governed function catalog exists; the engine's predicate set is fixed in code today.
- **Refs:** REGISTRY R11 (schemas/catalogs as records); ADR-0088. PL1.

### PL8 — Policies ship with tests that must pass to publish
A policy is published only if it **ships with tests** (fact-sets → expected results) and they **pass** — a
policy that fails its own tests cannot be governed into force.
- **Status: PLANNED.** No policy-test gate at publish; conformance exists for components (certify) but not for
  policies.
- **Refs:** COMPONENT CP15 (listing checks precedent); DECISION D3 (determinism makes tests meaningful). PL3.

---

## Summary of status

| Rule | Topic | Status | Key refs / debt |
|---|---|---|---|
| PL1 | typed rule trees, no code | PARTIAL | ADR-0088 S1; R2 |
| PL2 | facts (credential/pinned/context) + self-asserted | PLANNED | W3/W4; D7; R1 |
| PL3 | governed, versioned, deterministic (D3) | PARTIAL | D3; R3; ADR-0088 |
| PL4 | per-clause results, evidence, reasons (D8) | PARTIAL | D8; engine trace |
| PL5 | minimum disclosure (W4) | PLANNED | W4; D7 |
| PL6 | one language, many uses | PARTIAL | ADR-0088; O4/O6; D12; N9 |
| PL7 | governed function catalog | PLANNED | R11; ADR-0088 |
| PL8 | tests must pass to publish | PLANNED | CP15; D3 |

**Tally:** 0 IN PLACE, **4 PARTIAL** (PL1, PL3, PL4, PL6), **4 PLANNED** (PL2, PL5, PL7, PL8). The rule engine
(ADR-0088) is the live nucleus; the gaps are fact-provenance + self-assertion (PL2), minimum disclosure (PL5),
the function catalog (PL7), and the publish-time test gate (PL8).

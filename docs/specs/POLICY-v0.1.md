# POLICY-v0.1 — The governed policy language (eligibility, consent, automation, limits, grants)

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (authority, minimum-disclosure), [[REGISTRY-v0.1]] (schemas as records,
versioning), [[DECISION-v0.1]] (deterministic/replayable DEC-3, reasons DEC-8), [[ACCOUNT-v0.1]] (wallet-signed
claims ACC-W3/ACC-W4). One **policy language** underlies eligibility (OFFERINGS OFF-4), consent conditions, automation
policies (DECISION DEC-12), spending limits and grant conditions — so every "who may / under what conditions"
question is answered the same auditable way.

**Debt references** → `../consolidation/DEBT-REGISTER.md`. **Status legend:** IN PLACE · PARTIAL · VIOLATED ·
PLANNED · TO CONFIRM.

---

## Policy rules

### POL-1 — Typed rule trees, not code
A policy is a **typed tree of rules** — conditions over named facts combining to a result — **never arbitrary
code**. It is data an authorised person can read, diff and govern, not a program.
- **Status: PARTIAL.** The rule engine (ADR-0088 S1) evaluates governed `governance.policy_rule` records
  (ruleset + facts → matching `then` effects + a trace) — a typed, no-code evaluator. A single **typed tree**
  schema spanning all policy uses (below) is PLANNED; today it is per-domain rule rows.
- **Refs:** rule-engine (ADR-0088 S1); REGISTRY REG-2 (schema-governed). POL-6.

### POL-2 — Facts: verified credentials, pinned records, request context (+ self-asserted where allowed)
A policy evaluates over **facts** drawn only from **verified credentials**, **pinned records** (addressed by
id+version), and the **request context**. **Self-asserted facts** are allowed **only where a policy explicitly
accepts them for named facts**: the claim is **signed by the person's wallet key** (ACCOUNT), the decision
**labels the fact self-asserted**, and the policy may attach **lower limits, later verification, sampling
audits and clawback terms**. **Verified evidence upgrades** a self-asserted fact.
- **Status: PLANNED.** The rule engine takes a facts bag today, but **fact provenance typing** (credential /
  pinned-record / context / self-asserted), wallet-signed self-assertion, and the self-asserted labelling +
  lower-limit/verify-later/clawback machinery are not built.
- **Refs:** ACCOUNT ACC-W3/ACC-W4 (wallet-signed, selective disclosure), ACC-7; DECISION DEC-7 (personal by reference);
  REGISTRY REG-1 (pinned ids). OFFERINGS OFF-4/OFF-11; POL-4.

### POL-3 — Governed, versioned, deterministic
Policies are **governed records** and **versioned**; **evaluation is deterministic and replayable** (DECISION
DEC-3) — the same policy version over the same facts always yields the same result.
- **Status: PARTIAL.** `governance.policy_rule` is governed and versioned; deterministic evaluation holds for
  the current engine. End-to-end **replay from a decision record to the exact policy version + facts** is
  (to confirm), tied to DECISION DEC-3.
- **Refs:** DECISION DEC-3 (replayable); REGISTRY REG-3 (versions); rule-engine. POL-8.

### POL-4 — Per-clause results with evidence and plain-language reasons
Evaluation returns a **per-clause result** — which clauses passed/failed, the **evidence** each used, and a
**plain-language reason** (DECISION DEC-8) the subject can read.
- **Status: PARTIAL.** The engine returns a trace of fired rules; **per-clause evidence** and **subject-facing
  plain-language reasons** (DEC-8) are PLANNED.
- **Refs:** DECISION DEC-8 (reason codes + subject access); rule-engine trace. OFFERINGS OFF-4/OFF-12.

### POL-5 — Minimum disclosure
A policy requests and records **only the minimum facts** needed for the decision (ACCOUNT **ACC-W4** selective
disclosure); it never pulls more personal data than the clauses evaluated require.
- **Status: PLANNED.** Selective disclosure (ACC-W4) is specified but wallet/VC presentation is not wired into
  policy evaluation; minimum-disclosure is not enforced at evaluation.
- **Refs:** ACCOUNT ACC-W4; FOUNDATIONS (minimum disclosure); DECISION DEC-7. POL-2.

### POL-6 — One language, reused everywhere
The **same policy language** expresses **eligibility** (OFFERINGS OFF-4), **consent conditions**, **automation
policies** (DECISION DEC-12), **spending limits**, and **grant conditions** — one grammar, many uses, so each is
governed and audited identically.
- **Status: PARTIAL.** The rule engine is already the shared evaluator for several policy kinds
  (data-visibility, access classification, thresholds — ADR-0088); extending the SAME language to consent
  conditions, DEC-12 automation, spending limits and grant conditions is PLANNED.
- **Refs:** ADR-0088 (generic evaluator); OFFERINGS OFF-4/OFF-6; DECISION DEC-12; NETWORK NET-9 (grant conditions). POL-1.

### POL-7 — Extensions via a governed function catalog
Where a clause needs a computation beyond the base grammar, it calls a **function from a governed catalog** —
extensions are **governed records**, not inline code, so the language stays typed and auditable.
- **Status: PLANNED.** No governed function catalog exists; the engine's predicate set is fixed in code today.
- **Refs:** REGISTRY REG-11 (schemas/catalogs as records); ADR-0088. POL-1.

### POL-8 — Policies ship with tests that must pass to publish
A policy is published only if it **ships with tests** (fact-sets → expected results) and they **pass** — a
policy that fails its own tests cannot be governed into force.
- **Status: PLANNED.** No policy-test gate at publish; conformance exists for components (certify) but not for
  policies.
- **Refs:** COMPONENT CMP-15 (listing checks precedent); DECISION DEC-3 (determinism makes tests meaningful). POL-3.

---

## Summary of status

| Rule | Topic | Status | Key refs / debt |
|---|---|---|---|
| POL-1 | typed rule trees, no code | PARTIAL | ADR-0088 S1; REG-2 |
| POL-2 | facts (credential/pinned/context) + self-asserted | PLANNED | ACC-W3/ACC-W4; DEC-7; REG-1 |
| POL-3 | governed, versioned, deterministic (DEC-3) | PARTIAL | DEC-3; REG-3; ADR-0088 |
| POL-4 | per-clause results, evidence, reasons (DEC-8) | PARTIAL | DEC-8; engine trace |
| POL-5 | minimum disclosure (ACC-W4) | PLANNED | ACC-W4; DEC-7 |
| POL-6 | one language, many uses | PARTIAL | ADR-0088; OFF-4/OFF-6; DEC-12; NET-9 |
| POL-7 | governed function catalog | PLANNED | REG-11; ADR-0088 |
| POL-8 | tests must pass to publish | PLANNED | CMP-15; DEC-3 |

**Tally:** 0 IN PLACE, **4 PARTIAL** (POL-1, POL-3, POL-4, POL-6), **4 PLANNED** (POL-2, POL-5, POL-7, POL-8). The rule engine
(ADR-0088) is the live nucleus; the gaps are fact-provenance + self-assertion (POL-2), minimum disclosure (POL-5),
the function catalog (POL-7), and the publish-time test gate (POL-8).

# DECISION-v0.1 — The decision record: what every authorization and decision must leave behind

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**, the conformance-derived rule × environment matrix (`conformance/run.py --matrix` → `conformance/build_matrix.py`; design: [STATUS-MATRIX-DESIGN.md](STATUS-MATRIX-DESIGN.md)). The inline **Status:** lines below are kept for prose and rationale and may lag; the matrix is authoritative for covered rules (uncovered rules show **NO TEST** there, not an implied status).

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (authority model §3; principles FND-1–FND-17) and [[REGISTRY-v0.1]] (record rules
REG-1–REG-18) — both are assumed, not restated. A **decision record** is a governed registry record (so REG-1–REG-18
apply: permanent id, versions-not-edits, bitemporal, provenance, signature, audit, personal-data-by-
reference, etc.); this spec adds what a decision record must **contain and guarantee** on top of that.
**Debt references** are to `../consolidation/DEBT-REGISTER.md` (DEBT-A1–DEBT-A61, DEBT-B1–DEBT-B18). *(to confirm)* = not traced
this pass; flagged, not asserted.

**Status legend:** **IN PLACE** · **PARTIAL** (exists but gated off/shadow or partial-path) · **VIOLATED**
(contradicted in live code) · **PLANNED** (decided/needed, not built) · **TO CONFIRM** (not verified).

A **decision** here means any adjudication that the platform must be able to explain and defend: an
authorization, an eligibility/approval outcome, a consent use, an automated decision affecting a person, or
a governance change. It is distinct from the **recommendation** that may precede it (ADR-0029 decision
spine) and from the **ChangeRequest** that carries a governance mutation (ADR-0056) — a decision record
*references* those, it does not replace them.

---

## Decision rules

### DEC-1 — Scope: what must produce a decision record
A decision record is required for every: **protected-action authorization** (both **allow and deny**);
**eligibility check**; **approval** (membership, grant, role, consent use); **automated decision affecting a
person**; and **governance change**. **Public reads (REGISTRY REG-6/REG-15) are excluded.**
- **Status: PARTIAL / VIOLATED.** The explicit "decide" spine produces decision records
  (recommendation→`governance.decision`, ADR-0029; facts+rules→decision, ADR-0046), and governance changes
  flow as ChangeRequests (ADR-0056). But the **high-volume** cases are not recorded: routine kernel authz
  allow/deny, eligibility, and most approvals leave **no** decision record, and **denials/failed auth are
  not logged at all** (DEBT-A9). So DEC-1 holds for deliberate decisions, not for the authorization plane.
- **Refs:** ADR-0029, ADR-0046, ADR-0056; DEBT-A9 (failed-auth not logged → denies unrecorded); DEBT-B1/DEBT-B3 (authz
  decided off token claims / authentication, not recorded). Tiered coverage is DEC-10.

### DEC-2 — Contents
A decision record carries: the **request** (who, what action, which target, when, correlation id); the
**exact policy version** applied; **inputs pinned to record versions** (REGISTRY REG-1/REG-4); **evidence by
reference** (not inline copies); **each rule's result**; the **outcome** with **reason codes**; and the
**decider**.
- **Status: PARTIAL / TO CONFIRM.** The `governance.decision` object captures request, inputs, outcome, and
  decider for the decision spine (ADR-0046 hourglass). **Exact policy-version pinning, per-rule results, and
  evidence-by-reference** completeness are **(to confirm)** — verify the object carries a resolvable policy
  version and a per-rule result array rather than a single outcome.
- **Refs:** ADR-0046, ADR-0029; REGISTRY REG-4/REG-7 (pinned versions, provenance). Per-rule-result + policy-
  version fields **(to confirm)**.

### DEC-3 — Replayable
Re-evaluating with the **same policy version and the same pinned inputs** yields the **same outcome**. Any
**model output is recorded as an input** — with the **model identity and version** — and never as the
decider; the **final decider is named** separately.
- **Status: PARTIAL / TO CONFIRM.** The hourglass (facts+rules→decision, ADR-0046) is deterministic by
  design given pinned facts+rules. Whether **model output is captured as a pinned input with model id+version**
  (vs. consumed and discarded) is **(to confirm)** against the model-gateway call path; the model-gateway
  reasoning split (kimi-k3) records model identity at the gateway, but its linkage into the decision record
  as a pinned input is unverified.
- **Refs:** ADR-0046; model-gateway reasoning split; REGISTRY REG-4/REG-7. Model-output-as-input **(to confirm)**.

### DEC-4 — Deciding requires recorded authority, named in the record
The decider must hold a **live recorded authority** to make this decision (FOUNDATIONS FND-2; §3 decision
function), and that authority is **named in the decision record**. Authentication alone never suffices.
**This is the fix for DEBT-B3.**
- **Status: VIOLATED (fix target).** `decision.py /decide` records **any valid token's `sub`** as the
  deciding authority **with no check** that the principal may decide that task (DEBT-B3); the effective gate is
  only whatever the kernel applies on the under-token read/write. Deciding authority is therefore asserted,
  not recorded-and-checked.
- **Refs:** **DEBT-B3** (authority from authentication alone — the rule this fixes), DEBT-B1; FND-2, FND-14 (traceable
  authority names its grantor). **PLANNED:** check a recorded grant before recording a decision, and name
  that grant in the record.

### DEC-5 — Never edited
A decision record is **never edited** (REGISTRY REG-3). A **correction, appeal, or override** is a **new
decision** that **references the original**; the original stays intact and addressable.
- **Status: IN PLACE for immutability; PARTIAL for the supersede-by-reference flow.** Decision records are
  governed registry records, so append-only/versions-not-edits (REGISTRY REG-3) holds. The
  correction/appeal/override-as-new-decision-referencing-original flow is the contest machinery (DEC-11) and is
  only partially built.
- **Refs:** REGISTRY REG-3/REG-5; ADR-0056. Override-references-original linkage **(to confirm)** — see DEC-11.

### DEC-6 — Denials recorded
A **denial is recorded**, including a **fail-closed** denial (FOUNDATIONS FND-8), **with its reason**. A silent
deny is not permitted — "no record" must never be the trace of a refusal.
- **Status: VIOLATED.** Failed authentication and most authorization denials are **not logged** (DEBT-A9); fail-
  closed denials leave no decision record. This is the inverse of DEC-1's allow-side gap and is the more
  security-relevant half.
- **Refs:** **DEBT-A9** (failed-auth not logged); FND-8 (fail-closed). **PLANNED:** emit a decision record on every
  deny, including the fail-closed branch, with a reason code (DEC-8).

### DEC-7 — Personal data by reference only
A decision record holds personal data **by reference only** (REGISTRY REG-14) — a reference + hash, never
inline personal data — so a decision record is itself erasable-compatible.
- **Status: PLANNED (inherits REGISTRY REG-14).** The erasable personal-data store and reference+hash split are
  not yet built (REG-14 PLANNED), so decision records cannot yet guarantee personal data is held by reference.
- **Refs:** REGISTRY REG-14; ADR-0125 (consent); DPDP open item (REGISTRY-v0.1 §Open item, erasure in force
  2027-05-13). Inline-personal-data audit of current `governance.decision` payloads **(to confirm)**.

### DEC-8 — Plain-language reason codes; subject access
Outcomes carry **plain-language reason codes** (not opaque internal errors), and **a person can obtain the
decision records about themselves**.
- **Status: PARTIAL / PLANNED.** Reason-code vocabulary for decision outcomes is **(to confirm)** — verify a
  governed reason-code set vs. free-text. **Subject access** to one's own decision records is **not built**;
  the per-object read-authority/sharing primitive exists but is adopted by 0 prod schemas (REGISTRY REG-6/REG-11;
  ADR-0103), and `governance.decision` is not subject-readable today.
- **Refs:** ADR-0103 (per-object access/consent); REGISTRY REG-6; FND-13. Reason-code governance **(to confirm)**;
  subject-access **PLANNED**.

### DEC-9 — Linked across decisions, ChangeRequests, and audit
Decision records are **linked via correlation / op ids** to the other decisions, **ChangeRequests**
(ADR-0056), and **audit events** (REGISTRY REG-12) they relate to — one adjudication is traceable end to end.
- **Status: PARTIAL.** An `op_id` exists and the Trust-plane role_assignment carries `granted_by`/op_id + an
  audit chain (per FND-14); ChangeRequests are first-class (ADR-0056). A **uniform correlation id threaded
  across decision ↔ CR ↔ audit** is **(to confirm)** — verify a single correlation id is propagated, not
  per-surface ids that must be joined by hand.
- **Refs:** FND-14 (grantor/op_id chain); ADR-0056 (CR); REGISTRY REG-12 (audit). Cross-surface correlation id
  **(to confirm)**.

### DEC-10 — Recording depth: full vs. aggregated
**Full records** for **consequential decisions** and **all denials** (DEC-6). **Aggregated records** (principal,
scope, period, count, and the authority records relied on) for **routine allowed reads**. **Any read of
personal data always gets a full record**, regardless of routineness.
- **Status: PLANNED.** There is no tiered decision-logging today — routine reads produce **no** decision
  record (not even aggregated), and personal-data reads are not specially recorded. The tiering (full /
  aggregated / always-full-for-personal-data) is unbuilt.
- **Refs:** DEC-1, DEC-6; REGISTRY REG-6 (reads), REG-14 (personal data). Depends on DEC-1 coverage landing first.

### DEC-11 — Contest flow
A **contest is a recorded request**. The **reviewer holds recorded authority** and **is not the original
decider** (separation of duties). The **outcome is a new decision** (DEC-5), and the **original is marked
contested / overridden**.
- **Status: PARTIAL / PLANNED.** The case/review spine exists — Inbox & Case (ADR-0048) and the
  Review/Remedy object (Slice-1, task #62) — and SoD + last-holder floors are defined for platform/tenant
  authority (ADR-0122). But the specific contest→new-decision→mark-original-contested chain, with a
  reviewer-≠-decider check enforced from recorded authority, is **(to confirm)** / not proven end to end.
- **Refs:** ADR-0048 (Inbox & Case), Review/Remedy (#62), ADR-0122 (SoD); DEC-4, DEC-5. Reviewer-≠-decider
  enforcement **(to confirm)**.

### DEC-12 — Automated decisions affecting a person
An automated decision affecting a person requires **either** a **named human approver with recorded
authority**, **or** an **explicit automation policy approved via ChangeRequest** that **names an accountable
owner**. The record **states which**. The person is **told it was automated** and **can contest** (DEC-11).
- **Status: VIOLATED / PLANNED.** Today engines hold a direct write-grant to `governance.decision`
  (campaign-engine, project-engine — **DEBT-B18**) and the guarantee that a **human authority precedes** such a
  run is **(to confirm)** / not enforced; automated outcomes are **not labelled** as automated to the
  subject, and no automation-policy-via-CR-with-accountable-owner construct is wired. Combined with DEBT-B3 (DEC-4),
  an automated decider is currently accepted on authentication alone.
- **Refs:** **DEBT-B18** (engines write `governance.decision` — "engine never decides" at risk), DEBT-B3; ADR-0056
  (automation policy via CR), ADR-0100 (generic Campaign — outbound population sweep), ADR-0029. Human-
  approver-or-named-owner gate **PLANNED**; subject notification + contest **PLANNED** (DEC-11).

---

## Summary of status

| Rule | Topic | Status | Key debt |
|------|-------|--------|----------|
| DEC-1 | Scope of decision records | PARTIAL/VIOLATED | DEBT-A9; DEBT-B1, DEBT-B3; ADR-0029/0046/0056 |
| DEC-2 | Contents | PARTIAL / *to confirm* | ADR-0046; REG-4/REG-7 |
| DEC-3 | Replayable (+model as input) | PARTIAL / *to confirm* | ADR-0046; model-gateway |
| DEC-4 | Deciding needs recorded authority | VIOLATED (fixes DEBT-B3) | **DEBT-B3**, DEBT-B1; FND-2/FND-14 |
| DEC-5 | Never edited | IN PLACE (immut.) / PARTIAL (override link) | REG-3/REG-5; ADR-0056 |
| DEC-6 | Denials recorded (incl. fail-closed) | VIOLATED | **DEBT-A9**; FND-8 |
| DEC-7 | Personal data by reference | PLANNED (inherits REG-14) | REG-14; ADR-0125; DPDP |
| DEC-8 | Reason codes; subject access | PARTIAL/PLANNED | ADR-0103; REG-6/REG-11; FND-13 |
| DEC-9 | Linked via correlation/op ids | PARTIAL | FND-14; ADR-0056; REG-12 |
| DEC-10 | Full vs aggregated depth | PLANNED | DEC-1, DEC-6; REG-6, REG-14 |
| DEC-11 | Contest flow | PARTIAL/PLANNED | ADR-0048; #62; ADR-0122 |
| DEC-12 | Automated decisions re a person | VIOLATED/PLANNED | **DEBT-B18**, DEBT-B3; ADR-0056/0100 |

**Tally:** 12 rules — 1 IN PLACE-leaning (DEC-5, immutability), 4 PARTIAL (DEC-2, DEC-3, DEC-8, DEC-9), 4 VIOLATED (DEC-1, DEC-4,
DEC-6, DEC-12), 3 PLANNED (DEC-7, DEC-10, DEC-11). DEC-1 and DEC-12 carry a mixed status; the governing gaps are **DEBT-B3**
(deciding authority not recorded — DEC-4), **DEBT-A9** (denials not recorded — DEC-6), and **DEBT-B18** (engines decide —
DEC-12).

---

## Cross-references
- **FOUNDATIONS:** FND-2 (authority from recorded state), FND-8 (fail-closed), FND-12 (auditable), FND-13 (consent), FND-14
  (traceable authority).
- **REGISTRY:** REG-3 (versions not edits), REG-4 (pinned/bitemporal inputs), REG-6 (reads excluded from DEC-1), REG-7
  (provenance), REG-12 (audit), REG-14 (personal data by reference), REG-15 (public designation).
- **ADRs:** 0029 (decision spine), 0046 (decision hourglass), 0048 (Inbox & Case), 0056 (decided
  ChangeRequest), 0100 (generic Campaign), 0122 (SoD / platform authority), 0125 (consent).

# DECISION-v0.1 — The decision record: what every authorization and decision must leave behind

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (authority model §3; principles F1–F17) and [[REGISTRY-v0.1]] (record rules
R1–R18) — both are assumed, not restated. A **decision record** is a governed registry record (so R1–R18
apply: permanent id, versions-not-edits, bitemporal, provenance, signature, audit, personal-data-by-
reference, etc.); this spec adds what a decision record must **contain and guarantee** on top of that.
**Debt references** are to `../consolidation/DEBT-REGISTER.md` (A1–A61, B1–B18). *(to confirm)* = not traced
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

### D1 — Scope: what must produce a decision record
A decision record is required for every: **protected-action authorization** (both **allow and deny**);
**eligibility check**; **approval** (membership, grant, role, consent use); **automated decision affecting a
person**; and **governance change**. **Public reads (REGISTRY R6/R15) are excluded.**
- **Status: PARTIAL / VIOLATED.** The explicit "decide" spine produces decision records
  (recommendation→`governance.decision`, ADR-0029; facts+rules→decision, ADR-0046), and governance changes
  flow as ChangeRequests (ADR-0056). But the **high-volume** cases are not recorded: routine kernel authz
  allow/deny, eligibility, and most approvals leave **no** decision record, and **denials/failed auth are
  not logged at all** (A9). So D1 holds for deliberate decisions, not for the authorization plane.
- **Refs:** ADR-0029, ADR-0046, ADR-0056; A9 (failed-auth not logged → denies unrecorded); B1/B3 (authz
  decided off token claims / authentication, not recorded). Tiered coverage is D10.

### D2 — Contents
A decision record carries: the **request** (who, what action, which target, when, correlation id); the
**exact policy version** applied; **inputs pinned to record versions** (REGISTRY R1/R4); **evidence by
reference** (not inline copies); **each rule's result**; the **outcome** with **reason codes**; and the
**decider**.
- **Status: PARTIAL / TO CONFIRM.** The `governance.decision` object captures request, inputs, outcome, and
  decider for the decision spine (ADR-0046 hourglass). **Exact policy-version pinning, per-rule results, and
  evidence-by-reference** completeness are **(to confirm)** — verify the object carries a resolvable policy
  version and a per-rule result array rather than a single outcome.
- **Refs:** ADR-0046, ADR-0029; REGISTRY R4/R7 (pinned versions, provenance). Per-rule-result + policy-
  version fields **(to confirm)**.

### D3 — Replayable
Re-evaluating with the **same policy version and the same pinned inputs** yields the **same outcome**. Any
**model output is recorded as an input** — with the **model identity and version** — and never as the
decider; the **final decider is named** separately.
- **Status: PARTIAL / TO CONFIRM.** The hourglass (facts+rules→decision, ADR-0046) is deterministic by
  design given pinned facts+rules. Whether **model output is captured as a pinned input with model id+version**
  (vs. consumed and discarded) is **(to confirm)** against the model-gateway call path; the model-gateway
  reasoning split (kimi-k3) records model identity at the gateway, but its linkage into the decision record
  as a pinned input is unverified.
- **Refs:** ADR-0046; model-gateway reasoning split; REGISTRY R4/R7. Model-output-as-input **(to confirm)**.

### D4 — Deciding requires recorded authority, named in the record
The decider must hold a **live recorded authority** to make this decision (FOUNDATIONS F2; §3 decision
function), and that authority is **named in the decision record**. Authentication alone never suffices.
**This is the fix for B3.**
- **Status: VIOLATED (fix target).** `decision.py /decide` records **any valid token's `sub`** as the
  deciding authority **with no check** that the principal may decide that task (B3); the effective gate is
  only whatever the kernel applies on the under-token read/write. Deciding authority is therefore asserted,
  not recorded-and-checked.
- **Refs:** **B3** (authority from authentication alone — the rule this fixes), B1; F2, F14 (traceable
  authority names its grantor). **PLANNED:** check a recorded grant before recording a decision, and name
  that grant in the record.

### D5 — Never edited
A decision record is **never edited** (REGISTRY R3). A **correction, appeal, or override** is a **new
decision** that **references the original**; the original stays intact and addressable.
- **Status: IN PLACE for immutability; PARTIAL for the supersede-by-reference flow.** Decision records are
  governed registry records, so append-only/versions-not-edits (REGISTRY R3) holds. The
  correction/appeal/override-as-new-decision-referencing-original flow is the contest machinery (D11) and is
  only partially built.
- **Refs:** REGISTRY R3/R5; ADR-0056. Override-references-original linkage **(to confirm)** — see D11.

### D6 — Denials recorded
A **denial is recorded**, including a **fail-closed** denial (FOUNDATIONS F8), **with its reason**. A silent
deny is not permitted — "no record" must never be the trace of a refusal.
- **Status: VIOLATED.** Failed authentication and most authorization denials are **not logged** (A9); fail-
  closed denials leave no decision record. This is the inverse of D1's allow-side gap and is the more
  security-relevant half.
- **Refs:** **A9** (failed-auth not logged); F8 (fail-closed). **PLANNED:** emit a decision record on every
  deny, including the fail-closed branch, with a reason code (D8).

### D7 — Personal data by reference only
A decision record holds personal data **by reference only** (REGISTRY R14) — a reference + hash, never
inline personal data — so a decision record is itself erasable-compatible.
- **Status: PLANNED (inherits REGISTRY R14).** The erasable personal-data store and reference+hash split are
  not yet built (R14 PLANNED), so decision records cannot yet guarantee personal data is held by reference.
- **Refs:** REGISTRY R14; ADR-0125 (consent); DPDP open item (REGISTRY-v0.1 §Open item, erasure in force
  2027-05-13). Inline-personal-data audit of current `governance.decision` payloads **(to confirm)**.

### D8 — Plain-language reason codes; subject access
Outcomes carry **plain-language reason codes** (not opaque internal errors), and **a person can obtain the
decision records about themselves**.
- **Status: PARTIAL / PLANNED.** Reason-code vocabulary for decision outcomes is **(to confirm)** — verify a
  governed reason-code set vs. free-text. **Subject access** to one's own decision records is **not built**;
  the per-object read-authority/sharing primitive exists but is adopted by 0 prod schemas (REGISTRY R6/R11;
  ADR-0103), and `governance.decision` is not subject-readable today.
- **Refs:** ADR-0103 (per-object access/consent); REGISTRY R6; F13. Reason-code governance **(to confirm)**;
  subject-access **PLANNED**.

### D9 — Linked across decisions, ChangeRequests, and audit
Decision records are **linked via correlation / op ids** to the other decisions, **ChangeRequests**
(ADR-0056), and **audit events** (REGISTRY R12) they relate to — one adjudication is traceable end to end.
- **Status: PARTIAL.** An `op_id` exists and the Trust-plane role_assignment carries `granted_by`/op_id + an
  audit chain (per F14); ChangeRequests are first-class (ADR-0056). A **uniform correlation id threaded
  across decision ↔ CR ↔ audit** is **(to confirm)** — verify a single correlation id is propagated, not
  per-surface ids that must be joined by hand.
- **Refs:** F14 (grantor/op_id chain); ADR-0056 (CR); REGISTRY R12 (audit). Cross-surface correlation id
  **(to confirm)**.

### D10 — Recording depth: full vs. aggregated
**Full records** for **consequential decisions** and **all denials** (D6). **Aggregated records** (principal,
scope, period, count, and the authority records relied on) for **routine allowed reads**. **Any read of
personal data always gets a full record**, regardless of routineness.
- **Status: PLANNED.** There is no tiered decision-logging today — routine reads produce **no** decision
  record (not even aggregated), and personal-data reads are not specially recorded. The tiering (full /
  aggregated / always-full-for-personal-data) is unbuilt.
- **Refs:** D1, D6; REGISTRY R6 (reads), R14 (personal data). Depends on D1 coverage landing first.

### D11 — Contest flow
A **contest is a recorded request**. The **reviewer holds recorded authority** and **is not the original
decider** (separation of duties). The **outcome is a new decision** (D5), and the **original is marked
contested / overridden**.
- **Status: PARTIAL / PLANNED.** The case/review spine exists — Inbox & Case (ADR-0048) and the
  Review/Remedy object (Slice-1, task #62) — and SoD + last-holder floors are defined for platform/tenant
  authority (ADR-0122). But the specific contest→new-decision→mark-original-contested chain, with a
  reviewer-≠-decider check enforced from recorded authority, is **(to confirm)** / not proven end to end.
- **Refs:** ADR-0048 (Inbox & Case), Review/Remedy (#62), ADR-0122 (SoD); D4, D5. Reviewer-≠-decider
  enforcement **(to confirm)**.

### D12 — Automated decisions affecting a person
An automated decision affecting a person requires **either** a **named human approver with recorded
authority**, **or** an **explicit automation policy approved via ChangeRequest** that **names an accountable
owner**. The record **states which**. The person is **told it was automated** and **can contest** (D11).
- **Status: VIOLATED / PLANNED.** Today engines hold a direct write-grant to `governance.decision`
  (campaign-engine, project-engine — **B18**) and the guarantee that a **human authority precedes** such a
  run is **(to confirm)** / not enforced; automated outcomes are **not labelled** as automated to the
  subject, and no automation-policy-via-CR-with-accountable-owner construct is wired. Combined with B3 (D4),
  an automated decider is currently accepted on authentication alone.
- **Refs:** **B18** (engines write `governance.decision` — "engine never decides" at risk), B3; ADR-0056
  (automation policy via CR), ADR-0100 (generic Campaign — outbound population sweep), ADR-0029. Human-
  approver-or-named-owner gate **PLANNED**; subject notification + contest **PLANNED** (D11).

---

## Summary of status

| Rule | Topic | Status | Key debt |
|------|-------|--------|----------|
| D1 | Scope of decision records | PARTIAL/VIOLATED | A9; B1, B3; ADR-0029/0046/0056 |
| D2 | Contents | PARTIAL / *to confirm* | ADR-0046; R4/R7 |
| D3 | Replayable (+model as input) | PARTIAL / *to confirm* | ADR-0046; model-gateway |
| D4 | Deciding needs recorded authority | VIOLATED (fixes B3) | **B3**, B1; F2/F14 |
| D5 | Never edited | IN PLACE (immut.) / PARTIAL (override link) | R3/R5; ADR-0056 |
| D6 | Denials recorded (incl. fail-closed) | VIOLATED | **A9**; F8 |
| D7 | Personal data by reference | PLANNED (inherits R14) | R14; ADR-0125; DPDP |
| D8 | Reason codes; subject access | PARTIAL/PLANNED | ADR-0103; R6/R11; F13 |
| D9 | Linked via correlation/op ids | PARTIAL | F14; ADR-0056; R12 |
| D10 | Full vs aggregated depth | PLANNED | D1, D6; R6, R14 |
| D11 | Contest flow | PARTIAL/PLANNED | ADR-0048; #62; ADR-0122 |
| D12 | Automated decisions re a person | VIOLATED/PLANNED | **B18**, B3; ADR-0056/0100 |

**Tally:** 12 rules — 1 IN PLACE-leaning (D5, immutability), 4 PARTIAL (D2, D3, D8, D9), 4 VIOLATED (D1, D4,
D6, D12), 3 PLANNED (D7, D10, D11). D1 and D12 carry a mixed status; the governing gaps are **B3**
(deciding authority not recorded — D4), **A9** (denials not recorded — D6), and **B18** (engines decide —
D12).

---

## Cross-references
- **FOUNDATIONS:** F2 (authority from recorded state), F8 (fail-closed), F12 (auditable), F13 (consent), F14
  (traceable authority).
- **REGISTRY:** R3 (versions not edits), R4 (pinned/bitemporal inputs), R6 (reads excluded from D1), R7
  (provenance), R12 (audit), R14 (personal data by reference), R15 (public designation).
- **ADRs:** 0029 (decision spine), 0046 (decision hourglass), 0048 (Inbox & Case), 0056 (decided
  ChangeRequest), 0100 (generic Campaign), 0122 (SoD / platform authority), 0125 (consent).

# ADR-0152 — Work allocation, absence and delegation: who does a role's work, and who stands in

**Status:** Proposed
**Date:** 2026-11-28
**Related:** ADR-0048 (role-separated work), ADR-0147 amendment (a case step under the officer's authority), ADR-0148
(a person's delegation to an agent), ADR-0151 (organisation roles, shared roles, *acts as*).

## The problem

A case step is addressed to a role (`role://<organisation>/<role>`), not to a person.

- **Many holders, no allocation.** Everyone holding the role sees the task, limited to their own scope, and whoever
  completes it first closes it. Two officers can work on the same application at once; no one can see who is handling
  what; nothing shares work out.
- **No absence.** If the only holder of a role is on leave, the work waits. The only safety net is a step's time limit
  escalating to another role.
- **No delegation.** Nobody can hand a role to someone else for a period — the everyday "additional charge" or "in
  charge during leave" of an office — so the work stops or the role is granted permanently and forgotten.

## Decision

1. **A task in a role's pool can be picked up.** An officer who holds the role (within its scope) picks the task up;
   from then it shows to the others as being handled by that person, and only they may complete it. They may release
   it back to the pool. A supervisor or administrator may reassign it to another eligible holder. Each change is kept
   with the task (who, when, why).

2. **Assignment can be automatic, per service step.** A service step may choose how its tasks are given out among
   current, eligible holders: *pool* (everyone sees it; pick up — the default), *share evenly*, or *fewest open
   tasks*. Eligible means holding the role for the task's scope and not absent.

3. **Absence is recorded.** A person (or their supervisor) records an absence with a start and an end. During it: new
   tasks are not given to them; tasks they have picked up return to the pool, or go to their named stand-in; their
   Inbox shows who is covering.

4. **A role can be delegated for a period — an additional charge.** A supervisor or administrator gives a named person a
   role for a stated period and reason; an organisation may also allow a holder to name their own stand-in for an
   absence. A delegation:
   - is limited to what the original holder has — the same role and scope, never wider;
   - ends automatically at its end date, and can be ended early;
   - cannot be passed on again;
   - is recorded like any role grant, marked as a delegation (`via: delegation`, from whom, until when, why), and counts
     only inside the organisation, as *acts as* does (ADR-0151 decision 8).

5. **The stand-in acts in their own name.** An act done under a delegation records the person who did it *and* whose
   charge they held ("Ravi, acting for Asha"). Consequential acts carry the stand-in's own signature (ADR-0147
   decision 10); the original holder is not made responsible for what they did not do.

6. **Who may delegate is the organisation's choice,** per role: only a supervisor or administrator (the default), or
   also the holder for their own absence. Roles that issue certificates or change authoritative records may require a
   supervisor's delegation.

7. **Escalation remains the backstop.** A step that passes its time limit still goes to its escalation role, whatever
   the allocation.

## What changes on the current build

| Today | After |
|---|---|
| Every holder sees a role's task; first to complete closes it | Pick up / release / reassign; optional automatic assignment per step |
| Leave is unknown to the platform | Absence with dates: no new tasks, picked-up tasks return or go to the stand-in |
| A role can only be granted, permanently | Time-limited delegation (additional charge), scope no wider, not re-delegable, ends itself |
| The record shows who acted | Who acted, and whose charge they held |

## Acceptance tests

- Two revenue officers see an assessment task; Asha picks it up; Ravi sees "being handled by Asha" and cannot complete it.
- A step set to *share evenly* gives three successive applications to three different eligible officers.
- Asha records leave for a week: new tasks skip her, her picked-up task goes to Ravi, her named stand-in.
- An administrator gives Ravi Asha's ward-169 revenue-officer charge until Friday; Ravi completes a ward-169 assessment
  recorded as "Ravi, acting for Asha"; on Saturday Ravi no longer holds it; he could never act in ward 170 under it.
- Ravi cannot pass the delegated charge to someone else.

## Open questions

1. Holidays and working hours in automatic assignment and time limits.
2. Workload limits (a maximum of open tasks per person) and fairness reporting.
3. Delegation across organisations (an officer of one department lent to another) — likely a mandate (ADR-0147), not a
   delegation.

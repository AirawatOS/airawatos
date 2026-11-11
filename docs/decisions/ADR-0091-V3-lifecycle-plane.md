# ADR-0091 V3 — Lifecycle plane: a generic `request/decide/update/withdraw/status` engine over `platform.workflow`

Status: Proposed (2026-09-16) · Sub-spec of ADR-0091 (interaction verb taxonomy)
Related: ADR-0048 (Case/Workflow/Task + universal Inbox) · ADR-0056 (decided change-request) · ADR-0045
(interaction/workflow declarations) · ADR-0088 (rule engine = `evaluate`) · ADR-0090 (interface bindings +
conformance) · ADR-0091 V2 (Decision-plane collapse — the proven pattern this reuses)

## Why this is the high-value slice
The Lifecycle plane is where the ~60→~12 verb reduction actually lands. Today each domain re-invents an
apply/approve pair as bespoke engine code: `leave-apply`/`leave-decide` (hr-workflows), `expense-apply`/
`expense-decide`, `proposal-submit`/`proposal-decide` (project-engine), `verify-submit` (campaign-engine),
`funding-award`/`funding-release-tranche`, `posting-apply`, the Justice `bail`/`summons`/`hearing` transitions…
Every one is the same shape: **open a case → guard → write a domain record + route to Inbox → transition on a
decision → run effects.** That shape is ADR-0056 (every mutation is a *decided change-request*) executed over an
ADR-0048 Case. V3 makes the shape generic and moves the domain into a `platform.workflow` declaration.

## The anatomy we're generalizing (observed in hr-workflows `leave-apply`)
1. resolve actor context (the employee, their manager);
2. **guard** — a policy check (`evaluate`, V2) e.g. leave-balance availability;
3. **write** the domain record at its initial state (`hr.leave_request`, `status: pending`) — attributed, bitemporal;
4. **route** — create a `platform.inbox_item` for the approver (ADR-0048);
5. on `decide`: **transition** the record's state + **run effects** (settle balance, post finance, issue VC…).

## Decision — the Lifecycle verbs + the declaration

### Generic verbs (one `lifecycle-engine` implements all of them)
| Verb | Meaning |
|---|---|
| `request` | open a new case instance of a workflow at its start state (guarded), write the domain record, route the first task |
| `decide` | apply a named transition to an existing case (guarded + authorized), run its effects, route the next task |
| `update` | edit a mutable draft of the domain record in place (pre-submit), re-guard |
| `withdraw` | actor-initiated terminal transition (cancel own request) |
| `status` | read the case state + history + open tasks (a projection = Data-plane `read`) |

### The domain = a `platform.workflow` declaration (governed data, ADR-0045)
```jsonc
{ "schema": "platform.workflow", "id": "ds:airawatdeveloper:workflow/hr.leave",
  "workflow": "hr.leave", "record_schema": "hr.leave_request",
  "start": "draft",
  "states": ["draft", "pending", "approved", "rejected", "withdrawn"],
  "transitions": [
    { "name": "submit",  "from": "draft",   "to": "pending",
      "actor": "applicant",
      "guard": { "ruleset": "hr.leave_eligibility" },              // ADR-0091 V2 `evaluate`
      "route": { "to": "manager", "task": "approve-leave" } },     // ADR-0048 Inbox
    { "name": "approve", "from": "pending", "to": "approved",
      "role": "manager", "scope": "org_unit",                      // authz key (below)
      "effects": [ { "run": "leave-settle" } ] },                  // ADR-0091 Compute `run`
    { "name": "reject",  "from": "pending", "to": "rejected", "role": "manager", "scope": "org_unit" },
    { "name": "withdraw","from": "pending", "to": "withdrawn", "actor": "applicant" }
  ] }
```
The declaration names: the record schema, the state machine, per-transition **guards** (`evaluate` rulesets),
**effects** (`run` recipes / `write`s), **routing** (Inbox target), and **authorization** (`role` + `scope`).
Everything domain-specific is here — as data an admin/author edits in Studio, not engine code.

### Authorization keys on `(workflow, transition)` — not the verb
Today `authz-check` is asked "may user do `leave-decide`?". Under V3 it's "may user apply transition `approve` on
workflow `hr.leave` at scope `org_unit`?" — expressed with the existing `governance.role_grant` scopes
(`decide@hr.leave:approve` bound to the manager role over an org_unit). The verb (`decide`) is generic; the
authorization unit is the tuple. `authz-check` stays the (locked) PDP that answers it.

### Each transition is a decided change-request (ADR-0056)
`decide` doesn't mutate in place blindly: it records the decision (who, when, guard result, inputs) and the state
change as an attributed, bitemporal registry write — so `status`/History replay the full case lineage. This is
ADR-0056 made the default for every lifecycle mutation, for free, because it's one engine.

## How the generic engine works (one dispatch, any workflow)
`request(workflow, payload)` → load `platform.workflow` → validate payload vs `record_schema` → run the `start`
transition's guard via `evaluate` → `write` the record at `start`→first state → `write` the `platform.inbox_item`
per `route`. `decide(workflow, case, transition, payload)` → load workflow + case → check the transition is legal
from the current state → authorize `(workflow, transition, scope)` via `authz-check` → run guard → `write` the
state change (decided change-request) → run `effects` (`run`/`write`) → route next task. `status`/`update`/
`withdraw` are the obvious specializations. **No per-domain code path** — hr.leave, expense, proposal, bail all run
the same engine; only their workflow records differ.

## Migration — non-breaking, mirrors V2 exactly
1. **V3a — engine + one workflow:** build `lifecycle-engine` implementing `request/decide/update/withdraw/status`
   over `platform.workflow`; author the `hr.leave` workflow (from the existing hr-workflows behaviour).
2. **V3b — alias + shadow:** `leave-apply` → alias `request(workflow=hr.leave, transition=submit)`;
   `leave-decide` → alias `decide(workflow=hr.leave)`. Retain `hr-workflows` handlers as `*-legacy`
   (V2's retained-engine pattern). Shadow-compare: generic vs legacy produce the same record + inbox routing +
   effects. **Fallback guard** (V2): where a workflow isn't authored for a tenant, the alias falls through to the
   legacy engine — non-breaking everywhere.
3. **V3c — fan out:** author workflows for expense, proposal, verify, funding, posting, Justice transitions; each
   collapses its verb pair to `request/decide` aliases; retire aliases per governed deprecation once callers move.
4. **V3d — conformance:** a `governance.conformance_suite` for the lifecycle interface, parameterized by workflow
   (ADR-0090 + V2's ruleset-parameterized cases) — so competing lifecycle engines are interchangeable.

## Consequences
- The single largest block of bespoke BFF/engine logic (all the apply/decide pairs) becomes **one engine + N
  workflow records**. New domains ship a workflow declaration, reviewed through governance — no new verbs, no new
  engine code.
- Case audit (who decided what, when, under which guard) is uniform and bitemporal by construction (ADR-0056).
- Conformance/authz/History all attach to the one lifecycle interface.

### Risks / honest edges
- **Effects are the hard part.** Guards are pure (`evaluate`); effects (`leave-settle`, `finance-post`, VC issue)
  are side-effecting and compose other engines. The declaration must express effects as `run`/`write` steps with
  clear failure/rollback semantics, or the "engine" quietly grows a bespoke tail again. Start with single-effect
  workflows (leave) before multi-effect (funding tranche release).
- **Not every "apply/decide" is a clean state machine.** Some carry rich domain computation (funding stacking,
  payroll apportionment) that belongs in a `run` effect, not the transition itself — keep the state machine thin,
  push computation to Compute-plane engines it calls.
- **Payload schemas still proliferate** (leave vs expense vs proposal) — correctly: those are *nouns*
  (`record_schema`), which SHOULD proliferate. The win is verb collapse, not schema collapse.
- **Migration breadth** — V3c touches many engines; sequence one workflow at a time, shadow before alias, alias
  before deprecate. Same discipline that made V2 safe.

## Recommended first build (V3a + V3b on `hr.leave`)
Build `lifecycle-engine` with `request`/`decide`/`status`; author the `hr.leave` workflow from the current
hr-workflows behaviour; alias `leave-apply`→`request(hr.leave, submit)` and `leave-decide`→`decide(hr.leave)`
with the retained-legacy fallback; shadow-compare generic vs legacy (same `hr.leave_request` record + inbox item +
settled balance). This proves the Lifecycle plane on the exact pattern V2 already validated, local-first.

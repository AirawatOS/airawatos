# ADR-0088 · Slice 2 — convergence: one rule engine, many lenses (policies ⊆ rules)

Status: Proposed (2026-09-16) · Parent: ADR-0088 (domain-services realization spectrum, lane 1)
Builds on: ADR-0088-S1 (governance.policy_rule + rule-engine, LIVE) · ADR-0075 (solution contributions + unified
Setup) · ADR-0037 (Studio) · the existing ERP Policy Console + `org.policy` + `policy-engine`

## Problem

There are now several "admin-edited config → decision" surfaces that are the same *idea* built three times:
- **`org.policy` + policy-engine + Policy Console** — org-hierarchy policies (leave days, expense caps by rank/unit).
- **`governance.rule` + governance-rules engine** — single-metric threshold rules (decision hourglass, air/flood).
- **`governance.policy_rule` + rule-engine (S1)** — the GENERIC condition→effect engine.

Left alone, each new policy area grows a new schema + engine + console — the same god-object sprawl ADR-0087
fought in the BFF, moved into config + admin UIs. This slice defines how they **converge onto one engine and one
admin surface**, without breaking what's live.

## The insight

A **policy is a rule** — it just adds two things a generic rule doesn't need:
1. **A resolution strategy** — org policies pick the *most specific* match in a hierarchy; generic rules take the
   *first* match by priority.
2. **A context provider** — org policies auto-derive their facts from *who the subject is* (an employee's
   classification: posting→position→level, stream, role, unit); generic rules are handed explicit facts.

So policy-engine isn't a different kind of thing — it's the generic engine **plus a `most_specific` resolution
mode plus an org-context provider**. Make those two things pluggable and the three engines become one.

## Decision

### 1. `governance.ruleset` — a ruleset becomes first-class (NEW governed noun)
Today rules are grouped only by a `ruleset` string. Promote it to a descriptor that carries the strategy + who
owns/edits it:
```jsonc
{ "schema": "governance.ruleset",
  "id": "ds:airawat:ruleset/hr.leave_policy",
  "name": "Leave policy",
  "resolution": "most_specific",         // first | all | most_specific
  "context": "org.classify@0.1.0",       // optional: a governed verb that turns a subject → facts (null = caller supplies facts)
  "owner": "platform",                   // platform | tenant  — who authored the DEFAULTS
  "editable_by": ["hr.admin", "tenant.admin"],   // roles a tenant may let edit it (∅ = platform-locked)
  "value_shape": "policy",               // effect carries a VALUE (e.g. {leave_days:18}); vs "gate" (deny/allow)
  "description": "..." }
```
Members stay `governance.policy_rule` rows (S1), with one addition — an optional **`scope`** used only in
`most_specific` mode:
```jsonc
{ "schema": "governance.policy_rule", "ruleset": "hr.leave_policy",
  "scope": { "level": "manager" },        // the tighter the scope, the higher it ranks
  "when": {},                             // may be empty; scope does the selecting in most_specific mode
  "then": { "leave_days": 18 } }          // effect carries the policy VALUE
```

### 2. `rule-eval` gains resolution modes + an optional context step (superset, backward-compatible)
```
rule-eval { ruleset, facts?, subject?, mode? }   →  { decision, matched, trace, winning_scope? }
```
- If the ruleset declares a **`context`** provider and a `subject` is passed, the engine calls that governed verb
  to produce `facts` (e.g. `org.classify(employee)` → `{level, unit, stream, role}`). Else it uses the caller's
  `facts`. **The engine stays generic — the org-tree traversal lives in the context provider (the existing
  org-rbac-engine's containment logic), not in the engine.**
- `resolution`:
  - **`first`** (S1 default) — flat, priority-ordered; first match wins. Generic rules.
  - **`all`** — every matching effect (already in S1).
  - **`most_specific`** (NEW) — of the rules whose `when`+`scope` match the facts, pick the one with the
    **tightest scope** (rank by scope specificity + the defaults-vs-overrides tie-break below). This *is* the
    policy-engine's "most-specific-first" resolution, generalized.
- Output adds `winning_scope` so a policy answer is explainable ("18 days — matched the *manager* rule").

### 3. Defaults vs overrides — precedence, in one line
Developer ships **platform-owned** rules (from Studio, `owner:platform`, tenant-agnostic). A tenant admin adds
**tenant-owned** rows. In `most_specific`, at equal scope specificity **tenant beats platform** (the tenant's
tuning wins); a rule flagged `locked` (platform safety rule, e.g. "hide sensitive PII") can never be overridden
or disabled by a tenant. In `first` mode, precedence is just `priority`, with tenant rows given a lower (earlier)
default band than platform rows.

### 4. One admin surface, lenses on top
There is **one** tenant surface — "Policies & Rules" (the ADR-0075 unified Setup / a generic console) — that
lists `governance.ruleset`s the tenant may edit and renders each through a **lens** chosen by `resolution`:
- `most_specific` + `context:org` → the **org-hierarchy lens** = today's **Policy Console** view.
- `first`/`all` → a **flat rules lens** = the generic Rules view (+ the live `rule-eval` tester).
Studio remains where developers author the **defaults** (ruleset descriptor + platform rules) as solution
members. The **History tab** (shipped) is the audit view of any ruleset/rule — unchanged. So:

| Surface | Who | Role |
|---|---|---|
| **Studio** | developer | author default ruleset + platform rules (solution member) |
| **Policies & Rules console / Setup** | tenant admin | tune/add *tenant* rules on editable rulesets; org lens or flat lens |
| **History tab** | anyone w/ read | see how a rule/ruleset changed (audit) |

Policy Console is thus **not a separate tool to reconcile** — it is the org-hierarchy lens of the one surface.

## Worked examples

| Need | Ruleset | resolution | facts from | effect |
|---|---|---|---|---|
| "Managers get 18 leave days, else 12" | `hr.leave_policy` | most_specific | `org.classify(employee)` | `{leave_days: 18}` |
| "Finance dept expense cap ₹1L, default ₹50k" | `hr.expense_cap` | most_specific | `org.classify(employee)` | `{cap: 100000}` |
| "Any expense over ₹50k needs approval" | `expense.approval` | first | caller passes `{amount}` | `{effect: require_approval}` |
| "Hide sensitive datasets" | `data.visibility` | first | caller passes `{sensitivity}` | `{effect: deny}` |
| "PM2.5 > 90 → advisory (mandatory)" | `air.threshold` | first (threshold adapter) | caller passes `{metric,value}` | `{action, strength}` |

Same schema, same engine, same admin surface — the only differences are the *resolution mode* and *where the
facts come from*, both declared on the ruleset.

## Migration — non-breaking, staged (nothing ripped out)

- **S2a — engine superset.** Add `governance.ruleset` + `most_specific` mode + the context-provider step to
  rule-eval. policy-engine, org.policy, governance.rule all keep running unchanged. (Pure addition.)
- **S2b — express ONE org domain as a ruleset (shadow).** Re-shape e.g. `hr.leave_policy` as a
  `governance.ruleset(most_specific, context:org.classify)` with the org.policy rows as members. Run rule-eval
  **side-by-side** with policy-engine for the same inputs; assert identical answers. (Proof, no cutover.)
- **S2c — cut that domain over + fold the console.** Point `policy-resolve` at the generic engine (policy-engine
  becomes a thin adapter or retires for that domain); Policy Console becomes the org lens of the unified console.
- **S2d — threshold adapter.** Express `governance.rule` (metric/operator/value) as a `first`-mode ruleset via a
  small threshold shim, retiring the third interpreter.
- Each step is one domain at a time, reversible, and validated against the incumbent before cutover.

## Consequences
- One engine + one governed config model + one tenant admin surface for *all* config-as-decision — the ADR-0088
  north-star made concrete for lane 1.
- "Add a policy area" becomes "declare a ruleset + author rows," not "new schema + new engine + new console."
- The org-hierarchy intelligence is preserved as a **context/specificity provider** (org-rbac-engine), not
  reimplemented — the engine stays generic.
- Risk: `most_specific` specificity ranking must be well-defined (scope dimensions + ordering) or policy answers
  become ambiguous — pin the ranking in the ruleset descriptor. Mitigation: shadow-validate S2b against
  policy-engine before any cutover.
- Risk: value-effects vs gate-effects differ — keep `then` opaque; `value_shape` on the ruleset only tells the
  *console/consumer* how to render/interpret, never the engine.
- Non-goal: forcing every existing engine to converge at once. Domains move individually; some may stay
  specialized indefinitely if convergence buys nothing.

## Recommended first build
S2a + S2b for **`hr.leave_policy`**: add the ruleset descriptor + `most_specific` + `org.classify` context
provider, re-express leave policy as a ruleset, and shadow-prove rule-eval == policy-engine on real employees.
That validates the whole convergence on the hardest case (hierarchy) before touching the live Policy Console.

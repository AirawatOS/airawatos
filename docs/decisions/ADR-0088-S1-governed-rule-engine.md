# ADR-0088 · Slice 1 — governed `rule` schema + generic rule engine

Status: Proposed (2026-09-15) · Parent: ADR-0088 (domain-services realization spectrum, lane 1)
Goal: prove that a real decision can be expressed as **governed config evaluated by ONE generic engine**, with
zero custom code per rule — the mechanism that lets most BFF business logic become data.

## What we build

### 1. A governed noun: `governance.rule`
Published via the normal schema-governance path (`/bridge/schema-request` → steward approve). One record = one
condition→effect rule; records sharing a `ruleset` are evaluated together.
```jsonc
{
  "schema": "governance.rule",
  "id": "ds:airawat:rule/data_visibility/hide-sensitive",
  "ruleset": "data.visibility",              // rules with the same ruleset are evaluated as a set
  "description": "Hide sensitivity=sensitive schemas from the data browser",
  "when": { "all": [ { "field": "sensitivity", "op": "eq", "value": "sensitive" } ] },
  "then": { "effect": "deny", "label": "hidden" },
  "priority": 100,                            // lower = evaluated first; first match wins (mode=first)
  "enabled": true
}
```
- `when` = a boolean tree of predicates: `{all:[…]}` / `{any:[…]}` / a leaf `{field, op, value}`.
- `op` (fixed, safe set — NOT a language): `eq ne lt lte gt gte in nin contains exists regex`.
- `then` = an opaque effect object the caller interprets (`{effect, label, …}`) — the engine does not act, it
  **decides**. Keeps it a pure function.
- Naming: `governance` is a governed domain; `governance.rule` is the generic superset (`org.policy`,
  `diagnosis.recipe`, `signal.alert` can later be re-expressed as rulesets — not in this slice).

### 2. A certified engine: `ds:airawat:engine/rule-engine`, verb `rule-eval`
Added to `ENGINE_VERBS`; dispatched exactly like `leave-apply` (ADR-0088 Hop 2–5). `meta.yaml`:
```yaml
component_id: ds:airawat:engine/rule-engine
kind: engine
verbs:   { rule-eval: governance.rule_eval@0.1.0 }   # governed verb (ADR-0058), published alongside
reads:   [governance.rule]
required_schemas: [governance.rule]
```
`run.py` — a small, total evaluator (no eval/exec, no I/O beyond reading rules):
```python
def h_rule_eval(ctx):
    ruleset = ctx["body"]["ruleset"]; facts = ctx["body"].get("facts", {})
    mode = ctx["body"].get("mode", "first")                  # first | all
    rules = sorted([r for r in ctx["kfind"]("governance.rule", {"ruleset": ruleset})
                    if r.get("enabled", True)], key=lambda r: r.get("priority", 100))
    hits = [r["then"] for r in rules if _match(r.get("when", {}), facts)]
    decision = (hits[0] if hits else None) if mode == "first" else hits
    return {"ruleset": ruleset, "matched": len(hits), "decision": decision,
            "trace": [r["id"] for r in rules if _match(r.get("when", {}), facts)]}, None   # ← auditable trace

def _match(node, facts):                                     # boolean tree; total; no code execution
    if "all" in node: return all(_match(n, facts) for n in node["all"])
    if "any" in node: return any(_match(n, facts) for n in node["any"])
    if not node: return True
    v = facts.get(node["field"]); op, want = node["op"], node.get("value")
    return {"eq":v==want,"ne":v!=want,"lt":v is not None and v<want,"lte":v is not None and v<=want,
            "gt":v is not None and v>want,"gte":v is not None and v>=want,"in":v in (want or []),
            "nin":v not in (want or []),"contains":want in (v or []),"exists":(v is not None)==bool(want),
            "regex":bool(v is not None and __import__("re").search(want, str(v)))}[op]
```

## Proof (acceptance criteria)

1. `governance.rule` published (steward-approved); `governance.rule_eval@0.1.0` interface governed.
2. rule-engine certified + published; `rule-eval` in `ENGINE_VERBS`.
3. Seed the `data.visibility` ruleset (the one rule above).
4. `POST /bridge/rule-eval {ruleset:"data.visibility", facts:{sensitivity:"sensitive"}}` → `decision:{effect:"deny"}`
   with a `trace` naming the matched rule; `facts:{sensitivity:"internal"}` → `decision:null`.
5. **Re-home one real BFF rule:** `_bridge_data_schemas` calls `rule-eval` for each schema instead of the
   hardcoded `sens != "sensitive"` check. Behaviour identical; the *policy* now lives in a governed record an
   admin can edit — not in the host image. (This is the first concrete BFF-logic → config move.)

## Out of scope (later slices)
- Rule authoring UI + Solution Architect "propose a ruleset" (lane-selection).
- Re-expressing `org.policy` / `diagnosis.recipe` / `signal.alert` as rulesets.
- Effects that *act* (that's the workflow lane, ADR-0089) — this slice only *decides*.
- Caching evaluated rulesets per tenant (add if hot).

## Build outcome (2026-09-15) — LOCAL-FIRST, PROVEN

**Reuse-vs-propose decision:** `governance.rule` already exists (v0.1.0/0.2.0) as a **single-metric threshold
rule** (required: metric/operator/value/proposed_action) consumed by the live `governance-rules` engine
(air/flood recommendations). Reusing that id for a predicate-tree rule would fail strict schema validation. So
this slice PROPOSED a distinct noun: **`governance.policy_rule`** (condition→effect). Convergence with the
threshold `governance.rule` is a later slice.

**Shipped + proven on the local stack (kernel+network=prod authority per ADR-0084 local topology):**
- Governed on the network: schema `governance.policy_rule@0.1.0` + interface `governance.rule_eval@0.1.0`.
- Engine `ds:airawat:engine/rule-engine` (verb `rule-eval`) — `components/engines/rule-engine/{run.py,meta.yaml}`.
  Pure evaluator (fixed safe operator set: eq/ne/lt/lte/gt/gte/in/nin/contains/exists/regex + all/any/not tree),
  returns `{matched, decision, trace}`. `--selftest` truth table PASSES.
- Wired `rule-eval` into `ENGINE_VERBS` + `BRIDGE_VERBS` (app_host.py).
- Local proof (devrick@airawatdeveloper): seeded the `data.visibility` ruleset (hide-sensitive, allow-public) →
  `/bridge/rule-eval` returns: sensitive→deny (trace=[hide-sensitive]); ref→allow (trace=[allow-public]);
  plain→null (matched=0). ✅
- **Re-home (acceptance #5) DONE + demonstrated:** `_bridge_data_schemas` now decides visibility via the
  rule-engine over `data.visibility` (fallback = the original `sens=="sensitive"` if engine/rules unavailable).
  Demo: added a governed rule hiding `governance.policy_rule` → after cache-bust the schema DISAPPEARED from the
  browser; disabled the rule → it returned. Behaviour is now editable config, zero code change. ✅

**Deploy state:** LOCAL only (local app-host overlay image `airawatos-reference:0.2.1-local-rule`). EC2 deploy
(new reference image with rule-eval + engine) NOT done — held for approval.

**Multi-tenant follow-up:** the seeded rule lives in one tenant; for the re-home to apply platform-wide, add
`governance.policy_rule` to the kernel's `SHARED_SCHEMAS` (read-unscoped like ref.*/viz.layer) so every tenant
reads the platform policy. Batch eval (`facts_list`) would also let data_schemas evaluate all schemas in one call.

## Why this is the right first slice
It is the highest-leverage, lowest-risk lane: pure function, no new runtime, rides the existing engine-dispatch
spine, and immediately converts a real piece of hardcoded BFF policy into an admin-editable governed record —
demonstrating "config, not code" end to end. Effort: ~1 schema + 1 small engine + 1 caller edit.

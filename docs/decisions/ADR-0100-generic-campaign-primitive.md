# ADR-0100 — The Campaign primitive: proactive, goal-directed sweeps of a population

**Status:** Proposed (2026-09-20)
**Relates to:** ADR-0091 (interaction verb taxonomy — domain in config, not verbs), ADR-0097 (one interaction spine — Case/Task substrate), ADR-0048 (Inbox / Case / Task), ADR-0047/0067 (service = inbound request), ADR-0046 (decision hourglass — facts+rules→decision→outcomes), ADR-0029 (AI recommends → authority admits), ADR-0088 (rule engine — routing policy), ADR-0089 (Compute plane — rollups as `run`), ADR-0056 (decided change-request). Supersedes the tax-coupled `campaign-engine` (#175) as the reference implementation.

## Context

The platform grew a `campaign-engine` to run the **tax field-verification loop** (#175): a manager creates a campaign, assigns AI-flagged tax candidates to field officers, and each officer records on-site ground truth → a `governance.decision` that verifies or dismisses the candidate. It works, but it is **tax-coupled in code**: the engine reads tax-candidate fields (`parcel_id`, `confidence`, `estimated_revenue`), its outcomes are tax-specific (`confirmed|not_taxable|not_found`), and its recorded fields are property-specific (`built_area`, `assessed_value`). That is the same anti-pattern ADR-0091 removes for verbs — domain baked into code instead of carried in config.

But "campaign" is not a tax feature, and it is not even *one* feature — it is a recurring **operational shape** the state uses constantly. Field verification is one instance; enumeration/surveys, service-delivery drives (vaccination, ration, pension enrolment), inspections (food-safety, fire, licence), grievance-backlog sweeps, asset-condition assessment, remediation drives, outreach/canvassing, recovery drives, and sector-deployment monitoring are all the **same thing** with a different subject. Each currently would need its own bespoke engine. We should have **one Campaign primitive** they all configure.

### What a campaign IS

A **campaign is a time-boxed, goal-directed sweep of a *population* by a *distributed workforce*, with progress tracked toward a target.** It is the **proactive / outbound** counterpart to a service:

- **Service** (ADR-0047/0067) = *inbound*: one citizen asks, one provider fulfils (pull).
- **Campaign** = *outbound*: the state picks a **population** and pushes work through it to a **coverage/count goal** (push).
- **Project** (ADR-0071) = the funded results-contract that may *pay for* a campaign.

The invariant across every campaign is four things; only these vary by domain:

```
  a TARGET SET   ×   a WORKFORCE   →   a per-item ACTION + OUTCOME   →   PROGRESS vs a GOAL, in a WINDOW
  (which items?)     (which agents?)    (what they do / record)         (how far, by whom, how much left)
```

The tax engine hard-codes all four. The fix is to make all four **declared**.

## Decision

Introduce a **generic Campaign primitive** — not a new engine per domain, but a thin **orchestration layer that composes the existing planes** (ADR-0091). "Tax field verification" becomes one *configuration* of it, exactly as `hr.leave` is one configuration of the generic Lifecycle plane.

### 1. Three governed nouns

- **`campaign.campaign`** — the container: `scope` (a **selector** over a governed target noun — a query/filter or an explicit set), `goal` (`{metric: count|coverage, target: N}`), `window` (`{opens, closes}`), `workflow` (the id of the per-item `platform.lifecycle` to run), `assignment_policy` (see §3), `status` (`draft|active|closed`).
- **`campaign.assignment`** — one **work-item** per enrolled target: `{campaign, target, target_schema, assignee, status, outcome, result, decision}`. *Domain-neutral*: `target` is any noun id; `parcel_id`/revenue live on the target, not here.
- **`campaign.enrolment`** *(optional projection)* — the resolved target set, for progress + idempotent re-enrolment.

The domain-specific parts — **target noun, outcome vocabulary, recorded fields, target-status mapping** — are declared, never coded.

### 2. The per-item lifecycle is the generic Lifecycle plane (ADR-0091/0097)

Each work-item runs a `platform.lifecycle` over `campaign.assignment`: `assign` (open + route to an agent) → `verify`/`act` (agent records a **declared outcome + fields**) → a `governance.decision` (ADR-0029/0056) + a **declared status update** on the target. This is the part #263 already generalized — the assign→verify FSM is a plain declaration; the only code needed is a small **compute-provider** per domain for anything the declaration can't express (e.g. deriving `taxable`/revenue), invoked as a `{call}` effect. The outcome set and field list are declared on the workflow, so a health-screening campaign declares `{screened, referred, absent}` and a licence inspection declares `{compliant, violation, closed}` with **zero engine change**.

### 3. Enrolment, assignment policy, progress — the other three planes

- **Enrolment** = **Data plane**: a `read`/query over the target noun (from `scope`) → bulk-open one lifecycle instance per target (`request`). Selection is config.
- **Assignment policy** = **Decision plane**: `evaluate` a governed ruleset to route each item — **by jurisdiction** (org-rbac containment, ADR-0028), **round-robin** across an agent pool, **self-pick** from a role queue, or **manual**. The strategy is a policy, not code.
- **Progress + close** = **Compute plane** (ADR-0089): `run` a rollup recipe → burn-down, coverage %, by-outcome, by-agent, by-area — measured against `goal`; auto-close when the goal is met or `window.closes` passes.

So the Campaign primitive is **mostly declaration + orchestration**: it *is* Data-select → Lifecycle-per-item → Decision-route → Compute-rollup, wired by the `campaign.campaign` config. There is no per-domain campaign engine.

### 4. Where it sits among the primitives

| Primitive | Direction | Cardinality | Driver |
|---|---|---|---|
| **Service** (0047/0067) | inbound (pull) | one requester → one case | a citizen asks |
| **Campaign** (this ADR) | **outbound (push)** | **one goal → many items → a workforce** | the state sweeps a population |
| **Project** (0071) | internal | a results-contract over time | funds/plans the work |

Campaign reuses the **same Case/Task substrate** (ADR-0048) and Inbox routing as Service and the internal lifecycles — a field agent sees the assignment as an actionable Inbox item, identical to how a manager sees a leave approval.

## Consequences

- **Positive:** one primitive serves a dozen domains (verification, surveys, delivery drives, inspections, grievance sweeps, asset assessment, remediation, outreach, recovery, deployment) with only a declaration each; tax stops being special; the state gains a first-class "proactive operations" capability to sit beside "reactive services"; progress/coverage governance (goal + burn-down) becomes uniform and auditable.
- **Costs:** a real refactor of a live tax feature — decouple `verify-decide` from tax outcomes/revenue (drive them from config), generalize the target from `tax.candidate` to any noun, and add the enrolment + assignment-policy + progress orchestration. Non-breaking migration: the tax config is authored first so the tax loop is byte-identical, then the coupling is removed underneath it.
- **Naming:** the reference engine is renamed to reflect that it is generic orchestration (candidate: `campaign-engine` kept but decoupled, or a neutral `verification`/`fieldwork` engine); the tax specifics move to a `tax` campaign **configuration**, not a `tax`-named engine.

## Rollout

1. **C1 — the per-item lifecycle, generic (largely #263).** Author the assign→verify `platform.lifecycle` over `campaign.assignment` with the tax config (outcome set + fields + status map + a tax compute-provider). Prove byte-identical to the bespoke tax loop. *(In progress — the generic engine features it needs — `guard.compute`, required `{call}` effects, multi-field `link` — already shipped in #263.)*
2. **C2 — decouple the engine.** Move outcomes/fields/target-status/revenue from `verify-decide` code into the declaration + a thin tax compute-provider; generalize `target` to any noun.
3. **C3 — the container + enrolment.** `campaign.campaign` config + a Data-plane selector that bulk-opens per-item lifecycles from `scope`.
4. **C4 — assignment policy.** Decision-plane routing (jurisdiction / round-robin / self-pick / manual) as governed config.
5. **C5 — progress + close.** Compute-plane rollup vs `goal`; auto-close on goal/window; a generic Campaign Console.
6. **C6 — prove generality.** Stand up a *second* campaign type by config only (e.g. an inspection or a survey), no engine change — the acceptance test for "generic."

## Status today

**C1 + C2 — DONE (2026-09-20), live+green on EC2 (nashik).** The tax field-verification loop now runs entirely on the generic assign→verify `platform.lifecycle` over `campaign.assignment`, with **zero tax vocabulary in the engine**: the outcome set (`confirmed|not_taxable|not_found`), the outcome→target-status map, the captured ground-truth fields, the revenue-on-approve rule, and the target-field passthrough (`parcel_id`) are all **declared** in the `platform.lifecycle` (see `seed_campaign.py`) and passed to the domain-neutral `campaign-engine` compute-providers (`assign-prepare`, `verify-decide`) as config. Enabling engine features (shipped in #263 + this slice): `guard.compute`, required `{call}` effects, multi-field `link`, `opener_field`, `__drop__` transient inputs, prepare-hook `args`, and single-record start-transition effects. The bespoke `campaign-assign`/`verify-submit` handlers remain as the `*-legacy` fallback (still tax-shaped, deprecated). Green e2e: candidate `flagged→assigned→verified`, `estimated_revenue 500000`, `governance.decision` written — through the config-driven engine, byte-compatible with the old loop. Source: `components` commit `8727c57`.

What is **not** built yet: a *second* campaign config to prove generality end-to-end (C6 — needs a non-tax target noun whose schema carries a writable status field), the campaign container + enrolment (C3), the assignment-policy plane (C4), and the progress/close rollup + console (C5).

# ADR-0091 — Interaction verb taxonomy: few generic verbs, domain expressed as data

Status: Proposed (2026-09-16)
Related: ADR-0048 (Case/Workflow/Task — universal inbox) · ADR-0056 (decided change-request pattern) ·
ADR-0058 (interaction contracts / interfaces) · ADR-0088 (rule engine + domain-services spectrum) ·
ADR-0089 (event/message spine) · ADR-0090 (interface bindings + conformance marketplace) · ADR-0087 (governed bridge)

## Context

The app-host today wires **~60 domain-specific verbs** (`leave-apply`, `expense-decide`, `gap-scan`,
`funding-award`, `welfare-prioritise`, `campaign-assign`, `policy-resolve`, `authz-check`, …), each a distinct
governed interface (`hr.leave_apply@0.1.0`, `tax.gap_scan@0.1.0`, …) dispatched via `ENGINE_VERBS` /
`/bridge/gov`. Every new domain adds new verbs. This is verb proliferation, and it is avoidable.

The reference architectures that scaled — **HTTP** and **Beckn** — did the opposite. They keep a **small, fixed,
semantically load-bearing verb set** and let the **nouns proliferate**:
- HTTP: ~9 methods over a universal resource model (URIs); domain lives in the *resource + body + media type*.
- Beckn: ~10 verbs as async request/callback pairs over one commerce lifecycle
  (`search→select→init→confirm→status/track/cancel/update/rating/support`). A ride, a meal, and a clinic
  appointment use the *same* verbs; the difference is entirely in the `Item`/`Fulfillment` **schema**, the domain
  code, and **tags**. Beckn never adds `book-ride`.

AirawatOS already owns the generic layer — twice over — but never named it as the verb contract:
1. **Data plane is already generic**: the kernel exposes ~4 operations — registry **read** (`/v1/registry/resolve`),
   **write** (`/v1/registry/objects`), **history**, **retract** (tombstone). That is our GET/POST/DELETE.
2. **The lifecycle spine is already decided**: ADR-0056 ("every mutation is a *decided change-request*") + ADR-0048
   (Service→Case→Workflow→Task→Inbox) are a generic `request → decide → transition` state machine where the
   *workflow declaration* is the domain part. `leave-apply`/`expense-apply`/`proposal-submit` are all `request(kind)`;
   `leave-decide`/`proposal-decide`/`verify-submit` are all `decide(case, transition)`.
3. **The decision spine is already decided**: ADR-0088's rule engine is a generic `evaluate`; we proved
   `policy-resolve == rule-eval(ruleset)`. So `policy-resolve` / `authz-check` / `matchpolicy-*` are **rulesets**,
   not verbs.

So most of the ~60 verbs are re-inventions of a handful of interaction shapes. This ADR names the shapes.

## Principle

> **Verbs are few and load-bearing; nouns and configuration proliferate.** Domain-specificity is expressed as
> governed *data* — schema + ruleset + workflow declaration + payload contract + tags — never as a new verb.
> A new verb is justified only by a genuinely new **interaction shape**, not a new domain.

## Decision — the interaction planes

AirawatOS is wider than Beckn (it spans lifecycle **and** analytics **and** policy evaluation **and** messaging),
so a single flat verb list is wrong. Instead we define **five planes** and a small generic verb set per plane.
`{noun}`/`{config}` are governed data, not part of the verb.

| Plane | Generic verbs | Domain expressed in | Semantics |
|---|---|---|---|
| **Data** | `read`, `write`, `history`, `retract` | schema + record id | CRUD over the bitemporal registry (already generic; kernel-native) |
| **Decision** | `evaluate` | `ruleset` (`governance.policy_rule`) + facts | pure function: governed rules × facts → decision + trace. Never acts. |
| **Lifecycle** | `request`, `decide`, `update`, `withdraw`, `status` | `workflow` declaration + case schema + transition | open/advance a Case; each transition is a decided change-request (ADR-0056) |
| **Compute** | `run` | analysis `recipe` (engine + params) + output schema | batch derivation over governed data → derived records (attributed) |
| **Messaging** | `post`, `subscribe` | channel/message schema + event `topic` (ADR-0089) | append to a channel / register a subscription |

Everything read-only that isn't `evaluate` is `read` with a projection (`allocation-list`, `campaign-progress`,
`project-review`, `funding-received/monitor`, `chat-channels`, `mail-list` are all `read`).

### Mapping the current ~60 verbs onto the planes
- **Decision** ← `rule-eval`, `policy-resolve` (both now aliases of `evaluate`); `authz-check` (belongs here but stays
  `binding_policy: locked` per ADR-0090 — grant resolution + security-critical, not opened to competition).
  *(Correction after V2 build: `matchpolicy-get`/`matchpolicy-set` are config read/write → **Data** plane, and
  `match-preview` is a stateless scorer → **Compute** — none is an `evaluate`. A verb's plane is its interaction
  SHAPE, not its domain proximity.)*
- **Lifecycle** ← `leave-apply/decide`, `expense-apply/decide`, `proposal-submit/save/decide`, `verify-submit`,
  `campaign-create/assign`, `funding-award/release-tranche/subscribe/revoke-subscription`, `allocation-set`,
  `posting-apply`, `process-order`, `bail`/`summons`/`warrant`, `hearing`…
- **Compute** ← `gap-scan`, `collection-coverage-scan`, `welfare-gap-scan`, `welfare-deprivation-scan`,
  `welfare-prioritise(-cells)`, `waste-compliance-rank`, `*-rollup`, `funding-stack`, `need-rollup`,
  `payroll-apportion/preview`, `match-preview`, the geo/ML pipelines (`pm25-*`, `flood-*`, `station-interpolation`, `ward-h3-map`)
- **Data (read/write)** ← `matchpolicy-get` (read), `matchpolicy-set` (write), and every projection listed under Query below
- **Messaging** ← `chat-send/create`, `mail-send`, ADR-0089 emits/subscribes
- **Query (=Data.read)** ← `allocation-list`, `campaign-progress`, `project-review/evaluate`, `funding-received/monitor`,
  `chat-messages`, `mail-list/get`, `payroll-schedule` (get)

**~60 bespoke verbs → ~12 generic verbs + a projection library.**

## The domain-as-data contract

Each generic verb takes one governed **descriptor** that carries the domain:
- `evaluate` → `{ ruleset, facts | subject }` resolves a `governance.ruleset` (ADR-0088-S2). *No domain code.*
- `request`/`decide` → `{ workflow, case?, transition, payload }` resolves a `platform.workflow` declaration
  (ADR-0045/0048) that names the case schema, the allowed transitions, the guard rulesets (`evaluate`), and the
  effects (writes / sub-`run`s). *Domain = the workflow record + schema.*
- `run` → `{ recipe }` resolves a recipe descriptor naming the compute engine + params + output schema. *Domain =
  the recipe.*
- `post`/`subscribe` → `{ channel | topic, message | filter }` (ADR-0089). *Domain = the channel/topic + message schema.*

So a domain author ships **records** (a workflow, a ruleset, a recipe, schemas), not a new engine with new verbs —
except in the ADR-0088 "custom engine" lane, which now registers under `run`/`decide` rather than minting a verb.

## Interaction with ADR-0090 (this is the migration mechanism)

Rationalization is **non-breaking** because interface bindings already let a name route anywhere:
- A legacy domain verb becomes a **thin alias** — its interface binds (ADR-0090) to a generic engine + a config
  param. `policy-resolve` stays callable; its binding routes to `rule-engine` with `ruleset=org.policy`.
  Apps don't change.
- **Conformance moves from per-verb to per-config.** A `governance.conformance_suite` attaches to the *generic*
  interface (`evaluate`, `decide`) and is **parameterized by the descriptor** (ruleset / workflow). One suite proves
  the evaluator; per-ruleset property cases prove the config. This is *fewer, stronger* contracts than 60 one-offs —
  and it requires extending the ADR-0090 suite construct to take config.
- **Authorization keys on `(verb, descriptor, transition)`**, expressed with existing `governance.role_grant`
  scopes — e.g. `decide` on `workflow=hr.leave` at `transition=approve`. The verb name is no longer the authz unit;
  the (verb, workflow, transition) tuple is.

## Worked example — leave approval, before and after
Before: app calls `POST /bridge/leave-decide {case, decision}` → `hr-workflows` engine with a bespoke handler +
its own `hr.leave_decide@0.1.0` interface.
After: app calls `POST /bridge/decide {workflow:"hr.leave", case, transition:"approve", payload}`. The host resolves
the `hr.leave` **workflow declaration**, checks the caller holds `decide@hr.leave:approve`, runs the transition's
guard via `evaluate(ruleset=hr.leave_eligibility, facts)`, and on pass writes the state change as a decided
change-request (ADR-0056) — an attributed, bitemporal `hr.leave_request` version. `leave-decide` survives as an
alias bound to `decide` for one release, then is deprecated. **No app rewrite; one generic lifecycle engine; the
domain is the `hr.leave` workflow record.**

## Migration — staged, non-breaking
- **V1 — name the planes (spec only):** ratify the 5 planes + ~12 verbs + the descriptor contracts. No code.
- **V2 — Decision plane collapse:** re-home `policy-resolve`/`authz-check`/`matchpolicy-*` onto `evaluate` +
  rulesets (extends the ADR-0088-S2 work already proven); keep the old verbs as bound aliases.
- **V3 — Lifecycle plane collapse:** a generic `lifecycle-engine` implementing `request/decide/update/withdraw/status`
  over `platform.workflow` declarations; migrate `hr-workflows`, `project-engine`, `campaign-engine`,
  `funding-engine` lifecycle verbs to workflow records; old verbs become aliases.
- **V4 — Compute + Messaging planes:** register scans/rollups under `run(recipe)`; fold chat/mail/events under
  `post`/`subscribe` (ADR-0089).
- **V5 — Deprecate aliases:** once callers move to generic verbs, retire the domain-verb aliases (governed
  deprecation, version discipline).

## Consequences
- The verb surface stops growing with the domain count. New domains ship **records** (workflow, ruleset, recipe,
  schema), reviewed through governance, not new engine code with new verbs.
- Conformance, authz, audit, and the History/`/prov` views all attach to a **stable, small** interface set —
  simpler to reason about and to certify.
- ADR-0090's marketplace gets sharper: competitors implement `evaluate` / `decide` / `run`, not 60 niche contracts.

### Risks / honest edges
- **God-endpoint risk.** Collapsing verbs pushes complexity into fat, mode-switched payloads. Survivable only with a
  *strong shared object model* — the schema registry + descriptor contracts must be disciplined, or `decide` becomes
  an untyped dumping ground. This is the single biggest failure mode; guard it with per-descriptor conformance.
- **Not everything is a lifecycle.** Forcing analytics into `request/decide` is Procrustean — hence a distinct
  `Compute` plane. Resist over-unification; five planes, not one.
- **Descriptor discovery.** With generic verbs, "what can I call?" becomes "what workflows/rulesets/recipes exist?"
  — needs a good catalog surface (Studio + Data app), or discoverability regresses vs named endpoints.
- **Migration is broad.** V3 touches every lifecycle engine. It is non-breaking (aliases-via-binding) but it is not
  small; sequence it plane-by-plane, prove each with shadow-compare (ADR-0088-S2b) before deprecating aliases.
- **Wire protocol vs. Beckn.** This governs the *internal* interaction verbs. Beckn/ONDC interop (external commerce)
  remains a separate adapter concern (ADR-0067 service federation) — do not conflate the two verb sets.

## Recommended first build
V2 (Decision plane) — it is already proven: `policy-resolve` collapses to `evaluate(ruleset=org.policy)`
(ADR-0088-S2b shadow-compare passed). Ship it as bound aliases behind `evaluate`, extend the ADR-0090 conformance
suite to take a `ruleset` parameter, and use it as the reference pattern for the Lifecycle collapse (V3).

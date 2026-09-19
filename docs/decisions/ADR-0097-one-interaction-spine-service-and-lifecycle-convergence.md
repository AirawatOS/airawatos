# ADR-0097 — One interaction spine: converging services and lifecycles onto a single workflow graph

**Status:** Proposed (2026-09-19)
**Relates to:** ADR-0091 (interaction verb taxonomy — few generic verbs), ADR-0048 (Case/Workflow/Task — universal inbox), ADR-0047 (service vs solution — cross-provider offerings), ADR-0067 (service directory + init/confirm/status runtime), ADR-0056 (decided change-request), ADR-0023 (federated Data/Requests/Events), ADR-0046 (decision hourglass), ADR-0088 (rule engine — `evaluate`), ADR-0090 (interface bindings + conformance), ADR-0044 (Solution/Service Architect agent).

## Context

Two subsystems, built at different times, turn out to be the **same thing**:

1. **The internal lifecycle plane (ADR-0091 V3).** `lifecycle-request / decide / status` over a governed
   `platform.lifecycle` **state machine**; opens the domain record, routes an approval task, applies a transition.
   Staff-facing, intra-tenant. Proven live on `hr.leave` (2026-09-19).
2. **The service runtime (ADR-0047/0067).** `service-search / init / confirm / status / route / consent` over a
   governed `service.offering` (an intake **form** + an ordered **workflow step-list** + roles + credentials +
   jurisdiction); `init` opens a `platform.case` in the **provider** tenant. Citizen-facing, cross-provider,
   federated. Live in Service Studio, which even has an **AI expert** that authors the offering from a description.

They share everything that matters: a **small fixed verb set**, a **governed declaration** carrying the domain, a
**Case/Task** substrate (ADR-0048), and **routing to an actor's Inbox**. A service step that routes to a provider
*is* a `decide`/`request` on that provider's lifecycle. The only real difference is **where fulfilment happens** —
the caller's own tenant vs. another provider's.

But three overlapping **workflow representations** have accreted, and they block "one spine":

| Model | Shape | Good for | Weak at |
|---|---|---|---|
| `platform.lifecycle` | **state machine** (states + `apply/approve/reject` transitions) | adjudication / approvals; branching on outcome; send-backs (cycles) | parallel fan-out / joins |
| `service.offering.workflow` | **ordered step-list** (`submit→verify→approve→issue`, each with role + credential) | linear multi-step fulfilment | branching, cycles |
| `platform.workflow` (ADR-0048) | **step-DAG** (steps + `assignee_role` + `after` deps + parallel) | orchestration: sequence, parallel, joins | branching on a decision outcome |

Leave/expense are FSMs. A property-transfer or building-permit service is a DAG *with* an approve/reject decision
inside it. Neither model alone is enough, and maintaining three is the reason the two runtimes can't merge.

## Decision

### 1. One substrate, one declaration, one verb set

**The Case/Task model (ADR-0048) is the runtime substrate.** A **Case** carries status; **Tasks** are units of work
routed to actors' Inboxes. Everything else is expressed as a **workflow graph** over it.

**The declaration is a workflow GRAPH whose nodes are typed steps and whose edges are dependencies + guarded
transitions.** This subsumes all three legacy models — an FSM is a tiny graph, a step-list is a linear chain, a
step-DAG is the general case:

- **node kinds:** `task` (work routed to a role; completes → unblocks dependents — the DAG lane) · `decision`
  (an actor picks one of several outgoing transitions; branches — the FSM lane) · `effect` (a system step: a
  registry `write` or a `{call}` to another engine — ADR-0091 E1) · `gateway` (join/split).
- each node declares: `guard` (an `evaluate` ruleset, ADR-0088), `route`/`assignee_role`, `after` (deps),
  `transitions` (for `decision` nodes), `effects` (`write` | `call`), `notify`.
- A leave FSM = `apply(task) → approve|reject(decision)`. A permit = `submit(task) → [site-check ∥ doc-check](tasks)
  → review(task) → grant|refuse(decision) → issue(effect)`. **Same schema.**

**The generic verbs operate on the graph** (ADR-0091 Lifecycle plane, canonical names):

| Verb | Meaning on the graph |
|---|---|
| `request` | open a Case at the entry node; materialise ready Tasks | (`service-init` becomes an alias) |
| `decide` | complete a `decision` node — pick a transition → advance | (`service-confirm` → alias) |
| `update` | complete/patch a `task` node → unblock dependents | |
| `withdraw` | terminate the Case | |
| `status` | the Case state + open Tasks | (`service-status` → alias) |

`service-search` stays a **Data-plane read** (discover offerings by jurisdiction/entitlement); `service-consent`
and `service-route` stay as the federation *transport* (below), not new interaction verbs.

### 2. Fulfilment locality is a per-node flag, not a second runtime

Each node declares **where it runs**:
- `fulfilment: local` — the Task/decision executes in the caller's tenant; effects write the caller's records.
- `fulfilment: { provider | offering }` — the node is a **federated Request** (ADR-0023) to another provider's
  exposed interaction; its Task/Case lives in the **provider** tenant, decided by *that* provider's authority with
  *its own* signed receipt (ADR-0046/0047). The parent Case tracks it as a pending federated step.

So a **cross-provider service** = a workflow graph some of whose nodes are federated; an **internal ERP lifecycle**
= a graph all of whose nodes are local. One declaration model, one verb set, one Case substrate — **the only
difference is a node's locality.** This is the convergence: there is no separate "service engine" and "lifecycle
engine", only the generic Lifecycle plane with local and federated nodes. `service-route`/`-consent` become the
**transport + consent gate** a federated node uses, not a parallel interaction surface.

### 3. Unify the three schemas → one `platform.workflow` graph; `service.offering` becomes an envelope

- Deprecate `platform.lifecycle` (FSM) and `service.offering.workflow` (step-list) as *declaration shapes*; both
  express as the unified **`platform.workflow`** graph (extend ADR-0048's schema with `decision` nodes +
  `transitions` + `guard` + `effects`, harmonising the fields the FSM used).
- **`service.offering` keeps its citizen/discovery envelope** — `jurisdiction`, `entitlement`, `request_schema`
  (intake form), directory registration, `interaction` (which verbs it exposes) — and **references** a
  `platform.workflow` for its process. The offering is *"a workflow + a discovery/entitlement wrapper + a form."*
- Existing `platform.lifecycle` records (e.g. `hr.leave`) are mechanically lifted to the graph form; aliases keep
  callers working (ADR-0090 bindings), so the migration is non-breaking.

### 4. Authoring: generalise Service Studio, don't build a new surface

Service Studio already authors workflow declarations (form + steps + roles + credentials) with an **AI expert**
grounded in governed roles/credentials. It becomes **the** workflow-authoring studio for the unified model — it
emits `platform.workflow` graphs consumed by *both* the local and federated paths, and `service.offering`
envelopes when the process is a citizen-facing service. (This subsumes the ADR-0091 "E5" authoring enabler.)

## Consequences

- **One spine.** Staff approvals and citizen services stop being two stacks; new domains (local or federated) ship
  a workflow graph — reviewed through governance, authored in Studio — not engine code and not new verbs.
- **The verb catalog stops growing** (ADR-0091 delivered on the widest domain): `request/decide/update/withdraw/
  status` cover leave, expense, permits, grievances, court cases, funding, and cross-provider journeys alike.
- **Conformance & authz sharpen** (ADR-0090): one suite per generic verb parameterized by the graph; authz keys on
  `(verb, workflow, node/transition)` — e.g. `decide@building.permit:grant`.
- **Federation is first-class, not bolted on:** a federated node is the ADR-0046 hourglass — each provider decides
  its own step under its own authority with its own receipt; the parent Case is the audit thread.
- **Beckn/ONDC interop stays external:** this governs the *internal* interaction spine; a federated node MAY be a
  Beckn call to an external network — the graph doesn't care what a node's transport is.

### Risks / honest edges
- **One graph model is heavier than a 2-state FSM.** Mitigate: simple cases stay simple (leave = a 2-node graph);
  the Studio + AI expert hide the graph for authors; conformance guards the "god-declaration" failure mode.
- **Async federated nodes** make a Case long-lived and partially-pending — already true for services; the status
  projection must make pending federated steps legible.
- **Migration touches live ERP + the service runtime.** Do it behind aliases + fallback (proven pattern), one
  domain at a time, dev-first.
- **Two engines to retire into one** — sequence carefully; keep both runtimes serving until the unified interpreter
  is proven across an FSM case (leave), a local DAG (multi-step approval), and a federated service (property
  transfer).

## Migration (staged, non-breaking)
- **C0 — ratify** the unified `platform.workflow` graph schema (add `decision`/`transitions`/`guard`/`effects` to
  ADR-0048's step model) + the node `fulfilment` flag. Spec only.
- **C1 — one interpreter:** extend the lifecycle-engine to interpret the graph (task nodes + decision nodes +
  `{call}` effects — ADR-0091 E1); prove it on `hr.leave` (FSM) unchanged.
- **C2 — local DAG:** prove a multi-step local workflow (e.g. an approval with parallel checks) on the interpreter.
- **C3 — federated node:** express one `service.offering` (e.g. a single-provider service) as a graph with a
  `fulfilment:{provider}` node; route via the existing gateway (`service-route`/`-consent`); `service-init/confirm/
  status` become aliases of `request/decide/status`.
- **C4 — Studio:** generalise Service Studio to emit `platform.workflow` graphs (+ `service.offering` envelope).
- **C5 — retire:** deprecate `platform.lifecycle` + `service.offering.workflow` as declaration shapes; both are the
  graph; retire the parallel service-runtime handlers into the unified interpreter.

## Open questions
1. **Verb names at the citizen edge.** Keep Beckn-flavoured `init/confirm/status` as the public BAP-facing aliases
   while the governed plane is `request/decide/status`? (Lean yes — aliases are cheap, names aid interop.)
2. **Case vs domain record.** Today the lifecycle engine writes the *domain record* (`hr.leave_request`) as the
   case; the service runtime writes a `platform.case` pointing at subjects. Unify on: a `platform.case` spine +
   a domain record it references? Or the domain record *is* the case (status field)? (Recommend: `platform.case`
   is the spine; the domain record is a subject — cleaner for multi-record and federated flows.)
3. **Where the graph lives for a service** — embedded in `service.offering` or referenced by id (reusable across
   offerings)? (Lean referenced.)

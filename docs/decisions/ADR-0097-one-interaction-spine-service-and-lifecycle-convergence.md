# ADR-0097 — One interaction spine: converging services and lifecycles onto a single workflow graph

**Status:** Accepted — **build ratified 2026-09-22** (clean-cut, **no aliases**; see the "Build (ratified 2026-09-22)" section, which supersedes the staged *Migration* + *Open questions* below). Foundations already in place: ADR-0091/#263 (generic verbs `request/decide/update/withdraw/status` + `lifecycle-engine` over the Case/Task spine; `hr.leave` live).
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

## Extraction plan (app_host → engine) — grounded in the 2026-09-20 audit

A full audit of `app_host.py` (2026-09-20) confirmed the **service-request runtime is the single largest
embedded-domain surface** still in the host — an entire BAP/BPP + workflow interpreter + a hardcoded fee table.
This plan lifts it into the certified lifecycle-engine per §1–2, non-breaking, smallest-first (the proven
`platform.verb_alias` + `*-legacy` fallback pattern from ADR-0091).

**Embedded surface to lift** (app_host.py):
- **Workflow interpreter:** `_advance_service_workflow` (labelled *"THE WORKFLOW INTERPRETER"*) + the service
  branches inside `_bridge_complete` / `_bridge_decide`.
- **BAP/BPP orchestration:** `_bridge_service_init / _route / _confirm / _status / _consent / _search`,
  `_provider_fulfil`, `_verify_consent` / `_verify_required_credentials`, `_service_receipt`, `_txn_status`.
- **Hardcoded business DATA:** `_quote_fee` / `_FEES` — a per-service price list *in code* (self-labelled
  "SIMULATED (reference); production: derive from the offering's fee_ref / finance.* rules").
- **Secondary domain shapers** (independent slices): `_intake_core` (hardcoded civic category taxonomy →
  incidents/cases), `_bridge_ingest_document` / `_retrieve` / `_expert_chat` (knowledge; the last hardcodes
  `risk.flood` math), `_bridge_approve_rule[s]` (governance rule enactment), `_bridge_camera_configure`
  (`device.camera` shaping), `_write_civic_profile` (`civic.profile` shaping).

**Slices — non-breaking, dev-first:**
- **S1 — externalize the fee table (DATA).** Move `_FEES` out of code onto the `service.offering` envelope as
  `fees:[{item,amount}]` (or a governed `ref.fee_schedule` referenced by the offering's existing `fee_ref`);
  `_quote_fee` reads governed data, falls back to the offering. Zero interpreter change — the cleanest proof that
  business *data* leaves host code and becomes governed config. **(done first.)**
- **S2 — interpreter into the engine.** Port `_advance_service_workflow` into the lifecycle-engine's graph
  interpretation (it already does FSM + `platform.case` spine + task/decision/`{call}` effects — §1/C1). The
  service branches in `_bridge_complete` / `_bridge_decide` become generic `lifecycle-update` / `lifecycle-decide`
  on the case. Prove byte-identical on one live service (e.g. `grievance-file`).
- **S3 — service verbs become aliases.** `service-init → lifecycle-request`, `service-confirm → lifecycle-decide`,
  `service-status → lifecycle-status` (governed `platform.verb_alias`, the proven recipe). `service-search` stays a
  Data-plane read; `service-route` / `-consent` stay as the federation transport (§2), not interaction verbs.
- **S4 — federated node locality.** `_provider_fulfil` + consent/credential verify become the `fulfilment:{provider}`
  node transport the engine invokes, not host orchestration.
- **S5 — retire.** Remove the service-runtime handlers from app_host once the engine path is proven across an FSM
  (leave), a local DAG (multi-step approval), and a federated service; deprecate `service.offering.workflow` as a
  declaration shape.
- **Parallel (independent) — secondary shapers.** civic intake → a certified civic-intake compute engine
  (`compute.run`, category vocab as config); knowledge ingest/retrieve/expert → a knowledge engine; `approve_rule[s]`
  → the governance Lifecycle plane; camera / civic-profile shapers → their own engines. Each is its own small slice
  on the proven patterns.

**Acceptance:** re-running the app_host audit shows **zero (B) service handlers** — the host retains only routing,
session/attribution, generic dispatch (`_dispatch_engine` / `compute-run` / `_dispatch_alias`), component lifecycle,
and thin proxies.

---

## Build (ratified 2026-09-22) — supersedes the staged *Migration* + *Open questions* above

**Directive (user, 2026-09-22): clean-cut convergence, no aliases.** Nothing is in production, so we do **not**
keep the old verbs, do **not** run two engines in parallel, and do **not** stage behind `platform.verb_alias`
fallbacks. We build the one graph model, **delete** the old service verbs + the embedded service runtime, and
**migrate or delete** existing declarations/offerings — including retracting stale *published* services — as needed.

**Open questions resolved:**
1. **No internal Beckn aliases.** The governed plane is `request / decide / update / withdraw / status` only. If an
   external Beckn/ONDC edge is ever needed, `init/confirm/status` map at the *transport boundary* (a BAP adapter),
   never as governed interaction verbs.
2. **`platform.case` is the spine; the domain record is a *subject* it references** (cleaner for multi-record +
   federated flows).
3. **The graph is a first-class `platform.workflow`, referenced by id** (reusable across offerings); `service.offering`
   references it rather than embedding it.

### Build slices
- **W0 — Govern the unified `platform.workflow` graph schema. ✅ SHIPPED (2026-09-22).** `platform.workflow@1.0.0` governed via the network (clean major bump over the ADR-0048 0.1.0/0.2.0 DAG versions, kept until W4); artifact `components/engines/lifecycle-engine/govern_workflow_graph.py`. Proven: a full building-permit graph (all 5 node kinds + `sla`/`escalate` + `timer` + `gateway`) validates; a bad node kind is rejected. Node kinds `task | decision | effect | gateway | timer`;
  each node carries `guard` (ADR-0088 `evaluate` ruleset), `route`/`assignee_role`, `after` (deps), `transitions`
  (decision nodes), `effects` (`write` | `call` — ADR-0091 E1), `notify`, **`sla`/`escalate`** (deadlines +
  escalation ladder), and `fulfilment` (`local` | `{provider|offering}`). `service.offering` keeps only its envelope (`jurisdiction · entitlement · request_schema ·
  interaction`) and **references** a `platform.workflow` by id. Deprecate `platform.lifecycle` and
  `service.offering.workflow` as declaration *shapes*. Steward-signed via the network.
- **W1 — The one interpreter (workflow-engine). ✅ SHIPPED (2026-09-22).** Extended the existing `lifecycle-engine`
  (already runs the 5 verbs over the Case/Task spine — #263) to interpret the full graph, as a strict **superset** of
  the FSM: it reuses `_run_effects`/`_authorized`/`_approver`/`_task_scope` and adds a graph interpreter
  (`_advance_graph` + `h_graph_request/update/decide/status` + `h_tick`). Each of the 5 bare verbs auto-detects a
  `platform.workflow` decl for the requested `workflow` (`_gwf`) and routes to the graph handler; otherwise the legacy
  FSM path is untouched (non-breaking). Node-state lives in the case's **freeform `scope._graph`**
  (`{done,open,waiting,decisions}`) — **no `platform.case` schema change**. `_advance_graph` materialises every
  ready-not-active node each tick: `task`/`decision` → route to Inbox with actions calling `update`/`decide` (carrying
  a `node` arg); `effect` → run `_run_effects` then done; `gateway` → done (readiness already enforced the join/split
  via `after`); `timer` → register a `platform.schedule` `tick` wake-up + wait. A dependency `"node:transition"`
  (e.g. `after:["decide:approve"]`) is satisfied only when that branch was taken — this is how a decision's outcome
  gates the effect. **Proven on EC2 (kmc), both shapes against the one engine:** (a) a local **DAG** (`submit` →
  `check_a ∥ check_b` → `join` → `decide[approve|reject]` → `issue` effect) — request opens the case + start task;
  completing `submit` materialises **two parallel tasks**; the `join` gateway stays blocked until **both** complete;
  `decide:approve` runs the effect and closes; `decide:reject` closes **without** running the effect. (b) the
  **FSM-as-graph** (`hr.leave` shape: `apply` routed to a **named** manager via `route.to_field` → `decide`) —
  transition + `stamp` (`$sub` → `user://kmc/kanpur-admin`) + close, behaving identically to the FSM path. Engine
  `ds:airawatdeveloper:engine/lifecycle-engine@0.1.19`; test residue retracted. *(EC2 delivery: run.py in the
  components-cache on the durable `/data` volume; proper filestore re-publish of 0.1.19 rides W4/rollout.)*
- **W2 — Federated node locality. ✅ SHIPPED (2026-09-23).** A `task` node with `fulfilment:{provider,workflow}`
  is a federated Request (ADR-0023): its Case lives in the **provider** tenant, decided under that authority; the
  parent Case tracks it **pending** and reconciles when the leg closes. Wired via a **host-held capability** (the
  authority boundary is real: the graph engine's `ctx.kwrite` is attributed to the engine in the *current* tenant and
  physically can't write into a provider tenant — cross-tenant writes need the provider-admin token only the host
  mints). Two capabilities added to `_engine_ctx`, same trust model as `provision_login`/`ensure_install` (the secret
  stays host-side): **`federate(provider,workflow,title,payload,parent_case)`** → `_federate_open` mints the
  provider-admin token and opens the leg by driving the **same lifecycle-engine** under provider authority (via a new
  optional `token` override on `_engine_ctx`/`_invoke_engine`) — *one engine, both sides*; **`remote_status(provider,
  remote_case)`** → `_federate_status` reads the leg back cross-tenant. In `_advance_graph`, a task node whose
  `fulfilment` is a dict federates instead of routing locally: it parks the node as `waiting` and stashes
  `scope._remote[node] = {provider, remote_case, transaction_id, status}` (no `platform.case` schema change — `scope`
  is open). There's **no push callback** (the transport is same-host cross-tenant), so the parent **reconciles on
  `status`/`tick`** (`_reconcile_federated`): it polls each waiting leg and, when the provider sub-case is
  closed/resolved, marks the node done and advances. **Proven on EC2:** a `kmc` permit graph (`submit → noc → decide →
  issue`) whose `noc` node has `fulfilment:{provider:nashik, workflow:nashik.noc}` — the leg opened as a
  **nashik-owned** case (`ds:nashik:case/…`, `opened_by user://nashik/nashik-admin`) driven by nashik's own governed
  graph; the parent stayed waiting until **nashik decided (grant) + closed** its leg under its own authority; a parent
  `status` reconciled it (`noc` done), the parent advanced to `decide → issue` and closed. Engine `@0.1.20`; host
  baked into `manishsv/airawatos-reference:0.2.70` (recreated + re-proven on the baked image); test residue retracted.
  *(A best-effort `network.service_transaction` ledger write gives the requester a "My Requests" correlation; the
  `service-route`/`-consent` VC+fee+consent gates + `service.offering` envelope resolution attach in W4/W5 when the
  step-list services migrate — W2 proves the graph↔provider seam itself.)*
- **W3 — Delete the old service runtime + verbs (hard-cut, once W1/W2 are green).** Remove from `app_host.py`:
  `_advance_service_workflow`, `_bridge_service_init/route/confirm/status/consent`, `_provider_fulfil`,
  `_service_receipt`, `_txn_status`, and the hardcoded `_quote_fee`/`_FEES` (fees move to the offering envelope as
  `fees:` / `fee_ref` — governed data). **Delete** the `service-init/confirm/status` interaction verbs — **no
  aliases**. Keep `service-search` (a Data-plane read) + the federation transport.
- **W4 — Migrate + clean up existing declarations (dev-first, one-shot).** Lift `hr.leave` (FSM) + the step-list
  services (`grievance-handling`, `justice-case-management`, `declarative-service`, ADR-0067 offerings) + any
  `platform.workflow` DAGs to the unified graph; **retract stale published services + old-shape
  `service.offering.workflow` / `platform.lifecycle` records** (user-authorized). Re-govern the migrated graphs.
- **W5 — One authoring surface.** Generalize **Service Studio** to emit `platform.workflow` graphs + `service.offering`
  envelopes (subsumes the ADR-0091 "E5" enabler); its AI expert authors the graph from a description. Developer
  Studio's "＋ Workflow" (Rules & Automation, ADR-0104-era DX) points here — one true workflow-authoring surface for
  local + federated.
- **W6 — Conformance + docs.** One `governance.conformance_suite` per generic verb, parameterized by the graph
  (reachability; every `task` has a role; every `decision` has ≥1 transition; every `effect` references a governed
  schema/verb); authz keys on `(verb, workflow, node)` — e.g. `decide@building.permit:grant`. Update the concept
  docs; retire the "three workflow models" language (this ADR becomes the record).

**Order + acceptance.** W0 → W1 (prove FSM + DAG) → W2 (prove federated) → **W3 delete** (only after W1/W2 green) →
W4 (migrate/clean) → W5 → W6. **Accept when:** a *single* `lifecycle-engine` runs an FSM (leave), a local DAG
(multi-step approval), and a federated service (e.g. property transfer) from one `platform.workflow` graph; the
app_host audit shows **zero (B) service handlers**; and **no** `platform.lifecycle` / `service.offering.workflow`
declaration *shapes* remain in the codebase or the registry.

### W0 detail — the `platform.workflow` graph schema (concrete)

A workflow is a **set of typed nodes** over the Case/Task spine (ADR-0048). Edges are expressed two ways:
**`after`** (dependency edges → sequencing, parallelism, joins) and a `decision` node's **`transitions`**
(branch edges → outcomes, send-backs / cycles). The `platform.case` is the spine; the `subject_schema` domain
record is a *subject* it references.

```jsonc
{
  "schema": "platform.workflow",
  "id": "ds:$tenant:workflow/building-permit",
  "name": "Building permit",
  "version": "1.0.0",
  "subject_schema": "permit.application",   // domain record the case REFERENCES (it isn't the case)
  "start": "submit",                         // entry node
  "nodes": [
    { "id": "submit", "kind": "task",
      "route": { "role": "applicant", "title": "Submit application" }, "after": [], "fulfilment": "local" },
    { "id": "doc_check", "kind": "task",
      "route": { "role": "records-clerk", "title": "Verify documents" },
      "guard": { "ruleset": "permit.docs_complete" }, "after": ["submit"] },
    { "id": "site_check", "kind": "task",
      "route": { "role": "field-inspector", "title": "Site inspection" }, "after": ["submit"] },  // ∥ doc_check
    { "id": "review", "kind": "task",
      "route": { "role": "building-officer", "title": "Review" },
      "after": ["doc_check", "site_check"],                         // JOIN: waits for BOTH
      "sla": { "due_in": "P5D", "escalate": [                       // deadline + escalation ladder
        { "after": "P5D", "notify":   { "role": "building-officer" } },   // reminder at breach
        { "after": "P7D", "reassign": { "role": "senior-officer" } } ] } },  // then hand it up
    { "id": "objection_window", "kind": "timer",
      "after": ["decide:grant"], "wait": "P15D", "to": "issue" },   // TIMER gate: 15-day objection window before issue
    { "id": "decide", "kind": "decision",
      "authorize": { "any": [ { "role": "building-officer" } ] }, "after": ["review"],
      "transitions": [
        { "name": "grant",    "to": "issue", "stamp": { "decided_by": "$sub", "decided_at": "$now" } },
        { "name": "refuse",   "to": "END",   "stamp": { "decided_by": "$sub" } },
        { "name": "sendback", "to": "submit" }                      // CYCLE — send back to applicant
      ] },
    { "id": "issue", "kind": "effect",
      "effects": [
        { "write": { "schema": "permit.certificate", "from_subject": true } },
        { "call":  { "verb": "credential.issue", "body": { "type": "permit", "subject": "$subject_ref" } } }
      ],
      "after": ["objection_window"] }                              // after the objection window closes
  ]
}
```

**Node kinds — the whole vocabulary:**

| kind | what it does | key fields |
|---|---|---|
| `task` | work routed to a role's Inbox; completing it unblocks dependents | `route`/`assignee_role`, `guard?`, `after`, `notify?`, `fulfilment` |
| `decision` | an actor picks one outgoing `transition` → branches (or cycles back) | `authorize`, `transitions[]`, `after` |
| `effect` | a system step — a registry `write` or a `{call}` to an engine (ADR-0091 E1) | `effects[]`, `after` |
| `gateway` | explicit split/join when `after` alone isn't enough | `mode: split\|join`, `after`, `to[]` |
| `timer` | a time gate — fires after a duration / at a deadline, then advances (objection window · cooling-off · appeal deadline) | `wait`/`until`, `after`, `to` |

- **Templating** (the live lifecycle grammar): `$sub` · `$now` · `$subject_ref` · `$record.<field>` — in `stamp`,
  `route.title`, `effects.body`.
- **Fulfilment locality per node:** `"local"` or `{ provider | offering }` (a federated Request — its task/case
  lives in the provider tenant, decided under that authority with its own receipt; the parent case tracks it pending).
- **SLA / deadlines / escalation (per `task` or `decision`):** a node may declare
  `sla: { due_in: <ISO-8601 duration> | due_at: "$record.<field>", escalate: [ { after: <duration>, <action> }, … ] }`.
  An escalation action is `notify: {role}` · `reassign: {role}` (hand the task up) · `transition: <name>` (auto-advance,
  e.g. auto-approve/close) · `effect: {…}`. The `escalate` list is an **ordered ladder**; each step fires **once**
  (idempotent). A standalone **`timer`** node is a pure time gate — `wait: <duration>` or `until: "$record.<field>"`
  → `to: <node>` — for objection windows, cooling-off, appeal deadlines. **Enforcement (W1):** the workflow-engine
  registers a `platform.schedule` wake-up per open SLA / active timer; on fire it applies the due ladder step or
  advances the timer node. So **time is a first-class driver of the case**, backed by the existing scheduler — not a
  cron bolted on the side.
- **Simple stays simple:** leave (FSM) = `apply`(task) → `approve|reject`(decision), 2 nodes; a linear complaint =
  a chain of `task` nodes each `after` the previous (today's step-list).
- **The verbs operate on the graph:** `request` opens the case at `start` + materialises ready tasks · `decide`
  completes a `decision` node · `update` completes a `task` · `withdraw` terminates · `status` projects
  case-state + open tasks.

### W0 known limitations (govern the schema aware of these; candidate later node kinds noted)

**Structural / expressiveness**
1. **No data-flow edges.** The graph is *control* flow; data moves implicitly through the shared subject/case
   record — no typed "output of A → input of B" wires. Real data mapping lives in an `effect: call` to an engine.
   It orchestrates; it does not compute or transform.
2. **No iteration / dynamic fan-out.** "Do X per line-item / per document" (multi-instance) isn't first-class —
   no `foreach`/multi-instance node. Pre-declare fixed parallel branches, or push the loop into an engine `call`.
3. **Guards are rulesets, not code.** A `guard` is an ADR-0088 `evaluate` ruleset; branching that isn't expressible
   as a ruleset must become an `effect: call` returning a value a `decision` reads (an extra hop).
4. **Join semantics are basic.** Multi-`after` = wait-*all*. Wait-any / N-of-M / discriminator joins need extra
   `gateway` modes.

**Time & lifecycle**
5. **Timers / SLA / escalation ARE first-class (W0).** `sla`/`escalate` on tasks + a `timer` node, enforced via
   `platform.schedule` (see the SLA note above). Residual limit: durations are **wall-clock** — no built-in
   business-calendar / working-hours / public-holiday awareness yet (a breach ladder counts calendar time);
   calendar-aware deadlines need an `effect: call` to a calendar engine, or a later `calendar` option on `sla`.
6. **No boundary events / interrupts.** A running task can't be interrupted mid-flight by an external event; the
   only cancellation is `withdraw` of the whole case.
7. **No compensation / saga.** Effects are forward-only — no declared "undo the earlier `write`/`issue`" if a late
   node fails. Rollback is a manual follow-up workflow.

**Federation & versioning**
8. **Federated nodes can hang.** A `fulfilment:{provider}` node makes the case partially-pending until the other
   provider responds — no built-in timeout/abandon; the status projection must make "pending elsewhere" legible.
9. **In-flight version migration undefined.** Cases running on graph v1 stay on v1 when v2 publishes; migrating
   *live* cases to a changed graph isn't modeled — they finish on the old shape.

**Cognitive / scope**
10. **"God-declaration" risk.** A genuinely complex process becomes a large, hard-to-read graph — mitigated by
    Studio + AI author + conformance, but real. The escape hatch stands: **sufficiently complex services bind a
    bespoke certified solution** rather than over-stretch the graph.
11. **Not general BPMN, deliberately.** A governed *subset*: no ad-hoc / dynamic case management (a reviewer
    inventing a step at runtime), no external transport concerns (Beckn/ONDC stay at the edge). A feature for
    auditability; a limit for flexibility.

**Candidate later node kinds (NOT in W0):** `foreach` (multi-instance, #2), `compensate` (saga rollback, #7).
(Timers / SLA / escalation are now **W0 core** — the five node kinds are `task | decision | effect | gateway | timer`.)
Ship this core first; add the deferred kinds only when a real domain needs them.

### W-cal (optional, after W1) — business-calendar / working-hours / public-holiday awareness

W0 SLA/timer durations are **wall-clock** (limitation #5). To make "3 business days" skip weekends + holidays, add
one governed calendar + one pure engine + two optional `sla` fields — no change to anything that doesn't opt in
(absent `basis:business` → wall-clock, exactly as today). *Nothing calendar-related exists in the codebase today
(verified 2026-09-22) — this is greenfield, mirroring the `ref.*` reference-data pattern (`ref.source`,
`ref.codelist`).*

**1. `ref.calendar` — a governed calendar as reference data**, per jurisdiction (a city ≠ a state ≠ a court):
```jsonc
{ "schema": "ref.calendar", "id": "ds:$tenant:ref/calendar/kmc", "jurisdiction": "space:kmc",
  "timezone": "Asia/Kolkata", "working_days": ["mon","tue","wed","thu","fri"],
  "working_hours": { "start": "10:00", "end": "17:00" },              // omit → whole-day granularity
  "holidays": [ { "date": "2026-01-26", "name": "Republic Day" }, … ] }  // REAL data — admin-entered or ingested
```

**2. `calendar-engine` — pure, certified computation** (logic = engine, per the platform): governed verbs
`calendar.due(start, duration, calendar_id) → deadline_instant` (add N business days/hours, skipping non-working
days + holidays) · `calendar.is_working` · `calendar.next_working`. Side-effect-free → cheap to certify + test.

**3. `sla` gains two optional fields** — the whole opt-in:
```jsonc
"sla": { "due_in": "P3D", "basis": "business",          // "wall" (default) | "business"
         "calendar": "ref/calendar/kmc",                 // optional; else resolved from the case's jurisdiction
         "escalate": [ { "after": "P2D", "basis": "business", "reassign": {"role":"senior-officer"} } ] }
```

**Runtime (extends W1's SLA/timer step only):** when a `task` becomes ready with `basis:business`, the
workflow-engine resolves the calendar (`sla.calendar`, else jurisdiction → `ref.calendar`), calls
`calendar.due(now, due_in, calendar)`, and registers the `platform.schedule` wake-up **at that computed instant**
(each escalation rung likewise). The scheduler, wake-up, and once-only firing are unchanged — only the deadline
*instant* comes from the calendar engine instead of `now + duration`. Falls back to wall-clock if no calendar
resolves (never blocks); conformance can warn a `basis:business` node with no resolvable calendar.

**Authoring home — Org Setup (HR owns the org calendar).** The working-day / holiday calendar is HR's domain, so
Cal-3 adds a **"Calendar / Holidays"** tab to the **Org Setup** app (`components/apps/org-setup`) that writes the
`ref.calendar` record. Today Org Setup has no such tab and no governed calendar exists — this is the home. **One
governed `ref.calendar` is then consumed everywhere:** HR leave / attendance / payroll (working-day counts,
holiday-aware proration — today payroll prorates by raw day-fraction) *and* civic-service SLAs (a permit's business
days skip the same holidays). A jurisdiction with special calendars (e.g. court holidays) defines its own
`ref.calendar` and points a workflow's `sla.calendar` at it; the org base calendar stays HR's, in Org Setup.
Holidays may also be **ingested by a certified `holidays` driver** (a government source → `ref.calendar.holidays`)
for scale — real data either way.

**Design decisions to make:** (a) **snapshot vs recompute** — compute the deadline once at task-ready (simple; a
holiday added later won't shift it) vs recompute each scheduler tick (handles late edits, costs a call per wake) —
*recommend snapshot + an admin "recompute deadlines" action*; (b) **granularity** — whole-business-day first (90%
of civic SLAs); sub-day working-hours later (partial days / rollover); (c) **timezone/DST** — carried on the
calendar, computed in it (a test gotcha, not a fork).

**Cal slices (after W1):** **Cal-1** govern `ref.calendar` + certify `calendar-engine` (whole-day) · **Cal-2**
`sla.basis`/`calendar` + wire the engine's SLA/timer registration to `calendar.due` · **Cal-3** Org Setup
"Calendar / Holidays" tab (+ optional `holidays` ingest driver), per jurisdiction · **Cal-4** (optional)
working-hours granularity + recompute-on-holiday-change. Degrades safely to wall-clock everywhere it isn't
configured.

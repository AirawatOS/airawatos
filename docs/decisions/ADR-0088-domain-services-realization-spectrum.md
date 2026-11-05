# ADR-0088 — Domain services: the realization spectrum, converging in Solution Studio

Status: Proposed (2026-09-15)
Related: ADR-0022 (everything-is-a-component) · ADR-0029/0046 (decision spine) · ADR-0030 (component SDK + broker
clean-room) · ADR-0034/0037 (Studio authoring, project-first) · ADR-0035 (solutions = member graph) ·
ADR-0044 (Solution Architect agent) · ADR-0045/0050 (solution runtime + execution engine) · ADR-0058
(interaction contracts / interfaces) · ADR-0067 (civic service federation / Service Studio) · ADR-0087
(governed bridge — declared-interface dispatch)

## Context

Business logic has accreted in the app-host BFF — not just proxying, but real decisions: RBAC/scope evaluation
(inbox role-expansion + scope containment), privacy rules (`personal` owner-scoping, `sensitivity=sensitive`
exclusion), data classification (`ref.*` public vs token-scoped), work routing, multi-source aggregation, and
cross-tenant consent. ADR-0087 R2 set out to thin the host; the R2/A1 finding was decisive: **this logic can't
be table-collapsed — it has to move somewhere.** The agreed destination is **domain-service components**
(ADR-0022/0030 substrate; ~48 engines already prove the pattern, e.g. hr-workflows, policy-engine, tax-gap).

But "move it to a component" is under-specified, because a component's behaviour can be expressed four very
different ways, and today each is a **separate authoring world**: Studio projects (custom engines), Service
Studio (ADR-0067 services), raw `platform.workflow`/`platform.subscription` declarations, and scattered
per-domain config consoles. There is no single surface where an author describes a capability and the platform
realizes it the cheapest correct way. That convergence is this ADR.

## Decision

**A domain service is a certified component. Its behaviour is realized on a spectrum, and every point on the
spectrum is a uniform member of a solution graph authored in Solution Studio.**

### The realization spectrum (cheapest correct lane first)

1. **Declare / configure → a generic RULE engine.** Behaviour = governed `rule` records (condition → effect)
   evaluated by ONE generic evaluator. For gates, limits, thresholds, classification, RBAC/scope, routing.
   *Today:* the shape exists but as bespoke interpreters (`policy-engine`, `governance-rules`,
   `diagnosis.recipe`, `signal.alert`, `org-rbac-engine`'s scope containment). *Gap:* one governed `rule`
   schema + one generic rule-engine component they collapse into.
2. **Orchestrate → a generic WORKFLOW engine.** Behaviour = a declared DAG (steps, guards, human tasks) run by
   an interpreter. For SOPs, case lifecycles, approvals. *Today:* `platform.workflow`/`platform.subscription`
   declarations exist and Studio edits them, but they are executed by *custom* engines (hr-workflows,
   project-engine, case-scrutiny). *Gap:* the generic interpreter — **ADR-0050 execution engine, still
   Proposed** — is the keystone that turns a workflow from code into config.
3. **Service-shape → Service Studio.** Behaviour = an interaction contract (ADR-0058 interface) + intake form +
   scope-map + fulfilment, for the request→fulfil→receipt civic-service pattern (ADR-0067). *Today:* live, but
   authored on a path **separate** from Studio projects.
4. **Custom component.** Hand-written engine `run.py` for genuinely novel/complex logic (ML, geospatial,
   scoring). *Today:* ~48 engines. This is the escape hatch and stays.

### Uniformity: one `domain-service` member kind

The solution graph (ADR-0035) treats all four lanes identically — a member is
`{kind: domain-service, realization: rule|workflow|service|engine, declares: [interfaces], reads/writes: […]}`.
The certifier governs it the same way; the app-host `/bridge/gov` dispatches to it the same way it now
dispatches `network.data_exchange` (ADR-0087). The caller (app or another service) never knows or cares which
lane realized the capability — it just calls the declared interface.

### The Solution Architect picks the lane (ADR-0044 extension)

Given a described capability, the agent proposes the **cheapest correct lane** (rule > workflow > service >
custom), generates the declaration (a `rule` set, a workflow DAG, a service spec) or scaffolds a custom engine,
and adds it as a graph member. It already does description→graph→scaffold→certify→publish; this adds
lane-selection + declaration generation. Humans keep the two confirm gates (spec approval, publish).

### Convergence in Solution Studio

Solution Studio = the Studio app + Solution Architect (ADR-0034/0037/0044) becomes the single authoring surface
where all four lanes live in ONE project, ONE graph, ONE certify/publish. Service Studio (ADR-0067) folds in as
the "service" lane rather than a parallel tool. The result: "add a domain capability" is a **declaration + a
lane choice**, not a decision about which tool to open.

## How the BFF logic re-homes (worked mapping)

| BFF logic today (app_host.py) | Lane | Realized as |
|---|---|---|
| inbox/task role-expansion + scope containment (`query`) | 1 rule | scope-containment rules on `org-rbac-engine`-as-evaluator |
| `personal` owner-scoping; `ref.*` public vs scoped | 1 rule | governed access-classification rules |
| `data-schemas` sensitivity exclusion | 1 rule | `sensitivity=sensitive ⇒ hidden` rule |
| leave / expense / approvals | 2 workflow | already done (hr-workflows) — the proof |
| civic request → fulfil → receipt | 3 service | ADR-0067 service (already live) |
| pm25 / tax-gap / welfare scoring | 4 custom | engines (already) |

Once these are uniform members, R2 completes itself: the host stops carrying the logic and simply routes to the
declared domain-service interface.

## Sequencing

1. **Rule engine + governed `rule` schema (Lane 1) — FIRST.** Highest leverage: re-homes the largest share of
   BFF logic as config, zero custom code, and unifies the four existing bespoke rule interpreters. Prove it by
   moving 2–3 real BFF rules (sensitivity-exclusion, owner-scoping, a scope-containment rule) onto it.
2. **ADR-0050 execution/workflow interpreter (Lane 2).** Turns workflows from code into declarations.
3. **Fold Service Studio into Solution Studio (Lane 3)** as one lane in one project.
4. **Solution Architect lane-selection + `domain-service` member kind** — the unifying authoring + graph change.
5. **Retire BFF logic handler-by-handler** as each capability lands on a lane (finishes ADR-0087 R2/R3).

## Consequences

- Adding a domain capability becomes a declaration + a lane choice — governed, versioned, certifiable — not
  host surgery and not, by default, custom code.
- The app-host becomes a genuinely thin, auditable router (ADR-0087 end-state).
- One rule engine + one workflow interpreter replace a sprawl of bespoke interpreters; consistency + one place
  to audit "what logic runs."
- Risk: the generic rule/workflow engines must be expressive enough for real cases without becoming a bad
  programming language. Mitigation: keep Lane 4 (custom) as a first-class escape hatch; do not force config.
- Migration is incremental and reversible: each capability moves on its own; existing engines already conform.

# ADR-0076 — The Solution anatomy, and process-first, form-anchored authoring

- **Status:** Proposed (2026-09-06)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0044 (Solution Architect agent: description → graph → generate → certify →
  publish — this ADR makes the *graph* an explicit layered anatomy and makes a **document** the primary seed),
  INT-0003 (Studio projects; the build workspace this reshapes), ADR-0058 (interaction contracts — the verb legs
  the domain model decomposes into), ADR-0038 (spec governance + `<domain>.<subject>` naming — how the nouns get
  governed), ADR-0060 (L0→L4 representation ladder — the data → insight spine of layers 2–3), ADR-0029/ADR-0046
  (decision spine — layer 5), INT-0002 (Experts = bundles of Skills — layer 6), spec-13 knowledge layer (the
  document ingest + rule extraction of layer 4), ADR-0074 (operator-configurable platform services — the config
  surface of layer 7), ADR-0067 (service fees/consent — the payment part of layer 7), ADR-0045 (the solution
  runtime declaration `{roles, interactions, tasks, workflows, triggers, decisions}` — this ADR frames it as the
  serialised anatomy), ADR-0075 (contributions into the 15 shared apps — layer 8; and the self-contained-closure
  rule this authoring must satisfy). External anchor: **ontology-first / semantic-triple** domain modelling
  (subject·predicate·object), and the **document-to-model** extraction pattern (read the SOP, don't re-key it).

## Context

Two problems, one root.

**(1) "Solution" is under-defined.** ADR-0035 says a solution is a pinned member graph; ADR-0045 gives it a
runtime declaration; ADR-0075 gives it contributions and a closure rule. But there is no single statement of what
a solution *is* end-to-end — its full anatomy — so every new one is assembled ad-hoc, and authors (and the
Solution Architect agent) have no canonical shape to fill. The pieces exist; the whole does not.

**(2) Authoring is a long form in the wrong language.** New Project asks the author to fill many abstract fields
up front — schemas, nouns, layers — before they have a model in their head. But domain people don't think in
schemas; they think in **their current process, told as a story** ("this actor does this to this thing, then that
actor does that"), and they understand what they can *see* — a **form**, a **map** — not a schema. The form throws
their natural language away and asks them to speak the machine's.

The root of both: we have not written down (a) that a solution is a **layered decomposition of a domain** — the
anatomy — nor (b) that the anatomy is *internal*, and the author authors by **narrating a process and reviewing
the visible artifacts** it produces. Write both down, and authoring becomes "tell me your process → review the
forms/flows/maps → confirm," with the eight-layer graph generated underneath. A document the author already holds
becomes raw material the Expert mines to draft that process, not a form to re-key.

## Decision

### Part A — The Solution anatomy (eight layers)

A solution is the same eight layers, air to property-tax. Layer 1 is modelled first; it generates the vocabulary
every layer below consumes.

| # | Layer | Author starts from | Which yields | Platform construct |
|---|---|---|---|---|
| 1 | **Domain model** | subject·verb·object **interactions** | **nouns** (registries/schemas), **verbs** (interfaces), **roles** (actors) — the decomposition | ADR-0058 · ADR-0038 · governed roles |
| 2 | **Data sourcing** | satellite · sensor · external system · human-entered | **drivers** (declared egress/sources → L0 observations → L1 features) | ADR-0060 L0→L1 · ADR-0030 |
| 3 | **Derived insight** | spatial/temporal interpolation, hotspot & anomaly (threshold/outlier), **models** | **engines** → L2 cell-measures, L3 intelligence | ADR-0060 L2→L3 |
| 4 | **Knowledge → Rules** | uploaded **documents / guidelines** | **rules** extracted (`governance.rule`) with citations | spec-13 |
| 5 | **Decisions** | facts **+** rules | a **decision** → recommendation/outcome (AI never decides) | ADR-0029 / ADR-0046 |
| 6 | **Agents / Skills** | schedule-, event-triggered, or chat | **Experts** that emit recommendations / answer | INT-0002 |
| 7 | **Platform services & integrations** | the shared backend the solution *uses* | declared **config/bindings**: workflow, notifications, payment/fees, scheduler, storage, model-gateway, external connectors | ADR-0074 · ADR-0045 (workflows/tasks) · ADR-0067 (fees) |
| 8 | **Surfaces** | — | **contributions** into the 15 shared apps | ADR-0075 |

Two things this makes explicit that were implicit before:

- **Layer 1 generates the rest.** Modelling the interactions (S·V·O) *first* yields the governed nouns, verbs,
  and roles; layers 2–8 are then "what produces / consumes / decides on / renders these nouns." The domain
  decomposition is the authoring backbone, not an afterthought.
- **Layer 7 — platform services — is a first-class layer, not plumbing.** A solution *configures* shared
  services (a leave workflow on the workflow engine, who gets notified on a threshold breach, a service fee and
  its consent step, the storage backend for its artifacts, which model the chat agent uses, an external-system
  connector). These are declared (governed config, ADR-0074) and rendered/managed through the shared apps
  (Setup, Admin) — never bespoke per solution. This layer was missing from the earlier framing and completes it.

The solution declaration therefore serialises all eight layers (ADR-0045's fields + ADR-0075's `contributions` +
the member closure + a new `platform` block for layer 7), and the member graph is its **complete closure**
(ADR-0075 Rule 1). "Install" brings the whole anatomy.

### Part A′ — The substrate: a solution IS a set of component configurations

The eight layers are an **organizing lens**, not the representation. Reductively, a solution **is a set of
component configurations** — and nothing else:

- **ADR-0036:** a component *instance* = **component + config in a scope**. A solution is a **set of instances**.
- **ADR-0022:** *everything* is a component through the one certify spine — schemas, interfaces, roles, drivers,
  engines, skills, apps, even the solution itself. So even the layer-1 domain vocabulary is component-configs, not
  a special kind of thing.

So two truths hold together, and both are load-bearing:
- **Substrate (what a solution *is*):** a uniform set of `(component, config-in-scope)` tuples plus their wiring.
  This is what install fans out (ADR-0075 closure), what the declaration serialises, and what conformance
  validates.
- **Anatomy (how an author *thinks*):** the eight layers label each config by its role, so the author knows
  *which* configs a complete solution needs and Studio can show completeness ("layer 4 has no rule configs yet").

**"Config" is richer than env vars.** A member's config-in-scope is
`{component ref (pinned) · scope · env · secret references · assets · schedule · platform-service bindings (layer 7)
· contribution declarations (layer 8) · wiring — which members' outputs feed its inputs}`. The solution is the
**graph** of these configs; the anatomy just names each node's role. This is why authoring is uniform: for every
layer the Expert does the same thing — **select an existing component and fill its config (reuse), or propose a
new component to generate (gap).**

### Part B — Authoring: process-narrative in, form/viz-anchored review

The eight layers (Part A) are the **internal** structure. A domain author must **never be asked to fill them**.
Domain people do not think in layers, schemas, or "nouns and verbs"; they think in **their current process, told
as a story** — and they review what they can *see* (a form, a map), not a schema. Authoring is therefore
**process-in, artifact-out**: the author narrates (or uploads a document describing) their process; the Expert
drafts the *visible artifacts*; the author reviews those; the eight-layer machinery is generated underneath.

**B.1 — The elicitation order (how a domain user actually expresses a solution).** The Expert follows the order the
author is comfortable in, not the layer order:

1. **Why** — the purpose / goal. (Authors can always state this.)
2. **The process, as a story** — *"Actor 1 does action 1 to object 1 → then actor 2 does action 2 to object 2 →
   …"*. This narration **is** subject·verb·object; it yields the candidate roles, verbs, and objects (layer 1)
   *without the author ever naming a schema*.
3. **The things** — for each object/subject in the story: what attributes define it, which are **mandatory**, what
   type. The Expert **drafts** this; the author **reviews** it.
4. **Rules / validation** — what constrains each action and each attribute (layer 4; if a guideline document
   exists, this is *literally its content*, cited).
5. **Workflow** — how the object (or the **case** containing it) **flows** from actor to actor (layers → workflow).
6. **Decisions** — who decides what, on the basis of which guideline or data (layer 5 decision spine).

**B.2 — Two entry types, one spine (the unifying move).** Every solution begins with data *arriving*; the only
question the Expert asks first is **what feeds it**:

- **User-initiated** — the data source is a **person filling a form.** The author reviews the **form** (the
  artifact they understand best): its attributes, mandatory fields, types. *(grievance, service request, leave,
  expense — the case pattern.)*
- **Observation-initiated** — the data source is a **sensor / satellite / external feed.** The author reviews the
  **data source + its map/`viz.layer`**: what is sensed, over what area, how often. *(air quality, flood,
  crowd-safety — the L0→L4 pattern.)*

**A data source is either a *user* or *other data*** — a form is simply the human-shaped data source. This unifies
the two: after the entry point, **both flows converge on the identical spine — → rules/validation → workflow →
decision (on guideline or data).** Only the *first* review artifact differs by entry type (a **form** vs a **source
+ viz**); everything downstream is reviewed the same way. The entry point maps directly to the platform **trigger**
(a form-submit event vs a data-arrival/schedule event, ADR-0062/0063); the rest is the shared workflow + decision
spine (ADR-0045/0029/0046).

**B.3 — Documents are raw material, not a separate path.** When the author holds a scheme guideline / SOP / mandate,
the Expert ingests it (spec-13: original preserved, text derived, **cited**) and **mines it to draft the process
story, the object attributes, and especially the rules** — then the author reviews the *same* form/viz/flow
artifacts. Uploading a document and narrating aloud are two ways to **seed the same review**, not two products.

**B.4 — Reuse-first, everywhere (the extraction-quality safeguard).** Before proposing anything new — a noun, a
driver, an engine, a rule engine — the Expert searches the marketplace and **reuses** what exists (ADR-0044's
reuse-or-propose gate). Reuse is high-confidence and safe; generation is the exception, quarantined behind an
explicit gap that routes to a component developer. **Nothing enters the draft without a citation and a confidence;**
low-confidence extractions are **flagged, not silently accepted** (the no-synthetic-data discipline applied to the
authoring model itself). The author always reviews a *grounded proposal*, never a black box.

**B.5 — Generation underneath.** On confirmation, new nouns/verbs/roles go through spec governance (ADR-0038); new
members are generated by the **Component Developer** with the architecture baked in — broker-only I/O, declared
egress, governed schemas, `viz.layer` for map-able outputs, `prov`, layer-7 platform bindings, ADR-0075
`contributions` + self-contained closure. The solution is closure-validated and owned by the Studio project. The
author reviewed forms, flows, and maps; the eight-layer graph was written for them.

### Part C — What changes in the tools

- **New Project** opens with the entry-type question — "**Does a person start this, or does data?**" — then
  "**tell me the process, or upload the document that describes it**." The long form becomes the last-resort
  fallback, not the front door.
- **Solution Expert** drives the B.1 elicitation order (why → process story → objects/attributes → rules →
  workflow → decisions); ingests documents as raw material with citations; runs reuse-first search everywhere; and
  is layer-7 aware (proposes workflow/notification/payment/storage/model config, not just data + UI).
- **The author's review surfaces are the form and the map/viz, never a schema.** For user-initiated solutions the
  Expert renders the **form** to review; for observation-initiated ones, the **data source + `viz.layer`**. The
  generated schemas, workflow declaration, and decision spine sit behind those artifacts.
- **Component Developer** generates members that satisfy the full contract (conventions above), so generated
  drivers/engines/skills are self-contained and contribution-ready by construction.
- **Studio** keeps the eight-layer anatomy as an *internal* completeness view (for builders/stewards — "layer 4:
  no rules yet", "layer 7: notifications unconfigured"), while the domain author sees only forms, flows, and maps.

## Consequences

**Positive.** A canonical definition of a solution that authors, the Expert, and reviewers share; authoring that
starts from what people actually have (their process story, or a document describing it) and lets them review what
they can see (forms, flows, maps) instead of a schema; a single unified front for both entry types (person and
data); the architecture (L-ladder,
decision spine, governance, contributions, closure, platform-service config) **baked into generation** so new
solutions are correct-by-construction; and completeness made visible (the anatomy shows what's missing). Layer 7
finally makes platform-service configuration a declared, governed, first-class part of a solution rather than
manual post-install plumbing.

**Negative / accepted.** Document extraction is **imperfect** — the Expert proposes, the human confirms; every
proposal must carry a citation and be editable, and low-confidence extractions are flagged, not silently
accepted (no-synthetic-data discipline applies to the *model* too). The eight-layer declaration is **more to
specify** than a member list — mitigated because most layers are reuse (few net-new components) and the document
seeds most of it. Layer 7's config schema must span heterogeneous services (workflow vs payment vs storage)
without becoming a general-purpose language — start from the services that exist (ADR-0074 leaf services +
ADR-0045 workflows + ADR-0067 fees) and widen on real need.

**Rejected alternatives.** *(a) Keep the abstract long form* — asks the author to speak schemas/layers and
front-loads modelling in the machine's language. *(b) Ask the author to fill the eight layers directly* — the
layers are the *internal* structure; exposing them repeats (a) in new clothing. The author narrates a process and
reviews forms/flows/maps; the layers are generated underneath. *(c) Free-form "describe it" with no anatomy behind
it* — produces ungrounded, incomplete solutions; the eight-layer target + reuse-first + citations are what make the
Expert's output complete and reviewable. *(d) One entry type only* — modelling only forms (user-initiated) or only
data (observation-initiated) forces the other kind of solution into the wrong shape; unifying on **data-source =
user | other data** lets both share the rules → workflow → decision spine.

## Implementation slices

1. **This ADR** — the anatomy (internal) + process-first, form/viz-anchored authoring + the two unified entry types.
2. **Anatomy as a first-class object** — extend the solution declaration with the `platform` (layer 7) block and a
   serialised eight-layer view; Studio renders the *internal* anatomy with completeness indicators (for
   builders/stewards), not to the domain author.
3. **Process-first intake** — New Project asks the entry type (person / data), then drives the B.1 elicitation
   order; Solution Expert mines any uploaded document as raw material (cited); the author reviews the **form**
   (user-initiated) or **data source + viz** (observation-initiated), then the shared rules → workflow → decisions;
   reuse-first everywhere.
4. **Component Developer conventions** — generation templates that bake broker I/O, governed schemas, viz.layer,
   prov, layer-7 bindings, ADR-0075 contributions + closure.
5. **Layer-7 config schema + Setup/Admin rendering** — workflow / notifications / payment / storage / model
   bindings declared and managed through the shared apps.

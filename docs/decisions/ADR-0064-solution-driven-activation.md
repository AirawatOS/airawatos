# ADR-0064 — Solution-driven activation (Packs): install *and* activate a capability, composed in Studio

- **Status:** Proposed (2026-08-23)
- **Deciders:** Airawat (platform steward), product owner
- **Composes:** ADR-0035 (`solution` kind = pinned member-graph, one fan-out install; `extends` composition),
  ADR-0036 (component instances = component + config in a scope), ADR-0045 (solution declaration:
  roles/interactions/tasks/workflows/**triggers**), ADR-0050 (execution engine — the eventual home of
  long-running activation; **not required by this ADR**), ADR-0034 (Studio authoring: scaffold→test→certify→
  publish), ADR-0016/0022 (certify spine + per-tenant install-as-grant), ADR-0060 (City Digital Baseline / the
  L0–L4 layer ladder), ADR-0062 (one `invoke` verb; declared triggers reuse `platform.subscription`/`schedule`),
  ADR-0063 (govern the *shape*, not just the name — write-time conformance), ADR-0025 (signed schema catalog —
  where the solution manifest schema lives).

## Context

The City Digital Baseline works today, but the way it is delivered contradicts the platform's own thesis.

1. **City Setup is a hardcoded pipeline, not a governed artifact.** `app_host._run_city_baseline` carries a
   literal `STEPS = [("terrain", "ds:airawat:driver/terrain-dem", {}), ("heat", …), …]` — 13 layers, their
   order, and their per-run config (`MODE`, `OUTPUT_SCHEMA`, `METHOD`…) baked into reference-service code. Adding
   a flood layer means editing the OS, not publishing a component. The baseline is the one thing on the platform
   that did NOT come through the marketplace.

2. **A Solution installs but does not activate.** `component_install` already **fan-out installs** a bundle's
   `members` (it is how AI Experts pull their Skills, and how a `solution` pulls its components) — each member
   gets a tenant-scoped run-token + steward grant (install-as-grant). But installation stops there. A Solution
   has no way to say *"and then run these, in this order, with this config, and show me per-layer progress."*
   The **activation** half — the actual value of City Setup — has no governed representation.

3. **The marketplace fronts Components, but people want outcomes.** Nobody wants to assemble 13 drivers; they
   want "flood monitoring for my city." The unit of consumption should be the **Solution** (a Pack), not the
   raw component. ADR-0047 already names the three tiers (components → solutions → services); this ADR makes the
   **middle tier the default front door**.

The user's framing — *Base Pack, Flood Pack, Heat Pack, Mobility Pack, each installs the components that light
up its layers; Solutions take the marketplace front page; the Components app becomes a way to manage installed
Solutions* — is exactly ADR-0035 solutions **plus the missing activation half**. This ADR adds that half.

## Decision

### 0. The solution manifest is a GOVERNED SCHEMA — `platform.solution`, distinct from runnable components.

By ADR-0063's rule (*a governed schema is a governed shape, not just a governed name*), a solution declaration
is a written object and MUST conform to a published JSON-Schema, validated at certify via the same write-time
conformance the platform applies to every other object.

**Which schema — and why solutions get their own.** ADR-0022 ("everything-is-a-component") unifies the certify /
install / listing **spine (the lifecycle)**, NOT the manifest *shape*. The honest axis is **runnable vs
composition**:

- **`platform.component`** governs **runnable** kinds (`driver | engine | app | model | skill`) —
  kind-discriminated among those (shared identity leg + `if kind==X` conditional bodies: `entrypoint` for app,
  `scopes`/`egress` for driver, …). These have a runnable artifact and declare their own capabilities.
- **`platform.solution`** governs **compositions** — `members`, `extends`, and the `activation`/`setup` blocks
  below. A solution has **no artifact** (no entrypoint/code), its capabilities are the *union* of its members',
  and its `version` is a **lockfile** pinning member versions. Cramming that into the runnable-component union
  would be a lopsided `kind: solution` branch that turns the base off and a different shape on — a smell that
  says "separate schema." (`expert`, a bundle of Skills, is the sibling composition kind; solution + expert may
  later share a `platform.bundle` base — both "fan-out-install a member set".)

Both schemas ride the **same certify spine** and both project to the same **`marketplace.component`** listing
(identity: `component_id`, `kind`, `version`, `provider`) — that shared identity layer is where
"everything-is-a-component" actually lives. So: **unify at the spine + listing; split at the manifest body.**

**No problematic recursion.** "A component composed of components" is not schema self-embedding: `members` are
**references** (`component_id` strings), never an embedded `platform.component`. The composition *graph* can
recurse (a solution whose member is a solution), but that is a data graph bounded by two certify/install **house
rules** — **closure** (every referenced id resolves in the member/`extends` set) and **acyclicity** (no include
cycle) — the same rules `extends` already needs. Adding `activation` vocabulary is a change to `platform.solution`
through the spec loop (ADR-0038); the schema sits in the ADR-0025 signed catalog + the boot-minimal governed set.

```jsonc
{ "$id": "platform.solution", "required": ["component_id","kind","version","provider","members"],
  "properties": { "kind": {"const":"solution"}, "members": {"type":"array","items":{"$ref":"#/$defs/component_ref"}},
    "extends": {"type":"array","items":{"$ref":"#/$defs/component_ref"}},
    "activation": {"$ref":"#/$defs/activation"}, "setup": {"$ref":"#/$defs/setup"} } }
```

**Shape vs. cross-reference — only the shape is JSON-Schema.** `platform.solution` governs the *structure*
(`members`, `extends`, `activation.layers[*].{key,member,env,label}`, `setup.{secrets,assets}`). The *referential*
checks — every `activation.member` ∈ the member/`extends` closure; graph acyclic; every `env` key legal for that
member; declared `setup` names well-formed — remain certify **house rules** on top of the schema (the split
ADR-0063 draws). §4's certify runs both.

### 1. A Solution may declare an ACTIVATION PLAN — the ordered work that lights up its layers.

Extend the `solution` manifest (ADR-0035) with an optional `activation` block. It is the governed, portable
form of what `STEPS` hardcodes today:

```yaml
component_id: ds:airawat:solution/flood-pack
kind: solution
extends: [ds:airawat:solution/base-pack]        # dependency closure (ADR-0035) — Flood needs Base's terrain/buildings
members:                                          # the certified components this pack installs (fan-out today)
  - ds:airawat:driver/hydro-merit
  - ds:airawat:driver/sentinel1-flood
  - ds:airawat:engine/flow-balance
  - ds:airawat:engine/flood-exposure-join
setup:                                            # prerequisites the activator collects BEFORE running (reuses
  secrets: [GEE_SERVICE_ACCOUNT_KEY]              # City Setup's wizard: keys via the Connections/secrets flow,
  assets:  [{name: OSM_PBF, populates: OSM_PBF_FILE_ID, hint: "city OSM extract"}]   # files via /bridge/asset
activation:
  layers:                                         # ORDERED activation steps — the governed form of STEPS
    - { key: hydrology, member: ds:airawat:driver/hydro-merit, label: "Hydrology (rivers & flow)" }
    - { key: flood-obs, member: ds:airawat:driver/sentinel1-flood, label: "Observed flood (SAR)" }
    - { key: balance,   member: ds:airawat:engine/flow-balance, env: {DOMAIN: water} }
    - { key: risk,      member: ds:airawat:engine/flood-exposure-join, label: "Pluvial risk" }
```

Rules:
- `activation.layers[*].member` MUST be a `member` of this solution or of a solution it `extends` (composition
  conformance — ADR-0035 closure, extended from schema-graph to the activation graph). Certify enforces it.
- `env` per layer is the per-run config (what `STEPS` tuples carry today). No secret values here — only names,
  materialised at run by the runtime-manager (ADR-0062 / the `--env-file` path).
- Order is explicit and linear in v1 (matches the current scheduler, which has no DAG). A later slice may make
  it a real dependency DAG; the linear list is a valid degenerate DAG, so this is forward-compatible.

### 2. City Setup becomes the generic PACK ACTIVATOR — driven by the installed Solution, not by code.

Rename the capability from "City Setup" (baseline-specific) to **activate a Solution**. `_run_city_baseline`
generalises to `activate(solution_id, tenant)`:

1. **Install** the solution (fan-out its `members` + `extends` closure) — already built (`_install_one`).
2. **Collect setup** — for each `setup.secrets`/`setup.assets` not already satisfied, drive the SAME wizard City
   Setup uses today (GEE key via secrets, OSM via `/bridge/asset from_url`). No new UI — parameterised by the
   solution's `setup` block.
3. **Run the activation plan** — iterate `activation.layers` in order, per-tenant install-as-grant + scheduler
   `/run` with the layer's `env` — **the exact machinery City Setup already uses** (the install-as-grant loop,
   the scheduler runs, the per-layer progress panel, the timeout chain).
4. **Record** a governed `platform.activation_run` (or reuse `city.workspace` + the per-layer status list) so the
   panel and the marketplace can show progress + freshness.

The baseline is then just **Base Pack** — the current `STEPS` lifted verbatim into `base-pack`'s `activation`.
Zero behaviour change for the existing flow; the list simply moves from code to a published, certified Solution.

### 3. Packs compose; installing Flood pulls Base.

`extends` (ADR-0035) already models the dependency as a lockfile of members. The activator resolves the
`extends` closure before running, and **skips any layer whose outputs already exist + are fresh** (coverage-qa
already computes per-layer freshness — reuse it) so activating Flood on a city that already has Base does not
re-run Base's layers. Idempotent + resumable, per §2.4.

### 4. Studio composes a Solution and publishes it to the marketplace.

Studio already has the seam (ADR-0034; the `/bridge/project-compose` + `/bridge/project-publish` paths). Extend
it so a **Project → Solution** compose emits the `activation` + `setup` blocks, not just `members`:

- Studio lists the project's certified members, lets the author **order them into layers** and set each layer's
  `env` (a form, not code), pick `extends` parents, and declare `setup` prerequisites.
- **Compose** writes the `solution` meta (with `activation`) into the project.
- **Publish** runs the existing verified-certify → `store/publish` path with `kind: solution` — certify
  validates the manifest against the governed **`platform.solution`** schema (shape, §0) and then runs the
  **composition house rules** (every `activation.member` ∈ the member/`extends` closure; graph acyclic; every
  `env` key legal for that member; declared `setup` names well-formed). AI Solution-Expert assistance (INT-0003) proposes the
  layer ordering + reuse-vs-propose for missing components, confirm-gated.

A published Solution is a first-class marketplace listing that, on install, **installs and can activate** itself.

### 5. Marketplace fronts Solutions; the Components app becomes "Solutions".

- **Marketplace home = Solutions** (outcomes: "City Baseline", "Flood monitoring", "Heat & shade", "Mobility").
  Components move to a **"For builders / Studio"** shelf — still installable directly, just not the front door.
- The **Components app is renamed "Solutions"** and becomes the **installed-pack manager**: which packs are
  installed, each pack's **health** (fresh/stale/missing layers — straight from `coverage-qa`/`city.coverage`),
  drill into member components + their setup, **Activate / Re-activate / Uninstall** (fan-out uninstall).
  Component-level management stays available inside a pack for developers.
- Components do **not** disappear — they remain the atom Studio builds and certifies. This ADR changes the
  **default unit of consumption**, not the type system (ADR-0047's three tiers stand).

### 6. Activation is a governed, idempotent, resumable run with per-layer receipts.

Each activation step is an `invoke` (ADR-0062) of a certified member under its install-as-grant token; each
writes attributed rows (ADR-0052). The activation run records per-layer status/count/error (the panel you see
today) as a governed `platform.activation_run` so it is queryable, resumable after failure, and re-entrant
(re-activate only stale/failed layers). This is deliberately a **thin sequencer**, NOT the ADR-0050 execution
engine — see Non-goals.

## Consequences

- **The baseline stops being special.** Every capability — including the L1 baseline — is a published, certified
  Solution. Adding "flood" to a city is publishing/installing Flood Pack, not editing the OS.
- **One activation path, many packs.** Base/Flood/Heat/Mobility differ only by their `activation` metas; the
  runner, install-as-grant, scheduler, progress panel, and prereq wizard are shared.
- **Studio closes the loop.** A domain team composes a Pack from certified components and publishes it —
  self-serve, governed, no core change. This is the ADR-0035/0034 north-star made concrete for city capabilities.
- **The marketplace tells the truth to buyers.** People shop outcomes; the installed-pack manager shows whether
  each outcome's data is actually fresh (coverage-qa), not just "installed".
- **Migration is additive.** `STEPS` → `base-pack.activation` is a lift-and-shift; the reference runner reads the
  solution instead of the literal. Existing tenants keep working; the code path is the same minus the hardcoding.
- **Cost:** certify gains an activation-conformance check; Studio gains a compose form; the runner gains a
  solution reader + a `platform.activation_run` record. All are small deltas over machinery that already exists.

## Slice plan (each step is shippable; schema/interface proposals are approval gates)

1. **Govern the artifacts** — propose the **`platform.solution`** manifest schema (members/extends/`activation`/
   `setup`) and **`platform.activation_run`** (per-layer status) through the spec loop; wire certify to validate a
   submitted solution against `platform.solution` (shape) + the closure/acyclicity/env house rules (§0). *(approval gate)*
2. **Base Pack** — author `ds:airawat:solution/base-pack` with `activation.layers` = today's `STEPS`; publish it.
3. **Solution-driven runner** — generalise `_run_city_baseline` to `activate(solution_id, tenant)` reading the
   installed solution's `activation`; verify Base Pack reproduces the current baseline byte-for-byte on a fresh
   test tenant.
4. **Flood Pack** — author `flood-pack` (`extends: base-pack`) as the second pack; prove `extends` closure +
   skip-if-fresh + prereq collection. Heat/Mobility follow as pure authoring.
5. **Studio compose→publish** — the Project→Solution compose emits `activation`; certify enforces
   activation-conformance; AI Solution-Expert proposes the ordering (confirm-gated).
6. **Marketplace + app rename** — Solutions on the home shelf; Components app → "Solutions" (installed-pack
   manager with coverage-qa health, Activate/Re-activate/Uninstall).

## Non-goals

- **Not the full ADR-0050 execution engine.** v1 activation is a thin, linear, resumable sequencer over the
  existing scheduler — no server-side interpreter, no long-lived case/workflow state machine. When ADR-0050
  lands, a Solution's `activation` becomes a declaration it runs; the `activation` block is authored to be
  forward-compatible with that (ordered steps = a degenerate workflow).
- **Not removing Components.** Components remain the certified atom; only the *default surface* changes.
- **Not a DAG scheduler (yet).** Linear order in v1 (matching the scheduler's current model); a real dependency
  DAG is a later slice and the linear list is a valid subset.
- **Not auto-activation on install.** Install and activate stay distinct verbs — installing a Pack makes it
  available; activation (which spends compute + external quota) is an explicit, confirm-gated action.

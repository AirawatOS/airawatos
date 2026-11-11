# ADR-0075 — Solutions contribute into shared apps; installing is self-contained; Setup is unified

- **Status:** Proposed (2026-09-06)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0035 (a `solution` = a pinned member graph installed by one fan-out — this ADR
  makes that graph the **complete dependency closure** and adds a **contributions** block), ADR-0045 (the solution
  runtime declaration `{roles, interactions, tasks, workflows, triggers, decisions}` — `contributions` is the new
  peer field), ADR-0022 (everything-is-a-component — the shared apps and the solutions that extend them are all
  components), ADR-0036 (component *instance* = component + config in scope — a contribution is rendered per
  install scope), ADR-0048 (the universal Inbox — one of the shared surfaces), the **City Scan viz.layer
  discovery** already in production (the working proof this ADR generalises — City Scan renders *any* solution's
  `viz.layer` with no City-Scan change), the **onboarding-composition** note (packs declaring `default_apps` +
  wizard — this ADR generalises that from packs to every solution), ADR-0074 (operator-configurable platform
  services — the same "governed config the right app already renders" instinct, one tier up). External anchor:
  the editor/IDE **extension-contribution model** (extensions declare contribution points; the host renders
  them) and the **plugin registry** pattern — the host never grows a new window per plugin.

## Context

The platform is accumulating **one app per vertical**. Air Intelligence got `air-explorer` and — as of this
week — `air-admin`. Flood, heat, crowd-safety, property-tax each trend the same way. Two failures follow:

1. **Adoption tax.** A user who learns City Scan, Inbox, Data, and Components then has to learn *another* console
   for every domain. The apps do the same *kinds* of things (show a map layer, route a task, set up a pipeline)
   but wear different clothes, so nothing transfers. Onboarding cost scales with the number of verticals.

2. **Hidden prerequisites.** Air Intelligence silently assumes City Scan and the baseline layers
   (buildings/roads/population/terrain…) already exist — they come from a *separate* City Setup flow. Install the
   Air Intelligence solution into a fresh city and it is quietly broken: the model has no per-cell features to
   join. The dependency is real but undeclared, so "install" does not mean "ready."

Both are the same mistake in two guises: **treating a vertical as a silo instead of a set of contributions to
shared surfaces.** And we already have the counter-example that proves the better way works in production: **City
Scan discovers and renders any solution's `viz.layer` descriptors with zero City-Scan code change.** A new
domain's layers just appear. That single pattern, generalised, dissolves both problems.

## Decision

Adopt one principle with two enforced rules and one contract.

> **Apps are shared surfaces. Solutions contribute *into* them. Installing a solution adds features to the same
> apps — it never adds a new app, and it never assumes anything it did not bring.**

### Rule 1 — Self-contained install (the complete-closure rule)

A `solution`'s member graph MUST be its **complete dependency closure** — every component it needs to function,
including the baseline-layer drivers it joins against. Install is a **fan-out over the closure, idempotent**: a
member already installed in the scope is skipped (not reinstalled, not duplicated); a missing one is installed.

- "Install the solution" ⇒ "the solution is ready," with no separate prerequisite the operator had to know about.
- Shared *infrastructure* (City Scan, Inbox, the registry) is not a solution member — it is always present. What
  a solution must declare is its **data/compute dependencies** (the drivers that produce the layers it reads, the
  engines it runs), not the shared apps that render its output.
- Closure is validated at publish (conformance): a solution that reads `cell.buildings` but includes no member
  that writes it is **incomplete** and the certificate is withheld — the same way ungoverned vocabulary is
  withheld today. Undeclared prerequisites become a publish-time error, not a runtime surprise.

### Rule 2 — No new app per vertical

A vertical does NOT ship its own console. It ships **contributions** to the existing shared apps. New apps are
added only when a genuinely new *interaction surface* is needed (rare, and itself reusable across verticals),
never as the home for one domain's controls.

### The contract — `contributions` + registry-driven renderers

Extend the solution declaration (ADR-0045) with a **`contributions`** block. Each key targets one shared surface;
the value is a declarative descriptor the surface knows how to render. The shared app is a **registry-driven
renderer**: at load it discovers the installed solutions' contributions for its surface and renders them — exactly
as City Scan already does for `layers`.

| Contribution | Rendered by (shared app) | Descriptor (what the solution declares) | Today |
|---|---|---|---|
| `setup` | **Setup** (unified) | ordered steps: required secrets/keys, assets, AOI requirement, `run` steps, `schedule`s, readiness probes | build |
| `layers` | **Visualize** *(renamed from City Scan)* | `viz.layer` refs (group/subgroup/interpretation) | ✅ in prod |
| `inbox` | **Inbox** | item types + actions the domain routes | partial (ADR-0048) |
| `data` | **Data** | schemas + attribution to surface for browsing | partial |
| `components` | **Components** | drivers/engines + their keys/assets to manage | ✅ mostly |
| `agent` | **Chat** (AI agent) | the domain **Expert** (INT-0002 bundle of Skills) the assistant can call | partial |
| `knowledge` | **Knowledge** | governed documents / guidelines + `governance.rule` sets (spec-13 corpora, citation contract) | partial |
| `audit` | **Audit** | receipts + decided change-requests + attributed writes the domain emits (ADR-0058/0056/0052) | partial |
| `appeals` | **Appeals** | which of the domain's decisions are contestable → contest/redecide (ADR-0029 decision spine) | partial |
| `files` | **Files** | the domain's content-addressed filestore artifacts (uploaded assets, documents, model blobs, corpora) | partial |
| `wallet` | **Wallet** | Verifiable Credentials the domain issues → the holder's Document Wallet (ADR-0049) | partial |
| `dashboard` | **Dashboard** | KPI tiles / summary widgets over the domain's governed data | partial |
| `reports` | **Reports** | report definitions the domain contributes → governed, exportable reports | partial |
| `marketplace` | **Marketplace** (Storefront) | the solution's published listing — discovery + one-click install (ADR-0016) | ✅ mostly |
| `admin` | **Admin** | the roles / app-access / config the domain needs the tenant admin to manage (ADR-0011/0026/0028) | ✅ mostly |

**Naming.** Shared surfaces are named for the *capability*, not a domain or an occasion — the map surface is
**Visualize** (renamed from *City Scan*: its job is to visualize any solution's layers, not scan one city). A
surface name that reads as domain- or city-specific is itself a smell that it will be mistaken for a silo.

Contract invariants:
- **The renderer is domain-agnostic.** It ships knowing the *descriptor shape*, never a domain. Adding air /
  flood / heat / property-tax adds zero renderer code — only solution declarations. (City Scan is the reference:
  it renders `air.*`, `risk.flood`, `waste.*`, `cell.crowd_density` layers by discovery, not by hardcoding.)
- **Discovery is scoped + governed.** A renderer shows a contribution only if the tenant has that solution
  installed (the `has(schema)`/installed-check City Scan already uses), so baseline tenants never see empty
  domain features.
- **Actions ride the existing governed bridges.** A `setup` step is `/bridge/install · /bridge/secret ·
  /bridge/run · /bridge/schedule` — the renderer composes calls; it holds no domain logic and no elevated power
  beyond the signed-in user's.
- **Contributions are data, not code.** They live in the solution declaration (governed, versioned, signed at
  publish), so what a domain adds to the shared apps is auditable and reproducible.

### Unified Setup — the first and hardest renderer

Replace per-domain setup apps (`City Setup`, the just-built `air-admin`) with ONE **Setup** app that renders each
installed solution's `setup` contribution and drives it. A `setup` descriptor is an ordered list of steps, each of
a known kind:

- `install-closure` — fan-out install the solution's members (Rule 1), idempotent.
- `secret` — a key the tenant must provide (name + hint; the operator enters it; never shown back — the standing
  "reference, never contain" rule, ADR-0074/ADR-0027). The Setup app collects it and calls `/bridge/secret`.
- `asset` — a data file the tenant uploads (e.g. an OSM PBF), via `/bridge/asset`.
- `aoi` — the solution needs an AOI at a resolution; Setup checks/prompts.
- `run` — invoke a member with config (`/bridge/run` with env), showing the result.
- `schedule` — put a member on a cron (`/bridge/schedule` with env).
- `probe` — a readiness check (a `has(schema)`/count query) that gates or greens a step.

Setup renders these per installed solution, shows readiness at a glance, and is the *same* console whether the
operator is standing up flood, heat, air, or property-tax.

### Worked migration — Air Intelligence

The concrete first cut (and the correction of this week's misstep):
1. **Make `solution/air-intelligence` self-contained** — add the baseline-layer drivers (buildings/roads/
   population/terrain/land-cover) to its member graph so install brings the full closure (Rule 1).
2. **Move `air-admin`'s 7 steps into the solution's `setup` contribution** — install-closure → keys → ingest →
   corpus → gated train → snapshot+infer → schedules. Deprecate the standalone `air-admin` app.
3. **The layers already contribute** to City Scan (`air.quality`, `air.sensor_reading`, `cell.cams`, `cell.aod`)
   — nothing to change there; it is the pattern being generalised.
4. Retrofit **City Setup** into the unified Setup as another set of `setup` contributions (the baseline solution).

## Consequences

**Positive.** One set of apps to learn; every vertical behaves identically, so adoption cost stops scaling with
the number of domains. "Install" means "ready" — no hidden prerequisites (closure enforced at publish). New
verticals ship *declarations*, not new UIs, so the platform's surface area stays flat as its capability grows.
The model is already proven (City Scan) — this is generalisation, not invention. Contributions are governed,
versioned, and signed, so what a domain adds is auditable.

**Negative / accepted.** The shared apps become **contribution renderers** — a more general (and initially more
complex) job than a bespoke screen; the descriptor schemas must be expressive enough for real domains without
becoming a general-purpose UI language (accepted: start narrow — `setup` first — and widen only on real need).
Closure validation at publish can make a solution **harder to publish** (it must declare producers for everything
it reads) — accepted, because that is precisely the hidden-prerequisite bug moved to where it is cheap to fix.
Some genuinely novel interaction may still need a *new* shared app — accepted, with the bar that it must be
domain-agnostic and reusable, never a one-vertical console.

**Rejected alternatives.** *(a) One app per vertical (status quo)* — the adoption tax and silo drift this ADR
exists to stop. *(b) A single mega-app with a tab per domain* — same silo, one window; tabs don't compose and the
app grows unboundedly. *(c) Keep setup per-solution but share only the map* — half-measure; the operator still
learns N setup flows, and the hidden-prerequisite bug remains. *(d) Bundle the shared apps *into* each solution's
closure* — inverts ownership (every solution would ship City Scan) and multiplies copies; shared infrastructure
is present by the platform, contributed *to*, not owned by each solution.

## Implementation slices

1. **This ADR** — the principle, the two rules, the contribution/renderer contract.
2. **`setup` contribution schema** (governed) + the unified **Setup** app as its renderer, driving the existing
   bridges; migrate `air-admin`'s steps into the Air Intelligence solution's `setup` declaration and deprecate the
   standalone app.
3. **Self-contained closure** for `solution/air-intelligence` (add baseline drivers) + publish-time closure
   validation in conformance.
4. **Retrofit City Setup** into unified Setup; then widen to `inbox` / `data` contributions so those apps become
   renderers on the same contract.

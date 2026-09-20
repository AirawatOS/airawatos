# ADR-0092 — Unified Settings & the Component Configuration Model

**Status:** Proposed
**Date:** 2026-09-18
**Supersedes/absorbs surfaces from:** ADR-0027 (component contracts / Setup & Keys), ADR-0075 (unified Setup), the City-Setup OSM/GEE flow, and the Connections/Components apps.

---

## Context

A tenant admin trying to configure an installed driver (`osm-transit`, needing its OSM PBF bound so it reads locally instead of hitting flaky Overpass) could not find *anywhere* in the UI to set that value. Chasing it exposed a structural problem, not a one-off:

### 1. Configuration is scattered across many overlapping apps

The OS shell (`platform-spec/reference/desktop.html`) has **no settings home** — it renders installed apps as tiles from `/apps`, and the profile menu holds only Theme / Language / Sign-out. "Configuring a component" is split across separate tile-apps with **inconsistent, overlapping capability**:

| App | What it configures | Gap |
|---|---|---|
| **Marketplace** (storefront) | install / uninstall only | no config at all |
| **Connections** | API keys **+ data-file asset uploads** (generic, any component declaring `assets[]`) | the only place generic assets can be set — but easy to miss |
| **Components** | API keys + schedules + run logs | **no asset/config UI**, even though *Setup* tells users to configure assets "here" |
| **Setup** (ADR-0075) | orchestrates a solution's `platform.setup` steps | the `asset` step is a **pointer** ("upload in Components → Settings") to a screen that can't do it |
| **City Setup** | AOI + OSM PBF + GEE key, auto-binds PBF to OSM drivers | OSM-specific; bind loop runs only *during* the wizard |
| **Org Setup / Admin** | org data / users↔roles | (governed data, not component config) |

The same intent — *configure this component* — has four partial homes, none complete. A value declared by a component can therefore have **no reachable home** in any of them.

### 2. The field-kind → store rule exists, but only 2 of 3 kinds have a home

Good news first: the secret-vs-not boundary **is already declarative** in each component's `meta.yaml`:

- fields under **`secrets:`** → **Vault** (`secret/<tenant>/<component>/<name>`), injected by the broker into outbound calls, never handed to the driver as plaintext;
- fields under **`assets:`** (`kind` + `populates`) → **`platform.component_asset`** registry bindings (blob in filestore), read at run time by `scheduler.py` → `env[a["populates"]] = a["file_id"]`;
- fields under **`config:`** → **declared but orphaned**: `/bridge/connections` reads only `secrets` and `assets` from meta, **never `config`**. So a plain scalar/reference config value has **no store and no UI**.

That third gap is exactly why `OSM_PBF_FILE_ID` had no field: it's declared as both `config:` (orphaned) and an `assets[]` binding (which only City Setup/Connections set).

### 3. Binding is manual and surface-bound, so post-setup installs are orphaned

Marketplace **install does not auto-bind** `assets[].populates`. The "one tenant PBF feeds many drivers" reuse is done **client-side in City Setup** (upload once, loop `bind` to the other OSM drivers). Any component installed *after* City Setup ran — like `osm-transit` — is never in that loop, so it silently falls back to its remote source and fails. This is a general defect, not specific to transit.

### 4. No declarative guarantee about what is a secret

Because only fields routed through the `secrets:`/Vault path are protected, a sensitive value a developer happens to route elsewhere (a connection client-secret, a token in a `config:`/registry record) lands in **plaintext**. "Secrets live in Vault" is a convention, not an enforced property of the field.

---

## Decision

Adopt **one configuration model** and **one two-tier Settings surface**, and make install honor bindings.

### A. One Component Configuration Contract (typed field kinds)

Every component declares a single, typed config contract in its `meta.yaml`. Each field has a **`kind`** that *deterministically* selects the store — collapsing today's `secrets:`/`assets:`/`config:` split into one list:

| `kind` | Meaning | Store (enforced by kind) |
|---|---|---|
| `secret` | credential / API key / token | **Vault** only |
| `asset` | a data file (e.g. OSM PBF) | filestore + `platform.component_asset` binding |
| `value` | a scalar / enum / typed literal | governed **`platform.component_config`** record *(new — closes the orphan gap)* |
| `reference` | a pointer to governed data or another component (e.g. an AOI, another component's output) | `platform.component_config` (stores the ref, resolved at run time) |
| `schedule` | cron/timezone/enabled | existing schedule store |

**The Vault rule becomes a property of the field, not a convention:** *only* `kind: secret` fields are eligible for Vault, and *every* `secret` field must go to Vault — validated at certify time. Anything not declared `secret` is, by construction, non-secret and governed in the clear. This directly answers "secrets should be special settings stored in the Vault — not everything."

### B. One generic renderer, one Settings app — a two-tier split (iOS-style)

Configuration lives in **Settings**, promoted from the profile menu into a first-class surface, in **two tiers**:

1. **Personal Settings** (every user): theme, language, notifications, personal defaults. Backed by the existing identity user record (`locale`, `theme`). This is the "iOS Settings" the profile menu hints at today.
2. **Admin / Component Settings** (tenant admin): **the single home for every installed component's config contract**, grouped by category — *Data Sources · Connections · Apps · Engines · Solutions*. A **generic renderer** (the pattern Connections already uses for `secrets`+`assets`, extended to `value`+`reference`) draws the form from the declared contract, so **every field kind has exactly one home**. No more "config has no UI".

### C. Consolidation map (what each existing surface becomes)

- **Marketplace** → stays *discover + install only*. Clean separation: Marketplace is the store, Settings is where you configure what you installed.
- **Connections** → becomes the **Connections category inside Settings** (external-system credentials + endpoints). No longer a separate app; its generic secret/asset renderer becomes *the* renderer.
- **Components** → its config responsibilities move into Settings; the ops view (reads/writes/egress/logs/schedules) remains as a **component detail** panel reached from Settings.
- **Setup (ADR-0075)** → becomes Settings' **guided-flow engine**. It already reads `platform.setup` contracts; because Settings now hosts *every* field kind, its `asset` step stops "pointing elsewhere" and configures inline.
- **City Setup** → stays as a **domain onboarding wizard** (AOI + OSM + GEE) but writes **through the shared config contract**, and its bespoke client-side bind loop is replaced by shared **install auto-bind** (below). It composes Settings writes; it doesn't own a private path.
- **Org Setup / Admin** → unchanged (governed org data / users↔roles), linked from Settings for discoverability.

### D. Install auto-binds `assets[].populates`

At install (and re-install/upgrade), the platform **auto-binds** each `asset` field to an existing same-`kind` asset in the tenant when one exists (e.g. reuse the tenant's single OSM PBF for every OSM driver). This makes post-setup installs correct by default and eliminates the "installed after City Setup → orphaned" class of bug. Manual override remains available in Settings.

### E. Solutions & shared configuration (set once, fan out)

A solution is a pinned member graph (ADR-0035/0036); installing it fans out to many components — City Setup provisions the ~19-member **City Baseline** solution. Users must **not** configure members one by one. Three mechanisms handle multi-component config:

1. **Shared fields, set once.** A solution declares that certain fields are *shared* across members — the AOI, the OSM PBF, the GEE key. The user sets each **once at solution scope**, and it fans out to every member declaring a matching field `kind`. This builds on ADR-0036's solution-scoped `context` layered over member `config`, plus install auto-bind (§D): one PBF binds to roads + facilities + transit + drainage — and to any member added *later*.
2. **Scope precedence (resolution rule).** A field's effective value resolves **tenant default → solution context → explicit member override** — most specific wins. So a shared PBF flows to all members, but a single member can still be pointed at a different file without disturbing the rest.
3. **Settings groups by solution.** A solution is a top-level group; opening it shows its **guided setup flow** (the wizard) or an **aggregated, de-duplicated** field view (shared fields once; member-specific fields under their component). Drilling into an individual member is possible but rarely needed.

**City Setup becomes the City-Baseline solution's setup flow** — it writes shared fields *through* the contract and relies on the shared auto-bind for fan-out, instead of its current bespoke client-side bind loop.

### F. Observability — run activity & notifications

Configuration (Settings) and *observation* are different concerns. A model that can **schedule** components must give a durable way to **watch** them. Today this is weak: run history is effectively in-memory (a scheduler restart read osm-transit's history back as zero and left a stuck in-memory lock), there is no cross-component "what's running now" view, and no completion signal — a failed 3am run surfaces nowhere until someone looks. The redesign adds a first-class **Activity** surface alongside Settings:

- **Cross-tenant Activity / Runs view** — one place listing every scheduled, running, and recent job across components: status, started/duration, next scheduled time, and click-through to the **live log stream** of anything in flight.
- **Per-component run history** in the component-detail panel (the ops view carried over from today's Components app): schedule, last N runs, each with its run log + egress log.
- **Durable, governed run records** — runs become persisted, bitemporal `platform.run`/job records, not in-memory, so history survives restarts and is auditable.
- **Notifications on scheduled outcomes** — success/failure posts to the notification/inbox spine; a **failure becomes an actionable inbox item** ("osm-transit run failed — source unbound").

**Settings = configure · Activity = observe · Inbox = get told when something needs you.**

---

## Consequences

**Positive**
- One mental model: *install in Marketplace → configure in Settings*. The Marketplace/Connections/Components/Setup/City-Setup confusion collapses to Marketplace + Settings (+ domain wizards that feed Settings).
- The secret boundary is enforced, declarative, and auditable: `kind: secret` ⇒ Vault, checked at certify; nothing sensitive lands in plaintext by omission.
- Every declared field has exactly one store and one UI — the `config:` orphan gap closes; `osm-transit`-style "no field anywhere" cannot recur.
- Auto-bind fixes a whole class of post-install failures.

**Costs / risks**
- New `platform.component_config` schema + a certify-time validator; a migration to fold existing `secrets:`/`assets:`/`config:` metas into the unified contract (can be mechanical, with back-compat shims so un-migrated components still work).
- Settings app is net-new UI; Connections/Components are refactored, not deleted, to avoid breaking deep links.
- Auto-bind must be conservative (match by `kind` + explicit opt-in via `populates`) to avoid binding the wrong asset.

**Migration (proposed slices, for later approval — this ADR is design-only)**
1. `platform.component_config` schema + certify-time secret/kind validator.
2. Unified contract loader in `app_host.py` (reads new contract; shims old `secrets/assets/config`).
3. Generic renderer extended to `value`/`reference`; stand up the **Settings** app shell (Personal + Admin tiers).
4. Install auto-bind for `assets[].populates`.
5. Re-home Connections/Components/Setup into Settings; City Setup writes through the contract.

---

## Immediate tactical note (not part of the model)

The `osm-transit` PBF can be bound **today** via the existing **Connections** app (generic asset uploader — it lists any component declaring `assets[]`) or by re-running **City Setup**'s OSM step. This is the correct current-state path; it does not require the redesign and does not need a secret hack.

---

## Refresh — 2026-09-20 (extends the model to solution-shipped config & the three-time flow)

The original decision (above) models **tenant-supplied** config: secrets, assets, values a *tenant admin fills in*. The ADR-0091/0097 lifecycle work since then surfaced a second, equally important half the original missed: **solution-shipped** config — the `platform.lifecycle` declaration, its rulesets, its ward/org scope tree, its default role assignments. Today a developer must hand-write these governed records into every tenant after install (proven painfully while migrating grievance/court/project onto the generic `lifecycle-engine`). That is the same "no reachable home" defect as `OSM_PBF_FILE_ID`, one layer up: the config item is authored by the **developer**, not the admin, and must be **materialised at install**, not typed into a form. This refresh folds that in.

### G. A sixth field kind: `contribution` (governed data the solution SHIPS)

Add to the contract table (§A):

| `kind` | Meaning | Store / lifecycle |
|---|---|---|
| `contribution` | a **governed record the solution ships** — a `platform.lifecycle` declaration, a `governance.policy_rule` ruleset, a scope/reference tree, seed `ref.*` rows | authored once in Studio; **written into the tenant at install** (id re-scoped to the tenant); its *tunable* leaves (a threshold in a rule, a route role) may be re-exposed as `value`/`reference` fields for the admin |

A `contribution` is **author-time data with an install-time write and a config-time tail**. It is distinct from `value` (a scalar the *admin* supplies) — a `contribution` is supplied by the *developer* and only its declared-tunable parts reach Settings. This is the ADR-0075 "contributions block" made typed and first-class in the config contract, and it is the missing home for the lifecycle declaration.

### H. The three *times* (who configures what, when)

The original ADR conflated authoring and administration under "Settings". Separate them explicitly — the same config contract is touched at three moments by three actors:

| Time | Actor | Surface | Does |
|---|---|---|---|
| **Author** | developer | **Solution Studio** | declares the contract + `contribution` records (lifecycle/rulesets/scopes) with types + defaults; ships them with the solution |
| **Install** | automatic | install fan-out (§D + §I) | materialises `contribution`s into the tenant, auto-binds `asset`s, seeds defaults, creates role placeholders |
| **Configure** | tenant admin | **Settings** (§B) | fills `secret`/`value`/`reference`/`schedule` fields and the tunable leaves of contributions |

**Studio authors the contract; install bridges it; Settings fills it.** These are three surfaces, not one — do not merge Studio into Settings.

### I. Install materialises contributions (extends §D)

§D auto-binds `asset`s. Extend install to also **write every `contribution` record into the target tenant**, tenant-scoping its id (`ds:<solution-steward>:…` → `ds:<tenant>:…`) and stamping `tenant`. Idempotent (re-install/upgrade overwrites by id). This is the concrete unblock: a grievance/court/project solution installs *and its workflow runs*, with no hand-authored `platform.lifecycle` write. Ordering: schemas/roles present (member grants) → contributions written → assets bound → guided-flow prompts for the remaining admin-supplied fields.

### J. Naming: **Solution Studio** (author) + **Settings** (admin); retire "Service Studio"

A **service is one kind of solution** (ADR-0047: a solution that also exposes a `service.offering` discovery envelope). Air Intelligence, Court, grievance are all solutions; only some are services. Therefore:

- The developer build surface is **Solution Studio** — it authors *any* solution (schemas, engines, apps, **and the config contract incl. `contribution`s**). **"Service Studio" folds into it** (ADR-0097 already calls for generalising Service Studio into the one workflow/solution authoring studio — this names the result).
- The admin config surface is **Settings** (§B). Distinct persona, distinct time.

### Consequences of the refresh
- The lifecycle declaration (and its rulesets + `route.scope` tree + default role grants) becomes a **shipped, installable `contribution`** — closing the gap the ADR-0091/0097 work exposed, exactly as `platform.component_config` closed the `value` gap.
- Install becomes the single place solution config is applied — governed records included, not just asset bindings.
- One authoring surface (Solution Studio) and one config surface (Settings), cleanly split by persona/time; "Service Studio" as a separate app disappears.

### Migration addendum (appended to the slice list)
6. `contribution` kind in the contract + a solution `contributions[]` manifest (or a `platform.solution_contribution` record set).
7. **Install-time materialisation** — `/bridge/install` writes contributed governed records into the tenant (tenant-scoped, idempotent). *(This refresh's first prototype.)*
8. Studio authors `contribution`s (the workflow-authoring surface, ADR-0097 C4) + rename Service Studio → Solution Studio.
9. Re-expose contribution tunables (rule thresholds, route roles) as `value`/`reference` fields in Settings.

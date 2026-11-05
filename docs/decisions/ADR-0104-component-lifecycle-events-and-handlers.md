# ADR-0104 — Component lifecycle events & handlers (one declared-handler model)

Status: Accepted — **S1, S2, S5 shipped** (S1: declared `subscribes:` auto-wired into a governed `platform.subscription` at install; S2: `on_configure` fires on a typed-config write; S5: `on_uninstall` fires before grant-revoke; `on_install` also fires from the install flow — all via the generic host helper `_run_lifecycle`, dispatching a declared handler in the component's confined ctx). **S4 (`on_upgrade`) is built in the helper but has no trigger until the ADR-0098 admin-gated upgrade endpoint lands.** S3 (`on_setup` guided form) + S6 (Studio surface + certify conformance) remain Proposed.
Date: 2026-09-22
Related: [[ADR-0089]] (event/message spine — the data-event half of this model), [[ADR-0092]] (unified Settings + typed config contract + the developer/admin/user split), [[ADR-0093]] (component delivery — materialize-on-install), [[ADR-0095]] (runtime lifecycle), [[ADR-0098]] (versioned install + admin-gated upgrades), [[ADR-0075]] (solution contributions + unified Setup), [[ADR-0058]] (interfaces as governed verbs), [[ADR-0090]] (verb→endpoint bindings), [[ADR-0030]] (broker + the engine handler model), the governed `platform.verb_binding` (#268), the runtime auditor (#69).

## Context

A component has a **lifecycle** — it is built, certified, published, installed into a tenant, set up, configured, run, upgraded, and eventually uninstalled — and each stage is performed by a **different actor** (developer, tenant admin, user). Today that lifecycle is **real but implicit**: the platform performs each stage through a *separate, ad-hoc mechanism*, and a developer who wants to hook into any of them must learn a different seam each time. There is no uniform "here is where your code runs when X happens."

What exists today, confirmed by reading `platform-spec/reference/app_host.py`:

- **Install** materializes a solution's shipped records — `_materialize_contributions(solution_id, tenant, token)` (app_host.py:4563, ADR-0092 §I) writes a `__contributions__` asset's records into the tenant, rewriting `$tenant`. Separately, `_ensure_component_install` (app_host.py:2359) registers a per-tenant install-as-grant and mints the scheduler's run-token — exposed to engines as the `ensure_install` capability (app_host.py:2345); `payroll-engine` calls `ctx["ensure_install"]` to self-provision.
- **Setup** (guided prereqs — API keys, an area-of-interest, a data file) is a **bespoke `city-setup` script** with its own status endpoints (#114), hand-written per solution.
- **Configure** writes typed config via `_bridge_settings_set` (app_host.py:4706, ADR-0092) — but **nothing tells the component** its config changed; there is no callback.
- **Run** is either a scheduled `main()` (e.g. `decision-router`, `payroll-engine`) fired by `platform.schedule`, or a governed verb dispatched into the engine's `HANDLERS` dict (verb → function). Publish already **self-registers** each verb as a `platform.verb_binding` (`_register_verb_bindings`, #268) — the one place the "declare it in meta, the platform wires it" pattern already works.
- **React to data** is the [[ADR-0089]] spine: a registry write emits `platform.event`; the automation dispatcher matches `platform.subscription` (WHEN) and fires a governed verb (THEN). Proven end-to-end (the Air Intelligence recommendation→action loop; `decision.route` governed + bound).
- **Upgrade** is admin-gated re-install ([[ADR-0098]]) with **no migration hook** — a new version cannot run a data migration against the old version's records.
- **Uninstall** revokes grants (`/v1/grants/revoke-for`) / unshelfs the app (the Marketplace uninstall flow) with **no cleanup hook** — a component cannot tombstone or archive what it created.

So the component lifecycle is **five different mechanisms** (contributions asset, `ensure_install` capability, the config write, the setup script, `main()`) plus the data-event spine — each learned separately. And the **actor split** ([[ADR-0092]]: developer builds; tenant admin installs/configures via Settings; user operates) is enforced case-by-case, not anchored to lifecycle stages.

The unlock is the same insight [[ADR-0089]] applied to *data*: **let a component declare handlers and have the platform call them.** Engines already carry exactly this shape — a `HANDLERS` dict mapping a name to a function. This ADR extends that from *verbs* (invoked actions) to the component's own *lifecycle events*, and unifies the scattered seams above under one contract.

## Decision

A component reacts to two families of events through **one declared-handler contract**: it names handlers in its **meta**, writes matching functions in its code, and the platform **calls them automatically** at the right moment, gated to the right actor, on the governed event/dispatch spine.

### 1. The two event families

- **Data events** — a governed object was written (the [[ADR-0089]] `subscribes:` model): `on: <schema>` + `where` → a handler. Unchanged by this ADR except that it becomes one arm of the same contract.
- **Lifecycle events** — the *component itself* crossed a stage. New here.

### 2. The lifecycle hook set

Each hook maps to a stage, an actor authorised to trigger it, and the **existing seam it formalises** (so this is consolidation, not new surface):

| Hook | Stage | Actor (who triggers) | Formalises today's seam |
|---|---|---|---|
| `on_install(ctx)` | first install into a tenant | tenant admin | `_materialize_contributions` + `_ensure_component_install` |
| `on_setup(ctx, inputs)` | guided prerequisites | tenant admin | the bespoke `city-setup` script (#114) |
| `on_configure(ctx, config)` | typed config changed | tenant admin (Settings) | `_bridge_settings_set` write — **no callback today** |
| `on_schedule(ctx)` | a scheduled tick | scheduler (system) | `main()` under `platform.schedule` |
| `on_<event>(ctx)` | a governed object written | platform (event spine) | `platform.subscription` ([[ADR-0089]]) |
| `on_upgrade(ctx, from_version)` | version bump | tenant admin (admin-gated) | **none today** ([[ADR-0098]] gap: no migration) |
| `on_uninstall(ctx)` | uninstall / revoke | tenant admin | `grants/revoke-for` / unshelf — **no cleanup today** |

A component implements **only the hooks it cares about** — most drivers implement none, most engines one or two.

### 3. The developer authoring surface

**meta.yaml** — declare hooks + data subscriptions:
```yaml
lifecycle:
  on_install:   provision      # → run.py handler names
  on_configure: reconfigure
  on_upgrade:   migrate
subscribes:
  - { on: governance.recommendation, where: { domain: air }, handler: on_recommendation }
setup:                          # on_setup's declared inputs (renders the guided form; ADR-0075/0092)
  - { id: gee_key, label: "Earth Engine key", kind: secret, required: true }
```
**run.py** — the handlers, in the shape engines already use:
```python
def provision(ctx):        seed_defaults(ctx)           # on_install
def reconfigure(ctx):      apply(ctx["config"])         # on_configure — new config in ctx
def migrate(ctx):          bump(ctx["from_version"])    # on_upgrade
def on_recommendation(ctx): route(ctx["subject_ref"])   # data event — the triggering id
HANDLERS = { "provision": provision, "reconfigure": reconfigure, "migrate": migrate,
             "on_recommendation": on_recommendation }
```
That is the whole surface. No hand-written `platform.subscription`, interface, binding, or setup script.

### 4. What the platform generates (invisible to the developer)

At **publish**, a generator reads `lifecycle`/`subscribes`/`setup` and — extending the existing `_register_verb_bindings` (#268) — auto-produces the **governed** plumbing:
- a signed **interface** ([[ADR-0058]]) per hook (e.g. `<component>.on_install`), and its **binding** ([[ADR-0090]]) to the app-host's engine-dispatch endpoint;
- for each `subscribes` entry, a **`platform.subscription`** contribution whose `action.interface` is the hook's verb (materialized on install, ADR-0092 §I);
- **conformance at certify** verifies every declared hook has a matching `HANDLERS` entry (mirrors today's `verb_conformance`).

At each **lifecycle stage**, the responsible seam emits a governed lifecycle event and the dispatcher invokes the hook — the same path a data event already takes. `on_install`/`on_setup`/`on_configure`/`on_upgrade`/`on_uninstall` are fired by the app-host install/settings/upgrade/uninstall flows respectively; `on_schedule` by the scheduler; `on_<event>` by automation.

### 5. Governance & the actor split are preserved

Each hook is a **governed, bound verb** — auditable, substitutable, enforceable — so the easy DX rides *on top of* governance, not around it. The **actor split is anchored to the stage**: which persona may trigger a hook is a property of the stage, enforced at the seam that fires it — developer owns build/publish; **tenant admin** owns install/setup/configure/upgrade/uninstall (the two-tier Settings, [[ADR-0092]]); **users** invoke only the run-time verbs they are authorised for. "Who can do what" stops being implicit and becomes *which actor can fire which lifecycle event*.

### 6. The handler contract (the rules that differ from UI `onClick`)

- **Idempotent + unordered.** Lifecycle and data events are at-least-once and may be redelivered or reordered — a handler must be safe to run twice (as `decision-router` already is: it skips already-routed recommendations). This is the one teaching point vs. the browser-event mental model.
- **`ctx` is the confined surface** (the broker/engine ctx from [[ADR-0030]]): `kget/kfind/kwrite/call/ai_complete/…` plus stage payload — `ctx["config"]` (on_configure), `ctx["from_version"]` (on_upgrade), `ctx["subject_ref"]` + `ctx["event"]` (data events), `ctx["inputs"]` (on_setup). A handler has exactly the component's declared grants — no elevation.
- **Compute components only.** Hooks belong to engines/skills/pipelines/drivers. **Apps** hold no authority and run in the browser as the user; they react to change via the UI, not backend hooks.

## Consequences

**Gains.** One model instead of five; a familiar "declare a handler, it gets called" DX; the `on_configure`/`on_upgrade`/`on_uninstall` gaps get filled (config-change callbacks, data migrations, cleanup) that don't exist today; Studio can render the lifecycle + subscriptions as a graph and let you author them visually (the [[ADR-0089]] ambition, generalised); every hook stays governed and audited.

**Costs / risks.** A publish-time generator is new surface with real blast radius (it writes interfaces + bindings + subscriptions). Auto-namespacing hook verbs must avoid collisions. `on_upgrade` migrations touch live tenant data — must run under the component's grants, be idempotent, and be reversible or forward-only by contract. The generator must be *additive* — never break the components that hand-wire these seams today.

**Migration.** Non-breaking, incremental: the hand-wired seams keep working; a component opts in by adding a `lifecycle:` block. Convert the reference examples first (e.g. move the Air Intelligence subscription from the hand-wired `platform.subscription` to a declared `subscribes:` on the decision-router; move `payroll-engine`'s `ensure_install` self-call to `on_install`).

## Build slices

1. **S1 — `on_install` + `subscribes:` generator. ✅ SHIPPED.** Declared `subscribes:` auto-wired into a governed `platform.subscription` at install (`_materialize_subscriptions`); `on_install` fires from the install flow. Proven on the Air Intelligence loop.
2. **S2 — `on_configure`. ✅ SHIPPED.** Fires from `_bridge_settings_set` after a typed-config write; the new config arrives in `ctx["body"]["config"]`. Proven live: writing a config value on `fund-flow-engine` fires its `reconfigure` handler (`[lifecycle] …on_configure→reconfigure: ok`).
3. **S3 — `on_setup`.** Declared `setup:` inputs render the guided form (retire the bespoke `city-setup` script into the generic hook). *Proposed.*
4. **S4 — `on_upgrade`.** Built in the helper (`_run_lifecycle("on_upgrade", …, {from_version})`) but **no trigger yet** — waits on the [[ADR-0098]] admin-gated upgrade endpoint (there is no upgrade seam today). *Proposed.*
5. **S5 — `on_uninstall`. ✅ SHIPPED.** Fires from `_bridge_uninstall` BEFORE grants are revoked, so cleanup still holds its rights.
6. **S6 — Studio surface + conformance. 🟡 PARTIAL (read-only view shipped).** Studio's Architecture graph now renders each component's declared `subscribes:` as amber **event-edges** (watched schema → reacting component) and its `lifecycle:` hooks as a green **⟳N badge** per node; the Configure modal shows read-only "Lifecycle hooks" + "Subscribes / data-events" cards. Data comes from a new parsed `declared` block on `/bridge/component-read` (`{lifecycle, subscribes, reads, writes, verbs}`). *Still Proposed:* visual **authoring** (add/edit hooks from the graph) and **certify-time conformance** (handler↔declaration parity check).

## Implementation note (S1/S2/S5)

The shipped mechanism is one generic host helper, `_run_lifecycle(hook, cids, tenant, token, claims, payload)` (`app_host.py`), the lifecycle sibling of `_materialize_subscriptions`. At each stage the responsible seam calls it; it resolves the component's meta, reads the `lifecycle:` block, and **dispatches the declared handler in the component's confined engine ctx** (`_invoke_engine` → `HANDLERS[handler](ctx)` — ADR-0030), with the stage payload in `ctx["body"]`. Best-effort + idempotent (§6): a hook that errors is logged and never fails the lifecycle operation. Because the host's minimal manifest reader flattens a nested `lifecycle:` map, the helper parses that block from the meta text directly (no PyYAML dependency in the app-host). Fired from: `_bridge_install` (`on_install`), `_bridge_settings_set` (`on_configure`), `_bridge_uninstall` (`on_uninstall`, before revoke). Reference example: `fund-flow-engine` declares `on_install: provision / on_configure: reconfigure / on_uninstall: teardown`. NOTE: the S1/S2/S5 dispatch is a **direct confined handler call**; the ADR §4/§5 "one governed interface per hook" (auto-generated + substitutable) is folded into S6 — the handler still runs with exactly the component's declared grants, so confinement holds today.

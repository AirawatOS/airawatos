# ADR-0098 — Versioned app install & admin-gated upgrades

**Status:** Proposed (2026-09-20)
**Relates to:** ADR-0016 (Store / certification / signing), ADR-0093 (component delivery — retire baking; filestore-default), ADR-0092 (unified settings & configuration model), ADR-0055/0075 (solution install & contributions), ADR-0036 (component instances — class vs installed instance), #137 (marketplace version discipline), #201 (archival tiering — hot/cold assets).

## Context

App upgrades are, today, a **globally forced rollout with no tenant control**. A tenant admin
who asks "how do I stay on the version I tested?" or "can I preview before my users get it?" has no answer,
because the serving layer does not model a per-tenant version at all.

The mechanism, confirmed in `platform-spec/reference/app_host.py`:

1. **Apps are served from a single shared overlay, keyed by app *name* only.** `_store_bundle()` for an app
   calls `_extract_overlay(name, blob)`, which unpacks the tar.gz into `APPS_OVERLAY/<name>/`
   (`/data/app-bundles/apps/<name>/`). There is no tenant segment and no version segment in that path — one
   directory per app name, **overwritten on every publish**.
2. **The publish-time overlay refresh is the delivery.** The moment a developer publishes, the overlay dir is
   replaced, and the app-host serves the new bundle at `/apps/<name>/` to **every tenant** on that host on their
   next load. "publish→live", as the code comment says.
3. **The bundle asset is not version-addressed either.** `platform.component_asset` is
   `additionalProperties:false` with **no `version` field** — the id is `ds:<steward>:platform/component_asset/<name>-bundle`,
   one record per app name, overwritten each publish. (The underlying filestore blob *is* content-addressed by
   `file_id`, so old bytes survive; nothing *references* them by version.)
4. **Install ≠ version pin.** Install (`app-install` / `platform.app_shelf`) only decides **shelf visibility** —
   whether the app appears on a tenant's desktop and under which roles (`_save_shelf`,
   `ds:<tenant>:app_shelf/default`). It records **no version**. So install carries no notion of "tenant X runs 0.1.2."

The store listing *does* have version discipline (#137): `0.1.1` and `0.1.2` are distinct, frozen certified
records. But the **serving path ignores it and always serves whatever was published last.** The version-immutable
store and the version-blind overlay are simply not connected.

### Consequences of the gap

- A developer publish **overrides every tenant immediately**. No staging, no rollout ring, no canary.
- A tenant admin **cannot** pin a version, preview a new one, or roll back a regression.
- There is **no changelog gate** — users get new behaviour with no admin acknowledgement.
- For a real multi-tenant network (regulated tenants, court/finance apps) this is not acceptable; forced-global is
  fine only for the single-operator dev environment we run today.

## Decision

Introduce a **per-tenant version pin** and make the serving path **resolve `(tenant, app) → pinned version → immutable
bundle`**, with **admin-gated upgrades**. Publishing makes a version *available*; it never moves a tenant.

### 1. Version-addressed bundle assets

Bundles become addressable by version, so more than one can exist at once.

- Store each published app bundle under a **version-qualified** component_asset id
  `ds:<steward>:platform/component_asset/<name>-bundle@<version>` (keep the plain `<name>-bundle` as an alias to
  "latest available" for back-compat during migration). Since `platform.component_asset` has no `version` field,
  either (a) add an optional `version` field via governance, or (b) encode it only in the id + `filename`
  (`<name>-<version>.tar.gz`) to avoid a schema change in slice 1. **Slice 1 uses (b)**; (a) is a fast-follow.
- **Do not overwrite the overlay on publish.** Instead extract to a **version-segmented** overlay path
  `APPS_OVERLAY/<name>/<version>/`. Old versions remain on disk (archival tiering, #201, sweeps cold ones later).

### 2. Install pins a version

`platform.app_shelf` entries gain an optional `version` per app (the entry is already a dict
`{"id", "roles"}` — add `"version"`). Semantics:

- **Install / add-to-shelf records the version installed** — the current "latest available" at install time — as
  the tenant's **pin**. This is the ADR-0036 distinction made real: the store listing is the *class*; the shelf
  entry is the tenant's *installed instance*, and an instance has a version.
- A shelf entry with **no** `version` means **"track latest"** — the current forced-global behaviour, preserved as
  an explicit opt-in (good default for the dev/operator tenant, not for regulated tenants).

### 3. Serve the pinned version

`GET /apps/<name>/…` resolves the requesting **tenant's** shelf pin, then serves
`APPS_OVERLAY/<name>/<pinned-version>/…`. Falls back to latest-available when the pin is absent (track-latest) or
the pinned dir is missing (rehydrate from the version-addressed filestore blob on demand — the delivery path of
ADR-0093). The resolver is the one new choke point; everything else is data.

### 4. Admin-gated upgrade

Publishing a new version sets **"upgrade available"** for pinned tenants; it does **not** move them.

- A tenant admin sees available upgrades **in the Settings app** (ADR-0092) — a new **Updates** surface listing
  `app · installed version · available version · changelog`. Approving re-pins the shelf entry to the new version.
- **Auto-upgrade is an opt-in setting** per app (or per tenant): flip a shelf entry back to track-latest to get
  the old behaviour deliberately. Enterprise/regulated tenants stay pinned; the dev operator can auto-track.
- Changelog text comes from the store listing (#137) — publishing should require a version note.

```
  TODAY (forced-global):                     ADR-0098 (pinned + admin-gated):

  dev publishes 0.1.2                        dev publishes 0.1.2
        │                                          │
        ▼                                          ▼
  overlay/<name>/  ⟵ overwritten          store gets 0.1.2 (frozen, #137)
        │  (one dir, no version)             overlay/<name>/0.1.2/  (0.1.1/ kept)
        ▼  publish→live, global                     │  tenants NOT moved
  ALL tenants serve 0.1.2               shelf pin still 0.1.1 → serve 0.1.2? NO, serve 0.1.1
                                                    │
                                        Settings ▸ Updates: "0.1.2 available → Upgrade?"
                                                    │  admin approves
                                                    ▼
                                        shelf entry re-pinned 0.1.2 → now serves 0.1.2
```

## Scope / non-goals

- **In:** apps (`kind:app`) served from the overlay. The pin, the version-segmented overlay, the resolver, the
  Settings ▸ Updates surface.
- **Out (for now):** drivers/engines — they already rehydrate + digest-verify on install (ADR-0093) and are pinned
  by the install record; a parallel "engine upgrade" gate is a later ADR. Cross-tenant/federated marketplace
  version negotiation (ADR-0085) is unchanged — content-addressed blobs already make old versions fetchable.
- **Not** a full release-train / ring-deployment system; that can layer on top of the pin later.

## Rollout

1. **Slice 1 — version-segmented overlay + serve latest (no behaviour change).** `_extract_overlay` writes
   `<name>/<version>/`; the resolver serves latest-available. Overlay stops being destructive; still forced-global.
   Safe, invisible, reversible.
2. **Slice 2 — shelf pin + pinned serve.** Add `version` to shelf entries; install records the pin; resolver
   honours it. New installs pin; existing (versionless) entries track latest → **no regression**.
3. **Slice 3 — Settings ▸ Updates.** Surface available upgrades + changelog; approve re-pins; per-app auto-upgrade
   toggle. This is the tenant-admin control the current model lacks.
4. **Slice 4 — governance + cleanup.** Optional `version` field on `platform.component_asset` (governed);
   cold-version overlay sweep (#201); require a version note at publish.

## Consequences

- **Positive:** tenant admins gain real version control (pin, preview, roll back, opt-in auto-upgrade); regulated
  apps (court/finance) stop receiving un-acknowledged behaviour changes; the store's existing version discipline
  (#137) finally reaches the serving path; ADR-0036 class-vs-instance becomes concrete for apps.
- **Costs:** the overlay grows (mitigated by #201 tiering); publish is no longer instantly live for everyone (that
  is the point, but it changes dev-loop expectations — keep the operator tenant on track-latest); one new resolve
  step on every app GET (cheap; pin is a shelf-record read already loaded for the desktop).
- **Migration:** existing shelf entries have no `version` → they track latest, exactly today's behaviour, so the
  network keeps working through every slice until an admin chooses to pin.

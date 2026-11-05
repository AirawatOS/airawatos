# ADR-0094 — Component Stewardship Separation: airawat governs, airawatdeveloper publishes

**Status:** Proposed
**Date:** 2026-09-19
**Related:** ADR-0038 (AirawatNetwork = standards body), ADR-0051 (AirawatDeveloper participant), ADR-0093 (retire baking), ADR-0016/0080 (certify/publish spine).

---

## Context

`airawat` is the **Network Administrator / certification authority** — it governs schemas, runs the CA, and *certifies* components. It must **not** also be a component **author/publisher**: a certifier that signs its own software is a separation-of-duties break. `AirawatDeveloper` was created (ADR-0051) precisely as the participant that develops and publishes platform software.

Investigation (2026-09-19) of the live catalogue (145 baked components) found the split is **incomplete**:

| Steward | Count | Meaning |
|---|---|---|
| `airawat` | **82** | mis-homed under the Network Authority (should not exist) |
| `airawatdeveloper` | 62 | correct |
| `acme` | 1 | a third-party |

**How the 82 came to be** (not a network exemption — verified):
- The network gate is strict: `_require_publisher` requires `token.tenant == id-steward` (network/api.py:223) and conformance enforces `steward == publisher` (network/conformance.py:123). There is **no** rule letting AirawatDeveloper publish under `ds:airawat`.
- Instead, the platform's own tooling authenticates **as `airawat`** to publish: the app-host's `_publish_member` uses `_dev_token()` — an identity login as the reference user **`"steward"`** (→ tenant `airawat`) — whenever a component's id-steward is `airawat` (app_host.py:2331, 2392-2393). The `network/tools/migrate-component-ids.py` docstring even codifies the (now-obsolete) intent: *"software … is published by the developer, so its steward is `airawat`."*
- Historical layering: `ds:kmc:*` (tenant-owned) → `ds:airawat:*` (migrate-tool era, "airawat = platform developer") → `ds:airawatdeveloper:*` (ADR-0051, the intended end-state). The move to the last layer stalled with 82 components still at `ds:airawat`.

## Scope (refined by source scan, 2026-09-19)

The migration is scoped to **software components**, NOT governance artifacts:

- **MIGRATE — 102 `ds:airawat` software components** (source tree; the deployed image bakes 82 of them): driver 34 · app 27 · engine 20 · solution 8 · runtime 5 · skill 2 · provider 2 · pipeline 2 · agent 2.
- **KEEP under `airawat` — governance artifacts** it legitimately stewards as the standards body/CA: `ref/source/*` (the source-attribution catalogue, ~80 refs), `pack/*` (spec packs), and `schema/domain/role/interface` (governed vocabulary). These are the Network Admin's *output*, not published software.

So "airawat doesn't publish" means **airawat is not a steward of software components**; it continues to govern schemas/refs/packs and to run the CA that *certifies* everyone's components.

## Decision

1. **`airawat` is Network-Admin-only for software.** No software component (`driver/engine/app/pipeline/skill/runtime/provider/agent/solution`) may be stewarded by `airawat`; software is published by a **developer participant** (`airawatdeveloper` first-party; others third-party). Airawat keeps stewarding governance artifacts and keeps its CA (certify) role.
2. **Re-home all 102 `ds:airawat:<software>` components → `ds:airawatdeveloper:*`** (82 deployed + ~20 source-only).
3. **Lock down component publishing:** the network refuses `certify`/`publish` when the subject id's steward is `airawat` **and** the subject is a software kind; conformance adds a `steward-not-authority-for-software` check; the app-host stops minting the `airawat` steward token for publishing (`_dev_token` retired from the publish path — publishes use the developer token). Governance-kind publishes under `airawat` (schema/ref/pack/…) stay allowed. `retire` stays permitted for `airawat` **until** migration completes, then closed.

## The per-component recipe (proven — S2b pilot + migrate tool)

For each of the 82: change `meta.yaml` `component_id` → `ds:airawatdeveloper:…`; **certify** under the airawatdeveloper token (real conformance: meta_yaml + files) → evidence_digest; **`_store_bundle`** (source tar → filestore + `__component_source__` record under the new id); **`store/publish`** the new listing (copy title/scopes/pricing/visibility); **retire** the old `ds:airawat` listing + cert (airawat token).

## Blast radius — every reference to a component_id that must move

- **Kernel installs** (install-as-grant, keyed by component_id) — per tenant: install(new) + uninstall(old). **HIGH RISK / needs each tenant's admin token.** Tenants seen: kmc, nashik, new-delhi, bmc, mysuru, court-1, mospi, … — must enumerate.
- **Store listings + certificates** — retire old, create new (recipe above).
- **`platform.component_asset`** records — both `__component_source__` and data-file bindings (e.g. `OSM_PBF`): the `component` field is the full cid → rewrite for the new id.
- **Solution / pipeline members** — e.g. `city-baseline` pipeline members, other solutions reference member component_ids → update.
- **App shelves + role grants** — app ids (`ds:airawat:app/…`) on tenant desktops and in `governance.role_grant` (app_id) → update.
- **viz.layer descriptors** — any that name a producing component.
- **prov / receipts** — historical `prov.component@version` references are immutable audit; leave as-is (bitemporal history), forward records use new ids.
- **The baked dirs** — meta `component_id` edit rides on ADR-0093 (retire baking); coordinate so the delivered component identifies as the new id.

## Migration plan (phased, local-first, each prod step gated)

- **P0 — Scan (read-only):** enumerate every reference site above on the live registry; produce the exact work-list (which of the 82 are installed in which tenants, which are in solutions, etc.). Sizes the real risk before any write.
- **P1 — Lock-down code (local-first):** network `_require_publisher` + conformance reject `airawat` as steward/publisher (allow `retire`); app-host publish path uses developer token only. Prove locally, then deploy. *Low-risk, future-proofs immediately.*
- **P2 — Re-home wave (local dry-run → prod in waves):** run the per-component recipe for the 82 under airawatdeveloper; retire old. Batch by kind, lowest-blast-radius first (engines/drivers not in solutions), apps + pipeline members last.
- **P3 — Re-point installs** per tenant (needs tenant-admin tokens — coordinate; this is the gating human-in-loop step).
- **P4 — Update solution/pipeline members, shelves, role grants, viz.layer, component_asset bindings** to new ids.
- **P5 — Close `airawat` `retire` too;** verify no `ds:airawat:*` component ids remain; fold into ADR-0093's retire-baking (deliver everything under the new ids).

## Consequences

- **Positive:** genuine separation of duties — the CA no longer signs its own software; every component has an accountable developer-publisher; future publishes cannot regress (lock-down enforces it).
- **Costs / risk:** an 82-id rename across **live installs in ~10 tenants** is the platform's largest reference migration; install re-pointing needs per-tenant admin tokens and must not leave a tenant with a dangling grant. Hence P0 (scan) and per-wave gating are mandatory; no big-bang.
- **Obsoletes** the S2b re-certs I did under `airawat` (43) — they get superseded by the airawatdeveloper re-homing; retract the stray `ds:airawat` certs/source-records as part of P2.

## Note
Design-only. No id is renamed and no lock-down ships without explicit per-phase approval; P0 is read-only and P1 is local-first per the project's test-before-deploy rule.

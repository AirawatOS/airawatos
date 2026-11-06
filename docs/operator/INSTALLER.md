# AirawatOS installer — consolidation

One idempotent installer runs every **CORE** setup step for an install, with profiles `production | rehearsal
| dev`. `bootstrap-dev.sh` becomes a thin wrapper = `install.sh --profile dev` plus the dev-only extras. This
doc holds the inventory, the DB-role model, and the standing rule (filled in across the slice).

## Step 1 — setup-step inventory (CORE vs DEV-ONLY)

Across `deploy/local-dev/bootstrap-dev.sh` (phases 1–11), `network/ensure_install.py`,
`deploy/local-dev/docker-compose.dev.yml`, and the legacy `deploy/local/airawatos-bootstrap.sh`.

| # | Setup step | Source | Class | Notes |
|---|---|---|---|---|
| 1 | **Base-OS install** — 6 tenant records (operator / network / data / developer / participant / citizens) + realm admins + scheduler daemon + `component-publisher` / `dev-sandbox` / `embed-service` service principals (Vault creds) + network directory listing | `ensure_install.py` (bootstrap Phase 1) | **CORE** | ADR-0115/0116/0124. Admin password generated into Vault if not supplied. |
| 2 | **Base vocabulary** — govern base domains / roles / schemas | `seed_base.py` (Phase 1) | **CORE** | the platform's governed noun/verb/role catalog |
| 3 | **Base apps** — deliver + shelf the platform apps (admin, settings, file-explorer, console, inbox, personal-assistant, storefront, network-admin, data) + mint listings | `seed_base_os.py` + `mint_base_listings.py` (Phase 1) | **CORE** | first-party *platform* apps, not demos — every install needs them |
| 4 | **Trust-plane schemas** (governed; dry-run → apply → dry-run) | `seed_trust_schemas` (Phase 2) | **CORE** | schemas + migrations |
| 5 | **Local Network** — mint the canonical network (generated ULID id, slug from INSTANCE) | Phase 3 | **CORE** | one per install; id ≠ slug |
| 6 | **network.admin role_assignment** on the network (governance path) | Phase 4 | **CORE** | records the steward as network admin |
| 7 | **trust-reader** service principal (+ Vault password) | Phase 5 | **CORE** | role-mode mint-on-demand reader |
| 8 | **Trust-plane audit HMAC** → Vault | Phase 6 | **CORE** | ADR-0119 console/governance signing |
| 9 | **trust-writer** service principal (+ Vault password) | Phase 7 | **CORE** | Trust-plane governance writes |
| 10 | **First platform.authority holder** via the governance path (first-holder-only) | Phase 7b | **CORE** | ADR-0122; never a direct registry write |
| 11 | **network capability_catalog** (empty) + link into the network | Phase 8 | **CORE** | Trust-plane grants need it |
| 12 | **app-host scheduler-caller** principal (+ Vault password, svc:scheduler/filestore audiences) | Phase 10 | **CORE** | ADR-0124 item 1 |
| 13 | **DB roles + lockout table + indexes** — least-privilege Postgres roles, `identity_login_fails`, registry indexes | Phase 11 (+ step 4) | **CORE** | see §DB-roles |
| 14 | **platform test users** `platauth` / `platnone` (Vault creds) | Phase 9 | **DEV-ONLY** | ADR-0122 conformance fixtures; created in `dev` + `rehearsal` (credentialed conformance needs them), never `production` |
| 15 | **Synthetic perf dataset** (~1M `perf.*` rows) | `perf/seed.py` (separate) | **DEV-ONLY** | dev profile only; refuses under `AIRAWAT_ENV=production` |
| 16 | **Demo tenants / sample components** | later demo slices / Studio (not in these 4 files) | **DEV-ONLY** | not part of the installer; listed for completeness |
| 17 | **Zero-repo prebuilt-image bootstrap** (writes a compose + vault config, brings up a Docker-Hub-image stack) | legacy `deploy/local/airawatos-bootstrap.sh` | **SUPERSEDED** | a *delivery* mechanism (bare-Docker demo), not install logic; retired in step 6 → points at the installer |

**compose** (`docker-compose.dev.yml`) is not itself an installer step — it defines services, their env (gates,
Vault paths, DB roles), and volumes. Its install-relevant settings (password-enforce mode, DB roles, ingress
gates) are CORE config consumed by the running services; the dev/prod difference is `AIRAWAT_ENV`, the
password-enforcement mode, and whether the dev-only extras (#14–#16) run.

## Step 2 — Postgres role each service connects as (before step 4)

One database `kernel` on a single Postgres 16 cluster; shared tables in schema `public`. Only three services
open a DB connection at all — every other service (app-host, automation, scheduler, filestore, notify,
event-relay, secrets, model-gateway, workflow, decision) reaches data **through** the kernel/network HTTP APIs
and has **no** DB credential.

| Service | Connects as | Superuser? | Tables it owns/uses | Can reach other services' tables? |
|---|---|---|---|---|
| **kernel** | `kernel` (compose sets no `DB_USER` → pg_store default `kernel`) | **YES** | `registry_version`, `kernel_admin_audit`, `registry_schema_meta` | **YES** — superuser; reads/writes/drops `kv` + `identity_login_fails` too |
| **network** | `kernel` (explicit `DB_USER=kernel`) | **YES** | `kv` (durable KV: tenants, networks, directory, grants) | **YES** — superuser over the whole DB |
| **identity** | `identity_lockout` (password from Vault) | no | `identity_login_fails` (SELECT/INSERT/DELETE) | **NO** — `permission denied` on every other table (proven, prior slice) |
| installer / bootstrap | `kernel` (superuser) | YES | DDL across all tables | — (should be a dedicated `migrator`, not a service identity) |

Role attributes today: `kernel` = `Superuser, Create role, Create DB, Replication, Bypass RLS`; all five public
tables are owned by `kernel`. `identity_lockout` = non-super, login, no table rights beyond its one grant.

**Finding:** kernel and network both run as the **cluster superuser** and can read/write each other's and
identity's tables — a compromise or bug in either has the whole database. Only identity is confined. Step 4
introduces non-superuser `kernel_app` / `network_app` owning only their own tables, keeps `identity_lockout`,
and adds an installer-only `migrator` role, with cross-service reads proven denied.

## Step 3 — the unified installer

`deploy/local-dev/install.sh` runs every CORE step (phases 1–13 above), idempotently, with
`--profile production | rehearsal | dev`. `deploy/local-dev/bootstrap-dev.sh` is now a thin wrapper =
`install.sh --profile dev`. Profiles differ only in which optional step-classes run; the surrounding stack env
(`AIRAWAT_ENV`, the production guard, password-enforcement) is set by the compose per profile.

| | production | rehearsal | dev |
|---|---|---|---|
| CORE steps (#1–#13) | ✓ | ✓ | ✓ |
| test users `platauth`/`platnone` (#14) | — | ✓ | ✓ |
| synthetic perf data (#15, opt-in `INSTALL_PERF_SEED=1`) | — | — | ✓ |
| expected stack env | `AIRAWAT_ENV=production`, guard on | `=production`, guard on | `=development`, guard off |

Verified: `--profile bogus` is rejected; the dev-only test-user phase is gated by profile; `bash -n` clean;
the dev wrapper runs the proven phase bodies unchanged (an idempotent re-run against the long-lived live stack
surfaces only pre-existing admin-login drift in `seed_base_os`, which the clean fresh-install test — step 5 —
exercises). Conformance both modes green.

## Step 4 — DB-role rework (SCOPED — its own slice; blockers surfaced)

Target (per the refinement): no service runs as a superuser; a dedicated non-super `kernel_app` / `network_app`
(DML only, **no DDL** — boot-time DDL moves into a `migrator` role run by the installer); keep `identity_lockout`;
all passwords in Vault, none in compose; prove each service cannot read another's tables.

**Blockers found while scoping (why this is a separate slice, not a tack-on):**
1. **`kv` is shared between kernel AND network.** The kernel imports `services.kv` (`kernel/api/app.py:1955,
   2009`) and writes the same `kv(store,key,value)` table the network owns (`network/kv.py`). So `network_app`
   cannot *exclusively* own `kv` — either both app roles get DML on a shared `kv` (weaker isolation: each can
   read the other's KV rows), or `kv` is split into per-service tables (a schema + code change in both
   services). **A design decision is required before implementation.**
2. **Boot/lazy DDL is spread across ≥4 code sites**, all of which must be relocated to the migrator and guarded
   behind a skip-DDL flag so a non-owner app role never attempts DDL:
   - `kernel/services/registry/pg_store.py` — `_DDL_CORE` (tables) at boot + `_DDL_MAINT`/`CONCURRENTLY`
     indexes in the maint thread + on-demand `rvx_*` expression indexes at schema-publish.
   - `kernel/api/adminaudit.py` — `kernel_admin_audit` created **lazily** on first audit write (`_ensure_table`).
   - `kernel/services/kv.py` and `network/kv.py` — `CREATE TABLE kv` on first connect.
3. **Two images rebuild** (kernel + network) plus Vault-password DSNs added to `pg_store`, both `kv.py` modules
   — each reading `DB_PASSWORD_VAULT_PATH` like identity already does.

**Planned shape** (for the dedicated slice): installer `migrator` role owns `registry_version`,
`kernel_admin_audit`, `registry_schema_meta`, `kv` (+ sequences); runs all the DDL above via a kernel/network
`migrate` entrypoint; grants DML — registry/audit/meta → `kernel_app`, `kv` → `kernel_app` + `network_app`
(pending the split decision), `identity_login_fails` → `identity_lockout`. Services boot with
`REGISTRY_SKIP_DDL=1` / `NETWORK_SKIP_DDL=1` and `DB_USER=kernel_app|network_app` (Vault password). Then prove
`kernel_app` is denied on `identity_login_fails` and `network_app` denied on `registry_version`, and both
services boot + conformance both modes. Reversible: revert compose `DB_USER` + the images.

## Step 7 — extended standing rule

Every code slice ends with: local-dev rebuild + live check of the specific fix + conformance both modes **and
updates this installer (so it still reproduces the stack) and — for a change that alters install/boot state —
passes the fresh-install test** (wipe volumes → `install.sh --profile dev` → conformance both modes match the
prior results) — unless told otherwise. Recorded in memory (`code-slice-rebuild-verify-rule`).

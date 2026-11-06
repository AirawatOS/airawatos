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

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

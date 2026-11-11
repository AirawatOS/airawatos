# AirawatOS installer — consolidation

One idempotent installer runs every **CORE** setup step for an install, with profiles `production | rehearsal
| dev`. `bootstrap-dev.sh` becomes a thin wrapper = `install.sh --profile dev` plus the dev-only extras. This
doc holds the inventory, the DB-role model, and the standing rule (filled in across the slice).

## Step 1 — setup-step inventory (CORE vs DEV-ONLY)

Across `deploy/local-dev/bootstrap-dev.sh` (phases 1–11), `network/ensure_install.py`,
`deploy/local-dev/docker-compose.dev.yml`, and the legacy `deploy/local/airawatos-bootstrap.sh`.

| # | Setup step | Source | Class | Notes |
|---|---|---|---|---|
| 1 | **Base-OS install** — the platform tenant (operator) + system realms (network / participant / citizens) + the transitional developer steward realm + realm admins + scheduler daemon + `component-publisher` / `dev-sandbox` / `embed-service` service principals (Vault creds) + network directory listing. The `<inst>` **data** tenant is **dev-profile only** (`SEED_DATA_TENANT`; not platform infra — see §Step 3) | `ensure_install.py` (bootstrap Phase 1) | **CORE** (data tenant: DEV-ONLY) | ADR-0115/0116/0124. Admin password generated into Vault if not supplied. |
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
| 13 | **DB roles + lockout table + indexes** — least-privilege Postgres roles, `identity_login_fails`, registry indexes | Phase 11 + 11b | **CORE** | see §Step 4b (split roles SHIPPED) |
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
identity's tables — a compromise or bug in either has the whole database. Only identity is confined. **Step 4b
(SHIPPED, below) replaces this**: non-superuser `kernel_app` / `network_app` own only their own tables (the
shared `kv` is split into `kernel_kv` / `network_kv`), `identity_lockout` is kept, and an installer-only
`migrator` role owns every table + is the sole DDL author — cross-service reads proven denied.

## Step 3 — the unified installer

`deploy/local-dev/install.sh` runs every CORE step (phases 1–13 above), idempotently, with
`--profile production | rehearsal | dev`. `deploy/local-dev/bootstrap-dev.sh` is now a thin wrapper =
`install.sh --profile dev`. Profiles differ only in which optional step-classes run; the surrounding stack env
(`AIRAWAT_ENV`, the production guard, password-enforcement) is set by the compose per profile.

| | production | rehearsal | dev |
|---|---|---|---|
| CORE steps (#1–#13) | ✓ | ✓ | ✓ |
| `<inst>` data tenant (`SEED_DATA_TENANT`) — NOT platform infra, see §Step 3 | — | — | ✓ |
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

## Step 4a — kv namespace matrix (READ-ONLY; review gate before 4b)

The `kv(store,key,value)` table is shared **physically** by the kernel and network, but every namespace
(`store`) is **single-owner**. Openers are the `_NS["…"]` / `_NScase(…,"…")` / `_DS_KV` call sites (dict-key
occurrences like `{"schemas": []}` or `claims.get("roles")` are NOT kv ops and are excluded).

**Live namespaces (rows today):**

| namespace | rows | owner | writer (file:line) | reader | cross-service? |
|---|---:|---|---|---|---|
| `certificates` | 8 | network | `network/api.py:73` (`_NS["certificates"]`) | network | single-owner |
| `domains` | 5 | network | `network/api.py:89` | network | single-owner |
| `networks` | 2 | network | `network/api.py:71` | network | single-owner |
| `participation` | 6 | network | `network/api.py:70` | network | single-owner |
| `roles` | 9 | network | `network/api.py:82` | network | single-owner |
| `schemas` | 21 | network | `network/api.py:76` | network | single-owner |
| `tenants` | 6 | network | `network/api.py:78` | network | single-owner |
| `trusted_issuers` | 2 | network | `network/api.py:100` | network | single-owner |
| `listings` | 8 | network | `network/api.py:74` (`Store(_NS["listings"])`) | network | single-owner |
| `tenant_datasets` | 4 | **kernel** | `kernel/api/app.py:2125,2127` (`_DS_KV.put`) | kernel (`:2138,2143,2173,2193,2213`) | single-owner |

**Kernel-owned namespaces (openers present; 0 rows live):** `cases` (`kernel/api/app.py:1958`), `installed`
(`:2011`), `installed_schemas` (`:2099`). **Network-owned (declared, mostly empty):** the full `_backend([...])`
list at `network/api.py:57–62` — participants, certificates, listings, inbox, events, offerings, schemas,
packs, keystore, tenants, grants, solutions, actor_keys, roles, role_requests, schema_requests, pack_requests,
domains, interfaces, interface_requests, bindings, joins, data_requests, service_offerings,
service_transactions, jurisdictions, credentials, trusted_issuers, file_shares, store_publish_requests,
email_codes, participation, networks, network_services, …

**Finding — NO cross-service kv reads.** Neither service reads the other's kv namespaces. The kernel does read
network-owned *data* (schemas, tenants) but via the **network HTTP API** — `NETWORK_URL/v1/schemas`
(`kernel/api/app.py:1287,2243`), `_net_get("/v1/tenants")` (`:1819`) — not by reading network's `kv` rows.
The only coupling of the shared table is physical co-tenancy, not a logical cross-read.

**Implication for 4b:** the split is clean — copy each namespace's rows to `kernel_kv` (tenant_datasets, cases,
installed, installed_schemas) or `network_kv` (everything else) by owner; there is **nothing to convert to a
governed registry record (★3)** at the kv layer, because the existing kernel↔network data dependency is
already an HTTP service boundary, not a shared-table read. (Flagged for review in case any out-of-repo or
future caller is expected to read across — none found in kernel/ or network/.)

## Step 4b — split-role least-privilege DB (SHIPPED, local-dev; reversible)

No service runs as a Postgres superuser. The shared `kv` table is split per-service and three non-super roles
replace the `kernel` superuser on the service path:

| role | owns | may DML | denied (proven) |
|---|---|---|---|
| `migrator` | every kernel-side table + 2 sequences; **only** role with `CREATE` on schema `public` | all (it runs the DDL) | — (installer-only; never a service identity) |
| `kernel_app` | — | `registry_version`, `registry_schema_meta`, `kernel_admin_audit`, `kernel_kv` (+ their sequences) | `network_kv`, `identity_login_fails` |
| `network_app` | — | `network_kv` | `registry_version`, `kernel_kv`, `identity_login_fails` |
| `identity_lockout` (unchanged) | — | `identity_login_fails` | everything else |

Every password is in Vault (`secret/data/<instance>/{migrator,kernel-app,network-app}/password`), **none in
compose**. The kernel boots with `REGISTRY_SKIP_DDL=1` + `KV_SKIP_DDL=1`, the network with `KV_SKIP_DDL=1`, so
the **migrator is the sole DDL author** — via `kernel/tools/db_migrate.py` (`run_migrations` = `_DDL_CORE` +
`_DDL_MAINT` + the two `CONCURRENTLY` live-set indexes, then `kernel_admin_audit` + `kernel_kv` + `network_kv`).
The three boot/lazy DDL sites named in §Step 4 are each guarded behind a skip flag (`pg_store` early-returns
before boot DDL + skips on-demand `rvx_*`; `adminaudit._ensure_table` returns; both `kv.py` skip `CREATE TABLE`).

**Installer.** Phase 11b (`deploy/installer/install.sh`) creates the three roles (Vault passwords, reuse-or-
generate), grants `CREATE`/`USAGE` on schema `public` to `migrator`, reassigns the split tables + sequences to
`migrator`, grants per-service DML, and — on a legacy DB that still has the shared `kv` — copies each namespace
to `kernel_kv` (tenant_datasets, cases, installed, installed_schemas) or `network_kv` (all else) by owner,
leaving `kv` in place. Idempotent; it **converges an existing install** onto the split roles.

**Fresh-install bring-up ordering (DEFERRED to the volume-wipe test, step 5 of the earlier slice).** On an
empty DB the app-role services cannot boot until their tables exist. The fresh-install sequence is:
`docker compose up -d postgres vault` → create roles (Phase 11b) → run the migrator
(`docker compose run --rm -e DB_USER=migrator -e DB_PASSWORD_VAULT_PATH=secret/data/<inst>/migrator/password
kernel python -m tools.db_migrate`) → `docker compose up -d`. The current installer runs **against an already-up
stack** (preflight health-checks kernel+network), so it exercises the converge path; the from-empty ordering is
what the deferred wipe test validates.

**Proven (local-dev, 2026-11-06).** Both services boot healthy as non-superusers (kernel logs
`REGISTRY_SKIP_DDL=1 … skipping boot DDL`); the migrator entrypoint runs idempotently; isolation 8/8 (each app
role denied the other's tables + `identity_login_fails`); conformance external **and** internal exit 0 (no FAIL;
XFAILs are pre-existing debt A1/A72, unchanged). Reversible: revert compose `DB_USER`/image tags + the roles.

## Step 3 — base-install tenants vs PLATFORM P1

P1: the installer creates **exactly one platform tenant** + base schemas/apps + service identities, and **no
data/customer tenants** outside the dev profile. The install stands up **one platform tenant** plus a set of
**system realms**. A realm is a **login namespace** (where accounts authenticate), not an authority: a realm
confers **no grant and no governance power** — authority comes only from a recorded `governance.role_assignment`
/ `platform.authority` / grant (F2), never from being a realm. The realms:

| realm | kind | purpose | authority it confers |
|---|---|---|---|
| `<inst>-operator` | **the platform tenant** | the one OS/system tenant — holds `platform.admin` + the scheduler daemon (ADR-0115) | **the platform tenant** (its admin holds `platform.admin` by an explicit role_assignment, not by the realm) |
| `<inst>-network` | network **authority** realm | the login namespace for the governance/trust-plane authority that signs certs, tenants, directory (ADR-0119); platform *infrastructure* | **none from the realm** — the network admin's authority is its recorded `network.admin` assignment (step 6), not the realm itself |
| `<inst>-participant` | shared **member** realm | one login namespace for **all** hosted network members (ADR-0116, *participant ≠ tenant*); never a tenant-each. No `admin` is provisioned at install; each member's login is minted on membership approval | **none** — a member's reach is its own membership + grants, not the realm |
| `citizens` | shared **identity** realm | the eKYC citizen-identity login namespace; individuals self-register/verify once, then join networks as individuals (ADR-0116) | **none** — identity only; joining a network is a separate governed act |

**`<inst>-developer` — TRANSITIONAL (COMPONENT CP2).** The development realm that also stewards this install's
first-party components (`ds:<inst>-developer:…`). It **retires under COMPONENT CP2** (a private publishing lane
replaces the dev-tenant steward); kept for now and flagged so its retirement is tracked. Not a standing part of
the platform-tenant set.

**`<inst>` data tenant — DEV PROFILE ONLY (moved out of CORE this slice).** The `<inst>` data tenant is **not**
platform infrastructure: an install-time audit found **nothing concrete requires it** — every later installer
phase (trust-reader, audit HMAC, platform.authority, capability_catalog, scheduler-caller, DB roles) targets
`-operator` / `-network` / `-developer`, and its only install-time consumer was the base-app *shelf* default
(cosmetic: giving its admin a populated app shelf). It is a **first data tenant**, so it is created **only under
the dev profile** (`SEED_DATA_TENANT=1`, set by `install.sh`; `ensure_install.py` gates both the tenant record
and its admin behind it, and the shelf step drops it from `SHELF_TENANTS` when absent). production / rehearsal
stand up the platform **without** it; a working tenant is created via **onboarding**, not the installer.

**Outcome:** one platform tenant (`-operator`); three system realms that confer no authority (`-network`,
`-participant`, `citizens`); one transitional steward realm (`-developer`, CP2); and the `<inst>` data tenant
relocated to the dev profile. This satisfies P1 strictly — the installer creates exactly one platform tenant
and no data/customer tenant outside dev. (The from-empty behaviour is validated by the fresh-install test.)

## Step 4 — rehearsal profile: test users have no access to personal data

In **rehearsal** the installer restores a production-shaped dataset, so the dev test users must be **powerless
over it**. Design:
- `platauth`/`platnone` are created in `<inst>-network` with **role `[]`** (ensure_install/Phase 9 never grant
  a role). Critically, in rehearsal the installer **must NOT run the ADR-0122 step-2b ChangeRequest** that
  grants `platauth` `platform.authority` — that grant is a dev convenience; over restored production data it
  would be authority on real personal data. So rehearsal test users stay **roleless**: no `platform.authority`,
  no tenant-admin, no governance role.
- Personal-data access is the **two-key rule** (FOUNDATIONS §3): a CapabilityGrant **and** the subject's
  Consent. Roleless test users hold neither, so every personal read/write is denied by the normal gate — no
  special rehearsal carve-out needed. (The restore must also NOT copy production Consents to a test principal.)
- The test-user passwords live in Vault (never compose); they exist only so the **credentialed conformance
  cases** can run (anonymous/abuse cases need no creds). They are **not** created in the production profile.

**Net:** rehearsal proves the install + conformance against realistic data **without** any test identity
holding authority or consent over that data. (Enforcement that the restore never attaches a production grant/
consent to a test principal is a restore-tool responsibility — flagged for the rehearsal restore slice.)

## Step 5 — DESIGN ONLY: one-time first-authority credential + break-glass custodian (P2, P5a)

Not built this slice; design recorded for the P2/P5a implementation.

**One-time first-platform-authority credential (P2).** At install, instead of seeding `platform.authority`
onto a named account, the installer mints a **single-use enrolment token** (high-entropy, stored only as a
hash in the registry; the plaintext delivered to the first admin out-of-band — printed once to the operator's
console or sealed to their key, never logged). The first admin presents it **once** to a
`POST /v1/platform/claim-authority` endpoint, which: verifies the hash, records the `platform.authority` role
(the governance path, first-holder-only), then **marks the token spent** (and expires it after a short TTL
even if unused). A spent/expired token is refused. Immediately after, the UI **requires a second holder** to
be added (SoD, P5) before the install is "complete". No long-lived installer credential, no committed secret.

**Break-glass custodian recovery (P5a).** A recovery secret is **split (Shamir k-of-n) among named
custodians** at install (each custodian receives one share, sealed to their own key; the installer keeps
none). Recovery requires a **quorum** of shares to reconstruct a one-time authority-restore token whose scope
is **only** "restore a `platform.authority` holder" (it can do nothing else). Every break-glass use is written
as a **public, permanent** decision record (DECISION) — who invoked, which custodians, when — visible in the
audit log and never editable. Setup is part of install (production/rehearsal); the shares' delivery is
out-of-band. Depends on P5 (recorded `platform.authority` role) landing first.

## Who does what — operator vs first platform authority

Two distinct humans, by design (FOUNDATIONS F11 separation of duties; PLATFORM P3 — the operator holds **no**
governance role):

| | **Operator** (host / infra) | **First platform authority** (governance) |
|---|---|---|
| Owns | the host, Docker, Vault, the OS, backups, the perimeter | platform policy: tenants/tiers, allowed issuers, the provider catalog (P6/P17) |
| Does at install | provisions the host; runs `install.sh --profile production`; holds Vault + unseal custody; passes the host pre-flight | receives the **one-time enrolment credential** (step 5), claims `platform.authority` once, then adds a **second holder** (SoD, P5) |
| Must NOT | hold any governance role; grant `platform.authority` to themselves | touch the host, Vault internals, or DB roles |
| Skills needed | Linux/Docker ops, Vault operation (unseal, policies — not dev-root), TLS/perimeter, backup/restore drills | the governance model (tenants, roles, consent, provider approval) — no infra skills required |
| Credentials | Vault token (scoped, not root), host SSH | a login + the one-time enrolment token; later a wallet/second factor |

**Break-glass custodians** (step 5, P5a) are a third set — named individuals each holding one Shamir share,
used only under quorum to restore a lost `platform.authority`; every use is a public permanent record.

## Target state (where the installer is heading)

- **Signed, prebuilt images** pinned by digest (not source builds); the installer verifies image signatures
  before standing anything up (supply-chain: COMPONENT CP-series).
- **One command**: `install.sh --profile production` runs Phase 0 → base-OS → … → done, idempotently, with
  the host pre-flight gating it; no manual phase-by-phase steps.
- **Prompts, not flags**, for the few human decisions (instance name, the first-authority credential delivery
  channel, custodian emails) — everything else generated into Vault.
- **Clean handover**: install ends by printing the operator checklist (backup drill scheduled, perimeter
  verified, Vault unseal custody recorded) and the first-authority enrolment instructions, then the operator
  steps back from governance entirely.

## Step 7 — extended standing rule

Every code slice ends with: local-dev rebuild + live check of the specific fix + conformance both modes **and
updates this installer (so it still reproduces the stack) and — for a change that alters install/boot state —
passes the fresh-install test** (wipe volumes → `install.sh --profile dev` → conformance both modes match the
prior results) — unless told otherwise. Recorded in memory (`code-slice-rebuild-verify-rule`).

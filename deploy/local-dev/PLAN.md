# Clean local-dev environment — PLAN

**Status:** Approved 2026-11-03 with amendments. **Build gated** on the tree-cleanup decision (§6) — build only from committed hashes; tag images `dev-<shortsha>`. EC2 untouched throughout.

**Goal:** a local development environment built from the repositories (not from production images), with its own keys, data, issuer/audience, and an explicit dev profile + production guard.

## Approved decisions
- Front door bound to **127.0.0.1:8080** (not :80).
- New **`deploy/local-dev/`** tree; **keep `deploy/local/`** (production-image eval path) until the new env passes both harnesses, then propose retiring it.
- This report saved here as `deploy/local-dev/PLAN.md`.

---

## Stage 1 — Discovery (facts)

### Service → source (three code images, all pulled today, none at branch head)
| Service(s) | Live image | Source repo → branch head |
|---|---|---|
| kernel | `airawatos-kernel:local-src` (ad-hoc session build) | **kernel** → `feat/admin-issuer-scope` @ `021fa22` |
| network | `airawatos-network:0.3.19-ekyc` | **network** → `feat/trust-plane-phase1` @ `29554c1` |
| identity / app-host / secrets / filestore / model-gateway / notify / workflow / decision / automation / event-relay / scheduler | one `reference` image (tags `0.2.83` / `0.2.95` / `0.2.100` / `0.2.115` / `local-src`) | **platform-spec** → `feat/network-console-multinetwork` @ `cf43173` |
| apps (Data, Files, network-admin, water-dashboard…) | served by app-host from `app_bundles` | **components** → `feat/network-console-multinetwork` @ `6e95b12` |
| postgres / vault / nginx | `postgres:16-alpine`, `hashicorp/vault:1.15`, `nginx:alpine` | stock; vault + nginx config in `deploy/local/` (Airawat repo) |

**Running-vs-source gap:** the live stack runs a mix of old pinned tags; only kernel + app-host are from (partial) source. "local" ≠ "the repos" today — the core problem this env fixes.

### Keys / issuer / audience (today)
- Network authority key: persistent via **Vault transit** `airawat-authority` (id `ds:airawat:network/authority`); local-seed fallback persisted in keystore.
- Identity: `IDENTITY_ISSUER` (default `ds:airawat:identity`), `IDENTITY_AUDIENCE` (default `airawatos`), per-tenant issuer gated by `IDENTITY_PER_TENANT_ISSUER`; Vault-transit per-issuer signing. **Issuer + audience are env-settable.**
- Kernel has `EXPECTED_AUD`/`EXPECTED_ISS`/`AUD_ISS_SHADOW`; live posture is `aud=UNBOUND, iss=UNBOUND`, auth/prov/dataplane = **shadow**.

### Dev conveniences currently active (to be gated)
`IDENTITY_SEED_DEMO`, passwordless reference IdP (blank password), `ENSURE_DEV_TENANT`, app-host `--no-verify-cert`, kernel shadow postures, dev DB password `kernel`.

### EC2-only (inferred; **not read from box** — confirm when unfrozen)
`runtime-manager` (docker socket), `mospi-gateway`, `keycloak` (+ `/kc` route); EC2 `nginx.conf` (TLS/domain), compose overrides (`trust-canary.override.yml`), Vault contents / DB / seed data / real prod image tags.

### Harness finding (Commit-D / Gate-2A build from source or pinned?)
**From source — not pinned images, and not the full container stack.** `network/trust/contract/up.sh` runs the **kernel from the `kernel/` working tree** (`uvicorn api.app:app`, venv, `pip install -r kernel/deploy/requirements.txt`) against a stock `postgres:16` container; the **Network Trust logic is imported from the `network/` working tree as a library** (`HttpRegistryClient` → kernel over HTTP). JWTs locally minted Ed25519; TRUST_SCHEMAS seeded via `seed_schemas.py`; `MODE=gate2a` / `MODE=commitd` run strict-schema. No network/identity/vault/app-host containers.
**Implication:** to run these "against this environment", point `KERNEL_URL` at the local-dev kernel (the validators already take `KERNEL_URL` + import the network trust modules), rather than the hermetic throwaway kernel.

---

## Stage 2 — Build proposal (with approved amendments)

1. **`docker-compose.dev.yml` from source, loopback-bound.** `build:` the kernel (`kernel/deploy/Dockerfile`), the network, and one `platform-spec` reference image from committed branch heads; tag each `dev-<shortsha>`. components apps delivered from the working tree. nginx bound **127.0.0.1:8080**; every other service internal (no host ports).

2. **Fresh keys + distinct identity.** Local-only Vault with freshly generated transit keys — authority id `ds:localdev:network/authority`, key `localdev-authority`. `IDENTITY_ISSUER=ds:localdev:identity`, `IDENTITY_AUDIENCE=airawatos-localdev`. No production key/seed/data copied.

3. **(amend)** Bootstrap creates a **recorded `platform.authority` `role_assignment` on an explicit platform scope** for the local steward, in addition to whatever current code needs.

4. **(amend)** The local canonical Network uses **normal canonical ID generation** (ULID) with **slug `localdev`** — no slug-derived id. Platform-tenant **self-membership only as a flagged, optional step**.

5. **Durable Postgres; ephemerality off.** Named volume `localdev_pg`. `AIRAWAT_EPHEMERAL_OK` unset except an explicit test profile.

6. **Scripted `bootstrap-dev.sh`** (explicit, ordered, idempotent): generate Vault keys → seed Trust-plane schemas + base vocab → create the first **platform authority** (+ the role_assignment in §3) → bootstrap the local canonical Network (§4). Each step annotated with how production did it (by hand / implicitly).

7. **(amend)** **Production guard checks EFFECTIVE settings:** if `AIRAWAT_ENV=production` **and** any convenience is active (passwordless login, demo seed, `--no-verify-cert`, any shadow posture, ephemeral-OK) → **refuse to start and log which one**. Must be tested.

8. **(amend)** **Dev profile never puts iss/aud back into shadow** — the kernel **enforces** the local issuer + audience (bound, not shadow) even in dev.

9. **Out of scope** (EC2-only, documented stubs): runtime-manager, mospi-gateway, keycloak.

**Then:** build → bring up → run `bootstrap-dev.sh` → run the Commit-D and Gate-2A harnesses against this environment → report evidence. STOP.

---

## Pre-build gate — tree cleanup (DONE 2026-11-03)
Resolved per decision: data-mount split to `feat/data-mount` in kernel + platform-spec (NOT on the hardening branches); scheduler/govern_fsnode/canary + components concerns committed one-per-concern on their branches; `.DS_Store` ignored everywhere; feature branches pushed (no main, no merge); outer-repo compose/overlay stepping-stones discarded. Local-dev built from the resulting committed hashes, tagged `dev-<shortsha>`.

---

## Item-4 — issuer/audience defaults + production deploy requirements (read-only analysis)

**What `IDENTITY_HOME_ISS` unset does — DEFAULT, not fail-closed (file:line):**
- Kernel: `kernel/api/kernelcore.py:31` → `HOME_ISS = os.environ.get("IDENTITY_HOME_ISS", "ds:airawat:identity")`. The admin predicate (`kernelcore.py:52,86`) compares `claims.iss == HOME_ISS`. Unset ⇒ home issuer silently defaults to `ds:airawat:identity` (no error, no fail-closed).
- Network: `network/api.py:208` → `_ADMIN_HOME_ISS = os.environ.get("IDENTITY_HOME_ISS", "ds:airawat:identity")`; used by `_home_issued()` (`api.py:211-212`). Same default behaviour.

**Related defaults:**
- Network audience: `network/api.py:29` → `authn.set_audience(os.environ.get("EXPECTED_AUDIENCE", "airawatos"))`. Unset ⇒ expects `airawatos`.
- Kernel iss/aud: `kernel/services/authn.py:24-25` → `EXPECTED_AUD`/`EXPECTED_ISS` default **empty set** (⇒ **no** iss/aud check); `:29` `AUD_ISS_SHADOW` default false. So the kernel's iss/aud enforcement is **dormant unless `IDENTITY_EXPECTED_ISS`/`IDENTITY_EXPECTED_AUD` are set**.

**Consequence for a production deploy of the current branch heads (`feat/admin-issuer-scope` + `feat/trust-plane-phase1`):**
The hardened branches **default to the legacy `ds:airawat:identity` issuer + `airawatos` audience**. So a prod deploy "works" by default coincidence (prod's IdP already issues exactly those), **but two different states apply:**
- **Issuer-scoped ADMIN/PUBLISHER authz (`IDENTITY_HOME_ISS`) is ACTIVE by default** — admin/publisher tokens are honoured only from `ds:airawat:identity`. Prod admin tokens already carry that issuer, so no lockout — but this is implicit; it should be set explicitly.
- **Kernel iss/aud token enforcement is OFF by default** (`IDENTITY_EXPECTED_*` empty). The hardening code ships but does nothing until set.

**What prod must set vs. today:**
| Env | Current branch-head default | Prod today | Action for prod |
|---|---|---|---|
| `IDENTITY_HOME_ISS` (kernel + network) | `ds:airawat:identity` | unset (⇒ default) | **Set explicitly** to prod's real home issuer; verify it equals the IdP's `iss`. |
| `EXPECTED_AUDIENCE` (network) | `airawatos` | unset (⇒ default) | Set explicitly to prod's token audience. |
| `IDENTITY_EXPECTED_ISS` / `IDENTITY_EXPECTED_AUD` (kernel) | empty (no check) | unset (no check) | To turn the §8 enforcement ON: set both, run with `IDENTITY_AUD_ISS_SHADOW=1` to soak, confirm the shadow log is clean, then clear shadow to hard-enforce. |
| `IDENTITY_AUD_ISS_SHADOW` (kernel) | false | unset | Use `1` during soak only. |

**Network canary plan refresh (do NOT run):**
1. Pre-flight: confirm prod IdP `iss`/`aud` (expected `ds:airawat:identity` / `airawatos`); set `IDENTITY_HOME_ISS` + `EXPECTED_AUDIENCE` **explicitly** to those on kernel + network (no behaviour change — makes the implicit default explicit + auditable).
2. Turn kernel iss/aud enforcement to **shadow**: set `IDENTITY_EXPECTED_ISS` + `IDENTITY_EXPECTED_AUD` + `IDENTITY_AUD_ISS_SHADOW=1`; deploy canary; soak; confirm the "would be 401" shadow log is empty across real traffic.
3. Flip to **enforce**: clear `IDENTITY_AUD_ISS_SHADOW`; re-deploy canary; re-run the Gate-2B scenario set; confirm no regression.
4. Keep the prod-guard addition (below) as a hard pre-condition before any of this reaches prod compose.

## §3 status (correction)
Bootstrap Phase 4 records **exactly `network.admin` on the local Network** for the steward — nothing more. It is **not** platform authority and **not** a proxy for it.
**platform.authority is not yet representable — `governance.role_assignment` needs a platform scope and role (next slice; design required).** See the design below.

## Design (NOT implemented) — `governance.role_assignment` v0.2.0: platform scope + `platform.authority`
**Goal:** make "X is the platform authority" a first-class governed record, instead of overloading `network.admin`.
- **Schema delta (0.1.0 → 0.2.0):**
  - add a `scope` block `{ "type": "platform" | "network", "ref": <id> }`; `type:"network"` carries the `net:…` id (today's implicit behaviour), `type:"platform"` carries the platform/operator id.
  - extend the `role` enum with `platform.authority` (kept distinct from the four network stewardship roles).
  - `required` becomes `["schema","id","principal","scope","role","status"]` (the bare `network` field is deprecated → folded into `scope`).
- **Who may assign it:** `platform.authority` may be assigned **once, by the installer/bootstrap** on a fresh platform (the installer *is* the authority, same trust seam as base seeding). After that it is **ChangeRequest-only** — a `governance.change_request` whose approved mutation hash matches. **Separation of duties: the ChangeRequest must be approved by a *different* existing `platform.authority` holder than the proposer** (never self-grant, never a plain token role). So a second holder can only be added with a sitting holder's approval.
- **Revocation floor:** revoking a `platform.authority` holder is refused if it would remove the **last live holder** — the platform must always have ≥1 live authority (prevents locking the platform out of its own governance). Revoking down to zero requires an explicit, separately-designed break-glass path (not this slice).
- **Migration from 0.1.0:** additive + dual-read. 0.1.0 records (role on a bare `network` field) are read as `scope:{type:"network", ref:<network>}`. A one-time migration rewrites them to the `scope` shape; `platform.audit_event` records the rewrite. No 0.1.0 record is destroyed; both shapes validate during the soak.
- **How `is_platform_authority` reads it:** today `is_platform_authority`/admin predicates key on `claims.iss == HOME_ISS` + a namespaced admin role. v0.2.0 adds: *holds a live `governance.role_assignment` with `role == platform.authority` and `scope.type == "platform"` and `scope.ref == <this platform>` and `status == active`* — evaluated by the same `authorize()` candidate-grant path (ADR-0119 D1: "holds a live grant", never "is of type X"). Issuer-scope still applies (the assignment is only honoured for a home-issuer principal).

## Design (NOT implemented) — remove production-pointing defaults; enforce by default
**Goal:** the hardened branches must not silently default to `ds:airawat:identity` / `airawatos` / "no iss-aud check". Instead:
- `IDENTITY_HOME_ISS`, `IDENTITY_ISSUER`, `IDENTITY_AUDIENCE` (and the kernel's `IDENTITY_EXPECTED_ISS` / `IDENTITY_EXPECTED_AUD`) become **required, with NO default** — remove the `, "ds:airawat:identity"` / `, "airawatos"` fallbacks at `kernel/api/kernelcore.py:31`, `network/api.py:208`, `network/api.py:29`, and the empty-set fallbacks at `kernel/services/authn.py:24-25`.
- **iss/aud enforcement ON by default** — `IDENTITY_AUD_ISS_SHADOW` defaults to **false** (enforce); shadow is an explicit, temporary opt-in only.
- **Fail closed at startup** — kernel + network refuse to start (non-zero exit, clear log) if any required issuer/audience setting is unset, so a misconfigured deploy never silently runs with no enforcement.
- **Production guard** gains these to its checked set: under `AIRAWAT_ENV=production`, refuse to start if `IDENTITY_HOME_ISS` / `IDENTITY_EXPECTED_ISS` / `IDENTITY_EXPECTED_AUD` / audience are unset or still equal to the removed legacy defaults.
- **Exact production settings this requires (ship with the next EC2 deploy so it does not break):**
  - identity: `IDENTITY_ISSUER=ds:airawat:identity`, `IDENTITY_AUDIENCE=airawatos`
  - network: `IDENTITY_HOME_ISS=ds:airawat:identity`, `EXPECTED_AUDIENCE=airawatos`
  - kernel: `IDENTITY_HOME_ISS=ds:airawat:identity`, `IDENTITY_EXPECTED_ISS=ds:airawat:identity`, `IDENTITY_EXPECTED_AUD=airawatos`, `IDENTITY_AUD_ISS_SHADOW=1` for the first soak then **cleared**.
  - (These equal the current implicit defaults, so setting them explicitly is a no-op behaviourally — then removing the defaults is safe. Order for EC2: set explicitly → deploy → remove defaults in a later image.)

## Installer-slice backlog
- **Phase 1 base-app delivery re-certifies on every bootstrap re-run** (seed_base_os MODE=deliver re-bundles the 8 base apps even when the artifact digest is unchanged). It must be made **idempotent** — skip certify+bundle when the live listing already matches the source digest — so a bootstrap re-run is a true no-op across *all* phases, not just schema/Network/assignment. (Own slice; design required.)

## Build / deploy notes (carry-over)
- **Local-dev images are native `arm64`** (built on this Apple-Silicon Mac). The first attempt pinned `linux/amd64` and the reference image **segfaulted (exit 139)** on the numpy/scipy/xgboost import-check under QEMU emulation. **Production images MUST be built on a native amd64 builder** (CI / an amd64 host), **never on the Mac via emulation** — the emulated build is both unreliable (segfaults) and slow.
- **The production guard (`prod-guard.sh`) is local-dev-only today** (a compose entrypoint wrapper). Before the next EC2 deploy it **must be added to the production images or the production compose** (as an entrypoint wrapper or a service-startup check), or the "refuse to start under AIRAWAT_ENV=production with a convenience on" protection does not exist in production.

## Validation C.e — role-mode admin authz (NETWORK_ADMIN_AUTHZ=role, local-dev only) — RESULTS 2026-11-03

Driven by **direct network-service calls** (the authorised fallback). Role mode resolves the Network by **slug** → `net:` id, then authorises `claims.sub` against a **live `governance.role_assignment`** on that id; **token `roles` are not consulted** (`network/trust_admin_authz.py:98`, `trust/roles.py:22`). Canonical Network: slug `localdev` = `net:01M6GAD8KXY5FMETWDHC081EPW`. Every decision emits a structured `[admin-authz]` record (allow/deny).

| # | case | token (sub) | endpoint / op | result | evidence |
|---|------|-------------|---------------|--------|----------|
| 1 | steward admin via role | `user://localdev-network/admin` (assign network.admin) | `POST /v1/networks` config | **PASS — ALLOW** | HTTP 200; `[admin-authz] ALLOW op=network.config matched=network.admin` |
| 2 | membership.steward → membership only | `user://localdev-network/memsteward` (assign membership.steward) | decide (membership) **and** networks (config) | **PASS** | membership: HTTP 404 *no participation request* = gate passed, `ALLOW op=membership.decide matched=membership.steward`; config: HTTP 403 `DENY … lacks ['network.admin']` |
| 3 | cross-tenant network.admin by recorded role | `user://localdev/xadmin` (token tenant=**localdev**, assign network.admin on the net) | `POST /v1/networks` config | **PASS — ALLOW** | HTTP 200; `ALLOW op=network.config principal=user://localdev/xadmin matched=network.admin` — authority from the recorded role, not the caller's tenant |
| 4 | faker (token role, no assignment) → deny | `user://localdev-network/faker` (token `roles:[network.admin]`, **no** assignment) | `POST /v1/networks` config | **PASS — DENY** | HTTP 403 `DENY … lacks ['network.admin']` — token roles ignored |
| 5 | federated-issuer token, tenant spoof → rejected, roles stripped | `contract-local` (federated, bound to tenant `localdev-participant`) | `POST /v1/networks` | **PASS — REJECTED** | 5a spoof `tenant=airawat` → HTTP 401 `issuer/tenant mismatch: contract-local may assert only tenant 'localdev-participant', not 'airawat'`; 5b correct tenant + `roles:[network.admin]` → HTTP 403 at the role gate (roles stripped, `authn.py:166`; no assignment) — federated token confers **zero** admin authority |
| 6 | Kernel admin endpoint, non-home-issuer token → denied (+ audit) | `contract-local` (non-home) / `user://localdev/outsider` (home, non-admin) | `POST /v1/registry/usage` | **PASS — DENIED** | 6a non-home → HTTP 401 `no jwks configured` (kernel never trusts a non-home issuer; rejected at verify, **before** the gate, so **not** audited); 6b home-issued non-admin → HTTP 403 + **durable** `kernel_admin_audit`: `deny \| user://localdev/outsider \| iss=ds:localdev:identity \| registry.usage` — audit-on-deny proven |
| 7 | production guard | — | `prod-guard.sh` | **PASS** | `AIRAWAT_ENV=production` + `AIRAWAT_ALLOW_PASSWORDLESS=1` → **exit 97**, `REFUSING TO START … passwordless-login`; `AIRAWAT_ENV=development` → exit 0, pass-through |

**All 7 checks PASS.** No bridge was used for 1–4 (direct network-service calls, the authorised fallback) — so no bridge-tenant-resolution Commit-D finding was exercised here; the bridge-selection probe is deferred to when the console path is driven.

### C.b extra case (role mode) — known gap confirmed, NOT fixed
`memsteward` (membership.steward) approved a **federated issuer registration** via `POST /v1/participation/decide` → **HTTP 200, `trust_established=True`**. Issuer registration rides on `participation.decide` (`op="membership"`, which `MEMBERSHIP_ROLES` grants to membership.steward), so **it is not restricted to network.admin**. Recorded as the known gap *"issuer registration not yet restricted to network.admin"* — **left unfixed** per instruction.

### Findings from C.e
1. **Role mode requires a Trust-store reader that was unconfigured.** `require_network_admin_role → _reader_from_env()` (`network/trust_admin_authz.py:87`) fail-closes to **HTTP 503** unless **`KERNEL_URL` and `TRUST_READ_TOKEN`** are both set on the network container; the committed `docker-compose.dev.yml` set `NETWORK_ADMIN_AUTHZ=role` but neither companion, so checks 1–4 initially returned 503 (*trust_store_unavailable*). Fixed for this run by injecting both via a **job-local override** (not committed; the token is an ephemeral secret).
2. **No durable service credential exists for `TRUST_READ_TOKEN`.** The reference identity service issues **1-hour** tokens only (`identity.py:364`, `exp = now + 3600`); there is no long-lived service token. A long-running network service in role mode therefore needs a **token-refresh mechanism** (or a dedicated service-credential path) before role mode can be left on durably — otherwise it reverts to 503 when the token expires or on any plain container restart. **Design item, not yet built.**
3. ~~**Federated issuer registrations are in-memory**~~ **(CORRECTED below — this was a mis-read).** The C.e run believed the C.b handshake was lost on `--force-recreate`; it was not. See the durability reconcile in the follow-up section — trusted-issuer registration **is durable** (Postgres KV write-through + startup rehydration). The "lost" reading came from inspecting `authn._TRUSTED` in a *separate* `compose exec python3` process (its own empty module singleton), not the live uvicorn worker.

> Note: checks were run inside the container against the live uvicorn worker over HTTP. Some diagnostic `authn._TRUSTED`/direct-`verify` readouts in-script printed `NO`/`unknown signing key` because `compose exec python3` is a **separate process** with its own empty `authn` singleton — the HTTP responses (which hit the real worker) are the authoritative evidence.

## Validation C — follow-up (2026-11-03): bridge e2e · durability reconcile · mint-on-demand · kernel auth-logging

### 1. Durability reconcile — trusted issuers ARE durable (no fix needed)
The handshake write path, with file:line:
- `POST /v1/participation/request` stores `issuer` + `jwks` into the participation rec (`network/api.py:838-847`); `PARTICIPATION` is a durable namespace.
- `POST /v1/participation/decide` approve → `TRUSTED_ISS[iss] = {...}` + `authn.register_issuer(...)` (`network/api.py:866-876`). `TRUSTED_ISS = _NS["trusted_issuers"]` (`network/api.py:100`) is a **durable** namespace.
- `Namespace.__setitem__` → `kv.put` → Postgres `INSERT … ON CONFLICT DO UPDATE` with `autocommit=True` (`network/kv.py:64-65`, `kv.py:33-34`) — an immediate durable write-through.
- At boot the service **rehydrates** every stored issuer into the verifier (`network/api.py:104-107`).

**Proof:** durable `kv` rows (store=`trusted_issuers`) survived a `--force-recreate`; a fresh worker then rejected a spoof token from `contract-local` with `issuer/tenant mismatch` over HTTP (requires the issuer registered + signature verified against the rehydrated key) — not `no jwks configured`. So **no code change** — the prior "lost on recreate" was a diagnostic artifact (a separate `compose exec` process has its own empty `authn._TRUSTED`; the live uvicorn worker rehydrated correctly).

### 2. Mint-on-demand TRUST_READ_TOKEN — BUILT (network `feat/trust-plane-phase1` @ 56fd371; image dev-56fd371)
Role mode no longer needs a manual token. `network/trust_admin_authz.py`:
- `_read_token()` — static `TRUST_READ_TOKEN` wins if set (tests/break-glass); otherwise mint-on-demand, cached, re-minted ~120s before expiry.
- `_mint_reader_token()` — reads the **dedicated read-only principal**'s password from **Vault** (`VAULT_ADDR`/`VAULT_TOKEN` + `TRUST_READER_VAULT_PATH`), logs in at the **local identity service** (`IDENTITY_URL`/realms/`TRUST_READER_TENANT`), returns `(token, exp)`.
- Principal: `trust-reader@localdev-network`, role `[]` — **never `platform.service`** (registry reads are tenant-scoped via `kernel/api/app.py` `_read_scope`, so a bare member reads only its own tenant's Trust records).
- Fail-closed: no `KERNEL_URL`, Vault down, missing secret, or IdP down → HTTP **503**.
- `bootstrap-dev.sh` **Phase 5** provisions the principal + Vault password (idempotent — reuses an existing password, no rotation).
- Compose now sets `NETWORK_ADMIN_AUTHZ=role` + `KERNEL_URL` + `TRUST_READER_{TENANT,PRINCIPAL,VAULT_PATH}` and **no `TRUST_READ_TOKEN`**.

**Proven locally:** role mode ALLOW (admin→config 200) / DENY (faker→config 403) with the manual token unset; **fail-closed 503** (`reader-token mint failed (HTTP Error 404)`) when the Vault path is wrong. The credential rotates transparently as the 1-hour IdP token nears expiry — the durability gap from C.e is closed for the admin-plane reader.

### 3. Bridge end-to-end (required) — checks 1–4 through the App Host console bridges
Real `POST /login` browser sessions (cookie `airawat_sid`) → `POST /bridge/network-configure` (→ `/v1/networks`, config) and `POST /bridge/network-decide` (→ `/v1/participation/decide`, membership). Slug `localdev` ≠ admins' tenant `localdev-network`. Check 2 used a **real pending membership request**.

**Prerequisite discovered:** the bridge's role-based network gate `_manageable_networks` (`app_host.py` ~4075) calls `GET /v1/governance/networks/mine`, which belongs to the **ADR-0119 Trust plane** — a *separate* subsystem from the Commit-D admin-plane role authz, env-gated by `TRUST_PLANE_ENABLED` + `TRUST_KERNEL_URL`/`TRUST_REGISTRY_TOKEN`/`TRUST_AUDIT_HMAC_KEY` (`network/trust_wiring.py:81-89`, registered at `network/api.py:3633`). With it off (local-dev default) `networks/mine` 404s, so no role-based selection can be verified and every admin 403s **at the bridge** except the tenant-collision case. Enabled transiently (minted read token) for this validation; then `networks/mine` returned the correct role-derived sets (admin/memsteward/xadmin → `[localdev]`, **faker → `[]`**).

| # | principal (session tenant) | bridge | HTTP | how the bridge resolved the Network |
|---|----------------------------|--------|------|-------------------------------------|
| 1 | admin (localdev-network) | network-configure | **200 ALLOW** | **by selection + recorded role** — `networks/mine` verified `localdev` → forwarded slug (`app_host.py:4094-4096`); network authority `matched=network.admin` |
| 2a | memsteward (localdev-network) | network-decide (real pending req) | **200** | **by selection + role** — forwarded slug; authority `matched=membership.steward` |
| 2b | memsteward (localdev-network) | network-configure | **403** | **by selection + role** — authority DENY `lacks ['network.admin']` (not the bridge) |
| 3 | xadmin (**localdev**) | network-configure | **200 ALLOW** | **by CALLER TENANT** — `app_host.py:4092` (`requested == tn`) short-circuits because xadmin's tenant `localdev` **equals the slug**; `networks/mine` is bypassed. Forwarded key is still correct and the authority re-checked the role (`matched=network.admin`). **Finding.** |
| 4 | faker (localdev-network) | network-configure | **403** | **by selection + role** — DENY **at the bridge** (`app_host.py:4097`): faker's `networks/mine` is `[]`, so the selection isn't in the manageable set; the request never reaches the network authority |

**Findings (step 2):**
- **F1 (tenant==slug collision, `app_host.py:4092`):** when a caller's session tenant equals the selected Network's slug, `_resolve_read_network` returns `(tenant, True)` via the legacy own-tenant shortcut *before* consulting `networks/mine`, so resolution is by **caller tenant**, not recorded role (check 3). Harmless when the forwarded key matches and the authority re-checks the role, but it means the bridge's role-verification is skipped on that path. Keeping Network slugs distinct from every admin's tenant avoids it; a stricter fix would consult `networks/mine` even when `requested == tenant`.
- **F2 (bridge depends on the ADR-0119 Trust plane):** the console's role-based selection is unusable unless `TRUST_PLANE_ENABLED` + its kernel/token/HMAC config are set — a heavier subsystem than the admin-plane role authz. Its `TRUST_REGISTRY_TOKEN` is read once at boot (`register_trust_endpoints`), so the mint-on-demand pattern (per-request refresh) does not drop in directly; enabling the Trust plane durably in the committed local-dev compose is a follow-up slice (extend mint/refresh to the Trust store, or accept a boot-time token). For this validation it was enabled transiently.

### 4. Kernel — log failed authentication on admin endpoints (DESIGN NOTE ONLY, not built)
Today `kernel/api/kernelcore.py` `_authenticate` raises `401 "invalid token: {err}"` on a bad/unknown-issuer token (`kernelcore.py:~40`) **before** any endpoint handler runs, and the durable `kernel_admin_audit` is written only inside `_require_admin` (`kernel/api/app.py:29-41`) — which a failed-auth request never reaches. So an **unknown-issuer / bad-signature / bad-audience attempt on an admin endpoint is invisible to monitoring** (only *verifiable-but-unauthorized* calls are audited, as shown in C.e check 6).

**Proposed (design):**
- Add a lightweight **auth-failure log** at the `_authenticate` reject point: emit a structured record `{ts, event:"auth_failure", issuer:<unverified iss, parsed best-effort>, reason:<err>, source_ip:<X-Forwarded-For/peer>, path:<request path>, method}` to stderr (so it lands in container logs) and, optionally, to the same `kernel_admin_audit` sink with `decision:"auth_failure"` so admin-surface monitoring has one table.
- Parse the issuer **without trusting it** (decode the JWT payload for display only; never use it for a decision) so a flood of forged-issuer attempts is attributable.
- Scope: log on **every** endpoint or at least the admin-gated set; rate-limit/sample to avoid log amplification from a hostile client. Keep it a pure side-effect (never changes the 401).
- Boundary: this records *attempts*; it does not widen what authenticates. Pairs with the existing allow/deny audit so the admin surface has both "unauthorized by a known principal" and "unauthenticated/forged" visibility.

### Current local-dev resting state
Network on `dev-56fd371`, `NETWORK_ADMIN_AUTHZ=role` via **mint-on-demand** (no manual token), `TRUST_PLANE_ENABLED` **unset** (Trust-plane/console-bridge path is enabled only transiently for validation — see F2). All committed: outer repo `docs/trusted-network-platform-adr-0119-0120` (compose+bootstrap+PLAN), network repo `feat/trust-plane-phase1` @ 56fd371 (both pushed, no merge).

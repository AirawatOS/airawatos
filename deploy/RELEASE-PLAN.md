# Production release plan — ADR-0124 (dedicated service identities) + ADR-0122 (platform.authority) + #282 (password hygiene)

**Status: PLAN ONLY. Nothing here has been applied to production.** EC2 (`airos.airawat.org`,
13.205.13.220) is the frozen demo box; it was touched only by read-only audits.

This plan rolls out everything hardened since the **current EC2 images**:

| service | current EC2 image | ships as |
|---|---|---|
| kernel | `airawatos-kernel:0.2.25-authn-observe` | **env-only** change (confirm support) or a pinned rebuild |
| network | `airawatos-network:0.3.7-trust-m1m2` | new amd64 image from `network` HEAD |
| reference (identity, app-host, automation, event-relay, scheduler) | `airawatos-reference:0.2.x` (several tags) | new amd64 image from `platform-spec` HEAD |

The EC2 images **predate the entire ADR-0124/0122/#282 series**, so the whole series below is the delta.
Confirm each image's exact source commit from its OCI label at build time; the ranges below are the authority.

---

## 1. Commit range per repo

All three are on feature branches; **no merge** has happened. Exact baselines are the commits the live EC2
images were built from (read from image labels); the series to ship:

- **network** (`github.com/AirawatOS/network`, branch `feat/trust-plane-phase1`) — `1211be4..93dd2c3`:
  - `1211be4` ADR-0122 P3: stable network token for platform-scope CR binding
  - `f0edcc1` Step 1 — scheduler Vault-backed password
  - `4923bad` Steps 2+3 — component-publisher + dev-sandbox principals
  - `8d7dc55` item (a) — narrow `component.publisher` role (NOT platform.steward)
  - `701da6c` item (b) — embed-service principal
  - `abc2a34` scheduler audience allow-list
  - `6136110` floor-role read-path provenance gate + governed retire-by-id
  - `93dd2c3` steward provenance re-seed migration + no-literal/never-reset install creds
- **platform-spec** (`github.com/AirawatOS/platform-spec`, branch `feat/network-console-multinetwork`) — `d61e132..2258d09`:
  - `d61e132` Steps 2+3 — app-host stops borrowing steward/devrick; audience-bound `/events`
  - `e5db266` item (a) — bundle publish + cross-tenant reads → component-publisher
  - `6e13cd7` item (b) — embed-service principal (stop borrowing scheduler)
  - `0c339f6` Step-4 fix — `/login` threads `body["aud"]` into `issue()`
  - `c9c7533` recorded per-principal audience allow-list at `/login`
  - `2258d09` identity `only_if_unset` + production default-password boot guard
- **airawatos** (`github.com/AirawatOS/airawatos`, branch `docs/trusted-network-platform-adr-0119-0120`) — `beedad5..HEAD`:
  conformance cases (audience allow-list, component-publisher refusals, dev-sandbox confinement, platform-authority
  bootstrap rule), the enforce/retag compose, bootstrap no-literal + Phase-9 convention, DEBT-REGISTER A65–A70,
  PRODUCTION-READINESS §8, and this plan.
- **kernel** — the only kernel change is the `PLATFORM_SERVICE_ROLES` env (scoped cross-tenant reach for
  `component.publisher` / `platform.scheduler`). **Confirm `0.2.25-authn-observe` honours it**; if not, bump the
  kernel image to the commit that reads `PLATFORM_SERVICE_ROLES`. No kernel code change is in this series.

> Branches are not merged to `main`. Either merge to `main` first and build from the merge commit, or build
> each image from the pinned branch HEAD and record the SHA in the image label + the prod compose comment.

---

## 2. Required settings (prod env) and secrets (Vault)

### 2a. Settings — set explicitly, never defaulted

Carried from PRODUCTION-READINESS §2/§4/§5 (identity envelope, trust plane, trust-reader/writer) **plus** the
new knobs from this series:

| env | service | value at ship | notes |
|---|---|---|---|
| `AIRAWAT_ENV` | all | `production` | activates both guards (prod-guard.sh dev-convenience check + the new account-password guard) |
| `PLATFORM_SERVICE_ROLES` | kernel | `platform.steward,platform.scheduler,platform.service,component.publisher` | scoped cross-tenant reach; NOT admin. Confirm kernel honours it |
| `KERNEL_REQUIRE_STEWARD_GRANT` | kernel | `1` | as local-dev |
| `IDENTITY_PASSWORD_REQUIRED` | identity | `shadow` → `enforce` | flip in §5 after all accounts have passwords |
| `AUTOMATION_EVENTS_REQUIRE_TOKEN` | automation | `0` → `1` | flip in §5 after event-relay mints svc:automation tokens |
| `PLATFORM_AUTHORITY_MODE` | network | `shadow` → `enforce` | ADR-0122; flip in §5 after seeding a holder |
| `TRUST_ENFORCE_STEWARD_PROVENANCE` | network | `0` → `1` | A70; flip in §5 after the reseed no-op |
| `SERVICE_PRINCIPAL` / `SERVICE_TENANT` / `SERVICE_TOKEN_AUDIENCE` | reference services | `scheduler` / `<inst>-operator` / `airawatos` | x-svc-identity anchor; the daemons share one principal (debt A68) |
| `COMPONENT_PUBLISHER` / `COMPONENT_PUBLISHER_TENANT` | app-host | `component-publisher` / `<inst>-network` | cross-tenant publish on-behalf-of |
| `DEV_SANDBOX` / `DEV_SANDBOX_TENANT` | app-host | `dev-sandbox` / `<inst>-developer` | dev-token mint + sandbox seeding only |
| `EMBED_CLIENT_PRINCIPAL` / `EMBED_CLIENT_TENANT` | app-host | `embed-service` / `<inst>-operator` | platform.app_client own-tenant |
| `VAULT_ADDR` | network + app-host + reference svcs | prod Vault URL | token NOT in compose — see 2c |

Everything in PRODUCTION-READINESS §2 (iss/aud envelope), §4 (`TRUST_PLANE_ENABLED`, audit HMAC path,
`TRUST_AUTHORITY_TENANT=airawat`), §5 (trust-reader) and §3 (prod-guard) still applies and is a prerequisite.

### 2b. Secrets — provision in Vault BEFORE the services that read them

One convention for every provisioned credential: **path `secret/data/<tenant>/<principal>/password`, field
`password`** (KV v2). (`#282` reconciled the old `test-users/<u>`/`value` shape onto this; the trust-reader/writer
paths historically use field `value` under the same path tail — leave those as the mint path expects, debt-note).

- `secret/data/<inst>-operator/scheduler/password` — scheduler daemon (ensure_install generates, idempotent)
- `secret/data/<inst>-network/component-publisher/password` — **must exist + be publish-capable before enforcing passwords**
- `secret/data/<inst>-developer/dev-sandbox/password`
- `secret/data/<inst>-operator/embed-service/password`
- `secret/data/<inst>-operator/admin/password` — operator admin initial password (generated unless the operator sets one)
- `secret/data/<inst>-network/trust-reader/password`, `.../trust-writer/password` (PRODUCTION-READINESS §4/§5)
- audit HMAC at `TRUST_AUDIT_HMAC_VAULT_PATH` (≥16-byte hex)
- (only if running conformance on prod) `secret/data/<inst>-network/{platauth,platnone}/password`

`network/ensure_install.py` provisions the service credentials + realm admins idempotently (generates into
Vault, never resets an existing one). Run it on the prod bootstrap after the network image is up.

### 2c. Vault unlock via instance identity

Prod Vault must be **unsealed without a human-held root token in compose**:
- Use auto-unseal (AWS KMS seal) **or** the instance's IAM role via Vault AWS-auth to obtain a short-lived token
  at boot; the services read their own secret paths with a policy scoped to `secret/data/<their-tenant>/<their-principal>/*`.
- Confirm the unseal path survives an instance reboot (the disk-full incident showed Postgres can come back
  unhealthy — the same reboot must re-unseal Vault or every mint fails closed and all logins/daemons break).
- **Do not** put a long-lived `VAULT_TOKEN` in the prod compose. The mint helpers (`svc_token.py`,
  trust-reader/writer) fail **closed** — a missing/expired token means no token minted, not a bypass.

---

## 3. Schema migrations

1. **`governance.role_assignment@0.2.0`** (ADR-0122 — adds `scope`). Govern it, then **reload the kernel** so
   its boot-cached schema validator accepts 0.2.0 (a running kernel 422s a freshly-governed version until
   reload; a fresh install is unaffected). EC2 network is `0.3.7-trust-m1m2` — verify whether 0.2.0 is already
   governed on EC2 (it likely is, since trust-m1 shipped); if present, this step is a no-op confirmation.
2. **Steward provenance reseed** (`network/trust/migration/reseed_steward_provenance.py`, A70) — **a no-op on
   EC2**: the read-only survey (2026-11-05) found EC2's single live steward record (`network.admin` for
   `user://airawat/steward`) already carries `op_id` + a matching `role.assign` audit. Run the migration anyway
   (idempotent; it will report `reseeded=0, retired_legacy=0, skipped_already_governed≥1`) as the gate's
   precondition, then it is safe to flip `TRUST_ENFORCE_STEWARD_PROVENANCE=1`.
3. **No data migration** for the floor-role provenance gate or the password changes — they are read-path /
   startup logic, not stored-shape changes.

---

## 4. Order of image rollouts

Dependencies: ensure_install (network image) must provision the service principals + Vault creds **before**
app-host (reference image) stops borrowing steward/devrick; `component.publisher` must be publish-capable
**before** passwords are enforced. So:

1. **kernel** — recreate with `PLATFORM_SERVICE_ROLES` (env-only if `0.2.25` honours it; else pinned rebuild).
   Canary: health + an existing governed read/write still work.
2. **network** (new image) with the new flags **OFF** (`PLATFORM_AUTHORITY_MODE=shadow`,
   `TRUST_ENFORCE_STEWARD_PROVENANCE=0`). Then **run `ensure_install.py`** (provisions scheduler /
   component-publisher / dev-sandbox / embed-service + their Vault creds, + realm admins, idempotent) and the
   **reseed migration** (no-op). Canary: service-principal logins mint audience-bound tokens; `component-publisher`
   can publish a component (on-behalf-of) end-to-end.
3. **reference** (new image) for **identity + app-host + automation + event-relay + scheduler**, with
   `IDENTITY_PASSWORD_REQUIRED=shadow` and `AUTOMATION_EVENTS_REQUIRE_TOKEN=0` still. Canary: human + embed +
   consumer logins succeed; daemons authenticate with their Vault-backed service tokens; `/events` still accepts
   (shadow) but logs would-refuse for un-tokened posts.

Keep each image pinned by **digest** in the prod compose. Build all three on a **native amd64 builder**
(PRODUCTION-READINESS §1 — the reference image segfaults under QEMU cross-emulation; never build on the Mac).

---

## 5. Flags to flip — shadow → enforce (in this order, each its own change window)

Only after §4 is deployed-and-green and every account/principal has a real Vault-backed credential:

1. **`PLATFORM_AUTHORITY_MODE=shadow → enforce`** (network). Precondition: ≥1 recorded `platform.authority`
   holder at platform scope for the steward (ADR-0122 phase-4b seed, through the governance path). Soak shadow,
   confirm the divergence log shows the steward `recorded==true`, then enforce.
2. **`TRUST_ENFORCE_STEWARD_PROVENANCE=0 → 1`** (network). Precondition: the reseed migration reported no
   un-provenanced active steward records (no-op on EC2). After the flip, un-provenanced steward records are
   ignored by the read path.
3. **`AUTOMATION_EVENTS_REQUIRE_TOKEN=0 → 1`** (automation). Precondition: event-relay (reference image) mints
   `svc:automation` tokens for `/events` delivery.
4. **`IDENTITY_PASSWORD_REQUIRED=shadow → enforce`** (identity). Preconditions (ALL): the account-password audit
   returns 0 default/literal offenders (PRODUCTION-READINESS §8); **`component-publisher` is provisioned and
   proven publish-capable** (so marketplace/publish keeps working once passwordless is gone); the **human
   steward** and every human admin have a real password; the service daemons have their Vault creds. Soak shadow
   (identity logs "SHADOW would-refuse passwordless"), confirm the log is empty for real traffic, then enforce.
5. **Account-password guard** rides `AIRAWAT_ENV=production` — it is already active once the guarded reference
   image boots under production. It is a **boot gate**, so it is effectively "flipped" at step §4's reference
   rollout; ensure §8's audit is 0 **before** that image boots, or identity will refuse to start.

Rationale for the order: authority first (so governance stays operable), then steward-provenance (read-path,
low blast radius), then the automation token, then the passwordless cutover **last** — because it is the most
likely to lock something out, and it depends on every service principal and `component-publisher` already working.

---

## 6. Canary checks per step

| step | canary (must pass before proceeding) |
|---|---|
| kernel | `/kernel/v1/health` 200; one existing governed resolve + one governed write still succeed |
| network image (flags off) | `/network/v1/health` 200; `networks/mine` unchanged; a service principal `/login` with its recorded audience returns a token, a disallowed audience → 403 |
| ensure_install | each of scheduler / component-publisher / dev-sandbox / embed-service exists with a Vault cred; `component-publisher` publishes a test component on-behalf-of a developer end-to-end |
| reseed migration | reports `failed=0`; survey shows 0 active steward records lacking provenance |
| reference image (flags off) | human login 200; embed + consumer login 200; daemons post/mint successfully; site 200 |
| PLATFORM_AUTHORITY enforce | steward `networks/mine` shows `platform_authority=true`; a non-holder shows false; grant-without-CR and last-holder-revoke both refused (403) |
| STEWARD_PROVENANCE enforce | the live `network.admin` steward still resolves (honoured via its governed record); admin console still administrable |
| AUTOMATION token | `/events` accepts an event-relay svc:automation token; rejects an un-tokened post (and a wrong-audience token) |
| IDENTITY enforce | a passwordless login attempt → 401 "password required"; all real logins still succeed; publish/marketplace still works via component-publisher |
| prod guard (boot) | identity boots (no default-password account); flip one account to a weak password in a throwaway and confirm it refuses (do NOT do this on the live file) |

Each canary is black-box where possible; the `conformance/run.py` external suite (with `AOS_TEST_USERS` /
`.creds.json`) covers the authority + audience + refusal cases and should be green post-cutover.

---

## 7. Rollback per step

Every step rolls back independently; nothing in this series requires a destructive data change, so rollback is
redeploy-previous-digest + revert-env.

| step | rollback |
|---|---|
| kernel | redeploy `0.2.25-authn-observe` digest; clear `PLATFORM_SERVICE_ROLES` |
| network image | redeploy `0.3.7-trust-m1m2` digest. The reseed only ADDED governed records + retired legacy duplicates; it is forward-safe, but if reverting the image, also set `TRUST_ENFORCE_STEWARD_PROVENANCE=0` so the old image's steward reads are unaffected |
| reference image | redeploy the previous `0.2.x` digests; set `IDENTITY_PASSWORD_REQUIRED=shadow`, `AUTOMATION_EVENTS_REQUIRE_TOKEN=0`. App-host reverts to its prior principal wiring |
| PLATFORM_AUTHORITY enforce | set `PLATFORM_AUTHORITY_MODE=shadow` (tenant rule becomes authoritative again; the recorded holder stays recorded — no data change) |
| STEWARD_PROVENANCE enforce | set `TRUST_ENFORCE_STEWARD_PROVENANCE=0` (un-provenanced steward records are honoured again) |
| AUTOMATION token | set `AUTOMATION_EVENTS_REQUIRE_TOKEN=0` |
| IDENTITY enforce | set `IDENTITY_PASSWORD_REQUIRED=shadow` — **the fastest unlock if a real account gets locked out**. (This is why passwordless is cut over last and behind its own window.) |
| prod guard refuses boot | the guard fired because an account is on a default password — **do not disable the guard**; rotate the offending account's password (POST `/set-password`) and reboot. Disabling `AIRAWAT_ENV=production` also lifts the dev-convenience guard, so only do that as a deliberate, logged exception |

Keep the previous digests pinned and recorded for the whole window. A full abort = revert all three images +
all flags to the pre-cutover values; the only durable side effects are additive (governed steward records,
Vault credentials, generated admin passwords) and are inert when the old images run.

---

## 8. Pre-flight gate (must all be ✅ before step §4's reference rollout)

- [ ] amd64 images built from pinned SHAs, pushed by digest, digests pinned in prod compose (PRODUCTION-READINESS §1).
- [ ] Prod guard shipped in the images/compose; `AIRAWAT_ENV=production`; no dev conveniences (PRODUCTION-READINESS §3).
- [ ] Vault unsealed via instance identity; mint paths reachable; survives reboot (§2c).
- [ ] Account-password audit returns **0** default/literal offenders (§PRODUCTION-READINESS-8).
- [ ] Human **steward** + operator **admin** have real Vault-backed passwords; not passwordless.
- [ ] `component-publisher` provisioned and proven publish-capable (before passwords are enforced).
- [ ] identity envelope (iss/aud) set to prod, one shadow soak clean (PRODUCTION-READINESS §2).
- [ ] trust-reader / trust-writer / audit HMAC provisioned (PRODUCTION-READINESS §4/§5).
- [ ] `governance.role_assignment@0.2.0` governed + kernel reloaded; reseed migration run (no-op).

_Generated as a plan for the next EC2 deploy. Nothing has been applied to production._

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

Sequence at a glance: **Stage 0** (backups + restore drill) → **Stage 0b** (housekeeping) → **Stage 0c**
(production compose variant `deploy/prod` + installer support — prerequisite) → **Stage 1** (full rehearsal on
an amd64 copy of prod) → §4 image rollouts → §5 enforce flips (one observed step each) → §8 gate.
Do not start §4 on production until Stage 0, 0b, 0c and 1 are green.

---

## Hotfixes awaiting production (local-dev verified; the §4 image rebuilds MUST include them)

Security fixes landed and verified in **local-dev** since the current EC2 images, each proven by a conformance
case and/or unit test. They are **not on EC2** (EC2 was touched only by read-only audits). The §4 image
rollouts rebuild amd64 images from each repo's HEAD, so they carry these commits — but the local `dev-hard*`
tags they were baked into are local-only and **must not** be shipped (Stage 0b removes `dev-*` images). Confirm
each production image's OCI source-commit label covers the commit below.

**Headline hotfixes:**

| DEBT | fix | repo · commit | prod image (rebuild from HEAD) | verified in local-dev |
|---|---|---|---|---|
| **DEBT-B22** | admin-gate `/v1/components/install` before any processing — close the unauthenticated run-token mint (FND-8) | kernel `b04b8d9` · conformance `881fb25` | `airawatos-kernel` (local bake tag `dev-hard6`) | FND-8 unauth-install XFAIL→PASS; EC2 read-only check confirmed kernel is not publicly routed |
| **DEBT-B28** | roleless account-create ⇒ **no** roles (never `platform.tenant-admin` by omission); installer Phase-9 double-POST workaround removed | platform-spec `6d5e319` · root `448e855` | `airawatos-reference` (local bake tag `dev-hard9`) | unit `test_identity_hotfix_b28_b29.py` + live `FND-1/DEBT-B28` PASS; fresh install platauth/platnone roles=(none) |
| **DEBT-B29** | identity account-write gates fail **closed** on unset/empty `IDENTITY_INTERNAL` (clear error) + `assert_internal_secret_configured` refuses production boot without it; committed literal default removed | platform-spec `6d5e319` · root `448e855` | `airawatos-reference` (`dev-hard9`) | unit test (empty-secret fail-closed + prod boot refusal) + live `FND-9/DEBT-B29` PASS |
| **DEBT-B33** (CRITICAL) | `POST /v1/participants` (federation trust-directory admission) requires an authenticated admin/steward of the participant's OWN tenant — closes anonymous key-binding → federation-message/credential forgery (NET-12/PTC-1/FED7). **Live + internet-reachable on EC2 today** (`0.3.5` via `/network/v1/participants`) — see §nginx-containment. | network `8fe46b7` · root `12d0a97` | `airawatos-network` (local bake `dev-a75`) | live `PTC-1/FED7/DEBT-B33` PASS (anon → 401); verified live on EC2 image (unauth → 200 before fix) |
| **DEBT-B34** (CRITICAL) | `POST /v1/grants` + `/v1/grants/revoke` (capability-grant store the kernel/broker enforce) require a recorded admin/steward of the grant's tenant — closes anonymous privilege grant (NET-9). **Live + internet-reachable on EC2 today** (`0.3.5` via `/network/v1/grants`) — see §nginx-containment. | network `fc849e5` · root `12d0a97` | `airawatos-network` (`dev-a75`) | live `NET-9/DEBT-B34` PASS (anon → 401); verified live on EC2 image (unauth well-formed → 200 `{stored}` before fix). Residual: steward-signature verify + grammar/version/no-wildcard (DEBT-B12) |
| **DEBT-B35** (CRITICAL) | zero-holder `platform.authority` first-holder bootstrap is installer-only (`ctx.is_installer`), never reachable via the governance API (FND-11). **Absent on EC2** (`0.3.5` has no trust plane / `/v1/governance/roles` → 404) — must be fixed **before** a trust-plane image (`0.3.7+`) reaches production. | network `6f13276` · root `4993354` (installer) | `airawatos-network` (`dev-a75`) | unit test `test_bootstrap_installer_only_b35.py` (governance-path self-escalation REFUSED; installer seed allowed) |
| **DEBT-B36** | `GET /v1/participation` members-only (auth + membership/admin); `POST /v1/service/search` members-only by default (anon sees only `visibility=="public"`) (NET-12/REG-15). Member list is internet-readable on EC2 today (`/network/v1/participation`). | network `b534de7` · root `12d0a97` | `airawatos-network` (`dev-a75`) | live `NET-12/DEBT-B36` PASS (anon participation → 401; anon search leaks 0 members-only). Residual: `/v1/service-offerings` + `/v1/federation/offerings` public reads not yet gated |

**Earlier local-only hardening also awaiting production** (same image rebuilds; each with its commit):

*Identity (`platform-spec`):* `8c0b7e5` `/users` POST merges, never clobbers (DEBT-A73) · `830ee7c` PBKDF2-SHA256
@600k + rehash-on-login · `2d48721` durable+shared brute-force lockout (Postgres, memory fallback) · `1fcf41f`
lockout DB as least-privilege role, password from Vault · `f72e9bd` alert on lockout-store fallback + mode on
`/healthz` · `258c6f0` `svc:filestore` ingress gate (shadow) · `ad729f7` component delivery surfaces registry
write failures (never false success, D1).

*Kernel (`kernel`):* `021fa22` issuer-scope admin authority + drop bare slugs + durable admin audit · `ad6fd0c`
admin-gate `GET /v1/components` + strip `run_token` (DEBT-B15) · `ae8d01f`+`ac3a24f` 4b least-privilege DB
(kernel boots as non-superuser `kernel_app`; migrator owns DDL).

These are additive to — not a replacement for — the ADR-0124/0122/#282 series that the rest of this plan rolls
out; they are called out here so the §4 rebuilds and the §8 gate explicitly account for them.

### EC2 interim containment (DEBT-B33/B34) — apply NOW, before the §4 network rebuild

> **Status 2026-11-06 (read-only forensics):** NOT yet applied. The live on-box `~/airawatos/nginx.conf`
> (== `airawat-nginx` container config, == committed `deploy/ec2/nginx/nginx.conf`, sha256 `db08240…`) still
> has a bare `location /network/` with no deny; external probes return 400/500 (handler reached), not 403.
> B33/B34 remain internet-exploitable until the block below is applied or the `dev-a75`-based image ships.
> Forensics also confirmed **no exploitation to date**: the network access log (since 2026-11-02, 1.3M lines,
> unrotated) has **zero successful (2xx) POST** to `/v1/participants` or `/v1/grants`; all 261 grants carry a
> steward `grantor`+`approved_by`; all 31 participants are known tenants (one off-pattern id `ds:pune:participant`
> to confirm, benign — same key as `ds:pune:steward`).


The current EC2 network image (`0.3.5-dev-tenant-ensure`) exposes `POST /network/v1/grants` and
`POST /network/v1/participants` **unauthenticated and internet-reachable** (the `location /network/` block
blanket-proxies the whole service). Until `dev-a75`→a pinned prod tag ships, block the two write paths at the
on-box nginx (`~/airawatos/nginx.conf`, container `airawat-nginx`). Insert **before** `location /network/ {`:

```nginx
# SECURITY CONTAINMENT (DEBT-B33/B34) — internal app-host→network calls are unaffected (they bypass /network/).
location = /network/v1/grants         { return 403; }
location = /network/v1/grants/revoke  { return 403; }
location = /network/v1/participants {
    if ($request_method != GET) { return 403; }     # block POST admission; keep GET directory read for pages
    set $up_network network:8090; rewrite ^/network/(.*)$ /$1 break; proxy_pass http://$up_network;
    proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Apply: `cd ~/airawatos && cp nginx.conf nginx.conf.bak.$(date +%s)`, insert, then
`docker exec airawat-nginx nginx -t && docker exec airawat-nginx nginx -s reload`.
Verify: anon `POST /network/v1/{grants,participants}` → 403; `GET /network/v1/participants` + `/health` → 200;
`POST /network/v1/participation/request` → not 403 (public join intact).
Undo: restore `nginx.conf.bak.<ts>` + reload. (B35 needs no containment on EC2 — the trust-plane governance API
is absent on `0.3.5`; it must be fixed before a `0.3.7+` image is deployed.)

---

## 0. Stage 0 — backups + restore drill (before touching anything)

A deploy that flips authentication/authority enforcement must be recoverable to the exact pre-cutover state.

- [ ] **Postgres logical backup** of every prod DB (`kernel`/registry, `platform`, `openfga`): `pg_dump -Fc`
      per DB to off-box storage (S3), checksummed. The registry (`registry_version`) is the system of record —
      back it up last, immediately before Stage-1 rehearsal and again immediately before the real §4.
- [ ] **Volume backups** — EBS snapshot of the data volume(s) backing the Docker named volumes
      (`airawatos_filestore_data` → `/data/filestore`, the Postgres data volume, the Vault + `identity_data`
      volumes). Snapshot while the stack is quiesced or use a crash-consistent snapshot + the logical dump above.
- [ ] **Restore drill (tested, not assumed):** on the Stage-1 amd64 copy (below), restore the `pg_dump` into a
      fresh Postgres and attach copies of the EBS snapshots; bring the stack up and confirm: site 200, a known
      record resolves, a login succeeds, the filestore serves a known blob. Record restore time (RTO) and the
      backup timestamp (RPO). **A backup that has not been restored does not count.**
- Rollback dependency: every §4/§5 rollback assumes these backups exist and restore cleanly.

## 0b. Stage 0b — housekeeping (remove ambiguity before rehearsal)

- [ ] **Authoritative Vault.** Confirm which Vault the prod stack unseals and reads from (one, not several);
      record its address, seal/auto-unseal mode (see §2c), and that no stale/second Vault is reachable from the
      services. Decommission or firewall any non-authoritative Vault so a service can never mint against the
      wrong one.
- [ ] **Remove stray images** from the prod host and the registry namespace so a deploy can only pick a real
      image: `buildx`/QEMU scratch images, `vms-fixture`, `demo-connector`, and every `dev-*`-tagged image
      (e.g. `dev-a70`, `dev-pwguard`, `dev-adr0124` — those are **local-dev only** and must never run on prod).
      `docker image ls | grep -E 'dev-|buildx|vms-fixture|demo-connector'` → remove; keep only the pinned
      prod digests from §1.
- [ ] **Resolve compose drift.** The EC2 host has drifted trees (`~/airos` vs `~/airawatos`) and the running
      compose has been hand-edited / `docker cp`-patched (see the A60 hot-patches). Reconcile to ONE committed
      compose that matches the running services, pin every image by digest, and delete the unused tree. The
      prod compose must equal what source produces — no hand edits on the box.
- [ ] **Decide `central_auth_framework`.** No code references it in any repo today (`grep` clean). Decide
      explicitly: is it an adopted direction (then record the ADR/owner + where it lands relative to the
      reference IdP + the ADR-0124 service identities), or dropped (then strike the term)? Do not carry an
      undefined auth concept into a cutover that hardens auth.

## 0c. Stage 0c — production compose variant + installer support (PREREQUISITE for Stage 1)

**Blocker, must land before the rehearsal.** The only compose today is `deploy/local-dev` — it is dev-only
(`AIRAWAT_ENV=development`, `AIRAWAT_ALLOW_PASSWORDLESS=1`, a dev/root-token Vault auto-init, 127.0.0.1 binds),
and the installer's compose project is hard-coded to `airawatos-localdev`. The fresh-install test (2026-11-06,
`docs/operator/FRESH-INSTALL-TEST.md` §Step 3) confirmed the production **posture gates** fire (prod-guard
refuses dev conveniences under `AIRAWAT_ENV=production`; the production profile seeds no data tenant and no test
users), but a production stack **cannot be stood up or rehearsed** without:

- [ ] **`deploy/prod` compose variant** — `AIRAWAT_ENV=production` (guard on), **no** `AIRAWAT_ALLOW_PASSWORDLESS`,
      durable **non-root** Vault (not the dev auto-init root token; real unseal/AppRole), 80/443-only ingress,
      the split-role DB (4b) with Vault-held passwords, `SCHEMA_VALIDATE=strict`, enforcement flags per §5.
- [ ] **Installer support for it** — `install.sh` parameterised on the compose project/file (not fixed to
      `airawatos-localdev`), and the ordered bring-up (infra → keys → roles → migrator → services, 4b) proven
      against the prod compose; production preflight (FileVault/encrypted volume, durable Vault, ports) passes
      on a real prod-grade host.
- [ ] **A from-empty install under `--profile production`** completes EXIT=0 and passes the non-demo
      conformance cases (the dev-only test-user cases are expected SKIP in production).

Until Stage 0c is green there is nothing production-shaped to rehearse in Stage 1. (Tracked as the
FRESH-INSTALL-TEST §Step 3 follow-up.)

## 1b. Stage 1 — full rehearsal on an amd64 copy of production

Before any production change, rehearse the **entire** plan end to end on a throwaway box that is production
shaped, not the local-dev Mac stack.

- [ ] Stand up a **separate native amd64 host** (CI runner or an EC2 instance of the same family/region).
- [ ] Seed it from a **restored prod backup** (Stage 0): same registry data, same identity accounts/passwords,
      same Vault secrets (or a sealed copy), same tenant graph — so enforcement behaves as it will on prod.
- [ ] Build the amd64 images there (§1/§4) and run **every step of §4 and §5 in order**, including each
      **rollback**, proving both directions work against prod-shaped data. Capture the conformance suite
      (`conformance/run.py`, external + internal) green at each enforce step.
- [ ] Record timings per step (for the real change windows) and any data-specific surprise (e.g. a legacy
      account without a password, a steward record lacking provenance) so it is fixed on prod **before** the flip.
- [ ] Tear the rehearsal host down. Go/no-go for production = the rehearsal ran clean, including rollbacks.

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

## 5. Flags to flip — shadow → enforce (each a SEPARATE, observed step)

Only after §4 is deployed-and-green and every account/principal has a real Vault-backed credential. **One flip
per change window** — never batch two. Each step below has its own soak and an explicit go/no-go. If any
go-criterion is not met, **do not proceed; roll that flip back** (§7) and re-diagnose. Watch during each soak:
service logs (denials/divergence), the conformance suite, and the edge (site 200, login success rate).

**Order rationale:** authority first (governance stays operable), then steward-provenance (read-path, low blast
radius), then the automation token, then the passwordless cutover **last** — it is the most likely to lock
something out and depends on every service principal + `component-publisher` already working.

### Step 5.1 — `PLATFORM_AUTHORITY_MODE: shadow → enforce` (network)
- Precondition: ≥1 recorded `platform.authority` holder at platform scope (ADR-0122 phase-4b seed, via the
  governance path).
- Soak **in shadow ≥ 24 h** of real traffic.
- **Go:** the `[adr0122][divergence]` log shows the steward `recorded==true` and **zero** divergences where the
  recorded result would deny what the tenant rule allowed (or vice-versa) for any live admin.
- **No-go:** any divergence on a principal that must stay authoritative, or no recorded holder.
- Flip → observe ≥ 1 h: `networks/mine` shows `platform_authority=true` for the holder, false for a non-holder;
  grant-without-CR and last-holder-revoke both 403.

### Step 5.2 — `TRUST_ENFORCE_STEWARD_PROVENANCE: 0 → 1` (network)
- Precondition: reseed migration reports **0** un-provenanced active steward records (no-op on EC2 — its one
  `network.admin` is already governed).
- Soak: re-run the read-only survey immediately before the flip; it must still show 0 un-provenanced.
- **Go:** survey clean AND, post-flip observe ≥ 1 h, the live `network.admin` steward still resolves (admin
  console administrable, `networks/mine` unchanged).
- **No-go:** any steward that must stay live lacks provenance (would be dropped) → reseed it first.

### Step 5.3 — `AUTOMATION_EVENTS_REQUIRE_TOKEN: 0 → 1` (automation)
- Precondition: event-relay (reference image) mints `svc:automation` tokens for `/events` delivery.
- Soak: with the token required, confirm a **real** event-relay delivery succeeds end-to-end in a canary.
- **Go:** tokened `/events` post → 2xx; un-tokened and wrong-audience posts → refused; no legitimate
  automation flow regressed during a ≥ 1 h observe.
- **No-go:** any legitimate producer still posts un-tokened.

### Step 5.4 — `IDENTITY_PASSWORD_REQUIRED: shadow → enforce` (identity) — LAST
- Preconditions (ALL): account-password audit returns **0** default/literal offenders (PRODUCTION-READINESS §8);
  **`component-publisher` provisioned and proven publish-capable** (marketplace/publish must survive the loss of
  passwordless); the **human steward** + every human admin have a real password; every service daemon has its
  Vault credential and is minting.
- Soak **in shadow ≥ 48 h** (longer than the others — this is the lock-out risk). Identity logs
  `SHADOW would-refuse passwordless` for every passwordless attempt.
- **Go:** the shadow log shows **zero** would-refuse events for any account that must keep working (i.e. nothing
  real is still passwordless) across the full soak, and the external conformance suite is green.
- **No-go:** any would-refuse for a real principal → give it a password first.
- Flip → observe closely: all real logins + embed + consumer + publish still work; a passwordless attempt → 401
  "a password is required". Keep the shadow→enforce revert ready as the fastest unlock (§7).

### Step 5.5 — Account-password guard (boot gate, rides `AIRAWAT_ENV=production`)
- Not a runtime flip: it is active the moment the guarded reference image boots under `production`. It is
  therefore effectively exercised at **§4's reference rollout**, not here.
- **Go precondition for §4 reference rollout:** §8's audit returns **0** offenders, or identity refuses to boot
  (`SystemExit 3`). Treat a refusal as expected-and-correct: rotate the named account, do not disable the guard.

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
- [ ] **A60 — every October hot-patch is in the new images, not re-`docker cp`-ed** (see §9).

---

## 9. A60 — October hot-patches must be baked into the new images

The live EC2 stack carries the **2026-10-19 hot-patches** applied by `docker cp` into running containers
(`deploy/ec2/HOTPATCHES-2026-10-19.md`). A fresh image/recreate **reverts** anything not baked. The source for
each is committed in the nested repos' HEADs, so building the new amd64 images from those HEADs bakes them —
**confirm each below is present in the built image before shipping** (don't assume the range covers it):

| # | hot-patch | lands in | source at | introducing commit | confirm in image |
|---|---|---|---|---|---|
| 1 | `/bridge/file-push` large-file upload (aos upload); run-gate `is_studio_builder × dev/sandbox`; dev-run routing; **async `/bridge/run`** (`{status:"started"}`) | reference (app-host) | `platform-spec/reference/app_host.py` | `d292aa0` (file-push) + the async-run change at HEAD | `grep -c 'bridge/file-push\|"started"' app_host.py` in the image |
| 2 | scheduler `DEV_RUN_TIMEOUT` 600→1800 s; dev/installed log tail 8/60→400 lines | reference (scheduler) | `platform-spec/reference/scheduler.py` | `9908610` | `grep DEV_RUN_TIMEOUT scheduler.py` shows 1800 |
| 3 | runtime launcher **`broker_ips`** L1-egress fix (component reaches kernel-as-broker over the container net) | reference (scheduler) | `platform-spec/reference/host_runner.py` + `host.py` | `3092018` | `grep broker_ips host_runner.py` present |
| 4 | **console** app (in-platform CLI, `roles:[]`, data browser) + **file-explorer** upload-error + 25 MB pre-check | app bundles (filestore `/data/app-bundles`, NOT the image) | `components/apps/console`, `components/apps/file-explorer` | `d0e5236` (console) | ship via Studio publish OR confirm the `/data/app-bundles` overlay is preserved on recreate |
| 5 | network tenant `airawatdeveloper` → `environment: development` | postgres-backed `TENANTS` (durable) | n/a (data, already corrected) | — | already durable; verify `development` on prod if that sandbox exists |

Notes:
- The `components` repo is a 4th nested repo (branch `feat/network-console-multinetwork`); its HEAD carries the
  console/file-explorer bundles. App **bundles** live in the filestore overlay (`/data/app-bundles/apps/<id>`),
  which survives a container recreate but **not** a volume loss — back it up in Stage 0 and either re-publish
  via Studio or confirm the overlay is intact after the reference rollout.
- Items 1–3 are plain source in `platform-spec/reference` → baked when the reference image builds from HEAD
  (`2258d09`); they are **ahead of** the EC2 `0.2.x` images, so this is also part of why the whole series is the
  delta. The confirm column is the gate: run the `grep` inside the built image, not just against the repo.

_Generated as a plan for the next EC2 deploy. Nothing has been applied to production._

# Production readiness — pre-flight checklist for the next EC2 deploy

EC2 (`airos.airawat.org`, 13.205.13.220) is the **frozen demo reference** and has **not** been touched.
Everything below was proven on the local-dev stack (`deploy/local-dev/`, `127.0.0.1:8080`, from-source
images). This is the single gate to clear **before** the next production deploy.

Status key: ✅ ready · ⚠️ needs an action before deploy · ⛔ blocker · ❓ needs owner context (not verifiable here).

---

## 1. Build — amd64 builder
**⚠️ Action required.** Local-dev images are native **arm64** (this Apple-Silicon Mac). The first attempt
pinned `linux/amd64` and the reference image **segfaulted (exit 139)** importing numpy/scipy/xgboost/osmium
under QEMU. Production is amd64, so production images **must be built on a native amd64 builder** (CI or an
amd64 host), never cross-emulated on the Mac.
- [ ] Build `kernel`, `network`, `reference` on amd64 from the committed hashes (network `feat/trust-plane-phase1` @ `c08ba28`; platform-spec `feat/network-console-multinetwork` @ `bd278e8`; kernel at its pinned commit).
- [ ] Push by digest; pin digests in the prod compose.

## 2. Identity envelope — IDENTITY_HOME_ISS / audience / iss
**⚠️ Action required.** Local-dev deliberately uses a *distinct* local envelope (`ds:localdev:identity`
/ `airawatos-localdev`). Production must use the production envelope, and these must be **set, not defaulted**
(the kernel/network default `IDENTITY_HOME_ISS` to `ds:airawat:identity` — do not rely on the default):
- [ ] identity: `IDENTITY_ISSUER=ds:airawat:identity`, `IDENTITY_AUDIENCE=airawatos`.
- [ ] network + kernel: `IDENTITY_HOME_ISS=ds:airawat:identity`, `EXPECTED_AUDIENCE=airawatos`.
- [ ] kernel: `IDENTITY_EXPECTED_ISS=ds:airawat:identity`, `IDENTITY_EXPECTED_AUD=airawatos`.
- [ ] Run exactly **one** shadow soak (`IDENTITY_AUD_ISS_SHADOW=true`) to confirm no iss/aud mismatches in real traffic, then **clear the shadow flag** so enforcement is hard (401 on mismatch). Do not deploy with shadow left on.
See `deploy/local-dev/PLAN.md` → "remove production-pointing defaults" for the exact matrix.

## 3. Production guard in images or compose
**⚠️ Action required.** `deploy/local-dev/prod-guard.sh` refuses to start under `AIRAWAT_ENV=production`
when any dev convenience is active (passwordless, demo-seed, ephemeral-OK, iss/aud-shadow, no-verify-cert,
schema-shadow) — exit 97, proven locally (3 cases). It is **local-dev only today**.
- [ ] Ship the guard to production: add it as the entrypoint wrapper in the prod images/compose (as in `docker-compose.dev.yml`), or fold an equivalent effective-settings check into each service's startup.
- [ ] Confirm prod sets `AIRAWAT_ENV=production` and carries **none** of the dev conveniences.

## 4. Trust plane (ADR-0119) enablement + secrets
**⚠️ Action required (secrets) / ✅ mechanism ready.** The console's role-based network selection
(`/v1/governance/networks/mine`) requires the Trust plane ON. Durable enablement proven locally with
**no secrets in compose**:
- [ ] `TRUST_PLANE_ENABLED=1`, `TRUST_KERNEL_URL=<kernel>`, `TRUST_AUTHORITY_TENANT=airawat`.
- [ ] Registry bearer: **mint-on-demand** (leave `TRUST_REGISTRY_TOKEN` unset) reusing the trust-reader credential, OR provide a long-lived platform-service JWT if prod policy prefers one. (The IdP issues 1h tokens; a static boot-time token expires — the mint path refreshes per request.)
- [ ] Audit HMAC: set `TRUST_AUDIT_HMAC_VAULT_PATH` to a Vault path holding a ≥16-byte hex secret (not `TRUST_AUDIT_HMAC_KEY` inline). Provision the secret in Vault first.
- [ ] Decide `TRUST_AUTHORITY_TENANT` for prod (who is platform-authority / sees all networks). Local-dev uses `airawat` so all local callers are role-scoped; prod's real platform tenant is `airawat` (see prod bootstrap, network `net:KQCP2EWWMSVSAJHK`).
- ✅ Governance **writes** (Capabilities/Grants/role-assign) now persist via a **dedicated trust-writer** principal (own-tenant write to `TRUST_WRITE_STEWARD`; role `[]`; never platform.service; mint-on-demand from Vault, fail-closed) — distinct from the read-only trust-reader. Prod must: create `trust-writer@<network-tenant>` + its Vault password (bootstrap Phase 7), set `TRUST_WRITER_{TENANT,PRINCIPAL,VAULT_PATH}`, and set `TRUST_WRITE_STEWARD` to the steward the Trust records live under (distinct from `TRUST_AUTHORITY_TENANT`, the is-platform-authority identity). The network's `network.network` must carry a `capability_catalog` ref (bootstrap Phase 8) before grants can be issued.
- ⚠️ **Seeding the first stewards needs a platform authority.** Assigning capability.steward/grant.steward is SoD-gated (ChangeRequest + an existing steward) OR the platform-authority bootstrap path; today `is_platform_authority` is tenant-name based, so on a network whose tenant is not the authority tenant, no one can seed the first steward without a transient authority. This is closed by ADR-0122 (platform.authority as a recorded role + installer seed); until then, seed the first steward via a one-time authority bootstrap.

## 5. trust-reader principal + Vault secret (role-mode admin authz + Trust-plane reads)
**⚠️ Action required.** Role-mode admin authz (`NETWORK_ADMIN_AUTHZ=role`) and the Trust-plane reader both
mint from a dedicated **read-only** principal (role `[]`, never `platform.service`) whose password is in Vault.
- [ ] Create `trust-reader@<network-tenant>` (prod: the network's own tenant, e.g. `airawat`) with role `[]`.
- [ ] Store its password in Vault at the path `TRUST_READER_VAULT_PATH` points to (KV v2, value under `.data.data.value`).
- [ ] Set `TRUST_READER_TENANT` / `TRUST_READER_PRINCIPAL` / `TRUST_READER_VAULT_PATH` + `KERNEL_URL` on the network.
- [ ] `bootstrap`'s Phase 5/6 (idempotent) provision the principal + both Vault secrets; run them on the prod bootstrap (or provision manually). Verify role mode returns a clean allow/deny (not a 503) after provisioning.

## 6. Canary order (network → kernel → role-mode flip)
**✅ Plan (do not deploy out of order).**
1. Deploy **network** first with the Trust plane OFF / `NETWORK_ADMIN_AUTHZ=legacy` — confirm no regression (site 200, `networks/mine` 404, legacy admin unchanged).
2. Deploy **kernel** (registry/audit changes) — confirm health + existing flows.
3. Provision trust-reader + Vault secrets (item 5) and the audit HMAC (item 4).
4. **Flip role mode** (`NETWORK_ADMIN_AUTHZ=role`) only after every network that must stay administrable has a canonical `network.network` + `governance.role_assignment` (role mode is global, fail-closed — see the prod bootstrap note: `net:KQCP2EWWMSVSAJHK` + 8 memberships + 1 role live, AUTHZ_MODE still LEGACY).
5. Enable the Trust plane console (`TRUST_PLANE_ENABLED=1`) last; soak `networks/mine` before advertising the multi-network console.
Rollback at each step = redeploy the previous pinned digest + clear the new env.

## 7. Open incident items (carried from the owner; ❓ = needs owner context to confirm status)
These were listed for inclusion by the owner; this session has no primary evidence for them (they predate or
sit outside this repo's tracked files), so they are recorded as **OPEN** pending the owner's detail — do not
treat as cleared.
- [ ] **❓ `13.61.56.103`** — an IP flagged as an incident item (distinct from the frozen demo box 13.205.13.220). Owner to confirm what host this is and whether it must be decommissioned / firewalled / reconciled before deploy.
- [ ] **❓ sessions** — session-store / session-durability concern (app-host sessions are in-process `_SESSIONS`, lost on restart). Confirm whether prod needs a shared/durable session store before deploy.
- [ ] **❓ bypass check** — an auth/enforcement bypass to verify is closed. Owner to name the exact surface; re-run the check against prod config before deploy.
- [ ] **❓ nginx in source** — the edge nginx config should live in source (the local-dev `nginx.conf` is tracked; confirm the prod nginx/edge config is committed and matches what's deployed, not hand-edited on the box).
- [ ] **❓ incident note** — a prior incident write-up to attach/close. Owner to point at it; link it here.
> Action: convert each ❓ into a ✅/⚠️ with the owner's context before the deploy sign-off. Related known-good
> reference: the EC2 disk-full incident recipe (root disk 100% → Postgres unhealthy; EBS grow + log rotation)
> is in memory `ec2-disk-full-incident` — ensure log rotation + disk headroom are in place for this deploy.

## 8. No account on a default / committed-literal password (#282 — deploy-blocking)
**✅ EC2 audit clean (2026-11-05) / ⛔ blocker if it ever regresses.** The reference IdP (`identity.py`,
`assert_no_default_passwords`) **refuses to boot under `AIRAWAT_ENV=production`** if any account's password
matches a known default/committed literal (`localdev-admin-pw`, `admin`, `password`, …). Hash-based — the
check verifies each stored pbkdf2 hash against the weak-password list and **never reads or logs a password**.
- **Deploy-blocking prerequisite:** **every** account with a password must hold a real (non-default) one
  **before** the production guard ships. Verify with the read-only audit below; it must report **0** accounts.
- **EC2 audit result (read-only, 2026-11-05):** `76` accounts carry a password; **`0`** match any known
  default/literal → **0 would block boot**. (The current EC2 IdP image predates the guard, so this is the
  pre-condition for shipping the guarded image, already satisfied for the default-password dimension.)
- Re-run the audit against the live passwords file before deploy (read-only; account keys only, no secrets):
  ```sh
  ssh airos 'docker exec -i airawat-identity python3 -' <<'PY'
  import json, hashlib, hmac
  WEAK=("localdev-admin-pw","admin","admin123","password","passw0rd","changeme","operator","test","test123","123456","secret","letmein")
  P=json.load(open("/data/identity/identity-passwords.json"))
  def ck(rec,pw):
      try:
          a,i,s,h=rec.split("$"); return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",pw.encode(),bytes.fromhex(s),int(i)).hex(),h)
      except Exception: return False
  bad=[k for k,r in P.items() if any(ck(r,w) for w in WEAK)]
  print("accounts:",len(P),"| on a default/literal (BLOCK boot):",len(bad)); [print(" -",k) for k in sorted(bad)]
  PY
  ```
- [ ] Audit returns 0 offenders immediately before shipping the guarded reference image + `AIRAWAT_ENV=production`.
- [ ] **Related (enforce dimension, not the default-password guard):** confirm no human/service account that must
  log in under `IDENTITY_PASSWORD_REQUIRED=enforce` is still passwordless — above all the **human steward**
  (`platform.steward`) and the operator `admin` accounts. Give each a real password (Vault-backed) first.

---

## Quick status summary
| # | Item | Status |
|---|------|--------|
| 1 | amd64 builder | ⚠️ build images on amd64 from pinned hashes |
| 2 | IDENTITY_HOME_ISS / aud / iss | ⚠️ set prod envelope; one shadow soak then enforce |
| 3 | production guard shipped | ⚠️ add to prod images/compose |
| 4 | Trust plane + secrets | ⚠️ enable + provision Vault HMAC; mechanism ✅ |
| 5 | trust-reader + Vault | ⚠️ provision principal + password in prod Vault |
| 6 | canary order | ✅ documented; follow in order |
| 7 | open incident items | ❓ five items need owner context before sign-off |
| 8 | no default/literal account passwords (#282) | ✅ EC2 audit 0/76 offenders; re-run before shipping the guard |

## ADR-0122 — platform.authority cutover (`PLATFORM_AUTHORITY_MODE`)
- **Unset default = `shadow`.** With the env unset, the network computes the recorded-role result alongside
  the legacy tenant rule and logs `[adr0122][divergence]`, but the **tenant rule stays authoritative** — no
  behavioural change. EC2 therefore stays shadow until explicitly cut over. Local-dev is already `enforce`.
- **Seed before enforce.** `enforce` derives `is_platform_authority` from the recorded `platform.authority`
  role **only, with no tenant fallback**. A deployment MUST seed at least one `platform.authority` holder
  (platform scope) for the steward **before** setting `PLATFORM_AUTHORITY_MODE=enforce`, or no principal will
  hold platform authority and platform-authority-gated governance will be unoperable. Order: (1) govern
  `governance.role_assignment@0.2.0`; (2) **reload the kernel** so its schema validator accepts 0.2.0 (a
  long-running kernel caches schemas at boot — see note); (3) seed the steward's `platform.authority`
  (bootstrap phase 4b); (4) soak in `shadow` and confirm the divergence log shows the steward recorded==true;
  (5) flip to `enforce`.
- **Kernel-reload note:** after governing a new schema version into a **running** stack, restart/reload the
  kernel before writing records against it — the kernel validates writes against its boot-loaded schema set,
  so a freshly-governed version 422s ("role not in enum") until reload. A fresh install is unaffected (kernel
  boots after schemas are seeded).

_Generated for the next EC2 deploy. Nothing here has been applied to production._

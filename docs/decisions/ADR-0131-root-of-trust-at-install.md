# ADR-0131 — Root of trust at install

**Status:** Accepted (FIX-PLAN L1 slice-1c-iv)
**Supersedes the bootstrap half of:** DEBT-A71 (IDENTITY_INTERNAL), DEBT-B29 (unconfigured provisioner gate)

## Context

The identity service's account-provisioning door (`/users`, `/set-password`, directory reads) was gated by a
**shared committed literal** `IDENTITY_INTERNAL`. Closing it to an audience-bound `svc:identity` token (the
A71 pattern already applied to secrets, runtime-manager, model-gateway) hit a **bootstrap deadlock**: the first
identity writes happen at install (via `network/ensure_install.py`), and minting any `svc:identity` token needs
a principal that only exists *after* those writes. A shared-secret bootstrap channel would re-introduce exactly
the literal we are removing.

## Decision

**The operator install config in Vault is the root of trust. Identity owns realm/principal creation. There is
no bootstrap channel on the internal door.**

1. **Install config in Vault (the root).** Before identity starts, the installer writes an operator install
   config to Vault: the operator realm, its first administrator's initial password, and the `provisioner`
   principal's password (dev profile additionally lists the local-dev realms + test principals). Vault — already
   the platform's secret/transit root — is therefore the single root of trust for who may first exist.
2. **Identity self-bootstraps at boot, create-only.** At startup identity reads that config and **creates only
   principals that do not already exist** — it NEVER resets an existing admin, password, or role. Changing the
   config afterwards does not alter existing principals (constraint 1). The seed is a direct in-process store
   write, not an HTTP call through the gate, so there is no deadlock and no bootstrap secret on the door.
3. **Minimum in production.** Production bootstraps only the **operator realm, its first administrator, and the
   provisioner**. All other tenants/principals are created later through the normal governed path. The four
   local-dev realms and test users are bootstrapped **only under the dev profile** (`IDENTITY_SEED_DEMO`/
   `AIRAWAT_PROFILE=dev`), consistent with PLT-1 (production ships empty).
4. **First admin rotates immediately.** The first administrator's seeded password is marked `must_reset`; the
   installer **removes the bootstrap admin password from Vault** once identity confirms the bootstrap, so the
   initial secret does not linger.
5. **The door is `svc:identity`-only from day one.** `/users`, `/set-password` and the directory reads require
   an audience-bound `svc:identity` token from an allow-listed caller (`provisioner` + the declared service
   callers in ARCHITECTURE-FLOWS), verified against identity's own JWKS, **always enforce**. **B29 preserved:**
   if the provisioner cannot be seeded (Vault unreachable / config absent) identity fails every write closed and
   refuses to boot under `AIRAWAT_ENV=production`.
6. **Tenant records stay the network authority's.** `ensure_install` still signs the tenant records via the
   network authority (`api.AUTH.sign_tenant` → network's own in-process registry); identity resolves tenants
   from the network registry (`/v1/tenants/resolve`). "Identity owns realm/principal **creation**" means the IdP
   **user/principal** records, not the authority-signed tenant records. `ensure_install` stops writing to
   identity entirely.

7. **The founding act registers each tenant's steward (slice-1e, DEBT-B62).** For every tenant record the
   installer signs (`<op>`, `<op>-network`, `<op>-developer`, `<op>-participant`, `citizens`, and the dev data
   tenant), `ensure_install` names the steward participant **`ds:<tenant>:steward`** — whose key is the tenant's
   own Vault transit key `steward-<tenant>`, the key `/v1/grants/issue` signs install grants with — and registers
   its **CA-signed directory entry** in the Network directory, on every run (idempotent; an older record naming
   the unregistered `ds:<tenant>:participant/admin` is re-signed). This is the **same** identity and mechanism the
   join→approve path (`_provision_steward`) already gives an onboarded tenant — no new trust-plane construct. So
   the kernel's `_steward_authorizes` resolves the steward key and an installed component's declared writes
   verify on a fresh install. Fail-closed: without Vault the steward cannot be provisioned and the install stops.
   (The kernel no longer caches an unresolved steward key, so a tenant whose steward is registered later is not
   pinned as "no steward" until restart.)

## Consequences

- `IDENTITY_INTERNAL` is removed from all code, compose, env, and committed defaults. A71 is fully closed for
  gates (secrets + runtime-manager + model-gateway already done in 1c-ii/1c-iii).
- Callers mint `svc:identity`: the installer scripts, app-host (×8 sites), and network `api.py` join→provision
  (×3 sites, which gains a Vault-backed inline minter + an `svc-network` policy grant to read the provisioner
  password). The allow-list the door declares: **identity writes ← `{provisioner}`** (+ any service principal a
  declared edge adds).
- The reference image (identity + app-host) and the network image are rebuilt; the installer seeds the config
  before bring-up and scrubs the admin password after confirmation.
- Trade-off: the install config (passwords) lives in Vault during install — acceptable because Vault is already
  the platform root, the admin password is single-use (`must_reset` + scrubbed), and nothing is a committed
  literal.

## Staged delivery (a / b / c)

The cutover ships in three fresh-install-gated commits so the one irreversible step (flipping the door to
`svc:identity`) happens only after the seed + relocations are proven:

- **1c-iv-a** — the installer writes the operator install config (`admin` + `provisioner` passwords) to Vault
  *before* bring-up (create-only). Images unchanged. **Shipped.**
- **1c-iv-b** — identity self-bootstraps the admins + provisioner from that config at boot (create-only);
  `ensure_install` stops all IdP writes (keeps the tenant records); the four role-bearing service principals
  (`scheduler`, `component-publisher`, `dev-sandbox`, `embed-service`) move to installer **Phase 1b-svc**. The
  door is **still `IDENTITY_INTERNAL`** — no cutover. Images: reference `dev-hard15`, network `dev-a76`.
  **Shipped (this commit; tag `pre-identity-cutover`).**
  - **Production minimum for the relocated principals:** `scheduler` + `component-publisher` are created on every
    profile (both production-needed). `dev-sandbox` is created **only under the dev profile**; `embed-service`
    **only when `EMBED_ENABLED=1`** (default on in dev, off otherwise). So a production install's relocated set is
    exactly **{scheduler, component-publisher}** (+ `embed-service` iff embedding is enabled); `dev-sandbox` never.
- **1c-iv-c** — flip the door to `svc:identity`-only; app-host (×8 sites), network `api.py` join→provision, and
  the installer phases mint `svc:identity`; `IDENTITY_INTERNAL` removed everywhere; B29 adapted to the
  provisioner-seedable check. New images reference `dev-hard16`, network `dev-a77`. **Shipped.**
  - **As built:** identity gate = `svc_authz.ingress_gate(accept={svc:identity}, allow={provisioner, app-host},
    require=True)` against identity's own `/jwks` (loopback), **plus** the caller's `sub` must be in the operator
    realm (`SERVICE_TENANT`) — a same-named principal in another realm is refused. Covers `/users` (POST+GET),
    `/set-password`, `/prefs`, `/realms`, `/realms/<t>/users`. **app-host** calls as its **own** `app-host`
    principal (recorded audience `svc:identity`, installer Phase 1c) — per-caller identity, not the shared
    provisioner; **network** `api.py` (join→provision ×3) mints as `provisioner` via an inline Vault-backed minter
    (`svc-network` grants exactly `secret/data/<op>/provisioner/*`); the **installer** mints a fresh provisioner
    token per identity-writing phase (`_idt`, phases 1b-svc/1c/5/7/9/9b). **B29:** `assert_provisioner_seeded`
    refuses boot under production when the provisioner is not seeded; outside production every call fails closed.
  - **Bootstrap confirmation + scrub (constraint 4):** installer Phase 1a confirms the bootstrap (provisioner mints
    `svc:identity` AND `admin@<op>` logs in, `must_reset:true`) before any identity write; Phase 14 — after every
    phase that logs in as admin and the dev conformance fixture — removes the admin bootstrap password with
    `vault kv metadata delete` (all versions; a soft `kv delete` would be recoverable) and writes the marker
    `secret/<op>/install-state`. A **re-install over a scrubbed install** requires `OPERATOR_PASSWORD=<current
    admin password>` (used in-shell only, never written back) instead of minting a new, unusable bootstrap secret.
  - **Verified (fresh `install.sh --profile dev`, EXIT 0):** 63/63 login-path checks — operator admin
    (`must_reset`), 3 dev realm admins + 4 dev test users, provisioner (`svc:identity` ok, other aud 403), all 11
    service principals (each recorded audience mints; `svc:identity` refused to every undeclared one), a normal user
    + a must-reset user through the App Host (login, change-password via app-host→identity, rotated pw works, old
    refused); network minter (own AppRole token) writes through the door. Conformance external 13/0, internal 44
    PASS / 6 XFAIL / 0 XPASS / 0 FAIL. Rollback was **not** needed.

## Slice-1e follow-up (as built)

- **Steward registration** (Decision 7, DEBT-B62 closed) — network `dev-a79`, kernel `dev-hard9`.
- **The fresh install proves function** — installer **Phase 15** (dev profile; the install FAILS if either check
  fails): (A) a user is onboarded through the App Host (tenant admin signs in at the edge → `/bridge/user-create`
  → the new user signs in with the admin-set password, `must_reset` → rotates via `/auth/change-password` → live
  session); (B) an installed component writes a record within its grant (install-as-grant → the steward resolves
  in the directory → the scheduler runs it via the runtime manager under its own install token → the declared
  `platform.inbox_item` write is accepted and readable by the tenant; an undeclared `platform.schedule` write is
  refused 403). Check (A) found that App Host user-create/reset never named the tenant, so every created user
  was unreachable (`404 unknown user`) — fixed in reference `dev-hard21` (the admin-set password is now also
  `must_reset`, per ADR-0115).
- **Re-install after bootstrap:** once Phase 14 has scrubbed the bootstrap password, a re-install over the same
  volumes must be run with `OPERATOR_PASSWORD=<the current admin password>` (see OPERATOR-GUIDE §2).

## Rollback procedure for the 1c-iv-c cutover

If the gate flip (1c-iv-c) breaks login or a service-principal mint and the fix is not immediately clear, roll
back to the **`pre-identity-cutover`** tag (the 1c-iv-b state, where the door is still `IDENTITY_INTERNAL` and
every caller still presents it):

1. **Revert the code** in all three repos to the tag:
   `git -C platform-spec checkout pre-identity-cutover -- reference/identity.py reference/… ` (or reset the
   branch), likewise `network` (`ensure_install.py`, `api.py`) and root (`deploy/`). The tag is applied to all
   three repos at the same slice so they revert as a consistent set.
2. **Revert the compose image tags** to the b-state: reference `dev-hard15`, network `dev-a76` (the c images
   `dev-hard16`/`dev-a77` are the forward tags). `docker compose up -d --force-recreate identity network app-host`
   — or a full fresh install for a clean environment.
3. **Vault: no restore needed.** The install config (`secret/data/<op>/{admin,provisioner}/password`) is written
   create-only and is read identically by the b and c identity images, so it is forward/backward compatible. The
   c step scrubs the admin password only *after* identity confirms the bootstrap; if c failed before that scrub
   the password is still present (expected), and if it was scrubbed the admin has already rotated (login uses the
   rotated password, which lives in the identity data volume, not the install config). Do **not** wipe the config.
4. **Postgres: no restore needed.** Identity's principal + password + must-reset stores live on the
   `localdev_identity` Docker volume (only the brute-force lockout table is in Postgres). The b boot-seed is
   create-only, so bringing the b image back up against the existing volume leaves every provisioned principal
   and rotated password intact — nothing is re-seeded or reset.
5. **Verify after rollback:** (a) `admin@<operator>` logs in (if not yet rotated, response carries
   `must_reset:true`; if rotated, the rotated password works); (b) the realm admins log in; (c) a service
   principal mints its token — e.g. `scheduler@<operator>` obtains an `aud=svc:automation` token and
   `provisioner@<operator>` obtains `aud=svc:identity` but is **refused** any other audience (403); (d) a fresh
   `install.sh --profile dev` completes green with conformance both modes 0 FAIL. If login still fails on the
   rolled-back b image, the fault is in the shared config/volume, not the gate — investigate there, do not
   re-flip the gate.

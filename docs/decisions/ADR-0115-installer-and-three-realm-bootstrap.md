# ADR-0115 — Installer & the three-realm bootstrap (operator / network / tenant)

> **⚠️ PARTIALLY SUPERSEDED (2026-11-05).** Two premises are overturned: (1) **passwordless service accounts
> baked into the image** (explicitly flagged as open item #282) → superseded by **ADR-0124** (dedicated service
> identities with Vault-backed credentials) and **PLATFORM-v0.1 P1** (service identities carry recorded service
> credentials, never passwordless). (2) **first platform authority seeded via the realm/tenant bootstrap** →
> superseded by **ADR-0122** (first `platform.authority` via a one-time installer credential that expires; a
> **recorded role** with SoD + last-holder floor) — **PLATFORM-v0.1 P2 & P5** — and **P4** (the platform tenant
> confers no authority; no tenant-name authority). The cited *"federated identity = network citizenship"* is
> overturned by **ADR-0116** / **PLATFORM-v0.1 P4** / **NETWORK-v0.1 N1**. The installer-minimum / idempotency
> shape (P1) otherwise stands. Body unchanged below.

- **Status:** Proposed — 2026-10-29
- **Context carried from:** ADR-0068 (pluggable identity + assurance tiers), ADR-0086/0096 (operator model),
  ADR-0039 (federated identity = network citizenship), ADR-0038 (spec governance), ADR-0051 (dev-tenant sandbox),
  ADR-0094 (component stewardship separation), ADR-0103 (per-object ownership), the registry zero-trust read gate.
- **Companion:** `docs/introduction-to-airawat.md` (the newcomer explainer this ADR formalises).

## 1. Context & problem

AirawatOS must deploy "like Linux" — the same base from a one-box municipality to a national ministry. Today a
fresh install is a **dev/demo bootstrap**, not a production one:

- The reference IdP ships a **hardcoded `USERS` dict** (`devrick`, `steward`, demo humans) — well-known,
  passwordless accounts baked into the image (open security item #282).
- There is **no install-time operator identity**. `kind:operator` exists only as a *network participant kind*,
  never created at install; on EC2 there is no operator principal at all.
- **OS-layer and network-layer concerns are conflated** in the `airawat`/`airawatos` platform tenant: the
  `steward` (network governance) and `airawat-scheduler` (OS daemon) both live there.
- Tenant/realm names, the network authority, and the dev sandbox are **hardcoded**, not derived from an
  instance identity chosen at install.
- **No forced first-login password reset; no OTP; no SMS provider.** Email is further along (a governed
  `email-sender` provider + SMTP/Zoho send + a working join email-verification code) but is not yet an
  install step nor a login factor.

We need a production installer that makes the **clean separation of operator / network / tenant** true from
first boot, ships **zero baked credentials**, and scales down to one box and up to a federation.

## 2. Decision

### 2.1 Three realms, provisioned at install (not baked)

The bottom of the stack is **three system realms** plus N data tenants:

| Realm | Domain prefix | Principals | Owns | Role of |
|---|---|---|---|---|
| **OS / system** (`<instance>-operator`) | `platform.*` | `admin` (operator, human), `scheduler` (daemon), platform services | the OS's *own* operational records (schedules, runtime registry, config, audit) — **never civic data** | the box / `root` + `cron` |
| **Network** (`<instance>-network`) | `network.*` | `network-admin` | schemas, roles-vocab, participant directory, marketplace, certification | the dictionary + registrar |
| **Tenant(s)** (`<instance>`, `<instance>-sandbox`) | `<domain>.*` + `platform.tenant-admin` | tenant-admins (username `admin`), users | civic/business data of record | the institutions that retain control over their data |

**Naming conventions (fresh-install provisioning):** all four realms are **`<instance>-`prefixed** for consistency
and global uniqueness (no fixed `os`/`sandbox` names that would collide when installs federate):
**`<instance>-operator`** (OS/system), **`<instance>-network`** (authority), **`<instance>`** (data),
**`<instance>-sandbox`** (`environment=development`). **Every realm's admin account has username `admin`** —
scoped by its realm, so `user://<instance>-network/admin` ≠ `user://<instance>/admin`, and the username never
collides with the `admin`/`platform.*`/`network.*` *roles* it holds (username ≠ role). The operator defaults to
`admin@<instance>-operator` (`platform.admin`) but may set a different username at the prompt.
This governs what the installer PROVISIONS on a fresh box; it does **not** rename the existing live
`airawatdeveloper` dev-tenant / `devrick` user (steward of the first-party component marketplace, ADR-0094) —
that is a separate, deliberate migration, not part of this installer work.

- The **operator** role is **`platform.admin`** (already an honored admin role in the kernel — reuse, not a new
  `os-admin`). The operator is a `platform.admin` principal in the **`<instance>-operator`** realm,
  **data-scopeless**: the registry read gate scopes it to `ds:<instance>-operator:` (verified — no admin
  cross-tenant read bypass exists).
- The **scheduler** is an OS daemon: `platform.scheduler` in the `<instance>-operator` realm. OS roles
  (`platform.admin`/`platform.scheduler`/`platform.service`) are **kernel built-ins** (intrinsic, like `root` —
  not network-governed vocabulary), so they exist from first boot with no chicken-and-egg on the network.
- **Human vs daemon reach:** the scheduler (`_is_platform_service`) gets *narrow cross-tenant reach on control
  schemas only* (read every `platform.schedule` — "cron reads all crontabs"); the human operator does **not**.
  Same layer, least-privilege split, already enforced in `_read_scope`.

### 2.2 The reference IdP ships empty; everything is provisioned

- `identity.py` `USERS = {}` — **zero baked accounts.** Keep the durable overlay (`identity-users.json`) +
  internal-gated `POST /users` + `_persist_provisioned` that already exist.
- The installer provisions, into the durable store: `operator` (`platform.admin`), `scheduler`
  (`platform.scheduler`), `<instance>-network-admin` (`network.admin`), and — if the dev sandbox is created — a
  developer. Login works **only** for provisioned users.
- A `IDENTITY_SEED_DEMO=1` escape hatch (demo/dev compose only) may re-enable `devrick`/`steward` for
  dogfooding; production ships with it unset → empty.
- **Service principals** are provisioned short-term; the better end-state is services authenticating with a
  service/client-credentials token rather than rows in a human directory (follow-up, not a blocker).

### 2.3 Forced first-login reset

The operator sets the `<instance>-network-admin` initial password at install; the IdP marks it `must_reset`,
and the admin is forced to change it on first login (new IdP capability).

### 2.4 Optional verification providers (OTP)

Email/SMS OTP is the ADR-0068 **A1** tier, **optional** per install:
- **Email** reuses the existing `email-sender` provider + send path; the install adds a "set SMTP creds" step
  and generalises the existing email-verification *code* into a login factor.
- **SMS** is a new `sms-sender` provider mirroring `email-sender` (likely Zoho CPaaS SMS), feeding the same OTP
  factor.
When configured, users can be verified/authenticated via OTP; when not, the install stays password-only.

### 2.5 Federation is opt-in and later (islands first)

A fresh install is a **sovereign island**: operator + local network (dictionary) + tenants, **no upstream root
required**. Networks connect later by trusting each other's issuers (per-issuer JWKS — kernel *and* network now
verify EdDSA + RS256) and writing **bilateral schema crosswalks** at the boundary; common schemas are *harvested*
into a shared root over time, never legislated up front. The only discipline required of an island to stay
connectable (all already enforced): global `ds:<tenant>:` ids, self-describing governed schemas, JWKS issuer
trust — plus one habit: **let entities carry external/authoritative identifiers** so cross-island entity
matching is possible later.

## 3. Installation — step by step

```
0. Preflight: Docker present; pull public images; Vault boots → auto-init/unseal → root token (machine-held).
1. PROMPT: operator admin username (default `admin`) + password → `admin@<instance>-operator` (platform.admin)
   AUTO:   generate a strong Postgres password          → Vault only; never shown.
2. PROMPT: instance name (e.g. "labour").               → the namespace root for all realm ids/issuers.
3. AUTO:   stand up the `<instance>-operator` realm     → + `scheduler` (platform.scheduler) daemon principal.
4. AUTO:   stand up `<instance>-network`                → + `admin@<instance>-network` (network.admin),
                                                           initial pwd set by operator, must_reset=true.
5. AUTO:   stand up `<instance>` (data) + `<instance>-sandbox` (environment=development) tenants, each with `admin`
           (platform.tenant-admin), initial pwd set by operator, must_reset=true.
5b. AUTO:  install the BASE APP SET into EVERY tenant — including the **Console** (the in-platform command line
           over governed bridges), so every tenant has it out of the box (alongside the existing base apps:
           Files, Workspace suite, Inbox). Base apps are part of the install, not a per-tenant opt-in.
6. OPTIONAL (install or later): configure email and/or SMS provider → unlock OTP verification (A1).
7. Services boot (kernel, network, identity, filestore, secrets, model-gateway, engines, app-host); nginx :80.
```

## 4. What is ready after installation

- A running platform on `:80`; empty registry (no demo content).
- **Operator** can log in (`platform.admin`) and operate the box — **cannot read tenant data** (scoped to `ds:<instance>-operator:`).
- **`<instance>-network-admin`** must reset password on first login, then governs the dictionary + admits participants.
- A **data tenant** and a **dev sandbox** ready to receive drivers / host apps.
- **No baked or well-known credentials anywhere.**
- Email/SMS OTP active **iff** a provider was configured; otherwise password login.
- The install is a **standalone island**, ready to federate later.

## 5. Enabler slices (build order)

1. **Operator identity + machine-secret DB + de-seed IdP** — `USERS={}`; installer provisions
   `platform.admin` operator (prompted) + `platform.scheduler` daemon; DB secret auto-generated to Vault.
   *(Keystone — de-seed and provision land together or boot breaks.)*
2. **Instance-name → namespace** — one prompt drives every id/issuer.
3. **Parameterised realms** — derive `<instance>-operator` / `<instance>-network` / `<instance>` / `<instance>-sandbox`;
   provision `admin` in each (operator `admin@<instance>-operator`, network `admin@<instance>-network`, data/sandbox `admin@…`).
4. **Forced first-login reset** — IdP `must_reset` flag + reset screen.
5. **OTP as a login factor** — generalise the existing email-code into an A1 auth factor, per-tenant configurable.
6. **SMS provider** — new `sms-sender` provider feeding the same OTP factor.

**Separate, sequenced cleanup slice (not entangled with the above):** role-vocab consistency —
adopt `platform.admin` (free; already exists), consolidate network governance under **`network.admin`**
(with `network.steward` as an *optional* curation role for separation-of-duties, not a peer), rename
`platform.steward → network.steward` behind a back-compat alias, reconcile the stray `platform.operator`,
and retire the bare un-namespaced `admin`/`steward`/`tenant_admin` forms. This touches ~18 call-sites + live
grants, so it runs on its own with an alias/transition and does not block the fresh-install work.

Slices 1–4 deliver the operator-first sovereign-island installer; 5–6 add optional verification; federation
and operator-attestation (ADR-0086 enforcement) are a later phase.

**Install UX (decided 2026-10-29): CLI now, web wizard later.** The provisioning logic ships first as a CLI
step (prompt operator/instance → provision principals + tenants via the IdP/network internal APIs), which
unblocks a real operator-first install and works headless. A first-run **web setup wizard** (services boot in a
locked "needs-setup" state; the operator browses in and completes operator → instance → network-admin → optional
OTP) is the polished default, built once the CLI flow is proven. Both drive the same provisioning underneath.

**Progress 2026-10-29:** #1a (de-seed) DONE — `identity.py` ships `USERS={}`, demo seed gated behind
`IDENTITY_SEED_DEMO` (set in the dev/demo composes); `platform.admin` adopted as the operator role (already
existed). Network RS256 (per-issuer JWKS) also landed this session so Keycloak/OIDC verifies at the network too.

**#1b CORE DONE + VERIFIED LIVE 2026-10-29:** (a) realm-scoped IdP user store (`tenant/username` keys + bare
back-compat) — `admin` per realm, collision-free, login + password-gate + legacy coexistence proven, unit test
5/5 (`platform-spec/reference/test_identity_realm_scope.py`, commit `65b9e3b`). (b) `network/ensure_install.py`
provisioner (commit `9694310`) — `INSTANCE=labour` created the four realms + `admin` in each + `scheduler`; all
four `admin@<realm>` logins verified with correct sub/roles/environment (sandbox=development), scheduler
passwordless, wrong-pw→401. (c) `must_reset` first-login forced reset (commits `3cd9733` + `68a9ea0`) — IdP
stores/signals it, provisioner marks the initial admin passwords, self-service set-password clears it; verified
live (set→signalled→cleared→old-pw-rejected). (d) base apps incl. **Console** — ALREADY SATISFIED in source,
no code change: `components/apps/console/meta.yaml` declares `default_install: true` (first-party), and
`_ensure_workspace_suite` (app_host, runs on every admin login) auto-shelves every first-party `default_install`
app onto every tenant — the production-proven path that already ships Docs/Sheets/Slides/Chat/Mail/Inbox/Files/
Personal-Assistant. (Can't be shown on the current LOCAL stack because its pinned reference image `0.2.115`
predates Console/components-apps; it appears once a current reference image is baked.)

**#1b BACKEND COMPLETE** (realm-scoped store · provisioner · must_reset · base-apps+Console-by-declaration).
**CLI installer DONE** (`deploy/local/airawatos-install.sh`, commit `ce4c618`) — prompts/env `INSTANCE`+operator
password, brings up a DE-SEEDED stack (`${IDENTITY_SEED_DEMO-1}` — no-colon so explicit empty de-seeds; quick-eval
default stays seeded), runs `ensure_install.py`. Verified headless (INSTANCE=health): 4 realms + admins, operator
login must_reset:true, IdP de-seeded (devrick/kmc gone).

**NETWORK IMAGE BAKED + pushed** — `manishsv/airawatos-network:0.3.6-installer` (amd64; folds RS256 `authn.py` +
`ensure_install.py`; Dockerfile COPY updated, commits network `29e74bd` + parent `7217727`); local compose points
at it; verified the baked image carries both.

**REFERENCE IMAGE BAKE — reassessed, NOT done:** the reference Dockerfile (ADR-0093) STRIPS `components/apps`, so
baking it would NOT deliver Console/base-apps (those come from the FILESTORE at runtime — backlog #281
image→filestore delivery; on EC2 the filestore already holds them, a fresh install must seed them). A reference
bake would carry only de-seed + must_reset (already overlay-proven) at the cost of a ~20–40 min emulated-amd64
build (osmium/numpy/shapely/xgboost/sklearn). RECOMMENDATION: defer the reference bake and pair it with the
filestore first-party-component seeding (the real base-apps delivery), ideally built on an amd64 host/CI rather
than emulated. #1b's operator-first install MECHANICS are complete + proven; base-apps-on-a-clean-install is a
filestore-seeding task, not a bake.

**app-host must_reset login screen DONE + verified live** (commits `01dc646` + `982c879`): `_login_session`
captures the IdP must_reset → `_do_login` surfaces it → `login.html` shows a "set a new password" form →
session-authenticated `POST /auth/change-password` calls the IdP `/set-password` (own sub only, must_reset:false)
to clear it, then proceeds. Verified end-to-end: login→must_reset:true → change → cleared → old-pw rejected.

**VERIFIED LIVE 2026-10-29** on a clean local install (16 containers, core healthy) via the dev-overlay compose
(edited source over pinned images, no rebuild): de-seed proven BOTH ways — `IDENTITY_SEED_DEMO=""` → identity
`/realms` returns `[]` (zero baked accounts, the production default); `="1"` → demo users restored. The RS256
`authn.py` runs live with no regression (EdDSA logins → stack healthy). Two install bugs found + fixed (see
`install-local.md` / `airawatos-bootstrap.sh`): (a) a global `DOCKER_DEFAULT_PLATFORM=linux/amd64` forces Vault
to emulate and its Go binary CRASHES under QEMU/Rosetta → rely on the per-service `platform:` pins instead;
(b) Vault's `init.json` is pretty-printed → flatten (`tr -d '\n '`) before the root-token `sed`.

## 6. Consequences

- **Positive:** production-grade first boot; the operator/network/tenant separation is real and enforced;
  zero baked credentials closes #282; scales from one box to a ministry; islands stay federation-ready for free.
- **Costs:** de-seeding the IdP is a coordinated change with install provisioning; the role-vocab rename touches
  many sites and the live EC2 `steward` (hence its own aliased slice).
- **Unchanged / honest limits:** an operator with host root can still read the disk — "operator can't see tenant
  data" holds *through the system* and is completed, for the operator≠data-owner case, by encryption-at-rest +
  operator-certification/attestation (ADR-0086) and, at the top tier, confidential computing (TEE).

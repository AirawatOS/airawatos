# ARCHITECTURE-FLOWS — v0.1 (ARC)

> **Status is conformance-measured** — see [STATUS-MATRIX.md](STATUS-MATRIX.md). ARC rules are now wired into the
> matrix via the **flow-map test** (`conformance/flow_map_test.py`, FIX-PLAN L1 slice-1a): as of that slice
> **ARC-1, ARC-3, ARC-5, ARC-7 read HELD** (network-boundary layer), **ARC-4 PLANNED(needs-build)** (per-service
> micro-segmentation), and **ARC-2, ARC-6 NO TEST** (owned by later layers — Kernel/ADR-0123 and the per-door
> decision function). The §d table below carries the narrative + residual debt per rule.

This spec states the platform's **flow architecture**: the *doors* through which every call must pass, the *rules*
that govern flow between layers, how each rule is *enforced*, and the *current-state* deviations (each a DEBT
finding). It does not restate authority semantics — those live in [FOUNDATIONS](FOUNDATIONS-v0.1.md); ARC is about
*topology*: what may call what, in which direction, through which door, authenticated and authorized how, recorded
where. It composes existing rules (FND-6 Kernel domain-blind, FND-7 + **ADR-0123** Kernel self-contained for authz
inputs, CLI-6 / PTC-12 public-versioned-protocol-never-`/bridge`, REG-18 Kernel-mediated files, per-service DB
roles) into one topology contract rather than duplicating them.

A **door** is a network-reachable entry point that (1) admits a defined set of callers, (2) in a defined
direction, (3) authenticates the caller, (4) authorizes the call through **one decision function that reads
recorded state** (FND-2), fail-closed (FND-8), and (5) records what it admitted/denied (FND-12). A **data store**
(Postgres facts, Vault secrets, blob files) is never a door: it is reachable only from the single layer directly
above it, which holds its credentials.

---

## a. The doors

| # | Door | Who may call (direction) | Authenticates | Authorizes (one decision fn, recorded state) | Records |
|---|------|--------------------------|---------------|----------------------------------------------|---------|
| **D1** | **Public edge** (nginx / reverse proxy) | the **internet** → inward only | nothing (TLS terminate, route, rate-limit) | routes to D2/D3 only; never to an internal service or store | access log |
| **D2** | **App Host front door** (`/`, `/bridge/*`, `/embed/*`) | internet (via D1) → apps, embed clients, citizens | session cookie / bearer via Identity (D4); **public** routes declared unauth | `_ensure_session` + per-route gate reading recorded roles/grants/consent; `/bridge/*` is the **internal app-confinement surface**, not the public protocol (CLI-6/PTC-12) | app-host audit; `prov.*` on writes it brokers |
| **D3** | **Federation door** (Network `/network/v1/{participation,join,grants,certify,decide,issue,resolve,verify,message,…}`) | internet (via D1) → other participants / networks | participant/issuer signature or scoped-issuer token (PTC-2, FND-15); public reads declared | Trust-plane decision fn over recorded `network.*` grants/roles | network audit + hash-chain |
| **D4** | **Identity door** (`/login`, `/jwks`, sessions) | apps/services/humans → authn only | password / OIDC / PKCE | **plumbing** (no authority); issues identity-only, audience-bound tokens (FND-1/FND-9) | failed-auth log (target: FND-12) |
| **D5** | **Network / governance door** (certify, publish, directory, catalog — Network service) | certified participants, stewards → governance | service/participant token, audience-bound | Trust-plane grant check (ADR-0119) | signed catalog + audit |
| **D6** | **Service gateways** (service-gateway read tier, mospi-gateway, …) | signed-in callers / peers → scalable reads | audience-bound service token (svc_authz) | read-scope decision fn; declared-interface only | gateway audit |
| **D7** | **Kernel door** (`/v1/*` registry + broker) | **only the layer directly above** (app-host, internal services, confined components via the broker) → never the internet | audience-bound service token / run-token (broker) | single P0 registry authorization gate over recorded grants (FND-2); broker caps = declaration ∩ grant (CMP-3) | `prov.derivation` / write records |
| **stores** | **Postgres** (facts), **Vault** (secrets), **filestore** (blobs) | each from the **one layer above**: Postgres ← Kernel; Vault ← secrets service; files ← filestore / Kernel-mediated (REG-18) | DB role / Vault token / internal gate | n/a (not a door — no onward decision) | DB/Vault audit |

---

## b. Rules of flow

- **ARC-1 — No call bypasses a door.** Every cross-layer call enters through exactly one door above; there is no
  side channel from a caller to an internal service or store that skips the door's decision function. (Composes
  FND-8 + CMP-6 "records & files only via the broker".)
- **ARC-2 — The Kernel never calls upward.** The Kernel reaches no higher layer (Network, App-Host, Identity) to
  make an authorization decision; it holds its own trust records. (FND-7, **ADR-0123**.)
- **ARC-3 — Only the Kernel holds fact-store credentials.** The Postgres **fact** store is reached only through
  the Kernel door (D7); no other service connects to the facts. Secrets reach Vault only through the secrets
  service; blob bytes are Kernel-mediated records (REG-18). (FND-6 keeps the Kernel domain-blind so it can be the
  sole substrate holder.)
- **ARC-4 — Each service reaches only the doors it is listed for.** A service's outbound calls are confined to the
  doors named in its `calls:` declaration (`platform-spec/reference/services.yaml`); an undeclared service→door
  edge is a violation.
- **ARC-5 — The internet reaches only the edge, and through it only the App Host front door (D2) and the
  federation door (D3).** No internal service, gateway, or data store is internet-reachable; the Kernel door (D7),
  secrets, filestore, runtime-manager, model-gateway, scheduler, automation, workflow, decision and the stores are
  internal-only.
- **ARC-6 — Every door runs one fail-closed decision function over recorded state, and records the decision.** A
  door authorizes from a live recorded grant/role/consent (FND-2), never from a token role claim or tenant name
  (FND-1/FND-3); it denies on missing/unavailable/unverifiable authority (FND-8); it must not default to
  off/shadow (FND-16); and it writes an allow/deny record (FND-12).
- **ARC-7 — A data store is reachable only from the layer directly above it.** Postgres ← Kernel only; Vault ←
  secrets service only; files ← filestore/Kernel only. No layer reaches two stores down, and no store is a door.

---

## c. Enforcement per rule

> **Default-deny egress (slice-1g, DEBT-B87).** Every boundary network is `internal: true` — no route to the internet,
> the host or another network. Two networks route out: **`aos-public`** (nginx alone — the only published network) and
> **`aos-egress`**, which only the declared egress gateways join: **kernel** (the broker's declared component egress),
> **model-gateway** (AI providers), **network** (email, federation), **app-host** (channel providers, tile/asset proxy).
> **`aos-component`** (placed components) is internal and holds only the broker. Proven by `conformance/flow_map_test.py`
> by actual connection attempts from every container (every peer IP on every network, the internet, the host).

| Rule | Primary enforcement | Assurance test (FIX-PLAN layer-1 nets) |
|------|---------------------|----------------------------------------|
| ARC-1 | **network separation** (each layer on its own docker/overlay network; deny-by-default egress) + broker-only component I/O (CMP-6) | **flow-map test**: enumerate running containers × their network memberships × actual socket edges; assert every edge crosses a declared door |
| ARC-2 | code: Kernel has no client to Network/App-Host for authz; **ADR-0123** | banned-pattern CI: no Kernel→upper-layer import/URL in an authz path |
| ARC-3 | **credential separation**: only the Kernel's DB role can read/write fact tables; other services get no fact-store credential | DB-grant audit: assert non-Kernel roles cannot `SELECT` fact tables; Vault policy audit (below) |
| ARC-4 | **audience-bound service tokens** (`svc_authz.ingress_gate` + `svc_token`): a door admits only a token addressed to it, minted by a listed caller | **route inventory**: each route declares `public`/`login`/`named-authority`/`internal-only`; per-service `calls:` cross-checked against observed edges |
| ARC-5 | **network separation** at the edge: only nginx is host-published; it proxies only D2 + D3 | external probe: every internal service + store is unreachable from the host/internet; only edge ports are open |
| ARC-6 | **one decision function** per door reading recorded state, fail-closed, gates armed-by-default (no shadow), writes a decision record | route-inventory anon probe (every non-public route → refusal); banned-pattern CI (token-role reads, fail-open handlers, default secrets); runtime decision-record presence |
| ARC-7 | **credential separation** (DB roles) + **Vault policies** (per-service policy, not a shared root token) + REG-18 Kernel-mediated files | Vault policy audit: each service token can read only its own paths; DB role audit as ARC-3 |

The five assurance nets named above — **network separation, credential separation, audience-bound service tokens,
route inventory, flow-map test** — are specified as CI/fresh-install gates in
[FIX-PLAN.md](../consolidation/FIX-PLAN.md) layer 1.

---

## d. Current state (local-dev) vs the spec — every off-map path is DEBT

Mapped against the `airawatos-localdev` compose + running containers.

**Containers / layers:** nginx (edge) · app-host · network · identity · kernel · secrets · filestore ·
model-gateway · notify · workflow · decision · automation · event-relay · scheduler · postgres · vault.

**Networks:** a **single implicit default network** (`airawatos-localdev_default`); the compose declares **no
per-layer `networks:` keys** → the topology is **flat**.

**Edge:** nginx publishes only `127.0.0.1:8080:80` and proxies three locations — `/`→app-host (D2), `/network/`→
network (D3), **and `/kernel/`→kernel (D7)**.

**Credentials:** per-service **DB roles exist** — kernel connects as `kernel_app`, network as `network_app`,
identity as `identity_lockout`, plus a `migrator` role and a `kernel` superuser/owner; all three app roles live on
the **same `kernel` database**, passwords stored at per-service Vault paths. **Vault**: all services share **one
`VAULT_TOKEN`** env var (no per-service Vault policy).

### ARC rule status

| ARC rule | Status | Deviation (DEBT) | Enforcing measured rows |
|----------|--------|------------------|-------------------------|
| **ARC-1** No call bypasses a door | **HELD** (network layer) | Per-boundary networks enforced + flow-map-tested (slice-1a); placed components confined to the broker-only net (**B52 closed at the container layer**). Residual at other layers: the in-process default runtime still inherits the host env (**B51**, Layer-7); apps/SDK still treat `/bridge/*` as the protocol (A23/CLI-6, Layer-5/7) | **ARC-1 HELD** (flow-map); CMP-5/CMP-6 |
| **ARC-2** Kernel never calls upward | **VIOLATED** | Kernel calls the Network for authority key/schemas/grants/tenant-dev (**DEBT-B9**); ADR-0123 open — Layer-2 | FND-7 (VIOLATED); ARC-2 NO TEST |
| **ARC-3** Only Kernel holds fact-store creds | **HELD** (network layer) | The fact DB is now reachable ONLY by kernel/network/identity (flow-map-tested); no other service can dial postgres. Residual: network/identity still connect **directly** rather than via the Kernel door (**DEBT-B57**, Layer-2) | **ARC-3 HELD** (flow-map); FND-6 |
| **ARC-4** Service reaches only its listed doors | **PLANNED(needs-build)** | Network boundaries are per-tier; per-service micro-segmentation inside the `aos-svc` mesh (a service dials only its `calls:` doors) is not yet enforced — shadow-default gates (**A72/B5**) remain the service-level control | **ARC-4 PLANNED**; CMP-1; svc_authz |
| **ARC-5** Internet reaches only edge + D2/D3 | **HELD** | The edge now proxies ONLY the App Host front door + the federation door; `/kernel/*` → 404 (flow-map + external probe). The Kernel door and every internal service/store are off the edge. Residual (Layer-5, not ARC-5): the public `/bridge/*`+`/embed/*` surface still needs rate-limiting/route-separation (B46) | **ARC-5 HELD** (flow-map) |
| **ARC-6** One fail-closed decision fn, recorded | **PARTIAL** | Kernel P0 gate + Trust-plane hold it; but shadow-default service gates (**A72**), unauthenticated privileged endpoints (**B5**), fail-open delivery (**B54**) and authority-from-token-role (**B1**) break it at several doors — Layers 2/5/6 | FND-2/8/12/16; ARC-6 NO TEST |
| **ARC-7** Store reachable only from layer above | **HELD** (network layer) | Vault is now reachable only by its declared clients (flow-map-tested); pure-compute services + the edge cannot reach it, and the fact store is not on the secrets net. Residual: those clients share one `VAULT_TOKEN` (no per-service policy — **DEBT-B58**, later Layer-1 slice); files REG-18 PLANNED | **ARC-7 HELD** (flow-map); REG-18 |

**Debt opened by the mapping (carried forward):** **DEBT-B57** (fact store reached directly by
`network_app`/`identity_lockout`, not Kernel-only — ARC-3 residual) and **DEBT-B58** (shared Vault token, no
per-service Vault policy — ARC-7 residual), both in [DEBT-REGISTER.md](../consolidation/DEBT-REGISTER.md).
**Closed by slice-1a:** ARC-5 (edge no longer exposes the Kernel), ARC-1/ARC-3/ARC-7 at the **network-boundary
layer** (flat net replaced by per-tier networks; **B52** closed for the container-placement path). Still open at
higher layers: B51 (in-process confinement, Layer-7), B9 (ARC-2, Layer-2), the shadow-default gates (A72/B5) and
ARC-4 micro-segmentation. The flow-map test (`conformance/flow_map_test.py`) is the standing enforcement.

---

## e. The full flow (text diagram)

```
                           ┌─────────────────────────── internet ───────────────────────────┐
                           │                                                                 │
                           ▼                                                                 ▼
                 ┌───────────────────┐   ARC-5: edge is the only ingress        (other participants /
                 │   D1  Public edge  │   (today also leaks /kernel/ → A1)         networks, signed)
                 │   (nginx :8080)    │
                 └───┬───────────┬────┘
            /  +/bridge  /embed   │ /network/                 /kernel/  ◀── ARC-5 deviation (A1)
                     ▼            ▼                               ▼
          ┌────────────────┐  ┌───────────────────┐    ┌───────────────────────────┐
          │ D2 App Host     │  │ D3 Federation /    │    │ D7 Kernel door (/v1/*)     │ ◀─ should be internal-only
          │ front door      │  │ D5 Network gov.    │    │ registry + broker          │
          │ (/bridge/*,     │  │ (Network svc)      │    │ P0 authz gate (FND-2)      │
          │  /embed/*)      │  └─────────┬──────────┘    │ broker caps = decl ∩ grant │
          └───┬────────┬────┘            │               └──────────────┬────────────┘
   D4 Identity│        │ internal svc calls (audience-bound tokens, svc_authz)        │
   (/login,   │        ▼                 ▼                                            ▼
    /jwks) ◀──┘  ┌──────────────────────────────────────────┐          ┌──────────────────────┐
                 │ internal services (internal-only, D7-ward)│          │   Postgres (facts)    │ ARC-3: Kernel only
                 │ secrets · filestore · model-gateway ·     │──D6─────▶│   (today also         │
                 │ notify · workflow · decision · automation·│  gateways│    network_app,       │
                 │ event-relay · scheduler · runtime-manager │          │    identity_lockout)  │
                 └───────────────┬──────────────┬────────────┘          └──────────────────────┘
                   secrets→Vault  │              │ filestore→blob files (REG-18, Kernel-mediated)
                                  ▼              ▼
                           ┌────────────┐  ┌────────────┐
                           │   Vault     │  │  filestore │   ARC-7: each store reached only from the layer above
                           │ (secrets)   │  │  (blobs)   │   (today: shared VAULT_TOKEN → B58)
                           └────────────┘  └────────────┘

  confined component ──(run-token)──▶ broker /v1/* (D7) ──▶ facts/files   ◀── ARC-1: the broker is the ONLY door…
       …but today the default runtime inherits the host env + joins the flat net (B51/B52) and can skip it.

  Legend:  ──▶ allowed declared flow     ◀── note/deviation
  Direction is always inward/downward (ARC-2: the Kernel never calls up).
```

**Target vs today in one line:** the door *shapes* and the per-door decision functions largely exist; what is
missing is the **separation that makes the doors unbypassable** — a flat network (ARC-1/ARC-5), a Kernel door and
stores that are not yet internal-only (ARC-5/ARC-3), shadow-default gates (ARC-6), and a shared Vault token
(ARC-7). Closing those is the substance of [FIX-PLAN.md](../consolidation/FIX-PLAN.md) layer 1.

---

## f. Request flow: login → app → Kernel (CURRENT vs TARGET)

The authenticated request path a person actually drives, and where each check sits. (Grounded in `identity.py`,
`app_host.py`/`hostcore.py`, `tokens.py`, the Kernel P0 gate.) This is the first-party desktop path; the embed
/participant SDK differs — the citizen's bearer JWT lives in the browser there (DEBT-B31/CLI-3).

### CURRENT — each gap marked by its DEBT id

```
 browser                         App Host (D2)                      Identity (D4)        Kernel (D7)
   │  POST /realms/<r>/login ──────▶│ forward creds ──────────────────▶│                    │
   │  (creds, no token)             │                                  │ password?+lockout  │
   │                                │                                  │ mint EdDSA JWT     │
   │                                │◀──────── access_token ───────────│ {sub,tenant,ROLES, │
   │                                │ tokens.verify(sig+exp)           │  iss,aud,exp}      │
   │                                │   └─ NO expected_aud  ◀───────────────── [DEBT-B59] user token not audience-bound
   │                                │ account-hold lookup  ◀──────────────────────────────── [DEBT-B47] fails OPEN on registry error
   │                                │ _SESSIONS[sid]={token,claims}  ◀───────────────────────[DEBT-B10] in-memory → restart = global logout (FND-5)
   │◀── Set-Cookie airawat_sid ─────│   (opaque; JWT stays server-side)◀──────────────────── [DEBT-B45] cookie no Secure; no CSRF/Origin
   │                                │                                  │                    │
   │  POST /bridge/<verb>  ─────────▶│ _ensure_session (exp+30, fail-closed)                  │
   │  (cookie only, app_id in body) │ route gate: _effective_roles(claims) & ADMIN_ROLES     │
   │                                │   └─ authority read from TOKEN ROLES ◀───────────────── [DEBT-B1] not a recorded grant (FND-1/2)
   │                                │ forward user's OWN token ───────────────────────────────▶│ tokens.verify(sig+exp), NO aud  [DEBT-B59]
   │                                │   └─ Kernel sees the USER, not "App Host for user" ◀───── [DEBT-B60] on-behalf-of not recorded (FND-17)
   │                                │                                  │           P0 registry authz gate (recorded grants, own-tenant) ✓
```

### TARGET

```
 browser                         App Host (D2)                      Identity (D4)        Kernel (D7)
   │  login ───────────────────────▶│ forward creds ──────────────────▶│ password + lockout │
   │                                │◀── user token (aud: app-host) ───│ identity-only       │
   │                                │ verify(sig+exp, expected_aud=app-host)  ◀────────────── audience-bound (B59 closed)
   │                                │ account-hold: fail-CLOSED on error ◀─────────────────── (B47 closed)
   │                                │ session in a DURABLE store (survives restart, shardable)◀ (B10/FND-5 closed)
   │◀── Set-Cookie (Secure, HttpOnly, SameSite) + CSRF token ───────────◀──────────────────── (B45 closed)
   │  POST /bridge/<verb> + CSRF ───▶│ ONE decision fn over RECORDED state (grant/role/consent),
   │                                │   writes a decision record  ◀──────────────────────────  (B1 closed → FND-2/FND-12)
   │                                │ mint on-behalf-of token: App Host SERVICE identity acting FOR the user,
   │                                │   audience-bound to svc:kernel ─────────────────────────▶│ verify(aud=svc:kernel)
   │                                │                                                          │ records BOTH principals
   │                                │                                                          │   (actor=app-host, represented=user)  (B60 closed → FND-17)
   │                                │                                                          │ P0 registry authz over recorded grants ✓
```

### Gaps → owning FIX-PLAN layer

| Gap (DEBT) | What | Owning layer ([FIX-PLAN](../consolidation/FIX-PLAN.md)) |
|---|---|---|
| **B1** | route/registry authority read from token `roles`, not a recorded grant | Cross-cutting **T1**; lands in Layer 2 (Kernel), 5 (App Host), 6 (services) |
| **B45** | session cookie no `Secure`; no CSRF/Origin check | **Layer 5** (App Host) |
| **B47** | account-hold check fails open on registry error | **Layer 5** (App Host) |
| **B10** | app-host `_SESSIONS` in-memory → restart = global logout (FND-5) | **Layer 5** (App Host) — thread **T5** |
| **B59** | user token not audience-bound; verifiers don't check `aud` on the user path | **Layer 3** (Identity mints audience/exchange) + **Layer 5** (App Host verify) |
| **B60** | user→App Host→Kernel on-behalf-of not recorded; Kernel can't tell the service from the user | **Layer 2** (Kernel records both principals) + **Layer 5** (App Host mints on-behalf-of) — relates to FND-17 |

Two ids are **new** (opened with this mapping): **DEBT-B59** (no audience on the user-token path) and **DEBT-B60**
(unrecorded on-behalf-of). The rest were already registered (B1, B45, B47, B10). The **TARGET** is one fail-closed
decision function over recorded state that writes a decision record, plus an **audience-bound on-behalf-of call**
where the App Host authenticates to the Kernel as its own service identity acting for the user — which is what
Layer-1 slice-1b's per-service Vault identities begin to make possible (each service gets its own credential).

---

## g. Per-service Vault policies (ARC-7, slice-1b — closes DEBT-B58)

The shared root `VAULT_TOKEN` is removed from every service. Each service authenticates to Vault via its own
**AppRole** (role-id + secret-id injected per-service; login done in the shared `prod-guard.sh` entrypoint) and
receives a **short-lived renewable** token scoped to a **least-privilege policy** that grants only the paths its
doors need. Policy files live in `deploy/local-dev/vault/policies/`; the installer creates them (step 3). The
root token is used only during install, then kept off every running service (step 4 guard refuses it).

| Service | Vault policy | Paths granted (least privilege) | Widened? |
|---|---|---|---|
| kernel | `svc-kernel` | `secret/data/localdev/kernel-app/*` (DB pw) + `transit/*` | **transit** (per brief; active use is REG-17/B23 future) |
| network | `svc-network` | `network-app` pw + `localdev-network/trust-{reader,writer,plane}/*` + `localdev-operator/provisioner/*` (1c-iv-c: svc:identity mint) + `transit/*` | no (transit = authority key; provisioner grant is exact — vault-scope test proves admin/app-host paths 403) |
| identity | `svc-identity` | `identity-lockout` pw + `transit/*` | no (transit = issuer key) |
| secrets | `svc-secrets` | `secret/data/*` + `secret/metadata/*` (read/write/delete) | **yes** — it IS the KV broker; per-(tenant,component) authz is in `secrets.py`'s own gate |
| model-gateway | `svc-model-gateway` | `secret/data/*` (read/write) | **yes** — per-tenant provider-key broker |
| scheduler / automation / event-relay | `svc-scheduler` | `secret/data/localdev-operator/scheduler/*` (one principal pw) | no |
| runtime-manager | `svc-runtime-manager` | `secret/data/localdev-operator/launcher/*` (the launcher principal pw — moved off svc-scheduler, 1c-iv step 2) | no |
| app-host | `svc-app-host` | `localdev-operator/*`, `localdev-network/component-publisher/*`, `localdev-developer/*` | modest — scoped to the 3 principal-bearing tenants, not exact principal names |
| filestore, notify, workflow, decision | *(none)* | — they use no Vault door | n/a |

**Widened policies, recorded (step 7 — "never widen without recording why"):** `svc-secrets` and
`svc-model-gateway` are broad on the KV data plane because both are *secret brokers* by design (ADR-0124) —
their fine-grained per-(tenant,component) authorization lives in the service's own request gate, not the Vault
policy; `svc-kernel` carries `transit/*` per the slice brief ahead of its active transit use; `svc-app-host` is
scoped to three tenant prefixes rather than exact principal names. Everything else is tight (one or two exact
paths). Tokens are renewable with a bounded TTL; an auto-renewer (Vault Agent sidecar) is the production
follow-up for truly short tokens — recorded, not yet built.

> **Update (slice-1c, step 4):** `svc-model-gateway` is **narrowed** from `secret/data/*` (the entire KV tree,
> any shape) to the per-(tenant,component) KV **shape** `secret/data/+/+/*` — the exact shape
> `secret/data/<tenant>/<component>/<key>` that `_vault_key`/`/admin/provider-key` use. It can no longer read
> root-level or 1-/2-segment paths (proven by the vault-scope test: a 2-segment read now returns 403). It is
> **not** moved to a disjoint provider-only prefix, because provider keys live on the **same component-secret
> plane** the Components-app "Settings → API keys" UI writes to (that is the "set your key in the UI" contract);
> so, like `svc-secrets`, its per-(tenant,component) **authorization** (which tenant/component a caller may
> read) is the **decision-function follow-up**, not a Vault path glob. `svc-secrets` **stays broad** because it
> *is* the KV broker; its gate (`SECRETS_INTERNAL`) carries the same decision-function priority. See §h.

## h. Inbound gate inventory (ARC, slice-1c — "GATES ON", closes A72/B5 where held)

Every externally-reachable write/spend/execute door and its **ingress gate**. Two mechanisms exist: the shared
`svc_authz.ingress_gate` (audience-bound service token verified against JWKS + a caller allow-list) and a
**bespoke** shared-literal `X-Internal-Token`. "Default" is the **code default** when no env flag is set.

Slice-1c inverts the stale semantics: the code now **defaults to ENFORCE**; a deployment opts a door into
**shadow only via an explicit `<SVC>_SHADOW` flag** (was: `<SVC>_REQUIRE_TOKEN` defaulting *off*). The
production startup guard (`prod-guard.sh`, step 3) **refuses to boot if any `*_SHADOW` flag is set** — so
production cannot run with a gate open.

| Door | Gate | Accept audience / token | Declared callers (the edge) | Default BEFORE 1c | Default AFTER 1c |
|---|---|---|---|---|---|
| scheduler `/run`,`/reload` | svc_authz | `svc:scheduler` | **app-host** | shadow (`SCHEDULER_REQUIRE_TOKEN`, armed=1 in compose) | **ENFORCE** (code default) |
| automation `/events` | svc_authz (`_authz_event`) | `svc:automation` only (platform aud **refused**, slice-1g B85) | **event-relay** (as `localdev-operator/scheduler`, tenant-pinned) | shadow (armed=1 in compose) | **ENFORCE** (code default) |
| notify `/notify` | svc_authz **(NEW)** | `svc:notify` | **decision, workflow** | **none** (DEBT-B5) | code default **ENFORCE**; local-dev **shadow via explicit `NOTIFY_SHADOW`** — decision/workflow have no service principal yet (recorded remaining wiring) |
| model-gateway `/transcribe` | svc_authz **(NEW)** (shared service-wide gate) | `svc:model-gateway` | **app-host** | **none** (DEBT-B5) | code default **ENFORCE**; shares the model-gateway gate below (held shadow by the kernel edge) |
| model-gateway `/admin/provider-key` | bespoke `X-Internal-Token` (`GW_INTERNAL_TOKEN`) | shared literal | **app-host** | enforce-when-set, **literal default `gw-internal`** (DEBT-A37) | **ENFORCE, fail-closed** (refuses when unset) |
| model-gateway `/complete`,`/embed` | svc_authz **(NEW)** | `svc:model-gateway` | **kernel** (`/complete`), app-host | **none** (DEBT-B5) | code default **ENFORCE**; local-dev **shadow via explicit `MODELGW_SHADOW`** — kernel caller unwired (A72 kernel sub-slice) |
| filestore `/files` (read+write) | svc_authz | `svc:filestore` | **app-host, kernel, launcher** | shadow (`FILESTORE_REQUIRE_TOKEN` unset) | code default **ENFORCE**; local-dev **shadow via explicit `FILESTORE_SHADOW`** — kernel+launcher readers unwired (A72 kernel sub-slice) |
| secrets `/materialize`,`/fetch` | svc_authz **(1c-iii)** | `svc:secrets` | **kernel** broker (`/fetch`), **launcher** (`/materialize`, in the runtime manager) | ENFORCE (literal `SECRETS_INTERNAL`) | **ENFORCE, always** — literal retired (A71); anon/wrong-aud 403 (conformance) |
| runtime-manager `/v1/invoke`,`/v1/ensure-connector` | svc_authz **(1c-iii; runs in local-dev since 1c-iv step 2)** | `svc:runtime-manager` | **scheduler** (installed runs), **kernel** (warm-connector ensure), launcher | ENFORCE (literal `RUNTIME_MANAGER_INTERNAL`) | **ENFORCE, always** — anon **401**, wrong-aud/undeclared **403** (conformance live). Scheduler never executes itself; in-process only via explicit dev flag `AIRAWAT_INPROCESS_COMPONENTS` (prod-guard refuses) |
| identity `/users` (POST+GET), `/set-password`, `/prefs`, `/realms`, `/realms/<t>/users` | svc_authz **(1c-iv-c)** + operator-realm check | `svc:identity` (verified against identity's **own** JWKS) | **provisioner** (installer phases, network join→provision) + **app-host** (own principal) — both `@<operator>` | ENFORCE (literal `IDENTITY_INTERNAL`; B29) | **ENFORCE, always** — literal retired (A71 closed, ADR-0131); unseeded provisioner ⇒ fail-closed + prod refuses boot (B29) |
| kernel `/v1/components/run-token` **(1c-iv step 3)** | kernel admin gate variant (home-issued platform service) + principal check | home-issued token, role `platform.scheduler`, principal on `RUN_TOKEN_READERS` | **scheduler** only | — (did not exist; the list read leaked no token, so runs broke — B61) | **ENFORCE, always**, audited allow/deny; returns ONE install's run-token |
| network **internal lookups** (13: `tenants/resolve`, `directory/resolve`, `grants/resolve`, `schemas/resolve`, `store/resolve`, `certificates/resolve`, `keys/resolve`, `interfaces/resolve`, `jurisdictions/resolve`, `packs/resolve`, `service-offerings/resolve`, `/v1/resolve`, `receipts/data-read`) **(1f)** | network `_require_internal_lookup` (`authn.verify(audience=svc:network)` + operator realm + caller allow-list) | `svc:network` | **per door** — see *Network internal doors — declared callers* below (slice-1g B86; was one set for all 13) | none — answered any caller | **ENFORCE, always** — anon 401; wrong audience / other realm / undeclared caller 403 |
| network **lists** with personal / institutional data (`join`, `credentials`, `data-requests`, `file-shares`, `service/transactions`, `participants`, `tenants`, request queues, `runtime/attestations`, `interfaces/bindings`) **(1f)** | network `_list_access` | `svc:network` (declared services) **or** a user token | service mode **per list** — see the table below; users (scoped to their own rows) | none — answered any caller | **ENFORCE** — anon 401; a user sees only its own tenant's/subject's rows; `join` = authority only; `interfaces/bindings` = services only; offerings: anon sees `visibility=public` only |
| network `/v1/runtime/attest` **(1c-iv step 5)** | network `authn.verify(audience=svc:network)` + caller allow-list | `svc:network` | **launcher** (the runtime manager attesting its certified images) | ENFORCE (literal `RUNTIME_ATTEST_INTERNAL`, code default `airawat-attest-internal`) | **ENFORCE, always** — literal retired; anon **401**, literal/wrong-aud/undeclared **403**, launcher admitted (conformance) |
| decision `/decide` | user-token authn (`tokens.verify`) | user bearer (AUTHORITY) | authenticated **users** | authn-only (no svc gate) | authn-only — **user-facing door**, not a service gate |
| workflow `/instantiate`,`/complete-task` | user-token authn (`tokens.verify`) | user bearer | authenticated **users** | authn-only | authn-only — user-facing door |
| decision/workflow `/verify`, model-gateway/embed `/healthz` | **none (public by design)** | — | anyone | none (intended) | none (public verify / liveness — documented, not debt) |

#### Internal service client — declared caller→door edges (DEBT-B174)

Every platform service reaches an internal door through ONE shared client, `aos_svc` (root `deploy/runtime/lib/aos_svc`,
shipped in every platform image). The client's methods are **generated from this table**: `aos_svc.client_for(caller)`
has an operation only when the caller is listed for it; anything else raises `NotDeclared`. Each call mints the
audience-bound token for the door, attaches it (never sends without one), applies the timeout and retries below (retries
only on 502/503/504/unreachable, never for a streamed body), carries `X-Request-Id`, and maps any refusal to a `DoorError`
with the door's reason and the status to answer with (never 500). `verify/svc_edges.py` keeps `aos_svc/edges.json`
identical to this table; `verify/banned_patterns.py` (GATED_DOOR_DIRECT) fails any request to these doors outside the
client. **Doors on the client now:** filestore, model-gateway. The remaining §h doors move in the first post-merge slice
(DEBT-B179), which then turns on "no raw HTTP to an internal service outside the client". Also on the client now: the
notify door (decision, workflow) and notify's ONE kernel write (`inbox_put`; audience `platform` = the platform token).
The kernel's notify lane admits notify ONLY for platform.inbox_item, ONLY with the originating caller's verified
svc:notify token and its request id, and records both on the item (notify decision).

<!-- svc-edges:begin -->
| door | audience | base | operation | request | timeout s | retries | callers |
|---|---|---|---|---|---|---|---|
| filestore | svc:filestore | FILESTORE_URL=http://filestore:8095 | put | POST /files | 60 | 2 | app-host, kernel |
| filestore | svc:filestore | FILESTORE_URL=http://filestore:8095 | get | GET /files/{id} | 30 | 2 | app-host, kernel, launcher |
| model-gateway | svc:model-gateway | EMBED_URL=http://model-gateway:8104 | complete | POST /complete | 90 | 3 | app-host, kernel |
| model-gateway | svc:model-gateway | EMBED_URL=http://model-gateway:8104 | embed | POST /embed | 30 | 2 | app-host, kernel |
| model-gateway | svc:model-gateway | EMBED_URL=http://model-gateway:8104 | transcribe | POST /transcribe | 95 | 0 | app-host |
| model-gateway | svc:model-gateway | EMBED_URL=http://model-gateway:8104 | provider_key | POST /admin/provider-key | 15 | 0 | app-host |
| model-gateway | svc:model-gateway | EMBED_URL=http://model-gateway:8104 | healthz | GET /healthz (public) | 10 | 1 | app-host |
| notify | svc:notify | NOTIFY_URL=http://notify:8094 | notify | POST /notify | 15 | 0 | decision, workflow |
| kernel | platform | AIRAWAT_API=http://kernel:8080 | inbox_put | POST /v1/registry/objects | 15 | 0 | notify |
<!-- svc-edges:end -->

#### Network internal doors — declared callers (slice-1g, DEBT-B86)

The authoritative caller set for every Network internal door and for the service mode of every gated list. Each door
admits an operator-realm `svc:network` token ONLY from the services named here (the realm check is mandatory; an
unconfigured realm admits no service). `conformance/net_doors_test.py` parses THIS table and proves, live, that each
door admits exactly these callers and refuses every other service — any difference fails. Callers were derived from
the code that calls each door (kernel, app-host + engines it hosts, scheduler, runtime manager `launcher`, identity,
decision/workflow `signing.py`).

<!-- net-doors:begin -->
| door | declared callers |
|---|---|
| `/v1/certificates/resolve` | launcher, scheduler |
| `/v1/directory/resolve` | kernel, app-host, scheduler |
| `/v1/grants/resolve` | kernel, app-host |
| `/v1/interfaces/resolve` | kernel, app-host |
| `/v1/jurisdictions/resolve` | app-host |
| `/v1/keys/resolve` | decision, workflow |
| `/v1/packs/resolve` | — |
| `/v1/receipts/data-read` | kernel |
| `/v1/resolve` | kernel |
| `/v1/schemas/resolve` | kernel, app-host |
| `/v1/service-offerings/resolve` | app-host |
| `/v1/store/resolve` | kernel, app-host, launcher, scheduler |
| `/v1/tenants/resolve` | kernel, app-host, identity |
| list `/v1/tenants` | kernel, app-host |
| list `/v1/interfaces/bindings` | scheduler, app-host |
| list `/v1/join` | app-host |
<!-- net-doors:end -->

`scheduler` on `certificates/resolve` and `store/resolve` is the in-process component path (development only; the
production guard refuses it, DEBT-B51). `packs/resolve` has no internal caller and admits none. `scheduler` on
`interfaces/bindings` is the automation daemon's principal (A68). Every other gated list's service mode is app-host only.


*(`embed.py` on :8104 is **not deployed** in local-dev — `EMBED_URL` points at the model-gateway, which serves
`/embed` on :8104 behind the model-gateway gate; the standalone embed service carries no gate of its own but
runs nowhere, so it is not in the table.)*

**The two kernel-edge gates** (model-gateway `/complete`, filestore read/write) are the only doors whose caller
set includes the **kernel**, which today has Vault + JWKS-verify but **no service principal and no `svc_token`**
(it authenticates *components* by run-token, it does not mint an identity token of its own). Their gate code
defaults to ENFORCE, but local-dev holds them open with an **explicit** `MODELGW_SHADOW` / `FILESTORE_SHADOW`
flag (never the old silent unset-is-off), the kernel edge is **declared here**, and the prod guard refuses those
flags — so the forcing function is real: production cannot start until the **kernel sub-slice** wires a kernel
service principal (`secret/data/<inst>/kernel/password` + identity user, installer-seeded) + `svc_token`, and
attaches `Authorization: Bearer <svc:model-gateway|svc:filestore>` on the kernel's two egress calls
(`app.py` `/v1/complete` forward + the filestore read/write helpers) and the launcher's filestore reads. This is
the remaining half of DEBT-A72.

> **Resolved (slice-1c-iv) ✅ — NO shared-literal internal gate remains in current code.** Every internal door in
> this table is an audience-bound service-token gate with a declared caller allow-list, always enforced: identity
> (`svc:identity`, 1c-iv-c), runtime-manager (`svc:runtime-manager`, now running in local-dev — step 2), network
> runtime-attest (`svc:network`, step 5), kernel run-token (scheduler-only, step 3), plus the 1c-ii/1c-iii doors.
> Proven by a cross-repo grep (no `X-Internal-Token` / `*_INTERNAL` compare in any service) and live conformance
> (anon / retired-literal / wrong-audience / undeclared-caller refused; declared callers admitted). **Recorded
> exceptions (not internal gates):** the inbound SMS/message channel gateway still uses ONE operator secret — now in
> Vault, constant-time, env not honoured (DEBT-B64 interim; target per-provider per-tenant signed webhooks, Layer 6
> with B46); and the **legacy** stacks (root `docker-compose.yml`, `deploy/local`, EC2 compose) still pin pre-A71
> images whose gates ARE the literals — their `SECRETS_INTERNAL` / `RUNTIME_MANAGER_INTERNAL` lines are annotated
> LEGACY and go away when those stacks move to reference `dev-hard16+` via the ADR-0131 installer.

> **Resolved (slice-1c-ii) ✅:** the kernel-edge gates now **ENFORCE** in local-dev and on a fresh install. The
> installer (Phase 1c) seeds Vault-backed, audience-bound **service principals** (role []) for the remaining
> edge callers: **kernel** [`svc:model-gateway`, `svc:filestore`] attaches on `/v1/complete` + broker file
> put/get; **decision** + **workflow** [`svc:notify`] on their notify posts; **launcher** [`svc:filestore`]
> (in-process in scheduler) on component-source fetch; **app-host** gains `svc:model-gateway` for
> `/embed`,`/transcribe`,`/admin/provider-key`. `GW_INTERNAL_TOKEN` is retired (provider-key is now
> `svc:model-gateway`-gated, allow `{app-host}`, always-enforce). All three `*_SHADOW` flags are removed. The
> install seeds principals **before** base-app delivery (which writes/reads the filestore). **DEBT-A72 is
> closed** — no svc_authz gate remains shadow. Conformance: anon→401/403 + wrong-audience→403 PASS for all five
> doors; fresh install external 13/0, internal 35 PASS/6 XFAIL/0 XPASS/0 FAIL.

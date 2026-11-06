# ARCHITECTURE-FLOWS — v0.1 (ARC)

> **Status is conformance-measured where a rule has a test** — see [STATUS-MATRIX.md](STATUS-MATRIX.md). ARC rules
> are not yet wired into `conformance/run.py`/`build_matrix.py` (that is FIX-PLAN layer-1's *flow-map test*); until
> then the **ARC status table in §d is authoritative for ARC rules**, each row cross-linked to the measured
> FND/CMP/REG rows that enforce it and the debt that keeps it from HELD.

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
| **ARC-1** No call bypasses a door | **VIOLATED** | Flat network → any container can dial any service directly; confined components bypass the broker (**B51** in-process inherits host env; **B52** container no egress policy); SDK/apps treat `/bridge/*` as the protocol (A23/CLI-6) | CMP-5, CMP-6 (PLANNED); FND-8 (VIOLATED) |
| **ARC-2** Kernel never calls upward | **VIOLATED** | Kernel calls the Network for authority key/schemas/grants/tenant-dev (**DEBT-B9**); ADR-0123 open | FND-7 (VIOLATED) |
| **ARC-3** Only Kernel holds fact-store creds | **PARTIAL** | `network_app` and `identity_lockout` connect to the `kernel` fact DB **directly**, not via the Kernel door — least-privilege roles bound the blast radius but the fact store is reached by 3 services, not 1 (**new: DEBT-B57**) | FND-6 (PARTIAL); per-service DB roles (partial) |
| **ARC-4** Service reaches only its listed doors | **PARTIAL** | `services.yaml` declares `calls:` but there is no enforcement that a service dials only those; shadow-default gates (**A72/B5**) let an undeclared caller through on a flat net | CMP-1 (PARTIAL); svc_authz (armed scheduler/automation only) |
| **ARC-5** Internet reaches only edge + D2/D3 | **VIOLATED** | nginx also proxies `/kernel/` → the Kernel door is internet-reachable, and anonymous kernel reads succeed (**DEBT-A1**); the full `/bridge/*` + `/embed/*` surface is internet-facing (slice-4 B41/B42/B46) | REG-6/FND-8 (VIOLATED); A1 |
| **ARC-6** One fail-closed decision fn, recorded | **PARTIAL** | Kernel P0 gate + Trust-plane hold it; but shadow-default service gates (**A72**), unauthenticated privileged endpoints (**B5**), fail-open delivery (**B54**) and authority-from-token-role (**B1**) break it at several doors; failed-auth largely unlogged (**A9**) | FND-2/8/12/16 (VIOLATED/PARTIAL) |
| **ARC-7** Store reachable only from layer above | **PARTIAL** | DB-role separation + Kernel-mediated files hold the *shape*, but the **shared `VAULT_TOKEN`** means any service can read any Vault path (no per-service policy) (**new: DEBT-B58**); files REG-18 PLANNED | REG-18 (PLANNED); FND-10 |

**New debt opened by this mapping:** **DEBT-B57** (fact store reached directly by `network_app`/`identity_lockout`,
not Kernel-only — ARC-3) and **DEBT-B58** (shared Vault token, no per-service Vault policy — ARC-7). Both are
recorded in [DEBT-REGISTER.md](../consolidation/DEBT-REGISTER.md). The flat-network and shadow-default deviations
(DEBT-B52, A72, B5) are carried from slices 5–6, not re-opened.

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

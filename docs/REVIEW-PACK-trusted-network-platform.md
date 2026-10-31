# Architecture Review Pack — AirawatOS as a Trusted Network Platform

- Date: 2026-10-31
- Scope: the system **as implemented today**, including incomplete areas, shortcuts and debt. No redesign.
- Primary evidence: `/Users/manishsv/Documents/Projects/Airawat` — `kernel/`, `network/`, `platform-spec/reference/`,
  `components/`, `deploy/`, `tests-repo/`. References are `file:line`. Status tags: **[IMPLEMENTED] / [PARTIAL] /
  [NOT-IMPLEMENTED]**.

---

## Executive verdict (the question the reviewer asked)

> *Is this a genuine generic Trusted Network Platform on which networks like Avsar and TOP can be configured, or an
> Avsar-specific build partially generalized?*

**Answer: it is a genuinely generic platform for the SERVICE/CREDENTIAL exchange pattern (Avsar-class), but it is
NOT yet a multi-pattern Trusted Network Platform — an event-exchange network like TOP cannot be configured today
without new code.** Three findings support this:

1. **The generic core is clean.** The kernel (registry/broker/decision) and the network authority contain **no**
   Avsar/worker/eShram/labour/traffic/road business logic — every such string is a comment, demo path, or
   data-driven default (one cosmetic exception: scaffold defaults in `hostcore.py:315`). Domain verticals live
   only in `components/*` and seed data. The design explicitly forbids domain verbs in the host
   (`app_host.py:208`). So "Avsar" is already content, not code.

2. **Service-Exchange (Avsar) is substantially configurable, with real gaps.** Networks, participants,
   roles/grants, provide/consume over governed Nouns/Verbs, eKYC join, credentials (issue/verify/revoke),
   wallet, and a service gateway all exist and are config-driven. But: credentials are a **signed-JSON stand-in,
   not W3C VC**; the **Requirement/eligibility manifest is not implemented** (only a flat `required_credentials[]`
   at the solution-workflow layer); the **IdP registry (`network.idp`, `verified_by`) does not exist** (external
   identity plugs in via the single ADR-0084 trusted-issuer map); credentials are **not yet wired into the
   `network.service` layer**; and the **Network Client / Participant Server SDKs are design-only** (ADR-0117/0118,
   Proposed) — only the ADR-0112 embed SDK is built.

3. **Event-Exchange (TOP) is essentially unimplemented.** There is **no** generic event publish/subscribe/route
   engine, **no** Resource registry (road/segment/intersection), **no** Authority-over-Resource model, and **no**
   Observation/Transformation machinery. A `network.jurisdiction` noun and a service gateway exist, but routing an
   event to multiple authorities by resolved jurisdiction + subscription is not built. **TOP would require new
   platform code, not configuration.**

**Net:** the foundations (governed registry, participants ≠ tenants, native/external one-contract, trust map,
credentials) are generic and sound; the platform is honestly a **Service-Exchange Trusted Network** today, on a
path to the broader two-pattern platform the ADRs describe. The event plane, resource/authority model, and the
packaged SDKs are the main gaps between "Avsar-class" and "generic Trusted Network Platform."

---

## 1. Repository map

```
Airawat/
├── kernel/            trusted kernel: governed bitemporal registry + broker (confinement) + decision/service/federation
│   ├── api/app.py                 (~2361 L) FastAPI — /v1/registry/*, /v1/read|write|query, /v1/complete|embed
│   └── services/ registry/(store,pg_store,query) · broker/ · decision/ · service/ · federation/ · receipts/
├── network/           AirawatNetwork authority (standards body + marketplace + membership)
│   └── api.py                     (3552 L) FastAPI — ~130 routes; authority.py, authn.py, crypto.py, store.py, seed_base.py
├── platform-spec/reference/   the running reference OS
│   ├── app_host.py                (10194 L) ThreadingHTTPServer, ~160 /bridge/* + /embed/* + /t/ + /portal + /ekyc
│   ├── hostcore.py (619) · routes/*.mixins (studio/marketplace/service/civic/governance/knowledge)
│   ├── identity.py (508) reference IdP · scheduler.py (588) · model_gateway.py (361) · secrets.py · filestore.py
│   └── workflow.py · decision.py · automation.py · event_relay.py · notify.py (generic engines) · *.html
├── components/        apps(59) engines(66) drivers(50) solutions(20) + runtimes/providers/skills/experts/demos
├── services/          mospi-gateway · service-gateway (scalable read tier)
├── deploy/local/      docker-compose.yml, nginx.conf, vault/, overlays/
└── tests-repo/        black-box e2e: test_{network,kernel,identity,app_host,filestore}.py, smoke, e2e_service_interpreter
```

**Plane classification**

| Component | Plane | Notes |
|---|---|---|
| kernel (`kernel/api/app.py` + services) | **Control + Transaction** | the governed registry (write gate, query), broker confinement, decision/service, confined LLM |
| network (`network/api.py`) | **Control (governance authority)** | standards body: certify, schemas/interfaces/roles/packs, membership, marketplace, service directory, grants |
| app_host (`app_host.py` + routes/*) | **Experience + mixed Control/Transaction** | desktop/apps + ~160 `/bridge/*` verbs = the single governed browser↔backend door; embed OIDC server |
| identity (`identity.py`) | **Infrastructure (reference IdP)** | realms, login, JWKS, per-tenant issuers |
| broker (`kernel/services/broker`) | **Transaction (SDK-integration boundary)** | the only I/O a sandboxed component gets |
| scheduler / model-gateway / filestore / secrets / notify / event-relay | **Infrastructure** | event-relay = **federation mail relay**, NOT a generic event bus |
| components/* | **Network-specific config / content** | every vertical (incl. worker-passport, roads, flood) lives here |

**Avsar/domain concepts in generic code:** effectively none. `eshram`/`avsar`/`labour`/`road` → 0 in kernel +
network core; the handful of hits in `app_host.py` are the `/demo` worker-passport try-it page, a data-driven
embed brand ("Sign in with Avsar" from the registered `platform.app_client`, default "Airawat"), and comments.
The only real hardcoded domain names in generic code are scaffold reference-defaults (`hostcore.py:315` —
`flood-risk`, `flood-advisory`, `air-quality-expert`) used when generating a new component skeleton. **Debt:
neutralize those defaults.**

**Debt — monolith sizes:** `app_host.py` 10,194 L (raw ThreadingHTTPServer, hand-rolled bridge table);
`network/api.py` 3,552 L. Mixin extraction started (`routes/*`) but the bulk remains in-file.

---

## 2. Current architecture (components & boundaries)

- **Control plane** — `network/api.py` (governance authority: who may participate, what schemas/verbs/roles/packs
  exist, certification, membership, service/offering definitions, grants) + the kernel's schema-provisioning.
- **Transaction / exchange runtime** — kernel `/v1/registry/*` (reads/writes/query over the bitemporal store) +
  the network **service gateway** (`/v1/service/route`, `SERVICE_TXNS` ledger) + app-host `/bridge/*` as the
  browser-facing exchange surface.
- **Participant gateway** — native components run behind the **broker** (`kernel/services/broker`); external
  participants connect via **connectors** (`kernel/services/broker/connector_gateway.py`) + the network service
  `endpoint` binding; no dedicated participant Server-SDK yet.
- **Trust services** — the Authority CA (`network/authority.py`, `crypto.py`): signs participant directory
  entries, tenant records, schema/interface records, component certificates; the **trusted-issuer map**
  (`TRUSTED_ISS`, `authn.register_issuer/verify`) honours federated token issuers.
- **Credential infrastructure** — `network/api.py:2667-2826` (`civic.credential`): issue/accept/verify/revoke,
  Ed25519 signed-JSON, revocation status-list + expiry.
- **Wallet infrastructure** — holder-keyed VCs in the network store + accepted copies deposited into the citizen's
  own tenant registry (`my-documents` app); embed `/embed/wallet`.
- **Policy / authorization** — the kernel **P0 single-registry authz gate** (write/read scoped by `(sub, tenant)`),
  `governance.access_grant` (steward-signed, broker+kernel enforced), component certificate verification at app
  load, sandbox-privilege rules.
- **Service execution** — ADR-0067 directory+gateway (`/v1/service-offerings`, `/v1/service/route`), sync; the
  generic `workflow`/`decision`/`automation` engines; the broker for confined native fulfilment.
- **Event exchange** — **NOT a plane today.** `event_relay.py` is federation mail; registry-write events exist as
  a substrate (ADR-0089 is Proposed). No generic publish/subscribe/route.
- **SDKs** — the **embed SDK** (`/embed/sdk.js`, ADR-0112) only.
- **Persistence** — Postgres: the kernel bitemporal `registry_version` table; the network authority's own
  `Namespace` KV (Postgres-backed when available, else in-process dict); Vault for secrets/keys; filestore for
  blobs.
- **External systems** — connect as federated participants (trusted issuer + service endpoint); the eKYC/Aadhaar
  check is currently **simulated** (`app_host.py:1744`).

---

## 3. Core domain model (implemented vs not)

Ownership note: governed vocabulary (schema/interface/role/pack/domain) is **network-authority**-owned; per-tenant
data is **tenant**-owned in the kernel registry, id-scoped `ds:<tenant>:<schema>/<local>`.

| Object | Status | Where / shape | Notes |
|---|---|---|---|
| **Network** | [IMPLEMENTED] | `NETWORKS` ns; `/v1/networks`, `/v1/network/profile`; `{label, blurb, participant_types[], domains}` | a tenant carrying `network.admin` + a profile |
| **Participant** | [IMPLEMENTED] | `PARTICIPANTS` directory (CA-signed) + `PARTICIPATION` membership edge `(participant,network)` | tenant-free membership (ADR-0116) |
| **ParticipantRole / Capability** | [PARTIAL] | roles in the token + `network.role` governed vocab; `participant_type` carries provide/consume | **capability-by-explicit-grant (`roles[]`+`authorized_credentials[]`) NOT modelled** — capability is inferred from type + membership |
| **Authority / Jurisdiction** | [PARTIAL] | `/v1/authority` (the network's own CA identity); `/v1/jurisdictions` (`network.jurisdiction`) used for service-offering matching | **no authority-over-a-resource model** (who may act on road X) |
| **Resource** | [NOT-IMPLEMENTED] | — | no road/segment/intersection/signal registry; `space.*`/`geo.*` exist for cities but not as governed network resources with authority |
| **IdentitySource** | [PARTIAL] | `TRUSTED_ISS` trusted-issuer map + `citizens` realm + `EMBED_EKYC_ISSUER` | **no `network.idp` registry / `verified_by` policy** |
| **CredentialType** | [IMPLEMENTED] | governed at runtime: a type must be a published `credential.*` schema (`api.py:2673`) | no seeded types; created via `/v1/schemas` |
| **Credential** | [IMPLEMENTED] | `civic.credential`, Ed25519 signed-JSON; issue/accept/verify/revoke | **not W3C VC** (no `@context`/`credentialSubject`) |
| **Offering** | [PARTIAL] | `service-offerings` (ADR-0067) carry title/scope/jurisdiction; `network.service` carries provide/consume | **no unified `Offering` object** spanning jobs/training/insurance with eligibility + outputs + validity |
| **Requirement** | [PARTIAL] | flat `required_credentials[]` on a solution's workflow steps (`api.py:2582`) | **no nested all/any manifest, no claim predicates/issuer/freshness/assurance** |
| **Service** | [IMPLEMENTED] | `network.service {service_id, interface, endpoint, provider, scopes, visibility}` + offerings | business service; mechanism verbs are separate interfaces |
| **ServiceRequest** | [IMPLEMENTED] | `network.service_request` (`/v1/network/services/apply`), `SERVICE_TXNS` for gateway | apply→decide (provider grant) |
| **Authorization / Consent** | [IMPLEMENTED] | ADR-0103 consent recorded on VP (`/embed/present`); ADR-0067 S5 service consent; `governance.access_grant` | |
| **Presentation** | [IMPLEMENTED] | `/embed/proof-request` → `/embed/present` → `/embed/verify-presentation` (challenge/nonce, holder sig, X25519 seal) | holder keys are server-side stand-ins |
| **Observation** | [NOT-IMPLEMENTED] | — | |
| **Event** | [PARTIAL] | registry-write events / webhooks as substrate; ADR-0089 Proposed | no governed `Event` type + routing |
| **Subscription** | [NOT-IMPLEMENTED] | — | |
| **Fulfilment** | [PARTIAL] | native via broker; external via connector/endpoint; `/v1/service/route` | **synchronous only**; async callbacks not built |
| **Outcome** | [PARTIAL] | service txn status; a workflow step may `issues:` a credential | no first-class outcome object |
| **Wallet** | [IMPLEMENTED] | holder-keyed network store + accepted-copy in citizen tenant; `/embed/wallet`, `my-documents` app | platform-stored, holder-controlled; not a device wallet |
| **Endpoint** | [IMPLEMENTED] | `network.service.endpoint` + connector registry + interface bindings (ADR-0063) | |
| **Policy** | [PARTIAL] | `org.policy` + policy-resolve (ERP); registry authz gate; cert gates | no unified network policy-evaluation engine for requirements |
| **AuditEvent** | [PARTIAL] | registry `prov`/`history` (bitemporal), decide records (`decided_by/at`), connector audit (`_connector_audit`) | not a unified, queryable audit log across all primitives |

---

## 4. Database model

**Kernel registry — one bitemporal table (`kernel/services/registry/pg_store.py`).**
- `registry_version(seq BIGSERIAL PK, id TEXT, kind TEXT, version TEXT, object JSONB, valid_from TEXT, valid_to
  TEXT, tx_from TEXT, tx_to TEXT, content_hash TEXT, agent TEXT, schema_version TEXT, retracted BOOL)`.
  **Bitemporal**: `tx_from/tx_to` (transaction time) + `valid_from/valid_to` (valid time). A row is "live" when
  `tx_to IS NULL`.
- `registry_schema_meta(schema_code PK, definition JSONB, x_indexes JSONB, x_timeseries JSONB, provisioned_at)`.
- Indexes: `rv_id(id)`, `rv_live(id) WHERE tx_to IS NULL`, `rv_schema((object#>>'{schema}'))`,
  `rv_one_open(id) UNIQUE WHERE tx_to IS NULL`, `rv_live_schema_id` partial on (schema,id) for query pushdown;
  per-schema `rvx_*` dynamic indexes from `x_indexes`.
- Writes append a new version + close the prior open row; retract sets `retracted`. History/prov read the chain.

**Tenant/network isolation.** Object **id is tenant-scoped**: `ds:<tenant>:<schema>/<local>`. The kernel's P0
authz gate scopes reads/writes by the caller's `(sub, tenant)` so a token for tenant A cannot write B's ids, and
reads are tenant-scoped unless a `governance.access_grant` (ADR-0103, steward-signed) opens a specific object/
schema to another tenant (the cross-tenant aggregator lane: `/v1/data-requests` asks, the target tenant decides,
a grant is issued, the broker+kernel enforce it). **There is no physical per-tenant schema/DB partition — isolation
is logical, id-prefix + authz-gate based.** Two networks' data are isolated the same way (each network is a tenant;
its governed records are `ds:<network>:...`).

**Network authority store (separate from the kernel registry).** `network/api.py` keeps its governance state in a
`Namespace` KV (`_NS`/`_backend`, `api.py:33-47`) — Postgres-backed when `KV()` connects, else an **in-process
dict**. Namespaces: participants, certificates, listings, schemas, interfaces, packs, roles, domains, grants,
solutions, participation, networks, network_services, participant_profiles, service_requests, credentials,
trusted_issuers, data_requests, file_shares, jurisdictions, service_offerings, service_transactions, tenants,
joins, email_codes. **Debt (known):** some network state (certificates + publish-requests) has historically been
in-memory and wiped on restart — confirm per-namespace durability before production.

**Versioning:** schemas/interfaces carry a `version`; republish requires a higher version (immutability of a
published (id,version)). Registry objects version via the bitemporal append. **Audit/history:** bitemporal
`history`/`prov` endpoints; no separate append-only audit table.

---

## 5. Network configuration model

A network is configured as the `NETWORKS[net]` profile + its governed vocabulary (schemas/interfaces/roles the
network publishes) + participants + offerings/services. Profile shape today:
`{network, label, blurb, domains[], description, participant_types:[{id,label,description, identity?, provide:[{kind:'noun'|'verb',ref}], consume:[...]}]}`.

**A. AVSAR — configurable TODAY (with the gaps noted):** participant types (eShram, platform, employer,
fleet-operator, training-provider, insurer, lender, benefit-provider) + their provide/consume matrices of
governed Nouns/Verbs; a `worker` type flagged `identity:"citizen"` for eKYC join; credential types governed via
`/v1/schemas` (`credential.worker-registration`, `.skill`, `.work-experience`, `.insurance-coverage`); services
offered with interface+endpoint. **What's config:** all of the above. **What needs code:** the unified `Offering`
object + eligibility manifest; wiring `issue-credential`/`verify-credential` into `network.service`; the IdP
registry; the client/server SDKs.

**B. TOP — NOT configurable today:** it needs Resources (road/segment/intersection), Authority-over-Resource,
Event types, Subscriptions, and event routing — **none implemented**. A network profile can list participant
types and jurisdictions, but there is no event plane to carry observations/events. **TOP ⇒ new platform code.**

**Config-vs-code boundary:** *config* = participant types, provide/consume matrix, governed schema/interface/role
vocabulary, credential types, service endpoints, jurisdictions, eKYC `identity:"citizen"` flag. *Code* = anything
in the event/resource/authority/observation/transformation space; the eligibility manifest; the IdP registry; the
SDKs.

---

## 6. Control plane (administration & authorization)

Administered via `network/api.py` endpoints, gated to the relevant authority:
- networks/profile/types → `POST /v1/networks` (`_require_network_admin`); participant roster → `/v1/participants`
  (+ Network-Admin app).
- credential schemas / event schemas / resource schemas → `POST /v1/schemas` (change-request flow, authority
  signs; `/v1/schema-requests`). **Event/resource schemas aren't special — they'd be governed nouns, but no
  runtime consumes them for events/resources yet.**
- interfaces (verbs) → `/v1/interfaces` (+ `/v1/interfaces/bind` for endpoint bindings).
- roles → `/v1/roles` + `/v1/role-requests`; packs → `/v1/packs`.
- trust / identity providers → `/v1/trusted-issuers` (register/revoke a federated issuer). **No `network.idp`
  config object.**
- offerings / service interfaces → `/v1/service-offerings` (+ steward `/v1/service-offerings/steward`).
- jurisdictions → `/v1/jurisdictions`.
- subscriptions / wallet providers / endpoint-for-event → **not administered (not implemented).**
- endpoints → on the `network.service` record + connector registry.

**Authorization:** `_require_network_admin(network)` = token tenant == the network AND role ∈ {network.admin,
network.steward, platform.steward, admin}. Schema/role/pack changes go through a change-request → authority signs
(ADR-0056). A tenant admin administers only its own tenant; the network authority administers the network vocab.

---

## 7. Participant model

Join (ADR-0116): `POST /v1/participation/request` (any principal applies, tenant-free — a local authenticated
caller, a self-asserted remote applicant with issuer+jwks, or a HOSTED web-form applicant) → the network's own
admin `POST /v1/participation/decide` (approve/reject/revoke). On approve: for a **federated** applicant, the
trust handshake registers its issuer (`register_issuer`); for a **HOSTED** applicant, a login is provisioned in
the shared `<instance>-participant` realm (identity `/users` + temp password); for an **individual via eKYC**,
`/v1/participation/ekyc-admit` auto-admits a citizen. **Key registration** = the CA-signed directory entry
(`PARTICIPANTS`); **endpoint registration** = on the service record. **Suspension/revocation** = `decide` with
`revoke` (tears down trust + membership).

**Classification vs authorization — [PARTIAL / the weak spot].** The platform does distinguish a participant's
*type* (vocabulary: employer, insurer, …) from its *membership status* (approved/pending). But capability is
**not** a separate explicit grant: what a participant may provide/consume is read from its `participant_type`'s
matrix + its approved membership, and roles come from the IdP token. There is **no** `authorized_credentials[]` /
per-participant capability-grant object, so a single participant wearing two hats (e.g. provider + credential-
issuer) is expressed by its type's matrix, not by composable capability grants. The review's "capability ≠ type"
principle is **partially** met (type is vocabulary; membership gates) but **not** fully (no explicit capability
grants).

---

## 8. Native vs external participants

**One contract, two realizations — [IMPLEMENTED at the data level, PARTIAL at runtime].** A `network.service`
carries `interface` (a governed verb) + a binding: native services run as certified components behind the
**broker** (confined I/O: read/write/secret/egress/finish, capability-checked); external services carry an
`endpoint` reached via the connector gateway / `/v1/service/route`. The gateway resolves offering → provider +
endpoint, verifies the action, mints a `SERVICE_TXNS` correlation id.

**What exists:** participant gateway (broker + connector_gateway), request forwarding with the caller's token,
connector endpoint-trust (SSRF guard), the service-txn ledger. **What's missing / debt:** no packaged **Server
SDK / Network Adapter**; **callbacks, retries, idempotency keys, timeout policy, async completion** are **not**
first-class — fulfilment is synchronous (`/v1/service/search` notes async provider search is "a later slice"). An
external system today integrates by exposing an endpoint + registering as a trusted issuer; there is no standard
adapter library.

---

## 9. Offering & service model

- **Service (business) — [IMPLEMENTED]:** `network.service` + `service-offering` (title/scope/jurisdiction/
  entitlement).
- **Offering (unified discoverable unit) — [PARTIAL]:** `service-offerings` are the closest thing, but there is no
  single `Offering` object spanning job/training/insurance/benefit with eligibility + outputs + validity.
- **Network primitives vs business services — [PARTIAL, good direction].** Mechanism is kept out of business
  services: the host explicitly forbids domain verbs (`app_host.py:208`); verbs are governed interfaces
  (ADR-0058) and there's a verb-consolidation effort to 5 generic planes (ADR-0091, in progress). Of the target
  primitive set `discover · request · authorize · present · verify · publish · subscribe · route · invoke · issue
  · status · revoke · notify · audit`: **present/verify/issue/revoke** exist (credential/embed), **route/
  request/status** exist (service gateway), **discover** exists (service search / embed discover), **authorize/
  audit** partial; **publish/subscribe/notify(as events)** **NOT-IMPLEMENTED** as governed primitives. So the
  separation is real but the primitive set is **incomplete on the event side**.

---

## 10. Requirement / policy model

**[NOT-IMPLEMENTED as a manifest].** The only requirements model today is a **flat list**: a solution's
workflow step carries `required_credentials: [governed credential types]` that a citizen must PRESENT, and may
`issues: <governed credential type>` (`api.py:2576-2584`). There is **no** support for AND/OR nesting, claim
comparisons (`activeDays >= 90`), issuer restrictions, participant-role restrictions, freshness, assurance level,
jurisdiction, or optional evidence.

The requested example — `WorkerRegistrationCredential AND (WorkExperienceCredential.activeDays>=90 OR
EmploymentCredential.durationMonths>=6)` — **cannot be expressed today**. Evaluation of the flat list happens in
the solution/workflow engine and in the embed proof flow (the relying app names a type; the holder presents it).
**Discovery + eligibility matching over claim predicates does not exist**, so there is no privacy-preserving
"show me offerings I qualify for" path — and with the current design, presenting a credential sends the signed VC
(with its claims) to the verifier, so **sensitive claims do leave the wallet/client at presentation time**
(there is no selective-disclosure / ZK predicate proof — see §11/§22).

---

## 11. Credential architecture

- **Format — [PARTIAL]:** `civic.credential` = Ed25519-signed, JCS-canonicalized **JSON** (`crypto.py` suite
  `mdk-sig-ed25519-jcs-2025`), `{conforms_to, id, issuer, issuer_tenant, holder, type, title, claims, subject_ref,
  issued_by, issued_at, expires_at?}`. **Not a W3C VC** — no `@context`, `credentialSubject`, `VerifiableCredential`
  type, or `proofPurpose`. A VC-shaped signed JSON.
- **Signing / issuer identity — [IMPLEMENTED]:** issuing **tenant's Vault steward key**; signs only the immutable
  `core` (status excluded). Issuer identity resolved from the CA-signed participant directory entry; verified
  offline against the issuer's published key (local-signer fallback in the reference).
- **Verification — [IMPLEMENTED]:** `/v1/credentials/verify` → `verified` iff signature valid AND not revoked AND
  not expired.
- **Credential type registry — [IMPLEMENTED]:** must be a published `credential.*` schema; governed via change
  request.
- **Revocation — [IMPLEMENTED]:** authoritative status-list lookup by id in the issuing network; `offered →
  accepted → revoked` kept outside the signed core. If id unknown locally → `revocation_checked:false` (signature-
  only).
- **Expiry — [IMPLEMENTED]** (signed `expires_at`). **Suspension — [NOT-IMPLEMENTED]** for credentials (only for
  service-offerings). **Replacement/correction — [NOT-IMPLEMENTED]** as a first-class flow (re-issue under a new
  id). **Key rotation — [PARTIAL]** via the directory/Vault; no credential-level key-rotation bookkeeping.
- **Credential vs certificate — [IMPLEMENTED, distinct]:** `civic.credential` (VC to a person) is entirely
  separate from `CERTIFICATES` (component/participant **conformance certification** by the Authority CA). Two
  stores, two signers, two meanings. (The user-facing word "certificate" as a rendering of a credential is a UX
  concept; the data model consistently uses *credential*.)

---

## 12. Wallet architecture

**[IMPLEMENTED as a platform/network-stored, holder-controlled store — NOT yet a provider interface].** Offered
VCs live in the network credential store keyed by holder `sub`; on **accept**, a copy is deposited into the
**citizen's own tenant** kernel registry (`civic.credential` with the signed VC nested under `.vc`). Surfaced via
`/embed/wallet` (any embedding app the citizen signs into) and the `my-documents` app. Holder gets an Ed25519
**holder key** stored **server-side** in app-host (explicit stand-in for a device/DID key).

- Managed Avsar wallet → **yes (this is it)**. External / DigiLocker / participant-hosted / self-custodied wallet
  → **NOT-IMPLEMENTED** (no `WalletProvider` interface; wallet is not pluggable).
- **Stored centrally by the platform:** offered VCs + holder keys in the network/app-host; accepted copies in the
  citizen's tenant. **Central user-profile / livelihood-history API → NOT-IMPLEMENTED** (no aggregated history
  endpoint; `civic.profile` sits in the citizen's own tenant; the worker-career-passport is a demo, not an API).

---

## 13. Identity & authentication

- **Worker/citizen auth — [IMPLEMENTED]:** the `citizens` realm (reference IdP), EdDSA JWT, `sub=user://citizens/
  <id>`, role `civic.resident`; self-signup (`/register`, `/bridge/citizen-register`).
- **Participant auth — [IMPLEMENTED]:** realm-per-tenant login; federated participants verified via their own
  issuer (trust map).
- **Organizational identity — [IMPLEMENTED]:** CA-signed participant directory entry (keys, jurisdiction, status).
- **Identity assurance — [PARTIAL/weak]:** `DEV_AUTH` injects a **static `assurance:A0`** into every token
  (`identity.py:35,317`). No assurance-upgrade in token minting; eKYC instead issues a `credential.identity_
  verified` VC. So assurance is a claim slot, hardcoded A0.
- **External IdP integration (eShram/Aadhaar) — [PARTIAL]:** via the **trusted-issuer map** (register the external
  `ds:<tenant>:identity` issuer + JWKS), NOT a `network.idp` registry (which doesn't exist). The eKYC issuer is
  config-driven (`EMBED_EKYC_ISSUER`, default `uidai`) but the Aadhaar check is **simulated** (`app_host.py:1744`).
  So eShram/Aadhaar plug in without code changes *as trusted issuers*, but the richer "identity_assurance policy
  with accepts:[aadhaar-auth, eshram-verified]" model is design-only.

---

## 14. Service request flow (trace)

```
Browser/app ──/bridge/service-apply──► app_host (_bridge, forward token)
  ──► network POST /v1/network/services/apply  (api.py:1042)  [membership-gated; records network.service_request]
Provider ──/bridge/service-decide──► network POST /v1/network/services/decide (api.py:1063)  [provider or net-admin → granted]
Gateway route (ADR-0067): /v1/service/search (api.py:2882) → /v1/service/route (api.py:2909)
  → resolve offering→provider+endpoint, verify action, mint SERVICE_TXNS id → /v1/service/transactions/status (2944)
Credential issuance (if the outcome mints one): solution workflow step issues:<credential-type>
  → network POST /v1/credentials/issue (api.py:2694) → offered VC in holder's wallet
Presentation (if the service requires evidence): /embed/proof-request → /embed/present → /embed/verify-presentation
```
**Modules:** `app_host.py` (`_bridge_service_apply/decide`, `_bridge_ekyc_join`, embed handlers) → `network/api.py`
(`network_service_apply/decide`, `service_route`, `participation_*`, `credential_*`) → `kernel` (registry
read/write for records) → `identity` (token). **Gaps vs the ideal flow:** requirement evaluation is flat (no
manifest); invocation is **synchronous** (no async processing / callback step); "notify worker" and a unified
"audit transaction" record are not first-class.

---

## 15. Event exchange flow (TOP)

**[NOT-IMPLEMENTED].** There is no observe→publish→authenticate→resolve-resource→resolve-authority→resolve-
subscriptions→authorize→route→act→audit pipeline. Substrate that exists: registry-write events / webhooks
(ADR-0089 Proposed), the `event_relay` **mail** relay, and the bitemporal registry (could store observations/
events as records). What's missing to route one event to multiple agencies by jurisdiction + subscription:
**Resource registry, Authority-over-Resource, Event type + publisher-authz, Subscription + filters, and the
routing engine** — none present. **This is the single largest gap between the current system and the generic
Trusted Network Platform.**

---

## 16. Resource & authority model

**[NOT-IMPLEMENTED generically].** `/v1/jurisdictions` (`network.jurisdiction`) exists but is used for
service-offering matching (residence-vs-property predicate), not as an authority-over-resource graph. There is no
`resource` registry and no model where *municipality owns road*, *traffic-police enforces*, *TMC operates signal*,
*all subscribe to one congestion event for different reasons*. City data (`space.ward`, `geo.building`, roads as
`geo.*`) exists as tenant data, but not as governed network resources with per-participant authority. Building
this is a prerequisite for TOP.

---

## 17. Event & subscription model

**[NOT-IMPLEMENTED].** No event schema governance consumed by an event engine, no publisher authorization, no
subscription object, no filters (geo/resource/confidence), no delivery guarantees / replay / ordering /
deduplication / dead-letter. ADR-0089 (event/message spine, emits/subscribes, CQRS) is **Proposed**, not built.

---

## 18. Transformation services

**[PARTIAL — only as domain engines].** The generic `engines/*` + `workflow`/`decision` can transform inputs to
outputs (e.g. air/flood engines derive risk), and a service can `issues:` a derived credential. But there is no
**event→transformation→derived-event** generic machinery (observation → intelligence → `congestion.detected`),
because there is no event plane. Transformations today are domain-specific certified components, invoked
synchronously, not a generic event-transformation primitive.

---

## 19. Client SDK

**Only the embed SDK (ADR-0112) — [IMPLEMENTED]** (`/embed/sdk.js`). Public API (global `AirawatOS.init`):
`login()` · `handleCallback()` · `discover()` (`GET /embed/services`) · `request(serviceId, inputs)` (`POST
/embed/request`) · `wallet()` (`GET /embed/wallet`) · `requestProof(opts)` · `present(requestId)` ·
`verifyPresentation(vp)` · `logout()`. Redirect-only PKCE; scope-bounding/consent-ledger are S2 TODO.
**Avsar-specific methods in the SDK: none** — the API is generic (discover/request/wallet/present). The richer
**Network Client SDK** (`getOffering/apply/subscribe/getRequestStatus`) is **design-only (ADR-0117)**.

---

## 20. Server SDK / Network Adapter

**[NOT-IMPLEMENTED].** No `Participant.publishOffering/receiveRequest/publishEvent/receiveEvent/verifyPresentation/
issueCredential/updateStatus/completeRequest/subscribe/revokeCredential` library. External participants integrate
ad hoc via an endpoint + the connector gateway + trusted-issuer registration. The `components/_common/aos/` SDK is
a **component-developer/build** SDK (CLI/config/confined-login), not a participant network adapter. This is
design-only in ADR-0118.

---

## 21. Multi-tenancy

**Relationships:** a **tenant** is a data workspace on an operator (optional). A **network** is a tenant carrying
`network.admin`. A **participant** is a tenant-free membership edge `(participant, network)`; a participant MAY be
a tenant or an external system or an individual. A **network administrator** is a token with tenant == the network
and a network-admin role.

**Enforcement:** the kernel P0 authz gate scopes every read/write by `(sub, tenant)` + id-prefix; cross-tenant
reads require a steward-signed `governance.access_grant` (ADR-0103) that the broker + kernel enforce.

**The pointed question — if a tenant has `network.admin`, can it read members' credentials or transaction
payloads?** **Largely NO, by construction, with caveats:**
- Network membership + eKYC **provision no tenant and store no member data in the network admin's tenant** — the
  participation record is network-governance metadata, not the member's data.
- Member **credentials** live keyed to the holder (network credential store) + the holder's own tenant on accept;
  reading them requires being the issuer (issue/revoke gate) or the holder (accept/present gate), **not** the
  network admin. A network admin is not on those gates.
- **Transaction payloads** that flow provider↔consumer via the gateway/connector are not deposited into the
  network-admin tenant; the gateway keeps a `SERVICE_TXNS` correlation record (ids/status), not payloads.
- **Caveats / debt:** (a) the network authority process *operates* the credential store and the directory, so an
  operator with DB/process access could read them — the **control/transaction-plane separation is architectural,
  not yet a hard cryptographic boundary**; (b) the network admin governs schemas/roles and could, in principle,
  grant itself roles — governance changes are logged (change-request + signed) but not independently constrained;
  (c) selective disclosure doesn't exist, so when a member *does* present a credential to a provider, full claims
  are shared. So the **neutrality property holds at the API/authorization layer but is not yet enforced against a
  privileged operator** — a real gap to document.

---

## 22. Privacy model

- **Consent — [IMPLEMENTED]:** recorded on VP (`/embed/present`, ADR-0103) and on service consent (ADR-0067 S5).
- **Credential disclosure — [PARTIAL]:** present a whole signed VC; **selective disclosure / ZK predicate proofs —
  NOT-IMPLEMENTED**, so proving "activeDays ≥ 90" reveals the credential's claims.
- **Data minimization / purpose limitation — [PARTIAL]:** per-tenant isolation + grants limit *access*; there is
  no per-network data-minimization/retention policy engine, and no `features{}`/privacy-policy knob on a network.
- **Retention / deletion — [PARTIAL]:** registry `archive`/`vacuum` exist; no governed per-network retention or a
  right-to-erasure flow.
- **Audit retention / anti-profiling — [PARTIAL].**
- **TOP-specific (observations without movement histories) — [NOT-IMPLEMENTED]:** there is no mechanism for
  identity-less, aggregated, bounded-retention observations because the event/observation plane doesn't exist. A
  network cannot today be configured to run *without* person-identity/wallet via a privacy policy; those are
  assumed-on in the service/credential pattern.

---

## 23. Audit

- **Logged:** participation decide (`decided_by/at`, reason); certification decisions; registry writes (bitemporal
  `tx_from`, `agent`, `content_hash`) + `prov`/`history`; connector reads (`_connector_audit`); grant issue/revoke;
  credential issue/accept/revoke (status-list + records). **Not uniformly logged:** event publication/delivery
  (no events), a single queryable cross-primitive audit trail, authorization *decisions* (allow/deny) as discrete
  audit entries.
- **Access:** registry history/prov is tenant-scoped (same authz as reads); network governance records are
  readable per the network-admin gate. There is **no dedicated audit API with its own access policy**; audit is
  implicit in the bitemporal store + decide records.
- **Debt:** historically some network records were in-memory (restart-wiped) — audit durability must be confirmed.

---

## 24. Security / threat model

**No formal written threat model exists.** Implemented mitigations (factual):
- **Token verification** — EdDSA JWT verified against per-issuer JWKS (`authn.verify`); multi-issuer trust map.
- **Write/read authz** — kernel P0 single-registry gate scoped by `(sub,tenant)`; retract authz parity.
- **Run-tokens** — high-entropy secrets (P0#1); scoped run tokens for component runs.
- **Connector SSRF** — endpoint-trust guard (A2); the `/bridge/fetch` SSRF guard rejects private/loopback/metadata
  addresses.
- **Component admission** — apps served only if their certificate verifies AND the bundle digest matches
  (fail-closed 404).
- **Sandbox** — components get I/O only via the broker with capability checks; sandbox-privilege = builder-role ×
  dev-env.
- **Credential integrity** — Ed25519 issuer signature on an immutable core; revocation + expiry; holder-binding +
  challenge nonce (single-use) on VP.

Per-threat status (**implemented** vs **planned/gap**):
| Threat | Status |
|---|---|
| Malicious participant | partial (membership gate + cert + authz; no behavioural controls) |
| Compromised participant keys | partial (revoke issuer / directory entry; no automatic key-compromise detection) |
| Fake credential issuer | mitigated (trust map + CA directory; only trusted issuers verify) |
| Credential replay | mitigated at VP (nonce/challenge single-use + holder binding); credential itself is bearer-ish if leaked |
| Event spoofing | **n/a — no event plane (gap)** |
| Unauthorized subscriptions | **n/a — no subscriptions (gap)** |
| Privilege escalation | partial (role gates; governance change-requests signed; no independent constraint on a network admin granting itself roles) |
| Tenant isolation failure | mitigated at authz/id layer; **not a hard boundary against a privileged operator** |
| PII leakage | partial (isolation + consent); **no selective disclosure; full-claim presentation** |
| Wallet compromise | partial (holder keys server-side stand-in — a compromise of app-host exposes holder keys) |
| Gateway impersonation | partial (TLS + token forward; no mutual-auth spec for external endpoints documented) |
| Callback spoofing | **n/a — async callbacks not implemented (gap)** |
| Replay attacks | mitigated for VP; general request idempotency not enforced |
| Denial of service | partial (pool sizing; no documented rate-limit/quotas beyond usage metering) |

---

## 25. Reliability

**[PARTIAL — synchronous-first].** Idempotency keys, retry policy, duplicate-request/event handling, service
timeouts, participant-unavailability handling, callback-failure handling, partial-transaction compensation, and
explicit transaction boundaries are **largely not implemented** at the network/gateway layer. The registry gives
**per-write atomicity** (bitemporal append; batch writes use SAVEPOINTs and report per-item failures) and
**eventual consistency** across services is implicit (no distributed transaction). Fulfilment is synchronous;
async provider interaction is noted as "a later slice." Concurrency on a single registry id is serialized by the
`rv_one_open` unique constraint. **This is a real production-readiness gap for a federation gateway.**

---

## 26. Versioning

- **Schemas / interfaces — [IMPLEMENTED]:** carry `version`; a published (id,version) is immutable; republish
  requires a higher version; `schema_version` stamped on each registry row. (Backward-compat diff-gate at approval
  is a pending item.)
- **Network configuration — [PARTIAL]:** the profile is merge-updated in place (no profile versioning/history
  beyond the registry's bitemporal trail where applicable).
- **Credential / event / resource schemas — [PARTIAL/n-a]:** credential types version as schemas; event/resource
  schemas would too but have no consumer.
- **Service interfaces — [IMPLEMENTED]** (interface versions + bindings, ADR-0063).
- **SDKs — [PARTIAL]:** images are tagged/pinned per service (compose pins); the embed SDK is unversioned same-
  origin JS.
- **Effect of schema change on existing data/credentials:** existing registry rows keep their `schema_version` and
  remain valid (bitemporal); already-issued credentials keep their signed `conforms_to` version — they are **not**
  retro-migrated. No automated migration framework.

---

## 27. Testing

**[PARTIAL].**
- **Black-box e2e / integration (`tests-repo/`):** `test_network.py`, `test_kernel.py`, `test_identity.py`,
  `test_app_host.py`, `test_filestore.py`, `smoke_health.py`, `e2e_service_interpreter.py`, driven by
  `run.py`/`lib.py`. These hit the running services over HTTP — the de-facto integration suite.
- **Unit:** `kernel/` has `pytest.ini` + tests (e.g. connector-scope red-first test, registry tests);
  `network/test_authn.py`.
- **Conformance:** certify-time output-schema validation + a11y (axe) gate (Tier-4 conformance,
  `network/conformance.py`); ADR-0059 conformance declaration. This is a form of **contract/conformance testing**
  at publish time.
- **Gaps:** no dedicated **security test** suite (the threat table above is unverified by tests); no **contract
  tests** for external-participant adapters (none exist); coverage is not measured/reported; much of this session's
  network/participant/credential work is proven by **ad-hoc scripts**, not committed tests. **Recommendation:
  promote the session's manual verifications into `tests-repo/test_network.py` and add adapter contract tests
  before claiming production readiness.**

---

## Appendix — top debt items (for the reviewer's risk list)

1. **No event/resource/authority/subscription plane** → TOP is not configurable (needs code). *(Largest gap.)*
2. **Requirement/eligibility manifest not implemented** (flat list only); **no selective disclosure**.
3. **Credentials are signed-JSON, not W3C VC**; **eKYC/Aadhaar is simulated**; **assurance hardcoded A0**.
4. **No IdP registry** (`network.idp`/`verified_by`) — external identity via the single trust map only.
5. **Network Client SDK + Participant Server SDK are design-only**; only the embed SDK exists.
6. **Async fulfilment / callbacks / idempotency / retries not implemented** — gateway is synchronous.
7. **Control/transaction-plane neutrality is architectural, not cryptographically enforced** vs a privileged
   operator; **holder keys are server-side stand-ins**.
8. **Network-authority store durability** (historically some in-memory, restart-wiped) must be confirmed.
9. **Monoliths**: `app_host.py` (10k L), `network/api.py` (3.5k L); cosmetic domain defaults in `hostcore.py`.
10. **Tests** are integration-heavy but **no security/adapter-contract tests**; session work largely script-proven.

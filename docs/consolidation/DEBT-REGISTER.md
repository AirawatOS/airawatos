# AirawatOS — Debt Register (Consolidation Phase 1)

**Read-only audit, 2026-11-03.** Merged from eight fresh-context layer reviews. Companion:
`CURRENT-STATE.md`. `file:line` are in the per-service nested repos under
`/Users/manishsv/Documents/Projects/Airawat/`. *(uncertain)* = not fully traced; nothing is a guess.

**Totals (deduplicated distinct items / raw per-layer line-items):**
- **A. Transitional mechanisms: 61 distinct (≈68 line-items across layers).**
- **B. Invariant violations: 18 distinct classes (≈30 instances).**
- **C. Duplication / dead-code clusters: 22.**

---

## A. Transitional mechanism register

| # | Mechanism | Location (file:line) | Purpose | Risk | Removal condition |
|---|---|---|---|---|---|
| A1 | `REQUIRE_AUTH` default OFF | kernelcore.py:19 | allow unauth reads in transition | tenant reads with no token | flip ON once all clients send tokens |
| A2 | `PROV_ENFORCE` off/shadow | kernelcore.py:60; app.py:861 | measure unattributed writes | unattributed writes accepted | flip 1 after shadow clean |
| A3 | `DATAPLANE_ENFORCE` off/shadow | kernelcore.py:62; app.py:1169 | fact-writer gate observe-only | unattributed "facts" injected | flip 1 after audit |
| A4 | `REQUIRE_STEWARD_GRANT` off | kernelcore.py:63; app.py:1379 | skip broker grant check | tenant-sovereignty grant skipped | flip on once grants populated |
| A5 | `IDENTITY_AUD_ISS_SHADOW` admit+log | authn.py:29,50 | soak iss/aud before enforce | mismatched aud/iss admitted | clear flag after soak |
| A6 | `IDENTITY_EXPECTED_ISS/AUD` empty=off | authn.py:24-25 | legacy tokens carry no aud/iss | no binding by default | set + clear shadow |
| A7 | Prod-pointing identity defaults `ds:airawat:identity`/`airawatos` | kernelcore.py:31, authn.py:74, identity.py:30-32, network api.py:29,208 | single-issuer default | dev/standalone silently assumes prod issuer | require explicit, no default |
| A8 | Other prod defaults `SHARED_STEWARD=airawat`, `FED_PARTICIPANT_ID`, fallback tenants | app.py:228,1767,98,638,1723 | standalone convenience | assumes prod steward identity | require explicit |
| A9 | Failed-auth not logged | kernelcore.py:34-47 | — | no trail of failed/forged auth | add auth-failure audit (ADR noted) |
| A10 | `COMPONENT_ENFORCE` shadow fallback + legacy global install path | app.py:1133,1140 | pre-per-tenant installs | setting 0 reopens dev-token backdoor | per-tenant installs only |
| A11 | `_PINNED_ENDPOINT_OK` SSRF relaxation | app.py:415 | dev fixtures pin endpoints | — | drop when no pinned fixtures |
| A12 | `SCHEMA_SHADOW_SCHEMAS` per-schema exceptions | app.py:2246 | pre-driver-pass conformance | — | delete (now empty) |
| A13 | In-memory federation authority fallback (standalone) | app.py:1786,2357 | run without Network | self-signs with no authority key | require NETWORK_URL in prod |
| A14 | `NETWORK_ADMIN_AUTHZ` legacy↔role | trust_admin_authz.py:68; api.py:783 | migrate admin plane to recorded roles | global all-or-nothing; role 403s un-bootstrapped nets | all nets bootstrapped + role default |
| A15 | `AUTHZ_MODE` (comment-only here) | trust_admin_authz.py:10,18 | marks untouched surface | naming confusion vs A14 | clarify when broader authz lands |
| A16 | `TRUST_PLANE_ENABLED` dark-launch | trust_wiring.py:81 | gate ADR-0119 governance | prod runs governance dark; legacy sole authority | always-on at GA |
| A17 | tenant-based `is_platform_authority` | trust_wiring.py:59; roles.py:62 | bootstrap/break-glass super-authority | network-wide authority from a tenant NAME | **ADR-0122**: recorded platform.authority role |
| A18 | TWO grant models (role_grant/role_assignment + CapabilityGrant shadow-only) | schemas.py:143,146; authorize.py:51; api.py:1040 | migrate to CapabilityGrant | two authority representations; grant model proven-but-unused | flip after dual-run divergence gate passes |
| A19 | single global `TRUST_WRITE_STEWARD` | trust_wiring.py:112 | one write prefix | not per-network | per-network stewarded prefixes |
| A20 | write-steward vs authority split (two tenant knobs) | trust_wiring.py:108-113 | write where readers read w/o conferring authority | easy to conflate; default equal | collapse when A17 is role-based |
| A21 | static-token vs mint-on-demand fallbacks | trust_admin_authz.py:151; trust_wiring.py:92 | tests/break-glass | 1h static token → 503 on expiry; bypasses Vault path | drop static envs once mint proven |
| A22 | dual-read role_assignment 0.1.0 `network` field | schemas.py:143; governed_store.py:137 | avoid new record type | overloads role_grant; net:id/slug conflation | cut first-class net:id-keyed schema |
| A23 | app-host token-role front-gates (network-requests, participants) | app_host.py:4190,3931,3939,3956 | cheap pre-filter | duplicates/diverges from server authz | match decide/configure (session+resolve) |
| A24 | `_resolve_read_network` no-selection→first-managed | app_host.py:4100 | default console view | mutating caller acts on rows[0] user didn't pick | require explicit selection |
| A25 | `networks-mine` Trust-plane dependency + fabricated fallback | app_host.py:4083,4524 | work when Trust plane off | fabricates authority (see B2) | Trust plane GA; delete fallback |
| A26 | passwordless service-principal / provisioning logins | app_host.py:857,5112; scheduler.py:50; automation.py:29; event_relay.py:25; identity.py `_DEMO_USERS:68` | infra convenience | full-authority token with no secret | real revocable service credentials |
| A27 | `--no-verify-cert` (app-host + host.py) | app_host.py:10321; host.py:314; deploy local:172, local-dev:224 | skip TLS verify internal | MITM on internal hops; on the live demo | trust internal certs, drop flag |
| A28 | sandbox-privilege gates (`builder × tenant_env`) | app_host.py:4434,4477,5442,7960 | self-serve dev run/secret/aoi/schema | authority from a token claim (`tenant_env`) | route builder actions through recorded grants |
| A29 | `IDENTITY_INTERNAL` default literal shared secret | app_host.py:44; identity.py:37; network api.py:31; deploy composes | provisioner gate | known literal guards user/password-set in prod | Vault-materialised random secret |
| A30 | identity `_PW_MODE` default **shadow** | identity.py:283,546 | measure-before-enforce passwords | **prod (EC2) still mints passwordless** | flip shadow→enforce once all have passwords |
| A31 | `AIRAWAT_ALLOW_PASSWORDLESS` dev flag (not read by identity) | deploy local-dev:21; prod-guard.sh:18 | mark stack passwordless | naming divergence from A30 masks prod shadow | retire when prod=enforce |
| A32 | `IDENTITY_SEED_DEMO` demo accounts | identity.py:80; deploy local bootstrap:121 | local dogfood | baked privileged principals if on in prod | keep off (prod-guard blocks) |
| A33 | 1-hour token, no durable service credential | identity.py:364 | — | service principals depend on passwordless mint | durable/renewable service creds |
| A34 | DEV_AUTH `A0` assurance stamped unconditionally | identity.py:35,363 | dev auth has no method | every ref token claims A0; assurance untrustworthy | compute from real method |
| A35 | Keycloak static `A2` assurance | keycloak-bootstrap.py:88 | seed | assurance not computed | compute from acr/amr |
| A36 | fail-OPEN internal-token gates (secrets, runtime-manager) | secrets.py:147,155; runtime_manager.py:49 | optional internal gate | **`RUNTIME_MANAGER_INTERNAL` set in NO deploy file → fail-open** | make gate mandatory, no empty default |
| A37 | hardcoded `GW_INTERNAL_TOKEN="gw-internal"` | model_gateway.py:21 | key-write gate | predictable | require env, no default |
| A38 | dev root Vault token `airawat-dev-root` | secrets.py:28; model_gateway.py:20 | dev | root token default | AppRole/short-lived |
| A39 | cross-tenant platform-service writes | scheduler.py, automation.py, event_relay.py | clock/dispatch across tenants | one principal writes platform.* everywhere | per-tenant scoped tokens / broker |
| A40 | reference direct-to-registry writes (no broker/provenance) | decision/workflow/notify/automation/scheduler/event_relay | skeleton | unattributed writes | route through broker |
| A41 | STT env-bootstrap hardcoded tenant/component/contact (`court-1`/bodhan) | model_gateway.py:124 | TODO(governed) | hardcoded provider | certified provider record |
| A42 | scheduler `COMPONENTS_ROOT` + host.py subprocess fallback | scheduler.py:19,156 | dev run drafts from source | bypasses signed delivery / runtime_invoke | always run signed packages |
| A43 | `SUBSCRIPTION_ENFORCE` default shadow | automation.py:119 | observe before enforce | fires raw-URL actions (SSRF) | flip strict after audit |
| A44 | hardcoded prod issuer in SDK oidc | _common/aos/oidc.py:17 | fallback | prod URL baked | config, no default |
| A45 | SDK intra-cluster dev defaults `network:8090`/`kernel:8080` | _common/aos/config.py:15 | dev | — | env-first (already) |
| A46 | absolute-path hardcode in all 11 selftests | _common/aos/selftest*.py:1-2 | — | non-portable tests | relativize |
| A47 | embed env/default allow-list + seeded `demo-embed` client | app_host.py:825,833 | S1 fallback to governed `platform.app_client` | demo client always present | governed clients only (S1b) |
| A48 | `same-origin-demo` redirect bypasses exact-URI check | app_host.py:1112 | built-in demo | redirect-registry check skipped for demo | remove demo mode in prod |
| A49 | simulated/open demo endpoints (`/embed/uidai-enrol`, eKYC) | app_host.py:1715,1744 | demo | open kiosk / simulated biometrics | governed eKYC |
| A50 | `aos deploy --sandbox` disables network plane + auto-approves dev-tenant governance | _common/aos/solution.py:211,263; policy.py:38 | fast dev | validated config ≠ prod path | Marketplace promotion for prod |
| A51 | `cmd_upload` direct-to-EC2 (1MB TLS-proxy cap workaround) | _common/aos/cli.py:323 | large files | points a tool at the prod IP | fix proxy cap / governed upload |
| A52 | fail-OPEN account-hold check | app_host.py:880 | don't lock out on registry hiccup | disabled account still logs in on error | fail-closed with cache |
| A53 | baked-vs-filestore + raw-urllib vs `-aos` SDK migration duplication | components (effectiveness-engine(-aos), hello-dev(-aos), water-safety-aos); 72 raw / 19 SDK | mid-migration | two of each kept | retire the superseded half |
| A54 | hardcoded contacts/hosts in components (`manishsv@gmail.com` UA, EC2 IP) | components/_common/aos/cli.py:323; driver metas | — | PII / prod host in source | compose egress UA from tenant contact (backlog) |
| A55 | dev-only components (hello-dev, crowd-sim, demo-connector, aos-modular-demo) | components/drivers, apps, connectors | dev/demo | ship in prod image | exclude from prod bundle |
| A56 | duplicated app helpers / `/shared/aos.js` not universally adopted | 21 app bundles inline esc/jget/jpost vs 6 using /shared/aos.js | pre-shared-runtime | copy-paste drift | adopt shared runtime |
| A57 | prod-guard is local-dev-only | deploy/local-dev/prod-guard.sh (wired only there) | effective-settings refuse | no guard in local/EC2 | ship to prod images/compose |
| A58 | transient override files (role-mode token, trust-canary, dev-example) | PLAN.md:156,187; local/docker-compose.override.yml.dev-example | validation convenience | validated config ≠ committed | bake proven settings |
| A59 | image-tag drift (network dev-ec365a4 vs docs; local bootstrap fork; INSTALL.md) | deploy local-dev:3,87; local/airawatos-bootstrap.sh; INSTALL.md:87 | — | deploy wrong build | single-source tags |
| A60 | EC2 hot-patches not baked (revert on recreate) | deploy/ec2/HOTPATCHES-2026-10-19.md | emergency fixes | container recreate reverts | bake + cutover |
| A61 | `local` nginx binds `0.0.0.0:80` while running prod-default auth | deploy/local/docker-compose.yml:188 | eval exposure | eval stack reachable beyond loopback on prod-default envelope | loopback bind |
| A62 | `governance.role_assignment@0.1.0` read-compat kept alongside 0.2.0 (ADR-0122) | network trust/schemas.py (0.1.0 + 0.2.0 both governed); platform_authority.py `_scope_of` reads legacy `network` alias | let 0.1.0 (network-only) records keep resolving during migration to the scoped 0.2.0 shape | two live shapes for the same schema; a reader must handle both | migrate all 0.1.0 records to 0.2.0 (`trust.migration.migrate_role_assignment_v2`), then retire 0.1.0 + the `network`-alias read path |
| A63 | `PLATFORM_AUTHORITY_MODE` shadow dual-compute (ADR-0122) | network trust_wiring.py `_actor_context` | compute recorded-role platform authority alongside the legacy tenant rule and log divergences before cutover | two authority sources computed per request; the tenant rule is still authoritative wherever mode≠enforce | flip every deployment to `enforce` once each has a seeded `platform.authority` holder; then delete the tenant-rule branch + the mode switch (local-dev already `enforce`) |
| A64 | Kernel caches governed schemas at boot — a schema version governed into a RUNNING stack is not validated against until the kernel reloads | kernel loads its schema set at startup; a post-boot `seed_trust_schemas` write (e.g. `governance.role_assignment@0.2.0`) 422s ("role not in enum") until the kernel is restarted (observed 2026-11-04 during the ADR-0122 cutover) | a fresh install is unaffected (kernel boots after schemas are seeded); the lag only bites when re-governing on a live stack | kernel hot-reloads schemas on change (subscribe to the schema-registry / a governance-driven refresh signal), so a newly governed version takes effect with no restart; until then, bootstrap/ops must restart the kernel after governing a new schema version |
| A65 | Audience-binding migration: a verifier accepts EITHER the platform audience OR its own service audience (ADR-0124) | `tokens.verify(expected_aud)`; network `api.py` `set_audience`; automation `_EVENTS_ACCEPT_AUD` = {svc:automation, platform} | let platform-audience tokens (the pre-ADR-0124 single `airawatos`/`airawatos-localdev`) keep working while services move to specific service audiences (svc:kernel / svc:network / svc:automation …) | two accepted audiences per verifier during migration; a stolen platform-audience token is still replayable at any service accepting the platform aud until each cuts over | move every service to its specific audience, flip each verifier to require ONLY its own (kernel→svc:kernel, network→svc:network), then remove platform-audience acceptance once nothing mints it |

## B. Invariant violations

Principles: (i) tokens carry identity only; (ii) authority only from recorded state; (iii) nothing implied by
tenant/membership/classification/issuer; (iv) Tenant ≠ Network; (v) no silent in-memory authoritative state;
(vi) the Kernel stays domain-blind.

| # | Violation (principle) | Where (file:line) | Note |
|---|---|---|---|
| B1 | **Authority from token role claims, not recorded state** (i,ii) — the dominant, cross-cutting violation | kernel `_is_admin`/`_is_platform_service` kernelcore.py:50,82 (HOME-iss-bound but still TR); network legacy `_require_network_admin` api.py:785, `_require_admin` :250, `network_service_offer` :1035; app-host `_NET_ADMIN_ROLES & roles` 4190/3931, `_bridge_proxy` 4543, sandbox 5442; identity STAMPS `roles` into the token identity.py:362 and downstream enforces off it (app_host 6790,1990,…); reference secrets.py:100, workflow.py:49; SDK embed `/embed/clients` :1990 | revocation ineffective until token expiry (1h); kernel's own comment concedes "authority still belongs in recorded state (STEP-3)" |
| B2 | **Authority implied by tenant name / fabricated from tenant** (iii,iv) | network `tenant==network` api.py:785, `is_platform_authority = tenant==authority_tenant` trust_wiring.py:59, `_is_operator`/`_require_admin` tenant=="airawat" api.py:2035,250; kernel platform-service cross-tenant `_read_reach` app.py:1045; **app-host `networks-mine` fabricates a manageable network+admin role from the session token+tenant** app_host.py:4524-4527 | the app-host fallback is the sharpest: `network==slug==tenant`, admin role synthesized, no recorded state |
| B3 | **Authority from authentication alone** (ii) — authentic ≠ authorized | decision.py `/decide` :66-92 records any valid token's `sub` as the deciding authority with no check it may decide that task | effective gate is only whatever the kernel applies on the under-token read/write |
| B4 | **Internal shared-secret treated as authority, fail-open when unset** (ii) | secrets.py:147,155 (`/materialize` raw secret, `/fetch` egress proxy); runtime_manager.py:49 (Docker+secret) — `RUNTIME_MANAGER_INTERNAL` set in no deploy file | bearer-of-secret model; open when env missing |
| B5 | **Unauthenticated privileged / writing endpoints** (ii) | filestore.py all routes; notify.py `/notify` :18 (forge inbox items, no token); scheduler.py `/run`/`/reload` (exec any component any tenant); model_gateway.py `/complete|/embed|/transcribe` (cost); embed.py `/embed`; automation.py `/events`; event_relay delivery | several write to the registry or spend money with no caller identity |
| B6 | **Unauthenticated identity/role directory disclosure** (ii,iii) | identity.py GET `/users` :428, `/realms` :419, `/realms/<t>/users` :424 — returns usernames, subjects, tenants, **roles** | exposes the authority map to any reachable caller |
| B7 | **Classification / schema-prefix drives authz** (iii) | kernel `_is_dataplane_schema` app.py:1165 (hardcoded prefixes :1160), shared-read via `SHARED_SCHEMAS` :246 | a data classification decides a write/read authority |
| B8 | **Kernel not domain-blind** (vi) | kernel `_NAT_KEYS` app.py:1276 (gstin/cnr/udise…), dataplane prefixes `cell./geo./air./…` :1160, event-skip prefixes :81, public allow-list `viz.layer/ref.*` :1034 | domain vocabulary baked into the kernel |
| B9 | **Upward / trust-anchor calls** (vi, "no upward calls") | kernel→network for authority key/schemas/grants/tenant-dev classification (app.py:1780,842,1923,1816…); kernel→identity JWKS authn.py:103; **network→identity provisioning** (participation/decide CREATES a user+password) api.py:889 | kernel depends on the Network for its authz inputs — policy call for the merge (Network = authority body per ADR-0055); the network→identity user-create is a clearer upward control call |
| B10 | **Silent in-memory authoritative state** (v) | kernel `RUN_TOKENS` dev-tokens memory-only app.py:1879 + `adminaudit._RING` when DB down; **app-host `_SESSIONS`** hostcore.py:52 (restart=global logout, unshardable) + `_ONBOARD_RUNS`; automation `_PROCESSED` dedup automation.py:21 (events re-fire on restart); scheduler `_RUNS` receipts | authoritative/at-least-once state lost on restart |
| B11 | **Tenant ≠ Network conflation** (iv) | network legacy gate keys on slug/tenant string api.py:785 while role mode keys on net:id trust_admin_authz.py:230; `cross_network_write_enabled` predicate mixes slug/net:id/tenant trust_wiring.py:179; app-host networks-mine fallback collapses all three app_host.py:4526 | same endpoint keys authority on different identifiers across modes |
| B12 | **Client-asserted scope not bound to registered client capability** (ii) | embed `/embed/authorize` passes `scope` from the query string app_host.py:1148,1160; consent always written `service:"*"` :1555 regardless of the client's registered scopes (demo-embed lists only `profile`) | an app registered for `profile` can obtain a `service:invoke` consent — S2-pending but live |
| B13 | **Assurance claim not trustworthy** (iii) | identity uniform `A0` identity.py:35; Keycloak static `A2` keycloak-bootstrap.py:89 | a downstream requiring ≥A1 cannot rely on it |
| B14 | **Passwordless full-authority principals** (ii) | identity `_DEMO_USERS` service/steward principals identity.py:68; passwordless mint under `_PW_MODE!=enforce` :546 | `platform.scheduler`/`platform.steward` mint with no secret |
| B15 | **Possible `run_token` exposure** *(uncertain — verify)* (ii) | kernel `/v1/components` app.py:2369 returns `list(INSTALLED.values())`, INSTALLED carries `run_token` :2058, unauthenticated | confirm whether run_token is serialized out — if so, a bearer-secret leak |
| B16 | **Open egress proxy / SSRF** | secrets.py `/fetch` (any caller URL); automation.py shadow POSTs any `action.url` :123; app-host `/bridge/connect-network` fetches arbitrary remote URL :4018 | server-side fetch of caller/tenant-supplied URLs |
| B17 | **Client-side-only role gating in apps** *(mitigated/uncertain)* (ii) | ~30 app bundles gate UI by role/session in JS (apps/admin/dist/index.html:49,68…) | not a real violation IF every server bridge re-checks — verify host-side (out of this repo's scope) |
| B18 | **Engines hold write-grant to `governance.decision`** *(uncertain)* | components engines/campaign-engine/meta.yaml:23, project-engine/meta.yaml:36 (writes governance.decision); effectiveness-engine reads it | departs from "engine never decides"; reconciled by ADR-0056 decided-change-request, but the guarantee now rests on who may trigger the run — verify a human-authority gate precedes these runs |

## C. Duplication / dead code

1. Kernel `_read_scope` (app.py:251) vs `_read_reach` (1037) — overlapping read-scope resolvers.
2. Three fast-path pushdown blocks: registry_query 501, registry_count 550, broker_query 1404.
3. Shadow-dedup warn-once sets repeated: `_PROV_WARNED`/`_ADMIT_WARNED`/`_DATAPLANE_WARNED`/`_SCHEMA_WARNED` (app.py:858,1130,1162,2256) + authn `_SEEN_PRINCIPALS`/`_SHADOW_SEEN`.
4. Kernel dead/unwired skeletons: `services/service/*` (Case loop, defined app.py:1950, no route), `services/decision/*`, `services/*/demo.py`, `services/broker/sdk.py`, `prior-art/`.
5. Kernel belt-and-suspenders post-filters duplicate SQL id_prefix pushdown (registry_resolve 1227, resolve_by_identifier 1333); `_dev_flag` 1997 duplicated inline 1140/1176/1437.
6. Network: one `HttpRegistryClient` but two build sites + near-identical `_read_token`/`_writer_token` wrappers (trust_admin_authz.py:167,172).
7. Network: ~8× token-extraction pattern (`_bearer_claims` api.py:761, `_claims` 2014, inline in `_require_admin`/`_require_publisher`/`_require_issuer`/`_verify_caller`/`_is_operator`).
8. Network: `shadow_authorize` (trust_wiring.py:212, "prefer shadow_compare") not called in prod; `authorize()`/dual_run/divergence stack wired shadow-only (gates nothing until the flip).
9. Network: two in-memory test fakes `InMemoryTrustStore` (store.py:69) + `FakeGovernedRegistry` (registry_client.py:102).
10. Network: unused assurance read methods (governed_store.py:130, authorize.py:120) — Phase-1 reserved.
11. App-host: `_resolve_read_network` vs `_resolve_trust_network` near-identical (unify with a key param); `/bridge/my-networks` vs `/bridge/networks-mine` confusingly named; inconsistent gating across the network-bridge family (network-requests still token-role front-gated while decide/configure aren't); `_read_bridge_body` vs inline `json.loads` in many bridges.
12. Reference: two embedding impls + identical `_bow` (embed.py:32, model_gateway.py:32); triplicated passwordless service-auth block (scheduler/automation/event_relay); registry-client helpers duplicated across 6 services; Vault helper in 3 services; port 8104 default collision (model_gateway/runtime_manager/embed).
13. SDK: PKCE+base64url implemented 3× (oidc.py:42, app_host.py:1121, app_host.py:1303); three distinct globals (`AirawatOS` Python class, `window.AirawatOS` embed, `window.AOS` runtime); one-time-code pruning duplicated (app_host.py:1228≈1271); `_send` helper re-implemented in embed.py/aos connector; selftest boilerplate ×11; `_Driver.scheduled` decorator stored but never consumed (__init__.py:588).
14. Components: inline `esc/jget/jpost` across ~21 app bundles vs `/shared/aos.js`; raw-urllib originals vs `-aos` rewrites; thin/demo kinds (experts, pipelines, adapters, demos, demo-connector) *(non-use uncertain)*.
15. Deploy: `local/nginx.conf` ≡ `local-dev/nginx.conf` (byte-identical) + a third inline copy in `airawatos-bootstrap.sh`; vault.hcl/entrypoint.sh duplicated 3×; `airawatos-bootstrap.sh` carries a stale compose fork; `local/overlays/` 28 one-off overlay Dockerfiles likely superseded; stale docs (PLAN.md:211, INSTALL.md:87, compose header :3).
16. Identity: per-realm JWKS serves the shared key (cosmetic); internal-token gate copy-pasted 3× (identity.py:451,466,480) and mirrored in secrets.py/runtime_manager.py.

(16 clusters listed; several contain multiple sub-items — ~22 distinct duplications/dead paths in total.)

---

## Top-ten risks (severity-ranked)

1. **Unauthenticated privileged reference endpoints** — filestore (any blob r/w), notify (forge any inbox item), scheduler `/run` (execute any installed component in any tenant via the passwordless platform-service principal), model_gateway (`/complete|/embed|/transcribe` spend money), automation/event_relay. [B5]
2. **Fail-OPEN internal-token gates; `RUNTIME_MANAGER_INTERNAL` set in no deploy file** — secrets `/materialize` (raw secrets) + `/fetch` (secret-injecting egress proxy) and runtime-manager `/invoke` (Docker + secret materialize) skip the gate when the env is unset. [B4, A36]
3. **Authority derived from token role claims, pervasively** — kernel/network/app-host/identity/reference; identity stamps `roles` into the token and downstream enforces off it; revocation ineffective for the 1h token life. The single most cross-cutting violation. [B1]
4. **`is_platform_authority` = tenant name (+ prod default `airawat`)** — network-wide super-authority from a tenant name, not a recorded grant; also the first-steward chicken-and-egg. [B2, A17; ADR-0122 target]
5. **Possible `run_token` leak via kernel `GET /v1/components`** (unauthenticated, returns INSTALLED values carrying `run_token`) — *verify whether serialized; if so, a bearer-secret leak.* [B15]
6. **Production-pointing identity defaults + iss/aud enforcement off** — `ds:airawat:identity`/`airawatos` silent defaults, `IDENTITY_EXPECTED_ISS/AUD` empty, EC2 posture shadow; hardening ships inert in `local`/EC2; a standalone kernel silently assumes the prod steward/issuer. [A5-A8, deploy B]
7. **Passwordless login still mints in production** — identity `_PW_MODE` defaults to shadow and EC2 doesn't set it; passwordless `platform.scheduler`/`platform.steward` principals mint full-authority tokens with no secret. [A30, B14]
8. **Silent in-memory authoritative state** — app-host `_SESSIONS` (restart = global logout, unshardable), kernel dev-tokens + adminaudit ring, automation dedup (events re-fire). [B10]
9. **app-host `networks-mine` fabricates authority from token+tenant** when the Trust plane is off (collapses Tenant≠Network, implies admin with no recorded state). [B2, A25]
10. **Embed client-asserted scope not bound to the registered client** (app registered for `profile` can get a `service:invoke` consent) + the SSRF surface (secrets `/fetch`, automation `action.url`, app-host `connect-network`). [B12, B16]

Runners-up: committed literal dev secrets in tracked compose [deploy B]; prod-guard local-dev-only [A57]; EC2 hot-patches not baked (revert on recreate) [A60]; near-total absence of tests for app-host, the reference services, embed, and `/shared/aos.js`.

## Method & uncertainty
Eight fresh-context reviewer agents (one per layer); this is the merged, de-duplicated register. Items marked
*(uncertain)* were not fully traced and are flagged, not asserted: B15 (run_token serialization), B17 (whether
every app's server bridge re-checks), B18 (human-authority gate before decision-writing engine runs),
component non-use, identity `BIND_HOST` reachability. EC2 statements derive only from committed
docs/overlays — the live EC2 host was not contacted.

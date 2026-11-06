# INTERNAL SERVICES + GATEWAYS review — Consolidation phase 5, slice 5

Scope: the reference internal daemons and gateways under `platform-spec/reference/` —
`secrets.py`, `runtime_manager.py`, `model_gateway.py`, `scheduler.py`, `automation.py`, `event_relay.py`,
`workflow.py`, `filestore.py`, `notify.py`, `decision.py`, `docrender.py`, `embed.py`, `spec_generation.py`,
and the shared service-auth substrate `svc_authz.py` / `svc_token.py`. Audited by four fresh, independent
read-only reviewers; findings only — no code changed in the review step. Judged against the repository source
and verified on the **local-dev** stack (dev-hard11). **EC2 is out of scope** (development environment; see
`docs/reviews/REVIEW-METHOD.md`) — no probes were run against it. First production deployment is a fresh install,
so the posture here is what a fresh install of this source produces.

## Exposure posture (not internet-reachable)

Unlike slice-4 (App Host), **no internal service in this slice is internet-reachable**. The local-dev compose
publishes exactly one host port — nginx `127.0.0.1:8080:80` (`deploy/local-dev/docker-compose.dev.yml:316`) —
and nginx proxies only three upstreams: `/network/`→network, `/kernel/`→kernel, `/`→app-host
(`deploy/local-dev/nginx.conf:11-36`). Every service below runs internal-only on the docker network. So there is
**no "production exposure" section** here: the relevant threat is a **malicious co-resident container** (e.g. a
tenant's own confined runtime component, which the scheduler/runtime-manager place on the same docker network),
which can address `secrets:8102`, `model-gateway:8104`, `notify`, `filestore`, etc. directly by service DNS,
bypassing nginx. That is the substance of FND-8/FND-9 for this slice. (Note the shipped image sets
`BIND_HOST=0.0.0.0`, so every daemon listens on the docker network even though the code default is 127.0.0.1.)

## Summary (one page)

**Headline: no un-registered HIGH/MED finding surfaced.** The ADR-0124 service-auth **primitives are sound** and
every material weakness was already in the debt register. Two NEW **LOW** findings were opened (B49, B50); the
slice's one concrete conformance improvement (promote the automation `/events` gate to a positive assertion) was
applied and verified.

Substrate soundness (verified, `svc_authz.py` / `svc_token.py` / `tokens.py`):
- `ingress_gate` is genuinely **fail-closed when `require=True`**; a wrong-audience or `aud`-less token is always
  rejected; `tokens.verify` rejects `alg:none`/alg-confusion/expiry. `svc_token` is fail-closed and **never falls
  back to a passwordless login**. Issuer trust is implicit via the pinned `jwks_url` (no `iss` check — same family
  as DEBT-A5/A6, not new).
- **The structural flaw is not in the primitives but in how enforcement is wired**: `require` is driven by a
  per-service `<SVC>_REQUIRE_TOKEN` env that defaults **OFF (shadow)**, with no fail-loud on absence (FND-16). On a
  fresh install only **scheduler** and **automation** ship ARMED; **filestore ships SHADOW**; **model-gateway** and
  **notify** have **no inbound gate at all**.

Top risks for this slice (all pre-existing debt):
1. **model-gateway `/complete`,`/embed`,`/transcribe`** — unauthenticated money-spend endpoints, no caller tenant/
   quota/attribution; key resolves to the provider's default tenant. `DEBT-B5` (+ gate 3rd in the `DEBT-A72` flip
   queue, not yet wired).
2. **notify `/notify`** — unauthenticated; `tenant`/`actor` taken from the body → forge a `platform.inbox_item`
   into any tenant's inbox, unattributed. `DEBT-B5` / `DEBT-A40`.
3. **filestore `/files`** — gate present but SHADOW on a fresh install → anonymous blob read/write today.
   `DEBT-B5` / `DEBT-A72`.
4. **Shared static literals** (`SECRETS_INTERNAL`, `GW_INTERNAL`="gw-internal" default, `RUNTIME_MANAGER_INTERNAL`,
   `IDENTITY_INTERNAL`) instead of audience-bound tokens. `DEBT-A71` / `DEBT-A37` / `DEBT-A36`. Positive: secrets
   `/materialize`,`/fetch` and runtime-manager `/invoke` now **fail closed when their literal is unset** (the
   `DEBT-B4` fix landed) — the gaps are the literal and the missing audience/principal binding, not fail-open.
5. **Authorization (not authentication) axis** on the decision/workflow spine: decision `/decide` and workflow
   `/instantiate` accept any authentic token as the deciding/issuing authority with no recorded-grant check and
   derive tenant from the token claim (`DEBT-B3` / `DEBT-B1`); scheduler `/run` trusts a body-supplied tenant
   (`DEBT-A28` / `DEBT-A39`). Audience binding alone does not satisfy FND-2/FND-3 here.
6. **Durability**: delivery is durable (registry outbox), but automation dedup (`_PROCESSED`) and scheduler run
   receipts (`_RUNS`) are **in-memory** → a restart can double-fire actions or lose receipts. `DEBT-B10`.

Verdict counts (findings across the four reviewers): **HIGH 4, MED 4, LOW 5** — of which **0 are new HIGH/MED**;
**2 new LOW** (B49, B50) opened; everything else maps to existing B/A debt. The service-auth substrate reaches
"fit for a fresh-install production" only when shadow is eliminated as a possible default (FND-16 fail-loud),
the shared literals are retired to audience-bound tokens (DEBT-A71), the shared daemon principal is split
(DEBT-A68), and the recorded-grant re-check lands on decide/instantiate/run (DEBT-B1/B3/A28).

## Per-service findings

| Service | Inbound auth (fresh install) | Finding(s) | Rule(s) | Debt |
| --- | --- | --- | --- | --- |
| model_gateway `/complete`,`/embed`,`/transcribe` | **NONE** | unauth LLM/STT spend; no tenant/quota; key→provider default tenant | FND-8/9/10/12 | B5 (+A72 gate unwired) |
| model_gateway `/admin/provider-key` | `X-Internal-Token` == `GW_INTERNAL` default **"gw-internal"** | not fail-closed on unset (known literal); writes any provider key | FND-8/9 | A37/A71 |
| notify `/notify` | **NONE** | forge `platform.inbox_item` into any tenant, actor/tenant from body, unattributed | FND-8/10/12 | B5/A40 |
| filestore `/files` | ingress_gate, `FILESTORE_REQUIRE_TOKEN` **unset→SHADOW** | anon blob read/write today; **no owning-tenant scope even once gated** | FND-8/10/16 | B5/A72; **B49 (new)** |
| secrets `/set`,`/rotate`,`/copy`,`/status` | `tokens.verify` + **token-role/tenant** (`platform.steward`/`admin`) | authority from token roles + tenant claim, not recorded state; own-tenant blast radius | FND-1/2/3 | A66/B1 |
| secrets `/materialize`,`/fetch` | `X-Internal-Token` == `SECRETS_INTERNAL` (**fail-closed when unset**) | shared literal; `/fetch` is a caller-URL egress proxy (SSRF); `_path` leaves tenant/name unquoted | FND-8/9/10 | B16/A71/A38; _path note |
| runtime_manager `/invoke`,`/ensure-connector` | `X-Internal-Token` == `RUNTIME_MANAGER_INTERNAL` (**fail-closed when unset**) | docker+secret power gated by a shared literal, no principal allow-list; set in no deploy file | FND-8/9/10 | A36/A71 (B4 resolved) |
| scheduler `/run`,`/reload` | ingress_gate **ARMED**, allow=`{app-host}` | authN solid; `/run` trusts body `tenant`/`component` — cross-tenant fire not scoped to caller | FND-10/2/3 | A28/A39/B5 |
| automation `/events` | `_authz_event` **ARMED** (`AUTOMATION_EVENTS_REQUIRE_TOKEN:"1"`) | authN solid (anon/wrong-aud refused — now asserted); dedup in-memory | FND-5 | B10; (plain `deploy/local` profile ships shadow) |
| workflow `/instantiate`,`/complete-task` | `tokens.verify` (no aud); assignee check reads token roles | any authentic token issues a signed `governance.order` + tasks; authz from claim | FND-2/3/1 | B1 |
| decision `/decide` | `tokens.verify` (no aud) | any authentic token recorded as deciding authority; closes case, fires SOP; tenant from claim | FND-2/3 | B3 (DEC-4) |
| event_relay | inbound = health only | delivery durable (registry outbox) — sound | FND-5 | — (A68 shared principal) |
| embed (vector) `/embed` | **NONE** | unauth text→vector; compute/DoS only, no write/cost; also missing `import os` (correctness) | FND-8 | B5; os-import note |
| docrender | library (no endpoint) | `md_to_html` passes `javascript:` schemes + svg `onload=` (strips only `<script>`) — latent stored XSS | PLT-14 | **B50 (new)** |
| spec_generation | pure function (no endpoint/URL fetch) | none | — | — |

SSRF sweep of docrender/spec_generation/embed(vector): **clean** (no request-supplied URL fetched). The real SSRF
surface in this file set is secrets `/fetch` (DEBT-B16).

## Conformance cases (slice-5 delta)

Internal-services coverage already existed in `conformance/run.py::run_internal_cases()` (ADR-0124 ingress abuse
probes for filestore/notify/scheduler/model-gateway/automation/secrets + identity directory + kernel anon). This
slice adds:

- **Promoted** automation `/events` from a shadow-style tokenless probe to a **real assertion** (anon → 401/403,
  wrong-audience → 403), mirroring scheduler. The gate is ARMED in local-dev; this proves it with a PASS instead of
  recording SKIP_BUILD. Verified live: anon `/events` → **401** (`a token addressed to svc:automation is required`).
- **`run_internal_services_review_cases()`** (new) records the two NEW findings as **SKIP_BUILD** with proposed unit
  tests (neither is black-box-reachable on a seeded healthy stack):
  - `FND-10/DEBT-B49` — filestore cross-tenant read once gated.
  - `PLT-14/DEBT-B50` — docrender active-content sanitization (verified by direct `md_to_html` probe).

All other findings are already encoded against their existing debt ids; the matrix rows for those rules are
unchanged by this slice (they were already VIOLATED/PARTIAL/PLANNED as recorded).

## Debt opened

- **DEBT-B49** (FND-10) — filestore blob path has no owning-tenant scope (cross-tenant read once gated). LOW.
- **DEBT-B50** (PLT-14, content safety) — docrender shared renderer does not neutralise active content (latent
  stored XSS). LOW.
- Notes (no id): secrets `_path` unquoted tenant/name (subsumed by B4/A71); `embed.py` missing `import os`
  (correctness); scheduler `/run` body-tenant trust coverage gap (A28/A39).

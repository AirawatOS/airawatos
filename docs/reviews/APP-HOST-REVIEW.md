# APP HOST + BRIDGES review — Consolidation phase 5, slice 4

**Date:** 2026-11-06 · **Scope:** the reference App Host — `platform-spec/reference/app_host.py` (~10.4k ln),
`hostcore.py`, `host.py`, `embed.py`, `tokens.py`, `svc_token.py`, and `routes/{marketplace,studio,service,civic,
governance,knowledge}_routes.py` — against the rules the App Host is responsible for: **CLIENT CLI-1..CLI-6**,
**PLATFORM PLT-14/PLT-15**, **FOUNDATIONS FND-1/FND-2/FND-5/FND-8/FND-10**, **NET-12** (bridges exposing governed
data), and the "`/bridge` is never the public protocol" rules **CLI-6 / PTC-12**.
**Method:** three fresh, independent reviewer agents (not the authoring session), read-only, findings-only — no
code changed. Evidence is `file:line`. **The App Host is served at the PUBLIC ROOT on production** (EC2 nginx
`location /` → `app-host:8099`, https://airos.airawat.org/), so any ungated route is internet-reachable — every
headline finding was **verified live, read-only, against production** (no writes/publishes performed).

> **Matrix vs review** (as prior slices): STATUS-MATRIX.md is conformance-*measured*; this is a code *audit*. New
> cases (`conformance/run.py` → `run_apphost_review_cases`) encode the two cleanest reproducible violations as
> live XFAIL; the rest are SKIP_BUILD with a reason + a proposed internal test (several require a completed auth
> flow or a write and are not safe to automate against a shared/production stack).

---

> **Slice-5 hotfix update (2026-11-06).** DEBT-B41 and DEBT-B42 are now FIXED in local-dev (ship in reference
> image `dev-hard11`): `/bridge/component-publish` VERIFIES the bearer + requires the publisher role before any
> processing (anon/`Bearer x` → 401); `/bridge/service-offerings`, `/bridge/schemas`, `/bridge/schema-history`
> require an authenticated session (anon → 401); `/bridge/service-search` shows anon only `civic.resident`
> offerings (no audience bypass). Conformance `FND-8/DEBT-B41` + `NET-12/DEBT-B42` (×3) now PASS; matrix NET-12
> → HELD, FND-8 → PARTIAL. The remaining findings below (B43–B48, A82, CLI-2/3 embed, PLT-15) are unchanged and
> still open. **EC2 note:** per `docs/reviews/REVIEW-METHOD.md`, EC2 is a dev environment and out of scope; the
> prod-exposure lines below are retained as the as-found record (first production deploy = fresh install of the
> fixed source).

## 🔴 PRODUCTION EXPOSURE — unauthenticated, internet-reachable (as-found; retained for history)

1. **`POST /bridge/component-publish` — unauthenticated privileged write (CRITICAL, DEBT-B41).**
   `routes/marketplace_routes.py:327-377`: the only auth check is `if not auth.lower().startswith("bearer "):`
   (`:339`) — **presence of a bearer, never verified** (`tokens.verify` is never called). It then `extractall`s a
   tar.gz body (`:354`) and publishes via `_store_bundle(..., self._developer_token(), is_app=…)` (`:359`) —
   writing the content-addressed filestore, a governed `platform.component_asset` fact, and (for an app) an app
   overlay served live, **under the host's own dev-sandbox Vault token** regardless of caller; `cid`/`version`/
   `is_app` come from the query string. **Live prod check (read-only):** no `Authorization` → **401**;
   `Authorization: Bearer x` + empty body → **400 "empty bundle"** — i.e. any bearer string passes the gate; a
   real bundle would publish. *Impact:* anyone on the internet can publish/overwrite an app bundle (stored-XSS /
   app-frontend takeover of a basename) or an engine's `run.py`, and write arbitrary governed `component_asset`
   facts. (Serving a forged app may be refused when `cfg.verify_apps` is on, but the filestore+overlay+fact write
   already happened.) **Covered by conformance XFAIL FND-8/DEBT-B41.**
2. **`POST /bridge/service-offerings` — anon governed-directory manage view (HIGH, DEBT-B42).**
   `routes/service_routes.py:232-240`: no session, `forward_token=False`; returns **every** service offering incl.
   suspended/retired to an anonymous caller. Live prod: anon → **200**. **Covered by XFAIL NET-12/DEBT-B42.**
3. **`POST /bridge/service-search` — anon audience-gate bypass (HIGH, DEBT-B42).** `:195-212`: for an anon caller
   `my_roles` is empty, so `(audience in my_roles) or not my_roles` is True — the audience filter is **disabled**
   and anon sees audience-restricted (officer-only) offerings. Live prod: anon → 200.
4. **`POST /bridge/schemas` + `POST /bridge/schema-history` — anon governance provenance (HIGH, DEBT-B42).**
   `app_host.py:3817`, `:4298`: the full schema catalog **plus pending change-requests** and, per schema, every
   version merged with change-requests (who proposed/decided + justifications) — unauthenticated. Live prod:
   schemas → 200.
5. **Unauth front door + reads (MEDIUM, DEBT-B46/B48).** `/t/<tenant>/converse`, `/t/<tenant>/telegram/webhook`,
   `/embed/signup` are unauth + **unthrottled** and share the port with admin → LLM cost-amplification +
   username-enumeration (DEBT-B46). `GET /bridge/schedules|/bridge/runs` (schedules + run errors), `POST
   /bridge/fetch` (host-allowlisted egress proxy, SSRF-bounded), `POST /bridge/doc-ask` (anon LLM) are anon
   (DEBT-B48). (`/bridge/catalog` → **404** on the prod image — newer source only, not a prod exposure.)

The production edge containment applied for the network service (DEBT-B33/B34) does **not** cover these — they are
App Host routes under `location /`. These need their own gates (code) and/or an edge deny for the write/admin
bridges; not changed in this review-only slice.

---

## Summary (one page)

**Verdict counts (14 rules):** VIOLATED **7** (FND-1, FND-8, CLI-2, CLI-3, CLI-6, PTC-12, NET-12-via-bridges) ·
PARTIAL **5** (FND-2, FND-5, FND-10, PLT-14, CLI-1) · PLANNED/absent where honest (CLI-4 ops, PLT-15 controls).
No rule fully held. Token *verification* (`tokens.py`) is sound (no `alg:none`, anti-confusion, exp, optional
aud); service-to-service auth for scheduler/filestore (`svc_token.py`, Vault + audience-bound, fail-closed) is the
*correct* pattern. The problems are authorization and the public surface.

**Cross-cutting roots:**
- **FND-1 / DEBT-B1 (dominant):** authority is read from the token's `roles` claim in ~20 gates (`hostcore.py:126`
  `ADMIN_ROLES`; `app_host.py:2190-2199` `_effective_roles` `via:"identity"`), and several admin bridges set
  `forward_token=False` so the app-host role check is the SOLE gate (participants `:3930`, participant-resolve
  `:3945`, service-offerings manage) → **DEBT-A82**.
- **CLI-6/PTC-12 / DEBT-A23:** no `/v1`-versioned public protocol exists; the live surface is unversioned
  `/embed/*` + the internal `/bridge/*` RPC family at the public root.
- **Static internal secret / DEBT-A71:** app-host→identity/gateway uses a static shared secret whose code default
  is a committed literal (`app_host.py:45` `IDENTITY_INTERNAL='airawat-identity-internal'`, `:252`
  `GW_INTERNAL_TOKEN='gw-internal'`) — mirror the identity DEBT-B29 fix (drop the committed default → fail closed;
  move to an audience-bound minted token).

**New debt opened:** DEBT-B41 (component-publish unauth privileged write), B42 (anon governed-directory/governance
disclosure via bridges), B43 (signup enumeration oracle), B44 (host-forged client signature / no client auth),
B45 (session cookie no `Secure` + no CSRF), B46 (unauth+unthrottled front door, PLT-15), B47 (account-hold check
fails open), B48 (fail-open anon bridge reads/proxies); DEBT-A82 (bridge authority from token roles + forward_token
=False). **Existing debt confirmed:** B1, B2, B4, B5, B10, B12, B16, B31; A23, A27, A47, A48, A71.

**Correctly PLANNED / by-design (not violations):** `GET /open` (kernel-side `access.grant` auth), `/bridge/tile/*`
(mediated basemap), `POST /bridge/citizen-register` (public self-signup minting only `civic.resident`), the
`_bridge_dir` public governed-vocab catalogs; in-memory sessions (FND-5 PLANNED, DEBT-B10 — availability, not a
forge). CLI-4 missing ops and the CLI-6 versioned protocol are genuinely unbuilt (PLANNED), not implemented-wrong.

---

## Per-rule findings

| rule | verdict | sev | evidence (app_host.py unless noted) | debt | prod-exposed |
|---|---|---|---|---|---|
| CLI-1 registered clients + recorded scopes | partial | med | governed resolve `:896-923`; register session+admin gated `:1989-1993`; env-seeded `demo-embed` fallback `:834-836`; `same-origin-demo` bypasses exact-URI check `:1114-1119` | A47, A48 | partial |
| CLI-2 consent ∩ registered scope | **violated** | high | `scope` from request `:1150,1212`, never intersected with `client['scopes']`; consent hardcoded `service="*"`/`scope="service:invoke"` `:1547,1557` | DEBT-B12 | **yes** (/embed/authorize+login) |
| CLI-3 short-lived app-addressed token + consent ref | **violated** | high | `/embed/token` returns the raw citizen IdP JWT `:1297` (not aud-bound, no consent ref); verify accepts any citizen JWT regardless of client `:1569` | DEBT-B31 | **yes** (/embed/token) |
| CLI-4 client operations + client authentication | partial | med | several ops present; client "which app" signature is host-forged (`_embed_app_keypair` `:974-1003`); PKCE-only, no client secret | **DEBT-B44** | partial |
| CLI-5 handle resolution; anti-enumeration | partial/violated | med | directory now fail-closed (`identity.py:699-701`, DEBT-B6 held, not public); residual: `/embed/signup` enumeration oracle `:1268-1269` | **DEBT-B43** | **yes** (/embed/signup) |
| CLI-6 public versioned protocol; never /bridge | violated/planned | high | no `/v1` client protocol; live surface `/embed/*` + `/bridge/*` at root `:2833` | DEBT-A23 | architectural |
| PTC-12 one public versioned participant protocol; never /bridge | **violated** | high | first-party apps reach the platform via `/bridge/*` only `:2868-2925`; no versioning | DEBT-A23 | architectural |
| FND-1 identity carries no authority | **violated** | high | `_effective_roles` unions token roles as authority `:2190-2199`; ~20 role-claim gates; `forward_token=False` removes upstream re-auth `:3930,3945` | DEBT-B1, **A82** | session-gated (authority still token-driven) |
| FND-2 authority from recorded state | partial | high | partial: unions recorded `role_grant` `:2196` + kernel re-checks on proxy `:4555`; but token role alone suffices `:2217`; `_bridge_networks_mine` fabricates a network from the session tenant `:4526-4528` | DEBT-B1, B2 | no |
| FND-5 durable sessions; cookie hygiene; CSRF | **violated** | med | in-memory `_SESSIONS` (`hostcore.py:94`); cookie HttpOnly+SameSite=Lax but **no `Secure`** `:2761,2783,2818`; **no CSRF/Origin check** on cookie-auth bridge POSTs; fixation + logout OK | DEBT-B10, **B45** | defense-in-depth |
| FND-8 fail-closed; no unauth mint/mutation | **violated** | critical | `/bridge/component-publish` presence-only bearer → unauth publish (`marketplace_routes.py:339,359`); passwordless writer/admin mint `_agent_token` `:2376-2394`, `_intake_core` `:5688`; account-hold fails open `:767-772`; several fail-open anon reads | **B41**, B47, B48, B14 | **YES** |
| FND-10 least-privilege, audience-bound svc tokens | partial | med-high | scheduler/filestore correct (`svc_token.py`); identity/gateway use a static shared secret (`:45,252`); `_agent_token` mints full realm tokens, not capability-scoped | A71, B4, B16 | partial |
| PLT-14 admin visibility from recorded roles; every action re-checked | partial/violated | high | visibility + gating from token `roles`, not recorded `role_assignment` (same sites as FND-1); re-check exists + fails closed but checks the token role | DEBT-B1, B17, A82 | no |
| PLT-15 public front door = apply/verify/status, rate-limited, bot-protected, route-separated | **violated** | med-high | unauth `/embed/signup`, `/t/*/converse`, `/t/*/telegram/webhook` `:2842-2867,5023,5044`; no rate-limit/CAPTCHA; same handler/port as admin | **DEBT-B46** | **YES** |
| NET-12 bridges don't expose governed data unauth | **violated (via bridges)** | high | `/bridge/service-offerings` all-status anon (`service_routes.py:232`), `/bridge/service-search` audience bypass (`:212`), `/bridge/schemas`+`schema-history` provenance anon (`:3817,4298`) | **DEBT-B42** | **YES** |

## Conformance cases added
`run_apphost_review_cases()` (internal; App Host reached at `app-host:8099`). **Live XFAIL (verified on local-dev
AND production):** `FND-8/DEBT-B41` (`/bridge/component-publish` with `Bearer x` + empty body → 400, presence-only)
and `NET-12/DEBT-B42` (anon `POST /bridge/service-offerings` → 200). **SKIP_BUILD** (reason + proposed internal
test) for the rest — service-search audience bypass and schemas/schema-history provenance (reachable anon but a
clean assert needs a seeded fixture), CLI-2/CLI-3 (need a completed citizen login that writes a consent — unsafe to
automate), CLI-5 signup enumeration (a probe would create an account — a write), CLI-4/B44, FND-5/B45, PLT-15/B46,
FND-8/B47-B48, FND-1/A82, FND-10/A71, CLI-6/PTC-12/A23. Conformance both modes ×3 identical, 0 FAIL, 0 SKIP_CREDS.
Matrix: FND-1, FND-8, NET-12 → PARTIAL (App-Host XFAILs alongside the passing kernel/network cases).

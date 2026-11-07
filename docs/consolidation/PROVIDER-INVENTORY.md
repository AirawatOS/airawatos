# Provider & pluggable-backend inventory

Every capability in the installation that reaches **outside** the platform — external providers and pluggable
backends — with its owning service, adapter, call path, credentials, who chooses it, the checks applied before
the provider is called, the data sent, status, and related debt. **Docs only** (surveyed from the source tree;
no code changed). Evidence is `file:line`/`file:function`.

Shorthand: **N** = north / caller-facing interface, **S** = south / provider-facing adapter. "broker egress" =
`kernel/services/broker/broker.py` `Broker.egress(host)` (default-deny capability, confined-container path).

## Summary (one row per capability)

| # | Capability | Owning service (file) | Providers today | Dir | Provider chosen by | Creds (where / scope) | Pre-call checks | Status | Debt |
|---|---|---|---|---|---|---|---|---|---|
| 1 | AI chat/completion + embeddings | model-gateway (`model_gateway.py`) | OpenAI-compatible (`_openai`), Anthropic (`_anthropic`) | out | tenant (sets key) + governance (`intelligence.provider` records) | Vault `secret/<tenant>/<component>/<key>`, **per-tenant** | svc:model-gateway gate + run-token; metering.usage; **no consent / cost / rate limit** | working | A71, B5(closed), C-1 |
| 2 | Speech-to-text | model-gateway `/transcribe` (`_stt`) | Bodhan STT (OpenAI-audio wire) | out | tenant key; **bootstrap env fallback** | Vault per-(tenant,component); `STT_PROVIDER_ID`/base env | svc:model-gateway gate; metering | partial (bootstrap provider not governed) | A71, C-2 |
| 3 | Email (transactional) | network (`network/api.py` `_send_email`) | AWS SES, generic SMTP relay, dev-echo | out | operator/admin (email-sender component secret) | Vault `secret/<tenant>/email-sender/<FIELD>` or `SMTP_*` env, **per-tenant (join=authority tenant)** | none beyond send; no rate/consent/audit | working (else dev-echo) | — |
| 4 | Inbox / notifications | notify (`notify.py`) | *internal only* (writes `platform.inbox_item` to kernel) | — | — | — | svc:notify gate (slice-1c-ii) | working | — |
| 5 | Chat messaging — Telegram | app-host (`app_host.py` `_telegram_webhook`) + `telegram-concierge` adapter | Telegram Bot API | in+out | tenant (install adapter + set token) | Vault (bot token, confined in adapter); optional webhook secret | optional webhook secret; agent-grounded reply; **no rate limit on public door** | working | **B46** |
| 6 | Chat messaging — SMS/USSD | app-host (`app_host.py` `_bridge_sms_intake`) | SMS/USSD gateway (shared-secret seam) | in | operator | `SMS_GATEWAY_TOKEN` env (shared literal, per-installation) | shared-secret match only | partial / seam | A71-class |
| 7 | Federated mail (cross-tenant) | mail-engine + network signed-relay | AirawatOS peers (Ed25519 signed relay) | in+out | network (trust directory) | network authority key (Vault transit) | message signature (Ed25519); dev-steward fallback | working (2-tenant proven) | body-seal pending (#234) |
| 8 | Data sources / drivers | broker + `components/drivers/*` (~48) | Open-Meteo, Google Earth Engine, OSM/Overpass+PBF, CPCB/CAMS/ERA5/MAIAC/FIRMS, Open Buildings, GHSL, eSankhyiki, GDELT/RSS, OpenAQ, … | out | tenant (install driver + set key) | Vault per-(tenant,component) (driver secrets); GEE key per tenant | run-token + capability (egress/secret/write) default-deny **in confined path**; metering; declared egress hosts in `meta.yaml` | working | **B51, B52, B61, B63**, #197 |
| 9 | Cameras (video) | `rtsp-ingest` driver (`run.py`) | RTSP / RTMP / HLS cameras via ffmpeg | in (pull) | tenant (`device.camera` records) | Vault / `device.camera` stream creds, per-tenant | run-token; protocol allow-list | working | **B62** |
| 10 | External identity providers | identity + `tokens.py` (`verify`) | reference IdP (EdDSA) + OIDC RS256 (Keycloak live; Google/Azure alg-supported) | in (verify) | operator (configures issuers, ADR-0068) | issuer JWKS (public); no secret held | alg↔kty match (no `alg:none`), iss/aud, JWKS pin | working (ref + Keycloak) | — |
| 11 | Identity verification / VCs | credential service + network directory | native Ed25519 VCs; cross-issuer verify via directory pubkey | in+out | issuer tenant | Vault transit (issuer key), per-tenant | signature + issuer-pubkey from governed directory | working (wallet LIVE) | — |
| 12 | File / blob storage | filestore (`filestore.py`) | local disk (`FILESTORE_DIR`); **S3 = backlog** | — | hardcoded (local volume) | — (no external creds yet) | svc:filestore gate (slice-1c-ii) | working (single volume; not HA) | **B49**, REG-18 |
| 13 | Secrets backend | secrets (`secrets.py`) + Vault | HashiCorp Vault (KV v2 + transit) | out | hardcoded (Vault) | Vault AppRole per service (slice-1b) | per-service policy + internal gate | working (single-node; HA + KMS pending) | A71, RELEASE-PLAN §2c |
| 14 | Git hosting | `git-publisher` engine (`run.py`) | GitHub (https push) | out | tenant/project (Studio Git, ADR-0083) | token via secrets/Vault `credential_ref`, **per-project** | credential_ref (token never in meta/argv/logs) | working | — |
| 15 | Maps / basemap / 3D tiles | **client-side (app bundles)**; Cesium ion proxy *not built* | OSM/basemap tile CDNs, deck.gl/Cesium JS CDNs; Cesium ion (photoreal) | out (browser) | hardcoded (bundle) | none server-side; ion token proxy pending | **none — browser egress, unmediated** | partial | **B64**, #187 |
| 16 | Payments | *not built* | — (ADR-0067 fee-quote + consent is a declarative record) | — | — | — | — | **not built** (platform starts without it) | — |
| 17 | Events / webhooks (outbound) | event-relay (`event_relay.py`) | *internal only* (delivers to automation) | — | — | — | svc principal mint; at-least-once + deadletter | working (internal); **external webhook egress not built** | ADR-0089 |
| 18 | Geocoding | layered geocoder (drivers: `gazetteer-builder`, `geocode-ledger`) | local OSM gazetteer + PIN-code centroids; external geocoder optional | out (optional) | tenant | local data (no external key by default) | broker egress if external | partial (local-first) | — |

*New debt IDs B61–B64 and C-1/C-2 are defined in the findings sections below (to be folded into the DEBT-REGISTER).*

---

## Per-capability detail

### 1. AI chat/completion + embeddings — `model-gateway`
- **Owner / file:** `platform-spec/reference/model_gateway.py` — `_route(task, model)` (`:154`), `_openai` (`:179`), `_anthropic` (`:185`), `_vault_key` (`:88`).
- **Providers today:** any OpenAI-compatible endpoint (`/chat/completions`, `/embeddings`) and Anthropic (`/v1/messages`). Providers are **governed data** — `intelligence.provider` records (`:62`, loaded from the registry, cached 30s), each with `base_url` + `models[{name,task}]`.
- **Direction:** outbound.
- **Call path:** *confined component* → kernel `POST /v1/complete|/v1/embed` (run-token) → model-gateway `/complete|/embed` (**svc:model-gateway** gate) → provider. *App-host* (converse / ai-assist / translate) → model-gateway `/complete|/embed` directly with its own svc:model-gateway token. **N** = `/complete`,`/embed` (task+messages); **S** = `_openai`/`_anthropic` (provider wire). N and S are separated (task-routing in `_route`, provider wire in the adapters).
- **Credentials:** the provider key is read from Vault at `secret/<tenant>/<component>/<key_secret>` — the **same per-(tenant,component)** path the Components "Settings → API keys" UI writes (`_vault_key` docstring). Per-tenant (strict: no cross-tenant key fall-back).
- **Who chooses:** the **tenant** sets its key (→ that provider becomes usable); **governance** adds the `intelligence.provider` records (which providers exist). `_route` picks by task + key-presence; an explicit `model` wins.
- **Pre-call checks:** svc:model-gateway ingress gate (slice-1c-ii) + run-token (confined path); **metering.usage** record emitted (audit of spend). **Absent:** per-call consent, cost ceiling, rate limit, data-minimisation of the prompt.
- **Data sent:** the caller's `messages`/`prompt` (chat) or `texts` (embeddings) — potentially citizen/case content — plus model name.
- **Status:** working. Platform starts without any provider key (features that need an LLM degrade / 501 "set your key").

### 2. Speech-to-text — `model-gateway /transcribe`
- **Owner / file:** `model_gateway.py` `_stt` (`:116`), `_stt_provider` (`:134`).
- **Provider today:** Bodhan STT (OpenAI-audio `/audio/transcriptions` wire).
- **Call path:** browser (mic) → app-host `/bridge/transcribe` (thin proxy, mints svc:model-gateway) → model-gateway `/transcribe` → provider. **N** = `/transcribe` {audio,mime,language}; **S** = `_stt`.
- **Credentials:** Vault per-(tenant,component), same convention as §1.
- **Who chooses:** tenant (sets voice-provider key). **Partial governance:** `_stt_provider` falls back to a **bootstrap env provider** (`STT_PROVIDER_ID`, base URL env) when no governed `intelligence.provider` (task `transcribe`) record exists — a documented `TODO(governed)` (`:137`).
- **Pre-call checks:** svc:model-gateway gate; metering. No consent/limit.
- **Data sent:** raw audio bytes (voice) + language hint.
- **Status:** working; governance partial (see finding **C-2**).

### 3. Email (transactional) — `network`
- **Owner / file:** `network/api.py` `_send_email` (`:612`), config at `:571–581`; `_vault_secret` reads `secret/<tenant>/<component>/<name>`.
- **Providers today:** AWS SES or any SMTP relay (`SMTP_HOST`, STARTTLS), else **dev-echo** (logs the mail) when nothing is configured.
- **Direction:** outbound.
- **Call path:** network join/verify flow → `_send_email` → SES/SMTP. Only north side (there is no separated south adapter; SES-vs-SMTP auto-selected by which secret is set).
- **Credentials:** admin sets the **email-sender** component secret in Settings → Components; stored in Vault at `secret/<tenant>/<url-encoded component_id>/<FIELD>` (the secrets-service path). The public join flow uses the authority tenant (`JOIN_EMAIL_TENANT`, default `airawat`). Per-tenant.
- **Who chooses:** operator/admin (sets the email-sender secret).
- **Pre-call checks:** none beyond "secret present" — **no rate limit, consent, or audit record** of outbound mail; `_send_email` never raises (a failure degrades).
- **Data sent:** recipient address + verification link / notification body.
- **Status:** working (SES/SMTP) or dev-echo. Platform starts without it (join emails just log).

### 4. Inbox / notifications — `notify` (internal)
- **Owner / file:** `notify.py` — `/notify` writes `platform.inbox_item` to the kernel registry.
- **Not an external provider** — included because it is the "messaging" endpoint callers reach. Direction: internal. Gate: **svc:notify** (slice-1c-ii), callers decision + workflow. No outside egress.

### 5. Chat messaging — Telegram — `app-host` + `telegram-concierge` adapter
- **Owner / file:** `app_host.py` `_telegram_webhook` (`:5051`), adapter `ds:airawatdeveloper:adapter/telegram-concierge`.
- **Provider:** Telegram Bot API.
- **Direction:** inbound (webhook) + outbound (reply push).
- **Call path:** Telegram → edge `/t/<tenant>/telegram/webhook` → app-host extracts chat_id+text → `_service_agent` (grounded reply) → dispatches the **adapter** (passing CHAT_ID + TEXT) which holds the bot token and calls Telegram. **N** = the webhook; **S** = the adapter (token confined, never in the host).
- **Credentials:** bot token in Vault, read only by the confined adapter; optional `TELEGRAM_WEBHOOK_SECRET` (anti-spam, not the token). Per-tenant.
- **Who chooses:** tenant (installs the adapter + sets the token).
- **Pre-call checks:** optional webhook secret; the reply is agent-grounded. **Absent:** rate limit on the public webhook door — **DEBT-B46**.
- **Data sent:** the grounded reply text to Telegram.
- **Status:** working (adapter-gated).

### 6. Chat messaging — SMS / USSD (inbound) — `app-host`
- **Owner / file:** `app_host.py` `_bridge_sms_intake` (`/bridge/sms-intake`, `:3044`); `SMS_GATEWAY_TOKEN` (`:5705`).
- **Provider:** an external SMS/USSD gateway POSTs inbound messages; shared-secret header (`X-Gateway-Token == SMS_GATEWAY_TOKEN`, fail-closed).
- **Direction:** inbound.
- **Credentials:** `SMS_GATEWAY_TOKEN` env — a **shared static literal**, per-installation (A71-class).
- **Who chooses:** operator (configures the gateway + token).
- **Pre-call checks:** shared-secret match only.
- **Status:** partial / seam (intake wired; outbound SMS send is not a built provider).

### 7. Federated mail (cross-tenant) — `mail-engine` + network signed-relay
- **Owner:** `mail-engine` certified engine + network signed-relay endpoints (`network/api.py`).
- **Provider:** other AirawatOS participants (not a third party) — Ed25519-signed relay between tenants.
- **Direction:** inbound + outbound (peer).
- **Credentials:** network authority key (Vault transit); dev-steward fallback.
- **Checks:** message signature (Ed25519). **Pending:** envelope **body sealing** (X25519) — task #234; scheduled drain + arrival notifications (#231/#232).
- **Status:** working (local + EC2 two-tenant proven).

### 8. Data sources / drivers — `broker` + `components/drivers/*`
- **Owner:** `kernel/services/broker/broker.py` (egress/secret/write capabilities, default-deny) + ~48 driver components under `components/drivers/`.
- **Providers today (examples):** Open-Meteo (`rainfall-openmeteo`, `weather-forecast`), **Google Earth Engine** (`population-ghsl`, `buildings-footprints`, `landcover-dw`, `maiac-aod`, `nightlight-viirs`, `terrain-dem`, `change-detect-alphaearth`, `hydro-merit`), OSM/Overpass + PBF (`osm-roads`/`-facilities`/`-transit`/`-drainage`), CPCB/air (`air-sensors`, `openaq-archive`), CAMS/ERA5 (`cams-regional`, `era5-pblh`), FIRMS (`firms-fire`), Open Buildings (`buildings-openbuildings`), eSankhyiki CPI (`mospi-esankhyiki-cpi`), news (`news-gdelt`, `news-rss`), satellite LST (`satellite-lst`).
- **Direction:** outbound (pull).
- **Call path:** scheduler/app-host → kernel broker (run-token, mints confined run) → driver container; driver egresses via `ctx.egress(host)` (SDK → broker) **or** raw `urllib` (see finding B63). **N** = the run request (AOI/params); **S** = the driver's own HTTP/SDK to the source. Declared egress hosts live in each `meta.yaml`.
- **Credentials:** driver API keys (e.g. GEE service-account JSON) in Vault per-(tenant,component), bulk-loaded; read via the broker secret capability or the driver's own Vault read.
- **Who chooses:** tenant (installs the driver + sets its key / AOI).
- **Pre-call checks:** run-token + per-capability default-deny (egress host, secret, write) **in the confined-container path**; metering.usage. **Absent in the in-process path** (local-dev / DEBT-B51): the capability gate is not enforced (finding B63).
- **Data sent:** mostly an AOI bounding box / query params (not citizen PII) to public data APIs.
- **Status:** working (many drivers live). Related: **B51** (in-process unconfined), **B52** (placed-container egress policy), **#197** (egress User-Agent from tenant contact), **B61/B63** below.

### 9. Cameras (video) — `rtsp-ingest`
- **Owner / file:** `components/drivers/rtsp-ingest/run.py`.
- **Provider:** RTSP/RTMP/HLS cameras; ffmpeg dials the camera directly.
- **Direction:** inbound pull (→ `media.frame` + `device.stream_health`).
- **Credentials / who chooses:** `device.camera` records (per-tenant) carry the stream URL/creds; tenant enables cameras.
- **Pre-call checks:** run-token; the driver protocol allow-list (`rtsp/http/https/hls/rtmp`). **The broker cannot proxy RTSP** (HTTP-only) — ffmpeg opens the socket itself (finding **B62**).
- **Status:** working.

### 10. External identity providers — `identity` + `tokens.py`
- **Owner / file:** `tokens.py` `verify` (`:60`), `ALG_KTY` (`:18`); `identity.py` issuer.
- **Providers today:** the reference IdP (**EdDSA**/Ed25519, local issuer) and OIDC **RS256** providers (**Keycloak** live via `/kc`; Google/Azure are alg-supported but not wired).
- **Direction:** inbound (the platform **verifies** externally-issued user tokens; it holds no provider secret).
- **Credentials:** the issuer's **public** JWKS (fetched + cached); no secret.
- **Who chooses:** operator (configures trusted issuers — pluggable IdP, ADR-0068).
- **Pre-call checks:** header `alg` must match the key `kty` (no `alg:none`, no alg-confusion), `iss`/`aud` checks, JWKS pin.
- **Status:** working (reference + Keycloak).

### 11. Identity verification / Verifiable Credentials — credential service + network directory
- **Owner:** credential service (issue/verify/revoke) + the network participant directory (published issuer pubkeys).
- **Providers:** native Ed25519 VCs; cross-issuer verification resolves the issuer's pubkey from the **governed directory** (not a third-party CA).
- **Credentials:** issuer key in Vault transit (per tenant).
- **Checks:** VC signature + issuer-pubkey provenance from the directory.
- **Status:** working (Document Wallet LIVE; cross-state verify proven).

### 12. File / blob storage — `filestore`
- **Owner / file:** `filestore.py` (`FILESTORE_DIR`, `:24`); network filestore for cross-tenant.
- **Provider today:** **local disk volume** (content-addressed). **S3 is a backlog item** (archival tiering REG-18; HA shared-object-store in the HA audit).
- **Credentials:** none external yet (local volume).
- **Who chooses:** hardcoded (the local volume).
- **Pre-call checks:** svc:filestore ingress gate (slice-1c-ii, ENFORCE); **no owning-tenant scope on the blob key** — **DEBT-B49**.
- **Status:** working (single volume; not HA — any copy serves only its own volume).

### 13. Secrets backend — `secrets` + Vault
- **Owner / file:** `secrets.py` (KV broker) over HashiCorp **Vault** (KV v2 + transit).
- **Direction:** outbound (to Vault).
- **Credentials:** each service logs in to Vault via its **own AppRole** (slice-1b), scoped to a least-privilege policy; the shared root token is gone.
- **Who chooses:** hardcoded (Vault is the backend).
- **Pre-call checks:** per-service Vault policy; secrets-service internal gate (shared literal `SECRETS_INTERNAL` — A71, fail-closed).
- **Status:** working. Single-node file storage; **Raft HA + KMS auto-unseal** are a RELEASE-PLAN §2c gate.

### 14. Git hosting — `git-publisher` engine
- **Owner / file:** `components/engines/git-publisher/run.py`; governance `govern_git_binding.py`.
- **Provider:** GitHub (https push; `x-access-token` in the remote URL, `GIT_ASKPASS` keeps it out of argv/logs).
- **Direction:** outbound.
- **Credentials:** the Git token comes from the **secrets service (Vault) via `credential_ref`** — never in the engine/meta/logs. Per-project.
- **Who chooses:** tenant/project (Studio Git integration, ADR-0083).
- **Status:** working.

### 15. Maps / basemap / 3D tiles — client-side
- **Owner:** the **app bundles themselves** (browser), e.g. `components/apps/crowd-command`, `lucknow-3d`, `city-setup`, `waste-collector` — they reference external tile/JS CDNs.
- **Providers:** OSM/basemap tile servers, deck.gl / Cesium JS from CDNs; Cesium **ion** (photoreal) tile proxy is **not built** (#187).
- **Direction:** outbound **from the viewer's browser** — not mediated by any service or the broker (finding **B64**).
- **Credentials / who chooses:** hardcoded in the bundle; no server-side key.
- **Pre-call checks:** **none** (client egress).
- **Status:** partial (2D/3D render from public CDNs; ion proxy pending).

### 16. Payments — not built
- No payment-provider adapter exists. ADR-0067 S5 "fee quote + consent" is a **declarative governance record** (a quoted fee the citizen consents to) — **no money moves, no gateway is called**. The platform starts and runs without any payment capability. (The Prohibited-actions rule would in any case keep real payment execution out of the agent.)

### 17. Events / webhooks (outbound) — `event-relay`
- **Owner / file:** `event_relay.py` — drains the durable `platform.event` outbox and delivers **to the automation service** (`AUTOMATION_URL`, `:14`) at-least-once (ack→delivered, retry→backoff, max→deadletter). Signs in as the `airawat-scheduler` service principal.
- **Direction:** today **internal only** — there is **no external webhook egress** (no delivery to a tenant-supplied URL). Subscriptions are internal fan-out.
- **Status:** working (internal). External/outbound webhooks would be a new provider seam (ADR-0089 event/message spine).

### 18. Geocoding — layered, local-first
- **Owner:** drivers `gazetteer-builder` (OSM PBF → name→coord), `geocode-ledger`, PIN-code centroids.
- **Providers:** **local data** built from OSM/PIN sources (no external key by default); an external geocoder is optional (would egress via the broker).
- **Status:** partial (local-first geocoder; Delhi gazetteer + PIN centroids built).

---

## Findings — code that reaches an outside provider **directly**, bypassing its owning service

These are egress paths that do **not** go through the capability-mediated seam the architecture intends (the
broker's `egress(host)` gate for data, or the owning service for a transport). Each gets a DEBT id.

- **DEBT-B61 — EO drivers egress via the Earth Engine SDK, not the broker.** `components/drivers/{population-ghsl,buildings-footprints,landcover-dw,maiac-aod,nightlight-viirs,terrain-dem,change-detect-alphaearth,hydro-merit,buildings-openbuildings}/run.py` call `ee.Initialize(..., opt_url="https://earthengine-highvolume.googleapis.com")` — the Earth Engine client opens its own TLS to `earthengine.googleapis.com` / `oauth2.googleapis.com`. The hosts are **declared in `meta.yaml`** for certification/audit and the key is from Vault, but the broker's `egress()` gate never sees the call, so it cannot enforce the host allow-list, meter, or minimise at the seam. Same class applies to any provider SDK that opens its own socket. **Fix direction:** treat declared-SDK-egress as a first-class, enforced capability (allow-list checked by the runtime/network policy, not just recorded in meta) — ties to B52.

- **DEBT-B62 — `rtsp-ingest` dials RTSP directly (ffmpeg).** `components/drivers/rtsp-ingest/run.py` opens the RTSP/RTMP socket with ffmpeg because the broker speaks HTTP only and cannot proxy RTSP (documented in its header + meta). Egress is declared but not broker-mediated. **Fix direction:** a network-policy egress allow-list for the placed container (B52) covers the non-HTTP case the broker can't.

- **DEBT-B63 — in-process driver runtime does not enforce `broker.egress()`.** In the local-dev / in-process placement path (DEBT-B51, no container, host-env inherited) drivers that egress via raw `urllib` (e.g. `components/drivers/{news-gdelt,rainfall-openmeteo}/run.py`) are **not** gated by the broker capability — the default-deny egress check is only enforced on the confined-container path. So an in-process driver can reach any host. **Fix direction:** the confined-container placement (B51) + per-container egress policy (B52) is the closure; until then the in-process path is trusted-only.

- **DEBT-B64 — app bundles egress to external CDNs from the viewer's browser.** Several app bundles (`components/apps/{crowd-command,lucknow-3d,city-setup,waste-collector,admin}/dist/*`) load basemap tiles, deck.gl/Cesium JS, and other assets from external CDNs **directly from the browser** — outside any service and outside the broker. No egress allow-list or data-minimisation applies on the client. **Fix direction:** a content-security-policy / bundled-asset or proxied-tile policy for app bundles (pairs with the Cesium ion proxy, #187).

### Governance gaps (not bypasses, but recorded)

- **C-1 — AI calls have no consent / cost / rate limit.** model-gateway meters usage (audit) but applies no per-call consent, spend ceiling, or rate limit before sending a prompt (which may carry citizen/case content) to an external LLM. The decision-function work is the natural home for a pre-call policy gate.
- **C-2 — STT bootstrap provider is not governed.** `_stt_provider` falls back to an env-configured provider when no `intelligence.provider` (task `transcribe`) record exists — a `TODO(governed)`; the key is still Vault-held, but the provider is not a governed record.

---

*Survey only — no code or configuration changed. Debt IDs B61–B64 and C-1/C-2 are proposed here for folding into
[DEBT-REGISTER](DEBT-REGISTER.md); existing IDs referenced: B5 (unauth endpoints, closed by ADR-0124), B46
(Telegram public-door rate limit), B49 (filestore tenant scope), B51 (in-process confinement), B52 (placed-container
egress policy), A71 (shared-literal internal tokens), REG-18 (archival/S3).*

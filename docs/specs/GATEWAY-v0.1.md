# GATEWAY-v0.1 — Gateways: one door per class of outside party, north and south contracts

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**. **GTW rules
> are not yet in the matrix inventory** (`conformance/build_matrix.py` `INVENTORY`) and no conformance case cites
> them, so the matrix does not list them yet. The **Status** lines below come from
> [PROVIDER-INVENTORY](../consolidation/PROVIDER-INVENTORY.md) and are hand-written until the GTW conformance suite
> exists (GTW-12).

**Status:** Draft v0.1 · **Date:** 2026-11-08 · **Decision:** [ADR-0130](../decisions/ADR-0130-trusted-core-gateways-components.md) (Proposed)
**Builds on:** [[FOUNDATIONS-v0.1]] (FND-3 recorded grants, FND-8 fail-closed, FND-10 least privilege, FND-12
audit), [[DECISION-v0.1]] (DEC-1 decision records), [[PLATFORM-v0.1]] (PLT-16–PLT-21 shared services and
providers, as restated by ADR-0129), [[COMPONENT-v0.1]] (CMP-5/CMP-6/CMP-7/CMP-11), [[REGISTRY-v0.1]] (REG-14,
REG-17, REG-18) — assumed, not restated.
**Prefix:** `GTW-` (added to ID-SCHEME).

A **gateway** is a core door (ADR-0130 §1c) to one class of outside party. Callers reach providers **only**
through it. A gateway is never installable; the **provider adapters** behind it are components (GTW-10).

---

## Part A — The shared pattern

### GTW-1 — One gateway per capability class; gateways are core
Each capability class (messaging, conversation channels, AI models, data sources, identity providers, payments,
outbound webhooks, geo) has exactly one gateway. A gateway is part of the core: it is not installable, not
replaceable by a tenant, and runs under its own service identity (ADR-0124). Vault/secrets is core, not a gateway.
Operator infrastructure (file storage, git hosting — Part C) follows the same two-contract shape but is chosen
once per installation.
- **Status:** PARTIAL — model-gateway (AI), notify (messaging, internal) and the broker egress (data sources) exist;
  messaging email, channels, identity, geo, payments and webhooks have no gateway (inventory).

### GTW-2 — Two contracts, versioned independently
Every gateway exposes a **NORTH** contract (provider-neutral, for callers: capability + operation, never a vendor
name) and a **SOUTH** contract (for provider adapters or remote provider participants). Each is versioned
(`<gateway>.north@MAJOR.MINOR`, `<gateway>.south@MAJOR.MINOR`). A breaking change is a new major; the previous
major is served for a recorded deprecation window. A north change never forces a provider change, and the reverse.
- **Status:** PARTIAL — the model-gateway separates task routing (`_route`) from provider wires, but neither side
  is a versioned contract.

### GTW-3 — No path around the gateway
Callers (components, apps, services) cannot reach a provider except through the gateway's north contract. This is
**enforced by the network**, not by code convention: component and adapter egress is denied by default, and only
the gateway's south side and an adapter's declared destinations are reachable (GTW-11). Browser-side egress
counts: an app bundle may not load code, tiles or data from third-party origins directly (GTW-13).
- **Status:** VIOLATED in parts — DEBT-B65 (EO SDK), DEBT-B66 (RTSP), DEBT-B67 (in-process runtime), DEBT-B68
  (browser CDNs), DEBT-A43 (automation raw-URL action), and the email sender inside the Network.

### GTW-4 — Checks between north and south, every call, in order
Between the two contracts the gateway enforces: (1) **caller authentication** — an audience-bound service token
or a run token (FND-9); (2) **grant** — the caller holds a recorded grant for this capability and operation
(FND-3); (3) **consent or lawful basis** whenever personal data crosses, with the provider recorded as a data
processor (two-key rule, PLT-20); (4) **rate and cost limits** — the tenant's ceilings, and on a shared
installation the operator's (ADR-0129 infrastructure policy); then (5) the adapter call. Any failed step refuses
the call (fail-closed, FND-8).
- **Status:** PARTIAL — authentication is enforced on model-gateway, notify and the broker; grants partly (run
  token + broker capability); **consent, cost and rate limits are absent everywhere** (DEBT-B71, B46).

### GTW-5 — Audit, metering and a decision record on every call
Every north call, allowed or refused, leaves an audit entry, a metering record naming the **provider and version**
(for models, DEC-3 identity and version) and a **decision record** (DEC-1), personal data by reference (DEC-7).
- **Status:** PARTIAL — `metering.usage` on AI and drivers; no decision records; email sends leave no record.

### GTW-6 — Data minimisation
The south payload for an operation carries only the fields the operation's south schema names; north fields
outside it are dropped, never forwarded. Personal data crosses only when the operation requires it and GTW-4(3)
passed, by reference where the provider can resolve one.
- **Status:** PLANNED.

### GTW-7 — Providers cannot bypass the checks
A provider adapter receives **only** the minimised south payload and the provider credential for that call. It
never receives the caller's token, other tenants' data, or broader Vault access. It can reach only the gateway's
south endpoint and its declared provider destinations (GTW-11). Results return through the gateway, which
validates them against the south schema before anything goes north.
- **Status:** PARTIAL — the Telegram bot token is confined to its adapter; other provider wires run inside core
  services.

### GTW-8 — Provider credentials
Provider credentials live in Vault: per tenant for tenant-chosen providers, per installation for operator
infrastructure. Only the gateway reads them, and it hands them to the adapter run for one call. They are never
given to callers or components (PLT-18, ADR-0030).
- **Status:** PARTIAL — per-(tenant, component) Vault paths for AI and drivers; the SMS gateway uses one operator
  secret (DEBT-B64); STT can fall back to env config (DEBT-B72).

### GTW-9 — Who chooses the provider
For tenant-chosen capabilities the tenant chooses any provider whose adapter passes south conformance, or any
participant passing provider-role conformance (ADR-0129 Decision 6). The choice is a **governed binding record**
(tenant, gateway, provider, adapter version, failover order). There is **no platform-approved provider catalogue
and no platform approval or veto**. The platform sets only infrastructure policy for shared installations
(residency, outbound security baseline), applied equally. A Network may set minimums for its members (PLT-19).
Failover is tenant-defined and recorded (PLT-21).
- **Status:** PARTIAL — the AI provider is chosen by key presence + governed `intelligence.provider` records;
  elsewhere it is operator configuration.

### GTW-10 — Provider adapters are components
A provider adapter is an installable component: publisher-signed and content-pinned (B23), confined (B51/B52),
listed only after passing the gateway's **south conformance** suite (GTW-12), installed by the chooser (GTW-9).
It **declares its outbound destinations** (named provider hosts and ports), shown at install. Alternatively a
provider may be a **remote participant** speaking the same south contract over the federation door, its messages
signed by its registered key (FED5).
- **Status:** PARTIAL — `telegram-concierge`, `git-publisher`, the drivers and `rtsp-ingest` are adapter-shaped
  components; the declared-destination and south-conformance parts do not exist.

### GTW-11 — Declared egress is enforced by the network
An adapter's declared destinations are enforced by **network policy** at the runtime (a per-adapter egress
allow-list), not only by an in-code check. A library or SDK that opens its own connection (the Earth Engine
client, ffmpeg) cannot step outside the declaration.
- **Status:** VIOLATED — destinations are recorded in `meta.yaml` but enforced only by `broker.egress()` on the
  HTTP path (DEBT-B65, B66, B67; B52).

### GTW-12 — Conformance on both sides
Each gateway profile has a **north conformance** suite (the gateway enforces GTW-3–GTW-7 for every operation) and a
**south conformance** suite (an adapter implements the south contract, minimises, handles errors and declares
egress truthfully). Passing south conformance is the **listing requirement** for an adapter. There is no other
approval.
- **Status:** PLANNED.

### GTW-13 — No browser-direct egress
App bundles load scripts, styles and fonts from the installation's own origin, and fetch tiles and other remote
data **through the edge** (self-hosted or proxied). A **content security policy** set by the App Host restricts
`script-src`, `connect-src` and `img-src` to the installation's origin and its declared proxies.
- **Status:** VIOLATED — DEBT-B68 (crowd-command, lucknow-3d, city-setup, waste-collector, admin load from
  CDNs); the Cesium ion proxy is not built (#187).

### GTW-14 — Inbound channels bind the tenant from registration
For inbound traffic the south side receives the provider's callback and **verifies it per provider and per tenant**
(the provider's signature over the raw body, e.g. Meta's HMAC). The **tenant comes from the provider registration
the callback matched, never from the body**. The public door is rate-limited and route-separated (PLT-15). The
north side then delivers an **authenticated, normalised message** to the tenant's handler.
- **Status:** PARTIAL — Telegram has an optional webhook secret and no rate limit (DEBT-B46); the SMS/message
  intake uses one operator secret with the tenant taken from the body (DEBT-B64).

---

## Part B — Gateway profiles

Each profile: the north operations, the south contract, who chooses, current status (inventory row) and debt.

### Messaging
- **North:** `send(channel_kind, recipient, template|body, purpose)` → receipt; `status(receipt)`. Kinds: email,
  inbox, sms, federated, telegram.
- **South:** `deliver(minimised message, provider credential)` → provider id / error, per kind.
- **Chooser:** tenant (per-tenant sender credentials); platform mail (e.g. join verification) uses the authority
  tenant's sender.
- **Status:** email [3] working via SES/SMTP or dev-echo **inside the Network**, no rate limit, consent or audit;
  inbox/notify [4] internal only (the gateway's built-in internal provider); SMS outbound **not built**; federated
  mail [7] working — its south side is the **federation door (core)**, not an adapter, and envelope body sealing is
  pending (#234); Telegram outbound [5] sent by the `telegram-concierge` adapter.
- **Debt:** none registered for email (gap recorded here: no rate limit, consent or audit); #234.

### Conversation channels (inbound)
- **North:** delivers `message(tenant, channel, sender_ref, text|media, received_at, verification)` to the
  tenant's handler (agent, case intake).
- **South:** `receive(raw callback)` → verified, normalised message or reject; one adapter per provider.
- **Chooser:** tenant for Telegram; **operator** for the SMS/USSD gateway today. Target: tenant per provider.
- **Status:** Telegram inbound [5] working (optional webhook secret); SMS/USSD/message intake [6] partial, one
  operator secret in Vault; WhatsApp (the Meta HMAC check exists in `_bridge_whatsapp`) and IVR future.
- **Debt:** **DEBT-B46** (public door unthrottled, not route-separated), **DEBT-B64** (one shared secret; target
  per-provider per-tenant signed webhooks).

### AI models
- **North:** `complete(task, messages, model?)`, `embed(texts)`, `transcribe(audio, mime, language)`.
- **South:** provider wire per adapter (OpenAI-compatible, Anthropic, OpenAI-audio for STT).
- **Chooser:** tenant (sets its key) among providers recorded as `intelligence.provider` records.
- **Status:** chat + embeddings [1] working; STT [2] partial.
- **Debt:** **DEBT-B71** (no consent, cost ceiling or rate limit), **DEBT-B72** (ungoverned STT bootstrap
  provider).

### Data sources
- **North:** the broker's run request + `egress(host)` capability (kernel) for components; driver outputs are
  registry writes under the driver's grant.
- **South:** a driver or data-source adapter fetching from its declared provider hosts.
- **Chooser:** tenant (installs the driver, sets its key and area of interest).
- **Status:** drivers [8] and cameras [9] working on the confined path; geocoding [18] is local-first.
- **Debt:** **DEBT-B65** (Earth Engine SDK bypasses the broker), **DEBT-B66** (RTSP dialled by ffmpeg),
  **DEBT-B67** (in-process runtime skips `broker.egress()`), **DEBT-B51/B52**, #197. `services/mospi-gateway` is a
  data-source adapter (ADR-0130 §2).

### Identity
- **North:** `verify(external token)` → identity claims only (FND-1/FND-15); `issue_credential`,
  `verify_presentation` (VCs).
- **South:** an external issuer's JWKS / OIDC endpoints; VC issuer keys via the governed directory.
- **Chooser:** the **tenant** registers its own external identity provider; the **operator sets the floor**
  (decided 2026-11-08, ADR-0130 § Resolved questions 1). VC issuance by the issuer tenant [11]. The home issuer is
  core and not a provider.
- **Rules for a tenant-registered provider:** the issuer is **pinned to that tenant only**; a token naming another
  tenant is rejected; it **can never confer platform roles** (asserted roles are stripped; authority only from
  recorded grants — FND-1/FND-3/FND-15). The operator's floor is **infrastructure policy only**: minimum assurance
  level, protocol and algorithm requirements (signed OIDC ID tokens, alg↔kty match, no `alg:none`), JWKS pinning and
  key rotation, residency. It is applied equally, with no per-provider approval or veto (ADR-0128, ADR-0129).
- **Status:** working (reference IdP EdDSA + Keycloak RS256; Ed25519 VCs, wallet live). **Today the operator
  configures trusted issuers** (ADR-0068, inventory [10]); tenant self-registration under the operator floor is
  **not built**. The tenant pin and role stripping already hold (`network/authn.py`).

### Payments — build to contract
- **North:** `quote`, `authorise`, `capture`, `refund`, `status`; every call cites the consent record from the
  ADR-0067 fee quote.
- **South:** a payment-provider adapter.
- **Chooser:** tenant. **Status:** not built [16]. The platform starts without it.

### Outbound webhooks — build to contract
- **North:** `subscribe(event_type, target_ref)`, deliveries at least once with dedup and dead-letter.
- **South:** HTTPS POST to a **registered, verified** tenant endpoint, signed by the installation; the target is a
  registration id, never a raw URL.
- **Chooser:** tenant. **Status:** not built [17] — event-relay is internal only. The automation raw-URL action
  (DEBT-A43) moves behind this gateway.

### Geo
- **North:** `tile(layer, z, x, y)`, `asset(lib, version, path)`, `geocode(query)`, `reverse(point)`.
- **South:** a tile/asset provider adapter (OSM, Cesium ion, …) behind an **edge proxy**; geocoders.
- **Chooser:** tenant (layer providers); the operator chooses the edge cache.
- **Status:** maps/tiles [15] partial — **browser-direct** from CDNs; the ion proxy is not built (#187);
  geocoding [18] partial (local OSM gazetteer + PIN centroids).
- **Debt:** **DEBT-B68**.

---

## Part C — Operator infrastructure (chosen once per installation)

### File storage
- **North:** the core **filestore door** (`svc:filestore`), blobs as records (REG-18).
- **South:** a storage backend adapter (local volume today; S3-compatible object store).
- **Requirements:** blobs are **tenant-scoped** (the owning tenant is part of the key and checked on read —
  DEBT-B49) and **encrypted** (per-blob data key, ADR-0126 next slice).
- **Status:** working on one local volume, not HA [12]. **Debt:** **DEBT-B49**, REG-18.

### Git hosting
- **North:** publish / pull of a project's source by `git-publisher`.
- **South:** a git host (GitHub today).
- **Chooser:** per the inventory [14], **tenant/project** (ADR-0083, per-project `credential_ref`). ADR-0130 open
  question 1 asks whether this becomes operator infrastructure.
- **Status:** working.

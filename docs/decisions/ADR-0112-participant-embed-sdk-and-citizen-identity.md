# ADR-0112 — Participant‑embed SDK: citizen identity, consent, services & credentials in a third‑party app

- **Status:** Partially implemented — reference LIVE (2026-10-16). S1–S3 + S1b delivered and running on `airos.airawat.org` (reference image `manishsv/airawatos-reference:0.2.19-embed-seal`), spanning the full identity→services→credentials→presentation security chain with request signing + X25519 sealing. Mobile SDK (S4) and public-surface hardening (S5) remain. See **Implementation status** below.
- **Builds on:** [[ADR-0039]] (federated identity = network citizenship), [[ADR-0068]] (pluggable IdP / auth methods), [[ADR-0049]] (Document Wallet + native Ed25519 VCs), [[ADR-0067]] (service federation: directory → init → provider fulfil → receipt), [[ADR-0105]] (scalable citizen service tier), [[ADR-0103]] (per‑object sharing / `access.grant` consent), [[ADR-0026]] (agent = signed scoped delegate), [[ADR-0087]] (governed bridge / Data Exchange), [[ADR-0024]] (participant message signing), [[ADR-0079]] (metering), [[ADR-0030]] (thin SDK over a governed broker seam — the precedent), [[ADR-0111]] (channel‑agnostic public interface; an embed is a *relying‑party channel adapter*), [[ADR-0082]] (offline/edge trust — device‑held wallet option), [[ADR-0056]] (decided change‑request = governed approval).

## Context

A participant in the network — a bank, a utility, a city's own super‑app, an NGO — wants to **embed AirawatOS inside their own mobile app or website**. The goal: a citizen signs in, accesses services published by **other** participants across the network, and receives **credentials** (certificates) that land in their **digital locker**, reusable anywhere on the network.

The temptation is to build "an AirawatOS login button + some REST calls." That would re‑implement, per embedder, four things the platform already governs — and would quietly make the *embedding app* the owner of identity, consent, and credentials. The correct framing, consistent with [[ADR-0039]] and [[ADR-0111]], is:

> **The citizen is a network citizen, not an app user.** The embedding app is a **relying party** — it never owns the identity, the consents, or the credentials. Those live in the network and are **portable across every embedding app.** A credential issued to a citizen inside app A is verifiable and presentable inside app B.

This is exactly why a credential from a Kanpur utility is usable in a Nashik app, and why consent granted to one app does not leak to another. An embed is therefore a **channel adapter** ([[ADR-0111]] layer 4) over the same channel‑agnostic capability spine, plus a client SDK that stays strictly on the citizen's side of the trust boundary.

Crucially, **~80% of the substance already exists** as governed server capabilities (identity, wallet, service federation, consent, metering). What is missing is (a) a *citizen‑facing, consent‑gated* surface safe to expose to third‑party clients, (b) the consent handshake, (c) an app‑client registration flow, and (d) the SDK packages themselves.

## Decision

Build an **AirawatOS Participant‑Embed SDK**: a thin, redirect‑based client over four governed planes, with everything attributed, consent‑bounded, and metered. The SDK composes existing rails; it introduces **no new trust path** and never bypasses the kernel's zero‑trust gates.

### 1. The four planes (each already backed by an ADR)

| Plane | Citizen‑facing capability | Backing rail |
|---|---|---|
| **Auth** | Citizen signs in against the network IdP | [[ADR-0068]] pluggable IdP (Keycloak + kernel EdDSA/RS256); [[ADR-0039]] |
| **Consent / delegation** | Citizen grants the app scoped, revocable access | [[ADR-0103]] `access.grant`; [[ADR-0026]] signed scoped delegate |
| **Services** | Discover + invoke services published by *other* participants | [[ADR-0067]] directory→init→fulfil→receipt; [[ADR-0105]] citizen service tier; [[ADR-0087]] governed bridge |
| **Credentials** | A participant issues a certificate → citizen's digital locker | [[ADR-0049]] Document Wallet + Ed25519 VCs (issue / verify / revoke) |

### 2. Identity is redirect‑based; the SDK never touches raw credentials

Sign‑in is standard **OIDC Authorization‑Code + PKCE** against the network IdP:
- **Web** → redirect to the network login, back via `redirect_uri`.
- **Mobile** → system browser (AppAuth pattern) + deep‑link return; tokens in the platform secure store (Keychain / Keystore).

The embedding app is a registered **OAuth client** bound to its participant principal. The SDK obtains a **citizen‑scoped** token. It **never** collects a password or handles credential entry — this keeps identity network‑owned and keeps the embedder out of the credential‑handling blast radius. (A password manager / passkey is the IdP's concern, not the SDK's.)

### 3. Consent is explicit, scoped, and revocable — the handshake

The first time an app requests a scope (read profile, invoke service *X*, list wallet, present credential *Y*), the citizen sees a **hosted consent screen** and grants an `access.grant` ([[ADR-0103]]). The token the app acts with is **bounded to exactly what was consented** — modelled as a **signed scoped delegate** ([[ADR-0026]]): the app acts *on behalf of* the citizen, only within the granted scope, for a bounded lifetime, revocably from the citizen's network profile. Every delegated action is attributed to `(citizen, embedding‑app, grant)` and metered ([[ADR-0079]]).

### 4. Services — the SDK wraps the federation lifecycle

`discover()` reads the **service directory** ([[ADR-0067]]); `request(service, inputs)` opens a **provider case**, the *publishing* participant **fulfils**, and a **signed receipt** returns. The SDK talks only to the **citizen service tier** ([[ADR-0105]]) / governed bridge ([[ADR-0087]]) — a public, rate‑limited, consent‑gated subset of the gateway, never a privileged scope. This is the "access services published by other participants" plane, unchanged server‑side.

### 5. Credentials → the digital locker (and portability)

The issuer side of the SDK calls `issue(subject, type, claims)` → a native Ed25519 **Verifiable Credential** ([[ADR-0049]]) lands in the citizen's **holder wallet**. **That wallet *is* the digital locker**, keyed to the citizen's network identity, visible in any embedding app via `wallet.list()` / `wallet.present()` (selective disclosure). Verification is the existing cross‑tenant VC verify path (already LIVE). "DigiLocker" (India) is an **optional federation adapter** later — not the core; the native wallet is the locker.

### 6. New surfaces to build (the net‑new ~20%)

1. **App‑client registration** (`platform.app_client`, governed) — in the Developer Portal: an embedder registers an app (OAuth client id, PKCE, redirect URIs / deep links) bound to its participant principal, declaring the **scopes + services + credential types** it may request. Reuse‑or‑propose gate; a decided‑change‑request ([[ADR-0056]]) for production.
2. **Citizen gateway surface** — expose a **public, consent‑gated** subset of the service tier ([[ADR-0105]]) + wallet APIs, safe for third‑party embedding (rate‑limited, attributed, no operator/steward scopes).
3. **Consent handshake** — a hosted consent screen wired to `access.grant`, surfaced inside the OIDC flow, with a citizen‑facing "apps & permissions" revocation view.
4. **SDK packages** — `@airawatos/sdk` (JS/TS, web) and a mobile SDK (React Native / Flutter, or thin native) with PKCE + secure token storage + deep‑link auth. Pure wrappers over OIDC + citizen‑gateway HTTP + wallet; **no governance logic client‑side.**

### 7. SDK contract (illustrative)

```
const aos = AirawatOS.init({ appClientId, redirectUri, network })
await aos.login()                              // OIDC + PKCE; → citizen-scoped session
aos.citizen                                    // id, display name (consented profile only)
await aos.consent.request(['service:invoke','wallet:read'])   // shows consent screen → access.grant
await aos.services.discover({ domain })        // ADR-0067 directory
const { caseId, receipt } = await aos.services.request(svc, inputs)   // init → fulfil → receipt
await aos.wallet.list()                        // ADR-0049 holder wallet
await aos.wallet.present(vcId, { disclose })   // selective disclosure
// issuer side (participant app):
await aos.issue({ subject, type, claims })     // Ed25519 VC → citizen's locker
```

## Implementation status (reference, LIVE 2026-10-16)

Delivered in the reference `app-host` (`platform-spec/reference/app_host.py`), self-contained over the existing kernel/network/IdP rails — **no new trust path, no kernel change**. Live image `manishsv/airawatos-reference:0.2.19-embed-seal`; demo at `https://airos.airawat.org/embed/demo` (built-in client `demo-embed`, test citizen `democitizen` in the `citizens` realm).

**Endpoints (served same-origin by app-host, so the embed CSP stays `'self'`):**
- `GET /embed/authorize` · `POST /embed/login` · `POST /embed/token` — hosted OIDC-style **PKCE** citizen login against the `citizens` realm; app-host is the embed authorization server, credentials never reach the embedding page.
- `GET /embed/services` — the cross-participant **service directory** ([[ADR-0067]]), consent-gated.
- `POST /embed/request` — invoke a federated service → **provider fulfils** (see below) → receipt (+ issued credential).
- `GET /embed/wallet` — the citizen's **portable VC wallet** ([[ADR-0049]]); holder-keyed, visible to any app the citizen signs into.
- `POST /embed/proof-request` · `POST /embed/present` · `POST /embed/verify-presentation` — **Verifiable Presentation** handshake (below).
- `GET /embed/register` · `GET|POST /embed/clients` — **Developer-Portal app-client registration** (S1b).
- `GET /embed/sdk.js` — the browser SDK: `init / login / handleCallback / discover / request / wallet / requestProof / present / verifyPresentation / logout`.

**The trust chain actually enforced (what each layer proves):**
1. **Citizen JWT (JWT-first, [[ADR-0039]]).** The provider's fulfilment **independently verifies** the citizen's token against the citizen realm's published keys and binds to the *verified* subject — it does not trust host-passed claims. Confined to trusted realms (`EMBED_CITIZEN_REALMS`).
2. **App request signature ([[ADR-0024]], integrity).** The embedding app (BAP) **signs each request** with its own Ed25519 key over a canonical envelope `{service_id, inputs_sealed, citizen, client_id, nonce, ts}`; the provider verifies against the app's **published key on its `platform.app_client` record** (S1b registry = key directory) + enforces freshness (±300s) + single-use nonce.
3. **X25519-sealed body ([[ADR-0024]], confidentiality).** The request inputs are **sealed to the provider's** X25519 key and the presentation is **sealed to the verifier's** — end-to-end, so the network gateway routes *blind*. Sealed-box = ephemeral X25519 → ECDH → HKDF → AES-256-GCM.
4. **Consent ([[ADR-0067]]/[[ADR-0103]]).** A `governance.consent` grant gates service-invoke and credential-present; recorded in the citizen's tenant, revocable.
5. **Provider-signed issuance ([[ADR-0049]]).** Issuance happens **inside the provider's own fulfilment step** (`_provider_fulfil`, under the provider's authority) when the offering declares `fulfillment.issues_credential` — not on the citizen-app side. The VC is signed by the provider's steward key, verifiable against the directory.
6. **Holder-signed presentation ([[ADR-0049]]/[[ADR-0103]]).** Each citizen has an Ed25519 **holder key**; a Verifiable Presentation is bound to the verifier's challenge, holder-signed, sealed, and verified for: holder signature, issuer signature, challenge freshness (single-use), holder binding, not-revoked/expired.

**Deviations from the sketch (deliberate):**
- Issuance was moved from a citizen-app-side call to the **provider's fulfilment** (the correct BPP placement) after confirming — via Jan Seva — that the platform *does* invoke providers (`/bridge/service-route` → `_provider_fulfil`); the embed now routes the same way.
- Consent is recorded as `governance.consent` (the live [[ADR-0067]] model) rather than a distinct `access.grant`; reconcile naming with [[ADR-0103]] in hardening.
- **Credential presentation (VP)** was added beyond the original S3 (which stopped at issuance+portability) — it is the "submit a certificate as proof on request" half.

**Reference-only shortcuts (to productionize):**
- Signing/holder/provider/verifier **private keys live in app-host's durable keystore** (`/data/app-bundles/.secrets/*.json`); their **public keys** are co-located (resolved from the keystore) for app-client/provider/verifier/holder. In a distributed deployment these public keys must be **published in the network directory / a holder DID doc** so sealing + verification work across separate nodes. (The `platform.app_client` record already publishes the app's signing key — that path is the model.)
- The demo provider `new-delhi`'s issuer credential is sourced from the `EMBED_ISSUERS` env (→ Vault); properly-onboarded providers use the standard passwordless `<provider>-admin` service principal.
- `platform.app_client` records are durable (kernel registry, airawat tenant) but the **schema** lives in the network's in-memory catalog (re-publish on a network restart).

## Slicing (prove narrow, end‑to‑end, before generalizing)

- **S1 — client + auth:** ✅ **DONE.** JS SDK `login()` (PKCE) → consented citizen profile; identity network‑owned, redirect‑only.
- **S1b — app‑client registration:** ✅ **DONE.** Governed, durable `platform.app_client` in the airawat platform registry; Developer‑Portal page (`/embed/register`); app-host resolves `client_id` from the registry (env default as fallback); the record also publishes the app's request‑signing key.
- **S2 — consent + one service:** ✅ **DONE.** Consent handshake (`governance.consent`) → `request()` a federated service (new‑delhi Address Certificate) → signed receipt.
- **S3 — credential + portability:** ✅ **DONE.** The **provider** issues a VC into the wallet *during its own fulfilment*; a second app/token for the same citizen sees the same credential (holder‑keyed, portable). VC cryptographically verified against the issuer's directory key.
- **S3p — presentation (added):** ✅ **DONE.** Relying app requests proof → citizen consents → **holder‑signed, sealed Verifiable Presentation** → verifier checks holder+issuer signatures, challenge (single‑use), holder binding, revocation/expiry.
- **Security hardening (ADR‑0024/0039):** ✅ **DONE.** JWT‑first provider verification; per‑request app signature (anti‑tamper + anti‑replay); X25519 end‑to‑end body sealing (request inputs → provider, VP → verifier).
- **S4 — mobile:** ⏳ pending — same contract with platform auth glue (system browser + secure store + deep link).
- **S5 — public‑surface hardening:** ⏳ pending — rate limits, grant‑revocation UX ("apps & permissions"), metering dashboards, abuse controls; move reference keystore secrets to Vault and publish public keys to the directory / holder DID for true cross‑node operation.

S1–S3 (+S1b, +presentation) exercise all four planes with real governance, now with signing + sealing; the mobile SDK (S4) is the same contract.

## Consequences

- **Pro:** third parties onboard the network without re‑implementing identity/consent/services/credentials; citizens get one portable locker + a single consent ledger across every embedder; the platform keeps attribution, metering, and the zero‑trust gate intact; aligns with the north‑star (core = spec + certified third parties).
- **Con / risk:** a public, internet‑facing citizen surface widens the attack surface — must be rate‑limited, consent‑gated, and carry **no** privileged scopes; app‑client registration is a trust decision (governed via CR); mobile key/token storage needs platform‑secure handling.

## Non‑goals (this ADR)

- Not a new identity system — it rides [[ADR-0068]].
- Not a new wallet — it exposes [[ADR-0049]].
- Not DigiLocker interop — a later federation adapter.
- Not on‑device/offline wallet — server‑held‑with‑presentation is the default; [[ADR-0082]] is the path if offline is required.

## Open questions

1. **Wallet residency:** server‑held‑and‑presented (default, centrally revocable, portable) vs device‑synced ([[ADR-0082]], offline but heavier key management). **Resolved for the reference:** server‑held, with a holder Ed25519 key that signs presentations; device‑held is the [[ADR-0082]] path if offline is required.
2. **Delegate model:** **Resolved (reference):** consent is a `governance.consent` grant ([[ADR-0067]] model) per (citizen, app, service/credential); reconcile naming with [[ADR-0103]] `access.grant` and the [[ADR-0026]] signed‑delegate facet during hardening.
3. **Discovery scope:** does an embedding app see the *whole* network service directory, or only services its participant is permitted to surface? **Reference today:** whole directory (consent‑gated to a signed‑in citizen); app‑declared allow‑list filtering is a hardening item.
4. **Public‑key distribution (the main distributed‑deployment gap):** the reference resolves app / provider / verifier / holder **public** keys from app‑host's co‑located keystore (and the `platform.app_client` record for the app's signing key). For true cross‑node operation these must be published in the **network directory / a holder DID document** so signing + sealing verify across separate hosts.

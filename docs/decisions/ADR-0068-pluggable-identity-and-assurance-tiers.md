# ADR-0068 — Pluggable identity providers + auth-method assurance tiers

> **⚠️ PARTIALLY SUPERSEDED (2026-11-05).** The cited *"tenant login = network citizenship; participant derived
> from realm"* model is overturned by **ADR-0116** (participant ≠ tenant; membership is tenant-free) — see
> **PLATFORM-v0.1 P4**, **NETWORK-v0.1 N1**, **FOUNDATIONS-v0.1 F3**. The passwordless tier (A0) is retained
> **only** as scoped by **ADR-0121**: permitted in local/offline dev, while production enforces
> `IDENTITY_PASSWORD_REQUIRED=enforce` (every account presents a password; #282). The pluggable-IdP /
> assurance-tier design otherwise stands. Body unchanged below.

- **Status:** Proposed (2026-09-02)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0011 (per-tenant realms + **assurance tiers** — this ADR implements the tiers),
  ADR-0039 (federated identity — *tenant login = network citizenship*; participant derived from realm),
  ADR-0024 (per-actor Ed25519 message/decision signing — **distinct** from login auth), ADR-0026 (agent = signed
  scoped delegate, `component:// obo user://`), ADR-0029/0046 (decision spine + hourglass — auth gates the
  **authority to decide**), ADR-0049 (holder wallet + verifiable credentials — a future assurance input). Also
  closes the kernel-review finding **S2** (`authn.verify` skips `aud`/`iss`/`alg`/`nbf`; JWKS has no TTL).
  External reference: **OpenID Connect / OAuth 2.0** (authorization-code + PKCE, `acr`/`amr` claims) and
  **Keycloak** as the platform-hosted IdP.

## Context

Authentication today is a **walking skeleton**: `reference/identity.py` issues a short-lived EdDSA JWT for any
username in a fixed dev directory — its own docstring says *"passwordless dev auth over a fixed user list — the
point is the TOKEN contract, not credential checking."* The OS trust boundary is the token, not the login: the
kernel's `authn.verify` accepts **any JWT whose signature verifies against the identity JWKS** and derives the
actor from `sub` + `tenant` + `roles`. Nothing downstream knows or cares *how* the person proved who they are.

That seam is exactly right — but the credential half is missing. For production civic deployments this is not
acceptable:

- tenants hold **citizen PII** and officials make **signed, accountable decisions** (`governance.decision`);
- different agencies and **different user types** need different methods — an official approving a payment
  should present **password + MFA**; a citizen filing a Field Report wants **email/SMS OTP or Sign-in-with-Google**;
- some agencies already run their **own IdP** (Google Workspace, a state SSO, Azure AD) and won't want a
  second credential store.

ADR-0011 already posits **assurance tiers** but never implemented them. We want real methods —
**password · email OTP · SMS OTP · Sign-in-with-Google/Microsoft · authenticator app (TOTP) · MFA** — that a
tenant admin can **configure for their users**, without weakening (or even touching) the OS's authorization
model, and without hand-building an identity provider (a large, security-critical surface on a high-value
target).

## Decision

Make **identity a pluggable provider behind the unchanged JWKS trust boundary**, and bind **auth method →
assurance tier → the authority to act**.

### 1. The trust boundary does not move

The OS keeps trusting a **JWKS-verified JWT** carrying the claim contract. The IdP is swappable; the kernel,
broker, apps, and every authorization gate (own-tenant writes, steward grants, decision spine) are **unchanged**.
The **session token contract** every IdP path MUST honour:

| claim | meaning |
|---|---|
| `sub` | stable subject (`user://<tenant>/<id>` or the IdP subject) |
| `tenant` | the realm / platform tenant |
| `roles` | governed roles (drives RBAC) |
| `assurance` | **new** — the achieved tier (see §3), from OIDC `acr`/`amr` |
| `amr`, `acr`, `idp` | **new** — methods used, context class, issuing provider |
| `iat`, `exp` | short-lived |

Hardening (folds in kernel-review S2): `authn.verify` MUST validate `aud` (the kernel), `iss` (the realm),
reject `alg != EdDSA`, honour `nbf`, and re-fetch JWKS on a short TTL (not only on `kid` miss) so revoked keys
stop verifying.

### 2. Pluggable IdP — per tenant (realm)

- **Default — platform-hosted Keycloak (Option B).** One Keycloak, **one realm per platform tenant** (matching
  ADR-0011/0039 realms). Keycloak natively provides password policies, email/SMS OTP, **TOTP authenticator
  apps**, **social login** (Google/Microsoft), and MFA/step-up. The platform **Admin console wraps the realm's
  auth-method config** (via the Keycloak admin API) so a tenant admin turns methods on/off without touching
  Keycloak directly. `IDENTITY_JWKS` for that tenant points at the realm's JWKS.
- **Escape hatch — bring-your-own OIDC IdP (Option C).** A tenant registers an **external OIDC provider** (their
  Google Workspace, Azure AD, a state SSO, Auth0). Login federates to it; the platform preserves the claim
  contract by **token exchange** — the external token is verified, then a platform-realm token is minted with the
  mapped `sub`/`tenant`/`roles`/`assurance` — so the OS never sees a foreign claim shape.
- **Development tenants keep `reference/identity.py`** (passwordless). Dev sandboxes stay frictionless; the
  reference service is explicitly **not** the production IdP.

### 3. Auth method → assurance tier (the governance binding)

Define a governed **assurance ladder** (ref vocabulary, like domains/roles):

| tier | example methods |
|---|---|
| **A0** | dev passwordless (development tenants only) |
| **A1** | single factor: email/SMS OTP, or social (Google/Microsoft) |
| **A2** | password (with policy) |
| **A3** | multi-factor: password **or** social **+** TOTP/OTP; step-up required |

The IdP stamps the achieved tier into the token (`acr`/`amr` → `assurance`). A per-tenant, **per-role /
per-action-class** policy declares the **minimum assurance** required — and it is enforced **at the point of
authority, not just at login**:

- view your own dossier / file a report → **A1**
- approve a decision · move money · **sign a `governance.decision`** → **A3**

A low-assurance session may browse; a high-stakes act triggers **step-up re-authentication** to the required
tier. This turns login into a first-class part of the **accountability chain** — the same spine where AI
recommends and a human *decides* (ADR-0029/0046) now also records **at what assurance** the human acted.

### 4. Login auth ≠ actor signing (reaffirm ADR-0024)

Login proves *who you are* to obtain a session; the **per-actor Ed25519 key** signs decisions/orders. High
assurance **gates the ability to use** the actor key for a signed act; it does not replace the signature. The
two identities stay cryptographically distinct.

### 5. Where config + policy live (governed)

- `governance.auth_policy` (per tenant): enabled methods, `idp` binding (`keycloak-realm` | `oidc-external`
  + config), and the min-assurance map per role/action-class. Authored in the Admin console.
- Provider secrets (OAuth client secrets, SMS/email provider keys) → **Vault + the secrets service** (existing).
- The assurance ladder + method→tier mapping → a **governed `ref.*` vocabulary** (network-signed, like roles).

## Alternatives considered

- **Hand-roll every method in `identity.py`.** Rejected — that is *building an IdP* (password hashing, OTP
  issuance + anti-abuse rate-limiting, TOTP secret storage, OAuth flows, account recovery, session/lockout).
  Large, security-critical, and needless: Keycloak does all of it, per-realm, battle-tested.
- **One global IdP, no per-tenant config.** Rejected — agencies differ and some bring their own IdP.
- **Social/OIDC only (no platform password/OTP).** Rejected — many citizens and agencies need password/OTP
  without a Google account.
- **Enforce assurance only at login.** Rejected — a session outlives a single act; the authority to perform a
  *specific* high-stakes act must be checkable at that act (step-up), so assurance lives in the token + policy,
  not a one-time gate.

## Consequences

- **+** Real, configurable auth **without touching the OS authorization model** — the JWKS seam already exists.
- **+** Auth becomes a **governance control** (assurance → authority), strengthening the decision spine and
  giving accountable actions a recorded assurance level.
- **+** Tenants self-serve their methods; BYO-IdP fits real agencies (ADR-0039 network-citizenship model).
- **+** Closes kernel-review **S2** as a side effect (aud/iss/alg/nbf + JWKS TTL).
- **−** **Operational weight**: run/patch/back-up Keycloak (HA); SMS costs + fraud controls; account-recovery UX;
  step-up UX in the app-host cookie-session flow (today a simple POST /login).
- **−** **Migration**: existing passwordless *production* sessions move to Keycloak; app-host login must add the
  OIDC authorization-code + PKCE redirect. During transition the kernel trusts **multiple JWKS** (reference
  identity for dev + Keycloak realms for prod) — resolve the realm's JWKS per `iss`.
- **−** The claim contract now carries `assurance`/`amr`/`acr`/`idp`; every issuer path (Keycloak mappers, the
  token-exchange for BYO-IdP, the dev reference service) must set them consistently.

## Slice plan

1. **S0 — model + hardening.** Govern `governance.auth_policy` + the assurance-ladder `ref` vocab; extend the
   token contract (`assurance`/`amr`/`acr`/`idp`); harden `authn.verify` (aud/iss/alg/nbf + per-`iss` JWKS with
   TTL). No user-visible change; dev stays passwordless.
2. **S1 — Keycloak as prod IdP, one tenant.** Stand up Keycloak (Vault-backed realm keys); one realm = one
   tenant; methods = password + TOTP + Google; point that tenant's `IDENTITY_JWKS` at the realm; app-host login
   does the OIDC redirect. Other tenants unchanged.
3. **S2 — per-tenant auth-method config UI.** Admin-console panel over the Keycloak admin API; wire email/SMS
   OTP providers (SES/Twilio) via Vault/secrets.
4. **S3 — assurance enforcement + step-up.** The decision spine + a declared set of sensitive verbs require a
   minimum `assurance`; a below-tier session gets a step-up challenge and a fresh higher-assurance token.
5. **S4 — BYO-IdP (Option C).** Register an external OIDC provider per tenant; token-exchange to preserve the
   platform claim contract.

## Non-goals

- **Not** replacing per-actor Ed25519 decision-signing (ADR-0024) — auth *gates* it, doesn't replace it.
- **Not** changing the kernel's authorization gates (own-tenant writes, steward grants) — only **who** the token
  says you are and **at what assurance**.
- **Not** building a bespoke identity provider.
- **Not** a citizen identity / KYC system (Aadhaar-style). Verified credentials (ADR-0049) are a *separate*
  concern; a VC could later *feed* an assurance tier, but that is out of scope here.

## Token hardening backlog (2026-09-13, from an OIDC/JWT best-practice review)

We use OIDC-standard primitives (JWT + JWKS, EdDSA/RS256, Authorization-Code+PKCE, Keycloak as a real IdP,
per-issuer JWKS) — the reference identity is a passwordless **dev shim** on the same token/JWKS contract. The
review (RFC 8725 / RFC 9700) confirmed the shape is right and flagged operational hardening:

**Done / in place**
- Asymmetric signing keys in **Vault transit** (never exported); per-tenant issuers (ADR-0084) shrink key-compromise blast radius.
- JWKS **refetch on unknown-kid / bad-sig** (self-healing rotation); per-issuer `kid` lookup within the selected issuer.
- **RFC 8725 on the Network verifier:** explicit `iss` allowlist (trusted-issuer set), `aud` validation, explicit **alg allowlist** (EdDSA — never a token-chosen alg). Live kernel authz re-check (steward grants / `governance.role_grant`) rather than trusting token role-claims alone.

**Backlog (tracked, not blockers)**
1. **Immediate revocation** — short access-token TTL (→ ~5–15 min) + refresh-token rotation; an emergency deny-list; and **cache invalidation when an issuer is de-registered** (dropping it from the trusted set must propagate, not linger in caches).
2. **Sender-constrained tokens** — DPoP or mTLS for high-impact operations, so a stolen bearer can't be replayed.
3. **Bounded issuer authority** — record, per registered issuer, the tenant + roles it may assert; drop out-of-bounds external claims (see ADR-0084). Governance, not crypto.
4. **Hygiene** — redact `Authorization` headers in all logs/proxies; keep claims minimal (no PII — already the rule).

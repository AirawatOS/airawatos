# CLIENT-v0.1 — Client apps, tokens, and the public protocol

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (F1 tokens-carry-identity-only, F9 audience-bound tokens, F10
least-privilege, F13 consent), [[REGISTRY-v0.1]], [[DECISION-v0.1]] (D1 decision records), [[ACCOUNT-v0.1]]
(A5 provider connections, A7 consent), [[NETWORK-v0.1]] (N10/N11/N12 offerings, exchange, directory).
Assumed, not restated. **Debt references** are to `../consolidation/DEBT-REGISTER.md`. *(to confirm)* = not
traced this pass. **Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

A **client** is an application (first- or third-party) that acts through the public protocol **on behalf of a
person** (and must therefore obey FOUNDATIONS F17 acting-on-behalf), never with ambient authority.

---

## Client rules

### C1 — Registered clients with recorded scopes
A client is a **registered record** (`platform.app_client`) with **recorded scopes** — the maximum set of
things it may ever ask for. An unregistered caller is not a client.
- **Status: PARTIAL.** Governed `platform.app_client` registration exists (ADR-0112 participant-embed; the
  client-SDK path of ADR-0117). But a transitional **env/default allow-list + a seeded `demo-embed` client**
  remain (debt A47), and the `same-origin-demo` redirect bypasses the exact-URI check (debt A48) — so
  "registered clients only" is not yet exclusive.
- **Refs:** ADR-0112, ADR-0117; debt A47, A48. Governed-clients-only is the fix (S1b).

### C2 — Consent-bounded, within registered scopes (fixes B12)
An app gets **only what the person consents to**, and **only within its registered scopes** (C1). The
effective grant is the **intersection** of (registered scope) ∩ (person's consent). **This is the fix for
debt B12.**
- **Status: VIOLATED (fix target).** Today embed `/embed/authorize` takes **`scope` from the query string**
  and the consent is written **`service:"*"`** regardless of the client's registered scopes (debt **B12**) —
  an app registered for `profile` can obtain a `service:invoke` consent. Neither the registered-scope ceiling
  nor the consent intersection is enforced.
- **Refs:** debt **B12**; ADR-0125 (consent), ADR-0112; F10 (least privilege), F13. Bind requested scope ≤
  registered scope ∧ ≤ recorded consent. PLANNED fix.

### C3 — Short-lived, app-addressed tokens carrying identity + consent reference
Client tokens are **short-lived**, **addressed to the app** (audience-bound, F9), carry **identity only**
(F1), and reference the **consent** they act under.
- **Status: PARTIAL / TO CONFIRM.** Tokens are short-lived (1h) and audience-bound exists as the home-issuer
  pattern (F9); the embed flow uses redirect OIDC + PKCE (ADR-0112). But **no durable client/service
  credential** underlies renewal (debt A33), and whether the token **carries a consent reference** (vs.
  consent resolved separately) is **(to confirm) / PLANNED**. Identity-only holds in principle but downstream
  still reads token roles (debt B1).
- **Refs:** F1, F9; debt A33 (1h token, no durable cred), B1; ADR-0112. Consent-reference-in-token **(to
  confirm)/PLANNED**.

### C4 — Operations
The client protocol offers: **find/create account**, **resolve handle**, **verify identity**, **connect
accounts and wallet**, **discover offerings**, **check eligibility**, **present** (a credential), **request**
(a service), and **track** (status).
- **Status: PARTIAL.** A citizen-auth client surface is live (ADR-0112 S1: redirect OIDC+PKCE, `/embed/demo`,
  `/embed/request`); offerings discovery + eligibility exist via the service directory (NETWORK N10/N12,
  ADR-0067); wallet present/verify via ADR-0049. **find/create account, resolve handle, connect accounts,
  track** as first-class protocol operations are **(to confirm)** / partially present.
- **Refs:** ADR-0112, ADR-0117 (client SDK), ADR-0067 (offerings/eligibility/track), ADR-0049 (present);
  ACCOUNT A1–A6. Full operation set **(to confirm)**.

### C5 — Minimal handle resolution; registered clients only; anti-enumeration
Handle resolution returns the **minimum** needed, is available to **registered clients only** (C1), and is
**anti-enumeration** (no bulk/scan discovery of accounts).
- **Status: VIOLATED / TO CONFIRM.** The sibling identity directory is **unauthenticated and enumerable** —
  `GET /users`, `/realms`, `/realms/<t>/users` return usernames, subjects, tenants, and **roles** to any
  reachable caller (debt **B6**). Whether the *client-facing* handle-resolution path is gated to registered
  clients, minimal, and rate-limited/anti-enumeration is **(to confirm)** — but the adjacent disclosure
  surface (B6) shows the invariant is not held platform-wide.
- **Refs:** debt **B6** (directory disclosure), A47 (demo client); ACCOUNT A2 (handle). Registered-only +
  minimal + anti-enumeration **PLANNED/(to confirm)**.

### C6 — Public versioned protocol; never /bridge/*; SDK is one implementation
Clients speak a **public, versioned protocol** — **never the internal `/bridge/*` surface**. The **SDK is one
implementation** of that protocol, not the protocol itself.
- **Status: PLANNED / VIOLATED.** There is **no stable public versioned client protocol** distinct from the
  host's internal surfaces today — clients reach the platform via `/embed/*` and the app-host `/bridge/*`
  proxies, and the bridge family is inconsistently gated and token-role front-gated (debt A23). The SDK
  (ADR-0112/0117) is effectively the contract. A public, versioned, `/bridge`-free protocol is **PLANNED**.
- **Refs:** debt A23 (bridge front-gates), A27 (`--no-verify-cert` internal), B1; ADR-0112, ADR-0117. Define
  the versioned public protocol; keep `/bridge/*` internal. PLANNED.

---

## Summary of status

| Rule | Topic | Status | Key debt / refs |
|------|-------|--------|-----------------|
| C1 | Registered clients, recorded scopes | PARTIAL | A47, A48; ADR-0112/0117 |
| C2 | Consent-bounded within registered scope | **VIOLATED (fixes B12)** | **B12**; ADR-0125; F10/F13 |
| C3 | Short-lived app-addressed tokens + consent ref | PARTIAL/TO CONFIRM | A33, B1; F1/F9 |
| C4 | Operations (find/resolve/verify/connect/discover/present/request/track) | PARTIAL | ADR-0112/0117/0067/0049 |
| C5 | Minimal handle resolution; registered-only; anti-enum | VIOLATED/TO CONFIRM | **B6**, A47 |
| C6 | Public versioned protocol; never /bridge/*; SDK=one impl | PLANNED/VIOLATED | A23, A27, B1; ADR-0112/0117 |

**Headline:** the governing fix is **C2 → debt B12** (bind client scope to registered client ∩ consent); the
exposure to watch is **C5 → debt B6** (enumerable identity directory); and **C6** needs a public versioned
protocol so clients stop depending on internal `/bridge/*`.

# CLIENT-v0.1 — Client apps, tokens, and the public protocol

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**, the conformance-derived rule × environment matrix (`conformance/run.py --matrix` → `conformance/build_matrix.py`; design: [STATUS-MATRIX-DESIGN.md](STATUS-MATRIX-DESIGN.md)). The inline **Status:** lines below are kept for prose and rationale and may lag; the matrix is authoritative for covered rules (uncovered rules show **NO TEST** there, not an implied status).

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (FND-1 tokens-carry-identity-only, FND-9 audience-bound tokens, FND-10
least-privilege, FND-13 consent), [[REGISTRY-v0.1]], [[DECISION-v0.1]] (DEC-1 decision records), [[ACCOUNT-v0.1]]
(ACC-5 provider connections, ACC-7 consent), [[NETWORK-v0.1]] (NET-10/NET-11/NET-12 offerings, exchange, directory).
Assumed, not restated. **Debt references** are to `../consolidation/DEBT-REGISTER.md`. *(to confirm)* = not
traced this pass. **Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

A **client** is an application (first- or third-party) that acts through the public protocol **on behalf of a
person** (and must therefore obey FOUNDATIONS FND-17 acting-on-behalf), never with ambient authority.

---

## Client rules

### CLI-1 — Registered clients with recorded scopes
A client is a **registered record** (`platform.app_client`) with **recorded scopes** — the maximum set of
things it may ever ask for. An unregistered caller is not a client.
- **Status: PARTIAL.** Governed `platform.app_client` registration exists (ADR-0112 participant-embed; the
  client-SDK path of ADR-0117). But a transitional **env/default allow-list + a seeded `demo-embed` client**
  remain (debt DEBT-A47), and the `same-origin-demo` redirect bypasses the exact-URI check (debt DEBT-A48) — so
  "registered clients only" is not yet exclusive.
- **Refs:** ADR-0112, ADR-0117; debt DEBT-A47, DEBT-A48. Governed-clients-only is the fix (S1b).

### CLI-2 — Consent-bounded, within registered scopes (fixes DEBT-B12)
An app gets **only what the person consents to**, and **only within its registered scopes** (CLI-1). The
effective grant is the **intersection** of (registered scope) ∩ (person's consent). **This is the fix for
debt DEBT-B12.**
- **Status: VIOLATED (fix target).** Today embed `/embed/authorize` takes **`scope` from the query string**
  and the consent is written **`service:"*"`** regardless of the client's registered scopes (debt **DEBT-B12**) —
  an app registered for `profile` can obtain a `service:invoke` consent. Neither the registered-scope ceiling
  nor the consent intersection is enforced.
- **Refs:** debt **DEBT-B12**; ADR-0125 (consent), ADR-0112; FND-10 (least privilege), FND-13. Bind requested scope ≤
  registered scope ∧ ≤ recorded consent. PLANNED fix.

### CLI-3 — Short-lived, app-addressed tokens carrying identity + consent reference
Client tokens are **short-lived**, **addressed to the app** (audience-bound, FND-9), carry **identity only**
(FND-1), and reference the **consent** they act under.
- **Status: PARTIAL / TO CONFIRM.** Tokens are short-lived (1h) and audience-bound exists as the home-issuer
  pattern (FND-9); the embed flow uses redirect OIDC + PKCE (ADR-0112). But **no durable client/service
  credential** underlies renewal (debt DEBT-A33), and whether the token **carries a consent reference** (vs.
  consent resolved separately) is **(to confirm) / PLANNED**. Identity-only holds in principle but downstream
  still reads token roles (debt DEBT-B1).
- **Refs:** FND-1, FND-9; debt DEBT-A33 (1h token, no durable cred), DEBT-B1; ADR-0112. Consent-reference-in-token **(to
  confirm)/PLANNED**.

### CLI-4 — Operations
The client protocol offers: **find/create account**, **resolve handle**, **verify identity**, **connect
accounts and wallet**, **discover offerings**, **check eligibility**, **present** (a credential), **request**
(a service), and **track** (status).
- **Status: PARTIAL.** A citizen-auth client surface is live (ADR-0112 S1: redirect OIDC+PKCE, `/embed/demo`,
  `/embed/request`); offerings discovery + eligibility exist via the service directory (NETWORK NET-10/NET-12,
  ADR-0067); wallet present/verify via ADR-0049. **find/create account, resolve handle, connect accounts,
  track** as first-class protocol operations are **(to confirm)** / partially present.
- **Refs:** ADR-0112, ADR-0117 (client SDK), ADR-0067 (offerings/eligibility/track), ADR-0049 (present);
  ACCOUNT ACC-1–ACC-6. Full operation set **(to confirm)**.

### CLI-5 — Minimal handle resolution; registered clients only; anti-enumeration
Handle resolution returns the **minimum** needed, is available to **registered clients only** (CLI-1), and is
**anti-enumeration** (no bulk/scan discovery of accounts).
- **Status: VIOLATED / TO CONFIRM.** The sibling identity directory is **unauthenticated and enumerable** —
  `GET /users`, `/realms`, `/realms/<t>/users` return usernames, subjects, tenants, and **roles** to any
  reachable caller (debt **DEBT-B6**). Whether the *client-facing* handle-resolution path is gated to registered
  clients, minimal, and rate-limited/anti-enumeration is **(to confirm)** — but the adjacent disclosure
  surface (DEBT-B6) shows the invariant is not held platform-wide.
- **Refs:** debt **DEBT-B6** (directory disclosure), DEBT-A47 (demo client); ACCOUNT ACC-2 (handle). Registered-only +
  minimal + anti-enumeration **PLANNED/(to confirm)**.

### CLI-6 — Public versioned protocol; never /bridge/*; SDK is one implementation
Clients speak a **public, versioned protocol** — **never the internal `/bridge/*` surface**. The **SDK is one
implementation** of that protocol, not the protocol itself.
- **Status: PLANNED / VIOLATED.** There is **no stable public versioned client protocol** distinct from the
  host's internal surfaces today — clients reach the platform via `/embed/*` and the app-host `/bridge/*`
  proxies, and the bridge family is inconsistently gated and token-role front-gated (debt DEBT-A23). The SDK
  (ADR-0112/0117) is effectively the contract. A public, versioned, `/bridge`-free protocol is **PLANNED**.
- **Refs:** debt DEBT-A23 (bridge front-gates), DEBT-A27 (`--no-verify-cert` internal), DEBT-B1; ADR-0112, ADR-0117. Define
  the versioned public protocol; keep `/bridge/*` internal. PLANNED.

---

## Summary of status

| Rule | Topic | Status | Key debt / refs |
|------|-------|--------|-----------------|
| CLI-1 | Registered clients, recorded scopes | PARTIAL | DEBT-A47, DEBT-A48; ADR-0112/0117 |
| CLI-2 | Consent-bounded within registered scope | **VIOLATED (fixes DEBT-B12)** | **DEBT-B12**; ADR-0125; FND-10/FND-13 |
| CLI-3 | Short-lived app-addressed tokens + consent ref | PARTIAL/TO CONFIRM | DEBT-A33, DEBT-B1; FND-1/FND-9 |
| CLI-4 | Operations (find/resolve/verify/connect/discover/present/request/track) | PARTIAL | ADR-0112/0117/0067/0049 |
| CLI-5 | Minimal handle resolution; registered-only; anti-enum | VIOLATED/TO CONFIRM | **DEBT-B6**, DEBT-A47 |
| CLI-6 | Public versioned protocol; never /bridge/*; SDK=one impl | PLANNED/VIOLATED | DEBT-A23, DEBT-A27, DEBT-B1; ADR-0112/0117 |

**Headline:** the governing fix is **CLI-2 → debt DEBT-B12** (bind client scope to registered client ∩ consent); the
exposure to watch is **CLI-5 → debt DEBT-B6** (enumerable identity directory); and **CLI-6** needs a public versioned
protocol so clients stop depending on internal `/bridge/*`.

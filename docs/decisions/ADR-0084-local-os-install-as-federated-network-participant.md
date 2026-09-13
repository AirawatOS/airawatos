# ADR-0084 — Local OS install as a federated participant of the shared Network

**Status:** Proposed
**Relates to:** ADR-0020 (OS / Network split — network authority is its own service+realm), ADR-0039 (federated
identity — tenant login = network citizenship), ADR-0068 (auth methods — pluggable IdP + per-issuer JWKS), ADR-0038
(spec governance — propose→approve→sign by the standards body), ADR-0016 (Store / certification / signing), INT-0004
(developer tenant), the network join→provision flow, and ADR-0083 (Studio Git integration — whose S1 local-first test
is what surfaced this).

## Context

AirawatOS is split (ADR-0020) into a **Network authority** (governance, certification, the participant directory,
per-tenant steward signing keys) and an **OS plane** (kernel/registry, identity, app-host) that runs a tenant's data
and apps. On EC2 today both halves run in one compose, so the split is logical, not physical — and every developer who
wants to work "locally" has only ever had a *partial* local stack (postgres + network + kernel), with no identity or
app-host, and their own **separate** network authority if they ran one at all.

That is the wrong shape. If each developer or operator runs their **own** network, they are on their own island: schemas
they govern, components they certify, and participants they know are invisible to everyone else. The whole value of a
Network — a shared, signed standards body and directory — evaporates.

The right shape follows directly from ADR-0020 + the federation north-star: **there is ONE Network (shared, on EC2), and
many OS installs — local or hosted — that are all participants of it.** A developer spins up an OS plane on their laptop;
an operator stands one up in their datacentre; both **point at the same Network** for governance, certification,
directory, and steward-signed publishing. Their code and tenant data stay local and private; the *governed vocabulary
and certified catalog they contribute to* are shared.

Two facts make this buildable today (verified):
- The EC2 Network API is **publicly reachable** — nginx routes `/network/` → `network:8090` (`/network/v1/health`,
  `/network/v1/participants` return 200).
- The Network authenticates callers by **verifying their bearer token against `IDENTITY_JWKS`** (`authn.verify(tok,
  IDENTITY_JWKS)`) — the ADR-0068 per-issuer JWKS seam — and it **signs approved schemas with its own per-tenant Vault
  steward key** (`steward-<tenant>`). So a caller only needs a *trusted-issuer token*; no tenant signing key ever has to
  leave the Network.

## Decision

A **local (or self-hosted) OS install is a first-class federated participant of the shared Network.** It runs its own OS
plane and **points `NETWORK_URL` at the shared Network**; the Network trusts the install's identity via **JWKS-federated
per-issuer trust** (ADR-0068). Governance stays a *propose-here, approve-and-sign-there* flow.

### What runs where

| Concern | Local OS install (per dev/operator) | Shared Network (EC2) |
|---|---|---|
| Tenant data / registry | **local** kernel + postgres | — |
| Secrets | **local** Vault | per-tenant steward keys in **its** Vault |
| User login / tokens | **local** identity (own issuer + JWKS) | trusts registered issuers |
| Apps / bridges | **local** app-host | — |
| Schema/verb governance | **proposes** to the Network | **approves + signs** (standards body) |
| Certification, directory, participant registry | — | **authoritative, shared** |

### Trust model — JWKS-federated, issuer = the TENANT (not the operator/install)

- **The issuer is the tenant, not the install.** A token's `iss` is `ds:<tenant>:identity` (e.g. `ds:kmc:identity`),
  because the *tenant* issues identities to its own users/citizens. Each tenant has its **own signing key + published
  JWKS**. One identity service may serve several tenants, but it signs each tenant's tokens as that tenant's issuer.
- **This makes tenants portable across operators — the sovereignty guarantee.** If a tenant moves from one platform
  operator (one OS install) to another, its issuer name (`ds:<tenant>:identity`) and signing key **travel with the
  tenant**. Users and citizens see **no change** — their credentials are still "issued by their tenant," independent of
  who runs the infrastructure. The operator is replaceable plumbing; the identity namespace belongs to the tenant.
  (This is why a per-*install* issuer would be wrong: it would tie citizens' identities to an operator.)
- The tenant's JWKS is **registered as a trusted issuer** on the shared Network (`IDENTITY_JWKS` becomes a *set* keyed by
  `iss` = `ds:<tenant>:identity`). The Network accepts tokens for that tenant, scoped to the roles the token carries.
- **Ties to ADR-0039** (tenant login = network citizenship): the tenant's issuer identity *is* its citizenship anchor,
  and it is the unit that moves — so citizenship survives an operator change.
- **Bounded issuer authority (governance, not just crypto).** Verifying a signature only proves *who signed*; it does
  not grant *what they may claim*. So a registered issuer is recorded with **the tenant it speaks for and the roles it
  may assert** — `ds:kmc:identity` may mint roles for `kmc`, never `platform.*` / super-admin over the network. The
  Network binds external claims to allowed actions at verify/authz time; an out-of-bounds claim is dropped, not honoured.
  (This is the hard part OIDC alone doesn't solve — see ADR-0068's hardening notes.)
- **Standard token hygiene enforced** (RFC 8725): the Network validates `iss` against the trusted set, `aud` against the
  platform audience, and an explicit **alg allowlist** (EdDSA) — it never honours a token-chosen algorithm. Signing keys
  live in Vault (never exported). Revocation + sender-constraining are tracked as hardening in ADR-0068.
- **No shared secret** between installs; each install's trust is **independently revocable** (drop its issuer from the
  Network's trusted set) — e.g. on offboarding or key compromise. This is why JWKS-federation is chosen over the
  quick "everyone shares one signing key" bootstrap.
- The **local kernel** trusts the shared Network's **published steward keys** (fetched from the Network directory) to
  verify signed schemas/certs it pulls — the mirror direction of trust.
- **Signing never leaves the Network.** The local install *proposes*; the Network *approves + signs* with the tenant's
  Network-held Vault steward key. A local install can therefore never forge a steward signature.

### Tenant & isolation invariants

- A local install operates **under a tenant the Network knows** (e.g. `airawatdeveloper`, or a tenant it obtained via
  the join→provision flow). It may propose/publish only under tenants its token is authorised for.
- Local tenant **data stays local** (in the install's kernel/registry) — it is never pushed to the Network. Only
  governed *vocabulary* (schema/verb requests) and *certified component* publications flow to the shared authority.
- Cross-install data sharing remains the existing federation/aggregator lane (ADR-0023/ADR-0075), not a side effect of
  co-locating on one Network.

## Consequences

- **Every install contributes to one commons.** A schema a developer governs locally is published to the *shared*
  catalog and immediately visible to all participants; a component they certify enters the *shared* Store. This is the
  federation north-star made concrete for the developer/operator experience.
- **Local-first development becomes real** (unblocks ADR-0083 S1): a developer runs the full OS plane on their laptop,
  authors + governs against the shared Network, and tests end-to-end without touching production tenant data.
- **The shared Network's trust surface grows** — it now trusts N issuers. Mitigated by: per-issuer registration + audit,
  independent revocation, tenant+role scoping on every token, and signing staying Network-side.
- **A shared-prod change is required to admit each new install** — registering its issuer JWKS on the Network. This is a
  deliberate, admin-gated act (not self-serve), matching how join→provision already gates participation.

## Rollout (slices)

- **S1 — Per-tenant issuer + Network multi-issuer trust.** (a) Make the reference identity issue as **`ds:<tenant>:identity`
  with a per-tenant signing key** (today it hardcodes `iss: ds:airawat:identity` for every tenant — the collision this
  ADR's bring-up exposed). (b) Add per-issuer JWKS support to the Network's token verification (accept a *set* of trusted
  issuers keyed by `iss`; today it verifies against a single JWKS). (c) Register the tenant's issuer + JWKS on the
  Network. Verify a locally-minted `ds:airawatdeveloper:identity` token is accepted by `/network/v1/*`.
- **S2 — Full local OS plane.** Extend the local compose to postgres + vault + kernel + identity + app-host, built from
  local source, `NETWORK_URL` → `https://airos.airawat.org/network`, local kernel trusting the Network's published
  steward keys. Bring it up; prove propose→(Network)approve+sign end-to-end (the ADR-0083 `dev.git_binding` govern run is
  the first real exercise).
- **S3 — Self-serve-ish onboarding.** A documented `install.sh` / compose profile any developer or operator can run to
  stand up an OS plane bound to the shared Network, plus an admin path on the Network to register/revoke their issuer.
- **S4 — Operator installs.** The same, hardened for a hosted operator (their own domain/TLS, backups), still federated
  to the one Network.

## Open questions

- Issuer registry storage on the Network: env-configured set vs a governed `network.trusted_issuer` record with an admin
  UI (prefer the governed record by S3).
- Key rotation for a local issuer's JWKS (JWKS URL vs pinned keys), and how the Network refreshes it.
- Whether a purely local dev loop (no network reachability) needs a "detached" mode that later reconciles — likely defer;
  the offline story is ADR-0082's concern, not this one.

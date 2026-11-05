# ADR-0127 — One authority model for services AND data

**Status:** Accepted · **Date:** 2026-11-05
**Relates to:** FOUNDATIONS §3 (authority model), NETWORK N9 (capabilities), REGISTRY R5/R6 (read/write
authority), DECISION D10 (recording depth), ACCOUNT A7 (consent), ADR-0125 (consent), per-object sharing
(ADR-0103), data-exchange (ADR-0088 governed bridge). Resolves debt **A18** (two grant models).

## Context

Authority is represented two ways today (debt A18): services use **CapabilityGrants** (`service.provide` /
`service.call`, issued by `grant.steward`, NETWORK N9), while data access rides a **separate `access_grant`
record** plus the legacy `role_grant`/`role_assignment` path; a CapabilityGrant data model exists but is
**shadow-only**. NETWORK N9 explicitly deferred "data capabilities" to this ADR. Two authority
representations means two code paths, two audit stories, and a standing risk that one drifts from the other.

## Decision

**One authority model for everything.**

1. **Data capabilities are CapabilityGrants.** A grant such as *read records of schema `X`* or *write records
   of schema `X`*, **scoped as needed** (tenant, subset, time), is the same kind of object as a service
   capability grant — same catalog, same `grant.steward` issuance, same version-pinning and no-wildcards
   (N9), same inactive-while-not-a-member rule.
2. **Personal data needs two keys.** Access to a **specific person's** data requires **both** the holder's
   **CapabilityGrant** **and** **that person's consent** — the *two-key rule* (FOUNDATIONS §3). Neither alone
   suffices for personal data.
3. **Non-personal data needs the grant only.** No consent key is required where no person is the subject.
4. **`access_grant` becomes a derived enforcement artefact.** The Kernel no longer treats `access_grant` as a
   separate permission that someone issues. It is an **internal artefact the Kernel derives from (grant +
   consent)** at enforcement time — the materialised answer to "does this caller, right now, hold the grant
   and (for personal data) the subject's consent?". Authority is the grant and the consent; `access_grant` is
   their computed consequence.

## Migration

- **Shadow comparison (dual-run).** For every existing `access_grant` flow — **cross-tenant data-sharing**
  (ADR-0085) and **embed consent** (ADR-0112) — the Kernel **derives** the access decision from (grant +
  consent) in parallel with the legacy `access_grant`, logs **divergences**, and does **not** change the
  live answer until the divergence gate is clean (the same discipline that gated the CapabilityGrant service
  cutover, A18).
- **Cutover / removal condition:** flip to the derived decision once shadow divergence is zero; **A18 is
  removed when no `access_grant` is created except as a derived artefact** (nothing issues one directly).

## Performance

- **Consent checks are cached** (short TTL, invalidated on consent change) so a personal read is not a second
  synchronous round-trip on every call.
- **DECISION D10** governs recording depth: a **personal-data read records a full decision record**; bulk
  non-personal reads may aggregate. Caching never skips the record — it skips the recompute, not the audit.

## Consequences

- **One grammar, one audit.** Services and data share the capability catalog, the steward issuance path, the
  version-pinning and membership rules — and one place to reason about "who may do what".
- **The two-key rule is explicit** (FOUNDATIONS §3): personal data always needs grant + consent; non-personal
  needs grant only. OFFERINGS O11 (purpose-matched consent) and POLICY PL2 (facts) build on it.
- **NETWORK N9** extends to data capabilities per this ADR (its "data capabilities pending the grant-model
  ADR" is now resolved).
- Until cutover, both representations coexist in shadow (A18 stays open, now with this ADR as its resolution
  path).

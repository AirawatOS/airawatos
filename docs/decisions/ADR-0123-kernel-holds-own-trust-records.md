# ADR-0123 — The Kernel holds its own trust records; no Kernel→Network calls for authorization inputs

**Status:** Accepted
**Date:** 2026-11-03
**Relates to:** [[FOUNDATIONS-v0.1]] F7; [[ADR-0119]] (Trust Network Platform); debt **B9**; ADR-0055
(layered reference architecture); ADR-0094 (component stewardship separation).

## Context
Today the Kernel reaches **upward** to the Network at authorization time for the inputs of its own
decisions — the federation authority public key, schema definitions, CapabilityGrants, and tenant/dev
classification (debt **B9**: `kernel/api/app.py:1780,842,1923,1816`, `authn.py:103`). This makes the
Kernel's zero-trust gate depend on a live call to a higher layer; a Network outage, a slow response, or a
compromised Network response can degrade or distort every Kernel authorization. It also contradicts the
layering intent that the Kernel is the self-contained enforcement point.

## Decision
**The Kernel holds its own trust records locally and decides authorization from local state only. The
Network governs those records by writing them into the Kernel registry through the ordinary governed
write path. The Kernel makes no synchronous call to the Network to obtain an authorization input.**

- **Trust records the Kernel holds (as governed registry objects):** (a) **authority public keys / trusted
  issuers** (the JWKS/keys it verifies tokens and steward signatures against); (b) **schema definitions**
  it validates writes against; (c) **grants** (`governance.capability_grant`, `governance.role_assignment`,
  `access.grant`, steward grants); (d) **tenant records + classification** (tenant existence, `environment`,
  steward). All are read from the Kernel's own registry at decision time.
- **The Network governs by governed writes, not by being called:** the Network (the standards/authority
  body) proposes/approves these records and **writes them into the Kernel registry** under the appropriate
  steward id — the same bitemporal, attributed, audited write path every other record uses. Governance is a
  *write into the Kernel*, never a *read the Kernel performs against the Network*.
- **Direction rule:** the dependency arrow points **down** (Network → writes → Kernel) or **sideways via
  governed records**, never **up** (Kernel → calls → Network) for an authorization input. Non-authorization
  operational calls (e.g. publishing an event the Network subscribes to) are out of scope.
- The Kernel may still *cache nothing it cannot re-derive from its own registry*; a cold Kernel with its
  registry intact can authorize with no Network reachable.

## Consequences
- The Kernel is self-contained and fail-closed on its own state (F7, F8): no Network call in the hot path,
  no upward coupling, no "standalone mode self-signs with no authority key" fallback.
  **Decided; debt B9 (and A13) remains OPEN until implemented.** Implementing work: *Kernel-local trust-records
  migration* — move each Network-call authorization input (trusted-issuer keys, schema catalog mirror, grant
  resolution, tenant/dev classification) to a locally-held governed record maintained by a Network-driven
  governed write, then delete the hot-path `NETWORK_URL` calls and the standalone self-sign fallback.
- The Network's authority is expressed as **recorded state in the Kernel**, consistent with F2 (authority
  from recorded state) — the Network writes the grants/keys/schemas; the Kernel reads them locally.
- Migration (separate slice, not this ADR): move each Network-call input to a locally-held record +
  a Network-driven governed write that maintains it (trusted-issuer keys, schema catalog mirror, grant
  resolution, tenant classification). Until migrated, the existing calls remain and are tracked as B9.
- Testability improves: the Kernel can be tested with no Network (today `_steward_authorizes` is untested
  because tests run with `NETWORK_URL` unset and it always denies).

## Alternatives rejected
- *Keep calling the Network, add caching/circuit-breakers* — still an upward authorization dependency; a
  stale or poisoned cache still distorts decisions; does not satisfy F7.
- *Move all authority into the Network and have the Kernel delegate every decision* — inverts the
  enforcement point and makes the Network a hot-path single point of failure; contradicts the Kernel-as-gate
  design.

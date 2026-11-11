# ADR-0128 — Networks are federated

**Status:** Accepted
**Date:** 2026-11-06
**Relates to:** [[ADR-0116]] (Participant ≠ Tenant), [[ADR-0117]] (credential/services network),
[[ADR-0118]]/[[ADR-0119]] (Trusted Network Platform, four planes), [[ADR-0123]] (Kernel holds its own trust
records), [[FOUNDATIONS-v0.1]] F2/F4/F15. Specs: NETWORK-v0.1 (N2/N5/N6), PARTICIPANT-v0.1 (PP1/PP11),
PLATFORM-v0.1, and the new FEDERATION-v0.1.

## Context

Until now a "Network" has read as something an installation *has* (one local `net:<ULID>` minted at install,
members implicitly the installation's own tenants). That conflates three separable things: who **runs servers**
(the operator), who **governs a Network** (its host tenant), and who **belongs** to a Network (its participants).
It also leaves cross-installation membership undefined, and it quietly re-introduced the "a member is a tenant"
reading that ADR-0116 rejected.

## Decision

**Networks are federated. A Network is governed by a tenant (its host) on some installation, and its members
may live on any installation or run their own system.**

- **Creation.** Any tenant holding **`network.creator`** on **any** AirawatOS installation may create a Network
  and becomes its **governing tenant** (the Network **host**). The Network's **registry, directory, and grant
  decisions live on that installation** — authority over the Network is the host's recorded state (F2), not a
  property of any other installation.
- **Hosting.** An installation **hosts zero or more Networks** (the ones created by its tenants) and its tenants
  **join zero or more Networks** hosted anywhere. "Which installation runs the servers" (operator) and "which
  tenant governs this Network" (host) are independent.
- **Joining = registering as a participant** in the hosting Network's registry: a **participant ID**, the
  **role(s)** sought (provider / issuer / funder / consumer channel …), **public keys**, and **conformance
  status**. A participant is **activated for a role only after it passes the conformance suite for that role**
  (PARTICIPANT PP1/PP11). Membership confers belonging, never capability (ADR-0116; NETWORK N5).
- **Three member modes.** (1) a **tenant on the same installation** as the host; (2) a **tenant on another
  AirawatOS installation**; (3) an **own system** implementing the specs via the **Participant SDK**. The
  Network treats all three uniformly — each is a registered participant with keys + conformance status.
- **The Network never creates tenants, logins, or participant systems.** It governs vocabulary, admits
  participants, and records grant/decision state. Standing up a tenant/login/node is the operator's and the
  member's job, not the Network's. **Analogy:** domain registration + a web server — the registrar (Network)
  records who may use a name and under what terms; the server (operator/installation) is run by someone, and
  visitors (participants) connect from anywhere.

## Cross-installation trust (scoped; detailed in FEDERATION-v0.1)

- Requests between installations are **signed** by the participant's **registered keys**; the hosting Network
  verifies against the keys it recorded at join.
- Each installation's **home issuer is trusted only for its own participants** (F15 issuer-scoping extended to
  the Network boundary). An installation does not trust another's issuer for anything beyond the participants
  that other installation vouches for and that are registered in the Network.
- The **hosting installation's registry + directory** are authoritative for the Network; a consuming
  installation reads the directory and verifies signatures, it does not mint the Network's authority.
- A **directory of Networks / root of trust** (how an installation discovers Networks hosted elsewhere and
  anchors trust in them) is scoped in FEDERATION-v0.1 and deferred to a later slice.

## Consequences

- NETWORK **N2** (lifecycle), **N5** (membership), **N6** (join) are rewritten to the federated model; the
  ADR-0116 **participant ≠ tenant** reading wins (N5's old "existing tenants only" is dropped — that was the
  open decision flagged in NETWORK §N5).
- PARTICIPANT **PP1/PP11**: registration + **per-role conformance before activation** becomes explicit.
- PLATFORM: **every installation is both a Network host and a participant node**; tenant **onboarding** applies
  only to **mode-1** members (same-installation tenants); the **installer may register an installation's
  tenants as participants in remote Networks**.
- Consistent with F2 (authority = recorded state on the host), F4 (Tenant ≠ Network), ADR-0123 (the Kernel/host
  holds its own records; no upward call to decide authority) and ADR-0117 (pluggable participants).

## Alternatives rejected

- *One Network per installation, members = local tenants* — the status quo; cannot express cross-installation
  membership or a tenant governing a Network while others run servers; re-breaks ADR-0116.
- *A central Network registry owned by one installation* — a single point of authority/failure; contradicts
  federation and F2 (each Network's authority is its host's recorded state).

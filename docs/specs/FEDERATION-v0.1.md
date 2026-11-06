# AirawatOS Federation v0.1 (scope draft)

**Status:** Scope draft, 2026-11-06. The cross-installation model. Builds on [[FOUNDATIONS-v0.1]] (FND-2, FND-4,
FND-15), [[NETWORK-v0.1]] (NET-1–NET-12), [[PARTICIPANT-v0.1]] (PTC-1–PTC-12), [[PLATFORM-v0.1]] (every installation is a
host + a node). Decided by [[ADR-0128]] (Networks are federated); relates to ADR-0116/0117/0119/0123.

This spec states *what federation guarantees*; several rules are **PLANNED** (the model is decided, the
cross-installation wiring is a later slice). Status key as elsewhere: IN PLACE / PARTIAL / PLANNED / TO CONFIRM.

## Terms

- **Installation** — a running AirawatOS deployment (one operator, one home issuer, its own registry + Vault).
  It **hosts** zero or more Networks and runs zero or more **participant nodes** (its tenants, or its own
  systems, acting in remote Networks).
- **Network host (governing tenant)** — the tenant that created a Network (held `network.creator`) and governs
  it. The Network's registry, directory and grant/decision records live on the host's installation.
- **Participant** — a member of a Network (ADR-0116, tenant-free): a registered `participant ID` with role(s),
  public keys and conformance status in the hosting Network's registry.
- **Member mode** — how a participant is realised: (1) a tenant on the **host's installation**; (2) a tenant on
  **another installation**; (3) an **own system** via the Participant SDK.
- **Home issuer** — an installation's own identity service; trusted (FND-15) **only for that installation's own
  participants**.

## Rules

### FED1 — A Network is hosted by one governing tenant
A Network has exactly one governing tenant (its host). The host's installation holds the Network's authoritative
registry, directory and grant/decision records; authority over the Network is the host's recorded state (FND-2),
never derived by a consuming installation. **Status: PARTIAL** — single-installation Networks exist (ADR-0119);
the "host is a specific tenant that may differ from the operator" framing is the new part.

### FED2 — Creation requires `network.creator`; never creates tenants/logins
Any tenant holding `network.creator` on any installation may create a Network and becomes its host. Creating a
Network **never** creates tenants, logins or participant systems (ADR-0128). **Status: PARTIAL** — network
creation exists; the `network.creator`-anywhere + host-tenant binding is the extension.

### FED3 — Joining is participant registration in the host's registry
A member joins by registering in the hosting Network's registry: `participant ID`, role(s), **public keys**,
and **conformance status**. Registration is belonging, not capability (NET-5/ADR-0116). **Status: PARTIAL**
(`network.participation` request/decide is live for mode-1; cross-installation registration is PLANNED).

### FED4 — Per-role conformance before activation
A participant is **activated for a role only after passing the conformance suite for that role** (provider,
issuer, funder, consumer channel). Conformance status is recorded on the participant record and gating is on it
(PARTICIPANT PTC-11). **Status: PLANNED** — the per-role suites + the activation gate are to be built.

### FED5 — Cross-installation requests are signed by registered keys
A request from a participant on one installation to a Network hosted on another is **signed** by the
participant's registered keys; the host verifies against the keys recorded at join. No unsigned cross-install
authority. **Status: PLANNED** (signed-relay primitives exist for mail/federation envelopes; generalising to
Network requests is the work).

### FED6 — Home issuer is trusted only for its own participants
Each installation's home issuer is trusted (FND-15) **only for its own participants**. A host does not accept
another installation's issuer as authority for anything beyond the participants that installation vouches for
**and** that are registered in the Network. Authority never widens by crossing an installation boundary.
**Status: PLANNED** — per-Network issuer scoping (beyond today's per-tenant binding, NET-7) is to be built.

### FED7 — The hosting installation's directory is authoritative
A consuming installation **reads** the host's Network directory (participants, roles, keys, conformance) and
**verifies** signatures against it; it does not mint or cache the Network's authority as its own. Reads are
fail-closed on an unreachable/unverifiable directory (FND-8). **Status: PLANNED**.

### FED8 — Directory of Networks / root of trust (DEFERRED)
How an installation **discovers** Networks hosted elsewhere and **anchors trust** in them (a directory of
Networks, and the root-of-trust that lets installation A trust a Network hosted by installation B) is **scoped
here and deferred** to a later slice. Open questions: is there a well-known Network-directory service; is trust
anchored per-Network (the host's authority key) or via a higher root; how is key rotation + revocation
propagated. **Status: PLANNED / TO CONFIRM.**

## Tally
8 rules — 0 IN PLACE, 2 PARTIAL (FED1, FED2; FED3 part), 6 PLANNED (FED3-cross-install, FED4, FED5, FED6, FED7,
FED8). The model is decided (ADR-0128); the cross-installation wiring is the backlog.

## Relation to the other specs
- NETWORK NET-2/NET-5/NET-6 state the Network-side lifecycle/membership/join under this model.
- PARTICIPANT PTC-1/PTC-11 state the participant-side registration + per-role conformance.
- PLATFORM states that every installation is both a host and a node, and that the installer can register an
  installation's tenants as participants in remote Networks.

# ADR-0130 — Trusted core, gateways and components

**Status:** Proposed · **Date:** 2026-11-08
**Grounded in:** [PROVIDER-INVENTORY](../consolidation/PROVIDER-INVENTORY.md) (every capability that reaches outside
the platform, with its owner, credentials, chooser, pre-call checks and debt — renumbered ids **DEBT-B65–B68**).
Where this ADR's brief contradicted the inventory, the inventory is followed and the difference is flagged
(§ Inventory reconciliation).
**Builds on:** ADR-0030 (no secrets in components), ADR-0050 (decision/workflow execution seam), ADR-0052
(signing), ADR-0063 (governed interfaces), ADR-0068 (pluggable IdP), ADR-0074 (operator-configurable platform
services), ADR-0089 (event/message spine), ADR-0105 (scaling tiers), ADR-0116 (participant ≠ tenant), ADR-0124
(service identities), ADR-0126 (field-level protection), ADR-0127 (one authority model), ADR-0128 (federated
Networks), ADR-0129 (no platform provider catalogue), ADR-0131 (root of trust at install).
**Affects:** PLATFORM (PLT-16–PLT-21), COMPONENT (CMP-5, CMP-6, CMP-7, CMP-11), FOUNDATIONS (FND-8, FND-10),
DECISION (DEC-1), REGISTRY (REG-8, REG-14, REG-18), ARCHITECTURE-FLOWS (door D6), new spec
[GATEWAY-v0.1](../specs/GATEWAY-v0.1.md) (GTW).

---

## Context

The platform grew by accretion: every capability landed in whichever service needed it first. Transactional
email is sent from the Network authority (`network/api.py` `_send_email`); the Telegram webhook and the SMS intake
live in the App Host; model-provider wires live in the model-gateway; the workflow engine and the document
renderer run as platform services or in-process modules; data-source drivers are components but some open their
own sockets (B65–B67); app bundles load maps straight from third-party CDNs in the viewer's browser (B68).

Two consequences follow. First, the **trusted computing base is larger than it needs to be**: code that holds no
authority (a markdown renderer, an SES client, a workflow interpreter) runs with the privileges of the service it
sits in, so every change to it is a change to the TCB. Second, **outside access has no single shape**: some
providers are reached through a gateway with a gate and metering, some through the broker's egress capability,
some directly — and none through a uniform place where grant, consent, cost and audit are enforced.

This ADR draws the line once: what belongs in the core, what is a gateway, what is a component, and what a
provider adapter is.

## Decision

### 1. The test for what belongs in the core

A part of the platform belongs in the **trusted core** if, and only if, at least one holds:

- **(a) It holds authority, facts or keys** — recorded grants and roles, the registry of record, signing and
  encryption keys, principals and credentials.
- **(b) It enforces the rules** — the decision function, the ingress gates, the broker's capability checks, the
  edge's route separation.
- **(c) It is a door to the outside world that needs one platform-wide policy** — a place where every tenant's
  traffic to or from a class of outside party must pass the same grant / consent / limit / audit checks.

**Everything else is a component**: installed, signed, confined, granted only what it declares, replaceable.

Corollaries:
- *Widely used* is not a reason to be core (a renderer every app uses is still a component).
- *Shipped by the platform* is not a reason to be core (system components are platform-shipped but installed and
  confined like any other).
- A component may be **trusted to do a job** by a grant; that does not make it part of the TCB — the core still
  checks every call it makes.
- A door (c) is core; the **provider-specific code behind it is not** (§6, §8).

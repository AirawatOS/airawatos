# Decisions (ADRs) — AirawatOS

Architecture Decision Records **authored natively for AirawatOS** — the *why* behind the shape of the
system. Each records a decision, its context, and its consequences at a point in time. Superseded and
historical records are kept, not deleted: the history is part of the system's reconstructability.

This is the **go-forward decision record**. It lives alongside the reference implementation
(`Airawat/`), not in the legacy AirOS repo. New ADRs are authored here.

## AirawatOS-native ADRs

| # | Decision | Status |
|---|---|---|
| 0062 | [Component invocation, lifecycle & triggering](ADR-0062-component-invocation-lifecycle-and-triggering.md) | Proposed |
| 0063 | [Govern the control-plane verbs](ADR-0063-govern-the-control-plane-verbs.md) | Proposed |
| 0064 | [Solution-driven activation (Packs)](ADR-0064-solution-driven-activation.md) | Proposed |
| 0065 | [Airawat Stack ontology (5 layers · 4 atoms · 3 templates)](ADR-0065-airawat-stack-ontology.md) | Proposed · supersedes 0055 |
| 0066 | [National guidelines & rules as shared network assets](ADR-0066-shared-network-assets.md) | Proposed |
| 0067 | [Civic service federation: network service directory + interaction protocol](ADR-0067-civic-service-federation.md) | Proposed |
| 0068 | [Pluggable identity providers + auth-method assurance tiers](ADR-0068-pluggable-identity-and-assurance-tiers.md) | Proposed |
| 0069 | [The welfare spine: a goal-anchored objective function over the city](ADR-0069-welfare-spine-the-objective-function.md) | Proposed |
| 0070 | [Uncertainty propagation & the publishability gate](ADR-0070-uncertainty-and-publishability.md) | Proposed |
| 0071 | [From recommendation to funded project](ADR-0071-recommendation-to-funded-project.md) | Proposed |
| 0072 | [Federated program funding: the information-gates-money loop](ADR-0072-federated-program-funding.md) | Proposed |
| 0073 | [Air Intelligence: a reproducible PM2.5 nowcast/forecast on the H3 baseline](ADR-0073-air-intelligence-pm25-modelling.md) | Proposed |
| 0074 | [Operator-configurable platform services](ADR-0074-operator-configurable-platform-services.md) | Proposed |
| 0075 | [Solutions contribute into shared apps; Setup is unified](ADR-0075-solution-contributions-and-unified-setup.md) | Proposed |
| 0076 | [The Solution anatomy, and process-first, form-anchored authoring](ADR-0076-solution-anatomy-and-document-first-authoring.md) | Proposed |
| 0077 | [The media plane: the broker is the only door for *authority*](ADR-0077-camera-media-plane.md) | Proposed |
| 0082 | [Offline-first capture & edge trust (connectivity tiers)](ADR-0082-offline-first-capture-and-edge-trust.md) | Proposed |

## Migration backlog — legacy AirOS ADRs to rewrite for AirawatOS

ADRs **0001–0061** were authored for the earlier **AirOS** system and live in the AirOS repo
(`AirOS/decisions/`). Many decisions still hold, but the framing, vocabulary, and boundaries are
AirOS-era and must be **revisited and rewritten for AirawatOS**, one at a time. Numbering is continued
unbroken (0062+) so cross-references stay stable as the back-catalog is migrated in under its own numbers.

Rewrite priority is driven by what the current build depends on. The load-bearing ones for the
invocation/lifecycle/trigger work (ADR-0062) are:

- **ADR-0030** — Component SDK + broker (the only I/O surface)
- **ADR-0045** — Solution declaration (roles, interactions, tasks, workflows, triggers, decisions)
- **ADR-0050** — Solution execution engine (runs declarations; single writer of case state)
- **ADR-0058** — Interaction contracts (`platform.runtime_invoke` as a first-class verb)
- **ADR-0052** — Authenticated & attributed registry writes
- **ADR-0056** — Decided change-request pattern
- **ADR-0016** — Marketplace certification & signed provenance
- **ADR-0060** — L0–L4 representation ladder & City Baseline
- **ADR-0067** — Civic service federation (network service directory + Beckn-adapted interaction protocol)

Loose decision notes already in `Airawat/network/decisions/` (onboarding-composition,
runtimes-are-certified-components, operators-and-tenant-portability) are to be **folded into this numbered
series** as they are formalized.

> When migrating a legacy ADR: read the AirOS original, rewrite it in AirawatOS terms, place it here under
> its **same number**, and mark the AirOS original *Superseded by AirawatOS ADR-NNNN*.

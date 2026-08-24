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

Loose decision notes already in `Airawat/network/decisions/` (onboarding-composition,
runtimes-are-certified-components, operators-and-tenant-portability) are to be **folded into this numbered
series** as they are formalized.

> When migrating a legacy ADR: read the AirOS original, rewrite it in AirawatOS terms, place it here under
> its **same number**, and mark the AirOS original *Superseded by AirawatOS ADR-NNNN*.

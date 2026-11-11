# ADR-0069 — The welfare spine: a goal-anchored objective function over the city

- **Status:** Proposed (2026-09-03)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0053 (data-model taxonomy — space/geo/domains, entity & cell-measure patterns;
  this ADR adds a *welfare* lens over that taxonomy), ADR-0060 (L0–L4 representation ladder —
  Observation→Feature→Cell→Intelligence→Decision; the spine is a lens *across* the ladder, not a new one),
  ADR-0046 (decision hourglass — facts+rules→decision→outcomes) and ADR-0029 (decision spine — *AI recommends,
  authority decides*): the spine's **output is a `governance.recommendation`**, so the entire back half of the
  loop is reused, not rebuilt. ADR-0041 (lineage & confidence — every derived welfare fact carries `prov` +
  `confidence`), ADR-0038 (spec governance — these nouns are proposed→approved→signed, not hand-added),
  ADR-0022 (everything-is-a-component — the deprivation/gap/prioritisation logic ships as **certified engines**),
  ADR-0015 (entity federation & links — household↔building↔connection identity reuses the link registry),
  ADR-0026 / ADR-0028 (agent RBAC + civic personas — the PII/equity-unit privacy boundary). External anchors:
  Sen's **capability approach**, the **NITI Aayog / OPHI Multidimensional Poverty Index** (deprivation as a
  composite), URDPFI Chapter 8 service norms + **MoHUA Service Level Benchmarks** (the floors). The URDPFI
  *City Ontology* draft becomes the **vertical detail** under this spine, not a parallel model.

## Context

Every schema AirawatOS governs today answers *what is there* — buildings, facilities, air quality, population
grids, flood risk, a decision loop. Reviewed against a stated goal —

> **raise the number of people living above a dignity floor across every basic capability, then keep lifting
> the whole distribution, subject to staying inside the city's environmental carrying capacity and its ability
> to pay to sustain it, weighting the worst-served most**

— the registry is thin on the exact axis the goal lives on: *service delivered → to a person → against a floor
→ weighted by who is worst-off → within an environmental and fiscal budget.* The platform is strong where a
**sensor or a satellite** produces the data and strong on the **grievance/decision loop**, but it cannot today
answer "does *this household* receive *enough* water, and are they the worst-off, and can we afford to fix it."

That objective, written literally, is:

```
maximize  Σ_units Σ_capabilities  weight(unit) × improvement(level → floor)
subject to   Σ cost ≤ fiscal_budget ,   Σ draw ≤ environmental_budget
```

Every term in that expression is an object the registry is missing. Naming them — capability-agnostically,
once — is this ADR. Pointing the spine at a first capability (sanitation, water, …) is a **later** decision;
the spine must not encode any single service.

**Two value choices are settled here, because they change the schema, not just the tuning:**

1. **Aggregation is floor-first, then prioritarian.** No one below the dignity floor on any capability while
   anyone still is (a hard constraint); above the floor, further gains are weighted toward the worst-served
   (soft optimisation). Pure utilitarian sum-maximising is rejected: it structurally abandons the
   hardest-to-serve, which is the opposite of the goal. This is why `welfare.deprivation` (the weight) is a
   first-class object and not a report.

2. **The equity unit is the household, held without PII.** "Weight by who is worst-off" is uncomputable over
   population *grids* — cell averages hide the worst-off, which is the whole point of equity. The unit is
   therefore `civic.household` (location, size, tenure, service levels, deprivation — **no personal
   identifiers**). Persons (`civic.resident`, PII) live in a separate store joined only under authorisation
   (ADR-0026/0028). This is what makes equity computable without building a surveillance graph.

## Decision

Introduce a small, capability-agnostic **welfare spine** — new governed domains `welfare` and `infra`, an
extension to `civic`, and (slice 2) `env` — that makes the objective function computable and feeds the
existing decision spine.

### The nouns (Slice 1 = 1–6, plus the derived `welfare.gap`)

| Noun | `x-kind` | Role in the objective | Essence |
|---|---|---|---|
| `welfare.capability` | entity | *what* we raise — the capability vector as governed vocabulary | id, label, `service_unit`, `floor_direction` |
| `welfare.floor` | entity | the *dignity floor* for a capability | `capability`, `threshold`, `unit`, `applies_when`{settlement_class,pop,terrain}, `legal_force`, `source`→`ref.source` |
| `civic.household` | entity | the *equity unit* (non-PII) — who is served | location (`building_ref`/`space`), `size`, `tenure`; PII persons held apart |
| `infra.service_connection` | entity | the *join* — does this unit receive a service | `capability`, `serves`, `provider`, `status`{active,none,illegal,…}, `metered` |
| `welfare.service_level` | measure | *what is actually delivered* to a unit | `subject`, `capability`, `value`, `unit`, `interval`, `method`, `prov`, `confidence` |
| `welfare.deprivation` | measure | the *equity weight* — how badly-off a unit is | `subject`, `index` 0–1, per-capability `shortfalls`, `deprived[]`, `prov` |
| `welfare.gap` | measure (derived) | floor − level, × weight, with evidence | `subject`, `capability`, `shortfall`, `weighted`, `floor_ref`, `derived_from[]`, `prov` |

### The engines (certified components — ADR-0022, writer taxonomy)

- **deprivation-engine** — all `welfare.service_level` for a unit → `welfare.deprivation` (the weight).
- **gap-engine** — `welfare.floor` × `welfare.service_level` × `welfare.deprivation` → `welfare.gap`.
- **prioritisation-engine** (slice 2) — ranks `welfare.gap` within `finance.budget` + `env.resource_budget`
  → emits **`governance.recommendation`**.

`welfare.gap` is **derived, never a primary fact**: it is the gap-engine's output, cached with `prov` +
`derived_from`, recomputed when a floor or a level changes. "Change the norm, every gap in the city recomputes"
falls out of P5 for free.

### Slice 2 — the two budgets (design fixed here, built next)

| Noun | Role |
|---|---|
| `env.resource_budget` | the *environmental* constraint — a stock you can overdraw: `resource`{aquifer,airshed,land,carbon}, `jurisdiction`, `capacity`, `regen_rate`, `current_draw` |
| (reuse) `finance.budget` + City Plan Console proforma | the *fiscal* constraint — what a fix costs to build and sustain |

### How it reuses what exists (this is not a parallel model)

- **On the L0–L4 ladder (ADR-0060):** `civic.household` is an L1 Feature; `welfare.service_level` and
  `welfare.deprivation` are L2/L3 Intelligence; `welfare.gap` is the L3→L4 trigger; `welfare.floor` is a
  governance-layer norm. The spine is a *welfare lens across the ladder*.
- **On the decision spine (ADR-0029/0046):** the prioritisation-engine emits `governance.recommendation`;
  everything after — `governance.decision → governance.order → platform.case/inbox` — is already live.
- **On identity (ADR-0015):** `civic.household ↔ geo.building ↔ infra.service_connection` reuses the
  **entity-link registry**; resolution assertions stay as link objects with confidence, not embedded arrays.
- **On the URDPFI City Ontology draft:** its Obligation → `welfare.floor`; Gap → `welfare.gap`; Agent →
  `civic.household`/`civic.resident`; Flow / Network / ServiceConnection → `infra.*`. Goal-anchored, not
  discarded.

## Consequences

- The platform gains the one thing it lacked: a computable answer to *"who is worst-served, across which
  capabilities, by how much, and what fix does the most good per rupee within the resource limit."*
- New governed vocabulary (`welfare`, `infra`, extend `civic`; `env` in slice 2) is a deliberate,
  semi-permanent act, correctly gated by ADR-0038 (propose→approve→sign).
- No capability is privileged in the schema; sanitation/water/housing become *configuration* (`welfare.floor`
  rows + a driver that writes `welfare.service_level`), not new code.
- **No synthetic data.** Slice-1 proof seeds `civic.household` coarsely from `geo.building_analytics`
  (people-per-building already estimated) — an honest approximation with `confidence`, refined later from
  surveys — never fabricated occupancy.

## Open questions

1. **Confidence propagation** (the sharpest): if a household→connection link is 0.6 confident, what is the
   confidence of a ward deprivation index over thousands of such links? Must be fixed before any welfare number
   is published — publishing an unqualified derived number is exactly what ADR-0041 forbids. Promoted from
   "later" to a **Slice-1 blocker for publication** (not for schema).
2. **Deprivation index method.** MPI-style equal-weighted headcount vs a floor-distance composite. Governed as
   data (a `welfare.floor`-linked method record), not hard-coded.
3. **Overlapping-jurisdiction precedence** for floors (ULB vs development authority vs cantonment) — state-
   specific; a data field on `welfare.floor.applies_when`, resolved by the gap-engine, not a global rule.
4. **Household survival across subdivision/merge** — `supersedes` lineage, mirroring the parcel pattern.

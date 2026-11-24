# ADR-0142 — Cell panel, governed indices and investment-impact analysis

**Status:** Proposed
**Date:** 2026-11-24
**Related:** ADR-0049 (signed records), ADR-0141 (the commons network: domain owners), the city layers (air quality,
heat, green cover, hydrology, roads, mobility, night lights, population, facilities).

## The problem

A city's data sits in many domains — air quality, roads, buildings, flooding, heat, transport, facilities, works and
payments — each kept on its own. Questions that matter cross them: *is the air worse where roads are denser? which
wards have the poorest access to clinics and schools? did this flyover raise land values, and can the city capture
part of that to reinvest?* Today there is no common unit to join on, no agreed way to define an index such as
quality of life, and no way to tell an association from an effect.

## Decision

1. **One unit for joining: map cell × period.** Every spatial layer is keyed by an H3 cell (resolution 9, ~0.1 km²)
   and an observation time. Data with other keys is mapped onto cells (works payments, tenders, facilities, civic
   issues). Cells map to wards through the governed `space.ward_cell`, so every result can be reported by cell, ward or
   zone — and the unit is always stated.

2. **A cell panel per period.** For each tenant and period (monthly), the platform assembles one row per cell with the
   current value of each layer — the panel every analysis starts from. Cell-level panels are kept as versioned files
   (they are large); summaries by ward are records in the registry.

3. **Indices are governed record types with a published definition.** An index definition names its components, the
   input for each, how it is normalised (for example percentile rank across the city's cells), its direction (higher
   is better or worse), its weights and its version. Results are computed per cell and per ward for each period,
   carry the definition's version, and can always be traced to their inputs. Index definitions belong to a domain
   owner (ADR-0141) — for example the urban development department for quality of life.

4. **Quality of life is an index of indices.** Starting components: health access, education access, mobility,
   environment and economic activity — each itself an index. A city may change weights or add components by
   publishing a new version; earlier results keep the version they were computed with.

5. **Analyses are components that produce evidence.** Correlation, regression and causal designs run as certified
   engines under the tenant's own grant, and produce *finding* records: the question, the unit, the number of
   observations, the method, the estimates with their uncertainty, and the caveats. Two rules hold for every finding:
   - **association is reported as association** — cells near each other are alike (spatial autocorrelation) and results
     change with the unit, so findings state both;
   - **effects need a causal design** — for an investment, compare the cells that received it with similar cells that
     did not, before and after (difference-in-differences, synthetic control).

6. **The investment loop is measured link by link.** Public investment (works paid, by place and time) → access and
   quality of life → land value (guidance values, sale prices, property-tax assessments) → value capture (betterment
   levies, premium floor area, development rights, tax revisions) → reinvestment → economic activity. Each link is a
   series by cell or ward; the links that matter for value capture use the causal designs of decision 5.

7. **People and agents read the results like any other record.** Index and finding records are ordinary registry
   records, so skills and agents (for example a city briefing) can explain a ward's index and what drives it, quoting
   the definition's version and the finding's caveats.

## First slice (staging, Janaagraha)

- A cell panel for November 2026 over the 6,575 cells mapped to wards.
- Quality of life v0: health access and education access (distance to the nearest facility), mobility (transit gap,
  walkability), environment (PM2.5, green cover, heat, flood susceptibility) and economic activity (night-light
  radiance), percentile-normalised, equal weights, population-weighted by ward.
- One finding: PM2.5 against road density, chokepoints, built-up share and green cover, by cell, with its caveats.
- A City Briefing agent and skill that read the ward index and the finding.

## Consequences

- Cross-domain questions become joins on one key instead of bespoke integrations.
- Every index is explainable and versioned; changing a weight is a governed act, not a silent edit.
- Findings carry their uncertainty, so decisions are not built on correlations dressed up as causes.

## Open questions

1. **Land value data** — connecting registration (guidance values, transactions) and property-tax assessments.
2. **Energy** — electricity consumption by feeder or meter, mapped to cells.
3. **Weights** — who sets quality-of-life weights, and whether residents are consulted.
4. **Panel retention** — how long cell-level panels are kept (they are the history causal designs need).

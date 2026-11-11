# ADR-0070 — Uncertainty propagation & the publishability gate

- **Status:** Proposed (2026-09-03)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0069 (welfare spine — this ADR resolves its open blocker OQ1: no welfare
  *number* may be published until per-record confidence can be propagated to an aggregate honestly),
  ADR-0041 (lineage & confidence — every derived fact carries `prov` + `confidence`; this ADR says *what a
  confidence means* and *how it composes*), ADR-0053 (the canonical embedded **space block** — precedent for a
  governed, embeddable value-object; `stat.estimate` follows the same pattern), ADR-0060 (L0–L4 ladder — the
  gate governs the L3→L4 boundary: an Intelligence value may not surface as a headline unless publishable),
  ADR-0029/0046 (decision spine — a decision may only cite a publishable estimate or an explicitly-provisional
  one). Standing constraint: **no synthetic data** — an unqualified derived number is a synthetic certainty and
  is forbidden. External anchors: **Wilson score interval** (proportions), **finite-population correction**,
  **Monte-Carlo error propagation**, calibration / reliability (a stated 0.6 must mean 60% correct when
  ground-truthed).

## Context

The welfare spine (ADR-0069) will compute ward- and city-level numbers — "42% of households below the water
floor", "ward deprivation index 0.38" — from thousands of per-household facts, each carrying its own
`confidence` (a household seeded from `geo.building_analytics` is ~0.6 confident it exists there; a modelled
service level is far less certain than a metered one). **How does per-record confidence become the confidence
of the aggregate?** Get this wrong and the platform becomes a confident liar — the single worst failure mode
for a civic decision system.

Two intuitive rules are both wrong, and wrong in instructive ways:

- **Multiply the confidences** → every aggregate collapses toward zero. These are not an AND-chain for a
  population statistic.
- **Average the per-record confidence** and report that → ignores the two terms that actually dominate:
  1. **Coverage.** 200 perfectly-confident records out of 5,000 households is not a confident ward figure —
     the 4,800 unobserved households *are* the uncertainty.
  2. **Correlation.** If every household was located by the *same* model with a systematic tilt, the errors do
     not cancel; the √N shrinkage that makes large samples precise **fails** under shared bias. You cannot
     average away systematic error.

So "confidence" is not one scalar to propagate with a formula. It is a set of components that combine
differently, and the honest output is an **interval plus a coverage figure**, never a bare number.

## Decision

### 1. A published derived number is a first-class `stat.estimate` fact, not a scalar

Per-record facts (`welfare.service_level`, `welfare.gap` on one household) keep their simple scalar
`confidence` — that is fine at the record grain. The estimate machinery applies **at the aggregate**: any
number a person or a decision reads (a ward/city rollup) is stored as a governed **`stat.estimate` measure**
whose `subject` is the jurisdiction/cell it summarises and whose `derived_from` is the record set it was built
from — never a naked number + `confidence`:

```
stat.estimate (measure; subject = ward|cell|city) = {
  metric,                    # what is estimated, e.g. "welfare.gap.below_floor_fraction" (reusable beyond welfare)
  value,                     # point estimate (median of the propagated distribution)
  ci_low, ci_high, ci_level, # credible interval (e.g. 90%)
  coverage,                  # n_observed / n_target  — the single most important honesty number
  n_observed, n_target,
  method_mix,                # { metered: .3, modelled: .5, imputed: .2 } — what it's made of
  model_version,             # the calibration in force when this was produced
  publishable,               # set by the gate (below)
  derived_from, prov         # the record set + lineage (ADR-0041)
}
```

This makes "no unqualified derived number" **structural**: an engine physically cannot emit an aggregate as a
bare `value` — the schema requires `coverage`, and the gate requires the interval. `stat.estimate` is a general
`stat` domain noun, reusable by tax-gap rates, coverage QA and air-quality ward means, not welfare-only.

### 2. Propagation decomposes uncertainty into four components and simulates the aggregate

For a ward metric over households *h* and capability *c*:

| Component | Source | Nature |
|---|---|---|
| existence / location | `civic.household.confidence` | is *h* real, in this ward? |
| linkage | `same_as` / entity-link confidence | is this reading actually *h*'s? |
| measurement | `welfare.service_level.confidence` + `method` | the value is a *distribution*, not a point |
| coverage | observed *n* ÷ target *N* | usually dominant; the unobserved are imputed with a widened prior |

The engine models each household's below-floor probability `p_h = P(service_level_h < floor_c)` (metered ⇒
`p_h≈0/1`; modelled ⇒ intermediate) and aggregates `Σ w_h·below_h / Σ w_h`. It carries a **shared latent bias
term per (method, source)**, applied to every record from that source in a given draw — this is what prevents a
razor-thin interval on 100k records that all came from one uncalibrated model. **Correlation and coverage, not
per-record confidence, set the interval width.**

- **v1 (analytic):** for proportions/counts, a **Wilson score interval** on the observed *n*, widened by a
  finite-population/coverage term for *N−n* and a bias-inflation factor for uncalibrated sources. Cheap, covers
  most floor-gap questions.
- **v2 (Monte-Carlo):** the full simulation, required for the **deprivation index** (a nonlinear composite over
  capabilities) and for value-distributions crossing the floor threshold. Rides in with the Slice-2 engines.

### 3. A governed publishability gate

A `governance.rule` (per capability, keyed on settlement class) sets `min_coverage` and `max_interval_width`.
An estimate that fails either is stored with `publishable=false` and rendered **greyed with "insufficient
coverage — n/N"**, never as a headline; a `governance.decision` may cite it only when explicitly marked
provisional. The gate is data, not code — tighten it and the whole platform's headline set recomputes.

### 4. A calibration loop closes the garbage-in gap

A stated `confidence: 0.6` is only meaningful if ~60% of such assertions are correct when ground-truthed.
A scheduled job ground-truths a sample (PropIQ's 82%-in-Mohali is exactly this data), fits the
confidence→probability mapping, and stamps `model_version` on every estimate. Calibration — not cleverer math —
is what defeats garbage-in.

## Consequences

- The platform gains a single, auditable honesty contract: every headline number carries its interval,
  coverage and lineage, and the low-coverage ones are visibly provisional rather than silently wrong.
- `stat.estimate` is reusable platform-wide (not welfare-specific): any aggregate — tax gap rates, coverage
  QA, air-quality ward means — can adopt it. A new general `stat` domain is justified.
- Cost is a real engine, not a field: propagation lives in a **certified** component (ADR-0022), and the gate
  + calibration are governed rules/jobs.

## Open questions

1. **Imputation prior for the unobserved** — observed-rate carry-over vs an explicit uninformative prior;
   probably per-capability, governed.
2. **Where correlation groups are drawn** — per (method, source) is the v1 grouping; spatial correlation
   (neighbouring households share error) may need a second grouping later.
3. **Interval semantics in the UI** — how a citizen-facing surface renders a credible interval without
   misleading; a rendering rule on `viz.layer`.

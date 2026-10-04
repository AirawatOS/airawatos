# Property Tax: Service Spec → System, worked backwards

*The [[ADR-0109]] S4 proving slice. We take a service AirawatOS has **already built** — the Tax Gap Finder —
and reverse-author its machine-readable **Service Specification**
([`property-tax.service-spec.yaml`](../../components/solutions/tax-gap-finder/property-tax.service-spec.yaml)),
then show that every line of the spec maps to a real governed artifact, that generation would reproduce the
system from the spec, and that the spec **surfaces exactly what is still missing**. This is the concrete
difference between today's low-code configuration and true spec-to-system.*

## Why reconstruct instead of invent

A greenfield "write a spec, get an app" demo proves nothing — you can't check it. Reconstructing a service
that already runs lets us **diff the spec against reality**: if the spec is faithful, every element resolves
to a governed id in the live system, and the handful that don't resolve are precisely the roadmap.

## The loop, worked backwards

Each row is a spec section → what it **already resolves to** in the running system → what a generator would
**emit** → whether a **conformance test** exists.

| Spec section | Resolves to today (governed) | Generator emits | Test |
|---|---|---|---|
| `domain_model` (parcel, assessment, utility, change_signal, candidate, cell.tax_gap) | `govern_schemas.py` (`tax.*`, `util.*`) + foundation `geo.*` | schema governance | — |
| `operations` (matchpolicy, match_preview, gap_scan, campaign.*) | `tax-gap-engine`, `campaign-engine` governed verbs | verb interfaces + engine code | — |
| `business_rules` (link/gap/confidence) | `tax.match_policy` config + `tax-gap-engine` helpers | `governance.policy_rule` + config | — |
| `workflow.candidate` (flagged→verified\|dismissed) | `tax.candidate.status` + campaign transitions | `platform.workflow` graph | — |
| `roles` (admin, field-officer) | `_ADMIN` gate + `org.employee` assignee | role grants | — |
| `data_sources` (register, cadastre, utilities, geocode, EO, footprints) | 6 ingest drivers | driver components | — |
| `acceptance_criteria` | behaviour present in the engines | conformance suite | **none** |
| `domain_model`: `tax.demand`, `tax.payment` | **nothing** (`impl: null`) | *would be generated* | — |
| `workflow.revenue` (assess→demand→collect) | **nothing** | *would be generated* | — |

Seven of nine sections resolve cleanly to governed ids — that is the ~70% substrate ADR-0109 describes. The
two that resolve to `null` are the real, honest gap.

## Traceability — the part no low-code platform has

Because every element carries an `impl:` id, the spec is a **traceability index**. You can ask, mechanically:

> **"Which code implements rule PT-GAP-FOOTPRINT?"**
> → `tax-gap-engine/run.py:270` (the footprint-no-assessment evidence), surfaced via `AC-GAP-FOOTPRINT`.

> **"Which requirement has no test?"**
> → **all of them.** Every `acceptance_criteria` entry has `test: null`. The spec makes the verification gap
> impossible to miss — it's a query, not a code review.

> **"What does the service promise that it can't yet do?"**
> → everything marked `status: roadmap`: assessment formula, demand issuance, payment/collection, the
> citizen and assessor roles, SLAs, outbound events, and privacy/consent governance.

For a government revenue system, those three questions *are* the audit.

## What this makes obvious

1. **The Tax Gap Finder is a detect-and-verify vertical, not a full revenue system.** The spec says so in one
   place (`workflow.revenue: roadmap`), rather than it being tacit knowledge buried across engines.
2. **The next build is specified, not guessed.** Closing the `assess → demand → collect` tail means
   generating `tax.demand` / `tax.payment`, the revenue workflow states, the `PT-ASSESS-FORMULA` rule, an
   assessor role and a citizen surface — each already has its slot in the spec with `impl: null`.
3. **Verification is the first debt to pay.** Turning the six `acceptance_criteria` into a conformance suite
   is a bounded, high-value task the spec hands you directly.

## Low-code config vs spec-to-system — the distinction

| | Today's low-code config | Service-Spec → System (ADR-0109) |
|---|---|---|
| Authored artifact | per-tool config screens | one governed `service_spec` |
| Source of truth | scattered across components | the spec (at the service layer) |
| "Which rule → which code?" | manual archaeology | a query over `impl:` ids |
| Coverage gaps | discovered in production | `status: roadmap` / `test: null`, up front |
| Generation | hand-wired per component | spec → generate → certify → reconcile |

## Next step to make it live (S4 continued)

1. Govern `platform.service_spec` and ingest this YAML as the first instance (S1).
2. Wire the `impl:` references into `prov.derivation` so the traceability queries run against the registry, not the file (S2).
3. Turn the six acceptance criteria into a conformance suite — the first executable tests this vertical has ever had.
4. Generate the `assess → demand → collect` tail *from the roadmap sections* and reconcile against the spec — the first true spec-to-code increment on a real DIGIT-class service.

*Spec: [`components/solutions/tax-gap-finder/property-tax.service-spec.yaml`](../../components/solutions/tax-gap-finder/property-tax.service-spec.yaml) · Decision: [[ADR-0109]] · Implementation inventory: the Tax Gap Finder solution (`ds:airawat:solution/tax-gap-finder`).*

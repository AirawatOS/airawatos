# Design — conformance-generated status matrix (BUILT)

**Status:** BUILT (2026-11-06). Implemented as `conformance/run.py --matrix` (per-case rule tags → JSON) +
`conformance/build_matrix.py` (reducer) → generated **[STATUS-MATRIX.md](STATUS-MATRIX.md)** (+ `.json`). The
12 specs + README now carry a banner pointing at the matrix as the conformance-derived source of truth; their
inline **Status:** lines are kept for prose/rationale. This document is the design/rationale for that build.
It describes how a **rule × environment → status** matrix is *generated from conformance results* so the
per-rule status stops being hand-written (and stops drifting, as the Step-1 sweep found it had: COMPONENT
11→13, DECISION 3→4 VIOLATED, README FND row).

## Problem

Each spec rule carries a hand-written status (IN PLACE / PARTIAL / VIOLATED / PLANNED / TO CONFIRM). Those are
edited by hand, so they drift from what the live system actually does, and they describe a single blended
posture even though a rule can be **held on local-dev but not in production** (the Step-1 "status lag" note:
FND-11/PLT-4/PLT-5/NET-3). The conformance suite (`conformance/run.py`) already *measures* behaviour per rule, per
environment — so the status should be **derived from it**, not retyped.

## The matrix

One row per spec rule, one column per **environment**, each cell a **derived status + provenance**:

| rule | local-dev | production | source |
|---|---|---|---|
| FND-8 (fail-closed) | VIOLATED (XFAIL REG-6/FND-8) | VIOLATED (XFAIL) | run 2026-11-06, cases FND-1/FND-3/FND-15… |
| PLT-4 (tenant confers nothing) | HELD (PASS PLT-4) | PARTIAL (not cut over) | local-dev enforce; prod shadow |
| NET-3 (network.admin role) | HELD (PASS NET-3) | PARTIAL | … |
| REG-14 (erasable store) | PLANNED (SKIP_BUILD) | PLANNED (SKIP_BUILD) | not black-box reachable |

Environments to start: **local-dev** and **production** (the two the installer profiles target). The column set
is open — a `rehearsal` or per-tenant column can be added by running the suite with that target.

## How it is produced (from `conformance/run.py`)

`run.py` already emits, per case: a **result kind** (PASS / XFAIL / XPASS / FAIL / SKIP_CREDS / SKIP_BUILD), the
**rule IDs** the case cites (e.g. "FND-1/FND-3/FND-15", "NET-3", "PLT-4"), and the **mode** (external / internal). It runs
against a base URL (`AOS_BASE`) — i.e. an environment. The matrix is a thin aggregation layer on top:

1. **Tag each case with its rule IDs** (already in the case label; formalise as a `rules=[…]` field so the
   mapping is machine-readable rather than parsed from the printed label).
2. **`run.py --matrix`** (new output mode): instead of the human report, emit a JSON array of
   `{case, rules:[…], mode, result}` for the environment it just ran against, plus `{env, base, git_sha, ts}`.
3. **Run once per environment** (`AOS_BASE`/`AOS_MODE` per env; local-dev edge + in-cluster, production edge).
   Each run writes `conformance/results/<env>.json`.
4. **A generator** (`conformance/build_matrix.py`, new) reads all `<env>.json`, groups cases by rule, reduces
   each rule×env to one status via the mapping below, and writes `docs/specs/STATUS-MATRIX.md` (+ a `.json`).

## Conformance result → spec status (the reduction)

A rule can be cited by several cases; reduce **worst-first** so a single failing case dominates:

| conformance (worst case for the rule, that env) | derived spec status |
|---|---|
| any **FAIL** | **REGRESSION** (contradicts spec — must be red; not a normal status) |
| all cited cases **PASS** (no SKIP_BUILD) | **HELD / IN PLACE** |
| mix of PASS + **XFAIL** | **PARTIAL** (held in some surfaces, known-violation in others) |
| only **XFAIL** (known violation reproduced) | **VIOLATED** (tracked as debt; cite the debt ID) |
| **XPASS** (violation looks fixed) | **REVIEW** (raise the status — the spec lags the code) |
| any **SKIP_BUILD** (part of the rule not built / not reachable black-box), with no FAIL/XPASS/XFAIL | **PLANNED / NEEDS-BUILD** — never HELD, even when the other cited cases PASS (slice-1e) |
| only **SKIP_CREDS** | **UNVERIFIED (creds)** — status not asserted; fix the fixture |

The reducer records *which* cases drove the cell (provenance), so a status is always explainable.

## How the specs consume it (replacing hand-written status)

- Each rule's hand-written status line becomes a **transclusion/reference** to `STATUS-MATRIX.md` (e.g. a
  marker `<!-- status: FND-8 -->` the generator fills, or the spec simply links the matrix and drops the inline
  word). Single source of truth = conformance results; the specs stop carrying a hand-typed status to drift.
- The per-spec **Tally** is computed by the generator from the matrix (counts per derived status per env),
  so a tally can never again disagree with its rules (the Step-1 defect).
- The README table's "Status (tally)" column is generated likewise.

## Honest limits (why this is design, not a mandate to auto-replace today)

- **Black-box only.** Many rules are `NEEDS-BUILD` (not reachable over HTTP: restart orchestration, audit-store
  internals, startup-time checks). Those rows are **PLANNED (not reachable)** and still need a prose rationale
  the generator can't invent — so the specs keep a short human note alongside the generated status, not instead.
- **Fixture dependence.** `SKIP_CREDS` rows assert nothing until the conformance fixture is provisioned (the
  fresh-install test's finding). The matrix must show `UNVERIFIED (creds)`, never silently PASS/FAIL.
- **Environment truth.** A `production` column is only as true as a real production run; until production is
  stood up (see FRESH-INSTALL-TEST.md §Step 3), that column is **projected**, and must be labelled as such, not
  asserted.
- **Rule→case coverage is partial.** Not every rule has a case yet; uncovered rules show **NO TEST** (distinct
  from PLANNED) so the gap is visible rather than hidden as "unknown = planned".

## Build order (when approved — not now)

1. Add `rules=[…]` to each case in `run.py` + a `--matrix` JSON emitter (no behaviour change to the human run).
2. `build_matrix.py` reducer + the markdown/JSON writer.
3. One generated `STATUS-MATRIX.md`; wire the specs to reference it for the covered rules; keep prose notes for
   NEEDS-BUILD / NO TEST.
4. CI step: regenerate on every conformance run; fail the build on any **REGRESSION** or on a tally mismatch.

# Consolidation review method (phase 5)

The standing method for the consolidation code-review slices (KERNEL, IDENTITY, NETWORK+TRUST, APP-HOST,
INTERNAL-SERVICES, …). Each review doc states its own scope + findings; this is the shared convention.

- **Fresh, independent reviewers.** Each slice is audited by fresh reviewer agents (not the session that wrote
  the code), read-only, **findings only** — no code changed in the review step. Evidence is `file:line`.
- **Judge the source + local-dev, never EC2.** The EC2 box (`airos.airawat.org`) is a **development
  environment and is out of scope**: reviews do **not** probe, curl, SSH, or otherwise check it, and its state is
  not a gating input. Findings are judged against the repository source and verified on the **local-dev** stack.
  The **first production deployment will be a fresh install**, so production posture is whatever a fresh install
  of the reviewed source produces — not whatever the current EC2 box happens to run. (Earlier slices recorded
  read-only EC2 audits; those are retained for history only and are not repeated.)
- **Matrix vs review.** `docs/specs/STATUS-MATRIX.md` is conformance-*measured* on local-dev; a review is a code
  *audit*. Reproducible violations are encoded in `conformance/run.py` as live **XFAIL** (the violation is
  reproduced today); once fixed they flip to **PASS**. Rules that can't be black-box-reached on a seeded,
  healthy local-dev stack are recorded **SKIP_BUILD** with a reason + a proposed internal/unit test.
- **Every VIOLATED finding needs a test that shows it**, and NO-TEST rules get a test where feasible (else a
  recorded reason). New debt is opened in `docs/consolidation/DEBT-REGISTER.md` (B-series = invariant violations,
  A-series = transitional mechanisms); the STATUS-MATRIX is regenerated; the review doc carries a one-page
  summary (top risks, verdict counts) over the per-rule tables.
- **Standing rule for code slices.** A slice that changes service code ends with a local-dev rebuild + fresh
  install + conformance both modes, and the corresponding XFAIL(s) flipping to PASS.

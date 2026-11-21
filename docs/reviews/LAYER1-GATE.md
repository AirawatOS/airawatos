# Layer 1 — POST-MERGE GATE RECORD

Status: **PASS — 2026-11-21.** The owner approved the slice-1m merges and the `layer1-complete` tag (§6).

FIX-PLAN § "Between Layer 1 and Layer 2", step 1: after the merges, a fresh install of the merged mains + conformance in
both modes (0 FAIL / 0 XPASS) + flow-map + vault-scope + the installer's functional proof (Phase 15); then tag
`layer1-complete` on `main` in all five repositories at the same point.

## 1. History of this gate

| Date | Step | Result |
|---|---|---|
| 2026-11-11 | run `20261111T080606Z-ef8346fd` (demo instance) on the Layer 1 mains | every net green **except `restoredrill`: no results file** |
| 2026-11-17 | strict-matrix comparison of that run (local instance) | 1 problem: the required net `restoredrill` missing |
| 2026-11-17 | owner decisions: **(a)** re-run the restore drill locally; **(i)** a focused fresh-reviewer pass over the commits after RECHECK-2 | — |
| 2026-11-19 | focused fresh review (findings only, REVIEW-METHOD) | **FAIL — 2 High** (both in authority code) |
| 2026-11-19..20 | slice 1m: fixes approved by the owner; a fresh re-review | **0 High** — both Highs closed |
| 2026-11-21 | fresh install + `make verify` on the 1m heads, run `20261121T031709Z-23f904f2` | **all nets green; strict matrix ✓** |

The focused review and re-review records hold kernel findings, so they are kept privately (git-ignored, not in this
public repository), as the standing rule requires. This record gives only the outcome.

## 2. The heads under the gate (slice 1m — open PRs, not yet merged)

| Repository | Head evidenced | Branch | PR |
|---|---|---|---|
| root | `052b67d` | `fix/layer1-gate-1m` | #4 |
| platform-spec | `fc6922a` | `fix/layer1-gate-1m` | #23 |
| kernel | `0316f59` | `fix/layer1-gate-1m` | #7 |
| network | `29c67b6` | `fix/layer1-gate-1m` | #13 |
| components | `47114ff` | `main` (unchanged) | — |

Images: tag `1m` (reference, kernel, network, devstub), built from git by `deploy/build-images.sh`; `IMAGES.lock.json`
re-recorded (only the tag keys changed; the pinned inputs are identical to 1l).

**The tag goes on `main` after the merges.** The merged `main` trees must equal the evidenced heads above. If a merge
brings in anything other than these commits, the gate run is repeated.

## 3. What slice 1m changed (public summary)

- **Kernel** (authority code; the owner approved the change on 2026-11-19): the two High findings of the focused review,
  plus one regression the re-review caught (fixed in `0316f59`). Each fix has tests that fail when the fix is reverted.
  The details are in the private review record.
- **Model gateway** (`platform-spec`): "is this production?" comes from the one shared definition (`gateflags`).
  Unset or unknown means production, so the dev stub provider is refused. The dev-stub host check also accepts a
  trailing dot.
- **Dev stub provider**: it fails closed and starts only under an explicit `AIRAWAT_ENV=development` (or `dev`).
- **New banned pattern `AIRAWAT_ENV_DIRECT`**: code may not read `AIRAWAT_ENV` directly outside the allow-list
  (self-test 43/43).
- **Tests that could not fail** (installer functional check, network B175): the revoke proof now has a positive control
  that sees the grant as active before the revoke.

## 4. Evidence — run `20261121T031709Z-23f904f2` (local instance, 2026-11-21 03:17Z–07:41Z)

There was a fresh install (dev profile) on an empty Docker: all earlier images and volumes had gone in a Docker Desktop
reset. The local credentials were backed up first. Then `make verify` ran with **exit 0**: "✓ make verify: all assurance
nets green".

| Net | PASS | XFAIL | SKIP_BUILD (ceiling) | FAIL / XPASS | PASS in baseline |
|---|---|---|---|---|---|
| functional (fresh install + Phase 15) | 47 | 0 | 0 (0) | 0 | 46 |
| conformance internal | 66 | 6 | 67 (67) | 0 | 66 |
| conformance external | 17 | 1 | 46 (46) | 0 | 17 |
| flowmap (ARC) | 13 | 0 | 1 (1) | 0 | 13 |
| vaultscope (ARC-7) | 198 | 0 | 0 (0) | 0 | 198 |
| dbgrants (B93 / ARC-3) | 15 | 0 | 0 (0) | 0 | 15 |
| netdoors (B86) | 31 | 0 | 0 (0) | 0 | 31 |
| edges (1c) | 66 | 1 | 0 (0) | 0 | 66 |
| routes (net 4) | 2 | 1 | 0 (0) | 0 | 2 |
| listen (ARC-5) | 1 | 0 | 0 (0) | 0 | 1 |
| banned | 9 | 1 | 0 (0) | 0 | 8 |
| gtwstatic | 0 | 4 | 0 (0) | 0 | 0 |
| knownviolations | 0 | 12 | 0 (0) | 0 | 0 |
| vaultrenewal (B96) | 10 | 0 | 0 (0) | 0 | 10 |
| ops (B102) | 7 | 0 | 0 (0) | 0 | 7 |
| scans (net 8) | 4 | 0 | 0 (0) | 0 | 4 |
| **restoredrill (B102 / B160)** | **38** | 0 | 0 (0) | 0 | 38 |

The two extra PASSes are the new 1m checks (banned `AIRAWAT_ENV_DIRECT`; functional positive control). The nets that
write no JSON also passed in the same run: unit suites, svcclient, gateflags, build-context, images, installer,
secret-names, decide-unit, the backup/restore self-test (0 failures) and the strict-matrix self-test (0 of 7 mutations
missed).

## 5. Strict-matrix comparison

`conformance/build_matrix.py --strict` against `verify/evidence-baseline.json` (as of `54ad252`, unchanged):

| Check | Result |
|---|---|
| every file carries the run id; no stale evidence | ✓ |
| evidence heads = current HEAD in all five repositories; nothing dirty | ✓ |
| no FAIL, no XPASS, no unknown result kind | ✓ |
| no baseline case group lost cases (17 nets) | ✓ |
| no baseline PASS demoted (17 nets) | ✓ |
| SKIP_BUILD within the 1l ceiling | ✓ every net exactly at its ceiling |
| every REQUIRED net wrote evidence (incl. `restoredrill`) | ✓ |

**`✓ STRICT: every required net wrote fresh, non-empty, passing evidence for run 20261121T031709Z-23f904f2`.**

`docs/specs/STATUS-MATRIX.{md,json}` were regenerated by this run. FND-9 moves from PLANNED(needs-build) to PARTIAL;
nothing moves down.

### Observations from the run (no failure in the evidence)

- **Restore self-test harness (test-only):** when a SIGKILL case kills `restore.sh` at a pause, the pause's
  `sleep 600` is left as an orphan. It still holds the test's output pipe, so each SIGKILL case waits until the sleep
  ends. With the machine asleep, one wait lasted about 80 minutes. The orphans were ended by hand during the run (the
  test's own outcome is unaffected). Not fixed: this needs a register entry and a decision.
- **Installer live test under load:** in an earlier full run (run 2) three installer live checks failed. Run alone, the
  test passed (0 failures, 786 s), and run 3 passed. Recorded as a flake under load (Docker memory 8 GB after the reset).

## 6. Owner decisions (2026-11-21)

1. **The pre-existing kernel Medium findings** surfaced by the re-review (in the private record, not introduced by 1m)
   do **not** block `layer1-complete`. They move to **Layer 2 (Kernel)** as **DEBT-B185**.
2. **Merge** the slice-1m PRs (root #4, platform-spec #23, kernel #7, network #13): approved.
3. **Tag** `layer1-complete` on the merged mains in root, platform-spec, components, kernel and network: approved.

The root PR also carries this record, the regenerated status matrix and the DEBT-B185 entry. Those are documentation
commits after the evidenced head `052b67d`; no code changed.

Still carried, and not blocking the tag (per the register): **DEBT-B179** (High, the first post-tag slice), **B163,
B164** (Med, before the Layer 2 exit), **B185** (Med, Layer 2), and the remaining Medium and Low findings of the focused
review (in the private record).

## 7. Verdict

**PASS.** The evidence meets the gate: fresh install, conformance in both modes with 0 FAIL / 0 XPASS, flow-map,
vault-scope, the Phase 15 functional proof, the restore drill and the strict matrix are all green on the 1m heads. The
focused fresh review closed with 0 High. `layer1-complete` goes on the merged mains.

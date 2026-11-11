# F2 — slice-1h evidence-integrity fix: independent review

Reviewer: independent (did not build Layer 1; took part in neither earlier exit review). Scope: ONLY the slice-1h B99
"evidence integrity" fix: `verify/evidence.py`, `Makefile` (run id, `clean-results`, `matrix`, `matrix-fast`),
`verify/conformance_matrix.sh`, `conformance/build_matrix.py --strict`, and every net that writes `conformance/results/*.json`.
HEAD at review: root `870fe8d`; the committed evidence is run `20261108T185730Z-827428c1`, recorded at root `ba2d764`.

**Threat model used for rating.** These nets defend against the platform's own regressions and an honest-but-mistaken
operator or agent. They do not defend against a malicious developer with write access to the repo. Anyone who can run
`python3` in the checkout can write any results file, so no local file-based scheme can stop forgery. Ratings below count
only routes an honest operator or a code regression could plausibly take.

**Benchmark.** Re-review §8 condition 4 / DEBT-B99 fix plan: "`ts`/`git_sha`/case-count required; `build_matrix.py` fails
… on stale or mixed inputs" (debt register: "require exit code + ts ≥ start + cases > 0 + git_sha; matrix refuses
stale/mixed inputs"). R3-7 named "results from two commits mixed" as part of the original Medium finding.

**Method.** I tested the synthetic matrix cases on an isolated copy of `build_matrix.py`: same code, same spec files, a
copy of the committed results, under `…/tmp/f2tree`. First check: with the old run id the copy reproduces the committed
`STATUS-MATRIX.md` byte for byte. I tested the Makefile and `evidence.py` routes in the real repo, using only `banned`,
`secret-names` (with a bogus image) and `matrix`. Nothing touched the stack. `make verify`, the installer and
`fresh_install.sh` were not run.

## Findings

| ID | Sev | Title | Owning layer | In 1h scope | L1-owned Med+? |
|---|---|---|---|---|---|
| F2-1 | **Med** | Strict matrix does not compare git heads: mixed-commit and dirty-tree evidence accepted; `ts`/`git`/`git_sha` not required | L1 | Yes (cond. 4 "git_sha required", "mixed inputs"; R3-7) | **Yes** |
| F2-2 | **Med** | No case-count or case-set baseline: a net that silently loses cases stays green, and losing SKIP_BUILD placeholders *raises* HELD (5 → 17) | L1 | Yes (cond. 4 "case-count required"; §3 "nothing gates on that count") | **Yes** |
| F2-3 | Low | Run id is a plain label: reusing an inherited `AOS_RUN_ID` re-validates any old evidence; `evidence.py seal` re-stamps any file | L1 | Yes | No |
| F2-4 | Low | Strict accepts unknown/duplicate modes and does not check `env` or mode-vs-filename; a production-env file creates a "measured" production column *and* satisfies a required local-dev net | L1 | Yes | No |
| F2-5 | Low | Six nets write no evidence (decide-unit, secret-names, gateflags, build-context, images, installer); under `make -k` or partial targets the strict matrix still prints "every required net … passing" | L1 | Partly | No |
| F2-6 | Low | `needs-build`/`needs-creds` are accepted result kinds but the reduction ignores them: PASS + `needs-build` reads HELD (SKIP_BUILD would read PLANNED) | L1 | Yes | No |
| F2-7 | Low | Cases citing no rules are accepted; a required file can contribute nothing to the matrix (4 such cases today, incl. the scans CVE case `rules: []`) | L1 | Yes | No |
| F2-8 | Info | `--optional` waives any required net by hand without saying so; `verify-fast` overwrites the tracked matrix (HELD 5 → 4) with no "fast run" marker | L1 | Yes | No |
| F2-9 | Info | Malformed input (truncated JSON, case with no `result`) crashes `build_matrix.py` with a traceback; it fails closed, but the old matrix stays on disk unchanged | L1 | Yes | No |
| F2-10 | Info | Matrix provenance line takes `git_sha` and `ts` from the first file alphabetically (banned) only, not the run's span or all five repos; there is no `.NOTPARALLEL` (`make -j` fails safe) | L1 | Yes | No |

### F2-1 (Med): git heads are recorded but never checked

`evidence.py` records `git` (5 repos, with `+dirty`) and `git_sha`. `build_matrix.py` never reads `git`. It uses `git_sha`
only for the provenance line, taken from the first file per env (`setdefault`). It compares neither against HEAD nor
across files, and it does not require `ts`, `git` or `git_sha` at all.

Evidence:
```
# T3: banned's git = all '0000000+dirty', vaultscope kernel = '1111111+dirty'; same run id
[build_matrix] ✓ STRICT: every required net wrote fresh, non-empty, passing evidence …   rc=0
md provenance: git `0000000+dirty`          (nested-repo dirtiness never shown at all)

# T17: run_id present but ts, git, git_sha removed
[build_matrix] ✓ STRICT: …   rc=0

# Real repo: AOS_RUN_ID=20261108T185730Z-827428c1 make banned matrix
✓ banned patterns: 0 check(s) failing
[build_matrix] ✓ STRICT: every required net wrote fresh … for run 20261108T185730Z-827428c1
 banned … 870fe8d4 2026-11-09T01:12:45Z | ops … ba2d7643 2026-11-08T19:14:26Z     ← two commits, 6 h apart, accepted
```
The committed matrix itself is at HEAD `870fe8d` from evidence recorded at `ba2d764`. That is legitimate here, because
`870fe8d` changes only the two matrix files. But nothing checks it.

Honest-mistake routes:
- A commit in any of the 5 repos during the ~20-minute `make verify`.
- Running verify on a dirty nested repo, then committing the matrix as if it came from the clean commit.

Suggested fix:
- Require `ts`, `git` and `git_sha`.
- Require one identical `git` map across all files.
- Refuse `+dirty` under `--strict`.
- Require that map to equal the current HEADs, or the parent when only `docs/specs/STATUS-MATRIX.*` changed.

### F2-2 (Med): case count is checked only as > 0

There is no expected case count, case-name set or SKIP_BUILD count per net. Neither `build_matrix.py` nor the
`conformance_matrix.sh` tally checks one. The tally gates only on `XPASS=0 FAIL=0 SKIP_CREDS=0`.

Evidence (strict, same run id, rc=0 every time):
```
baseline                                         HELD 5  PARTIAL 15  PLANNED 87  NO TEST 70
T13b internal reduced to 1 case                  HELD 15 PARTIAL 8   PLANNED 38  NO TEST 114
T14b every internal PASS → SKIP_BUILD            HELD 4  PARTIAL 9   VIOLATED 11 PLANNED 88
T18 external's 46 SKIP_BUILD cases dropped       HELD 7  …           PLANNED 58  NO TEST 97
T19 internal's 67 SKIP_BUILD cases dropped       HELD 17 …           PLANNED 36
    HELD now: FND-9 FND-10 FND-11 FND-12 FND-19 NET-12 ACC-4 CLI-1 CLI-5 PLT-5 CMP-3 CMP-5 CMP-6 FED7 ARC-1 ARC-3 ARC-5
```
A realistic regression shows this: a merge or refactor in `run.py` drops a `run_*_review_cases()` call or an `nb(...)`
list. Those placeholders are what keep rules PLANNED instead of HELD. The matrix then *overstates* assurance, and the
build stays green.

Suggested fix: keep a committed per-mode baseline of the case-name set (or at least counts per result kind). Strict should
fail on any case that disappears or any change in SKIP_BUILD/XFAIL counts that nobody acknowledged.

### F2-3 (Low): the run id binds nothing beyond a writable value

- `Makefile` mints `AOS_RUN_ID` only when `$(origin AOS_RUN_ID)` is undefined, so an exported shell value is inherited.
  Partial targets then re-validate stale evidence. Fresh id, `make banned matrix`: 15 × STALE, rc=2 (held). Inherited old
  id, `make banned matrix`: ✓ STRICT, rc=0.
- `AOS_RUN_ID=20991231T000000Z-forged00 python3 verify/evidence.py seal conformance/results/local-dev-ops.json` printed
  `sealed … run 20991231T000000Z-forged00`. The 7-case file from yesterday now carries the new id, the new HEAD and a new
  `ts`.
- `seal` also stamps a file with a FAIL case, mode `whatever` and env `production` without complaint. The matrix still
  catches the FAIL.
- The `ts ≥ run start` check from the fix plan is not implemented, although the run id embeds its start time.

Honest claim to make: "The run id is a freshness label that stops *accidental* reuse of evidence from an earlier
`make` invocation. It is not proof that a net ran." That claim is acceptable for a local assurance net. An inherited
`AOS_RUN_ID` is the one honest-mistake route. Two possible fixes: `make` could refuse an inherited id for `verify`
unless one is passed explicitly (e.g. `AOS_REUSE_RUN=1`), or the matrix could check `ts` against the run id's embedded
start time and HEAD (F2-1).

### F2-4 (Low): mode/env structure not checked

- T7b: a stray second file with `mode: ops` and one PASS citing FND-13 was accepted. It was merged in, and FND-13
  went NO TEST → HELD.
- T8: a file with `mode: bogus` and `env: production` was accepted. The md then shows "production — measured: modes
  bogus" *and* "production — PROJECTED".
- T9: `local-dev-ops.json` relabelled `env: production` satisfies required `ops` (`seen_modes` is not per env), so
  local-dev has no ops evidence and strict is still green.
- T15 (mode/filename mismatch) is caught only indirectly, through MISSING.

Realistic route: `flow_map_test.py` and `vault_scope_test.py` honour `AOS_ENV`, and the matrix doc tells operators to run
with `AOS_ENV=production`. With that exported, `make verify` against local-dev would file flowmap and vaultscope under
production, and strict would pass.

Suggested fix: under strict, require `env == local-dev` (or `AOS_ENV`), `mode` in REQUIRED, exactly one file per mode,
and filename = `<env>-<mode>.json`.

### F2-5 (Low): nets without evidence

decide-unit, secret-names, gateflags, build-context, images and installer write no results file. They are guarded only by
make's exit status.

- `AOS_RUN_ID=<old> make -k REF_IMAGE=airawat-f2-nonexistent:0 secret-names matrix` failed `secret-names` (Error 125),
  yet the matrix target then printed `✓ STRICT: every required net wrote fresh, non-empty, passing evidence`. make rc=2.
- The same applies to an evidence-writing net that exits non-zero for a reason it does not record as a FAIL case.
  Currently, every writer's exit condition matches a FAIL case; `scans.py` cases are *stricter* than its `failed` count.
- No HELD rule depends on these nets. The HELD rules (FND-19, PLT-5, ARC-1, ARC-3, ARC-5) are all cited by
  evidence-writing nets. FND-16, whose B97 fix is proven by gateflags, shows PLANNED(needs-build).

So the matrix does not overclaim. But its success line is wider than its inputs. Suggested fix: each of these nets writes a
one-case evidence file and is added to REQUIRED, or the success line names only the nets it actually covers.

### F2-6 (Low): `needs-build`/`needs-creds` reduction hole

`KINDS` includes `needs-build` and `needs-creds`, but `reduce_status` handles only the SKIP_* names. T10b: FND-19 with an
added `needs-build` case stays HELD; the same case as `SKIP_BUILD` gives PLANNED(needs-build). No net emits these as a
`result` today: `run.py` uses `needs-build` as the *kind* and maps the result to SKIP_BUILD. So this is latent. Fix:
drop them from KINDS, or reduce them like SKIP_*.

### F2-7 (Low): rule-less cases

These cases carry no rules:
- external: "handle/username is not a credential", "components list does not leak run_token"
- internal: "component.publisher refused at secrets admin (/set)"
- scans: "no new CRITICAL image CVE and no HIGH/CRITICAL dependency CVE" (`rules: []`)

T12: a listen file whose cases all have `rules: []` satisfies REQUIRED `listen`. ARC-5 stays HELD only because flowmap
also cites it. Strict should refuse a case with no rules, or a required file that cites none.

### F2-8 (Info): `--optional` and `verify-fast`

`--optional` only waives MISSING; stale or FAILed optional files are still refused. T6: `--optional banned,internal` with
both files removed gives ✓ STRICT, with no line naming the waived nets. The Makefile passes only `functional`, so this
needs a hand-run command (not an abuse route through make). Separately, `verify-fast` rewrites the tracked
`STATUS-MATRIX.md` without functional evidence (T20: HELD 5 → 4, NO TEST 70 → 71) and gives no marker that it was a fast
run.

### F2-9 / F2-10 (Info)

- Truncated JSON (T4) gives a `JSONDecodeError` traceback, and a case without `result` (T11) gives a `TypeError` in
  `sorted()`. Both exit 1 and fail closed, but the previous matrix is left in place. A clear "✗ unreadable evidence" line
  would be better.
- The provenance line shows `ts 2026-11-08T18:57:31Z`, which is banned's timestamp. The run actually ended around 19:16.
- With `make -j`, `clean-results` and `matrix` can race the nets. This fails safe (MISSING).

## Held (tried and could not break)

- **run.py crash or early exit**: `conformance_matrix.sh` deletes the host and container results first (and `rm -rf
  /tmp/conf`). An uncaught exception exits 1, which is accepted, but then no file exists, so the net reports "✗ run.py
  wrote NO results file". Exit codes other than 0/1 (preflight `sys.exit(2)`) fail. The `run.py` exception handlers are
  per call, not per group, so no case group is silently swallowed.
- **conformance tally**: it checks the run id *before* sealing. A STALE, EMPTY or unparseable file yields a tally without
  the `XPASS=0 FAIL=0 SKIP_CREDS=0` substring and fails. The substring cannot be matched by two-digit counts.
- **Mixed run ids** (T2): reported as STALE. The same goes for older-version files with no `run_id` (T5).
- **Skipped clean-results** (`make banned matrix`, fresh id): 15 × STALE, rc=2.
- **Zero cases**: refused by `write()`, `seal()` and strict. FAIL/XPASS fail strict. An unknown result kind fails strict
  (lowercase `pass`), and so does a missing result (by crash).
- **Truncated JSON**: fails closed (F2-9).
- **Phase 15 functional evidence**: if `functional_check.py` emits no `MATRIX_RESULTS`, the file is empty and `seal`'s
  `json.load` fails, so install.sh exits "✗ the functional proof wrote no evidence".
- **REQUIRED coverage**: REQUIRED lists all 16 modes that any net writes, so none is missing.
- **No HELD rule** depends on a net that writes no evidence.
- **`matrix-fast`**: waives only `functional` and still refuses a stale or failed functional file.
- **Normal `make verify`**: one run id per invocation, exported to every net, with `clean-results` first. In the default
  path (no inherited id, no mid-run commits) only this run's evidence can reach the matrix.

## Exit-rule view

Two Layer-1-owned Medium findings remain inside slice-1h scope: **F2-1** (no git-head / mixed-commit / dirty check; `ts`
and `git_sha` not required) and **F2-2** (no case-count baseline; silent case loss inflates HELD). Both are explicit in
condition 4 ("`ts`/`git_sha`/case-count required", "mixed inputs"), and both can be reached by honest mistakes or code
regressions, without any malice. **The evidence-integrity condition is therefore not fully met.** By case: the
stale-file, missing-file and failed-run cases the slice targeted are held.

## Restoration

`conformance/results/` was copied aside before any test, then restored with `cp -a`. Its `shasum` listing is identical to
the pre-test listing (`RESULTS-RESTORED`). `docs/specs/STATUS-MATRIX.md` and `.json` were restored with
`git checkout --`, and `cmp` against the pre-test copies shows them identical (`MATRIX-RESTORED`). Afterwards `git status`
shows only the pre-existing `?? deploy/installer/__pycache__/`, and the nested repos are clean. No tracked code, config or
git state was changed and nothing was committed. The synthetic tests ran in
`/Users/manishsv/.claude/jobs/8ad4875a/tmp/f2tree` (a scratch copy).

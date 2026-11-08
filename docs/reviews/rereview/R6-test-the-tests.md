# R6 — Testing the tests (mutation pass over `make verify`)

Independent reviewer, 2026-11-08, HEAD 5e4ce7e. Each check that `make verify` runs got one deliberately broken change. Every change was made to a copy where the check accepts an override, or to a tracked file that was restored with `git checkout` right after. Live mutations were reversed and the reversal was confirmed. Scratch copies are in `/Users/manishsv/.claude/jobs/8ad4875a/tmp/rereview/mut/`.

## Results

| # | check | mutation (exact) | command | result | note |
|---|---|---|---|---|---|
| 1 | banned | appended `DB_PASSWORD = os.environ.get("DB_PASSWORD", "hunter2secret")` to kernel/services/authz/decide.py | `python3 verify/banned_patterns.py` | **FAILED as expected** (rc 1, LITERAL_SECRET_OR_GATE) | PROD_SHADOW_OR_INPROCESS is vacuous for production config: "production config files found: 0" (the check says so itself) |
| 2 | gtw-static | appended `# rate_limit: TODO (mutation)` to platform-spec/reference/model_gateway.py (a comment, not a fix) | `python3 verify/gtw_static.py` | **STAYED GREEN** (rc 0). GTW-4 flipped XFAIL→XPASS | Exits 0 every time. It is evidence only, never a gate. Detection is a keyword search, so a comment fakes a fix. See R6-3 |
| 3 | known-violations | `_NAT_KEYS = (` → `_NAT_KEYS  = (` (one extra space) in kernel/api/app.py | `python3 verify/known_violations.py` | **STAYED GREEN** (rc 0). FND-6/REG-13 flipped XFAIL→XPASS | Same as gtw-static: exact-text match, and it always exits 0. See R6-3 |
| 4 | decide-unit | decide.py:107 fail-closed `d.allow, … = False,` → `True,` (source down ⇒ allow) | `cd kernel && python3 services/authz/test_decide.py` | **FAILED as expected** (AssertionError at the "source down → fail closed" line) | — |
| 5 | secret-names | in a copy of platform-spec/reference: secret_names.check_component lost the `".." in value` and `/./` segment checks | `docker run … -v mut/ref:/r:ro … python /v/secret_names_test.py` | **FAILED as expected** (rc 1, 9 failures) | — |
| 6 | gateflags | prod-guard copy: removed `\|\| [ "$_ENV" = "prod" ]` | `PG=mut/pg.sh python3 verify/gateflags_test.py` | **FAILED as expected** (rc 1; 'PROD' and 'prod' started with a shadow flag) | — |
| 7 | build-context | kernel .dockerignore copy without `**/*.env` | `IGNORE_KERNEL=mut/kernel.dockerignore python3 verify/build_context_test.py` | **FAILED as expected** (rc 1, canary 1/8 reached the daemon) | Canaries go into the real working trees (kernel/zz-b94-canary etc.) for the duration of the run. They were cleaned up, but a concurrent `git add -A` or build could pick them up |
| 8 | images | (a) appended `requests>=2.0` to network/deploy/requirements.lock | `python3 verify/images_test.py` | **FAILED as expected** (rc 1) | — |
| 8b | images (extra) | appended `RUN pip install --no-cache-dir flask` to network/deploy/Dockerfile | same | **STAYED GREEN** (rc 0) | The lock check only requires the lock file's name to appear somewhere in the Dockerfile. An extra unpinned `pip install <pkg>` passes. See R6-5 |
| 9 | fresh-install | **reasoned, not run.** Would catch: a broken decision sink (no allow/deny row in kernel_authz_decision), because Phase 15 queries counts ≥1 on a proven-new DB volume. Would NOT catch: host-side state reused across "fresh" installs. `deploy/local-dev/.env` (POSTGRES_PASSWORD) is never removed and is read back by install.sh:171. The freshness proof only covers docker containers, volumes and networks | read verify/fresh_install.sh + deploy/installer/install.sh | reasoned | See R6-6 (Low) |
| 10 | conformance | `raise SystemExit(2)` inserted as the first line of `main()` in conformance/run.py, so the suite runs **nothing** | `bash verify/conformance_matrix.sh 1` | **STAYED GREEN** (rc 0, "✓ conformance both modes: 0 FAIL…"; tallies PASS=16/65 read from the 15:40 results file left in the container) | run.py is called with `\|\| true`. The tally then reads `/tmp/conf/results/local-dev-<mode>.json` from an EARLIER run, which is never deleted or freshness-checked. That stale file is then copied into conformance/results/. See **R6-1 (High)** |
| 11 | flowmap | `docker network connect aos-data-facts airawat-ld-notify` (then disconnected) | `python3 conformance/flow_map_test.py` | **FAILED as expected** (rc 1; ARC-1 membership + ARC-3 postgres reached from notify) | Runtime 75 s. DECLARED is hard-coded in the test, not read from ARCHITECTURE-FLOWS (unlike netdoors). Note only |
| 12 | vaultscope | live svc-workflow policy widened with `path "secret/data/localdev/kernel-app/*" { capabilities = ["read"] }`, then rewritten from the file | `python3 conformance/vault_scope_test.py` | **FAILED as expected** (rc 1; workflow foreign path → 200) | Each tight service is probed against ONE foreign path. Widening to a different foreign path (e.g. workflow → decision's password) would not be probed. See R6-7 (Low) |
| 13 | netdoors | ARCHITECTURE-FLOWS net-doors table: `/v1/keys/resolve` callers `decision, workflow` → `workflow` | `python3 conformance/net_doors_test.py` | **FAILED as expected** (rc 1; undeclared admitted ['decision']) | Both declared callers got **500** on /v1/keys/resolve and were counted "admitted" (admitted = any status except 401/403). A door that errors for its declared callers still passes. See R6-8 (Low) |
| 14 | routes | added `if self.path == "/debug/dump": return self._send(200, {"env": dict(os.environ)})` to notify.py do_GET | `python3 verify/route_inventory_test.py` | **FAILED as expected** (rc 1, UNDECLARED notify GET /debug/dump) | Stdlib route discovery is static AST over literal comparisons. Dict- or table-dispatched routes would be invisible (not tested) |
| 15 | listen | compose nginx `ports: [ "127.0.0.1:8080:80" ]` → long syntax `ports: [ { target: 80, published: 8080 } ]` (binds 0.0.0.0) | `python3 verify/listen_test.py` | **STAYED GREEN** (rc 0) | Control: the short form `"8080:80"` FAILED as expected. The static regex only parses short `host:container` strings, so long syntax and a bare `"80"` (random host port, all interfaces) are skipped. The LIVE half would catch it once deployed. See R6-4 |
| 16 | scans | uncommitted `creds.py` with an AWS-style key pair. Run on a scratch git repo (mut/glrepo) with the same gitleaks image + `detect --source` flags scans.py uses, then committed and run again | `docker run zricethezav/gitleaks:v8.21.2 detect --source /repo …` | uncommitted: **GREEN** (rc 0). committed: **FAILED** (rc 1) | Works as designed (history scan). Secrets in the working tree are not seen until committed. scans.py was not run against the five repos (trivy is slow). conformance/results/local-dev-scans.json has `"cases": []`, so scans give the matrix nothing. See R6-9 (Low) |
| 17 | matrix | rewrote one PASS case in conformance/results/local-dev-internal.json as FAIL (FND-11), with the XPASS results from rows 2–3 still present | `python3 conformance/build_matrix.py` | **STAYED GREEN** (rc 0; tally showed REGRESSION 1, REVIEW 3) | build_matrix always exits 0. It is a report generator, not a gate, so REGRESSION/REVIEW never fail `make verify`. See R6-2 |

## Findings (checks that stayed green)

- **R6-1 — conformance passes without running the suite, on stale results.** Severity **High**. Owning layer L1. Blocks L1 exit: **yes**.
  - The mutation was `raise SystemExit(2)` at the start of `main()` in conformance/run.py. `make conformance` still printed "✓ conformance both modes", exit 0.
  - Cause, in verify/conformance_matrix.sh:
    - run.py's exit code is discarded (`|| true`).
    - The tally is read from `/tmp/conf/results/local-dev-$m.json`, which persists in the long-running network container from earlier runs.
    - That stale file is then `docker cp`'d into conformance/results/ and feeds the matrix.
  - Any crash, preflight failure or import error in run.py therefore reports the previous green run.
  - Fix: delete the container results before each mode, fail on a missing file, and check that the file's `ts`/`git_sha` belong to this run. Keep run.py's exit code; at minimum, fail on 2 (preflight).
- **R6-2 — matrix never fails.** Severity **Med**. L1. Blocks L1 exit: **yes**.
  - `make verify` ends with build_matrix.py, which exits 0 even when the matrix contains REGRESSION or REVIEW.
  - That is acceptable only if every result-producing check gates on its own. gtw-static, known-violations (R6-3) and conformance (R6-1) do not, so a REGRESSION or REVIEW can reach the published STATUS-MATRIX with `make verify` green.
  - Fix: exit non-zero on REGRESSION, on REVIEW, and on a results file older than the current run or missing.
- **R6-3 — gtw-static and known-violations always exit 0, and detection is exact-text.** Severity **Med**. L1. Blocks L1 exit: **no** (it is honest only if R6-2 is fixed).
  - A comment (`# rate_limit`) or one extra space (`_NAT_KEYS  = (`) turns XFAIL into XPASS, i.e. "looks fixed". The only consequence is REVIEW in the matrix, which nothing gates.
  - Fix: fail on XPASS, so a real fix forces a deliberate spec/baseline update. Also anchor the detectors to AST or semantics rather than substrings where cheap.
- **R6-4 — listen static check misses compose long-syntax and port-only publications.** Severity **Low**. L1. Blocks L1 exit: **no**.
  - `ports: [ { target: 80, published: 8080 } ]` and `- "80"` both bind 0.0.0.0 and pass the static half. The live half catches it only once the stack runs that compose.
  - Fix: parse the YAML (`docker compose config --format json` normalises everything to `host_ip`/`published`).
- **R6-5 — images: an extra unpinned `pip install <pkg>` in a Dockerfile passes.** Severity **Low**/**Med**. L1. Blocks L1 exit: **no**.
  - The lock check only asks that the lock file's name appear somewhere in the Dockerfile. It does not check that every `pip install` installs only from `-r <lock>` (plus pinned tooling).
  - B80's "installs Python dependencies only from a lock file" is therefore not enforced.
- **R6-6 — fresh-install freshness proof ignores host-side state (reasoned).** Severity **Low**. L1. Blocks L1 exit: **no**.
  - `deploy/local-dev/.env` (Postgres superuser password) and other host files the installer reads survive the "proven-empty slate". The installer consistency check at install.sh:171 only covers the case where the volume exists but the .env is missing.
- **R6-7 — vaultscope probes one foreign path per service.** Severity **Low**. L1. Blocks L1 exit: **no**.
  - A policy widening to any other platform path is not probed.
  - Fix: use `sys/capabilities-self` across the full list of other services' paths, as the broker checks already do.
- **R6-8 — netdoors treats 5xx as "admitted".** Severity **Low**. L1. Blocks L1 exit: **no**.
  - /v1/keys/resolve answered 500 to both declared callers (decision, workflow) in the live run, and the test passes that.
  - Fix: require a 2xx/4xx-other-than-auth for declared callers, or report 5xx separately.
  - The 500 itself deserves a look: the declared callers of the keys door may be broken today.
- **R6-9 — scans contribute nothing to the matrix, and secrets are seen only after commit.** Severity **Low**. L1. Blocks L1 exit: **no**.
  - `local-dev-scans.json` has an empty `cases` list.
  - gitleaks runs in git mode, so working-tree secrets are not seen. That is by design, but nothing says so.

Vacuous or weak, noted but not failures:
- banned PROD_SHADOW_OR_INPROCESS: 0 production config files exist yet. It reports this honestly.
- conformance: SKIP_BUILD 46 (external) and 67 (internal) cases are not gated.
- flowmap: ARC-4 is reported PLANNED, never ✓.

## Restore confirmation

Every tracked-file mutation was reverted with `git checkout`. The live network connect was reversed: airawat-ld-notify is on `aos-svc` only again. The container's /tmp/conf/run.py was replaced with the clean file (grep MUTATION = 0). Results files I overwrote (flowmap, listen, netdoors, routes, vaultscope) were restored from the pre-run backups. STATUS-MATRIX.md/.json were restored with `git checkout`.

**Not mine:** local-dev-knownviolations.json was rewritten at 22:03:58 by another process, so I left it. **Also not mine:** root-repo `M docs/consolidation/DEBT-REGISTER.md` and `M verify/known_violations.py` appeared mid-session from a concurrent editor. I did not touch them; they were absent at the start.

```
== .
 M docs/consolidation/DEBT-REGISTER.md      (NOT mine — concurrent edit by another session)
 M verify/known_violations.py               (NOT mine — concurrent edit by another session)
?? deploy/installer/__pycache__/
?? verify/__pycache__/
== platform-spec
== kernel
== network
== components
```

Live Vault policies compared with `vault policy read <n> | diff - deploy/local-dev/vault/policies/<n>.hcl`, all 10 identical: svc-app-host, svc-decision, svc-identity, svc-kernel, svc-model-gateway, svc-network, svc-runtime-manager, svc-scheduler, svc-secrets, svc-workflow. svc-workflow is the one I widened, and it was rewritten from its file.

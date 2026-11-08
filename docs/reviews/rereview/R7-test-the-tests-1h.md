# R7: testing the tests after slice-1h (mutation pass over `make verify`)

Independent reviewer, 2026-11-08. HEADs: root 81329b7 · platform-spec 98b0e72 · kernel b3b6373 · network 0c9b094 · components 8cef04a.

**Method.** Each of the 22 checks that `make verify` runs got at least one deliberately broken change, and every case was actually run, the fresh install included. Each change went one of three ways:
- into a scratch copy, through the override the check accepts;
- into a tracked file, reverted with `git checkout` right after;
- into the live stack, reverted and confirmed.

The cases ran one at a time. Afterwards a full control run was done: `make -k verify AOS_RUN_ID=r7-base`, log in `r7/logs/30-make-verify-control.log`.

**Where things are.** Scratch copies are in `/Users/manishsv/.claude/jobs/8ad4875a/tmp/rereview/r7/mut/`. Every log is in `…/r7/logs/`, and every row below names its log.

## Results

| # | check | mutation (exact) | command | result | note |
|---|---|---|---|---|---|
| 1 | banned | appended `_mut_roles = (lambda claims: (claims or {}).get("roles"))` to kernel/api/app.py | `python3 verify/banned_patterns.py --json /tmp/r7-banned.json` | **FAILED as expected** (rc 1: `TOKEN_ROLES … NEW 1: kernel/api/app.py::_mut_roles …`) | Control is **red at HEAD**: LITERAL_SECRET_OR_GATE flags `deploy/installer/install.sh:132 ${AOS_VAULT_TOKEN_PERIOD:-1h}`. That is a false positive: TOKEN in a variable name, value `1h`. See R7-6. (01-banned.log) |
| 2 | gtw-static | (a) appended `# rate_limit: TODO (mutation)` to platform-spec/reference/model_gateway.py; (b) appended `rate_limit = None` (code); (c) renamed the target file away | `python3 verify/gtw_static.py` | (a) **stays XFAIL, rc 0**. This is correct: a comment no longer fakes a fix (R6-3 fixed). (b) **FAILED** (rc 1, XPASS needs attention). (c) **FAILED** (rc 1, "evidence target readable … missing") | R6 green, now fixed. (b) shows detection is still by keyword: any identifier `rate_limit` reads as a fix. It fails loudly now, so this only forces a review (02a/b/c) |
| 3 | known-violations | (a) `_NAT_KEYS = (` → `_NAT_KEYS  = (` in kernel/api/app.py; (b) `_NAT_KEYS` → `_NATKEYS_RENAMED` (the vocabulary stays, the target breaks) | `python3 verify/known_violations.py` | (a) **stays XFAIL, rc 0**. This is correct: the regex is whitespace-tolerant and the violation is still there. (b) **FAILED** (rc 1, XPASS needs attention) | R6 green, now fixed (03a/b) |
| 4 | decide-unit | decide.py:107 fail-closed `d.allow, … = False,` → `True,` | `cd kernel && python3 services/authz/test_decide.py` | **FAILED as expected** (AssertionError "source down → fail closed") | (04) |
| 5 | secret-names | REF copy: `secret_names._NoRedirect.redirect_request` now `return super().redirect_request(...)` (follows redirects) | `docker run … -e REF=/m -v mut/ref:/m:ro … python /v/secret_names_test.py` | **FAILED as expected** (rc 1; Vault 307 followed to kernel-app password; /fetch 302 leaked `Bearer fake-secret-value` to /leak) | Control on the real tree: 0 failures (05) |
| 6 | gateflags | PG copy of deploy/runtime/airawat-entrypoint.sh: `if [ "$_PROD" = 1 ]` → `= 2` (prod guard never runs) | `PG=mut/pg.sh python3 verify/gateflags_test.py` | **FAILED as expected** (rc 1; production started with FILESTORE_SHADOW='1','2','true',…) | (06) |
| 7 | build-context | `IGNORE_KERNEL` = kernel/.dockerignore without `**/*.pem` | `IGNORE_KERNEL=mut/kernel.dockerignore python3 verify/build_context_test.py` | **STAYED GREEN** (rc 0, "0 leak(s)") | The probe and canaries cover only .env/*.env/.env.*/.creds.json/init.json/approle/results/*.jsonl. They do not cover `*.pem`, `*.key`, `*creds*.json`, `pgdata`, `vault-data`, which the ignore file lists as secrets. Control mutation (R6's): dropping `**/*.env` **FAILED** (canary 1/8). See R7-4 (07, 07b) |
| 8 | images | (a) added `RUN pip install --no-cache-dir flask` after the lock install in network/deploy/Dockerfile; (b) IMAGES.lock.json platform-spec source SHA set to the commit before gateflags.py existed (the image then holds a file not in the recorded tree) | `python3 verify/images_test.py` | (a) **STAYED GREEN** (rc 0). (b) **FAILED** (rc 1; "untracked in image: reference/gateflags.py" + label mismatch) | R6-5 is still open (an unpinned `pip install` passes). The /app check compares file names only, not content. No image was rebuilt. See R7-3 (08, 08b) |
| 9 | installer | copy of install.sh with `\|\| true` removed from the `_bad_ports=` pre-flight line | `INSTALL=mut/install-nopf.sh python3 verify/installer_test.py` | **FAILED as expected** (rc 1; "host pre-flight completes … exit 1") | Run without `--live`: the copy lives outside deploy/installer, and the mutation is in the static half. Control `--live` (from `make`) is **red at HEAD** on any already-installed stack. See R7-6 (09, 09c) |
| 10 | fresh-install | deploy/installer/install.sh Phase 8: `post("/v1/registry/objects", …)` → `post("/v1/registry/objectz-MUTATION", …)` (that phase's write fails) | `verify/fresh_install.sh` (real, from a proven-empty slate) | **FAILED as expected** (rc 1; `✗ [phase8] /v1/registry/objectz-MUTATION -> 404` / `✗ install FAILED in phase: Phase 8 · network capability_catalog … (exit 1, line 77)`) | Reverted, then `verify/fresh_install.sh` ran again: rc 0, "fresh install passed from a proven-empty slate" (10-fresh-mut*, 10-fresh-clean*) |
| 11 | conformance | `raise SystemExit(2)  # MUTATION` as the first line of `main()` in conformance/run.py | `bash verify/conformance_matrix.sh 1` | **FAILED as expected** (rc 1; "run.py did not complete (exit 2)" in both modes) | R6-1 is fixed (11) |
| 12 | flowmap | `docker network connect aos-data-facts airawat-ld-notify` (then disconnected) | `python3 conformance/flow_map_test.py` | **FAILED as expected** (rc 1; ARC-1 membership + ARC-3 postgres reached from notify) | notify is back on `aos-svc` only (12) |
| 13 | vaultscope | live svc-workflow policy + `path "secret/data/localdev-operator/decision/*" { capabilities = ["read"] }` (a foreign path the test does not probe), then rewritten from the .hcl | `python3 conformance/vault_scope_test.py` | **STAYED GREEN** (rc 0, "Vault least-privilege PASS") | R6-7 is still open. Control: widening to the probed path `secret/data/localdev/kernel-app/*` **FAILED** (workflow → 200). See R7-5 (13, 13b) |
| 14 | vault-renewal | while the test ran its 5 × 60 s lifetimes, `mut/killrenew.sh` killed every `python… vault_renew.py` process in every project container every 5 s (12 kills logged) | `python3 verify/vault_renewal_test.py` | **FAILED as expected** (rc 1; tokens lapsed `OK 0 60`/`ERR 403`, vault_scope failed after the lifetimes) | The test's own `finally` restored the 1h period; every service healthy afterwards (14, 14-killer) |
| 15 | netdoors | ARCHITECTURE-FLOWS net-doors table: `/v1/keys/resolve` callers `decision, workflow` → `decision, workflow, scheduler` (a caller the door refuses) | `python3 conformance/net_doors_test.py` | **FAILED as expected** (rc 1; "declared refused ['scheduler']") | R6-8 is still open: keys/certificates/directory resolve answer **500** to their declared callers and are counted "admitted" (15) |
| 16 | dbgrants | `GRANT UPDATE ON kernel_admin_audit TO kernel_app` (then `REVOKE`) | `python3 verify/db_grant_audit.py` | **FAILED as expected** (rc 1; extra UPDATE; audit table not append-only) | Control rc 0. Grants are back to INSERT,SELECT (16) |
| 17 | routes | removed the declaration `filestore` `GET /files/*` (a helper-dispatched route found only by runtime discovery) from verify/route-inventory.json | `python3 verify/route_inventory_test.py` | **FAILED as expected** (rc 1; `UNDECLARED filestore GET /files/*`; runtime discovery found 41 routes source parsing missed) | Adding a route to a source copy would test nothing: the services run baked images and must not be rebuilt. Removing a declaration is the equivalent (17) |
| 18 | listen | compose nginx `ports: [ "127.0.0.1:8080:80" ]` → `ports: [ { target: 80, published: 8080 } ]`; extra: `ports: [ "80" ]` | `python3 verify/listen_test.py` | **FAILED as expected** for both (rc 1, "host_ip unset = all interfaces") | R6-4 is fixed (18, 18b) |
| 19 | ops | removed `logging: *logging` from the `postgres` service in docker-compose.dev.yml | `python3 verify/ops_test.py` | **FAILED as expected** (rc 1; "uncapped: ['postgres']") | Side finding: the rotation case also failed, and the unmutated control right after it failed the same way. The check is not re-runnable. See R7-7 (19, 19-control) |
| 20 | scans | (a) unknown mode `scans.py secret`; (b) copy with `TRIVY = "aquasec/trivy:0.0.0-does-not-exist"`, mode vulns; (c) copy whose trivy fs scan adds `--skip-dirs /src` (scans nothing) | `python3 verify/scans.py secret`; `python3 verify/zz_scans_mut.py vulns` (temp copy in verify/, deleted) | (a) **FAILED** (rc 2, "nothing scanned"). (b) **FAILED** (rc 1, every image + manifest "scan failed"). (c) **STAYED GREEN** (rc 0, "trivy scanned … every repository manifest (5/5)") | Worse than (c): the **real** manifest scan already scans nothing. Trivy logs `Number of language-specific files num=0` for network, kernel, platform-spec, root and components, because `requirements.lock` is not a name trivy recognises. See **R7-1** (20a/b/c) |
| 21 | restore-drill | deploy/local-dev/backup.sh `VOLS=` without `localdev_vault_audit` | `python3 verify/restore_drill.py` | **STAYED GREEN** (rc 0, "6 volumes … restored, stack healthy") | The drill passed while the whole Vault audit history (~160 MB, audit.log + .1 + .2) was destroyed. Afterwards only a fresh 577 KB audit.log existed. The drill marks only pg/vault/identity/filestore/appbundles and never checks that the backup covers every compose volume. See R7-2 (21) |
| 22 | matrix | on the coherent r7-base evidence set: (a) flowmap `run_id` set to an old run; (b) local-dev-listen.json deleted; (c) one internal PASS case → FAIL; (d) netdoors `cases: []` | `AOS_RUN_ID=r7-base python3 conformance/build_matrix.py --strict` | **FAILED as expected** for all four (rc 1; STALE / MISSING / FAIL / EMPTY problems each added) | R6-2 is fixed. The baseline problem (banned FAIL) was present in every run, and each mutation added exactly its own problem (22a–d) |

## Count

The primary mutation is the first one listed in each row. **17 of 22 checks fail on it.**

Five checks stayed green on a mutation they exist to catch: build-context, images, vaultscope, scans, restore-drill.

All six of R6's green checks now fail on their R6 mutation: conformance, matrix, gtw-static, known-violations, listen, and scans (unknown mode and scanner cannot run). scans stays green on an empty scan, though; see R7-1.

## Findings

### Checks that stayed green

- **R7-1: the scans net's dependency-manifest half scans zero files.** Severity **Med**. Layer L1. Blocks L1 exit: **no**, but it must not be counted as evidence.
  - `trivy fs` over each repository reports `Number of language-specific files num=0`.
  - The Python lock files are named `requirements.lock`, which trivy does not parse. `network/deploy/requirements.txt` holds only `>=` ranges, which trivy skips.
  - Result: the case "trivy scanned … every repository manifest (5/5)" and "no HIGH/CRITICAL dependency CVE" pass vacuously.
  - A mutation that skips everything (`--skip-dirs /src`) is indistinguishable from today's run.
  - The image scans do cover installed packages. But only CRITICALs fail there; HIGHs are counted, not failed.
  - Fix:
    - point trivy at the lock files explicitly (rename or symlink to `requirements.txt`, or `--file-patterns 'pip:requirements.*\.lock'`);
    - fail when the number of scanned language files is 0 for a repository that has one.
- **R7-2: the restore drill does not prove that every volume came back.** Severity **Low/Med**. L1. Blocks L1 exit: **no**.
  - With `localdev_vault_audit` dropped from backup.sh, the drill passed and the audit log history was lost.
  - The drill has no mark in the audit volume or `localdev_netfiles`, and never compares the backup manifest with the compose volume list.
  - `ops` does catch a VOLS list in backup.sh that misses a volume. It does not catch a restore.sh that skips or mis-restores one.
  - Fix: mark every volume (or checksum each volume before and after), and fail if the manifest's volume set differs from `docker compose config` volumes.
- **R7-3: images: an extra unpinned `pip install <pkg>` still passes (R6-5 open).** Severity **Low/Med**. L1. Blocks L1 exit: **no**.
  - The lock check only requires the lock's file name to appear somewhere in the Dockerfile.
  - Separately, the /app-equals-git-tree check compares file *names* only. A tracked file whose content differs in the image would pass. The B101 note says "/app proven equal", but only the file list is proven equal.
- **R7-4: build-context covers only some secret patterns.** Severity **Low**. L1. Blocks L1 exit: **no**.
  - Dropping `**/*.pem` (likewise `**/*.key`, `**/*creds*.json`, `**/pgdata`, `**/vault-data`) from an ignore file goes unnoticed. The probe's `find` and the canaries do not include those kinds.
  - Fix: derive the canary and probe list from the security block of each ignore file, or add the missing kinds.
- **R7-5: vaultscope probes one foreign path per service (R6-7 open).** Severity **Low**. L1. Blocks L1 exit: **no**.
  - workflow widened to read decision's password passed.
  - Fix: apply the brokers' `sys/capabilities-self` sweep over all platform credential paths to every tight service.

### Found while running controls (not mutation survivors)

- **R7-6: `make verify` is red at HEAD before any mutation.** Severity **Med**. L1. Blocks L1 exit: **yes**. The green claimed for slice-1h cannot be reproduced, for two independent reasons:
  1. **banned**: LITERAL_SECRET_OR_GATE flags `deploy/installer/install.sh:132 token_period=${AOS_VAULT_TOKEN_PERIOD:-1h}`. It is a false positive: the shell-default rule keys on `TOKEN` in the variable name. This line arrived in d6b47f1.
     - In the control run the strict matrix's only problem was `local-dev-banned.json: FAIL`.
  2. **installer `--live`**: it runs the real installer against the stack that is already up. On any stack that has completed an install, the installer stops in "bring-up: operator install config" with "the admin bootstrap password was scrubbed after the first install (ADR-0131); re-run with OPERATOR_PASSWORD=…".
     - Both fault cases therefore report the wrong phase and the net fails. This was reproduced directly (09c).
     - `installer` runs *before* `fresh-install` in `make verify`, so it only passes on a host with no stack, or with OPERATOR_PASSWORD exported.
  - Fix:
    - narrow the shell-default rule (exclude `*_PERIOD`/`*_TTL`, or require a credential-shaped value);
    - run the installer live test after fresh-install with the operator password from Vault, or on a throwaway project.
- **R7-7: the ops rotation case is not re-runnable.** Severity **Low**. L1. Blocks L1 exit: **no**.
  - "rotated" is `size(audit.log.1) > limit`. A previous run leaves a large audit.log.1 (only .2–.9 are cleaned up), so the next run sees "rotated" after 5 s, before the 60 s rotation loop has acted. "fresh" then fails, because audit.log is still over the limit.
  - In this session: the mutated run and the unmutated control right after it both failed this case. It passed again only on a fresh audit volume.
  - Fix: record the inode or mtime of audit.log.1 before pushing, or remove .1 first.
- **R6-8 is still open (netdoors)**: declared callers that get **500** count as admitted.
  - Affected: `/v1/keys/resolve` (decision, workflow), `/v1/certificates/resolve` (scheduler, launcher) and `/v1/directory/resolve` (kernel, app-host, scheduler).
- **verify-fast cannot pass the strict matrix.** Reasoned from code, not run.
  - `functional` is a REQUIRED net, but only installer Phase 15 writes it, and `clean-results` deletes it first. So `make verify-fast` (no fresh install) always ends with "MISSING evidence … functional".
- **scans ignores an unknown flag.** `scans.py --update-baselin` (typo) silently ran a full scan. It is harmless, but it is the same fail-open shape that R3-6 closed for modes.

## Restore evidence

At the end of the session, from `r7/restore-evidence.txt`:

```
== . (81329b7)            (clean; only untracked __pycache__ ignored)
== platform-spec (98b0e72)
== kernel (b3b6373)
== network (0c9b094)
== components (8cef04a)
== Vault policies (live `vault policy read` vs deploy/local-dev/vault/policies/*.hcl)
  svc-app-host, svc-decision, svc-identity, svc-kernel, svc-model-gateway, svc-network,
  svc-runtime-manager, svc-scheduler, svc-secrets, svc-workflow: identical (10/10)
== kernel_app table grants
kernel_admin_audit|INSERT,SELECT
kernel_authz_decision|INSERT,SELECT
kernel_kv|DELETE,INSERT,SELECT,UPDATE
registry_schema_meta|DELETE,INSERT,SELECT,UPDATE
registry_version|DELETE,INSERT,SELECT,UPDATE
== notify networks: aos-svc   (all containers' membership = declared map: flowmap PASS in the r7-base control run)
== docker ps (project airawatos-localdev): 16 × "Up … (healthy)" + airawat-ld-nginx "Up" (no healthcheck defined)
```

### Notes on what changed during the session

- **Stack rebuilds.** The stack went through:
  - two fresh installs (one mutated and failed at Phase 8, one clean that passed);
  - my restore drill;
  - the control `make -k verify` (its own fresh install and restore drill);
  - one installer re-run reproducing R7-6 (stopped in the bring-up phase; policies were rewritten from the files, and AppRole env files rewritten).
- **Vault audit history.** The audit history from before the mutated drill was lost by case 21. That loss is the finding itself; it was dev-stack filler.
- **Results and matrix files.** conformance/results/ was put back to its pre-session contents (copied back from `r7/results-backup/`). The coherent r7-base evidence set is kept in `r7/results-r7-base/`. docs/specs/STATUS-MATRIX.{md,json} were restored with `git checkout`.
- **Not changed.** No image was rebuilt or retagged, and nothing was committed or pushed.

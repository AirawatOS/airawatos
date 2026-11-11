# Layer 1 — FOCUSED exit review of slice 1h

Date: 2026-11-09. Scope: the eleven slice-1h items ([LAYER1-EXIT-REREVIEW](LAYER1-EXIT-REREVIEW.md) §8 conditions;
slice-1h commits). Findings only — no code changed by the review; the commit carrying this file adds debt rows
(DEBT-B116–B137) and two matrix-honesty evidence cases (FND-16, NET-12). Findings outside slice 1h are routed to FIX-PLAN
under their owning layer and do not affect the verdict.

**Verdict rule (set by the brief):** PASS only if no Layer-1-owned finding of Medium or higher remains.

**Reviewers** — five fresh agents that built no part of Layer 1 and took part in neither earlier review, briefed with the
re-review and the slice-1h commits only. Non-destructive reviewers ran in parallel; destructive and mutation work ran alone.

| Reviewer | Scope | Report |
|---|---|---|
| F1 | production guard, citizen rows (every list/filter), join code, audit tables via every DB role | [final/F1](final/F1-guard-citizen-join-audit.md) |
| F2 | evidence integrity: forged run id, mixed-run, partial run, matrix strictness | [final/F2](final/F2-evidence-integrity.md) |
| F3 | reproducible build from a CLEAN CLONE in another directory | [final/F3](final/F3-reproducible-build.md) |
| F4 | installer partial failures, Vault renewal under restart / blip / Vault restart / skew, backup-restore with a running stack and corrupted archives | [final/F4](final/F4-installer-vault-restore.md) |
| F5 | independent mutation of every `make verify` check (own design, all cases run incl. the fresh install) | [final/F5](final/F5-mutation.md) |

## Verdict: **FAIL** — Layer 1 does not exit

Every slice-1h item holds against the routes its own regression test covers, and much more held under attack (below).
But **fourteen Layer-1-owned findings of Medium or higher remain** (one High), all inside slice-1h scope. Most are
"the fix is right for the case tested, wrong for a neighbouring case": a guard that matches one spelling of an argument,
a restore that validates what the manifest lists rather than what it extracts, a healthcheck that is silent before the
first token, nets that check one representative path. The conditions to PASS are in §5.

## 1. Layer-1-owned findings, Medium or higher (block exit)

| ID | Sev | 1h item | Finding | Evidence (summary — full commands in the reports) | Debt |
|---|---|---|---|---|---|
| F5-1 | **High** | 9 matrix / DB audit | The DB-grant audit reads DIRECT grants only — UPDATE/DELETE on both audit tables granted to `kernel_app` through a NOLOGIN group role WORKED and every case passed, incl. "append-only" | F5 mutation, live; sequences not audited either (F1-11) | B131 |
| F1-1 | Med | 3 guard | Production argument check bypassable: argparse accepts abbreviations (`--no`, `--vault-t=`); `sh -c "…"` commands never inspected | live: `app_host.py … --no` started in production, guard said "no dev conveniences detected" | B116 |
| F2-1 | Med | 5 evidence | Strict matrix never checks the recorded git heads; dirty or mixed-commit evidence accepted | live: `AOS_RUN_ID=<old> make banned matrix` → ✓ STRICT with files from two commits | B117 |
| F2-2 | Med | 5 evidence | Case counts not baselined — any non-zero count passes | dropping 67 SKIP_BUILD cases raised HELD 5→17 with strict green | B118 |
| F4-1 / F4-2 | Med | 8 restore | `restore.sh` validates only the archives the manifest LISTS, then extracts every `*.tgz`; host secrets not checked before `down -v` | empty manifest + corrupt pg archive → "✓ 0 archives match", stack destroyed, Vault volumes gone; missing `host/.env` → destroyed then `cp` fails | B124 |
| F4-3 | Med | 2/8 | Healthcheck "healthy" while a service has NO Vault token (AppRole login failing); restore's wait ignores restarting containers | bad secret-id: decision crash-looping (exit 96) shown `(healthy)`; restore printed "✓ … stack healthy" | B125 |
| F4-4 | Med | 8 backup | A failed backup leaves the stack stopped, no ✗, no manifest | one tar failing | B126 |
| F4-5 | Med | 1 installer | A helper step can fail and the installer still prints "install complete" | `seed_base_os.py MODE=shelf` exits 0 with "0/1 tenant shelves set" after a 401; `_FAILS` covers only inline heredocs | B127 |
| F4-6 | Med | 2 Vault | A Vault outage longer than one token period is never recovered | 30 s periods + 64 s Vault stop → loud + unhealthy, never recovers (no re-login, restart policy ignores health) | B128 |
| F5-2 | Med | 5 nets | Vault scope check misses non-`secret/` mounts | `svc-decision` given `components/data/*` read every tenant's component secrets; check green | B132 |
| F5-3 | Med | 7 images | Images check matches only the literal `pip install` | unpinned `pip3 install requests` passed | B133 |
| F5-4 | Med | 8 drill | Restore drill never removes the host secrets, so restore to a new host is unproven | restore.sh with the `.env`/approle lines deleted passed | B134 |
| F5-5 | Med | 1 installer | Installer test misses a swallowed write in another spelling | `except … as err: return err.code` passed static + live fault injection | B135 |

## 2. Lower or other-layer findings (recorded and routed, do not block)

**Layer 1, Low/Info** (B119, B122, B123, B129, B130, B136):
- evidence: the run id is only a label; mode/env not validated; six nets write no evidence; `needs-build` kinds ignored when statuses are reduced; cases citing no rules; `--optional` used silently; tracebacks; provenance from the first file only (F2-3–F2-10);
- guard: a crashing parser is read as development (F1-2); `'d e v'` counts as development (F1-5);
- reproducible build (F3-1–F3-9): the claim "same commits give the same image ids" proved only a cache hit. A cold rebuild from a clean clone matched the running images in content (pip, Debian packages, every file in `/app` and `/opt/airawat`, the docker CLI, the image config); ids differ by timestamps. Also: `images_test` checks content for the reference image's `/app` only; the build script uses the selected builder and a working-directory-relative lock path; a floating frontend; host `__pycache__` and ingest logs ship; the Dockerfile header is stale;
- audit sequences writable by the runtime role (F1-11);
- restore: no age check, secret-ids never destroyed, env files 0644 (F4-9, F4-10); the EXIT trap prints the wrong line on a signal; Vault healthy while sealed for about 150 s; drill markers left behind (F4-12–F4-14);
- nets: banned misses a named-constant fallback; the route extractor ignores `add_api_route`; decide-unit leaves branches unexercised; the fresh install accepts an external volume; listen ignores `network_mode: host` (F5-6–F5-9).

**Layer 2, Low:** kernel's shadow switches don't call `is_production` (F1-3, B110).

**Layer 4, Medium — routed, not blocking:**
- **B120:** a citizen whose username equals a tenant id sees that tenant's rows. Reproduced live; XFAIL evidence on NET-12.
- **B121:** a pending join application can be overwritten by another applicant. Reproduced live.

Also Layer 4: the verify-code attempt race and DB-pool exhaustion from the edge (F1-8, F1-9).

**Pre-production:** development conveniences are refused only at the entrypoint (F1-4, B110).

## 3. What held under attack (selection)

- **Guard:**
  - every `AIRAWAT_ENV` spelling tried (casing, empty, zero-width, unicode, `developmentx`, `development;x`) is production;
  - gates refuse shadow in-process;
  - `gateflags.py` is present in the kernel and network images, with a production fallback.
- **Citizen rows:** random-name citizens are isolated on all 13 lists probed.
- **Join code:** never in a response, log or the page; resend throttling holds under casing and whitespace changes.
- **Audit tables:** every role is refused UPDATE / DELETE / TRUNCATE / ALTER / DROP / trigger / function; there are no SECURITY DEFINER functions, triggers or rules; no runtime service can reach the migrator or superuser credentials.
- **Evidence:**
  - a `run.py` crash or early exit is caught; other-run and old-format files read STALE;
  - zero, FAIL, XPASS and unknown result kinds are refused;
  - `matrix-fast` waives only the functional evidence;
  - a plain `make verify` admits only its own run's evidence.
- **Reproducible build:** content-identical from a clean clone; the dirty-tree refusal works for all five repos; no export-ignore, submodules or LFS.
- **Installer:** stops loudly and names the phase, never printing "install complete", when:
  - identity is killed mid-phase;
  - Vault is sealed mid-install;
  - Ctrl-C or SIGTERM is sent;
  - compose hits a port conflict;
  - a re-run is attempted without the password.
- **Vault renewal:**
  - a restarted service logs in again;
  - a short Vault restart is survived; a seal makes services unhealthy and they recover after unseal;
  - clock skew cannot affect renewal (relative TTL only).
- **Backup/restore:**
  - quiescing is real;
  - restore refuses before destroying anything on a flipped byte, a truncated or missing archive, or a missing manifest or directory;
  - the audit device and per-service Vault scope survive a restore;
  - RTO reproduced at 23 s.
- **Mutation (F5, 14 of 23 caught):** clean-results, gtw-static, known-violations, secret-names, gateflags, build-context, conformance, flowmap, vault-renewal, netdoors, listen, ops, scans and matrix each failed on an independently designed mutation.

## 4. Single-run `make verify` (proven-empty slate, no other containers)

**`make verify` PASSED** in one run (run `20261109T030733Z-8375b972`, 03:07–04:11 UTC by the host clock) from a proven-empty
slate (0 containers / 0 volumes / 0 networks of the project) with NO other container on the host (`docker ps` count of
non-project containers: 0). The strict matrix accepted only that run's evidence. Every net was green, from banned patterns
through the fresh install (with the Phase 15 functional proof) to the restore drill.

**A green run does not outweigh §1.** F5 shows that nine of these nets stay green under a breakage they exist to catch,
and F1/F2/F4 show the fixes hold only for the cases the nets cover. The run proves the current tree passes the nets as
written; the findings show where those nets are too narrow to carry the exit.

## 5. Conditions to PASS (remediation slice 1i — Layer-1 Medium+ only)

1. **B131:** the DB-grant audit checks EFFECTIVE privileges (`has_table_privilege`, role membership) for every role, plus sequence grants.
2. **B116:** each service itself refuses cert-skip and static-token options in production, in any spelling (abbreviations, `=` forms, `sh -c` wrappers). The guard treats a parser crash as a refusal.
3. **B117 / B118:** the strict matrix requires every file's git heads to equal the current HEAD (no `+dirty`), and checks a per-net case baseline including SKIP_BUILD ceilings.
4. **B124 / B126:** restore validates everything it will extract and copy before destroying anything; backup always restarts the stack and reports a failure.
5. **B125 / B128:** a service that declares Vault but has no token is unhealthy. A token lost past its period is recovered (re-login or container restart), and the runbook has the step.
6. **B127 / B135:** every helper the installer runs fails on a failed write. Fault injection happens inside writes, not only at phase banners.
7. **B132 / B133 / B134:**
   - Vault scope covers every mount;
   - the images check covers every installer spelling, or checks the built image's pip freeze against the lock;
   - the drill proves the host secrets come back.
8. `make verify` in one run on a proven-empty slate, then a re-review of these conditions only.

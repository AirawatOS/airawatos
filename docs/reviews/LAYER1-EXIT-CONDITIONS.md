# Layer 1 — CONDITIONS-ONLY exit re-review (slice 1i)

Date: 2026-11-09. Scope, frozen: the eight conditions of [LAYER1-EXIT-FINAL](LAYER1-EXIT-FINAL.md) §5 as implemented in
slice 1i (root `6a9e47f`; platform-spec `be155c9`, kernel `b3b6373`, network `030e4ae`, components `8cef04a`). Findings
only. No product code was changed by the review. The commit carrying this file contains:
- the reviewer reports;
- debt rows DEBT-B138 to B151;
- five matrix evidence cases (`verify/known_violations.py`), so the rules these findings break no longer read HELD;
- the regenerated matrix.

**Exit rule** ([FIX-PLAN §Layer exit standard](../consolidation/FIX-PLAN.md)): PASS if all eight conditions hold, with the
reviewers' original cases plus new neighbouring variants, and no High-severity Layer 1 finding exists. A NEW finding of
Medium or lower is registered with an owning layer and a deadline and does not block.

## Verdict: **FAIL**

Three of the eight conditions do not hold: **4** (restore), **6** (installer write guard) and **7** (the Vault-scope part).
In each, a variant of the original reviewer's case, in the same class, got through. Condition 8 ran green
(run `20261109T094332Z-ecf1ace6`, strict matrix green). No High-severity finding was raised. Every finding is Medium or lower, and each has an owner and a deadline.

| # | Condition (§5) | Result | Deciding evidence |
|---|---|---|---|
| 1 | B131: DB-grant audit by effective privilege, sequences included | **HOLDS** | The original group-role case and 13 privilege-route neighbours are caught. These include nested and NOINHERIT/SET roles, predefined roles, PUBLIC, column, TRIGGER/REFERENCES/TRUNCATE, ownership and BYPASSRLS. New Medium finding: owner-rights views and rules (C1-N1). |
| 2 | B116: production refuses cert-skip / static-token options in every spelling; a parser crash counts as a refusal | **HOLDS** | 25 cases. The original `--no`, `=`, `-m`, absolute path, `sh -c` with `exec -a`/`env`/quote splicing, Unicode dashes, interpreter crashes and a preset `VAULT_TOKEN` are all refused (97). Each service refuses on its own when the guard is bypassed. New Medium finding: `UVICORN_*` environment variables (C2-N1). |
| 3 | B117/B118: strict matrix requires HEAD equality with no `+dirty`, and a per-net case baseline with SKIP_BUILD ceilings | **HOLDS** | Both originals fail (mixed commits; dropped SKIP_BUILD). So do the neighbours: one repo off, a short SHA, an extra key, a dirty nested repo, a rename, PASS turned XFAIL, a missing or unknown mode, a SKIP_BUILD swap. New Low findings C3-N1 and C3-N2. |
| 4 | B124/B126: restore validates everything before destroying anything; backup always restarts and reports failure | **DOES NOT HOLD** | The originals (empty manifest with a corrupt archive; missing `.env`) are refused, and so are a corrupt archive with a rehashed manifest and a host file outside `host/`. SIGTERM mid-backup restarts the stack and exits 143. **But:** a self-consistent 6-of-7-volume backup restored with rc 0, "healthy", and the filestore volume came back empty (F-C4-1, the original F4-1 in substance). A backup without AppRole files passed validation and failed after `down -v`. An archive that lists cleanly but does not extract (an absolute symlink) destroyed the stack before failing (F-C4-2). |
| 5 | B125/B128: a Vault-declared service with no token is unhealthy; a lost token is recovered; runbook | **HOLDS** | The original case (Vault down for more than 2× a 60 s period): all 12 services went unhealthy, then recovered by controlled restart and re-login, all healthy 15 s after Vault was back. Vault sealed for more than 100 s, then a slow manual unseal: healthy 16 s after unseal. All services losing tokens at once recovered. A destroyed secret-id gives a loud FATAL restart loop. A real ~10 min host sleep (a clock jump) recovered unaided. The runbook section is present. New Low findings L-C5-1 and L-C5-2. |
| 6 | B127/B135: every installer helper fails on a failed write; fault injection sits inside writes | **DOES NOT HOLD** | The guard is copied into app-host and then removed by the app-host `--force-recreate` (install.sh:283, then :496). The shelf step, the original F4-5 case, therefore runs unguarded. With the fault aimed at the shelf login (`Phase 1c\|/realms/localdev-network/login`) it never fired, and the install ended rc 0, "✓ install complete". The shelf helper with a wrong password printed `SHELF DONE — 0/1` and exited rc 0. The slice's test passes only because its `Phase 1c\|/login` fault hits an earlier, network-side login (F-C6-1). Writes that time out are caught. |
| 7 | B132/B133/B134: Vault scope covers every mount; images check vs lock; drill proves host secrets | **DOES NOT HOLD** (Vault scope). Images and drill hold as worded. | Using decision's own token, the scope check missed five reads: a KV-v1 mount, a live TOTP code from a non-KV engine, a `list` of every secret name, `identity/entity/name`, and a sudo read of `sys/policies/acl/*`. The check stayed green (C7-N3). It did catch KV-v2 mounts, templated paths and group-attached policies. The images check catches the original pip spellings, but not a venv, a sitecustomize/.pth file, deleted dist-info, an unpackaged binary or an edited `/opt/airawat/commands.json` (C7-N4). The drill deletes `.env` and the AppRole files and hash-checks them on return. |
| 8 | `make verify` in one run on a proven-empty slate | **HOLDS** | Run `20261109T094332Z-ecf1ace6`, 09:43:26 to 10:14:12 UTC, rc 0. Every net was green, from a slate proven empty (0 containers, 0 volumes, 0 networks; no other container running on the host) through `build_matrix --strict`: 16 required nets, fresh evidence at the live clean HEAD of all five repos, case baselines held. Afterwards: still no non-stack container running, and the only change to the tree was the regenerated matrix. |

## New findings (all registered; none High)

The first four are what make conditions 4, 6 and 7 fail. Under the exit rule a condition that does not hold blocks the
exit whatever the finding's severity. They are therefore due **before Layer 2 starts**. The rest are routed and do not block.

| Debt | Finding | Sev | Owner | Deadline |
|---|---|---|---|---|
| **B138** | C7-N3: the Vault scope check misses KV-v1 mounts, non-KV engines, LIST-only grants, `identity/` paths other than entity/id, and sudo `sys/` reads. The KV-v1 canary is never deleted. | Med | L1 assurance net | **before Layer 2 starts** (condition 7) |
| **B139** | F-C4-1: restore checks the manifest against itself, not against the compose-declared volumes and AppRole files. A partial backup restores "healthy" with a volume emptied. | Med (operational) | L1 deploy/local-dev | **before Layer 2 starts** (condition 4) |
| **B140** | F-C4-2: restore's "test-extract" only lists the archive, so extraction failures (links, disk-full, undeclared volumes) happen after `down -v`. | Med (operational) | L1 deploy/local-dev | **before Layer 2 starts** (condition 4) |
| **B141** | F-C6-1: the installer write guard is silently absent in app-host after its recreate. The shelf, deliver and Phase-15 fixture helpers run unguarded, and the slice test targets the wrong login. | Med | L1 deploy/installer | **before Layer 2 starts** (condition 6) |
| B142 | C2-N1: `UVICORN_*` environment variables set any uvicorn option in production. kernel:1i started the reloader. | Med | L1 guard | before Layer 2 exit |
| B143 | C7-N4: the image check sees only pip metadata and dpkg (venv, sitecustomize/.pth, removed dist-info, raw binaries, `/opt/airawat` all unchecked). | Med | L1 assurance net | before Layer 2 exit |
| B144 | C1-N1: the DB-grant audit is blind to views and rules. A migrator-owned view or rule let kernel_app delete or rewrite audit rows, and an INSTEAD NOTHING rule drops them. | Med | L1 assurance net | before Layer 2 exit |
| B145 | C1-N2: WITH GRANT OPTION is not checked. C1-N3: database CREATE and `pg_default_acl` are not checked. | Low | L1 | C1-N2 before Layer 2 exit; C1-N3 before first production |
| B146 | C3-N1: a case can be swapped with counts unchanged (the baseline keys on name and count). C3-N2: untracked files are not "dirty". C3-N3: additions are unconstrained. | Low | L1 evidence | C3-N1 before Layer 2 exit; C3-N2 before first production |
| B147 | C7-N5: `os_packages` is recorded from the image just built. | Low | L1 | before Layer 2 exit |
| B148 | C2-N2: a static `TRUST_REGISTRY_TOKEN` is not refused in production. | Low | L1 guard / network | before first production |
| B149 | L-C5-1: the health check tests token validity, not Vault access (a deleted policy leaves the service healthy). L-C5-2: a login crash loop never shows "unhealthy". I-C5-1: HTTP 400 on an expired token is treated as retryable. | Low (operational) | L1 deploy/runtime | before first production |
| B150 | L-C6-1: the write guard covers only `urllib` in a normal interpreter (`http.client`, curl/wget, `-I`/`-S`, `os._exit(0)` bypass it); none is used for writes today. | Low | L1 deploy/installer | before first production |
| B151 | Info: C1-N4, C3-N3, C7-N6 (the network default CMD is refused in production, which fails closed), I-C4-1 (backup restarts a stack that was already stopped; a relative path gives a misleading refusal; archives are 0644). | Info | L1 | before first production |

**Matrix.** Five evidence cases were added to `verify/known_violations.py`, each matching on code. Each one reproduces a
finding demonstrated live, as an XFAIL:
- **ARC-3:** B139, B140 and B144. ARC-3 read HELD from the restore and append-only cases, and is now **PARTIAL**.
- **ARC-7:** B138. Already PARTIAL.
- **FND-16:** B142. FND-16 moves from PLANNED(needs-build) to PARTIAL; both are not-HELD, and the XFAIL now names the violation.

B141 and B143 cite no matrix rule and are tracked in debt only. The matrix was regenerated (non-strict) after the condition-8 run, from that run's evidence plus the re-run known-violation net. A strict run accepts the added cases, because the baseline flags only lost cases.

## Recommended next step (scope frozen, per the exit standard)

A remediation slice limited to B138 to B141, fixing each by class:
- validate against what compose declares;
- extract into staging before the destroy;
- a guard that cannot be silently absent;
- a scope check per engine type.

Then a conditions-only re-review of conditions 4, 6 and 7 alone. Conditions 1, 2, 3, 5 and 8 held and are not reopened.
B142 to B151 keep their deadlines.

## Method

Three fresh reviewer agents took part. None built any part of Layer 1, and none took part in the earlier exit review,
re-review or focused review. Each had a time box and the scope frozen to its conditions. Destructive work (restores,
Vault outages, installs) ran alone on the stack.

| Reviewer | Conditions | Report |
|---|---|---|
| C-A | 1, 3 | [conditions/C1-C3](conditions/C1-C3.md) |
| C-B | 2, 7 | [conditions/C2-C7](conditions/C2-C7.md) |
| C-C | 4, 5, 6 (destructive; ended with `verify/fresh_install.sh` passing from a proven-empty slate) | [conditions/C4-C6](conditions/C4-C6.md) |

Each reviewer restored what it changed:
- the live DB catalog snapshot matched before and after;
- every `svc-*` Vault policy was byte-equal to its `.hcl`;
- every AppRole `token_period` was back at 1h;
- no throwaway images, containers, mounts or volumes remained;
- all five repos were clean.

The scratch backups, which held the Vault root token, were deleted.

Condition 8 was run afterwards by the coordinator. The stack was torn down first: 0 running containers, 0 project volumes,
0 project networks, and no other container running on the host. Then `make verify` ran once.

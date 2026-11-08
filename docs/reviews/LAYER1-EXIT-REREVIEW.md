# Layer 1 — exit RE-REVIEW (after remediation slice 1g)

Date: 2026-11-08. Scope: the ten slice-1g fixes (exit conditions 1–13 of [LAYER1-EXIT-REVIEW](LAYER1-EXIT-REVIEW.md)),
the areas the first review did not cover, the verify tooling itself, the four items 1g left open, and a single-run
`make verify` from a proven-empty slate. Findings only — no code was changed by the review. The only non-review edits
in the commit that carries this file are the debt register (new DEBT-B96–B115) and two matrix-honesty evidence cases in
`verify/known_violations.py` (ARC-7, FND-16).

**Reviewers.** Six fresh, independent reviewer agents that neither built Layer 1 nor took part in the first review,
each briefed with the first review and the slice-1g commits only (not the builder's conclusions):

| Reviewer | Brief | Report |
|---|---|---|
| R1 | try to break B87 egress, B83 guard, B85 automation, B86 Network doors | [R1-walls-gates](rereview/R1-walls-gates.md) |
| R2 | try to break B88 transit, B89 brokers, B90 names, B92 nets, B93 matrix, B80/B94 images | [R2-keys-nets](rereview/R2-keys-nets.md) |
| R3 | uncovered: installer + scripts, the verify/ tooling, scheduler + runtime manager | [R3-installer-verify-runtime](rereview/R3-installer-verify-runtime.md) |
| R4 | uncovered: backup/restore, logs, error responses, time + token expiry | [R4-backup-logs-errors-time](rereview/R4-backup-logs-errors-time.md) |
| R5 | the four open items from 1g (amd64, kernel flag parsing, route extractor, DB-grant audit) | [R5-open-items](rereview/R5-open-items.md) |
| R6 | test the tests: one deliberate breaking change per `make verify` check | [R6-test-the-tests](rereview/R6-test-the-tests.md) |

Wave 1 (R1–R5) probed the live stack read-only in parallel; wave 2 (R6) ran alone because it mutates (every mutation
was reverted; R6 confirmed clean repos and live Vault policies equal to the files). The builder independently
re-checked the headline claims before recording them: R4-1 (live `lookup-self`: ttl 24 h, no renew code anywhere),
R1-1 (image `Entrypoint=null`; `svc_gate` has no `is_production`), R1-4 (`_row_is_callers` prefix match), R2-5
(`/app/reference/identity-users.json`, 53 users, gitignored).

## Verdict: **FAIL** — Layer 1 does not exit yet

All ten slice-1g fixes **hold against the attacks their tests did not cover** (§1) — none was broken. But the re-review
found, in areas the first review did not look at and in the verify tooling itself, **five High and nine Medium
L1-blocking findings** (§4): the platform stops working 24 h after start (R4-1); the gates do not refuse shadow under
production outside the dev compose (R1-1); citizen personal data leaks between citizens (R1-4, L4-owned but personal
data reachable from public sign-up); and the assurance nets can report green on stale or absent evidence (R6-1,
R3-5–R3-7, R6-2). These are mostly small, mechanical fixes; the conditions to PASS are listed in §8.

## 1. The ten 1g fixes — held or broken

| Fix | Attacks the regression test does not cover | Result |
|---|---|---|
| B95 loopback only | (listen test) long-form `ports: [{published: …}]` not parsed (R6-4) | **held live**; test gap Low |
| B87 default-deny egress | external DNS / DNS tunnel, UDP, IPv6, ICMP, 172.17.0.1, Docker VM 192.168.65.x, LAN IP, host.docker.internal, cross-network names, nginx as proxy, docker socket | **held**. Gaps: bridge-gateway IP reaches the Docker VM's rpcbind/statd (R1-6 Low); app-host `/bridge/fetch-file` follows redirects (R1-5 Med, L5) |
| B88 per-service transit | hmac/encrypt/export/backup/restore/trim/LIST, `..`/`%2e` key names, child tokens, AppRole cross-login | **held**. identity's `identity-*` glob allows rotate/config/trim on its own per-tenant keys (R2-9 Low) |
| B89 brokers → `components/` | other mounts, cubbyhole, sys/raw, kv-v1 paths, metadata destroy, cross-tenant broker/gateway HTTP calls; audit HMAC readable only by network | **held**. Not held for in-process components, which read the runtime manager's Vault token from `/proc/1/environ` (R3-1 High, L7/B51 — matrix ARC-7 corrected) |
| B90 secret names | fullwidth `．．／`, U+2024, `%2E`/`%252e`, `;`, `?`, `#`, CRLF, long names, run-token tenant | **held**. Trailing `\n` accepted → 500 not traversal (R2-10 Low); broker auth-login still follows 301–303 (R2-11 Low); `/fetch` template placeholder can rewrite the authority so a component's own key goes to an undeclared host (R2-1 Med) |
| B83 one flag parser | NBSP / tabs / unicode in `AIRAWAT_ENV`, other weakening env names, `--no-verify`, `--vault-token`, images without the compose entrypoint | **broken in part**: gates do not refuse shadow under production themselves; the shipped images carry no guard (R1-1 High); shell and Python disagree on "production" (R1-2 Med); guard fail-open when `AIRAWAT_ENV` unset/misspelt (R5-2 Med) |
| B85 automation /events | other tenants' `scheduler`, sub/tenant disagreement, list aud, expired, alg:none, HS256, path/method variants, 30 MB body | **held**. The declared caller is a principal shared by scheduler, automation and event-relay (R1-7 Med, L6) |
| B86 Network doors | trailing slash, `//`, case, `%`-encoding, `;`, query, other methods, undeclared callers, another realm's same-named principal, nginx `/network/` | **held** for the doors. But list **user mode** leaks every citizen's rows (R1-4 High, L4); netdoors counts a 500 as "admitted" and decision/workflow get 500 on `keys/resolve` today (R6-8) |
| B92 nets | role reads via variables, `**claims`, JS; literals in compose list form, Python dicts, JSON/TOML/INI, `curl -u`; gitleaks fail-closed via `--update-baseline` | **held for what it claims**; misses listed (R2-3 Med, R2-4, R2-12 Low). "N3 FIXED" overstated: the compose list form `- DB_PASSWORD=x` still passes |
| B93 matrix | every HELD row vs its spec status | NET-3/PTC-1/REG-5/FND-15 now PARTIAL (held). PLT-5 HELD vs spec PARTIAL — local-dev enforces the recorded role, so the spec text is stale (R2-2). ARC-3 DB-grant audit still not a case (R2-15, R5 item 4) |
| B80/B94 images | untracked files in the context, sensitive files in /app, unpinned inputs | **broken in part**: image ships gitignored `identity-users.json` (53 users) and local `dist/`/egg-info — not reproducible from git (R2-5 Med); docker CLI without checksum, locks without hashes, root user (R2-7, R5-6 Low) |
| B57 → Layer 2 | — | decision recorded; consistent with ARCHITECTURE-FLOWS §d |

## 2. Areas covered — first review vs this re-review

First review (four reviewers): walls (networks), keys (Vault policies), gates, service identity (badges), the
banned-pattern / route / scan nets, matrix honesty; assessments of reproducibility, DEBT-B82, Vault restore/rotation.

Deliberately reviewed here (not covered before): the installer and its scripts; the verify/ tooling and the matrix
pipeline; the scheduler, runtime manager and launcher; backup/restore of every durable store; logs and what they record;
error responses and what they disclose; time, token and Vault-token expiry; mutation testing of every net.

## 3. Test the tests (R6) — one deliberate breaking change per check

| Check | Mutation | Result |
|---|---|---|
| banned | new `(claims or {}).get("roles")` read | FAILED ✓ |
| gtw-static | violation text varied (`# rate_limit`) | **STAYED GREEN** (always exits 0; XFAIL→XPASS only) — R6-3 |
| known-violations | `_NAT_KEYS  = (` (extra space) | **STAYED GREEN** (exact-text evidence; always exits 0) — R6-3 |
| decide-unit | decision function admits a refused case | FAILED ✓ |
| secret-names | validator accepts `..` | FAILED ✓ |
| gateflags | guard treats "2" as off | FAILED ✓ |
| build-context | `.env` pattern removed from ignore | FAILED ✓ |
| images | unpinned line in a lock | FAILED ✓ — but an extra `RUN pip install flask` passes (R6-5) |
| fresh-install | (reasoned) host-side state such as `deploy/local-dev/.env` is not part of the empty-slate proof | gap — R6-6 |
| conformance | `raise SystemExit(2)` as the first line of `run.py main()` | **STAYED GREEN** — stale results counted (R6-1 **High**) |
| flowmap | notify connected to an extra network | FAILED ✓ |
| vaultscope | svc-workflow widened | FAILED ✓ (one foreign path per service only — R6-7) |
| netdoors | declared table edited | FAILED ✓ (500 counts as admitted — R6-8) |
| routes | undeclared route added | FAILED ✓ (extractor blind on helper-dispatched routes — R5 item 3) |
| listen | `ports: [{target: 80, published: 8080}]` | **STAYED GREEN** — R6-4 |
| scans | uncommitted planted key | **STAYED GREEN** (gitleaks scans history only); `local-dev-scans.json` has `cases: []` — R6-9 / R3-6 |
| matrix | a PASS case rewritten as FAIL | **STAYED GREEN** — `build_matrix.py` exits 0 on REGRESSION/REVIEW (R6-2) |

Vacuous: the banned check's production-config rule covers 0 files; 46 external + 67 internal conformance cases are
SKIP_BUILD and nothing gates on that count.

## 4. Findings that block Layer 1 exit

| ID | Sev | Finding | Evidence | Layer | Debt |
|---|---|---|---|---|---|
| R7-1 | **High** | Installer exits silently on a host with no 0.0.0.0 port (pipefail on an empty `grep`); every earlier green fresh install depended on an unrelated container's public ports | §7; `install.sh:302`, `set -euo pipefail` line 15 | L1 | B100 |
| R4-1 | **High** | Every service's Vault token expires 24 h after start; nothing renews it, re-login is impossible (`VAULT_SECRET_ID` unset after first login), failure is silent; runbook wrongly says tokens renew | live `auth/token/lookup-self` from identity: `ttl 84813`, `expire_time 2026-11-09T15:38Z`, renewable, no renew code in any repo; `install.sh:121` | L1 | B96 |
| R1-1 | **High** | Gates do not refuse shadow under production; only the local-dev compose entrypoint does; shipped images have no guard | `docker image inspect …reference:1g` → `Entrypoint=null`; `svc_gate.require()` never calls `is_production()`; live: `AIRAWAT_ENV=production FILESTORE_SHADOW=1` → `require()` False | L1 | B97 |
| R1-4 | **High** | Network list user mode returns every citizen's rows (credentials incl. eKYC VC, transactions, file shares, data requests) to any citizen | `network/api.py:392-399` matches any `user://<tenant>/` value; all citizens share tenant `citizens`; public sign-up `/embed/signup` → raw bearer. Proven with the extracted function, not live (no rows; no self-registration write) | L4 (blocks: personal data from public sign-up) | B98 |
| R6-1 / R3-5 | **High** | Conformance net green when the suite does not run | `conformance_matrix.sh` `run.py … \|\| true`, tallies `/tmp/conf/results/*.json` from an earlier run and copies it into the matrix | L1 | B99 |
| R3-6 | Med | Scans net passes with nothing scanned; recorded evidence empty | `scans.py` unknown mode → "0 failing"; `local-dev-scans.json` `"cases": []`; trivy/gitleaks tag-pinned | L1 | B99 |
| R3-7 / R6-2 | Med | Matrix trusts every results file and never fails | no freshness/sha check (8 of 12 nets write empty `git_sha`; results from two commits mixed); `build_matrix.py` exits 0 on REGRESSION/REVIEW | L1 | B99 |
| R3-8 | Med | Installer can print "✓ install complete" after failed phases | `_idt` empty token on error; phases 1b–9b ignore HTTP/Vault errors; phase 8 exit 0 on missing record; prod/rehearsal skip Phase 15 | L1 | B100 |
| R2-5 | Med | Reference image not reproducible from git: ships gitignored `identity-users.json` (53 users, 5 tenant-admins; identity's default users file) and local `dist/`/egg-info; no components SHA recorded | `docker run … ls /app/reference/identity-users.json`; `git check-ignore` → `.gitignore:5` | L1 | B101 |
| R4-7a | Med | No Vault audit device | `vault audit list` → none | L1 | B102 |
| R4-8 | Med | No log rotation / size limit on any container | no `logging:` block in any compose | L1 | B102 |
| R4-2 | Med | Backup set incomplete: identity volume (sole store of accounts + rotated passwords), filestore, app-bundles missing; no scripts | RESTORE-AND-ROTATION.md credential-state table | L1 | B102 |
| R5-3 | High (per R5) | Route extractor blind on helper-dispatched routes — the secrets service and the governance plane among them | R5 item 3 list | L1 | B104 |
| R2-15 / R5-4 | Med | ARC-3 DB-grant audit still not a case (exit condition 8; FIX-PLAN lists it as an L1 test) | R5 ran it read-only: roles least-privilege, but `kernel_app` can UPDATE/DELETE audit tables (R5-3 → B112) | L1 | B103 |
| R3-1 (honesty) | Med | ARC-7 read HELD while an in-process component reads the runtime manager's Vault token → launcher password → `/materialize` any secret | live in airawat-ld-runtime-manager (status 200). **Corrected in this commit: ARC-7 now XFAIL → PARTIAL** | L1 matrix / L7 fix | B103, B105 |
| R2-4 | Low | Exit condition 6's per-entry debt ids for the TOKEN_ROLES baseline not delivered | `verify/banned-baseline.json` file/line counts, one global note | L1 | B103 |

## 5. Findings that do not block Layer 1 exit (owning layer; debt)

High: **R3-1** in-process components read the host's Vault token (L7, B105).
Medium:
- R1-2 production definition disagrees (L1, B97);
- R1-3 / R5 item 2 weakening switches outside the guard (pre-production, B110);
- R1-5 `/bridge/fetch-file` follows redirects (L5, B106);
- R1-7 shared scheduler principal (L6, B105);
- R2-1 `/fetch` template placeholder (L6/L2, B106);
- R2-3 literal-check gaps (L1, B115);
- R2-8 decision/workflow signing fails open (L6, B113);
- R2-13 model-gateway key path/destination from registry records (L6/L2, B106);
- R3-2 tar-slip before the digest check (L5, B107);
- R3-3 federated delivery tokens (L4/L5, B107);
- R3-4 placed-container hardening (L5, B107);
- R3-9 secrets on argv (pre-production, B111);
- R4-3 run-tokens never expire, plaintext at rest (L2, B112);
- R4-4 lockout keyed on the edge IP (L3/L5, B108);
- R4-5 user enumeration (L3, B108);
- R4-6 / R5-1 join `dev_code` echoed (L4, B109);
- R5-2 guard fail-open when unset (with B97);
- R5-4 fail-open env parses (B110);
- R6-3 gtw-static/known-violations text-fragile (L1, B99).

Low/Info (B115 unless noted):
- R1-6, R1-8 (B107), R1-9, R1-10 (B108), R1-11, R1-12;
- R2-6, R2-7 (B111), R2-9, R2-10, R2-11 (B106), R2-12 (B99), R2-14;
- R3-10, R3-11, R3-14 (B111), R3-12, R3-13 (B99);
- R4-9 to R4-19;
- R5-5, R5-6 (B111), R5-7, R5-8 (no CI exists although the exit gate says "green in CI"), R5-9, R5-10, R5-11;
- R6-4 to R6-9.

Full evidence for every row is in the reviewer reports under [rereview/](rereview/).

## 6. The four 1g open items

| Item | Assessment | Verdict |
|---|---|---|
| amd64 image not proven | Every locked dependency installs for linux/amd64; only `import pyarrow` segfaults, under QEMU on the arm64 host (emulation). Kernel and network have no amd64 build either. Production target is EC2 amd64 | **blocks pre-production only** — native amd64 build recording all three digests (B114) |
| kernel's own flag parsing | kernel/network/identity parse their own switches; several weaken by absence (KERNEL_REQUIRE_AUTH off by default, PLATFORM_AUTHORITY_MODE default shadow, IDENTITY_PASSWORD_REQUIRED default shadow) and the guard cannot see weakening-by-absence | **pre-production** (B110), except the guard's own holes (unset AIRAWAT_ENV fail-open, R1-2 disagreement) which go with **B97 (blocks)** |
| route extractor (B92 N1) | misses privileged helper-dispatched routes on the secrets service and governance plane — the route net is blind where it matters | **blocks L1 exit** (B104) |
| DB-grant audit not in the matrix (B93) | audit run read-only: login roles least-privilege and only kernel/network/identity reach 5432; but `kernel_app` can UPDATE/DELETE audit tables; not a case | **blocks L1 exit** (exit condition 8; B103) |

## 7. Single-run `make verify` (proven-empty slate)

**`make verify` FAILED** (2026-11-08T16:40Z, one run): banned, secret-names, gateflags, build-context, images ✓; the
fresh install **tore the stack down to a proven-empty slate (0 containers / 0 volumes / 0 networks), then the installer
exited silently** right after the host pre-flight, so every later net did not run.

**R7-1 (High, L1, blocks exit) — the installer fails on any host that publishes no port on 0.0.0.0.**
`deploy/installer/install.sh:302`: `_bad_ports=$(docker ps … | grep -oE '0\.0\.0\.0:[0-9]+' | … )` under
`set -euo pipefail` (line 15). With no 0.0.0.0 publication anywhere, `grep` exits 1 and the shell exits with no message
(reproduced: `rc=1 bad=[]`). Every earlier green `make verify` (slice 1g, steps 13) passed only because an UNRELATED
container on the host (`rtsp-test-mediamtx`, another project) was publishing 0.0.0.0 ports at the time — i.e. the
"clean-slate" proof depended on foreign host state. The empty-slate fresh install therefore does **not** pass on a
clean host; this is exactly the R3-8 class (install failures not surfaced) and the R6-6 class (host-side state outside
the empty-slate proof). Fix: `|| true` inside the substitution (and an install-wide ERR trap that prints the failing
line). Not fixed here (findings only); the local-dev stack is left torn down by this run.

## 8. Conditions to PASS (remediation slice 1h)

1. **B96** services renew their Vault tokens and re-login before max TTL; a net proves a service survives a short TTL; runbook corrected.
2. **B97** every gate refuses shadow when `gateflags.is_production()`; the guard is the ENTRYPOINT of every image; one production definition shared by guard and services; unset/misspelt `AIRAWAT_ENV` fails closed outside an explicit development profile.
3. **B98** list user mode scoped by subject for shared realms; a two-citizen conformance case.
4. **B99** every net fails on stale or absent evidence: results deleted before each run, run exit code checked, `ts`/`git_sha`/case-count required; `build_matrix.py` fails on REGRESSION/REVIEW and on stale or mixed inputs; scans write real evidence and reject unknown modes; gtw-static/known-violations evidence by structure (AST/regex with whitespace tolerance), not exact text.
5. **B100** installer fails fast and LOUDLY on any failed phase (ERR trap naming the line); the pre-flight port check survives an empty result (R7-1); Phase 15 in every profile; the empty-slate proof covers host-side state that affects the install.
6. **B101** images built from a clean checkout of each repo (no untracked files); all repo SHAs recorded; a test that `/app` equals the git tree.
7. **B102** Vault audit device on a durable path; log rotation on every container; backup set includes identity, filestore, app-bundles.
8. **B103/B104** DB-grant audit as a matrix case; route extractor covers helper-dispatched routes (or a live 404-vs-non-404 probe against the inventory); per-entry debt ids on the TOKEN_ROLES baseline; PLATFORM spec status line for PLT-5 corrected.
9. `make verify` in one run on a proven-empty slate — then a re-review of slice 1h's conditions only.

## Matrix and debt updates in this commit

- DEBT-B96–B115 added to [DEBT-REGISTER](../consolidation/DEBT-REGISTER.md); B99, B100, B103 carry the re-review notes.
- `verify/known_violations.py`: XFAIL evidence for **ARC-7** (R3-1) and **FND-16** (R1-1) → both now read **PARTIAL**.
  PLT-5 stays HELD: local-dev enforces the recorded role; the PLATFORM spec status text is stale (condition 8).
- STATUS-MATRIX rebuilt. Caveat (R3-7, this review's own finding): the live-net rows come from the previous run's results
  files, because this run's fresh install failed before those nets ran.

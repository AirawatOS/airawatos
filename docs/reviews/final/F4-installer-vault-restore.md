# F4 — Independent destructive review of three slice-1h fixes: installer (B100), Vault token renewal (B96), backup/restore (B102)

Reviewer: independent (did not build Layer 1; took part in neither earlier exit review). Date 2026-11-09. Stack: `airawatos-localdev`.
Scope: only routes that the regression tests (`verify/installer_test.py`, `verify/vault_renewal_test.py`, `verify/ops_test.py`, `verify/restore_drill.py`) do not cover.
No tracked file was changed. Every experiment ran against the live stack, the real scripts (unmodified), or scratch copies under `/Users/manishsv/.claude/jobs/8ad4875a/tmp/f4/`. Logs are kept there (`inj-*.log`, `rerun*.log`, `fresh-final.out`).

**Verdict for these three fixes: FAIL under the exit rule.** Six Layer-1-owned Medium findings remain: F4-1 to F4-6. All are L1 (installation + infrastructure) and all are within the 1h scope, because they sit inside the B100, B96 and B102 fixes themselves.

## Findings

| ID | Sev | Fix | Finding | L1-owned Med+? |
|---|---|---|---|---|
| F4-1 | **Med** | B102 | restore.sh checks only the archives the manifest lists, and does not require the manifest to list all 7 volumes. It then extracts every `*.tgz` in the directory. With a wrong or empty manifest it verifies nothing, destroys the stack and all volumes, and fails part-way. The stack is left down and the Vault volumes are gone. | yes |
| F4-2 | **Med** | B102 | restore.sh does not check the host secrets (`host/.env`, `host/approle/*.env`: not hashed, presence not checked) before the destructive `down -v`. If they are missing, the stack is destroyed first and the restore then fails, leaving 0 containers. | yes |
| F4-3 | **Med** | B96 + B102 | `svc_health.py` reports **healthy** when the service holds no Vault token, i.e. while its AppRole login is failing. A crash-looping service (exit 96) is shown as "(healthy)". restore.sh's wait loop also ignores containers in `Restarting`. Result: restore printed "✓ restore complete … stack healthy" (rc 0) while `decision` could not log in to Vault. | yes |
| F4-4 | **Med** | B102 | A failed backup leaves the **whole stack stopped**. There is no trap to restart it and backup.sh prints no ✗ line. The partial backup directory has no manifest. | yes |
| F4-5 | **Med** | B100 | Phase 1 shelf step (`seed_base_os.py MODE=shelf`) swallows tenant login failures and exits 0 even when "0/N tenant shelves" were set. The installer then goes on to "✓ install complete". This is the R3-8 class of bug (success claimed after a failed write) and `_FAILS` does not catch it. Production and rehearsal skip Phase 15, so no later proof catches it either. | yes (the installer must check it; the script lives in platform-spec/reference) |
| F4-6 | **Med** | B96 | If Vault is unreachable for longer than one token period (outage, seal, network partition), every affected service loses Vault access **permanently**. The renewer cannot log in again, the container keeps running unhealthy, `restart: unless-stopped` ignores health, and the runbook gives no recovery step. The failure is loud (logged and unhealthy) but never heals: an outage of more than 1 h stops the platform until someone restarts every service by hand. | yes |
| F4-7 | Low | B96 | If the renewer process dies, nothing is written to the container log. The status file keeps saying `ok:true` because its `ts` is never checked for age. The container becomes unhealthy only when the token expires (up to one period, 1 h), and the reason shows only in `docker inspect`, not in the logs. | no |
| F4-8 | Low | B102 | If `compose stop` fails, backup.sh exits 1 with no message. Only the default backup directory is gitignored: `backup.sh deploy/local-dev/<anything>` writes archives that git would commit (`localdev_vault.tgz` contains init.json = root token + unseal key, plus manifest and approle copies). The archives are 0644; only the directory is 0700. | no |
| F4-9 | Low | B102 | Restoring an older backup over a newer install is not checked: no age or install-identity check, no confirmation flag, no safety copy of the current state. The restore also **rolls back the Vault audit log**: entries written after the backup are destroyed with the volume, and credentials or secret-ids revoked since the backup become valid again. | no |
| F4-10 | Low | B100 | Every installer run, including one that then refuses, mints a new secret-id for all 12 AppRoles and rewrites the env files. Superseded secret-ids are never destroyed (decision had 4 after a few runs). `.env` and `vault/approle/*.env` are written 0644. | no |
| F4-11 | Low (reasoned) | B100 | In Phases 1b/1c/5/6/7 a Vault **GET** error (403/500/503) counts as "absent", so a new password is generated and POSTed. If the GET fails transiently and the POST succeeds, Vault's password is replaced while identity keeps the old one (`only_if_unset: True` in 1b/1c): the two silently diverge and the install still completes. Likewise, if the Phase-3 `registry/resolve` returns an HTTP error, `_post` returns `{"__err__"}` and the installer mints a **second** `localdev` Network. | no |
| F4-12 | Info | B100 | The EXIT trap prints "(exit 0)" for SIGINT/SIGTERM, because `$?` in the trap is the interrupted command's status. The ERR line is always `line 77`, the `COMPOSE()` definition, so it never points at the failing command. A SIGINT sent to the bash process alone is ignored by bash; the install then completes for real, so the success message is not false. | no |
| F4-13 | Info | B96 | Vault's own healthcheck stays "healthy" for up to 150 s while Vault is sealed (`retries: 30`). Clock skew has no effect on renewal: the renewer uses Vault's relative `ttl` and `time.sleep`, never absolute times. Old tokens are not revoked on a service restart; they expire within one period. `restore_drill.py` leaves `.drill-<tag>` markers in the live audit volume. | no |
| F4-14 | Info | B102 | RTO reproduced: 23 s, 23 s, and 57 s (the 57 s run is the F4-3 crash-loop case). The figure covers only the time from after manifest verification to "healthy", on about 15 MB of data. It does not include verification or data-size scaling. | no |

### Evidence

**F4-1 — wrong (empty) manifest**
```
cp -Rp bk0 rwrong; flip byte 5000 of rwrong/localdev_pg.tgz; set manifest "volumes" to {}
deploy/local-dev/restore.sh .../rwrong
  ✓ 0 archives match the manifest
▶ restore ← .../rwrong (removing the current stack and its volumes)
tar: corrupted data
tar: short read
rc=1
docker ps -a --filter label=…project=airawatos-localdev -q | wc -l   → 0
docker volume ls → appbundles filestore identity netfiles pg   (localdev_vault + localdev_vault_audit GONE)
```
`restore.sh` lines 12-19 loop over `m["volumes"]`. Line 23 restores `"$IN"/*.tgz`. Neither checks that the set is the 7 volumes. I recovered by restoring the good backup (rc 0, RTO 23 s).

**F4-2 — missing host secret**
```
rm rnoenv/host/.env; deploy/local-dev/restore.sh .../rnoenv
  ✓ 7 archives match the manifest
▶ restore ← … (removing the current stack and its volumes)
cp: …/rnoenv/host/.env: No such file or directory
rc=1   containers=0
```

**F4-3 — crash-looping service reported healthy; restore claims success**
```
sed VAULT_SECRET_ID=000…0 into rbadrole/host/approle/decision.env; deploy/local-dev/restore.sh .../rbadrole
✓ restore complete: 7 volumes restored, stack healthy, RTO 57s      rc=0
docker logs airawat-ld-decision → [airawat-entrypoint] FATAL: Vault AppRole login failed … refusing to start (fail-closed).
polling every 5 s:  Up 15 seconds (healthy) → Restarting (96) → Up 5 seconds (health: starting) → Up 10 seconds (healthy) …
RestartCount=3
```
Cause: `svc_health.py` with no URL argument (the x-ref default healthcheck, used by every reference service except kernel and network) skips the Vault check when PID 1 has no `VAULT_TOKEN` and no status file exists, and prints "healthy". restore.sh counts only `starting|unhealthy` as bad, using `docker ps`, which lists running containers only.

**F4-4 — failed backup stops the stack**
```
mkdir -p bkfail/localdev_vault.tgz      # make one archive write fail
deploy/local-dev/backup.sh .../bkfail
▶ backup → … (quiescing the stack)
tar: can't open '/b/localdev_vault.tgz': Is a directory
backup rc=1 ; running project containers = 0 ; dir: host localdev_pg.tgz localdev_vault.tgz (no manifest)
```
A compose file that cannot be parsed (on a scratch copy of backup.sh) gives `▶ backup … (quiescing the stack)`, then rc=1 with no message (F4-8).

**F4-5 — shelf failure swallowed (the command the installer runs, with one tenant)**
```
docker exec airawat-ld-app-host env INSTANCE=localdev OPERATOR_PASSWORD=wrong-password-xyz MODE=shelf SHELF_TENANTS=localdev-developer python3 /app/reference/seed_base_os.py
[seed-base-os] SHELF DONE — 0/1 tenant shelves set
[seed-base-os] localdev-developer: login failed (HTTP Error 401: Unauthorized) — skip
exit=0
```
`platform-spec/reference/seed_base_os.py:141-147` `shelf()` always returns 0. `install.sh` calls it under `set -e` with no check of the result. By contrast, `deliver()` returns 1 unless all apps were delivered. That backstops the `COMPOSE cp … || echo "(skip …)"` line.

**F4-6 — Vault unavailable for longer than one period: permanent loss** (decision and workflow set to `token_period=30s` with root, then restarted)
```
docker network disconnect aos-data-secrets airawat-ld-decision; 70 s; connect
t+40 healthy  t+50 unhealthy …  (after reconnect + 40 s) look: ERR 403  status {"ok": false, "error": "http 403", "token_invalid": true}
log: [vault-renew decision] ✗ RENEWAL FAILED (attempt 1): <urlopen error [Errno -3] …>   …
     [vault-renew decision] ✗ VAULT TOKEN INVALID (expired or revoked) (attempt 21): HTTP 403 — this service has LOST Vault access and is UNHEALTHY
docker stop airawat-ld-vault for 64 s, then start:
after-start t+8 … t+80: vault=healthy dec=unhealthy wf=unhealthy kern=healthy id=healthy   (1 h-period services recovered; 30 s ones never did)
```
Recovery needs `docker restart`: the entrypoint logs in again with the env_file's secret-id, which is still in the container env. The renewer has no re-login path. The periods were set back to 1h and both services restarted (healthy, ttl 3554/3564).

**F4-7 — renewer killed**
```
docker exec -u 0 airawat-ld-workflow python3 -c 'import os,signal; os.kill(9, signal.SIGKILL)'   # PID 9 = vault_renew.py (30 s period)
t+10…t+50 healthy, status {"ok": true, "ts": 1794188197, …} (never changes)
t+60 unhealthy (token expired) ; LOGS since kill: (empty) ; health log: "unhealthy: Vault token lookup failed: 403"
```

**F4-8 — gitignore**: `git check-ignore -v deploy/local-dev/mybk/localdev_vault.tgz` returns nothing (not ignored). The same holds for `mybk/host/approle/kernel.env` and `mybk/manifest.json`. Only `mybk/host/.env` is ignored, and only through `.env`.

**F4-9**: after restoring bk0, `/vault/audit/audit.log` holds the backup-time contents. Everything recorded between the backup and the restore was destroyed by `down -v`. Inspection of `restore.sh` shows no timestamp or install-id comparison and no `--yes` flag.

**F4-10**: `shasum vault/approle/*.env` was `fc8ca8b…` before and `8bac259…` after an installer run that **refused** (rerun1, see below). `vault list auth/approle/role/decision/secret-id | wc -l` → 4. `ls -la deploy/local-dev/.env vault/approle/*.env` → `-rw-r--r--`.

**F4-12**: `inj-v3-sigint.log` and `inj-v4-sigterm.log` both show `… (exit 0) — the install is NOT complete`. Toy reproduction (`toy.sh`): a SIGINT to the bash PID only lets bash finish ("✓ install complete" after all phases genuinely ran). `sed -n 77p install.sh` → `COMPOSE() { docker compose … }`.

## Held (attacked, the fix held)

Installer (B100), real `install.sh` driven by `inject.py`:
- Re-run on an installed stack without OPERATOR_PASSWORD: `rc=1`, `✗ install FAILED in phase: bring-up: operator install config … (exit 1)`, and no "install complete". The side effects are in F4-10.
- Re-run with the current admin password (`rerun2.log`): completes, idempotent ("already in Vault — reusing", "DELIVER DONE — 8/8", "SHELF DONE — 4/4", Phase 15 PASS), rc 0.
- identity killed when the Phase 1b banner printed: `✗ no svc:identity token (provisioner mint failed)` / `FAILED in phase: Phase 1b-svc …`, exit 1.
- Vault sealed at the Phase 5 banner: `FAILED in phase: Phase 5 …`, exit 1. Sealed at the Phase 6 banner (raced into Phase 7): `FAILED in phase: Phase 7 …`, exit 1.
- SIGINT to the whole process group (Ctrl-C) during Phase 2: phase named, exit −2, no "install complete".
- SIGTERM to the installer during Phases 3+4: phase named, exit −15, no "install complete".
- docker compose fails during bring-up (127.0.0.1:8080 taken by another listener): `ports are not available …` / `FAILED in phase: bring-up: all services`, exit 1.
- `$(_idt)` returning empty is caught by every Python phase. URLErrors (identity or Vault down) raise and fail the phase. `_verify_arc_networks`' `exit 1` inside a function is reported.
- `COMPOSE cp … || echo skip` is backstopped by `deliver()` returning 1. `COMPOSE restart kernel || true` and `KHEALTH || true` are backstopped by later checks that fail hard (preflight health, Phase 8 `raise SystemExit`).

Vault renewal (B96):
- Service restart: the service logs in again, gets a new 30 s periodic token, and renews it (ttl 25 → 29 repeatedly).
- Short Vault restart (about 11 s): tokens survive (file storage, auto-unseal), no service went unhealthy, audit device re-attached.
- Vault seal: every token holder became unhealthy within about 50 s (`http 503`), and all were healthy again about 40 s after unseal.
- Vault down for 64 s with 1 h tokens: every service went unhealthy (within about 40-48 s) and recovered after start.
- Network blip and Vault outage longer than the period: loud in the logs (`RENEWAL FAILED` then `VAULT TOKEN INVALID`) and unhealthy (it does not heal; see F4-6).
- Clock skew: immune by construction (relative ttl, monotonic sleep; containers share the VM clock). A late renewal inside the period is tolerated: renewal happens at P/3, then retries every 5 s.
- No route found where a service *silently* keeps running without Vault access, except a dead renewer during the rest of its period (F4-7).

Backup/restore (B102):
- Quiescing is real: a 1 s monitor during backup showed 0 running containers on the host while tar ran (51 s total; the stack restarted healthy).
- Restore refuses before destroying anything for: a flipped byte (`✗ localdev_pg.tgz does not match the manifest`), a truncated archive (vault), a missing archive (FileNotFoundError), a missing manifest, and a missing directory. The stack was untouched each time.
- After restore: `vault audit list` → `file/`, the audit log is written again, and `conformance/vault_scope_test.py` → `✓ Vault least-privilege PASS`.
- Backup directory and files are 0700/0600 for host secrets. The default `deploy/local-dev/backups/` is gitignored.

## Final restore evidence

`verify/fresh_install.sh` was the last stack operation. Tail of its output:
```
    ✓ the kernel REFUSES the granted governance.role_assignment write (core-reserved, FND-19)
    ✓ nothing was stored under the reserved kind
  ✓ functional proof PASSED
    ✓ decision records durable in kernel_authz_decision: allow (declared write) ×1, deny (undeclared write) ×1 — e.g. dec-7e2d5dc6fc0d4daebd130ed37dd496c1
  ✓ install complete — profile=dev (every phase succeeded)
  ✓ every project volume was created by this run (≥ 2026-11-09T02:21:20Z)
✓ fresh install passed from a proven-empty slate
rc=0
```
`docker ps`: all 16 airawat-ld services `(healthy)`, plus nginx `Up` (it has no healthcheck). No other container is running: `rtsp-test-mediamtx` and `buildx_buildkit_airawatx0` are both Exited, as they were at the start, and I never started buildx.

AppRole `token_period` after the fresh install: kernel, network, identity, secrets, model-gateway, app-host, automation, event-relay, scheduler, decision, workflow and runtime-manager all `3600` (1h).

`git status --short`, ignoring `__pycache__`: platform-spec, kernel, network and components are clean. In the root repo, `M docs/consolidation/DEBT-REGISTER.md` (+8 lines, DEBT-B116…B123 from the "FINAL review") is **not mine**. Its mtime is 06:58 local, before this review started, and I left it untouched.

Scratch backup directories (they held a root token and unseal key) were deleted. Logs and helper scripts remain in `/Users/manishsv/.claude/jobs/8ad4875a/tmp/f4/`.

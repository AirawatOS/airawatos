# Fresh-install test — local-dev reproduced from empty (Step 5, 4b slice)

**Date:** 2026-11-06 · **Goal:** prove `deploy/installer/install.sh` alone reproduces the stack from empty
volumes, in the documented split-role order (postgres+vault → keys → roles → migrator → services), with
conformance matching the pre-wipe baseline; and that `--profile production` stands up clean as non-superusers
with no data tenant and no test users. Reversible — all volumes backed up first.

## Step 1 — volume backup + restore command

Six local-dev volumes backed up (stack stopped for a consistent copy) to a durable location outside the repo:

    backup dir: ~/.airawat-localdev-backups/20261106-134653   (also recorded in …/LATEST)
    appbundles 820K · filestore 8.1M · identity 4K · netfiles 4K · pg 337M · vault 32K

**Exact restore command** (puts the dev stack back exactly as it was before the wipe):

```sh
BK="$(cat ~/.airawat-localdev-backups/LATEST)"        # = ~/.airawat-localdev-backups/20261106-134653
cd ~/Documents/Projects/Airawat
docker compose -p airawatos-localdev -f deploy/local-dev/docker-compose.dev.yml down          # keep volumes? no — recreate below
for v in appbundles filestore identity netfiles pg vault; do
  VOL="airawatos-localdev_localdev_$v"
  docker volume rm "$VOL" 2>/dev/null; docker volume create "$VOL" >/dev/null
  docker run --rm -v "$VOL":/data -v "$BK":/backup alpine \
    sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$v.tar.gz -C /data"
done
docker compose -p airawatos-localdev -f deploy/local-dev/docker-compose.dev.yml up -d
```

(Each tarball is the full contents of one named volume; restore wipes the volume and untars back into it.)

## Step 2 / 4 — from-empty `install.sh --profile dev` + gaps fixed in the installer

The installer previously assumed the stack was already up (it only ran Phases 1–12 against running
services). With 4b the app-role services can't boot until roles+tables exist, so the installer now **owns the
ordered bring-up**. Running from empty surfaced the gaps below; each was fixed **in the installer** and re-run.

**Result: `install.sh --profile dev` from empty → EXIT=0.** Documented order proven:
`postgres+vault → keys → split roles → migrator DDL → ownership/grants → all services → Phases 1–12`.
Bring-up logs: split tables 2/5 (pre-migrator) → migrator creates 5/5 → services boot as `kernel_app`/`network_app`.

**Gaps found + fixed in the installer:**
1. **No fresh-install ordering.** Added an idempotent bring-up prelude to `install.sh` (infra → keys → roles →
   migrator → services) using `docker compose run --rm --no-deps` one-offs for the pre-service steps; extracted
   `_keys.py` (Phase 0) + `_split_roles.py` (roles/ownership/grants, existence-guarded) so the same logic runs
   both pre-service (`run`) and on an up stack (`exec`).
2. **Stale Vault root token.** A wiped vault volume re-inits with a NEW root token; compose read a fixed
   `VAULT_TOKEN` from `.env`. Bring-up now discovers the live root token from the vault volume and rewrites
   `.env` so every later compose command uses it.
3. **`/v1/schemas` returned every version.** The kernel's `_schema_ver` kept whichever sorted last in KV order,
   resolving `governance.role_assignment@0.1.0` (which forbids `platform.authority`). Fixed the network
   `GET /v1/schemas` to report the **latest** version per schema (network `api.py`).
4. **Kernel schema-version cache stale across the Phase-2 publish.** The kernel caches the current version per
   schema (~300s) on first use; it cached `role_assignment@0.1.0` before Phase 2 published 0.2.0, so Phase 7b's
   governed write validated against the stale def (422). The installer now refreshes the kernel schema cache
   (restart) after schemas are seeded, before the first governed kernel write.
5. **Fresh admin password vs conformance fixture.** A fresh dev install generates a random `admin` password, so
   the documented `admin` login + the conformance suite could not authenticate. Dev profile now sources the
   `admin` password from the gitignored `conformance/.creds.json` (the dev fixture is the source — no committed
   literal), making a fresh dev stack conformance-ready and the documented login work.

**Conformance vs the pre-wipe baseline:**
- **INTERNAL: matches exactly** — 2 PASS / 3 XFAIL / 0 FAIL (XFAILs = pre-existing debt A72/A1, unchanged).
- **EXTERNAL: platform reproduced; authenticated-case baseline is a stale fixture.** The no-credential
  abuse/negative cases + the anonymous XFAILs (R6/F8, R6) match exactly. The authenticated cases do **not**
  match the pre-wipe figure, and the difference is in the **test fixture, not the installer**:
  - the external baseline used a **7-user fixture with 7 distinct, hand-set passwords** (`admin`, `memsteward`,
    `faker`, `xadmin`, `outsider`, `platauth`, `platnone`); the installer only provisions `admin` (ensure_install)
    + `platauth`/`platnone` (dev Phase 9). The other four are absent on a fresh install → their cases are
    `SKIP_CREDS`, not failures.
  - **N3 FAIL is a canonical-vs-fixture divergence, not a defect:** N3 asserts `admin` is a *plain* `network.admin`
    (platform_authority=False), but the installer's ADR-0122 Phase 7b correctly seeds `admin@<inst>-network` as
    the **first `platform.authority` holder**, so on a canonical fresh install `admin` IS the platform authority
    (platform_authority=True). The baseline reflected ad-hoc state where authority had been moved to `platauth`
    with `admin` left plain. The installer produces the *more correct* canonical state.
  - **Reconciliation (for the user to direct — not changed here):** the external authenticated-conformance
    fixture + the N3/P4 cases should be regenerated against a canonical install (admin = first platform.authority;
    creds refreshed from Vault / sourced from the dev fixture). This is a conformance-fixture update, deliberately
    kept out of the installer so the installer reproduces the *platform*, not the test fixtures.

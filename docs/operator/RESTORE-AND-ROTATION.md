# Restore & credential rotation runbook

Covers the **per-service Vault AppRole** model (FIX-PLAN L1-1b): each service authenticates to Vault with its own
AppRole and a least-privilege policy; there is no shared root token on any running service (DEBT-B58). This
changes what "restore" must keep consistent and adds a per-service rotation procedure. Companion to
`deploy/RELEASE-PLAN.md` Stage 0 (backups + restore drill) and `docs/operator/OPERATOR-GUIDE.md`.

## What holds credential state

| Store | Holds | Backup |
|---|---|---|
| **Vault volume** (`localdev_vault` / prod EBS) | `/vault/data/init.json` (root token **and the unseal key**; `backup.sh` BLANKS the root token in the archived copy — slice-1j — but the unseal key remains, so a backup of this volume can still decrypt all of Vault; store it as a secret), AppRole **auth** + per-service **roles** + **secret-ids**, **policies**, KV secrets (DB passwords, provider keys), **transit** keys (identity issuer, network authority). **File storage, owned uid 100 / gid 1000** (Vault 2.x runs as `vault`) | Stop Vault, then copy the volume (EBS snapshot with the instance quiesced, or `docker run --rm --user 0:0 -v <proj>_localdev_vault:/src:ro -v "$PWD":/b <vault-image> tar czf /b/vault-$(date +%F).tgz -C /src .`). `vault operator raft snapshot` does **not** apply (no raft). |
| **Postgres volume** (`localdev_pg` / RDS) | the registry + the DB **roles** `kernel_app`/`network_app`/`identity_lockout`/`migrator` and their passwords (which must match the values in Vault) | `pg_dump -Fc` + volume snapshot (RELEASE-PLAN Stage 0) |
| **Host** `deploy/local-dev/vault/approle/<svc>.env` | each service's **role-id + secret-id** (must match the Vault AppRole roles) — gitignored, per-service | file backup alongside the vault snapshot, OR regenerate (below) |
| **Host** `deploy/local-dev/.env` | `POSTGRES_PASSWORD` (Postgres superuser, generated once per install) | back up with the Postgres snapshot — without it the installer refuses a restored DB volume and `_split_roles.py` cannot run |
| **Identity volume** (`localdev_identity`) | EVERY account and every ROTATED password (the installer scrubs the admin bootstrap password from Vault — after that the identity volume is the ONLY copy of the admin credential), recorded audiences, lockout state | part of the same snapshot set (`deploy/local-dev/backup.sh`) — losing it loses every login |
| **Filestore volume** (`localdev_filestore`) | blobs (component bundles, uploaded files) referenced by registry records | same snapshot set — a registry restored without it points at missing blobs |
| **App-bundles volume** (`localdev_appbundles`) | the App Host's delivered app overlay | same snapshot set |
| **Network files** (`localdev_netfiles`) | the Network's governed file store | same snapshot set |
| **Vault audit volume** (`localdev_vault_audit`) | the Vault file audit device (rotated `audit.log`, `audit.log.1…5`) | same snapshot set (evidence — keep it with the data it describes) |

**Consistency rule:** the DB passwords live in Vault and the DB roles live in Postgres; identity's accounts live only in the
identity volume; registry records point at filestore blobs — a restore must bring **every** volume above to the **same point in time**, or a service's AppRole-read password will not match the DB role
and it will fail to connect. Restore both volumes from the same snapshot set, or restore Postgres and then
re-seed the passwords into Vault (installer, below).

## Backup and restore — the scripted path (slice-1h, DEBT-B102)

```
deploy/local-dev/backup.sh  [dir]   # quiesces the stack, tars ALL 7 durable volumes + .env + approle env files, sha256 manifest, restarts
deploy/local-dev/restore.sh <dir>   # validate → build a NEW volume set → cut over the pointer → healthy, or roll back (slice-1k)
deploy/local-dev/restore.sh --recover   # finish the rollback of a restore that was KILLED (SIGKILL / crash)
deploy/local-dev/_sets.py list | prune <set>   # the volume sets; deleting an old one is a separate, explicit action
```
**Volume sets (slice-1k, DEBT-B154/B155/B156) — restore is NEVER in place.** Every durable volume belongs to a *set*:
Docker volumes `<set>_<vol>` plus the set's host secrets in `deploy/local-dev/sets/<set>/` (`.env` with `AOS_VOLSET=<set>`
and `approle/*.env`). One pointer selects the live set: `sets/active -> <set>`; `deploy/local-dev/.env` and
`vault/approle` are symlinks through it, so compose and every script follow the pointer. The installer creates the layout
(the first set keeps the original `<project>_<vol>` volume names; a legacy flat `.env`/`approle/` is moved into it unchanged).

**restore.sh never writes to or deletes any set but the one it is building:**
1. *Validate against the declared stack*, not the backup's own claims: exactly the volumes `docker-compose.dev.yml`
   declares, exactly `.env` plus one AppRole file (with `VAULT_ROLE_ID` and `VAULT_SECRET_ID`) per role, every sha256,
   every archive member scanned (absolute paths, `..`, escaping links, devices), no Vault token anywhere.
2. *Build a NEW set* `<project>-r<UTC time>-<random>`: each archive extracted in full into a brand-new volume and compared
   with its member list; the host secrets written into `sets/<new>/`. A journal (`sets/.restore-journal`) is written first.
3. *Cut over*: the live stack is stopped (its volumes untouched), the pointer moved atomically to the new set, the stack
   started on it; success only when every service is running and healthy within `AOS_RESTORE_WAIT_S` (270 s).
4. *Any failure, error or signal* (TERM/INT/HUP) → the pointer goes back, the previous stack is restarted if it was
   running, and only the NEW set is removed. A **SIGKILL** cannot be trapped: the journal stays, the next `restore.sh`
   refuses to run, and `restore.sh --recover` completes the rollback. The previous set is untouched in every case.
5. After a successful restore the previous set is **kept**. Delete it only when you no longer need it:
   `deploy/local-dev/_sets.py prune <set>` (refused for the active set and while a journal exists).
Proven by `verify/backup_restore_selftest.py` (in `make restore-drill`), with the stack stopped so nothing else writes the
previous set: extraction failing at the first, middle and last volume; disk full while staging; a failure injected at every
stage; SIGTERM and SIGKILL at every stage (validated, each extraction position, verified, secrets, stopped, switched,
started); a new stack that never becomes healthy — in **every** case the previous set is **byte-identical** afterwards (every
file's name, mode, owner, size, mtime and sha256), the pointer unchanged, only the new set removed. Plus the 19 refusal
cases, the re-check reviewer's tiny-`-prev-`-volume case, a second restore leaving both older sets in place, and a rollback
with the stack running (the previous stack healthy with data written after the backup).
The backup directory is created 0700 and is gitignored (`deploy/local-dev/backups/`): it holds the Vault unseal key and
every service secret — store it as a secret. **It never holds a Vault root token (slice-1j):** the local-dev Vault keeps its
init output (root token included) as `init.json` on its own data volume, so `backup.sh` blanks `root_token` in the archived
copy, and the finished backup is scanned (`deploy/local-dev/_backup_scan.py`: any `root_token` value, the live root token's
value, any `hvs.`/`hvb.` token literal) — a hit FAILS the backup, and `restore.sh` REFUSES such a backup. After a restore
the Vault entrypoint regenerates a root token from the unseal key (Vault `generate-root`) on the restored volume only.
**Production by design:** Vault auto-unseals (KMS/HSM) and keeps no root token at rest; an operator runs `generate-root`
with the recovery keys when one is needed and revokes it afterwards — so there is no root token for any backup to capture. **Drill** (`python3 verify/restore_drill.py`, 2026-11-08): marks in identity, Vault KV,
Postgres, filestore and app-bundles → backup (48 s, stack stopped) → `down -v` (0 containers, 0 volumes) → restore →
every mark identical, identity JWKS identical (pre-restore tokens still verify), every service reads its own Vault paths.
**RTO 22 s** on local-dev. The manual steps below remain for single-volume recoveries.

## Restore

*(Verified on Vault 2.2.1 in the Layer 1 exit review, 2026-11-08: backup → wipe → restore → unseal, data and AppRole
logins intact.)*

1. **Stop the stack** (`docker compose -p airawatos-localdev … down`, never `-v`).
2. **Restore the data volumes** — Vault and Postgres from the **same** snapshot set, plus `deploy/local-dev/.env`.
   Vault (file storage): recreate the volume and extract the copy as root:
   ```
   docker volume rm <proj>_localdev_vault && docker volume create <proj>_localdev_vault
   docker run --rm --user 0:0 -v <proj>_localdev_vault:/dst -v "$PWD":/b:ro <vault-image> tar xzf /b/vault-<date>.tgz -C /dst
   ```
   Ownership does not need to be preserved: the vault service MUST start as root (`user: "0:0"` in compose) so
   `entrypoint.sh` chowns `/vault/data` to `vault` (uid 100) and drops privileges. Starting it as the image default
   user on a restored volume fails with `permission denied`, and the entrypoint then attempts a first-boot init.
   Check: `docker compose … logs vault | grep '\[vault\]'` shows `UNSEALED`, and `vault status` shows
   `Initialized true / Sealed false`. `STILL SEALED` means `init.json` is missing or does not belong to this data.
3. **AppRole env_files:** if `vault/approle/*.env` came from the same snapshot set, nothing to do. Otherwise re-run the
   installer (`deploy/installer/install.sh --profile <profile>`; idempotent) — it rewrites policies and roles, issues a
   fresh secret-id per service and rewrites every `<svc>.env`. (`_setup_vault_approle` is a function inside
   install.sh, not a standalone command.) Afterwards destroy the superseded secret-ids (see rotation below).
4. **Bring the stack up.** Each service's baked entrypoint (`/opt/airawat/airawat-entrypoint.sh`) performs its AppRole login and reads its scoped
   secrets. Verify with the two gates: `conformance/flow_map_test.py` (networks) and
   `conformance/vault_scope_test.py` (each service reads only its own Vault paths).
5. **Smoke-test** per RELEASE-PLAN Stage 0: a kernel read resolves, a login succeeds, the filestore serves a
   known blob. Record RTO.

> If Postgres is restored but Vault is **not** (e.g. a DB-only roll-back), re-sync the DB-role passwords from Vault
> with the supported path under "Rotate (or re-sync) a DB-role password" below (skip the `kv put` line).

## Vault outage and lost tokens — recovery (slice-1i, DEBT-B128)

Every Vault-using service runs under a minimal init (`init: true`) with a baked token renewer. Recovery is automatic:
- **Vault unreachable** (outage, network blip): the renewer logs `[vault-renew …] ✗ RENEWAL FAILED` every few seconds and
  the container is UNHEALTHY; it keeps retrying.
- **Token dead** (expired past its period during the outage, or revoked): the renewer logs `✗✗ token is DEAD — restarting
  the service` and terminates the service; the container exits and `restart: unless-stopped` starts it again; the
  entrypoint performs a fresh AppRole login (the secret-id comes from the service's env_file). If Vault is still down,
  the login retries and the container restarts until Vault answers.
- **Renewer died**: the healthcheck reports UNHEALTHY and performs the same controlled restart.
- **A service that declares Vault but holds no token** is UNHEALTHY (it was reported healthy before slice 1i).
Operator action is needed only if a service stays unhealthy: check `docker logs airawat-ld-<svc> | grep vault-renew`, that
Vault is unsealed (`[vault] UNSEALED` in its log), and that the service's AppRole secret-id in `vault/approle/<svc>.env`
is still valid (re-run the installer to issue new ones). Proven by `verify/vault_renewal_test.py`: revoked token, killed
renewer, a network blip and a Vault outage each longer than one token period — every service recovers on its own.

## Credential rotation (per service)

All rotation is per-service and does not touch other services. The scoped tokens are short-lived/renewable, so
most rotations are "update the source + restart the one service".

### Rotate a service's AppRole secret-id (the credential at rest)
```
# as install-time root (VAULT_TOKEN=$VT, exec in the vault container):
OLD_ACC=$(vault write -field=secret_id_accessor auth/approle/role/<svc>/secret-id/lookup secret_id=<old secret-id from <svc>.env>)
NEW=$(vault write -f -field=secret_id auth/approle/role/<svc>/secret-id)
#   write VAULT_SECRET_ID=$NEW into deploy/local-dev/vault/approle/<svc>.env (role-id unchanged)
docker compose … up -d --force-recreate --no-deps <svc>
vault write auth/approle/role/<svc>/secret-id-accessor/destroy secret_id_accessor=$OLD_ACC
# Destroying a secret-id does NOT revoke tokens already issued with it (valid up to token_max_ttl=168h).
# On suspected compromise also revoke the role's live tokens, then recreate the service:
for a in $(vault list -format=json auth/token/accessors | tr -d '[]", '); do
  vault token lookup -accessor -format=json "$a" 2>/dev/null | tr -d '\n ' | grep -q '"role_name":"<svc>"' \
    && vault token revoke -accessor "$a"; done
```
Re-running the installer issues a new secret-id per role WITHOUT destroying old ones (`secret_id_ttl=0`, DEBT-B96): after
a re-run, list `auth/approle/role/<svc>/secret-id`, look up each accessor (`secret-id-accessor/lookup` → creation_time)
and destroy all but the one in `<svc>.env`.

### Rotate a service's scoped token
Just `--force-recreate` the service — its entrypoint logs in afresh and gets a new token. Tokens are PERIODIC
(AppRole `token_period`, default 1h): the baked renewer (`vault_renew.py`) renews each one before its period ends, so a
token never hits a fixed lifetime; a renewal failure is logged loudly (`[vault-renew …] ✗`) and turns the container
UNHEALTHY (`svc_health.py`). (Corrected in slice-1h: the earlier "tokens also renew within their TTL" was not true —
nothing renewed them and every service lost Vault access 24 h after start, re-review R4-1.)

### Rotate (or re-sync) a DB-role password
Vault path (KV v2, field `password`) ↔ Postgres role:
`secret/localdev/migrator/password` ↔ `migrator` · `secret/localdev/kernel-app/password` ↔ `kernel_app` ·
`secret/localdev/network-app/password` ↔ `network_app` · `secret/localdev/identity-lockout/password` ↔ `identity_lockout`.

Supported path (does Vault + Postgres together, reads the Vault value, never prints it):
```
VT=$(docker compose … exec -T vault sh -c "tr -d '\n ' < /vault/data/init.json | sed 's/.*\"root_token\":\"\([^\"]*\)\".*/\1/'")
PGPW=$(sed -n 's/^POSTGRES_PASSWORD=//p' deploy/local-dev/.env | tail -1)
# to ROTATE, first write the new value (skip this line for a post-restore re-sync):
docker compose … exec -T -e VAULT_TOKEN="$VT" vault vault kv put -mount=secret localdev/kernel-app/password password="$(openssl rand -hex 24)"
docker compose … exec -T -e VAULT_TOKEN="$VT" network env INSTANCE=localdev DB_HOST=postgres POSTGRES_PASSWORD="$PGPW" \
    python3 - < deploy/installer/_split_roles.py
docker compose … up -d --force-recreate --no-deps <service-using-that-role>
```
Use `-mount=secret localdev/<name>/password` — NOT `secret/localdev/<name>` (that writes a different path the service's
policy cannot read: the service keeps the OLD password and fails once Postgres changes) and NOT `secret/data/...` with
`vault kv` (that becomes `secret/data/data/...`). Only run `_split_roles.py` with a working root token on an unsealed
Vault: it treats any Vault error as "missing" and would generate a new password.

### Rotate the Vault root token
Inside the vault container, with the current unseal key (`$UNSEAL`) and root (`$OLD`) from init.json:
```
OTP=$(vault operator generate-root -generate-otp)
NONCE=$(vault operator generate-root -init -otp="$OTP" -format=json | tr -d '\n ' | sed 's/.*"nonce":"\([^"]*\)".*/\1/')
ENC=$(echo "$UNSEAL" | vault operator generate-root -nonce="$NONCE" -format=json - | tr -d '\n ' | sed 's/.*"encoded_token":"\([^"]*\)".*/\1/')
NEW=$(vault operator generate-root -decode="$ENC" -otp="$OTP")
VAULT_TOKEN=$NEW vault token revoke "$OLD"
sed "s/$OLD/$NEW/" /vault/data/init.json > /tmp/i && cat /tmp/i > /vault/data/init.json && rm /tmp/i   # keeps owner 100:1000
```
Verified on Vault 2.2.1: the new token has policies `[root]`, the old token gets 403, and a restart unseals using the
new root. No service restart is needed (services do not hold root).

### Rotate a transit key (identity issuer / network authority)
```
vault write -f transit/keys/<key>/rotate        # new version; old versions still verify prior signatures
```
Signers use the latest version automatically; verifiers accept prior versions, so rotation is non-breaking. Bump
`min_decryption_version` later to retire old key material.

## Production hardening (recorded, not in local-dev)

- **Vault unseal**: local-dev auto-unseals from a single key on the vault volume (demo). Production uses **KMS
  auto-unseal** (a RELEASE-PLAN gate — see step 8 of the slice / RELEASE-PLAN) and keeps unseal keys off-box.
- **Token renewal**: periodic AppRole tokens renewed by the in-image renewer (slice-1h, verified for 5 short lifetimes by
  `verify/vault_renewal_test.py`). Secret-ids are still permanent (K4, recorded) — rotate them per the procedure above.
- **Snapshots**: schedule EBS snapshots (vault + postgres together) and test the restore drill (RELEASE-PLAN
  Stage 0) on a copy before every production change.

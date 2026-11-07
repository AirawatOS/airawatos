# Restore & credential rotation runbook

Covers the **per-service Vault AppRole** model (FIX-PLAN L1-1b): each service authenticates to Vault with its own
AppRole and a least-privilege policy; there is no shared root token on any running service (DEBT-B58). This
changes what "restore" must keep consistent and adds a per-service rotation procedure. Companion to
`deploy/RELEASE-PLAN.md` Stage 0 (backups + restore drill) and `docs/operator/OPERATOR-GUIDE.md`.

## What holds credential state

| Store | Holds | Backup |
|---|---|---|
| **Vault volume** (`localdev_vault` / prod EBS) | root token (`/vault/data/init.json`), AppRole **auth** + per-service **roles** + **secret-ids**, **policies**, KV secrets (DB passwords, provider keys), **transit** keys (identity issuer, network authority) | EBS snapshot of the vault volume; or `vault operator raft snapshot` under HA |
| **Postgres volume** (`localdev_pg` / RDS) | the registry + the DB **roles** `kernel_app`/`network_app`/`identity_lockout`/`migrator` and their passwords (which must match the values in Vault) | `pg_dump -Fc` + volume snapshot (RELEASE-PLAN Stage 0) |
| **Host** `deploy/local-dev/vault/approle/<svc>.env` | each service's **role-id + secret-id** (must match the Vault AppRole roles) — gitignored, per-service | file backup alongside the vault snapshot, OR regenerate (below) |

**Consistency rule:** the DB passwords live in Vault and the DB roles live in Postgres — a restore must bring
Vault and Postgres to the **same point in time**, or a service's AppRole-read password will not match the DB role
and it will fail to connect. Restore both volumes from the same snapshot set, or restore Postgres and then
re-seed the passwords into Vault (installer, below).

## Restore

1. **Stop the stack** (`docker compose … down`, no `-v`).
2. **Restore the data volumes** — Vault and Postgres from the **same** snapshot set (EBS snapshot, or `pg_restore`
   into a fresh DB + vault volume restore). Do not restore one without the other.
3. **Restore (or regenerate) the AppRole env_files:**
   - If `deploy/local-dev/vault/approle/*.env` was backed up with the vault snapshot and the roles/secret-ids in
     the restored Vault still match → nothing to do.
   - Otherwise, after Vault is unsealed, re-run the installer's AppRole provisioning (idempotent): it rewrites
     the policies, recreates the roles, issues fresh secret-ids and rewrites every `<svc>.env`
     (`_setup_vault_approle` in `deploy/installer/install.sh`). This is safe on a restored stack.
4. **Bring the stack up.** Each service's `prod-guard.sh` performs its AppRole login and reads its scoped
   secrets. Verify with the two gates: `conformance/flow_map_test.py` (networks) and
   `conformance/vault_scope_test.py` (each service reads only its own Vault paths).
5. **Smoke-test** per RELEASE-PLAN Stage 0: a kernel read resolves, a login succeeds, the filestore serves a
   known blob. Record RTO.

> If Postgres is restored but Vault is **not** (e.g. a DB-only roll-back), the DB-role passwords in the restored
> DB will not match Vault → re-set them: `ALTER ROLE <role> PASSWORD '<new>'` in Postgres AND write the same value
> to the Vault path (`secret/data/localdev/<role>/password`), then restart the service. The installer's split-role
> step does both and is the supported path.

## Credential rotation (per service)

All rotation is per-service and does not touch other services. The scoped tokens are short-lived/renewable, so
most rotations are "update the source + restart the one service".

### Rotate a service's AppRole secret-id (the credential at rest)
```
# as the install-time root (not a service):
vault write -f auth/approle/role/<svc>/secret-id        # issues a NEW secret-id
# write it to the per-service env_file and restart ONLY that service:
#   VAULT_ROLE_ID=<same>  VAULT_SECRET_ID=<new>   → deploy/local-dev/vault/approle/<svc>.env
docker compose … up -d --force-recreate --no-deps <svc>
# optionally revoke the old secret-id accessor:
vault list auth/approle/role/<svc>/secret-id        # find the old accessor
vault write auth/approle/role/<svc>/secret-id-accessor/destroy secret_id_accessor=<old>
```
Prefer `_setup_vault_approle` (installer) to rotate **all** services' secret-ids at once; it regenerates every
`<svc>.env` and is idempotent.

### Rotate a service's scoped token
Just `--force-recreate` the service — `prod-guard.sh` logs in afresh and gets a new token. (Tokens also renew
within their TTL; a restart is the simplest rotation.)

### Rotate a DB-role password
```
NEW=$(openssl rand -base64 24)
vault kv put secret/localdev/<role> password="$NEW"      # e.g. kernel-app / network-app / identity-lockout
#   (the service reads secret/data/localdev/<role>/password via its policy)
docker compose exec -T -e VAULT_TOKEN=<root> postgres psql -U <owner> -c "ALTER ROLE <role> PASSWORD '$NEW'"
docker compose … up -d --force-recreate --no-deps <service-that-uses-that-role>
```
Do Vault and Postgres together (consistency rule). The installer's split-role step performs both.

### Rotate the Vault root token
Root is install-time only (removed from every service). Rotate with `vault operator generate-root` (or issue a
new root and revoke the old), update `/vault/data/init.json`, and keep it off every service. No service restart
is needed because services do not hold root.

### Rotate a transit key (identity issuer / network authority)
```
vault write -f transit/keys/<key>/rotate        # new version; old versions still verify prior signatures
```
Signers use the latest version automatically; verifiers accept prior versions, so rotation is non-breaking. Bump
`min_decryption_version` later to retire old key material.

## Production hardening (recorded, not in local-dev)

- **Vault unseal**: local-dev auto-unseals from a single key on the vault volume (demo). Production uses **KMS
  auto-unseal** (a RELEASE-PLAN gate — see step 8 of the slice / RELEASE-PLAN) and keeps unseal keys off-box.
- **Secret-id TTL + auto-renew**: local-dev AppRole tokens are renewable with a bounded TTL (24h/168h) and are
  re-minted on restart; a production **Vault Agent** sidecar should renew them continuously (recorded follow-up).
- **Snapshots**: schedule EBS snapshots (vault + postgres together) and test the restore drill (RELEASE-PLAN
  Stage 0) on a copy before every production change.

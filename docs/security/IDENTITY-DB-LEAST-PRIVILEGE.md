# Identity DB access — least-privilege for the lockout store

**Date:** 2026-11-06 · **Context:** the durable brute-force lockout store (ADR-0121) gave the identity service
a Postgres connection. This note reports what that connection can reach today and the least-privilege
remediation.

## Step 1 — what identity connects as today (the finding)

As first wired (local-dev), identity connects with:

| | value |
|---|---|
| role (`DB_USER`) | **`kernel`** |
| password | **literal in compose** (`DB_PASSWORD: kernel`) |
| database | `kernel` |

`kernel` is the cluster's **superuser**: `Superuser, Create role, Create DB, Replication, Bypass RLS`, and it
**owns every table** in `public` — `registry_version` (~1M rows of governed records), `kernel_admin_audit`,
`kv`, `registry_schema_meta`, and `identity_login_fails`.

**Finding:** identity needs exactly one table (`identity_login_fails`: SELECT/INSERT/DELETE) but holds
superuser rights over the entire governed registry and the audit log. A compromise of the IdP process — or a
bug in it — could read or rewrite any registry row or the audit trail. The credential is also a committed
literal. **Massively over-privileged; remediated in step 2.**

PostgreSQL is **16.15**, so the `PUBLIC` role has no default `CREATE` on schema `public` and no default table
privileges — a purpose-made role is naturally confined to exactly what it is granted.

## Step 2 — least-privilege role `identity_lockout` (remediation)

A dedicated login role with access to **only** `identity_login_fails`:

- Role `identity_lockout` (LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE). Password generated at bootstrap and
  stored in **local Vault** (`secret/data/localdev/identity-lockout`); identity reads it at startup via
  `DB_PASSWORD_VAULT_PATH` — **no literal in compose**.
- The table + indexes are created **once, by the privileged bootstrap** (as `kernel`), then
  `GRANT SELECT, INSERT, DELETE ON identity_login_fails TO identity_lockout` + `GRANT USAGE ON SCHEMA public`.
  No grants on `registry_version`, `kernel_admin_audit`, `kv`, or `registry_schema_meta`.
- Identity connects as `identity_lockout`. Its `_fails_db_ready` probes with a SELECT (it no longer needs to
  CREATE — the bootstrap owns DDL), so a non-owner role works.

**Proof (step 2, live):** connecting as `identity_lockout`, `SELECT … FROM identity_login_fails` succeeds while
`SELECT … FROM registry_version` is refused with `permission denied for table registry_version`. The lockout
flow still works end to end, and the credential is Vault-sourced.

## Related
- Fallback behaviour when the DB is unreachable: `../operator/OPERATOR-GUIDE.md` (lockout store mode on the
  health endpoint) and FOUNDATIONS §F8 (the alerted availability-over-strictness exception for this counter).
- Hashing + durable counters: `../performance/IDENTITY-KDF-REPORT.md`.

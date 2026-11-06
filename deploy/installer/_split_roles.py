"""4b split-role provisioning — idempotent, existence-guarded, runnable INSIDE a container that has psycopg2 +
Vault access (the network image). Safe to run before OR after the migrator creates the tables, and on an
already-up stack (converge). Run via `docker compose run --rm -T network python3 - < _split_roles.py` on a
fresh install, or `docker compose exec -T network python3 - < _split_roles.py` on an up stack.

  - Creates NOSUPERUSER roles migrator / kernel_app / network_app with Vault passwords (reuse-or-generate).
  - Grants USAGE on schema public to all three; CREATE on schema public to migrator (sole DDL author, PG15+).
  - Ensures kernel_kv / network_kv exist; on a legacy DB copies the shared `kv` rows to them by owner.
  - For every split table/sequence that EXISTS: OWNER→migrator + per-service DML grants (kernel_app → its 4
    tables + seqs; network_app → network_kv). Non-existent tables are skipped (fresh, pre-migrator pass).

Env: INSTANCE (default localdev), DB_HOST (default postgres), VAULT_ADDR, VAULT_TOKEN. Prints no secrets."""
import os, json, secrets, urllib.request, urllib.error
import psycopg2

INST = os.environ.get("INSTANCE", "localdev")
VA = (os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/")
VT = os.environ.get("VAULT_TOKEN", "")


def vault_pw(path, prefix):
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(VA + "/v1/" + path, headers={"X-Vault-Token": VT}), timeout=8))
        pw = ((d.get("data") or {}).get("data") or {}).get("password")
        if pw:
            return pw
    except urllib.error.HTTPError:
        pass
    pw = f"{prefix}_" + secrets.token_hex(24)
    urllib.request.urlopen(urllib.request.Request(VA + "/v1/" + path, data=json.dumps({"data": {"password": pw}}).encode(),
        headers={"X-Vault-Token": VT, "Content-Type": "application/json"}, method="POST"), timeout=8).read()
    return pw


roles = {"migrator": (f"secret/data/{INST}/migrator/password", "mg"),
         "kernel_app": (f"secret/data/{INST}/kernel-app/password", "ka"),
         "network_app": (f"secret/data/{INST}/network-app/password", "na")}
pw = {r: vault_pw(p, pre) for r, (p, pre) in roles.items()}

c = psycopg2.connect(host=os.environ.get("DB_HOST", "postgres"), port=5432, dbname="kernel", user="kernel", password="kernel")
c.autocommit = True
cur = c.cursor()


def table_exists(t):
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (t,))
    return cur.fetchone() is not None


def seq_exists(s):
    cur.execute("SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name=%s", (s,))
    return cur.fetchone() is not None


for r in roles:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (r,))
    if not cur.fetchone():
        cur.execute(f"CREATE ROLE {r} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
    cur.execute(f"ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s", (pw[r],))
    cur.execute(f"GRANT USAGE ON SCHEMA public TO {r}")
cur.execute("GRANT CREATE ON SCHEMA public TO migrator")   # sole DDL author (PG15+ needs this)

# kv split tables — ensure present (migrator makes these too; harmless if already there).
cur.execute("CREATE TABLE IF NOT EXISTS kernel_kv  (store TEXT, key TEXT, value JSONB, PRIMARY KEY(store,key))")
cur.execute("CREATE TABLE IF NOT EXISTS network_kv (store TEXT, key TEXT, value JSONB, PRIMARY KEY(store,key))")

# Legacy shared-kv split copy (idempotent) — only if the old `kv` still exists.
if table_exists("kv"):
    KERNEL_NS = ("tenant_datasets", "cases", "installed", "installed_schemas")
    cur.execute("INSERT INTO kernel_kv  SELECT * FROM kv WHERE store = ANY(%s) ON CONFLICT (store,key) DO NOTHING", (list(KERNEL_NS),))
    cur.execute("INSERT INTO network_kv SELECT * FROM kv WHERE NOT (store = ANY(%s)) ON CONFLICT (store,key) DO NOTHING", (list(KERNEL_NS),))

KERNEL_TABLES = ["registry_version", "registry_schema_meta", "kernel_admin_audit", "kernel_kv"]
SEQS = ["registry_version_seq_seq", "kernel_admin_audit_seq_seq"]

# Ownership → migrator (only tables/sequences that already exist; skipped on the pre-migrator pass).
for t in [x for x in KERNEL_TABLES + ["network_kv"] if table_exists(x)]:
    cur.execute(f"ALTER TABLE {t} OWNER TO migrator")
for s in [x for x in SEQS if seq_exists(x)]:
    cur.execute(f"ALTER SEQUENCE {s} OWNER TO migrator")

# Clean slate then least-privilege DML (guarded by existence).
for r in ("kernel_app", "network_app"):
    for t in [x for x in KERNEL_TABLES + ["network_kv"] if table_exists(x)]:
        cur.execute(f"REVOKE ALL ON {t} FROM {r}")
    for s in [x for x in SEQS if seq_exists(x)]:
        cur.execute(f"REVOKE ALL ON SEQUENCE {s} FROM {r}")
for t in [x for x in KERNEL_TABLES if table_exists(x)]:
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO kernel_app")
for s in [x for x in SEQS if seq_exists(x)]:
    cur.execute(f"GRANT USAGE, SELECT, UPDATE ON SEQUENCE {s} TO kernel_app")
if table_exists("network_kv"):
    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON network_kv TO network_app")

present = sum(1 for t in KERNEL_TABLES + ["network_kv"] if table_exists(t))

# identity_lockout — the identity service's durable brute-force lockout store (ADR-0121). Not a 4b kernel
# split role, but provisioned here so ONE installer step re-syncs EVERY DB-role password from Vault (the
# restore runbook depends on this: after a volume restore the pg role passwords drift from Vault and every
# service that authenticates to Postgres must be re-synced). Least-privilege: SELECT/INSERT/DELETE on
# identity_login_fails only — no registry/audit tables. Idempotent (reuse-or-generate password; guarded DDL).
il_pw = vault_pw(f"secret/data/{INST}/identity-lockout/password", "il")
cur.execute("SELECT 1 FROM pg_roles WHERE rolname='identity_lockout'")
if not cur.fetchone():
    cur.execute("CREATE ROLE identity_lockout LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
cur.execute("ALTER ROLE identity_lockout WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s", (il_pw,))
cur.execute("CREATE TABLE IF NOT EXISTS identity_login_fails (k TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL)")
cur.execute("CREATE INDEX IF NOT EXISTS identity_login_fails_k_ts ON identity_login_fails (k, ts)")
cur.execute("GRANT USAGE ON SCHEMA public TO identity_lockout")
cur.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM identity_lockout")
cur.execute("GRANT SELECT, INSERT, DELETE ON identity_login_fails TO identity_lockout")

cur.close(); c.close()
print(f"[split-roles] migrator/kernel_app/network_app + identity_lockout ready (split tables present: {present}/5)")

#!/usr/bin/env python3
"""Database-grant audit as a matrix case (slice-1h, DEBT-B93/B103 — exit condition 8; ARC-3, FND-10).

Read-only, against the LIVE fact store (psql in the postgres container as the install-time superuser):
  1. the LOGIN roles are exactly the declared set; no service role is superuser / createrole / createdb / bypassrls;
  2. every public-schema table grant to a service role EQUALS the declared least-privilege map (more = fail, less = fail);
     the kernel's AUDIT tables are append-only (SELECT, INSERT) for its runtime role;
  3. PUBLIC holds no privilege on any public-schema table; only `migrator` may CREATE in schema public;
  4. every public-schema table is owned by `migrator` (the sole DDL author) — except identity's own lockout table;
  5. no running service is connected as the superuser.
Writes conformance/results/local-dev-dbgrants.json. Exit 1 on any finding.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402

LOGIN_ROLES = {"kernel", "migrator", "kernel_app", "network_app", "identity_lockout"}   # kernel = install-time superuser
SUPERUSER = "kernel"
DML = {"SELECT", "INSERT", "UPDATE", "DELETE"}
EXPECTED = {
    "kernel_app": {"registry_version": DML, "registry_schema_meta": DML, "kernel_kv": DML,
                   "kernel_admin_audit": {"SELECT", "INSERT"}, "kernel_authz_decision": {"SELECT", "INSERT"}},
    "network_app": {"network_kv": DML},
    "identity_lockout": {"identity_login_fails": {"SELECT", "INSERT", "DELETE"}},
    "migrator": None,                                   # owner of the tables: privileges via ownership, checked in (4)
}
OWNER_EXCEPTIONS = {"identity_login_fails"}
cases, bad = [], 0


def q(sql):
    r = subprocess.run(["docker", "exec", "airawat-ld-postgres", "sh", "-c", 'psql -U "$POSTGRES_USER" -d kernel -tAF"|" -c "$0"', sql],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("✗ DB-grant audit could not query the fact store: %s" % r.stderr[:200])
    return [l.split("|") for l in r.stdout.strip().splitlines() if l.strip()]


def check(name, ok, detail):
    global bad
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail)
    cases.append({"case": name, "rules": ["ARC-3", "FND-10"], "result": "PASS" if ok else "FAIL", "detail": detail[:300]})
    bad += (not ok)


print("▶ DB-grant audit (ARC-3, live fact store)")
roles = {r[0]: r[1:] for r in q("select rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls from pg_roles "
                                 "where rolcanlogin and rolname !~ '^pg_'")}
check("the login roles are exactly the declared set", set(roles) == LOGIN_ROLES,
      "login roles %s; undeclared %s; missing %s" % (sorted(roles), sorted(set(roles) - LOGIN_ROLES), sorted(LOGIN_ROLES - set(roles))))
elevated = {r: v for r, v in roles.items() if r != SUPERUSER and "t" in v}
check("no service role is superuser / createrole / createdb / bypassrls", not elevated, "elevated: %s" % (elevated or "none"))
grants = {}
for grantee, table, priv in q("select grantee, table_name, privilege_type from information_schema.role_table_grants "
                              "where table_schema='public'"):
    grants.setdefault(grantee, {}).setdefault(table, set()).add(priv)
for role, exp in EXPECTED.items():
    if exp is None:
        continue
    got = grants.get(role, {})
    diff = {t: {"extra": sorted(got.get(t, set()) - exp.get(t, set())), "missing": sorted(exp.get(t, set()) - got.get(t, set()))}
            for t in set(got) | set(exp) if got.get(t, set()) != exp.get(t, set())}
    check("%s holds exactly its declared least-privilege table grants" % role, not diff, ("differences %s" % diff) if diff else
          "; ".join("%s=%s" % (t, ",".join(sorted(p))) for t, p in sorted(exp.items())))
audit_rw = {t: sorted(grants.get("kernel_app", {}).get(t, set()) & {"UPDATE", "DELETE", "TRUNCATE"})
            for t in ("kernel_admin_audit", "kernel_authz_decision")}
check("the kernel's audit tables are append-only for its runtime role (no UPDATE/DELETE)", not any(audit_rw.values()),
      "kernel_app write/erase on audit: %s" % audit_rw)
check("PUBLIC holds no privilege on any public-schema table", "PUBLIC" not in grants,
      "PUBLIC grants: %s" % (grants.get("PUBLIC") or "none"))
creators = [r[0] for r in q("select rolname from pg_roles where rolcanlogin and rolname <> '%s' and has_schema_privilege(rolname, 'public', 'CREATE')" % SUPERUSER)]
check("only migrator may CREATE in schema public", creators == ["migrator"], "CREATE: %s" % creators)
owners = {r[0]: r[1] for r in q("select tablename, tableowner from pg_tables where schemaname='public'")}
wrong = {t: o for t, o in owners.items() if o != "migrator" and t not in OWNER_EXCEPTIONS}
check("every public-schema table is owned by migrator (sole DDL author)", owners and not wrong, "%d tables; wrong owner: %s" % (len(owners), wrong or "none"))
su = q("select count(*) from pg_stat_activity where usename = '%s' and pid <> pg_backend_pid() and backend_type = 'client backend'" % SUPERUSER)
check("no running service is connected as the superuser", su and su[0][0] == "0", "superuser client sessions: %s" % (su[0][0] if su else "?"))
evidence.write("dbgrants", cases)
print(("✗" if bad else "✓") + " DB-grant audit: %d finding(s)" % bad)
sys.exit(1 if bad else 0)

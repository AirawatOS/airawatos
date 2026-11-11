#!/usr/bin/env python3
"""Database-grant audit by EFFECTIVE privilege (slice-1i, DEBT-B131 — was direct grants only; ARC-3, FND-10).

The previous audit read information_schema DIRECT grants, so a privilege arriving any other way was invisible: through a
group role the service role is a member of (the final review's case), a column-level grant, a grant to PUBLIC, a sequence
grant (setval), or a SECURITY DEFINER function owned by the table owner. This audit asks Postgres what each role can
ACTUALLY do — has_table_privilege / has_any_column_privilege / has_sequence_privilege, which resolve membership,
inheritance and PUBLIC — for EVERY role that can log in and every public-schema table and sequence, and compares the
result with an ALLOW-LIST. Anything not on the list fails, however it was granted.

  1. login roles are exactly the declared set; no service role is superuser / createrole / createdb / bypassrls /
     replication; service roles are members of NO other role (no inherited privilege at all);
  2. per role × table × privilege (SELECT INSERT UPDATE DELETE TRUNCATE REFERENCES TRIGGER, table- and column-level):
     effective privileges EQUAL the allow-list (owner `migrator` and the install-time superuser excepted — owners hold
     everything on what they own; they are not runtime roles);
  3. per role × sequence (USAGE SELECT UPDATE): effective privileges EQUAL the allow-list (USAGE only);
  4. the audit tables are append-only for every runtime role, by effect;
  5. no SECURITY DEFINER function exists in a non-system schema (it would run with its owner's rights);
  6. only migrator may CREATE in schema public; every public table is owned by migrator (identity's lockout table aside);
  7. no running service is connected as the superuser.
Writes conformance/results/local-dev-dbgrants.json. Exit 1 on any finding.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402

LOGIN_ROLES = {"kernel", "migrator", "kernel_app", "network_app", "identity_lockout"}
SUPERUSER, OWNER = "kernel", "migrator"
RUNTIME = ("kernel_app", "network_app", "identity_lockout")
TPRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
SPRIVS = ("USAGE", "SELECT", "UPDATE")
DML = {"SELECT", "INSERT", "UPDATE", "DELETE"}
AUDIT = ("kernel_admin_audit", "kernel_authz_decision")
ALLOW_T = {   # role -> table -> the ONLY privileges it may hold, by any route
    "kernel_app": {"registry_version": DML, "registry_schema_meta": DML, "kernel_kv": DML,
                   "kernel_admin_audit": {"SELECT", "INSERT"}, "kernel_authz_decision": {"SELECT", "INSERT"}},
    "network_app": {"network_kv": DML},
    "identity_lockout": {"identity_login_fails": {"SELECT", "INSERT", "DELETE"}},
}
ALLOW_S = {"kernel_app": {"registry_version_seq_seq": {"USAGE"}, "kernel_admin_audit_seq_seq": {"USAGE"},
                          "kernel_authz_decision_seq_seq": {"USAGE"}}}
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
    cases.append({"case": name, "rules": ["ARC-3", "FND-10"], "result": "PASS" if ok else "FAIL", "detail": detail[:400]})
    bad += (not ok)


print("▶ DB-grant audit by EFFECTIVE privilege (ARC-3, live fact store)")
roles = {r[0]: r[1:] for r in q("select rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication from pg_roles "
                                 "where rolcanlogin and rolname !~ '^pg_'")}
check("the login roles are exactly the declared set", set(roles) == LOGIN_ROLES,
      "login roles %s; undeclared %s; missing %s" % (sorted(roles), sorted(set(roles) - LOGIN_ROLES), sorted(LOGIN_ROLES - set(roles))))
elevated = {r: v for r, v in roles.items() if r != SUPERUSER and "t" in v}
check("no service role is superuser / createrole / createdb / bypassrls / replication", not elevated, "elevated: %s" % (elevated or "none"))
mem = q("select u.rolname, g.rolname from pg_auth_members m join pg_roles g on g.oid=m.roleid join pg_roles u on u.oid=m.member "
        "where u.rolname in (%s)" % ",".join("'%s'" % r for r in RUNTIME + (OWNER,)))
check("no runtime role (or the owner) is a member of another role — nothing is inherited", not mem,
      "memberships: %s" % (["%s ∈ %s" % (u, g) for u, g in mem] or "none"))

tables = [r[0] for r in q("select tablename from pg_tables where schemaname='public'")]
seqs = [r[0] for r in q("select sequencename from pg_sequences where schemaname='public'")]
expr = ",".join("has_table_privilege('%s', 'public.'||t, '%s') or has_any_column_privilege('%s', 'public.'||t, '%s')"
                % (r, p, r, p) if p in ("SELECT", "INSERT", "UPDATE", "REFERENCES") else "has_table_privilege('%s', 'public.'||t, '%s')" % (r, p)
                for r in RUNTIME for p in TPRIVS)
eff = {}
for row in q("select t, %s from unnest(array[%s]) t" % (expr, ",".join("'%s'" % t for t in tables))):
    t, vals = row[0], row[1:]
    i = 0
    for r in RUNTIME:
        for p in TPRIVS:
            if vals[i] == "t":
                eff.setdefault(r, {}).setdefault(t, set()).add(p)
            i += 1
for r in RUNTIME:
    got, allow = eff.get(r, {}), ALLOW_T.get(r, {})
    diff = {t: {"extra": sorted(got.get(t, set()) - allow.get(t, set())), "missing": sorted(allow.get(t, set()) - got.get(t, set()))}
            for t in set(got) | set(allow) if got.get(t, set()) != allow.get(t, set())}
    check("%s's EFFECTIVE table privileges equal its allow-list (incl. inherited, column-level and PUBLIC)" % r, not diff,
          ("differences %s" % diff) if diff else "; ".join("%s=%s" % (t, ",".join(sorted(p))) for t, p in sorted(allow.items())))
for t in AUDIT:
    w = {r: sorted(eff.get(r, {}).get(t, set()) & {"UPDATE", "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES"}) for r in RUNTIME}
    check("audit table %s is append-only for every runtime role, by effect" % t, not any(w.values()), "write/erase rights: %s" % w)

sexpr = ",".join("has_sequence_privilege('%s', 'public.'||s, '%s')" % (r, p) for r in RUNTIME for p in SPRIVS)
seff = {}
for row in q("select s, %s from unnest(array[%s]) s" % (sexpr, ",".join("'%s'" % x for x in seqs))):
    s_, vals = row[0], row[1:]
    i = 0
    for r in RUNTIME:
        for p in SPRIVS:
            if vals[i] == "t":
                seff.setdefault(r, {}).setdefault(s_, set()).add(p)
            i += 1
for r in RUNTIME:
    got, allow = seff.get(r, {}), ALLOW_S.get(r, {})
    diff = {s_: {"extra": sorted(got.get(s_, set()) - allow.get(s_, set())), "missing": sorted(allow.get(s_, set()) - got.get(s_, set()))}
            for s_ in set(got) | set(allow) if got.get(s_, set()) != allow.get(s_, set())}
    check("%s's EFFECTIVE sequence privileges equal its allow-list (USAGE only — no setval)" % r, not diff,
          ("differences %s" % diff) if diff else ("%s" % ({k: sorted(v) for k, v in allow.items()} or "none")))

sd = q("select n.nspname||'.'||p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
       "where p.prosecdef and n.nspname not in ('pg_catalog','information_schema')")
check("no SECURITY DEFINER function exists outside the system schemas", not sd, "found: %s" % ([x[0] for x in sd] or "none"))
creators = [r[0] for r in q("select rolname from pg_roles where rolcanlogin and rolname <> '%s' and has_schema_privilege(rolname, 'public', 'CREATE')" % SUPERUSER)]
check("only migrator may CREATE in schema public (effective)", creators == [OWNER], "CREATE: %s" % creators)
owners = {r[0]: r[1] for r in q("select tablename, tableowner from pg_tables where schemaname='public'")}
wrong = {t: o for t, o in owners.items() if o != OWNER and t not in OWNER_EXCEPTIONS}
check("every public-schema table is owned by migrator (sole DDL author)", owners and not wrong, "%d tables; wrong owner: %s" % (len(owners), wrong or "none"))
su = q("select count(*) from pg_stat_activity where usename = '%s' and pid <> pg_backend_pid() and backend_type = 'client backend'" % SUPERUSER)
check("no running service is connected as the superuser", su and su[0][0] == "0", "superuser client sessions: %s" % (su[0][0] if su else "?"))
evidence.write("dbgrants", cases)
print(("✗" if bad else "✓") + " DB-grant audit: %d finding(s)" % bad)
sys.exit(1 if bad else 0)

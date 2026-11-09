#!/usr/bin/env python3
"""Mutation self-test of the DB-grant audit (slice-1i, DEBT-B131).

Applies, ONE AT A TIME, a privilege that lets a runtime role rewrite the audit trail — granted by a route OTHER than a
direct table grant — runs the audit, and requires it to FAIL; then reverts and requires it to PASS again:
  1. the final review's case: UPDATE/DELETE on an audit table to a NOLOGIN GROUP role, kernel_app made a member;
  2. a COLUMN-level UPDATE grant on an audit table;
  3. UPDATE granted to PUBLIC on an audit table;
  4. UPDATE on an audit SEQUENCE (setval survives ROLLBACK);
  5. a SECURITY DEFINER function owned by the table owner that deletes audit rows, executable by PUBLIC;
  6. a two-level chain: group role → nested group role → kernel_app.
AUDIT=<path> runs another copy of the audit (e.g. the pre-1i one). Live; every mutation is reverted. Exit 1 on failure.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.environ.get("AUDIT", os.path.join(ROOT, "verify/db_grant_audit.py"))
MUT = [
    ("group role (final-review case)",
     "create role aos_st_g nologin; grant update, delete on kernel_admin_audit to aos_st_g; grant aos_st_g to kernel_app;",
     "revoke aos_st_g from kernel_app; revoke all on kernel_admin_audit from aos_st_g; drop role aos_st_g;"),
    ("column-level UPDATE", "grant update (decision) on kernel_admin_audit to kernel_app;",
     "revoke update (decision) on kernel_admin_audit from kernel_app;"),
    ("UPDATE to PUBLIC", "grant update on kernel_authz_decision to public;", "revoke update on kernel_authz_decision from public;"),
    ("sequence UPDATE (setval)", "grant update on sequence kernel_admin_audit_seq_seq to kernel_app;",
     "revoke update on sequence kernel_admin_audit_seq_seq from kernel_app;"),
    ("SECURITY DEFINER function",
     "create function public.aos_st_wipe() returns void language sql security definer as 'delete from kernel_admin_audit where false'; "
     "alter function public.aos_st_wipe() owner to migrator;",
     "drop function public.aos_st_wipe();"),
    ("nested group roles",
     "create role aos_st_g1 nologin; create role aos_st_g2 nologin; grant delete on kernel_authz_decision to aos_st_g2; "
     "grant aos_st_g2 to aos_st_g1; grant aos_st_g1 to kernel_app;",
     "revoke aos_st_g1 from kernel_app; revoke aos_st_g2 from aos_st_g1; revoke all on kernel_authz_decision from aos_st_g2; "
     "drop role aos_st_g1; drop role aos_st_g2;"),
]


def psql(sql):
    return subprocess.run(["docker", "exec", "airawat-ld-postgres", "sh", "-c", 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d kernel -q -c "$0"', sql],
                          capture_output=True, text=True)


def audit():
    return subprocess.run([sys.executable, AUDIT], capture_output=True, text=True).returncode


fails = []
print("▶ DB-grant audit self-test (B131) — audit under test: %s" % os.path.relpath(AUDIT, ROOT))
base = audit()
print(("  ✓" if base == 0 else "  ✗") + " baseline: the audit passes on the unmutated database (exit %d)" % base)
if base:
    fails.append("baseline")
for name, do, undo in MUT:
    r = psql(do)
    if r.returncode:
        print("  ✗ %s: could not apply (%s)" % (name, r.stderr.strip()[:120])); fails.append(name); psql(undo); continue
    rc = audit()
    psql(undo)
    after = audit()
    ok = rc != 0 and after == 0
    print(("  ✓" if ok else "  ✗") + " %s → audit %s; after revert %s" % (name, "FAILS" if rc else "STAYED GREEN", "passes" if after == 0 else "FAILS"))
    if not ok:
        fails.append(name)
print(("✗" if fails else "✓") + " DB-grant audit self-test: %d of %d mutation(s) not caught" % (len(fails), len(MUT)))
sys.exit(1 if fails else 0)

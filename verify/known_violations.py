#!/usr/bin/env python3
"""Static evidence of KNOWN violations for rules the matrix would otherwise show HELD (Layer 1 exit review, M1–M4).

The Layer 1 exit review found rules reading HELD because every case citing them PASSes, while the code still
violates them (the cases test one narrow surface). Each case below reproduces a recorded violation from the source
tree and is reported XFAIL (violation present) or XPASS (it looks fixed — review the rule). An XFAIL makes the rule
PARTIAL, never HELD (STATUS-MATRIX-DESIGN reduction). Writes conformance/results/local-dev-knownviolations.json.
"""
import glob, json, os, re, time
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "conformance", "results", "local-dev-knownviolations.json")
cases = []


def read(p):
    try:
        return open(os.path.join(ROOT, p), errors="replace").read()
    except Exception:
        return ""

def code(p):
    """slice-1h (DEBT-B99, re-review R6-3): the source WITHOUT comments (tokenize) — evidence is matched on code, so a
    comment like `# rate_limit` cannot flip a case. A missing/unreadable target is recorded as a FAIL (broken target)."""
    import io, tokenize
    src = read(p)
    if not src:
        cases.append({"case": "evidence target readable: " + p, "rules": ["FND-8"], "result": "FAIL", "detail": "missing or empty"})
        print("  ✗ FAIL  evidence target missing: " + p)
        return ""
    try:                                         # blank ONLY the comment text; layout (and every string) is kept
        lines = src.split("\n")
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type == tokenize.COMMENT:
                (r, c0), (_, c1) = t.start, t.end
                lines[r - 1] = lines[r - 1][:c0] + " " * (c1 - c0) + lines[r - 1][c1:]
        return "\n".join(lines)
    except Exception:
        return src


def finish(name):
    """Exit non-zero on a FAIL (broken target) or an XPASS (the recorded violation no longer reproduces: either it was
    fixed — update the case + rule status — or the detector broke). A net that cannot fail proves nothing."""
    import sys
    bad = [c for c in cases if c["result"] in ("FAIL", "XPASS")]
    for c in bad:
        print("  ✗ %s: %s — %s" % (c["result"], c["case"], c.get("detail", "")))
    print(("✗" if bad else "✓") + " %s: %d case(s), %d needing attention" % (name, len(cases), len(bad)))
    sys.exit(1 if bad or not cases else 0)



def xfail(rules, name, reproduced, detail):
    cases.append({"case": name, "rules": rules, "result": "XFAIL" if reproduced else "XPASS", "detail": detail})
    print(f"  {'XFAIL' if reproduced else 'XPASS'}  {'/'.join(rules):14} {name} — {detail}")


print("▶ known-violation evidence (Layer 1 exit review)")
k = code("kernel/api/app.py")
xfail(["FND-6", "REG-13"], "kernel is domain-blind (no domain vocabulary baked in) — DEBT-B8",
      bool(re.search(r"\b_NAT_KEYS\s*=\s*\(", k)), "kernel/api/app.py defines _NAT_KEYS (case_number, gstin, udise_code, …)")
n = code("network/api.py")
xfail(["PLT-4"], "the platform tenant confers nothing — DEBT-B2/A17/B82",
      'claims.get("tenant") == "airawat"' in n or 'AUTHORITY_TENANT = "airawat"' in n,
      "network/api.py grants operator/authority power by the tenant NAME 'airawat'")
# slice-1g (DEBT-B93 / review M3) — rules that read HELD from narrow cases while their spec status is PARTIAL:
pa = read("network/trust/platform_authority.py"); taz = read("network/trust_admin_authz.py")
xfail(["NET-3"], "network roles: second-holder SoD + never-zero network.admin (ADR-0122 extended to the network role set)",
      not re.search(r'FLOOR_ROLES\s*=\s*\{[^}]*"network\.admin"', pa) or 'else "legacy"' in taz,
      "FLOOR_ROLES (SoD + last-holder floor) covers only platform.authority/tenant.admin; NETWORK_ADMIN_AUTHZ defaults to "
      "'legacy' (DEBT-A14)")
m = re.search(r"def register\(body.*?PARTICIPANTS\[pid\] = entry", n, re.S)
reg = m.group(0) if m else ""
xfail(["PTC-1"], "participant registration records roles sought, conformance status and its service accounts",
      bool(reg) and not all(w in reg for w in ("role", "conformance", "service_account")),
      "network /v1/participants signs only the key + jurisdiction + kind; roles, conformance status and service accounts "
      "under the participant are not recorded (ADR-0124 service principals are free-standing)")
kc = read("kernel/api/kernelcore.py"); dcmp = read("deploy/local-dev/docker-compose.dev.yml")
off = [f for f in ("PROV_ENFORCE", "DATAPLANE_ENFORCE") if re.search(r'%s = os\.environ\.get\("%s", ""\)' % (f, f), kc)
       and not re.search(r"%s:\s*[\"']?(1|true|yes)" % f, dcmp)]
xfail(["REG-5"], "a write is authorized only by a recorded grant — never a token role (FND-2)",
      bool(off) or '.get("roles"' in kc,
      "kernel admin/write authority still read from token role claims (kernelcore _is_admin, DEBT-B1); enforcement "
      "switches default off and unset in local-dev: %s (DEBT-A2/A3)" % ", ".join(off))
au = read("network/authn.py")
m = re.search(r"def register_issuer\(([^)]*)\)", au)
xfail(["FND-15"], "external issuers are bound to a recorded tenant AND network; authority never widens by issuer",
      bool(m) and "network" not in m.group(1),
      "network authn.register_issuer(%s) has no network binding; the kernel grants admin from issuer + token role "
      "(DEBT-B1/B13)" % (m.group(1) if m else "?"))
# Layer 1 RE-REVIEW (DEBT-B103) — over-claims the re-review found:
# PLT-5 (re-review R2-2): local-dev ENFORCES the recorded role (compose PLATFORM_AUTHORITY_MODE: enforce) — the spec's
# PARTIAL text is stale for local-dev; the code default 'shadow' is fail-open and is recorded on DEBT-B110, not here.
rm = read("platform-spec/reference/runtime_manager.py") + read("components/_common/launcher.py")
xfail(["ARC-7"], "a placed/in-process component cannot reach the host service's Vault credential (re-review R3-1, DEBT-B105)",
      "/proc/1/environ" not in rm and "hidepid" not in read("deploy/local-dev/docker-compose.dev.yml"),
      "in-process components run as root in the runtime-manager container; PID 1's environ (VAULT_TOKEN) is readable — "
      "a scrubbed env does not isolate them (live: launcher password read, 200)")
# FND-16 (re-review R1-1, DEBT-B97) FIXED in slice-1h: gates refuse shadow in production and the guard is baked into every
# image — proven by verify/gateflags_test.py (shipped images, outside compose). Case removed.
# Layer 1 FINAL review (2026-11-09) — violations reproduced live by the reviewers, evidence from the source:
# FND-16 (FINAL F1-1, DEBT-B116) FIXED in slice-1i: production runs only allow-listed commands; proven by verify/gateflags_test.py.
xfail(["NET-12"], "a citizen sees only its own rows — never a tenant's by a username equal to the tenant id (FINAL F1-6, DEBT-B120)",
      'v.startswith(f"ds:{pid}:")' in n,
      "network _row_is_callers matches ds:<username>:… for shared-realm callers — a citizen registered as `localdev` saw ds:localdev: rows")
# slice-1g: review K1 (shared transit/*, B88) and K2 (brokers read platform credentials, B89) are FIXED and proven LIVE by
# conformance/vault_scope_test.py (actual sign / read attempts → 403); review W1 (no default-deny egress, B87) is FIXED and
# proven LIVE by conformance/flow_map_test.py (actual connection attempts). Their static evidence cases were removed.
# slice-1g: review N5 (unquoted secret name → ../ traversal, B90) is FIXED — secret_names.py validates tenant, component
# and name and follows no redirects; proven by verify/secret_names_test.py (make secret-names). Static case removed.
# Layer 1 CONDITIONS-ONLY re-review (2026-11-09) — violations reproduced LIVE by the reviewers, evidence from the source
# (docs/reviews/LAYER1-EXIT-CONDITIONS.md). Each makes its rule PARTIAL until the debt is closed.
# slice-1j: F-C4-1 (DEBT-B139) and F-C4-2 (DEBT-B140) FIXED — restore validates against the declared stack, stages, switches
# and rolls back; proven by verify/backup_restore_selftest.py and verify/restore_drill.py. Cases removed.
# slice-1k: re-check F-C4-3 (DEBT-B154, High) FIXED — restore never works in place (volume sets + atomic pointer; the
# previous set is never written or deleted); proven by verify/backup_restore_selftest.py. Case removed.
ga = code("verify/db_grant_audit.py")
xfail(["ARC-3"], "audit tables are append-only for every runtime role by effect, through views and rules too (conditions C1-N1, DEBT-B144)",
      "pg_rewrite" not in ga and "relkind" not in ga,
      "db_grant_audit enumerates pg_tables only: a migrator-owned view or rule let kernel_app delete/rewrite audit rows, audit green")
# slice-1j: C7-N3 (DEBT-B138) FIXED — exact configuration match (conformance/vault_scope_test.py exact_config), proven by
# verify/vault_scope_selftest.py (16 live mutations). Case removed.
gf = code("platform-spec/reference/gateflags.py") + read("deploy/runtime/airawat-entrypoint.sh")
xfail(["FND-16"], "production starts only allow-listed configuration, environment-borne server options included (conditions C2-N1, DEBT-B142)",
      "UVICORN_" not in gf,
      "the guard checks argv only: kernel:1i with AIRAWAT_ENV=production UVICORN_RELOAD=true started the reloader")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"env": "local-dev", "mode": "knownviolations", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "git_sha": "", "cases": cases}, open(OUT, "w"), indent=1)
_ev.seal(OUT)
finish('known-violation evidence')

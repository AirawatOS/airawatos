#!/usr/bin/env python3
"""Static evidence of KNOWN violations for rules the matrix would otherwise show HELD (Layer 1 exit review, M1–M4).

The Layer 1 exit review found rules reading HELD because every case citing them PASSes, while the code still
violates them (the cases test one narrow surface). Each case below reproduces a recorded violation from the source
tree and is reported XFAIL (violation present) or XPASS (it looks fixed — review the rule). An XFAIL makes the rule
PARTIAL, never HELD (STATUS-MATRIX-DESIGN reduction). Writes conformance/results/local-dev-knownviolations.json.
"""
import glob, json, os, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "conformance", "results", "local-dev-knownviolations.json")
cases = []


def read(p):
    try:
        return open(os.path.join(ROOT, p), errors="replace").read()
    except Exception:
        return ""


def xfail(rules, name, reproduced, detail):
    cases.append({"case": name, "rules": rules, "result": "XFAIL" if reproduced else "XPASS", "detail": detail})
    print(f"  {'XFAIL' if reproduced else 'XPASS'}  {'/'.join(rules):14} {name} — {detail}")


print("▶ known-violation evidence (Layer 1 exit review)")
k = read("kernel/api/app.py")
xfail(["FND-6", "REG-13"], "kernel is domain-blind (no domain vocabulary baked in) — DEBT-B8",
      "_NAT_KEYS = (" in k, "kernel/api/app.py defines _NAT_KEYS (case_number, gstin, udise_code, …)")
n = read("network/api.py")
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
gate = read("platform-spec/reference/svc_gate.py")
xfail(["FND-16"], "gates refuse shadow under production themselves, not only via the compose entrypoint (re-review R1-1, DEBT-B97)",
      "is_production" not in gate,
      "svc_gate.require() never consults gateflags.is_production(); the shipped images have no prod-guard entrypoint")
# slice-1g: review K1 (shared transit/*, B88) and K2 (brokers read platform credentials, B89) are FIXED and proven LIVE by
# conformance/vault_scope_test.py (actual sign / read attempts → 403); review W1 (no default-deny egress, B87) is FIXED and
# proven LIVE by conformance/flow_map_test.py (actual connection attempts). Their static evidence cases were removed.
# slice-1g: review N5 (unquoted secret name → ../ traversal, B90) is FIXED — secret_names.py validates tenant, component
# and name and follows no redirects; proven by verify/secret_names_test.py (make secret-names). Static case removed.
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"env": "local-dev", "mode": "knownviolations", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "git_sha": "", "cases": cases}, open(OUT, "w"), indent=1)

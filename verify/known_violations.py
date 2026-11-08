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
# slice-1g: review K1 (shared transit/*, B88) and K2 (brokers read platform credentials, B89) are FIXED and proven LIVE by
# conformance/vault_scope_test.py (actual sign / read attempts → 403); review W1 (no default-deny egress, B87) is FIXED and
# proven LIVE by conformance/flow_map_test.py (actual connection attempts). Their static evidence cases were removed.
s = read("platform-spec/reference/secrets.py")
m = re.search(r"def _path\(tenant, component, name=None\):\n(.*\n){1,3}", s)
unquoted = bool(m) and 'quote(name' not in m.group(0)
xfail(["ARC-7"], "a component injects only its own secrets — unquoted secret name allows ../ traversal (review N5)", unquoted,
      "secrets.py _path() quotes the component but not the secret name")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"env": "local-dev", "mode": "knownviolations", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "git_sha": "", "cases": cases}, open(OUT, "w"), indent=1)

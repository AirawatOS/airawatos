#!/usr/bin/env python3
"""Per-service Vault least-privilege test (FIX-PLAN L1-1b, step 5 — closes DEBT-B58).

For every Vault-using service: using the service's OWN runtime token (its AppRole-scoped token, read from PID 1's
environment), assert it CAN read its own path and CANNOT read another service's path (403); assert its token is
NOT the Vault root token; and assert no STATIC VAULT_TOKEN is baked into its container config. Services that use
no Vault door must carry no Vault token at all.

Runs on the HOST (needs docker + each container reaching Vault on the aos-data-secrets network). Emits
conformance/results/<env>-vaultscope.json (ARC-7 cases) for build_matrix.py. Exits non-zero on any violation.
Usage: python3 conformance/vault_scope_test.py
"""
import json, os, subprocess, sys, time

ENV = os.environ.get("AOS_ENV", "local-dev")
PFX = "airawat-ld-"

# tight services: (own readable path, a FOREIGN path that must be refused)
TIGHT = {
    "kernel":      ("secret/data/localdev/kernel-app/password",            "secret/data/localdev-operator/scheduler/password"),
    "network":     ("secret/data/localdev-network/trust-reader/password",  "secret/data/localdev/kernel-app/password"),
    "identity":    ("secret/data/localdev/identity-lockout/password",      "secret/data/localdev/kernel-app/password"),
    "scheduler":   ("secret/data/localdev-operator/scheduler/password",    "secret/data/localdev/kernel-app/password"),
    "automation":  ("secret/data/localdev-operator/scheduler/password",    "secret/data/localdev/kernel-app/password"),
    "event-relay": ("secret/data/localdev-operator/scheduler/password",    "secret/data/localdev/kernel-app/password"),
    "app-host":    ("secret/data/localdev-operator/app-host/password",     "secret/data/localdev/kernel-app/password"),
}
# broker service: svc-secrets is broad on secret/data/* BY DESIGN (it IS the KV broker; per-(tenant,component)
# authz is its own gate — the decision-function follow-up). Assert scoped non-root token + can read a sample.
BROAD = {
    "secrets":       "secret/data/localdev/kernel-app/password",
}
# slice-1c step 4 — model-gateway NARROWED from secret/data/* to the per-(tenant,component) KV SHAPE
# secret/data/+/+/*: (3-seg own path readable) AND (a 2-segment path now REFUSED 403, proving it is no longer
# the whole tree). own = 3-seg component-secret shape; short = 2-seg path that the narrowed glob excludes.
NARROWED = {
    "model-gateway": ("secret/data/localdev/kernel-app/password", "secret/data/localdev-operator/scheduler"),
}
# services with no Vault door — must carry no Vault token at all
NOVAULT = ["notify", "workflow", "decision", "filestore"]

RESULTS = []
def rec(rule, name, ok, detail, kind="testable"):
    RESULTS.append({"spec": "ARCHITECTURE", "rule": rule, "name": name,
                    "status": ("PASS" if ok else "FAIL") if kind == "testable" else kind, "detail": detail})
    print(("  ✓ " if ok else "  ✗ ") + "[%s] %s — %s" % (rule, name, detail)); return ok

def root_token():
    try:
        return subprocess.run(["docker", "exec", PFX + "vault", "sh", "-lc",
                               'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"'],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""

# in-container probe: print "TOKEN <tok>" then "<label> <status>" for each path read with PID1's token
_PROBE = r'''
import json, urllib.request, urllib.error, sys
tok = ""
try:
    for line in open("/proc/1/environ","rb").read().split(b"\0"):
        if line.startswith(b"VAULT_TOKEN="): tok = line.split(b"=",1)[1].decode()
except Exception: pass
print("TOKEN " + tok)
def rd(p):
    req = urllib.request.Request("http://vault:8200/v1/"+p, headers={"X-Vault-Token": tok})
    try: urllib.request.urlopen(req, timeout=6); return 200
    except urllib.error.HTTPError as e: return e.code
    except Exception: return 0
import os as _os
for lbl, p in [("OWN", _os.environ.get("P_OWN","")), ("FOREIGN", _os.environ.get("P_FOREIGN",""))]:
    if p: print(lbl + " " + str(rd(p)))
'''
def probe(svc, own="", foreign=""):
    try:
        r = subprocess.run(["docker", "exec", "-e", "P_OWN=" + own, "-e", "P_FOREIGN=" + foreign,
                            PFX + svc, "python3", "-c", _PROBE], capture_output=True, text=True, timeout=20)
        out = {}
        for ln in r.stdout.splitlines():
            k, _, v = ln.partition(" "); out[k] = v
        return out
    except Exception as e:
        return {"ERR": str(e)[:60]}

def config_has_static_vault_token(svc):
    try:
        r = subprocess.run(["docker", "inspect", "-f", "{{range .Config.Env}}{{println .}}{{end}}", PFX + svc],
                           capture_output=True, text=True, timeout=10)
        for ln in r.stdout.splitlines():
            if ln.startswith("VAULT_TOKEN=") and ln.split("=", 1)[1].strip():
                return True
    except Exception:
        pass
    return False

def main():
    print("▶ per-service Vault least-privilege test — env=%s" % ENV)
    ok_all = True
    ROOT = root_token()
    ok_all &= rec("ARC-7", "root token discoverable (to verify services do NOT use it)", bool(ROOT),
                  "root %s" % ("read" if ROOT else "NOT read — cannot verify"))

    for svc, (own, foreign) in TIGHT.items():
        o = probe(svc, own, foreign)
        tok = o.get("TOKEN", "")
        ok_all &= rec("ARC-7", "%s: holds a scoped (non-root) Vault token" % svc,
                      bool(tok) and tok != ROOT, "token present=%s, is-root=%s" % (bool(tok), tok == ROOT and bool(ROOT)))
        ok_all &= rec("ARC-7", "%s: CAN read its own path" % svc, o.get("OWN") in ("200", "404"),
                      "%s -> %s" % (own, o.get("OWN")))
        ok_all &= rec("ARC-7", "%s: CANNOT read a foreign service's path" % svc, o.get("FOREIGN") == "403",
                      "%s -> %s (want 403)" % (foreign, o.get("FOREIGN")))
        ok_all &= rec("ARC-7", "%s: no static VAULT_TOKEN in container config" % svc,
                      not config_has_static_vault_token(svc), "config static token present=%s" % config_has_static_vault_token(svc))

    for svc, sample in BROAD.items():
        o = probe(svc, sample, "")
        tok = o.get("TOKEN", "")
        ok_all &= rec("ARC-7", "%s (KV broker): scoped non-root token, broad by design" % svc,
                      bool(tok) and tok != ROOT and o.get("OWN") in ("200", "404"),
                      "token present=%s non-root=%s read=%s (svc-%s is intentionally broad — recorded widening)"
                      % (bool(tok), tok != ROOT, o.get("OWN"), svc))
        ok_all &= rec("ARC-7", "%s: no static VAULT_TOKEN in container config" % svc,
                      not config_has_static_vault_token(svc), "config static token present=%s" % config_has_static_vault_token(svc))

    for svc, (own, short) in NARROWED.items():
        o = probe(svc, own, short)
        tok = o.get("TOKEN", "")
        ok_all &= rec("ARC-7", "%s: holds a scoped (non-root) Vault token" % svc,
                      bool(tok) and tok != ROOT, "token present=%s, is-root=%s" % (bool(tok), tok == ROOT and bool(ROOT)))
        ok_all &= rec("ARC-7", "%s: CAN read a per-(tenant,component) component-secret path (its shape)" % svc,
                      o.get("OWN") in ("200", "404"), "%s -> %s" % (own, o.get("OWN")))
        ok_all &= rec("ARC-7", "%s: NARROWED — a 2-segment path is now REFUSED (no longer secret/data/*)" % svc,
                      o.get("FOREIGN") == "403", "%s -> %s (want 403; proves svc-model-gateway narrowed to +/+/*)" % (short, o.get("FOREIGN")))
        ok_all &= rec("ARC-7", "%s: no static VAULT_TOKEN in container config" % svc,
                      not config_has_static_vault_token(svc), "config static token present=%s" % config_has_static_vault_token(svc))

    for svc in NOVAULT:
        o = probe(svc)
        tok = o.get("TOKEN", "")
        ok_all &= rec("ARC-7", "%s: no Vault identity (uses no Vault door)" % svc,
                      not tok, "PID1 VAULT_TOKEN present=%s (want absent)" % bool(tok))

    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(d, exist_ok=True)
    out = {"env": ENV, "mode": "vaultscope", "base": "docker-host", "git_sha": os.environ.get("GIT_SHA", ""),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cases": [{"case": r["name"], "spec": r["spec"], "rule": r["rule"], "rules": [r["rule"]],
                      "mode": "vaultscope", "result": r["status"]} for r in RESULTS]}
    with open(os.path.join(d, "%s-vaultscope.json" % ENV), "w") as f:
        json.dump(out, f, indent=2)
    print("✓ Vault least-privilege PASS" if ok_all else "✗ Vault least-privilege FAILED")
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()

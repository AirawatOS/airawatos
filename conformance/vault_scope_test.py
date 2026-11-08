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
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

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
    # slice-1c-ii: decision + workflow now hold their OWN service-identity to mint svc:notify (svc-decision /
    # svc-workflow policies grant only their own password path).
    "decision":    ("secret/data/localdev-operator/decision/password",     "secret/data/localdev/kernel-app/password"),
    "workflow":    ("secret/data/localdev-operator/workflow/password",     "secret/data/localdev/kernel-app/password"),
    # slice-1c-iv step 2: the runtime manager reads ONLY the launcher password (moved off the scheduler).
    "runtime-manager": ("secret/data/localdev-operator/launcher/password", "secret/data/localdev-operator/scheduler/password"),
}
# slice-1g (DEBT-B89) — the two KV BROKERS (secrets broker, model-gateway) hold component secrets ONLY. Component
# secrets live in their OWN KV mount (`components/`, per-(tenant, component)); platform credentials (DB passwords, the
# provisioner and every service principal's password, the audit HMAC key) stay in `secret/`, where only each owner
# reads its own path. Each broker: CAN read+write its component mount; has NO capability on any platform credential.
COMPONENT_MOUNT = "components"
BROKERS = {"secrets": "localdev/ds%3Aslice1g%3Aprobe/api_key", "model-gateway": "localdev/ds%3Aslice1g%3Aprobe/api_key"}
PLATFORM_CREDS = (["secret/data/localdev/%s/password" % u for u in ("kernel-app", "migrator", "network-app", "identity-lockout")]
                  + ["secret/data/localdev-operator/%s/password" % u for u in
                     ("provisioner", "admin", "scheduler", "launcher", "kernel", "app-host", "decision", "workflow", "svcprobe")]
                  + ["secret/data/localdev-network/%s/password" % u for u in ("trust-writer", "trust-reader", "component-publisher", "platauth")]
                  + ["secret/data/localdev-network/trust-plane/audit_hmac"])
# app-host is not a broker, but held localdev-operator/* (review K3): it may read only its OWN credentials.
APP_HOST_OWN = {"secret/data/localdev-operator/app-host/password", "secret/data/localdev-network/component-publisher/password"}
# services with no Vault door — must carry no Vault token at all (slice-1c-ii: decision + workflow moved to
# TIGHT — they now mint svc:notify; notify VERIFIES tokens via JWKS, not Vault, so it stays here).
NOVAULT = ["notify", "filestore"]

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

# capabilities probe (slice-1g): with PID1's own token, ask Vault what it may do on each path (sys/capabilities-self),
# and optionally ATTEMPT an operation (POST path with a body) — prints "CAP <path> <caps>" / "TRY <path> <status>".
_CAPS = r'''
import json, urllib.request, urllib.error, sys, os
tok = ""
for line in open("/proc/1/environ","rb").read().split(b"\0"):
    if line.startswith(b"VAULT_TOKEN="): tok = line.split(b"=",1)[1].decode()
H = {"X-Vault-Token": tok, "Content-Type": "application/json"}
def post(p, body):
    r = urllib.request.Request("http://vault:8200/v1/"+p, data=json.dumps(body).encode(), headers=H, method="POST")
    try: return urllib.request.urlopen(r, timeout=8).status, json.loads(urllib.request.urlopen(r, timeout=8).read() or b"{}") if False else {}
    except urllib.error.HTTPError as e: return e.code, {}
    except Exception: return 0, {}
paths = json.loads(os.environ.get("CAPS","[]"))
if paths:
    r = urllib.request.Request("http://vault:8200/v1/sys/capabilities-self", data=json.dumps({"paths": paths}).encode(), headers=H, method="POST")
    try: d = json.loads(urllib.request.urlopen(r, timeout=8).read())
    except Exception as e: d = {}
    for p in paths: print("CAP", p, ",".join(d.get(p) or d.get("data", {}).get(p) or ["?"]))
for p in json.loads(os.environ.get("TRY","[]")):
    print("TRY", p, post(p, {"input": "c2xpY2UtMWctcHJvYmU="})[0])
'''
def caps(svc, paths=(), tries=()):
    r = subprocess.run(["docker", "exec", "-e", "CAPS=" + json.dumps(list(paths)), "-e", "TRY=" + json.dumps(list(tries)),
                        PFX + svc, "python3", "-c", _CAPS], capture_output=True, text=True, timeout=30)
    out = {"CAP": {}, "TRY": {}}
    for ln in r.stdout.splitlines():
        k, _, rest = ln.partition(" ")
        if k in out:
            pth, _, v = rest.rpartition(" "); out[k][pth] = v
    return out


def granted(c, write=False):
    """True if the capability string allows a read (or, write=True, a create/update/delete)."""
    want = {"create", "update", "delete", "sudo", "root"} if write else {"read", "root", "sudo"}
    return bool(set((c or "").split(",")) & want)


# slice-1g (DEBT-B88) — per-service transit keys: identity's issuer key usable ONLY by identity; the authority + steward
# keys ONLY by the network; every other service touches no transit key.
TRANSIT_KEYS = {"airawat-identity": "identity", "airawat-authority": "network", "steward-localdev": "network"}
TRANSIT_SERVICES = ["kernel", "network", "identity", "app-host", "scheduler", "secrets", "model-gateway", "decision",
                    "workflow", "automation", "event-relay", "runtime-manager"]


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

    # ADR-0131 / slice-1c-iv-c — the svc-network grant for the provisioner credential is EXACT: network can read
    # the provisioner's install-config secret (to mint svc:identity for join→provision) but NOT the operator
    # admin's bootstrap password next to it, nor any other operator-realm principal.
    for own, foreign in (("secret/data/localdev-operator/provisioner/password", "secret/data/localdev-operator/admin/password"),
                         ("secret/data/localdev-operator/provisioner/password", "secret/data/localdev-operator/app-host/password")):
        o = probe("network", own, foreign)
        ok_all &= rec("ARC-7", "network: CAN read the provisioner credential (svc:identity mint, ADR-0131)",
                      o.get("OWN") == "200", "%s -> %s (want 200)" % (own, o.get("OWN")))
        ok_all &= rec("ARC-7", "network: CANNOT read another operator-realm secret (grant is exact)",
                      o.get("FOREIGN") == "403", "%s -> %s (want 403)" % (foreign, o.get("FOREIGN")))

    # slice-1h (re-review R7-5): EVERY service is checked against EVERY platform credential (not one sample foreign path)
    # — it may read ONLY its documented own set; widening a policy to any other credential fails here.
    OWN = {
        "kernel": {"localdev/kernel-app", "localdev-operator/kernel"},
        "network": {"localdev/network-app", "localdev-network/trust-reader", "localdev-network/trust-writer",
                    "localdev-network/trust-plane", "localdev-operator/provisioner"},
        "identity": {"localdev/identity-lockout", "localdev-operator/admin", "localdev-operator/provisioner"},
        "scheduler": {"localdev-operator/scheduler"}, "automation": {"localdev-operator/scheduler"},
        "event-relay": {"localdev-operator/scheduler"},
        "app-host": {"localdev-operator/app-host", "localdev-network/component-publisher"},
        "decision": {"localdev-operator/decision"}, "workflow": {"localdev-operator/workflow"},
        "runtime-manager": {"localdev-operator/launcher"},
    }
    for svc, own in OWN.items():
        cp = caps(svc, PLATFORM_CREDS)["CAP"]
        readable = sorted(c.split("secret/data/", 1)[1].rsplit("/", 1)[0] for c in PLATFORM_CREDS if granted(cp.get(c)))
        extra = sorted(set(readable) - own)
        ok_all &= rec("ARC-7", "%s reads ONLY its own platform credentials (all %d checked)" % (svc, len(PLATFORM_CREDS)),
                      not extra, ("reads foreign: %s" % extra) if extra else ("readable: %s" % (readable or "none")))

    # slice-1g (DEBT-B89): brokers refused on EVERY platform credential (read and write, data and metadata), and an
    # ACTUAL read attempt on each must return 403. Positive: each broker can still write+read its component mount.
    for svc, comp in list(BROKERS.items()) + [("app-host", None)]:
        o = probe(svc)
        tok = o.get("TOKEN", "")
        ok_all &= rec("ARC-7", "%s: holds a scoped (non-root) Vault token" % svc,
                      bool(tok) and tok != ROOT, "token present=%s, is-root=%s" % (bool(tok), tok == ROOT and bool(ROOT)))
        ok_all &= rec("ARC-7", "%s: no static VAULT_TOKEN in container config" % svc,
                      not config_has_static_vault_token(svc), "config static token present=%s" % config_has_static_vault_token(svc))
        creds = [c for c in PLATFORM_CREDS if not (svc == "app-host" and c in APP_HOST_OWN)]
        paths = creds + [c.replace("secret/data/", "secret/metadata/", 1) for c in creds]
        cp = caps(svc, paths)["CAP"]
        for c in creds:
            m = c.replace("secret/data/", "secret/metadata/", 1)
            bad = [x for x, w in ((c, False), (c, True), (m, False), (m, True)) if granted(cp.get(x), write=w) or cp.get(x) in ("list",)]
            g = probe(svc, c, "")
            ok_all &= rec("ARC-7", "%s CANNOT read or write platform credential %s" % (svc, c.split("secret/data/", 1)[1]),
                          not bad and g.get("OWN") == "403",
                          "caps data=%s metadata=%s; GET -> %s (want no capability, 403)" % (cp.get(c), cp.get(m), g.get("OWN")))
        if comp:
            cpath = "%s/data/%s" % (COMPONENT_MOUNT, comp)
            cc = caps(svc, [cpath])["CAP"].get(cpath)
            ok_all &= rec("ARC-7", "%s CAN read+write component secrets (its own mount)" % svc,
                          granted(cc) and granted(cc, write=True), "%s caps=%s" % (cpath, cc))

    # slice-1g (DEBT-B88): transit keys are per service. ACTUAL sign attempts: kernel and network with identity's key.
    for svc in ("kernel", "network"):
        o = caps(svc, tries=["transit/sign/airawat-identity"])
        st = o["TRY"].get("transit/sign/airawat-identity")
        ok_all &= rec("ARC-7", "%s CANNOT sign with identity's issuer key (forge identity tokens)" % svc,
                      st == "403", "POST transit/sign/airawat-identity -> %s (want 403)" % st)
    for svc in TRANSIT_SERVICES:
        paths = []
        for key in TRANSIT_KEYS:
            paths += ["transit/sign/" + key, "transit/keys/" + key + "/rotate", "transit/keys/" + key + "/config"]
        o = caps(svc, paths)["CAP"]
        bad = []
        for key, owner in TRANSIT_KEYS.items():
            if svc != owner and granted(o.get("transit/sign/" + key), write=True):
                bad.append("sign " + key)
            for adm in ("rotate", "config"):     # nobody administers ANOTHER service's key
                if svc != owner and granted(o.get("transit/keys/%s/%s" % (key, adm)), write=True):
                    bad.append("%s %s" % (adm, key))
        own_ok = all(granted(o.get("transit/sign/" + k), write=True) for k, ow in TRANSIT_KEYS.items() if ow == svc)
        ok_all &= rec("ARC-7", "%s: transit limited to its own keys (cannot sign with, rotate or configure another service's key)" % svc,
                      not bad and own_ok, ("foreign/admin: %s" % bad) if bad else ("own keys signable=%s" % own_ok))

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
    _ev.seal(os.path.join(d, "%s-vaultscope.json" % ENV))
    print("✓ Vault least-privilege PASS" if ok_all else "✗ Vault least-privilege FAILED")
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()

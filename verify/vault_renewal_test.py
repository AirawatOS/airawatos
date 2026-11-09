#!/usr/bin/env python3
"""Every service keeps its Vault access across many token lifetimes, and a lost token is LOUD (slice-1h, DEBT-B96).

  1. SHORT LIFETIMES: every service AppRole is switched to a 60 s token period and every Vault-using service is
     restarted (fresh AppRole login → 60 s periodic token).
  2. KEEPS WORKING for PERIODS × 60 s (default 5 lifetimes): every 30 s, for every service, its OWN token (PID 1's
     VAULT_TOKEN) must still answer lookup-self with ttl > 0 and period 60 s; at the end every service must still read its
     own Vault path (conformance/vault_scope_test.py) and identity must still sign a login (Vault transit).
  3. FORCED FAILURE: one service's token is revoked; within 90 s the service's log must carry the renewer's loud
     "VAULT TOKEN INVALID" line AND Docker must report the container UNHEALTHY. The service is then restarted (re-login).
  4. Restore: the AppRoles go back to the install period (AOS_VAULT_TOKEN_PERIOD, default 1h) and the services restart.
Writes conformance/results/local-dev-vaultrenewal.json. Exit 1 on any failure.
"""
import json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402

P = "airawatos-localdev"
C = ["docker", "compose", "-p", P, "--project-directory", os.path.join(ROOT, "deploy/local-dev"), "-f",
     os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")]
ROLES = ["kernel", "network", "identity", "secrets", "model-gateway", "app-host", "automation", "event-relay", "scheduler",
         "decision", "workflow", "runtime-manager"]
POL = {"kernel": "svc-kernel", "network": "svc-network", "identity": "svc-identity", "secrets": "svc-secrets",
       "model-gateway": "svc-model-gateway", "app-host": "svc-app-host", "automation": "svc-scheduler",
       "event-relay": "svc-scheduler", "scheduler": "svc-scheduler", "decision": "svc-decision", "workflow": "svc-workflow",
       "runtime-manager": "svc-runtime-manager"}
PERIODS = int(os.environ.get("RENEWAL_PERIODS", "5"))
VICTIM = os.environ.get("RENEWAL_VICTIM", "decision")
cases, fails = [], []


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def check(name, ok, detail=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (" — " + detail if detail else ""), flush=True)
    cases.append({"case": name, "rules": ["ARC-7", "FND-16"], "result": "PASS" if ok else "FAIL", "detail": detail[:300]})
    if not ok:
        fails.append(name)


ROOT_TOKEN = sh("docker", "exec", "airawat-ld-vault", "sh", "-lc",
                'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"').stdout.strip()


def vroot(cmd):
    return sh("docker", "exec", "-e", "VAULT_TOKEN=" + ROOT_TOKEN, "-e", "VAULT_ADDR=http://127.0.0.1:8200", "airawat-ld-vault", "sh", "-lc", cmd)


def set_period(period):
    for r in ROLES:
        rc = vroot("vault write auth/approle/role/%s token_policies=%s token_period=%s token_ttl=0 token_max_ttl=0 "
                   "token_num_uses=0 secret_id_num_uses=0 secret_id_ttl=0" % (r, POL[r], period))
        if rc.returncode:
            raise SystemExit("✗ could not set the token period of %s: %s" % (r, rc.stderr[:200]))


LOOKUP = r'''
import json, urllib.request
t = [l.split(b"=",1)[1].decode() for l in (lambda rd: next((d for d in (rd(p) for p in sorted(__import__("glob").glob("/proc/[0-9]*/environ"), key=lambda x: int(x.split("/")[2]))) if b"VAULT_TOKEN=" in d), b""))(lambda p: (lambda f: f.read())(open(p, "rb")) if __import__("os").access(p, 4) else b"").split(b"\0") if l.startswith(b"VAULT_TOKEN=")]
try:
    r = urllib.request.Request("http://vault:8200/v1/auth/token/lookup-self", headers={"X-Vault-Token": t[0] if t else ""})
    d = json.loads(urllib.request.urlopen(r, timeout=6).read())["data"]; print("OK", d.get("ttl"), d.get("period"), d.get("accessor"))
except Exception as e:
    print("ERR", getattr(e, "code", str(e)[:60]))
'''


def lookup(svc):
    out = sh("docker", "exec", "airawat-ld-" + svc, "python3", "-c", LOOKUP).stdout.strip().split()
    return out


def health(svc):
    return sh("docker", "inspect", "-f", "{{.State.Health.Status}}", "airawat-ld-" + svc).stdout.strip()


def restarts(svc):
    return sh("docker", "inspect", "-f", "{{.RestartCount}}", "airawat-ld-" + svc).stdout.strip()


def renewer_alive(svc):
    return sh("docker", "exec", "airawat-ld-" + svc, "sh", "-c", "pgrep -f vault_renew.py >/dev/null && echo yes").stdout.strip() == "yes"


def recovered(svc, old_accessor, wait=240):
    """True once the service holds a NEW valid token (another accessor) and is healthy again."""
    deadline = time.time() + wait
    while time.time() < deadline:
        r = lookup(svc)
        if len(r) >= 4 and r[0] == "OK" and r[3] != old_accessor and health(svc) == "healthy":
            return True
        time.sleep(5)
    return False


def restart_and_wait(svcs):
    sh(*C, "restart", *svcs)
    deadline = time.time() + 240
    while time.time() < deadline:
        if all(health(s) == "healthy" for s in svcs):
            return True
        time.sleep(5)
    return False


print("▶ Vault token renewal test (B96): %d lifetimes of 60 s, then a forced renewal failure" % PERIODS, flush=True)
try:
    set_period("60s")
    check("every Vault-using service restarts healthy on 60 s periodic tokens", restart_and_wait(ROLES),
          "; ".join("%s=%s" % (s, health(s)) for s in ROLES))
    t0, worst = time.time(), {}
    while time.time() - t0 < PERIODS * 60 + 5:
        for s in ROLES:
            r = lookup(s)
            ok = len(r) >= 3 and r[0] == "OK" and int(r[1] or 0) > 0 and r[2] == "60"
            if not ok:
                worst.setdefault(s, " ".join(r))
        time.sleep(30)
    check("every service's OWN token stayed valid for %d lifetimes (renewed, period 60 s)" % PERIODS, not worst,
          ("lost: %s" % worst) if worst else "%d services × %d s" % (len(ROLES), int(time.time() - t0)))
    vs = sh(sys.executable, os.path.join(ROOT, "conformance/vault_scope_test.py"))
    check("after %d lifetimes every service still reads its own Vault paths (vault_scope_test)" % PERIODS,
          vs.returncode == 0, vs.stdout.strip().splitlines()[-1] if vs.stdout.strip() else vs.stderr[-200:])
    login = sh("docker", "exec", "airawat-ld-network", "python3", "-c",
               "import json,urllib.request;r=urllib.request.Request('http://identity:8093/healthz');"
               "print(json.loads(urllib.request.urlopen(r,timeout=5).read()).get('key_backend'))")
    check("identity still signs through Vault transit after %d lifetimes" % PERIODS, "vault" in login.stdout.lower(),
          "key_backend=%s" % login.stdout.strip())
    # forced failure
    r = lookup(VICTIM)
    acc = r[3] if len(r) >= 4 else ""
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rv = vroot("vault token revoke -accessor %s" % acc) if acc else None
    loud, unhealthy, deadline = False, False, time.time() + 120
    while time.time() < deadline and not (loud and unhealthy):
        time.sleep(5)
        logs = sh("docker", "logs", "--since", since, "airawat-ld-" + VICTIM)
        loud = loud or "VAULT TOKEN INVALID" in (logs.stdout + logs.stderr)
        unhealthy = unhealthy or health(VICTIM) == "unhealthy"
    check("a revoked token is reported LOUDLY in %s's log (renewer: VAULT TOKEN INVALID)" % VICTIM, loud and bool(acc) and rv is not None and rv.returncode == 0,
          "accessor %s, revoke rc %s" % (bool(acc), rv and rv.returncode))
    check("a revoked token makes %s UNHEALTHY (docker health)" % VICTIM, unhealthy, "health=%s" % health(VICTIM))
    # slice-1i (DEBT-B128): the lost token is RECOVERED — controlled restart → fresh AppRole login → healthy, valid token
    check("after the revocation %s RECOVERS by itself (controlled restart, fresh login, healthy)" % VICTIM, recovered(VICTIM, acc),
          "health=%s restarts=%s" % (health(VICTIM), restarts(VICTIM)))
    # neighbour 1: the renewer is killed → not silent: unhealthy, then a controlled restart brings it back
    acc2 = (lookup(VICTIM) + ["", "", "", ""])[3]
    sh("docker", "exec", "airawat-ld-" + VICTIM, "sh", "-c", "pkill -f vault_renew.py")
    check("a KILLED renewer is detected and %s recovers (restart, renewer running again)" % VICTIM,
          recovered(VICTIM, acc2) and renewer_alive(VICTIM), "health=%s renewer=%s" % (health(VICTIM), renewer_alive(VICTIM)))
    # neighbour 2: a network blip longer than one token period (the token expires while Vault is unreachable)
    acc3 = (lookup(VICTIM) + ["", "", "", ""])[3]
    net = "airawatos-localdev_aos-data-secrets" if sh("docker", "network", "inspect", "airawatos-localdev_aos-data-secrets").returncode == 0 else "aos-data-secrets"
    sh("docker", "network", "disconnect", net, "airawat-ld-" + VICTIM)
    time.sleep(75)
    sh("docker", "network", "connect", net, "airawat-ld-" + VICTIM)
    check("after a network blip longer than one period %s recovers (fresh token, healthy)" % VICTIM, recovered(VICTIM, acc3),
          "health=%s" % health(VICTIM))
    # the final review's case: Vault itself DOWN for longer than one token period — every service must recover
    accs = {s_: (lookup(s_) + ["", "", "", ""])[3] for s_ in ROLES}
    sh(*C, "stop", "vault"); time.sleep(75); sh(*C, "start", "vault")
    deadline, back = time.time() + 240, set()
    while time.time() < deadline and len(back) < len(ROLES):
        for s_ in ROLES:
            r_ = lookup(s_)
            if s_ not in back and len(r_) >= 4 and r_[0] == "OK" and r_[3] != accs[s_] and health(s_) == "healthy":
                back.add(s_)
        time.sleep(10)
    check("after Vault was DOWN longer than one token period, every service recovers (%d/%d fresh + healthy)" % (len(back), len(ROLES)),
          len(back) == len(ROLES), "not recovered: %s" % sorted(set(ROLES) - back))
finally:
    set_period(os.environ.get("AOS_VAULT_TOKEN_PERIOD", "1h"))
    ok = restart_and_wait(ROLES)
    print("  · restored the install token period and restarted every service: %s" % ("healthy" if ok else "NOT all healthy"), flush=True)
    if not ok:
        fails.append("restore")
evidence.write("vaultrenewal", cases)
print(("✗" if fails else "✓") + " Vault renewal test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

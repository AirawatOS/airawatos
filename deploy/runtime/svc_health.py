#!/usr/bin/env python3
"""Container healthcheck (slice-1h, DEBT-B96): UNHEALTHY when the service's Vault access is gone or failing.

  svc_health.py [http-url]
  1. if a URL is given, it must answer 2xx;
  2. if the service holds a Vault token (PID 1's VAULT_TOKEN), `auth/token/lookup-self` must succeed with ttl > 0;
  3. the renewer's status file (/tmp/airawat-vault.status), if present, must not report a failure.
Prints the reason; exit 0 healthy, 1 unhealthy.
"""
import json, os, sys, urllib.request


def pid1_env(name):
    try:
        for kv in (lambda rd: next((d for d in (rd(p) for p in sorted(__import__("glob").glob("/proc/[0-9]*/environ"), key=lambda x: int(x.split("/")[2]))) if b"VAULT_TOKEN=" in d), b""))(lambda p: (lambda f: f.read())(open(p, "rb")) if __import__("os").access(p, 4) else b"").split(b"\0"):
            if kv.startswith(name.encode() + b"="):
                return kv.split(b"=", 1)[1].decode()
    except Exception:
        pass
    return os.environ.get(name, "")


def _restart():
    """Controlled restart: terminate the service process (the lowest pid holding VAULT_TOKEN); with `init: true` the init
    then exits and the container's restart policy starts it again — the entrypoint logs in to Vault afresh."""
    import glob, signal
    for p in sorted(glob.glob("/proc/[0-9]*/environ"), key=lambda x: int(x.split("/")[2])):
        pid = int(p.split("/")[2])
        try:
            if pid != 1 and b"VAULT_TOKEN=" in open(p, "rb").read():
                os.kill(pid, signal.SIGTERM); return
        except Exception:
            continue


def main():
    if len(sys.argv) > 1:
        try:
            urllib.request.urlopen(sys.argv[1], timeout=4)
        except Exception as e:
            print("unhealthy: %s -> %s" % (sys.argv[1], str(e)[:80])); return 1
    tok, addr = pid1_env("VAULT_TOKEN"), (pid1_env("VAULT_ADDR") or "").rstrip("/")
    # slice-1i (DEBT-B125): a service that DECLARES Vault (it has an AppRole role id) but holds no token is UNHEALTHY —
    # it was "healthy" before, because the token check only ran when a token existed.
    declared = bool(os.environ.get("VAULT_ROLE_ID") or pid1_env("VAULT_ROLE_ID"))
    if declared and not tok:
        print("unhealthy: this service declares Vault (AppRole) but holds NO Vault token"); return 1
    # slice-1i (DEBT-B128, FINAL F4-7): the renewer must be alive — a dead renewer means the token silently lapses later.
    # Controlled restart: the service is terminated so the restart policy brings it back with a fresh AppRole login.
    if declared and tok:
        import glob
        alive = any(b"vault_renew.py" in (open(c, "rb").read() if os.access(c, 4) else b"") for c in glob.glob("/proc/[0-9]*/cmdline"))
        if not alive:
            print("unhealthy: the Vault token renewer is not running — restarting the service for a fresh login")
            _restart(); return 1
    if tok and addr:
        try:
            req = urllib.request.Request(addr + "/v1/auth/token/lookup-self", headers={"X-Vault-Token": tok})
            ttl = int(json.loads(urllib.request.urlopen(req, timeout=4).read())["data"].get("ttl") or 0)
            if ttl <= 0:
                print("unhealthy: Vault token ttl %s" % ttl); return 1
        except Exception as e:
            print("unhealthy: Vault token lookup failed: %s" % (getattr(e, "code", None) or str(e)[:80])); return 1
    st = os.environ.get("AIRAWAT_VAULT_STATUS", "/tmp/airawat-vault.status")
    if os.path.exists(st):
        try:
            d = json.load(open(st))
        except Exception:
            d = {"ok": False, "error": "unreadable status"}
        if not d.get("ok"):
            print("unhealthy: Vault renewal failing: %s" % d.get("error")); return 1
    print("healthy"); return 0


if __name__ == "__main__":
    sys.exit(main())

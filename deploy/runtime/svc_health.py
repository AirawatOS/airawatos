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
        for kv in open("/proc/1/environ", "rb").read().split(b"\0"):
            if kv.startswith(name.encode() + b"="):
                return kv.split(b"=", 1)[1].decode()
    except Exception:
        pass
    return os.environ.get(name, "")


def main():
    if len(sys.argv) > 1:
        try:
            urllib.request.urlopen(sys.argv[1], timeout=4)
        except Exception as e:
            print("unhealthy: %s -> %s" % (sys.argv[1], str(e)[:80])); return 1
    tok, addr = pid1_env("VAULT_TOKEN"), (pid1_env("VAULT_ADDR") or "").rstrip("/")
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

#!/usr/bin/env python3
"""Keep the service's Vault token alive (slice-1h, DEBT-B96 / re-review R4-1).

Started in the background by airawat-entrypoint.sh after the AppRole login. The token is PERIODIC (AppRole
token_period): renewing it before each period ends keeps it valid indefinitely, with the SAME token id, so the
service process (which read VAULT_TOKEN once) never needs a new one. Every renewal failure is LOUD (stderr → container
logs) and recorded in /tmp/airawat-vault.status, which svc_health.py turns into an UNHEALTHY container.
"""
import json, os, sys, time, urllib.error, urllib.request

ADDR = os.environ.get("VAULT_ADDR", "").rstrip("/")
TOK = os.environ.get("VAULT_TOKEN", "")
STATUS = os.environ.get("AIRAWAT_VAULT_STATUS", "/tmp/airawat-vault.status")
SVC = os.environ.get("SERVICE_PRINCIPAL") or os.environ.get("HOSTNAME", "service")


def call(path, method="GET"):
    req = urllib.request.Request(ADDR + "/v1/" + path, method=method, data=(b"{}" if method == "POST" else None),
                                 headers={"X-Vault-Token": TOK, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read() or b"{}")


def status(ok, **kw):
    try:
        with open(STATUS + ".tmp", "w") as f:
            json.dump({"ok": ok, "ts": int(time.time()), **kw}, f)
        os.replace(STATUS + ".tmp", STATUS)
    except Exception:
        pass


def log(msg):
    print("[vault-renew %s] %s" % (SVC, msg), file=sys.stderr, flush=True)


def main():
    if not (ADDR and TOK):
        return
    period, failures = 0, 0
    while True:
        try:
            d = call("auth/token/lookup-self")["data"]
            ttl, period = int(d.get("ttl") or 0), int(d.get("period") or 0)
            if ttl <= 0 and not period:
                raise RuntimeError("token has no ttl and no period")
            wait = max(2, min(ttl or period, period or ttl) // 3)
            status(True, ttl=ttl, period=period, failures=failures)
            time.sleep(wait)
            r = call("auth/token/renew-self", "POST")["auth"]
            failures = 0
            status(True, ttl=int(r.get("lease_duration") or 0), period=period, renewed=int(time.time()))
        except Exception as e:
            failures += 1
            code = getattr(e, "code", None)
            dead = code in (401, 403)
            log("✗ %s (attempt %d): %s — %s" % ("VAULT TOKEN INVALID (expired or revoked)" if dead else "RENEWAL FAILED",
                failures, ("HTTP %s" % code) if code else str(e)[:160],
                "this service has LOST Vault access and is UNHEALTHY" if dead else "retrying; the service is UNHEALTHY until it succeeds"))
            status(False, error=("http %s" % code) if code else str(e)[:160], failures=failures, token_invalid=dead)
            time.sleep(5)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Vault ROOT token ON DEMAND for the local-dev stack (slice-1k, DEBT-B160 / B161).

The local-dev Vault no longer regenerates a root token at start: after a restore it runs with NO root token at all. When
tooling needs one, it is generated on demand (Vault generate-root, which needs the unseal key) and revoked as soon as the
tooling has finished. Root tokens are never printed.

  vault_root.py generate      ensure a VALID root token in /vault/data/init.json (reuse a valid one, else generate-root)
  vault_root.py revoke-all    enumerate EVERY token by accessor, revoke every token carrying the `root` policy (the
                              current one last), blank init.json's root_token; prints how many were revoked
  vault_root.py verify-none   prove NO root token remains: a short-lived probe root enumerates every accessor and must find
                              no other root token; the probe is then revoked and init.json must be blank. Exit 1 otherwise.
  vault_root.py status        'valid' / 'absent' / 'invalid' for the token in init.json
"""
import json, subprocess, sys

VC = "airawat-ld-vault"


def dex(cmd, token="", stdin=None):
    env = ["-e", "VAULT_ADDR=http://127.0.0.1:8200"] + (["-e", "VAULT_TOKEN=" + token] if token else [])
    return subprocess.run(["docker", "exec", "-i"] + env + [VC, "sh", "-c", cmd], input=stdin, capture_output=True, text=True)


def init_root():
    out = dex("tr -d '\\n ' < /vault/data/init.json 2>/dev/null | sed -n 's/.*\"root_token\":\"\\([^\"]*\\)\".*/\\1/p'").stdout.strip()
    return out


def valid(tok):
    if not tok:
        return False
    r = dex("vault token lookup -format=json", token=tok)
    try:
        return r.returncode == 0 and "root" in (json.loads(r.stdout)["data"].get("policies") or [])
    except Exception:
        return False


def write_root(tok):
    # replace the root_token value in init.json in place (keeps owner vault:vault and mode), value passed on stdin
    r = dex('read -r T; sed "s/\\"root_token\\": *\\"[^\\"]*\\"/\\"root_token\\": \\"$T\\"/" /vault/data/init.json > /tmp/i.$$ '
            '&& cat /tmp/i.$$ > /vault/data/init.json && rm -f /tmp/i.$$', stdin=tok + "\n")
    if r.returncode:
        raise SystemExit("✗ could not update init.json: %s" % r.stderr.strip()[:200])


def generate_root():
    script = r'''
UNSEAL=$(tr -d '\n ' < /vault/data/init.json | sed -n 's/.*"unseal_keys_b64":\["\([^"]*\)".*/\1/p')
vault operator generate-root -cancel >/dev/null 2>&1 || true
G=$(vault operator generate-root -init -format=json | tr -d '\n ')
N=$(printf %s "$G" | sed -n 's/.*"nonce":"\([^"]*\)".*/\1/p'); O=$(printf %s "$G" | sed -n 's/.*"otp":"\([^"]*\)".*/\1/p')
E=$(vault operator generate-root -nonce="$N" -format=json "$UNSEAL" | tr -d '\n ' | sed -n 's/.*"encoded_token":"\([^"]*\)".*/\1/p')
vault operator generate-root -decode="$E" -otp="$O"
'''
    r = dex(script)
    tok = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    if r.returncode or not valid(tok):
        raise SystemExit("✗ generate-root failed (needs the unseal key in init.json and unauthenticated generate-root in vault.hcl): %s"
                         % (r.stderr.strip().splitlines() or ["?"])[-1][:200])
    return tok


def ensure():
    t = init_root()
    if valid(t):
        return t, False
    t = generate_root()
    write_root(t)
    return t, True


def root_accessors(tok):
    """every accessor whose token carries the root policy, and the caller's own accessor"""
    me = json.loads(dex("vault token lookup -format=json", token=tok).stdout)["data"]["accessor"]
    lst = json.loads(dex("vault list -format=json auth/token/accessors", token=tok).stdout or "[]")
    roots = []
    for a in lst:
        r = dex("vault write -format=json auth/token/lookup-accessor accessor=%s" % a, token=tok)
        try:
            if "root" in (json.loads(r.stdout)["data"].get("policies") or []):
                roots.append(a)
        except Exception:
            pass
    return roots, me


def revoke_all():
    tok, _ = ensure()
    roots, me = root_accessors(tok)
    n = 0
    for a in roots:
        if a != me and dex("vault write auth/token/revoke-accessor accessor=%s" % a, token=tok).returncode == 0:
            n += 1
    dex("vault token revoke -self", token=tok)
    write_root("")
    return n + 1


def verify_none():
    probe = generate_root()                           # a short-lived probe — revoked below whatever happens
    try:
        roots, me = root_accessors(probe)
        others = [a for a in roots if a != me]
    finally:
        dex("vault token revoke -self", token=probe)
    blank = init_root() == ""
    gone = not valid(probe)
    return others, blank, gone


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["status"])[0]
    if cmd == "generate":
        _, new = ensure()
        print("  ✓ a valid root token is in init.json (%s)" % ("GENERATED on demand" if new else "already present"))
    elif cmd == "revoke-all":
        print("  ✓ revoked %d root token(s) (every one found by accessor enumeration, this one last); init.json carries none" % revoke_all())
    elif cmd == "verify-none":
        others, blank, gone = verify_none()
        ok = not others and blank and gone
        print(("  ✓" if ok else "  ✗") + " root tokens remaining: %d; init.json root_token blank: %s; probe revoked: %s" % (len(others), blank, gone))
        sys.exit(0 if ok else 1)
    elif cmd == "status":
        t = init_root()
        print("absent" if not t else ("valid" if valid(t) else "invalid"))
    else:
        raise SystemExit(__doc__)

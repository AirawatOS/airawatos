"""Phase 0 — platform signing + audit keys in Vault (generate-or-verify). Idempotent. Runnable INSIDE a
container with Vault access (the network image), via `... python3 - < _keys.py`. Env: INSTANCE, VAULT_*."""
import os, sys, json, secrets, urllib.request, urllib.error
VA=(os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT=os.environ.get("VAULT_TOKEN",""); INST=os.environ["INSTANCE"]
def v(method, path, body=None, ok_fail=False):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(f"{VA}/v1/{path}", data=data, method=method,
                             headers={"X-Vault-Token":VT, **({"Content-Type":"application/json"} if data else {})})
    try: return json.loads(urllib.request.urlopen(r, timeout=8).read() or b"{}")
    except urllib.error.HTTPError as e:
        if ok_fail: return None
        raise
def fail(msg, fix):
    print(f"  ✗ {msg}\n     FIX: {fix}", file=sys.stderr); sys.exit(1)
if not VT:
    fail("VAULT_TOKEN is not set — the installer cannot reach Vault.",
         "Set VAULT_TOKEN in the environment (compose .env in local-dev); never commit it.")
try:
    v("GET", "sys/health", ok_fail=False)
except Exception as e:
    fail(f"Vault not reachable at {VA} ({str(e)[:80]}).",
         "Start Vault and confirm VAULT_ADDR/VAULT_TOKEN; in production Vault must be unsealed and NOT in dev-root mode.")
# slice-1i (B127): enable transit only when ABSENT — no write is ever expected to fail (the installer's write guard fails a
# helper on ANY failed write; "already mounted" used to be a swallowed 400)
if "transit/" not in (v("GET", "sys/mounts") or {}).get("data", v("GET", "sys/mounts") or {}):
    v("POST", "sys/mounts/transit", {"type":"transit"})
for key, label in (("airawat-identity","identity issuer"), ("airawat-authority","Network authority")):
    v("POST", f"transit/keys/{key}", {"type":"ed25519"}, ok_fail=True)   # create if missing (idempotent)
    r=v("GET", f"transit/keys/{key}", ok_fail=True)
    keys=((r or {}).get("data") or {}).get("keys") or {}
    pub=next((kv.get("public_key") for kv in keys.values() if isinstance(kv,dict) and kv.get("public_key")), None)
    if not pub:
        fail(f"{label} key transit/keys/{key} missing or has no public key.",
             f"Ensure the Vault transit engine is enabled and the installer can create keys (token policy), or pre-provision transit/keys/{key} (ed25519).")
    print(f"  ✓ {label} key: transit/keys/{key} (ed25519, public key present)")
AUD=f"secret/data/{INST}-network/trust-plane/audit_hmac"   # field `value`, same as installer Phase 6 + the network reader
r=v("GET", AUD, ok_fail=True)
hm=(((r or {}).get("data") or {}).get("data") or {}).get("value") if r else None
if not hm:
    v("POST", AUD, {"data":{"value":secrets.token_hex(32)}})
    print(f"  ✓ trust-plane audit HMAC: generated at {AUD}")
else:
    print(f"  ✓ trust-plane audit HMAC: present at {AUD}")
print("  Phase 0 OK — trust roots present + valid.")

"""Service-identity tokens — the ONE implementation (ADR-0124 dedicated service principals).

Consolidates what was three copies: platform-spec `svc_token.py` (reference-plane daemons + app-host), kernel
`api/svc_identity.py`, and app-host's `hostcore.fs_headers / mgw_headers`. Those modules are now thin shims over
this one until the post-merge slice moves their last callers onto `aos_svc.client_for` (DEBT-B179).

A platform service authenticates as ITS OWN provisioned principal: it reads that principal's password from Vault
(installer-seeded, never baked), logs in WITH the password, and mints a short-lived token ADDRESSED to one audience.
Tokens are cached per (principal, tenant, audience) and re-minted a minute before expiry.

FAIL-CLOSED: no Vault credential, or the login refused → None. Never a passwordless token, never a fallback.

Env: IDENTITY_URL, VAULT_ADDR, VAULT_TOKEN (re-read on every mint — the renewer may replace it),
     SERVICE_PRINCIPAL / SERVICE_TENANT (this process's default identity), SERVICE_CRED_PATH (single-principal override).
"""
import json
import os
import time
import urllib.request

_CACHE: dict = {}   # (principal, tenant, audience) -> {"token": str, "exp": float}


def default_principal():
    return os.environ.get("SERVICE_PRINCIPAL", "scheduler")


def default_tenant():
    return os.environ.get("SERVICE_TENANT", "airawat")


def _identity():
    return (os.environ.get("IDENTITY_URL") or "http://identity:8093").rstrip("/")


def cred_path(principal, tenant):
    """Vault KV-v2 read path for a principal's password. SERVICE_CRED_PATH overrides ONLY the env-default
    single-principal case (the daemons); multi-principal callers (app-host) resolve per (tenant, principal)."""
    if os.environ.get("SERVICE_CRED_PATH") and principal == default_principal() and tenant == default_tenant():
        return os.environ["SERVICE_CRED_PATH"]
    return "secret/data/%s/%s/password" % (tenant, principal)


def _vault_password(principal, tenant):
    addr = (os.environ.get("VAULT_ADDR") or "").rstrip("/")
    vtok = os.environ.get("VAULT_TOKEN") or ""
    if not (addr and vtok):
        return None
    req = urllib.request.Request("%s/v1/%s" % (addr, cred_path(principal, tenant)), headers={"X-Vault-Token": vtok})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=8).read() or b"{}")
        return (((d.get("data") or {}).get("data") or {}).get("password")) or None
    except Exception:
        return None


def token(principal=None, tenant=None, audience=None):
    """A short-lived token for `principal`@`tenant` ADDRESSED to `audience`; cached, re-minted early. None when it
    cannot be minted (fail-closed)."""
    principal = principal or default_principal()
    tenant = tenant or default_tenant()
    audience = audience or os.environ.get("SERVICE_TOKEN_AUDIENCE") or os.environ.get("IDENTITY_AUDIENCE") or "airawatos"
    ck = (principal, tenant, audience)
    c = _CACHE.get(ck)
    if c and c["exp"] > time.time():
        return c["token"]
    pw = _vault_password(principal, tenant)
    if not pw:
        print("[aos-svc] no Vault credential for '%s@%s' at %s — cannot mint %s (fail-closed, ADR-0124)"
              % (principal, tenant, cred_path(principal, tenant), audience), flush=True)
        return None
    body = {"username": principal, "tenant": tenant, "password": pw, "aud": audience}
    req = urllib.request.Request(_identity() + "/login", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=8).read())
    except Exception as e:
        print("[aos-svc] login refused for '%s@%s' aud=%s: %s" % (principal, tenant, audience, str(e)[:120]), flush=True)
        return None
    tok = d.get("access_token")
    if not tok:
        return None
    _CACHE[ck] = {"token": tok, "exp": time.time() + min(3000, int(d.get("expires_in", 3600)) - 60)}
    return tok


def bearer(base=None, principal=None, tenant=None, audience=None):
    """`base` headers + the bearer (omitted when none can be minted). For the shims only — new code uses a client."""
    h = dict(base or {})
    t = token(principal, tenant, audience)
    if t:
        h["Authorization"] = "Bearer " + t
    return h

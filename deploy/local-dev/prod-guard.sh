#!/bin/sh
# AirawatOS production guard (ADR local-dev §7). Runs as each service's ENTRYPOINT (compose-level), so it
# needs no service-code changes. It inspects the EFFECTIVE settings — env + the service's own command args —
# and, when AIRAWAT_ENV=production AND any development convenience is active, REFUSES to start and logs which
# one. Otherwise it execs the service command unchanged. A dev-profile stack sets AIRAWAT_ENV=development, so
# the guard is a transparent pass-through there.
set -e

# L1-1b step4 — capture whether a STATIC VAULT_TOKEN was injected via the environment, BEFORE the AppRole login
# below may set one. In production a service must obtain its token via AppRole; a pre-injected static token is a
# root/shared token and the prod guard refuses it.
_VAULT_PRESET="${VAULT_TOKEN:-}"

# ── FIX-PLAN L1-1b — per-service Vault AppRole login (closes DEBT-B58) ──────────────────────────────
# Each service authenticates to Vault with ITS OWN AppRole (role-id + secret-id from its env_file) and gets a
# short-lived, policy-scoped token. The shared root token is gone from every service. If VAULT_TOKEN is ALREADY
# set (the installer's one-off bootstrap runs pass root via `-e VAULT_TOKEN=…`), we use it and skip the login.
if [ -z "${VAULT_TOKEN:-}" ] && [ -n "${VAULT_ROLE_ID:-}" ] && [ -n "${VAULT_SECRET_ID:-}" ] && [ -n "${VAULT_ADDR:-}" ]; then
  _VT=""
  i=0
  while [ "$i" -lt 10 ]; do
    _VT="$(VAULT_ADDR="$VAULT_ADDR" VAULT_ROLE_ID="$VAULT_ROLE_ID" VAULT_SECRET_ID="$VAULT_SECRET_ID" python3 -c '
import os, json, urllib.request, sys
try:
    body = json.dumps({"role_id": os.environ["VAULT_ROLE_ID"], "secret_id": os.environ["VAULT_SECRET_ID"]}).encode()
    req = urllib.request.Request(os.environ["VAULT_ADDR"].rstrip("/") + "/v1/auth/approle/login",
                                 data=body, headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=8).read())
    sys.stdout.write(d["auth"]["client_token"])
except Exception:
    sys.exit(1)
' 2>/dev/null)" && [ -n "$_VT" ] && break
    i=$((i + 1)); sleep 2
  done
  if [ -z "$_VT" ]; then
    echo "[prod-guard] FATAL: Vault AppRole login failed for this service (role_id/secret_id/VAULT_ADDR) — refusing to start (fail-closed)." >&2
    exit 96
  fi
  export VAULT_TOKEN="$_VT"
  unset VAULT_SECRET_ID    # don't leave the secret-id in the service process environment
  echo "[prod-guard] Vault: logged in via AppRole (scoped token; not printed)." >&2
fi

# slice-1g (DEBT-B83): the production check is the SAME parser the gates use — platform-spec/reference/gateflags.py
# (mounted at /local-dev/gateflags.py; baked at /app/reference/gateflags.py in reference images). Production refuses
# every *_SHADOW flag that is set at all, whatever its value. If production is requested and the parser cannot be
# found or run, the guard refuses (fail closed).
_GF=/local-dev/gateflags.py
[ -f "$_GF" ] || _GF=/app/reference/gateflags.py
_ENV="$(printf '%s' "${AIRAWAT_ENV:-}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
if [ "$_ENV" = "production" ] || [ "$_ENV" = "prod" ]; then
  if [ ! -f "$_GF" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "[prod-guard] REFUSING TO START — AIRAWAT_ENV=production but the gate-flag parser (gateflags.py) is unavailable (fail closed)." >&2
    exit 97
  fi
  _ST=""
  [ -n "$_VAULT_PRESET" ] && _ST="--static-vault-token"
  python3 "$_GF" guard $_ST -- "$@" || exit 97
fi
exec "$@"

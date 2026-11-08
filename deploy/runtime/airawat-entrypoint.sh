#!/bin/sh
# AirawatOS entrypoint — BAKED INTO EVERY SHIPPED IMAGE (slice-1h, DEBT-B97/B96). Replaces the local-dev-only
# deploy/local-dev/prod-guard.sh mount: the guard now runs wherever the image runs, not only under the dev compose.
#   1. PRODUCTION is decided by THE one parser (gateflags.py is-production): unset / misspelt AIRAWAT_ENV ⇒ production;
#      development must be declared (AIRAWAT_ENV=development|dev). If the parser cannot run ⇒ refuse (fail closed).
#   2. Per-service Vault AppRole login (role-id + secret-id from the service's env_file) → a PERIODIC token.
#   3. Production: refuse to start with any shadow flag set at all, any development convenience, a static
#      (root/shared) VAULT_TOKEN, or --no-verify-cert (gateflags.py guard).
#   4. A background renewer (vault_renew.py) renews the token before every period ends; failures are LOUD (logs) and
#      make the container UNHEALTHY (svc_health.py) — never a silent loss of Vault access (re-review R4-1).
#   5. exec the service command unchanged.
set -e
RT="${AIRAWAT_RUNTIME_DIR:-/opt/airawat}"
_VAULT_PRESET="${VAULT_TOKEN:-}"

if [ ! -f "$RT/gateflags.py" ] || ! command -v python3 >/dev/null 2>&1; then
  echo "[airawat-entrypoint] REFUSING TO START — the gate-flag parser ($RT/gateflags.py) or python3 is missing (fail closed)." >&2
  exit 97
fi
_PROD=1
python3 "$RT/gateflags.py" is-production || { _rc=$?; [ "$_rc" = 1 ] && _PROD=0 || { echo "[airawat-entrypoint] REFUSING TO START — the gate-flag parser failed (exit $_rc)" >&2; exit 97; }; }

# ── per-service Vault AppRole login (closes DEBT-B58). A preset VAULT_TOKEN (installer one-offs pass root) skips it.
_LOGGED_IN=0
if [ -z "${VAULT_TOKEN:-}" ] && [ -n "${VAULT_ROLE_ID:-}" ] && [ -n "${VAULT_SECRET_ID:-}" ] && [ -n "${VAULT_ADDR:-}" ]; then
  _VT=""
  i=0
  while [ "$i" -lt 10 ]; do
    _VT="$(python3 -c '
import os, json, urllib.request, sys
try:
    body = json.dumps({"role_id": os.environ["VAULT_ROLE_ID"], "secret_id": os.environ["VAULT_SECRET_ID"]}).encode()
    req = urllib.request.Request(os.environ["VAULT_ADDR"].rstrip("/") + "/v1/auth/approle/login",
                                 data=body, headers={"Content-Type": "application/json"})
    sys.stdout.write(json.loads(urllib.request.urlopen(req, timeout=8).read())["auth"]["client_token"])
except Exception:
    sys.exit(1)
' 2>/dev/null)" && [ -n "$_VT" ] && break
    i=$((i + 1)); sleep 2
  done
  if [ -z "$_VT" ]; then
    echo "[airawat-entrypoint] FATAL: Vault AppRole login failed (role_id/secret_id/VAULT_ADDR) — refusing to start (fail-closed)." >&2
    exit 96
  fi
  export VAULT_TOKEN="$_VT"
  unset VAULT_SECRET_ID
  _LOGGED_IN=1
  echo "[airawat-entrypoint] Vault: logged in via AppRole (scoped, periodic token; not printed)." >&2
fi

if [ "$_PROD" = 1 ]; then
  _ST=""
  [ -n "$_VAULT_PRESET" ] && _ST="--static-vault-token"
  python3 "$RT/gateflags.py" guard $_ST -- "$@" || exit 97
fi

if [ "$_LOGGED_IN" = 1 ]; then
  python3 "$RT/vault_renew.py" &       # loud renewer; status for the healthcheck in /tmp/airawat-vault.status
fi
exec "$@"

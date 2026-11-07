#!/bin/sh
# AirawatOS production guard (ADR local-dev §7). Runs as each service's ENTRYPOINT (compose-level), so it
# needs no service-code changes. It inspects the EFFECTIVE settings — env + the service's own command args —
# and, when AIRAWAT_ENV=production AND any development convenience is active, REFUSES to start and logs which
# one. Otherwise it execs the service command unchanged. A dev-profile stack sets AIRAWAT_ENV=development, so
# the guard is a transparent pass-through there.
set -e

_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;; *) return 1 ;;
  esac
}

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

_ENV="$(printf '%s' "${AIRAWAT_ENV:-}" | tr '[:upper:]' '[:lower:]')"
if [ "$_ENV" = "production" ]; then
  VIOL=""
  _truthy "${AIRAWAT_ALLOW_PASSWORDLESS:-}" && VIOL="$VIOL passwordless-login(AIRAWAT_ALLOW_PASSWORDLESS)"
  _truthy "${IDENTITY_SEED_DEMO:-}"         && VIOL="$VIOL demo-seed(IDENTITY_SEED_DEMO)"
  _truthy "${AIRAWAT_EPHEMERAL_OK:-}"       && VIOL="$VIOL ephemeral-ok(AIRAWAT_EPHEMERAL_OK)"
  _truthy "${IDENTITY_AUD_ISS_SHADOW:-}"    && VIOL="$VIOL iss-aud-shadow(IDENTITY_AUD_ISS_SHADOW)"
  _truthy "${AIRAWAT_NO_VERIFY_CERT:-}"     && VIOL="$VIOL no-verify-cert(AIRAWAT_NO_VERIFY_CERT)"
  [ "$(printf '%s' "${SCHEMA_VALIDATE:-}" | tr '[:upper:]' '[:lower:]')" = "shadow" ] \
      && VIOL="$VIOL schema-shadow(SCHEMA_VALIDATE=shadow)"
  # L1-1b step4 — a service must obtain its Vault token via AppRole; a STATIC token injected via env is a
  # root/shared token (DEBT-B58). Refuse it in production.
  [ -n "$_VAULT_PRESET" ] && VIOL="$VIOL static-vault-token(root/shared — use per-service AppRole)"
  # L1-1b step4 — the in-process component runtime inherits the host env + is unconfined (DEBT-B51). Refuse it
  # in production (interim: the operator must run a confined container runtime, not the in-process subprocess).
  _truthy "${AIRAWAT_INPROCESS_COMPONENTS:-}" && VIOL="$VIOL in-process-component-placement(DEBT-B51)"
  # L1-1c step3 — an inbound GATE in SHADOW is an OPEN write/spend/execute door. Every gate ENFORCES by default;
  # a dev opts one open ONLY via an explicit <SVC>_SHADOW flag. Production refuses ANY such flag (fail-loud):
  for _sv in $(env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*_SHADOW\)=.*/\1/p'); do
    eval "_sval=\${$_sv:-}"
    _truthy "$_sval" && VIOL="$VIOL gate-shadow($_sv)"
  done
  # effective command args — catches --no-verify-cert passed on the service command line
  for a in "$@"; do
    [ "$a" = "--no-verify-cert" ] && VIOL="$VIOL no-verify-cert(--no-verify-cert arg)"
  done
  if [ -n "$VIOL" ]; then
    echo "[prod-guard] REFUSING TO START — AIRAWAT_ENV=production with development conveniences active:$VIOL" >&2
    echo "[prod-guard] remove the flag(s)/arg(s) above for production, or set AIRAWAT_ENV=development for a dev stack." >&2
    exit 97
  fi
  echo "[prod-guard] AIRAWAT_ENV=production — no dev conveniences detected; proceeding." >&2
fi
exec "$@"

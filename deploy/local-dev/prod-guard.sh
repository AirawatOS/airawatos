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

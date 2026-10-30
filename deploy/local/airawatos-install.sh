#!/usr/bin/env bash
# AirawatOS — operator-first install (ADR-0115). Prompts the operator for an instance name + admin password,
# brings up a DE-SEEDED stack (empty IdP — no baked accounts), and provisions the four realms + their `admin`
# accounts via ensure_install.py:
#     <instance>-operator  admin→platform.admin  + scheduler daemon
#     <instance>-network   admin→network.admin
#     <instance>           admin→platform.tenant-admin
#     <instance>-sandbox   admin→platform.tenant-admin (development)
# Each admin uses the one password you set and is forced to change it on first login. Console + the base app
# suite auto-install on every tenant.
#
# Run from deploy/local. Interactive by default; set INSTANCE and OPERATOR_PASSWORD in the env to run headless
# (the future web setup wizard calls it this way). The password is read with no echo, passed to the provisioner
# via the process env only — never written to a file or printed.
#
#   cd deploy/local && ./airawatos-install.sh
set -euo pipefail
cd "$(dirname "$0")"                                  # deploy/local

command -v docker >/dev/null 2>&1 || { echo "✗ Docker is required."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "✗ docker compose v2 is required."; exit 1; }

# ── 1 · gather instance + operator password (env or prompt) ──────────────────────────────────────────
INSTANCE="${INSTANCE:-}"
if [ -z "$INSTANCE" ]; then read -rp "Instance name (e.g. labour, health): " INSTANCE; fi
INSTANCE="$(printf '%s' "$INSTANCE" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
[[ "$INSTANCE" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "✗ invalid instance name — start with a-z, then a-z 0-9 - only."; exit 1; }

OPERATOR_PASSWORD="${OPERATOR_PASSWORD:-}"
if [ -z "$OPERATOR_PASSWORD" ]; then
  read -rsp "Operator admin password (min 6 — sets every realm admin; reset on first login): " OPERATOR_PASSWORD; echo
  read -rsp "Confirm password: " _p2; echo
  [ "$OPERATOR_PASSWORD" = "$_p2" ] || { echo "✗ passwords do not match."; exit 1; }
  unset _p2
fi
[ "${#OPERATOR_PASSWORD}" -ge 6 ] || { echo "✗ password too short (min 6)."; exit 1; }

echo "▶ Installing AirawatOS instance '$INSTANCE' (de-seeded; operator-first)…"

# ── 2 · env + Vault token (machine secret; never shown) ──────────────────────────────────────────────
[ -f .env ] || cp .env.example .env
docker compose up -d vault >/dev/null
for i in $(seq 1 30); do
  TOKEN=$(docker compose exec -T vault sh -lc \
    "tr -d '\n ' < /vault/data/init.json | sed 's/.*\"root_token\":\"\([^\"]*\)\".*/\1/'" 2>/dev/null | tr -d '\r\n ')
  [ -n "${TOKEN:-}" ] && break; sleep 2
done
[ -n "${TOKEN:-}" ] || { echo "✗ could not read the Vault token — check: docker compose logs vault"; exit 1; }
if sed --version >/dev/null 2>&1; then sed -i "s|^VAULT_TOKEN=.*|VAULT_TOKEN=$TOKEN|" .env   # GNU
else sed -i '' "s|^VAULT_TOKEN=.*|VAULT_TOKEN=$TOKEN|" .env; fi                                # BSD/macOS

# ── 3 · bring up the stack DE-SEEDED (empty IdP) ─────────────────────────────────────────────────────
IDENTITY_SEED_DEMO="" docker compose up -d >/dev/null
printf "▶ waiting for the network authority"
for i in $(seq 1 40); do
  curl -fsS localhost/network/v1/health >/dev/null 2>&1 && { echo " … ready"; break; }
  printf "."; sleep 3
done

# ── 4 · provision the four realms + admins + scheduler (password via env only) ───────────────────────
docker compose cp ../../network/ensure_install.py network:/app/ensure_install.py >/dev/null
docker compose exec -T -e INSTANCE="$INSTANCE" -e OPERATOR_PASSWORD="$OPERATOR_PASSWORD" \
  network python3 /app/ensure_install.py
unset OPERATOR_PASSWORD

# ── 5 · done ─────────────────────────────────────────────────────────────────────────────────────────
cat <<EOF

✓ AirawatOS is installed for instance '$INSTANCE'.
  Open http://localhost/ and sign in (you'll be asked to set a new password on first login):

    realm                 user     role                  purpose
    ${INSTANCE}-operator  admin    platform.admin        runs the box (operator)
    ${INSTANCE}-network   admin    network.admin         the dictionary / authority
    ${INSTANCE}           admin    platform.tenant-admin the data tenant
    ${INSTANCE}-developer admin    platform.tenant-admin development (+ base-component steward)

  Teardown + fresh reinstall:  docker compose down -v
EOF

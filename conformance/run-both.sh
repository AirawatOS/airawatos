#!/usr/bin/env bash
# Run the conformance suite in BOTH modes (external + internal) against the local-dev stack, credentialed,
# N times (default 3). Runs INSIDE the local-dev `network` container, which is the only place that can reach
# BOTH the edge (nginx) and Vault — so every Vault-minted service token + the .creds.json logins resolve and
# a healthy stack shows 0 SKIP_CREDS. Prints each run's tally so you can confirm the runs are identical.
#
#   conformance/run-both.sh            # 3 iterations of each mode
#   conformance/run-both.sh 1          # 1 iteration
#
# Prereqted by the installer: .creds.json generated FROM Vault (Phase 13) + the stack healthy
# (identity /healthz lockout_store=durable(postgres)). See docs/operator/OPERATOR-GUIDE.md.
set -euo pipefail
N="${1:-3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
# Resolve the running `network` container of the local-dev compose project.
NET="$(docker ps --filter "label=com.docker.compose.project=$P" --filter "name=network" --format '{{.Names}}' | head -1)"
[ -n "$NET" ] || NET="$(docker ps --format '{{.Names}}' | grep -E 'ld-network$' | head -1)"
[ -n "$NET" ] || { echo "✗ could not find the local-dev network container (is the stack up?)"; exit 1; }
EDGE="${AOS_EDGE:-http://nginx}"     # the edge nginx service, reachable on the compose network
REALM="${AOS_REALM:-localdev-network}"
echo "▶ conformance both modes ×$N — container=$NET edge=$EDGE realm=$REALM"

# L1-1b: services no longer carry the shared VAULT_TOKEN (per-service AppRole). The conformance harness still
# needs a Vault token to MINT a wrong-audience token for the ingress-abuse tests (reads a principal password),
# which only a privileged token can do — so discover the install-time ROOT from the vault volume and pass it to
# the test exec ONLY (never a service). Empty if unavailable → those cases SKIP_CREDS, not fail.
VROOT_TOK="$(docker exec "$NET" sh -lc 'true' 2>/dev/null && docker exec "$(docker ps --format '{{.Names}}' | grep -E 'ld-vault$' | head -1)" sh -lc 'tr -d "\n " < /vault/data/init.json 2>/dev/null | sed "s/.*\"root_token\":\"\([^\"]*\)\".*/\1/"' 2>/dev/null | tr -d '\r')"
VT_ARG=""; [ -n "$VROOT_TOK" ] && VT_ARG="-e VAULT_TOKEN=$VROOT_TOK -e VAULT_ADDR=http://vault:8200"
docker exec "$NET" mkdir -p /tmp/conf
docker cp "$HERE/run.py" "$NET:/tmp/conf/run.py"
[ -f "$HERE/.creds.json" ] && docker cp "$HERE/.creds.json" "$NET:/tmp/conf/.creds.json" || echo "  ⚠ no .creds.json (run installer Phase 13 first) — external logins will SKIP_CREDS"

for i in $(seq 1 "$N"); do
  echo "================= iteration $i / $N ================="
  echo "----- external -----"
  docker exec -e AOS_MODE=external -e AOS_BASE="$EDGE" -e AOS_REALM="$REALM" $VT_ARG "$NET" python3 /tmp/conf/run.py 2>&1 | sed -n '/== mode/,/^TOTAL/p'
  echo "----- internal -----"
  docker exec -e AOS_MODE=internal $VT_ARG "$NET" python3 /tmp/conf/run.py 2>&1 | sed -n '/== mode/,/^TOTAL/p'
done

#!/usr/bin/env bash
# Restore a backup made by backup.sh (slice-1h, DEBT-B102). DESTROYS the current stack state.
#   deploy/local-dev/restore.sh <backup-dir>
# Verifies every archive against the manifest, removes the stack (containers + volumes), recreates each volume from its
# archive, puts the host secrets back, starts the stack and waits until every service is healthy.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$HERE/docker-compose.dev.yml")
IN="${1:?usage: restore.sh <backup-dir>}"
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$HERE/docker-compose.dev.yml")"
python3 - "$IN" <<'PY'
import hashlib, json, os, sys
d = sys.argv[1]; m = json.load(open(os.path.join(d, "manifest.json")))
for v, h in m["volumes"].items():
    got = hashlib.sha256(open(os.path.join(d, v + ".tgz"), "rb").read()).hexdigest()
    if got != h:
        raise SystemExit("✗ %s.tgz does not match the manifest — refusing to restore" % v)
print("  ✓ %d archives match the manifest" % len(m["volumes"]))
PY
t0=$(date +%s)
echo "▶ restore ← $IN (removing the current stack and its volumes)"
"${C[@]}" down -v --remove-orphans >/dev/null 2>&1
for a in "$IN"/*.tgz; do
  v="$(basename "$a" .tgz)"
  docker volume rm "${P}_$v" >/dev/null 2>&1 || true
  docker volume create --label com.docker.compose.project="$P" --label com.docker.compose.volume="$v" "${P}_$v" >/dev/null
  docker run --rm --user 0:0 --entrypoint tar -v "${P}_$v":/dst -v "$IN":/b:ro "$TAR_IMG" xzf "/b/$v.tgz" -C /dst
done
cp "$IN/host/.env" "$HERE/.env"
mkdir -p "$HERE/vault/approle" && cp "$IN"/host/approle/*.env "$HERE/vault/approle/"
"${C[@]}" up -d >/dev/null 2>&1
for i in $(seq 1 90); do
  n="$(docker ps --filter "label=com.docker.compose.project=$P" --format '{{.Status}}' | grep -c 'healthy)' || true)"
  bad="$(docker ps --filter "label=com.docker.compose.project=$P" --format '{{.Status}}' | grep -cE 'starting|unhealthy' || true)"
  [ "$bad" = 0 ] && [ "$n" -ge 15 ] && break
  sleep 3
done
[ "$bad" = 0 ] || { echo "✗ restore: services not healthy after start"; exit 1; }
echo "✓ restore complete: $(ls "$IN"/*.tgz | wc -l | tr -d ' ') volumes restored, stack healthy, RTO $(( $(date +%s) - t0 ))s"

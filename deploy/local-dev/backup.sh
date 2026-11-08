#!/usr/bin/env bash
# Consistent point-in-time backup of EVERY durable store of the local-dev stack (slice-1h, DEBT-B102 / re-review R4-2).
#   deploy/local-dev/backup.sh [backup-dir]      (default: deploy/local-dev/backups/<UTC timestamp>)
# The stack is QUIESCED (all containers stopped) so Postgres, Vault, identity, filestore and app-bundles are taken at
# the SAME point in time (the consistency rule: DB-role passwords live in Vault, the roles in Postgres; identity's
# accounts and rotated passwords live ONLY in the identity volume). Each volume becomes one tar.gz; the host-side
# secrets (.env with the Postgres superuser password, the per-service AppRole env files) are copied too. A manifest
# records sha256 of every archive. The backup is a FULL credential set (Vault root token + unseal key): the directory
# is created 0700 — store it as a secret.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$HERE/docker-compose.dev.yml")
OUT="${1:-$HERE/backups/$(date -u +%Y%m%dT%H%M%SZ)}"
VOLS="localdev_pg localdev_vault localdev_vault_audit localdev_identity localdev_filestore localdev_appbundles localdev_netfiles"
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$HERE/docker-compose.dev.yml")"   # pinned, has tar
umask 077; mkdir -p "$OUT/host"; chmod 700 "$OUT"
t0=$(date +%s)
echo "▶ backup → $OUT (quiescing the stack)"
"${C[@]}" stop >/dev/null 2>&1
for v in $VOLS; do
  docker volume inspect "${P}_$v" >/dev/null 2>&1 || { echo "✗ volume ${P}_$v missing — nothing to back up?"; "${C[@]}" start >/dev/null 2>&1; exit 1; }
  docker run --rm --user 0:0 --entrypoint tar -v "${P}_$v":/src:ro -v "$OUT":/b "$TAR_IMG" czf "/b/$v.tgz" -C /src .
done
cp "$HERE/.env" "$OUT/host/.env"
mkdir -p "$OUT/host/approle" && cp "$HERE"/vault/approle/*.env "$OUT/host/approle/"
"${C[@]}" start >/dev/null 2>&1
python3 - "$OUT" $VOLS <<'PY'
import hashlib, json, os, sys, time
out, vols = sys.argv[1], sys.argv[2:]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
m = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "volumes": {v: sha(os.path.join(out, v + ".tgz")) for v in vols},
     "host": sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(os.path.join(out, "host")) for f in fs)}
json.dump(m, open(os.path.join(out, "manifest.json"), "w"), indent=1)
PY
echo "✓ backup complete: $(echo $VOLS | wc -w | tr -d ' ') volumes + host secrets in $(( $(date +%s) - t0 ))s (the stack was stopped for the copy)"

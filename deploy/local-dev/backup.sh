#!/usr/bin/env bash
# Consistent point-in-time backup of EVERY durable store of the local-dev stack (slice-1h DEBT-B102; slice-1i DEBT-B126).
#   deploy/local-dev/backup.sh [backup-dir]      (default: deploy/local-dev/backups/<UTC timestamp>, gitignored)
# The stack is QUIESCED (all containers stopped) so every volume is taken at the SAME point in time; each volume becomes
# one tar.gz; the host-side secrets (.env, the per-service AppRole env files) are copied too. The manifest records the
# sha256 of EVERY archive and EVERY host file (restore.sh refuses anything that does not match it exactly).
# slice-1i (DEBT-B126): the stack is ALWAYS restarted (EXIT trap) and ANY failure is reported (✗) with a non-zero exit —
# a failed backup never leaves the stack stopped or silently claims success. A backup directory inside the repository
# is refused unless it is the gitignored default (the backup holds the Vault unseal key and every service secret).
# slice-1j (step 4): the backup NEVER holds a Vault root token — blanked in the archived init.json, and the finished backup
# is scanned (_backup_scan.py: any root_token value, the live root token, any Vault token literal) or it FAILS.
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$HERE/docker-compose.dev.yml")
OUT="${1:-$HERE/backups/$(date -u +%Y%m%dT%H%M%SZ)}"
VOLS="${AOS_BACKUP_VOLS:-localdev_pg localdev_vault localdev_vault_audit localdev_identity localdev_filestore localdev_appbundles localdev_netfiles}"
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$HERE/docker-compose.dev.yml")"   # pinned, has tar
STOPPED=0; DONE=0; STEP="start"
_finish() {
  rc=$?
  if [ "$STOPPED" = 1 ]; then
    "${C[@]}" start >/dev/null 2>&1 || echo "✗ backup: COULD NOT RESTART the stack — run: docker compose -p $P … start" >&2
  fi
  if [ "$DONE" != 1 ]; then
    echo "✗ backup FAILED at step: $STEP (exit ${rc}) — no valid backup was produced${OUT:+; partial output in $OUT}" >&2
    [ "$rc" = 0 ] && exit 1
  fi
}
trap _finish EXIT
case "$(cd "$(dirname "$OUT")" 2>/dev/null && pwd)/" in
  "$REPO"/*) case "$OUT" in "$HERE/backups/"*) ;; *) STEP="output dir"; echo "✗ backup dir $OUT is inside the repository but not the gitignored deploy/local-dev/backups/ — refused" >&2; exit 2 ;; esac ;;
esac
umask 077; mkdir -p "$OUT/host"; chmod 700 "$OUT"
t0=$(date +%s)
echo "▶ backup → $OUT (quiescing the stack)"
STEP="stop the stack"; "${C[@]}" stop >/dev/null; STOPPED=1
for v in $VOLS; do
  STEP="archive volume $v"
  docker volume inspect "${P}_$v" >/dev/null 2>&1 || { echo "✗ volume ${P}_$v missing" >&2; exit 1; }
  # slice-1j (step 4): a backup NEVER carries the Vault root token — the local-dev Vault keeps its init output (root token
  # included) as init.json on its own data volume; the archived copy has the root token BLANKED (the unseal key stays: it
  # is what a restore needs; vault/entrypoint.sh regenerates a root token from it after a restore).
  docker run --rm --user 0:0 --entrypoint sh -v "${P}_$v":/src:ro -v "$OUT":/b "$TAR_IMG" -c '
    D=/src
    if [ -f /src/init.json ]; then
      mkdir /w && cp -a /src/. /w/ && sed -i "s/\"root_token\": *\"[^\"]*\"/\"root_token\": \"\"/" /w/init.json && D=/w || exit 1
    fi
    tar czf "/b/$0.tgz" -C "$D" .' "$v"
done
STEP="copy host secrets"
cp "$HERE/.env" "$OUT/host/.env"
mkdir -p "$OUT/host/approle" && cp "$HERE"/vault/approle/*.env "$OUT/host/approle/"
STEP="restart the stack"; "${C[@]}" start >/dev/null; STOPPED=0
STEP="write the manifest"
python3 - "$OUT" $VOLS <<'PY'
import hashlib, json, os, sys, time
out, vols = sys.argv[1], sys.argv[2:]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
host = sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(os.path.join(out, "host")) for f in fs)
m = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "volumes": {v: sha(os.path.join(out, v + ".tgz")) for v in vols},
     "host": {h: sha(os.path.join(out, h)) for h in host}}
json.dump(m, open(os.path.join(out, "manifest.json"), "w"), indent=1)
PY
STEP="verify: no Vault root token in the backup"
AOS_ROOT_TOKEN="$(docker exec "$(docker ps -q --filter "label=com.docker.compose.project=$P" --filter "label=com.docker.compose.service=vault" | head -1)" sh -c \
  "tr -d '\n ' < /vault/data/init.json 2>/dev/null | sed -n 's/.*\"root_token\":\"\([^\"]*\)\".*/\1/p'" 2>/dev/null || true)" \
  python3 "$HERE/_backup_scan.py" "$OUT"
DONE=1
echo "✓ backup complete: $(echo $VOLS | wc -w | tr -d ' ') volumes + $(find "$OUT/host" -type f | wc -l | tr -d ' ') host secret files in $(( $(date +%s) - t0 ))s (the stack was stopped for the copy)"

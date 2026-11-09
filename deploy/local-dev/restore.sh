#!/usr/bin/env bash
# Restore a backup made by backup.sh (slice-1h DEBT-B102; slice-1i DEBT-B124/B125). DESTROYS the current stack state —
# but ONLY after EVERYTHING it will use has been validated:
#   1. the manifest lists EXACTLY the archives present (no missing, no extra) and every host file present (no missing,
#      no extra); every archive and every host file matches its sha256;
#   2. every archive is test-extracted (gzip + tar integrity) BEFORE anything is removed;
# Any problem → refused, nothing touched. Then: stack + volumes removed, each volume recreated from its archive, the host
# secrets put back, the stack started; the restore succeeds only when EVERY project container is running and every
# container with a healthcheck is HEALTHY (a restarting or exited container fails it).
#   deploy/local-dev/restore.sh <backup-dir>
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$HERE/docker-compose.dev.yml")
IN="${1:?usage: restore.sh <backup-dir>}"
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$HERE/docker-compose.dev.yml")"
DESTROYED=0
trap 'rc=$?; [ "$rc" != 0 ] && { [ "$DESTROYED" = 1 ] && echo "✗ restore FAILED after the stack was removed — the backup in $IN is untouched; fix the cause and re-run restore.sh" >&2 || echo "✗ restore REFUSED — nothing was changed" >&2; }' EXIT
python3 - "$IN" <<'PY'
import hashlib, json, os, sys
d = sys.argv[1]
try:
    m = json.load(open(os.path.join(d, "manifest.json")))
except Exception as e:
    raise SystemExit("✗ manifest.json missing or unreadable: %s" % e)
vols, host = m.get("volumes") or {}, m.get("host") or {}
present = {f[:-4] for f in os.listdir(d) if f.endswith(".tgz")}
hostf = {os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(os.path.join(d, "host")) for f in fs}
errs = []
if not vols:
    errs.append("the manifest lists no volume archive")
if set(vols) != present:
    errs.append("archives present %s ≠ manifest %s" % (sorted(present), sorted(vols)))
if not host or ".env" not in {os.path.basename(h) for h in host}:
    errs.append("the manifest lists no host secrets (.env, approle env files)")
if set(host) != hostf:
    errs.append("host files present %s ≠ manifest %s" % (sorted(hostf), sorted(host)))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
for v, h in vols.items():
    p = os.path.join(d, v + ".tgz")
    if os.path.exists(p) and sha(p) != h:
        errs.append("%s.tgz does not match its sha256" % v)
for f, h in host.items():
    p = os.path.join(d, f)
    if os.path.exists(p) and sha(p) != h:
        errs.append("host file %s does not match its sha256" % f)
if errs:
    raise SystemExit("✗ backup does not validate — refusing to restore:\n    " + "\n    ".join(errs))
print("  ✓ manifest: %d archives + %d host files present and matching" % (len(vols), len(host)))
PY
for a in "$IN"/*.tgz; do       # test-extract EVERY archive before anything is removed
  docker run --rm --user 0:0 --entrypoint sh -v "$IN":/b:ro "$TAR_IMG" -c "tar tzf /b/$(basename "$a") >/dev/null" \
    || { echo "✗ $(basename "$a") is not a readable gzip/tar archive — refusing to restore" >&2; exit 1; }
done
echo "  ✓ every archive test-extracts cleanly"
t0=$(date +%s)
echo "▶ restore ← $IN (removing the current stack and its volumes)"
DESTROYED=1
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
want="$("${C[@]}" config --services | wc -l | tr -d ' ')"
ok=0
for i in $(seq 1 90); do
  st="$(docker ps -a --filter "label=com.docker.compose.project=$P" --format '{{.Names}}|{{.State}}|{{.Status}}')"
  running="$(printf '%s\n' "$st" | grep -c '|running|' || true)"
  bad="$(printf '%s\n' "$st" | grep -cE 'starting|unhealthy|restarting|exited|dead' || true)"
  if [ "$running" -ge "$want" ] && [ "$bad" = 0 ]; then ok=1; break; fi
  sleep 3
done
if [ "$ok" != 1 ]; then
  echo "✗ restore: the stack did not come up healthy — not running/healthy:" >&2
  printf '%s\n' "$st" | grep -vE '\|running\|.*\(healthy\)|nginx' >&2 || true
  exit 1
fi
echo "✓ restore complete: $(ls "$IN"/*.tgz | wc -l | tr -d ' ') volumes + host secrets restored; all $want services running and healthy; RTO $(( $(date +%s) - t0 ))s"

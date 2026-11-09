#!/usr/bin/env bash
# Restore a backup made by backup.sh — STAGE, VERIFY, then SWITCH (slice-1j, DEBT-B139/B140; was slice-1h B102 /
# slice-1i B124). Nothing of the running stack is touched until a COMPLETE, VERIFIED stage exists, and the previous
# state is kept until the restored stack is healthy:
#   1. VALIDATE against what the stack DECLARES, not against the backup's own claims: the archives must be EXACTLY the
#      volumes docker-compose.dev.yml declares (missing or extra → refused); the host secrets must be EXACTLY .env plus
#      one AppRole env file (VAULT_ROLE_ID + VAULT_SECRET_ID) for every role the compose file references; every file
#      must match the manifest's sha256; no archive or host file may carry a Vault root token (slice-1j step 4).
#   2. SCAN every archive member on the host (python tarfile, full decompression): absolute paths, `..`, links that
#      point outside the volume, device/fifo members → refused.
#   3. STAGE: every archive is EXTRACTED IN FULL into a side volume (<project>-stage-<vol>) and the staged tree is
#      compared with the archive's member list. A failure here (bad member, disk full, unwritable) → refused, stage
#      removed, the running stack untouched.
#   4. SWITCH: the stack is stopped (volumes kept); each live volume is copied aside (<project>-prev-<vol>) and the host
#      secrets to .restore-prev/; the live volumes are refilled from the stage; the stack is started.
#   5. The restore succeeds only when EVERY service is running and every container with a healthcheck is HEALTHY.
#      Otherwise — or on ANY error after the switch began — it ROLLS BACK automatically: the previous volumes and host
#      secrets are put back and the previous stack started (on a new host with no previous state: the restored volumes
#      are removed again). Exit non-zero either way.
#   deploy/local-dev/restore.sh <backup-dir>
#   AOS_RESTORE_WAIT_S (default 270): how long the restored stack may take to become healthy.
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
CF="$HERE/docker-compose.dev.yml"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$CF")
[ -n "${1:-}" ] || { echo "usage: restore.sh <backup-dir>" >&2; exit 2; }
IN="$(cd "$1" 2>/dev/null && pwd)" || { echo "✗ backup directory $1 not found — restore REFUSED, nothing was changed" >&2; exit 1; }
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$CF")"
WAIT_S="${AOS_RESTORE_WAIT_S:-270}"
PREV_HOST="$HERE/.restore-prev"
PHASE=validate; SWITCHED=0; ROLLED=0; VOLS=""; PREV_EXISTED=""

dkr_run() { docker run --rm --user 0:0 --entrypoint sh "$@"; }
cleanup_side() { for v in $VOLS; do docker volume rm -f "$P-stage-$v" "$P-prev-$v" >/dev/null 2>&1 || true; done; rm -rf "$PREV_HOST"; }

wait_healthy() {   # every compose service running; nothing starting/unhealthy/restarting/exited  ($1 = seconds)
  local want st running bad i n=$(( ${1:-$WAIT_S} / 3 ))
  want="$("${C[@]}" config --services 2>/dev/null | wc -l | tr -d ' ')"
  for i in $(seq 1 "$n"); do
    st="$(docker ps -a --filter "label=com.docker.compose.project=$P" --format '{{.Names}}|{{.State}}|{{.Status}}')"
    running="$(printf '%s\n' "$st" | grep -c '|running|' || true)"
    bad="$(printf '%s\n' "$st" | grep -cE 'starting|unhealthy|restarting|exited|dead' || true)"
    if [ "$running" -ge "$want" ] && [ "$bad" = 0 ]; then return 0; fi
    sleep 3
  done
  echo "  not running/healthy:" >&2; printf '%s\n' "$st" | grep -vE '\|running\|.*\(healthy\)|nginx' >&2 || true
  return 1
}

rollback() {
  set +e; ROLLED=1
  echo "↺ restore: ROLLING BACK to the previous state" >&2
  "${C[@]}" down --remove-orphans >/dev/null 2>&1
  local ok=1 v
  for v in $VOLS; do
    if printf ' %s ' "$PREV_EXISTED" | grep -q " $v "; then
      dkr_run -v "${P}_$v":/dst -v "$P-prev-$v":/src:ro "$TAR_IMG" -c 'find /dst -mindepth 1 -delete && cp -a /src/. /dst/' || ok=0
    else
      docker volume rm -f "${P}_$v" >/dev/null 2>&1     # it did not exist before this restore (a new host)
    fi
  done
  if [ -d "$PREV_HOST" ]; then
    rm -f "$HERE/.env" "$HERE"/vault/approle/*.env
    [ -f "$PREV_HOST/.env" ] && cp -p "$PREV_HOST/.env" "$HERE/.env"
    ls "$PREV_HOST"/approle/*.env >/dev/null 2>&1 && mkdir -p "$HERE/vault/approle" && cp -p "$PREV_HOST"/approle/*.env "$HERE/vault/approle/"
  fi
  if [ -n "$PREV_EXISTED" ]; then
    "${C[@]}" up -d >/dev/null 2>&1 || ok=0
    wait_healthy "${AOS_ROLLBACK_WAIT_S:-270}" || ok=0     # the previous stack gets the full budget, whatever WAIT_S is
  fi
  if [ "$ok" = 1 ]; then
    cleanup_side
    echo "✗ restore FAILED in phase '$PHASE' — ROLLED BACK: the previous state is back$([ -n "$PREV_EXISTED" ] && echo ' and healthy'); the backup in $IN is untouched" >&2
  else
    echo "✗ restore FAILED in phase '$PHASE' and the ROLLBACK did not complete — the previous volumes are kept as $P-prev-<vol> and the host secrets in $PREV_HOST; do not delete them" >&2
  fi
}

_exit() {
  rc=$?
  [ "$rc" = 0 ] && return
  if [ "$SWITCHED" = 1 ] && [ "$ROLLED" = 0 ]; then rollback
  elif [ "$SWITCHED" = 0 ]; then
    for v in $VOLS; do docker volume rm -f "$P-stage-$v" >/dev/null 2>&1 || true; done
    echo "✗ restore REFUSED in phase '$PHASE' — nothing was changed" >&2
  fi
}
trap _exit EXIT

# ── 1+2. validate against the DECLARED stack, scan every archive member ────────────────────────────────────────────
VOLS="$(python3 "$HERE/_restore_check.py" "$IN" "$CF")" || exit 1
LISTS="${VOLS%% *}"; VOLS="${VOLS#* }"

# ── 3. stage: extract EVERY archive in full into a side volume and compare it with the archive's member list ───────
PHASE=stage
for v in $VOLS; do
  docker volume rm -f "$P-stage-$v" >/dev/null 2>&1 || true
  docker volume create "$P-stage-$v" >/dev/null
  dkr_run -v "$P-stage-$v":/dst -v "$IN":/b:ro "$TAR_IMG" -c "tar xzf /b/$v.tgz -C /dst" \
    || { echo "✗ $v.tgz does not extract — refusing to restore" >&2; exit 1; }
  dkr_run -v "$P-stage-$v":/dst:ro "$TAR_IMG" -c 'cd /dst && find . | LC_ALL=C sort' > "$LISTS/$v.staged" \
    || { echo "✗ could not list the staged $v" >&2; exit 1; }
  LC_ALL=C sort "$LISTS/$v" | diff -q - "$LISTS/$v.staged" >/dev/null \
    || { echo "✗ staged $v differs from its archive's member list — refusing to restore" >&2; exit 1; }
done
rm -rf "$LISTS"
echo "  ✓ staged: every archive extracted in full into a side volume and matches its member list"

# ── 4. switch (previous state kept) ────────────────────────────────────────────────────────────────────────────────
t0=$(date +%s)
echo "▶ restore ← $IN (switching; the previous state is kept until the restored stack is healthy)"
PHASE=switch; SWITCHED=1
"${C[@]}" down --remove-orphans >/dev/null 2>&1
for v in $VOLS; do
  if docker volume inspect "${P}_$v" >/dev/null 2>&1; then
    PREV_EXISTED="$PREV_EXISTED $v"
    docker volume rm -f "$P-prev-$v" >/dev/null 2>&1 || true; docker volume create "$P-prev-$v" >/dev/null
    dkr_run -v "${P}_$v":/src:ro -v "$P-prev-$v":/dst "$TAR_IMG" -c 'cp -a /src/. /dst/'
  else
    docker volume create --label com.docker.compose.project="$P" --label com.docker.compose.volume="$v" "${P}_$v" >/dev/null
  fi
done
rm -rf "$PREV_HOST"; mkdir -p "$PREV_HOST/approle"; chmod 700 "$PREV_HOST"
[ -f "$HERE/.env" ] && cp -p "$HERE/.env" "$PREV_HOST/.env"
ls "$HERE"/vault/approle/*.env >/dev/null 2>&1 && cp -p "$HERE"/vault/approle/*.env "$PREV_HOST/approle/"
for v in $VOLS; do
  dkr_run -v "${P}_$v":/dst -v "$P-stage-$v":/src:ro "$TAR_IMG" -c 'find /dst -mindepth 1 -delete && cp -a /src/. /dst/'
done
mkdir -p "$HERE/vault/approle"
rm -f "$HERE"/vault/approle/*.env
cp "$IN/host/.env" "$HERE/.env"
cp "$IN"/host/approle/*.env "$HERE/vault/approle/"
PHASE="start the restored stack"
"${C[@]}" up -d >/dev/null 2>&1
PHASE="wait until every service is healthy"
wait_healthy
cleanup_side
echo "✓ restore complete: $(echo $VOLS | wc -w | tr -d ' ') volumes + host secrets restored; all services running and healthy; RTO $(( $(date +%s) - t0 ))s"

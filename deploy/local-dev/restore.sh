#!/usr/bin/env bash
# Restore a backup made by backup.sh — NEVER IN PLACE (slice-1k, DEBT-B154/B155/B156; was slice-1j B139/B140).
#
# The backup is restored into a NEW, separately named VOLUME SET (volumes <set>_<vol> + host secrets in
# deploy/local-dev/sets/<set>/) beside the live one; the stack is started on the new set and the cut-over is only the
# atomic move of ONE pointer (sets/active, see _sets.py). restore.sh NEVER writes to or deletes any other set — the
# live/previous set stays byte-identical whatever happens; deleting it later is a separate, explicit operator action
# (`deploy/local-dev/_sets.py prune <set>`).
#   1. VALIDATE against what the stack DECLARES (_restore_check.py): exactly the declared volumes, .env + one AppRole file
#      per role, every sha256, every archive member scanned, no Vault token anywhere.
#   2. BUILD the new set: each archive extracted IN FULL into a brand-new volume <set>_<vol> and compared with its member
#      list; the host secrets written into sets/<set>/ (AOS_VOLSET pinned to the new set).
#   3. CUT OVER (journal written first): the live stack is stopped (volumes untouched), the pointer moved to the new set,
#      the stack started on it; success only when every service is running and healthy.
#   4. ANY failure, error or signal (TERM/INT/HUP) → the pointer goes back, the previous stack is restarted if it was
#      running, and ONLY the new set is removed. SIGKILL cannot be trapped: the journal stays, the next restore.sh refuses
#      to run, and `restore.sh --recover` finishes the rollback (the previous set is untouched either way).
#   deploy/local-dev/restore.sh <backup-dir>      |      deploy/local-dev/restore.sh --recover
#   AOS_RESTORE_WAIT_S (default 270): how long the restored stack may take to become healthy.
#   Test hooks, honoured only with AOS_RESTORE_TEST=1 (verify/backup_restore_selftest.py): AOS_RESTORE_TEST_PAUSE=<stage>
#   (+ AOS_RESTORE_TEST_PAUSE_FILE) pauses at a stage so a signal can be sent; AOS_RESTORE_TEST_FAULT=<stage> fails it;
#   AOS_RESTORE_TEST_TMPFS=<vol>:<size> makes that NEW volume a small tmpfs (disk full while staging).
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
CF="$HERE/docker-compose.dev.yml"
C=(docker compose -p "$P" --project-directory "$HERE" -f "$CF")
SETS="$HERE/sets"; JOURNAL="$SETS/.restore-journal"; SP=(python3 "$HERE/_sets.py")
TAR_IMG="$(awk '/^ *image: *hashicorp\/vault/{print $2; exit}' "$CF")"
WAIT_S="${AOS_RESTORE_WAIT_S:-270}"
STAGE=validate; S=""; PREV=""; PREV_RUNNING=0; CUT=0; DONE=0; ABORTED=0; VOLS=""; LISTS=""; IN=""

_test() { [ "${AOS_RESTORE_TEST:-}" = 1 ]; }
pause() { STAGE="$1"; echo "  · stage: $1 ($(date -u +%H:%M:%S))"
  if _test && [ "${AOS_RESTORE_TEST_PAUSE:-}" = "$1" ]; then : > "${AOS_RESTORE_TEST_PAUSE_FILE:?}"; sleep 600 & wait $! || true; fi
  if _test && [ "${AOS_RESTORE_TEST_FAULT:-}" = "$1" ]; then echo "⚡ test fault injected at stage $1" >&2; return 1; fi; return 0; }
dkr() { docker run --rm --user 0:0 --entrypoint sh "$@"; }
running() { docker ps -q --filter "label=com.docker.compose.project=$P" | wc -l | tr -d ' '; }

wait_healthy() {   # every compose service running; nothing starting/unhealthy/restarting/exited
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

remove_new_set() {   # ONLY the new set: its volumes and its host-secrets dir — never anything else
  local v
  [ -n "$S" ] || return 0
  for v in $("${SP[@]}" vols); do docker volume rm -f "${S}_$v" >/dev/null 2>&1 || true; done
  rm -rf "${SETS:?}/$S"
}

rollback() {   # stack off the new set, pointer back, previous stack restarted if it was running, new set removed
  set +e
  if [ "$CUT" = 1 ]; then
    "${C[@]}" down --remove-orphans >/dev/null 2>&1
    if [ -n "$PREV" ]; then "${SP[@]}" switch "$PREV"; else rm -f "$SETS/active"; fi
    if [ "$PREV_RUNNING" = 1 ]; then
      "${C[@]}" up -d >/dev/null 2>&1
      wait_healthy "${AOS_ROLLBACK_WAIT_S:-270}" || echo "✗ the PREVIOUS stack did not come back healthy — its set ($PREV) is untouched; inspect it" >&2
    fi
  fi
  remove_new_set
  rm -f "$JOURNAL"
}

abort() {   # $1 = why
  [ "$ABORTED" = 0 ] || return 0; ABORTED=1
  if [ "$CUT" = 1 ]; then
    echo "↺ restore: rolling back ($1, stage '$STAGE') — the pointer goes back to ${PREV:-<none>}; only the new set $S is removed" >&2
    rollback
    echo "✗ restore FAILED at stage '$STAGE' ($1) — ROLLED BACK: the previous set ${PREV:-<none>} is active and untouched$([ "$PREV_RUNNING" = 1 ] && echo ', its stack restarted'); the backup in ${IN:-?} is untouched" >&2
  else
    set +e; remove_new_set; rm -f "$JOURNAL"; [ -n "$LISTS" ] && rm -rf "$LISTS"
    echo "✗ restore REFUSED at stage '$STAGE' ($1) — nothing of the live stack was touched${S:+; the partial new set $S was removed}" >&2
  fi
}
on_signal() { trap '' TERM INT HUP; kill $(jobs -p) 2>/dev/null || true; abort "signal $1"; DONE=1; exit 143; }
_exit() { rc=$?; [ "$DONE" = 1 ] && return; [ "$rc" = 0 ] && rc=1; abort "error, exit $rc"; exit "$rc"; }

# ── --recover: finish a rollback after a SIGKILL (or a crash) left the journal behind ──────────────────────────────
if [ "${1:-}" = "--recover" ]; then
  [ -f "$JOURNAL" ] || { echo "  ✓ no interrupted restore (no journal) — nothing to recover"; exit 0; }
  PREV="$(sed -n 's/^PREV=//p' "$JOURNAL")"; S="$(sed -n 's/^NEW=//p' "$JOURNAL")"; PREV_RUNNING="$(sed -n 's/^PREV_RUNNING=//p' "$JOURNAL")"
  CUT="$(sed -n 's/^CUT=//p' "$JOURNAL")"; [ "$CUT" = 1 ] || CUT=0
  case "$S" in "$P"-r*) ;; *) echo "✗ the journal names an unexpected set '$S' — refusing; inspect $JOURNAL" >&2; exit 1 ;; esac
  echo "↺ recovering an interrupted restore ($([ "$CUT" = 1 ] && echo "after the cut-over: back to ${PREV:-<none>}" || echo "before the cut-over: the live stack was never touched")); removing only the new set $S"
  rollback
  echo "✓ recovered: active set ${PREV:-<none>}; the new set $S removed; the previous set untouched"; exit 0
fi
[ -n "${1:-}" ] || { echo "usage: restore.sh <backup-dir> | --recover" >&2; exit 2; }
if [ -f "$JOURNAL" ]; then
  echo "✗ an interrupted restore was found ($JOURNAL) — run: deploy/local-dev/restore.sh --recover" >&2; exit 1
fi
if { [ -e "$HERE/.env" ] && [ ! -L "$HERE/.env" ]; } || { [ -d "$HERE/vault/approle" ] && [ ! -L "$HERE/vault/approle" ] && [ -n "$(ls -A "$HERE/vault/approle")" ]; }; then
  echo "✗ this install uses the legacy flat .env layout — run deploy/local-dev/_sets.py ensure-layout (or the installer) first" >&2; exit 1
fi
trap 'on_signal TERM' TERM; trap 'on_signal INT' INT; trap 'on_signal HUP' HUP; trap _exit EXIT
IN="$(cd "$1" 2>/dev/null && pwd)" || { echo "✗ backup directory $1 not found" >&2; exit 1; }
PREV="$("${SP[@]}" active)"

# ── 1. validate against the DECLARED stack ─────────────────────────────────────────────────────────────────────────
OUT="$(python3 "$HERE/_restore_check.py" "$IN" "$CF")"
LISTS="${OUT%% *}"; VOLS="${OUT#* }"
pause validated

# ── 2. build the NEW set beside the live one ───────────────────────────────────────────────────────────────────────
S="${P}-r$(date -u +%Y%m%dT%H%M%SZ)-$(od -An -N3 -tx1 /dev/urandom | tr -d ' \n')"
if [ -e "$SETS/$S" ] || [ -n "$(docker volume ls -q --filter "name=^${S}_")" ]; then echo "✗ set $S already exists" >&2; S=""; exit 1; fi
mkdir -p "$SETS"; chmod 700 "$SETS"
( umask 077; printf 'PREV=%s\nNEW=%s\nPREV_RUNNING=0\nCUT=0\n' "$PREV" "$S" > "$JOURNAL" )   # a SIGKILL from here on is recoverable
set -- $VOLS; N=$#; i=0
for v in $VOLS; do
  i=$((i + 1)); pos=middle; [ "$i" = 1 ] && pos=first; [ "$i" = "$N" ] && pos=last
  pause "extract-$pos"
  topt=()
  if _test && [ "${AOS_RESTORE_TEST_TMPFS:-}" != "" ] && [ "${AOS_RESTORE_TEST_TMPFS%%:*}" = "$v" ]; then
    topt=(--driver local --opt type=tmpfs --opt device=tmpfs --opt "o=size=${AOS_RESTORE_TEST_TMPFS#*:}")
  fi
  docker volume create "${topt[@]+"${topt[@]}"}" --label com.docker.compose.project="$P" --label com.docker.compose.volume="$v" "${S}_$v" >/dev/null
  dkr -v "${S}_$v":/dst -v "$IN":/b:ro "$TAR_IMG" -c "tar xzf /b/$v.tgz -C /dst" \
    || { echo "✗ $v.tgz does not extract into the new set" >&2; exit 1; }
  dkr -v "${S}_$v":/dst:ro "$TAR_IMG" -c 'cd /dst && find . | LC_ALL=C sort' > "$LISTS/$v.staged" \
    || { echo "✗ could not list the new $v" >&2; exit 1; }
  LC_ALL=C sort "$LISTS/$v" | diff -q - "$LISTS/$v.staged" >/dev/null \
    || { echo "✗ the new $v differs from its archive's member list" >&2; exit 1; }
done
rm -rf "$LISTS"; LISTS=""
pause verified
mkdir -p "$SETS/$S/approle"; chmod 700 "$SETS" "$SETS/$S"
python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import _sets; _sets.write_env(sys.argv[2], open(sys.argv[3]).read())' "$HERE" "$S" "$IN/host/.env"
cp "$IN"/host/approle/*.env "$SETS/$S/approle/"; chmod 600 "$SETS/$S"/approle/*.env
pause secrets
echo "  ✓ new set $S built: $(echo $VOLS | wc -w | tr -d ' ') volumes extracted in full and checked, host secrets in sets/$S/"

# ── 3. cut over (journal first) ────────────────────────────────────────────────────────────────────────────────────
t0=$(date +%s)
[ "$(running)" -gt 0 ] && PREV_RUNNING=1
( umask 077; printf 'PREV=%s\nNEW=%s\nPREV_RUNNING=%s\nCUT=1\n' "$PREV" "$S" "$PREV_RUNNING" > "$JOURNAL" )
CUT=1
echo "▶ restore ← $IN — cutting over from ${PREV:-<no previous set>} to $S (the previous set is never touched)"
"${C[@]}" down --remove-orphans >/dev/null 2>&1
pause stopped
[ -L "$HERE/.env" ] || ln -s sets/active/.env "$HERE/.env"
if [ ! -L "$HERE/vault/approle" ]; then
  [ -d "$HERE/vault/approle" ] && rmdir "$HERE/vault/approle" 2>/dev/null   # an EMPTY leftover dir only (a new host)
  ln -s ../sets/active/approle "$HERE/vault/approle"
fi
"${SP[@]}" switch "$S"
pause switched
"${C[@]}" up -d >/dev/null 2>&1
pause started
wait_healthy
rm -f "$JOURNAL"; DONE=1
echo "  · healthy ($(date -u +%H:%M:%S))"
echo "✓ restore complete: the stack runs on the new set $S, all services running and healthy; RTO $(( $(date +%s) - t0 ))s"
[ -z "$PREV" ] || echo "  · the previous set $PREV is KEPT, untouched. Delete it explicitly when it is no longer needed: deploy/local-dev/_sets.py prune $PREV"
exit 0

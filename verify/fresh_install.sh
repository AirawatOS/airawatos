#!/usr/bin/env bash
# Fresh-install harness with VERIFICATION INTEGRITY (slice-1d, FIX-PLAN §0 net 7).
#
# A "fresh install" result is only worth something if the install really started from nothing. This harness
#   1. tears the local-dev project down WITH its volumes,
#   2. REFUSES to continue (exit 3) unless it can prove the slate is empty: no container, no volume and no network
#      of the project remains (a stale stack — e.g. a teardown that silently did nothing — is caught here),
#   3. runs `deploy/installer/install.sh --profile dev` (which ends with the Phase 15 functional proof), and
#   4. proves afterwards that every project volume was CREATED by this run (creation time ≥ the harness start), so
#      the install could not have reused old state.
# Exit: 0 = fresh install passed; 3 = not a clean slate / reused state (refused); otherwise the installer's code.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
P="${AOS_LD_PROJECT:-airawatos-localdev}"
C=(docker compose -p "$P" --project-directory "$ROOT/deploy/local-dev" -f "$ROOT/deploy/local-dev/docker-compose.dev.yml")
LOG="${FRESH_INSTALL_LOG:-$ROOT/conformance/results/fresh-install.log}"; mkdir -p "$(dirname "$LOG")"

echo "▶ fresh install — tear down $P (containers + volumes + networks)"
"${C[@]}" down -v --remove-orphans >/dev/null 2>&1
# the project's own networks that compose no longer models (e.g. an unused `<project>_default`) are not removed by
# `down`; drop them only when no container is attached. Volumes and containers are NEVER auto-removed here — a
# leftover one is exactly the stale state this harness exists to refuse.
for n in $(docker network ls -q --filter "label=com.docker.compose.project=$P"); do
  [ "$(docker network inspect -f '{{len .Containers}}' "$n")" = 0 ] && docker network rm "$n" >/dev/null 2>&1
done
left_c="$(docker ps -a --filter "label=com.docker.compose.project=$P" -q | wc -l | tr -d ' ')"
left_v="$(docker volume ls -q --filter "label=com.docker.compose.project=$P" | wc -l | tr -d ' ')"
left_v2="$(docker volume ls -q | grep -cE "^${P}(_|-r)" || true)"   # slice-1k: every volume set of the project (<set>_<vol>)
left_n="$(docker network ls -q --filter "label=com.docker.compose.project=$P" | wc -l | tr -d ' ')"
if [ "$left_c" != 0 ] || [ "$left_v" != 0 ] || [ "$left_v2" != 0 ] || [ "$left_n" != 0 ]; then
  echo "✗ REFUSED: not a clean slate after teardown — containers=$left_c volumes=$left_v/$left_v2 networks=$left_n"
  echo "  (a fresh-install result from a stale stack would be meaningless; remove them and re-run)"; exit 3
fi
echo "  ✓ clean slate proven: 0 containers, 0 volumes, 0 networks for project $P"
# slice-1k: no volume of ANY set is left, so every set's host secrets are stale — start the host layout from nothing too
# (the installer creates sets/<project>/ and the .env / vault/approle symlinks). Only the set layout is removed here.
LD="$ROOT/deploy/local-dev"
if [ -d "$LD/sets" ]; then rm -rf "$LD/sets"; fi
[ -L "$LD/.env" ] && rm -f "$LD/.env"
[ -L "$LD/vault/approle" ] && rm -f "$LD/vault/approle"
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; START_EPOCH="$(date -u +%s)"

echo "▶ fresh install — deploy/installer/install.sh --profile dev  (log: ${LOG#$ROOT/})"
"$ROOT/deploy/installer/install.sh" --profile dev > "$LOG" 2>&1; rc=$?
sed -n '/Phase 15/,$p' "$LOG" | grep -E "✓|✗" | sed 's/^/  /'
[ "$rc" = 0 ] || { echo "✗ install FAILED (exit $rc) — see ${LOG#$ROOT/}"; exit "$rc"; }

stale=0
for v in $(docker volume ls -q --filter "label=com.docker.compose.project=$P"); do
  created="$(docker volume inspect -f '{{.CreatedAt}}' "$v")"
  ce="$(python3 -c "import sys,datetime;print(int(datetime.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()))" "$created" 2>/dev/null || echo 0)"
  if [ "$ce" -lt "$START_EPOCH" ]; then echo "  ✗ volume $v predates this run ($created < $START)"; stale=1; fi
done
[ "$stale" = 0 ] || { echo "✗ REFUSED: the install reused pre-existing state"; exit 3; }
echo "  ✓ every project volume was created by this run (≥ $START)"
echo "✓ fresh install passed from a proven-empty slate"

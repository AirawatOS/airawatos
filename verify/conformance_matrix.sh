#!/usr/bin/env bash
# Conformance, BOTH modes, writing matrix results (conformance/results/local-dev-{external,internal}.json).
# Runs inside the local-dev `network` container (it reaches the edge and Vault), with the install-time root token
# read from the vault volume and passed to this exec only.
# slice-1h (DEBT-B99, re-review R6-1/R3-5): FRESH EVIDENCE ONLY. Before each mode the previous results are DELETED (in the
# container and on the host); run.py's exit code must be 0 (all pass) or 1 (cases failed) — anything else means the suite
# did not run; the results file must exist, carry THIS run id and at least one case. Otherwise the net FAILS.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
NET="${AOS_NET_CONTAINER:-airawat-ld-network}"; VLT="${AOS_VAULT_CONTAINER:-airawat-ld-vault}"
export AOS_RUN_ID="${AOS_RUN_ID:-$(python3 "$HERE/evidence.py" new-run-id)-adhoc}"
VR="$(docker exec "$VLT" sh -lc 'tr -d "\n " < /vault/data/init.json | sed "s/.*\"root_token\":\"\([^\"]*\)\".*/\1/"')"
SHA="$(git -C "$ROOT" rev-parse --short HEAD)"
docker exec "$NET" sh -c 'rm -rf /tmp/conf && mkdir -p /tmp/conf' || { echo "✗ conformance: cannot reach $NET"; exit 1; }
docker cp "$ROOT/conformance/run.py" "$NET:/tmp/conf/run.py" >/dev/null
[ -f "$ROOT/conformance/.creds.json" ] && docker cp "$ROOT/conformance/.creds.json" "$NET:/tmp/conf/.creds.json" >/dev/null
mkdir -p "$ROOT/conformance/results"
fail=0
for i in $(seq 1 "${1:-1}"); do
  for m in external internal; do
    rm -f "$ROOT/conformance/results/local-dev-$m.json"
    docker exec "$NET" rm -f "/tmp/conf/results/local-dev-$m.json"
    extra=(); [ "$m" = external ] && extra=(-e AOS_BASE=http://nginx -e AOS_REALM=localdev-network)
    docker exec -e GIT_SHA="$SHA" -e AOS_MODE=$m -e AOS_RUN_ID="$AOS_RUN_ID" ${extra[@]+"${extra[@]}"} -e VAULT_TOKEN="$VR" \
           -e VAULT_ADDR=http://vault:8200 "$NET" python3 /tmp/conf/run.py --matrix > "$ROOT/conformance/results/conformance-$m.log" 2>&1
    rc=$?
    if [ "$rc" != 0 ] && [ "$rc" != 1 ]; then
      echo "  ✗ conformance $m: run.py did not complete (exit $rc) — see conformance/results/conformance-$m.log"; fail=1; continue
    fi
    if ! docker cp "$NET:/tmp/conf/results/local-dev-$m.json" "$ROOT/conformance/results/" >/dev/null 2>&1; then
      echo "  ✗ conformance $m: run.py wrote NO results file"; fail=1; continue
    fi
    tally="$(python3 - "$ROOT/conformance/results/local-dev-$m.json" <<'PY'
import collections, json, os, sys
d = json.load(open(sys.argv[1]))
if d.get("run_id") != os.environ["AOS_RUN_ID"]:
    print("STALE run_id=%r (expected %r)" % (d.get("run_id"), os.environ["AOS_RUN_ID"])); sys.exit(0)
if not d.get("cases"):
    print("EMPTY (0 cases)"); sys.exit(0)
c = collections.Counter(x["result"] for x in d["cases"])
print(" ".join(f"{k}={c.get(k,0)}" for k in ("PASS", "XFAIL", "XPASS", "FAIL", "SKIP_CREDS", "SKIP_BUILD")))
PY
)"
    echo "  conformance $m (iteration $i, run $AOS_RUN_ID): $tally"
    case "$tally" in *"XPASS=0 FAIL=0 SKIP_CREDS=0"*) python3 "$HERE/evidence.py" seal "$ROOT/conformance/results/local-dev-$m.json" >/dev/null ;;
      *) fail=1 ;; esac
  done
done
docker exec "$NET" rm -f /tmp/conf/.creds.json    # re-review R3-10/R4-16: no creds fixture left in the edge-facing container
[ "$fail" = 0 ] && echo "✓ conformance both modes: 0 FAIL, 0 XPASS, 0 SKIP_CREDS (fresh evidence, run $AOS_RUN_ID)" \
  || { echo "✗ conformance: FAIL, XPASS, SKIP_CREDS, stale or missing evidence"; exit 1; }

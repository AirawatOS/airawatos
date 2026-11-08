#!/usr/bin/env bash
# Conformance, BOTH modes, writing matrix results (conformance/results/local-dev-{external,internal}.json).
# Runs inside the local-dev `network` container (it reaches the edge and Vault), with the install-time root token
# read from the vault volume and passed to this exec only. N iterations (default 1); the last one writes results.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
NET="${AOS_NET_CONTAINER:-airawat-ld-network}"; VLT="${AOS_VAULT_CONTAINER:-airawat-ld-vault}"
VR="$(docker exec "$VLT" sh -lc 'tr -d "\n " < /vault/data/init.json | sed "s/.*\"root_token\":\"\([^\"]*\)\".*/\1/"')"
SHA="$(git -C "$ROOT" rev-parse --short HEAD)"
docker exec "$NET" mkdir -p /tmp/conf
docker cp "$ROOT/conformance/run.py" "$NET:/tmp/conf/run.py" >/dev/null
[ -f "$ROOT/conformance/.creds.json" ] && docker cp "$ROOT/conformance/.creds.json" "$NET:/tmp/conf/.creds.json" >/dev/null
fail=0
for i in $(seq 1 "${1:-1}"); do
  for m in external internal; do
    extra=(); [ "$m" = external ] && extra=(-e AOS_BASE=http://nginx -e AOS_REALM=localdev-network)
    docker exec -e GIT_SHA="$SHA" -e AOS_MODE=$m ${extra[@]+"${extra[@]}"} -e VAULT_TOKEN="$VR" -e VAULT_ADDR=http://vault:8200 \
           "$NET" python3 /tmp/conf/run.py --matrix >/dev/null 2>&1 || true
    # --matrix prints no report: tally from the results file it wrote
    tally="$(docker exec "$NET" python3 -c "import json,collections;c=collections.Counter(x['result'] for x in json.load(open('/tmp/conf/results/local-dev-$m.json'))['cases']);print(' '.join(f'{k}={c.get(k,0)}' for k in ('PASS','XFAIL','XPASS','FAIL','SKIP_CREDS','SKIP_BUILD')))")"
    echo "  conformance $m (iteration $i): $tally"
    case "$tally" in *"XPASS=0 FAIL=0 SKIP_CREDS=0"*) ;; *) fail=1 ;; esac
  done
done
mkdir -p "$ROOT/conformance/results"
for m in external internal; do docker cp "$NET:/tmp/conf/results/local-dev-$m.json" "$ROOT/conformance/results/" >/dev/null; done
[ "$fail" = 0 ] && echo "✓ conformance both modes: 0 FAIL, 0 XPASS, 0 SKIP_CREDS" || { echo "✗ conformance: FAIL, XPASS or SKIP_CREDS present"; exit 1; }

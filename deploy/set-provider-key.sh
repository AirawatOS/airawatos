#!/usr/bin/env bash
# Set an intelligence-provider API key into the LOCAL Vault at the exact path the model-gateway reads.
#   ./deploy/set-provider-key.sh <component-id> <KEY_NAME> <value> [tenant] [vault-addr] [vault-token]
# e.g. ./deploy/set-provider-key.sh ds:airawat:provider/anthropic ANTHROPIC_API_KEY sk-ant-xxx
set -euo pipefail
COMP="$1"; NAME="$2"; VAL="$3"; TENANT="${4:-kmc}"; VADDR="${5:-http://localhost:8200}"; VTOK="${6:-airawat-dev-root}"
python3 - "$COMP" "$NAME" "$VAL" "$TENANT" "$VADDR" "$VTOK" <<'PY'
import sys, json, urllib.parse, urllib.request
comp,name,val,tenant,vaddr,vtok = sys.argv[1:7]
path = f"{tenant}/{urllib.parse.quote(comp, safe='')}/{name}"
req = urllib.request.Request(f"{vaddr}/v1/secret/data/{path}",
    data=json.dumps({"data":{"value":val}}).encode(),
    headers={"X-Vault-Token":vtok,"Content-Type":"application/json"})
urllib.request.urlopen(req, timeout=8); print(f"set {name} for {comp} (tenant {tenant})")
PY

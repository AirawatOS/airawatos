#!/bin/sh
# Start Vault (file storage), then auto-init (first boot only) + auto-unseal on EVERY boot. The unseal key
# + root token are persisted in the data volume (/vault/data/init.json) so restarts are seamless. This is a
# DEMO convenience (single unseal key on the same volume) — a real deployment uses auto-unseal (KMS/HSM) and
# keeps the unseal keys off-box.
set -e
export VAULT_ADDR=http://127.0.0.1:8200
vault server -config=/vault/config/vault.hcl &
VPID=$!
# wait for the server to answer
until vault status >/dev/null 2>&1 || vault status 2>&1 | grep -qi seal; do sleep 1; done
# init once
if ! vault status 2>&1 | grep -qi 'Initialized *true'; then
  echo "[vault] initializing (first boot)"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > /vault/data/init.json
fi
UNSEAL=$(grep -o '"unseal_keys_b64":[^]]*]' /vault/data/init.json | grep -o '"[A-Za-z0-9+/=]\{20,\}"' | head -1 | tr -d '"')
vault operator unseal "$UNSEAL" >/dev/null 2>&1 || true
if vault status 2>&1 | grep -qi 'Sealed *false'; then echo "[vault] UNSEALED"; else echo "[vault] STILL SEALED — check init.json"; fi
wait $VPID

#!/bin/sh
# Start Vault (file storage), then auto-init (first boot only) + auto-unseal on EVERY boot. The unseal key
# + root token are persisted in the data volume (/vault/data/init.json) so restarts are seamless. This is a
# DEMO convenience (single unseal key on the same volume) — a real deployment uses auto-unseal (KMS/HSM) and
# keeps the unseal keys off-box.
set -e
# slice-1f (DEBT-B79): Vault 2.x runs as the non-root `vault` user, but the data volume mounts root-owned. Start as
# root ONLY to hand the data directory to `vault`, then re-exec this script as `vault` (su-exec ships in the image).
if [ "$(id -u)" = 0 ]; then
  mkdir -p /vault/data && chown -R vault:vault /vault/data
  exec su-exec vault /bin/sh "$0" "$@"
fi
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
# `vault operator init -format=json` writes PRETTY-PRINTED (multi-line) JSON — flatten it (strip newlines +
# spaces; keys/tokens contain neither) before the sed extract. Alpine sh: no jq/python.
UNSEAL=$(tr -d '\n ' < /vault/data/init.json | sed 's/.*"unseal_keys_b64":\["\([^"]*\)".*/\1/')
vault operator unseal "$UNSEAL" >/dev/null 2>&1 || true
if vault status 2>&1 | grep -qi 'Sealed *false'; then echo "[vault] UNSEALED"; else echo "[vault] STILL SEALED — check init.json"; fi
# Server mode (unlike -dev) does NOT auto-mount the KV engine — enable secret/ kv-v2 idempotently so the
# Components app, secrets service, and model-gateway can read/write secret/data/… (transit is enabled by
# the identity/network services themselves).
export VAULT_TOKEN=$(tr -d '\n ' < /vault/data/init.json | sed 's/.*"root_token":"\([^"]*\)".*/\1/')
vault secrets enable -version=2 -path=secret kv >/dev/null 2>&1 || true
# slice-1g (DEBT-B89): component secrets in their OWN mount — the brokers' policies cover this mount only, never the
# platform credentials in secret/ (DB passwords, service principals, the audit HMAC key).
vault secrets enable -version=2 -path=components kv >/dev/null 2>&1 || true
wait $VPID

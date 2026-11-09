#!/bin/sh
# Start Vault (file storage), then auto-init (first boot only) + auto-unseal on EVERY boot. The unseal key
# + root token are persisted in the data volume (/vault/data/init.json) so restarts are seamless. slice-1j: a BACKUP of
# this volume carries the unseal key but never the root token (backup.sh blanks it); after a restore the root token is
# generated ON DEMAND only (deploy/local-dev/vault_root.py; slice-1k) — never here at start. This is a
# DEMO convenience (single unseal key on the same volume) — a real deployment uses auto-unseal (KMS/HSM) and
# keeps the unseal keys off-box.
set -e
# slice-1f (DEBT-B79): Vault 2.x runs as the non-root `vault` user, but the data volume mounts root-owned. Start as
# root ONLY to hand the data directory to `vault`, then re-exec this script as `vault` (su-exec ships in the image).
if [ "$(id -u)" = 0 ]; then
  mkdir -p /vault/data /vault/audit && chown -R vault:vault /vault/data /vault/audit
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
export VAULT_TOKEN=$(tr -d '\n ' < /vault/data/init.json | sed -n 's/.*"root_token":"\([^"]*\)".*/\1/p')
# slice-1k (DEBT-B160a): NO root token is ever generated here. A restored Vault (its init.json carries none — backup.sh
# blanks it) runs WITHOUT a root token; tooling that needs one generates it ON DEMAND (deploy/local-dev/vault_root.py,
# generate-root with the unseal key) and revokes it when done. The first-boot setup below runs only when a root token is
# present (the very first boot); a restored Vault already holds its mounts and audit device in its storage.
if [ -n "$VAULT_TOKEN" ]; then
vault secrets enable -version=2 -path=secret kv >/dev/null 2>&1 || true
# slice-1g (DEBT-B89): component secrets in their OWN mount — the brokers' policies cover this mount only, never the
# platform credentials in secret/ (DB passwords, service principals, the audit HMAC key).
vault secrets enable -version=2 -path=components kv >/dev/null 2>&1 || true
# slice-1h (DEBT-B102 / re-review R4-7): a FILE AUDIT DEVICE on its own volume — every Vault request and response is
# recorded (secret values HMAC'd, never in clear). Idempotent. ROTATION: when audit.log passes AUDIT_MAX_MB it is
# renamed (keeping AUDIT_KEEP generations) and Vault is sent SIGHUP, which reopens the audit file.
vault audit list 2>/dev/null | grep -q '^file/' || vault audit enable file file_path=/vault/audit/audit.log >/dev/null \
  || echo "[vault] ✗ could not enable the file audit device"
vault audit list 2>/dev/null | grep -q '^file/' && echo "[vault] audit device: file → /vault/audit/audit.log"
else
  echo "[vault] no root token at rest — none is generated at start (on demand: deploy/local-dev/vault_root.py generate)"
fi
unset VAULT_TOKEN
( MAX=$(( ${AUDIT_MAX_MB:-50} * 1024 * 1024 )); KEEP=${AUDIT_KEEP:-5}
  while sleep ${AUDIT_ROTATE_CHECK_S:-60}; do
    f=/vault/audit/audit.log
    [ -f "$f" ] && [ "$(wc -c < "$f")" -gt "$MAX" ] || continue
    i=$KEEP; while [ "$i" -gt 1 ]; do [ -f "$f.$((i-1))" ] && mv "$f.$((i-1))" "$f.$i"; i=$((i-1)); done
    mv "$f" "$f.1" && kill -HUP "$VPID" && echo "[vault] audit log rotated"
  done ) &
wait $VPID

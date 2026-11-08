# FIX-PLAN L1-1b — least-privilege Vault policy for the NETWORK service.
# Doors: DB-app password + the Trust-plane reader/writer/audit creds; transit for the authority signing key.
path "secret/data/localdev/network-app/*"              { capabilities = ["read"] }
path "secret/data/localdev-network/trust-reader/*"     { capabilities = ["read"] }
path "secret/data/localdev-network/trust-writer/*"     { capabilities = ["read"] }
path "secret/data/localdev-network/trust-plane/*"      { capabilities = ["read"] }
path "secret/metadata/localdev-network/*"              { capabilities = ["read", "list"] }
# slice-1g (DEBT-B88): ONLY the network authority key and the per-tenant steward keys — create/read, sign.
# Never identity's issuer key. (The steward-* glob also lets the network administer its OWN steward keys —
# Vault globs cannot stop at the key name; per-tenant keys are created at runtime.)
path "transit/keys/airawat-authority" { capabilities = ["create", "read", "update"] }
path "transit/sign/airawat-authority" { capabilities = ["update"] }
path "transit/keys/steward-*"         { capabilities = ["create", "read", "update"] }
path "transit/sign/steward-*"         { capabilities = ["update"] }
# ADR-0131 / slice-1c-iv-c — the network's join→provision paths mint svc:identity as the `provisioner` principal
# (inline minter in api.py). READ-only, exactly the provisioner's install-config secret — nothing else under
# the operator realm (not the admin bootstrap password).
path "secret/data/localdev-operator/provisioner/*"     { capabilities = ["read"] }

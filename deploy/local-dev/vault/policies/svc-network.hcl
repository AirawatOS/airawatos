# FIX-PLAN L1-1b — least-privilege Vault policy for the NETWORK service.
# Doors: DB-app password + the Trust-plane reader/writer/audit creds; transit for the authority signing key.
path "secret/data/localdev/network-app/*"              { capabilities = ["read"] }
path "secret/data/localdev-network/trust-reader/*"     { capabilities = ["read"] }
path "secret/data/localdev-network/trust-writer/*"     { capabilities = ["read"] }
path "secret/data/localdev-network/trust-plane/*"      { capabilities = ["read"] }
path "secret/metadata/localdev-network/*"              { capabilities = ["read", "list"] }
path "transit/*" { capabilities = ["create", "read", "update"] }   # authority EdDSA key sign/verify/create

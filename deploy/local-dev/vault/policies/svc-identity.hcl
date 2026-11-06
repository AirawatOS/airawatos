# FIX-PLAN L1-1b — least-privilege Vault policy for the IDENTITY service.
# Doors: its lockout-store DB password; transit for the issuer EdDSA signing key.
path "secret/data/localdev/identity-lockout/*"     { capabilities = ["read"] }
path "secret/metadata/localdev/identity-lockout/*" { capabilities = ["read", "list"] }
path "transit/*" { capabilities = ["create", "read", "update"] }   # issuer EdDSA key sign/verify/create

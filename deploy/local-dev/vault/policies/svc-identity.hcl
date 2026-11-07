# FIX-PLAN L1-1b — least-privilege Vault policy for the IDENTITY service.
# Doors: its lockout-store DB password; transit for the issuer EdDSA signing key.
path "secret/data/localdev/identity-lockout/*"     { capabilities = ["read"] }
path "secret/metadata/localdev/identity-lockout/*" { capabilities = ["read", "list"] }
path "transit/*" { capabilities = ["create", "read", "update"] }   # issuer EdDSA key sign/verify/create
# ADR-0131 — the operator install config (root of trust). Identity self-bootstraps the operator admin + the
# provisioner from here at boot (create-only). READ-only, scoped to exactly these two config secrets.
path "secret/data/localdev-operator/admin/*"           { capabilities = ["read"] }
path "secret/data/localdev-operator/provisioner/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/admin/*"       { capabilities = ["read"] }
path "secret/metadata/localdev-operator/provisioner/*" { capabilities = ["read"] }

# FIX-PLAN L1-1b — least-privilege Vault policy for the IDENTITY service.
# Doors: its lockout-store DB password; transit for the issuer EdDSA signing key.
path "secret/data/localdev/identity-lockout/*"     { capabilities = ["read"] }
path "secret/metadata/localdev/identity-lockout/*" { capabilities = ["read", "list"] }
# slice-1g (DEBT-B88): ONLY identity's own issuer keys — create/read the key, sign with it. No rotate/config
# (key administration is install-time root), and no other service's key.
path "transit/keys/airawat-identity" { capabilities = ["create", "read", "update"] }
path "transit/sign/airawat-identity" { capabilities = ["update"] }
path "transit/keys/identity-*"       { capabilities = ["create", "read", "update"] }   # per-tenant issuer keys (ADR-0084)
path "transit/sign/identity-*"       { capabilities = ["update"] }
# ADR-0131 — the operator install config (root of trust). Identity self-bootstraps the operator admin + the
# provisioner from here at boot (create-only). READ-only, scoped to exactly these two config secrets.
path "secret/data/localdev-operator/admin/*"           { capabilities = ["read"] }
path "secret/data/localdev-operator/provisioner/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/admin/*"       { capabilities = ["read"] }
path "secret/metadata/localdev-operator/provisioner/*" { capabilities = ["read"] }

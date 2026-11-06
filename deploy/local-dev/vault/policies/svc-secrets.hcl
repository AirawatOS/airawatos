# FIX-PLAN L1-1b — Vault policy for the SECRETS service.
# WIDENED (recorded): the secrets service IS the Vault KV broker (ADR-0124) — it reads/writes per-(tenant,
# component) secrets on behalf of components. Fine-grained per-(tenant,component) authorization is enforced in
# secrets.py's OWN gate, not in this Vault policy, so this is deliberately broad on the KV data plane.
path "secret/data/*"     { capabilities = ["create", "read", "update", "delete"] }
path "secret/metadata/*" { capabilities = ["read", "list", "delete"] }

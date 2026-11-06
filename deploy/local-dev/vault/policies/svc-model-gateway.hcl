# FIX-PLAN L1-1b — Vault policy for the MODEL-GATEWAY service.
# WIDENED (recorded): model-gateway reads each tenant's provider API key from secret/data/<tenant>/<component>/
# <key> and writes keys via /admin/provider-key — per-tenant, so broad on the KV data plane. (Fine-grained
# per-caller authorization is model-gateway's own gate.)
path "secret/data/*"     { capabilities = ["create", "read", "update"] }
path "secret/metadata/*" { capabilities = ["read", "list"] }

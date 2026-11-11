# FIX-PLAN L1-1c-ii — least-privilege Vault policy for the DECISION service.
# Door: reads ONLY its own service-identity password to mint an audience-bound svc:notify token (svc_token),
# which it attaches when posting to notify /notify. No other Vault access.
path "secret/data/localdev-operator/decision/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/decision/*" { capabilities = ["read", "list"] }

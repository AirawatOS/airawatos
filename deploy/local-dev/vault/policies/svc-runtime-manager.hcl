# slice-1c-iv step 2 — least-privilege Vault policy for the RUNTIME MANAGER (placement authority).
# It reads ONLY the `launcher` principal's password, to mint the launcher's audience-bound svc:secrets
# (/materialize) + svc:filestore (source fetch) tokens. Raw component secrets come via the secrets SERVICE, never
# directly from Vault (ARC-7).
path "secret/data/localdev-operator/launcher/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/launcher/*" { capabilities = ["read", "list"] }

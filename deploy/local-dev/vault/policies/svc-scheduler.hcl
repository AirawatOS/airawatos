# FIX-PLAN L1-1b — least-privilege Vault policy for the reference-plane daemons (scheduler, automation,
# event-relay). They authenticate as the shared `scheduler@localdev-operator` principal (DEBT-A68) and read
# only that one password to mint their audience-bound service token (svc_token).
path "secret/data/localdev-operator/scheduler/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/scheduler/*" { capabilities = ["read", "list"] }

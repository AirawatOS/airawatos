# FIX-PLAN L1-1b — least-privilege Vault policy for the reference-plane daemons (scheduler, automation,
# event-relay). They authenticate as the shared `scheduler@localdev-operator` principal (DEBT-A68) and read
# only that one password to mint their audience-bound service token (svc_token).
path "secret/data/localdev-operator/scheduler/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/scheduler/*" { capabilities = ["read", "list"] }
# slice-1c-ii — the scheduler hosts the IN-PROCESS launcher (DEBT-B51); the launcher mints its own
# svc:filestore token under the `launcher` principal, so the scheduler's Vault token must read that password.
path "secret/data/localdev-operator/launcher/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/launcher/*" { capabilities = ["read", "list"] }

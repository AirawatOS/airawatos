# slice-1j (DEBT-B138) — the ONLY self-service paths a service token needs, attached to every service role IN PLACE OF Vault's
# built-in `default` policy (which also grants cubbyhole, response wrapping, hashing, lease and identity reads — none used).
#   lookup-self / renew-self: the baked renewer (vault_renew.py) and healthcheck (svc_health.py);
#   capabilities-self: a token may ask what it may do (introspection only; used by the Vault scope conformance test).
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/renew-self"  { capabilities = ["update"] }
path "sys/capabilities-self"  { capabilities = ["update"] }

# DEBT-B174/notify decision — least-privilege Vault policy for the NOTIFY service.
# Door: reads ONLY its own service-identity password to mint a platform-audience token, with which it writes
# platform.inbox_item through the kernel's notify lane (and nothing else — the kernel refuses any other schema).
path "secret/data/localdev-operator/notify/*"     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/notify/*" { capabilities = ["read", "list"] }

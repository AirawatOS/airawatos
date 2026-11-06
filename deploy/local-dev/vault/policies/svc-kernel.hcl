# FIX-PLAN L1-1b — least-privilege Vault policy for the KERNEL service.
# Doors: reads its own DB-app password; (per the slice brief) kernel additionally gets transit.
path "secret/data/localdev/kernel-app/*"     { capabilities = ["read"] }
path "secret/metadata/localdev/kernel-app/*" { capabilities = ["read", "list"] }
# WIDENED (recorded): "kernel additionally transit" per the slice brief. Kernel's active transit use is
# future (REG-17 field encryption, B23 registry signing); granted now so those land without a policy change.
path "transit/*" { capabilities = ["create", "read", "update"] }

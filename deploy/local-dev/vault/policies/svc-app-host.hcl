# FIX-PLAN L1-1b — Vault policy for the APP-HOST service. It mints audience-bound service tokens (ADR-0124)
# for several principals and reads their passwords.
# WIDENED (recorded, modestly): scoped to the three principal-bearing tenants rather than the exact principal
# names (app-host, embed-client under operator; component-publisher under network; dev-sandbox under developer).
path "secret/data/localdev-operator/*"                      { capabilities = ["read"] }
path "secret/data/localdev-network/component-publisher/*"   { capabilities = ["read"] }
path "secret/data/localdev-developer/*"                     { capabilities = ["read"] }
path "secret/metadata/localdev-operator/*"                  { capabilities = ["read", "list"] }

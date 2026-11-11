# Vault policy for the APP-HOST service. It mints audience-bound service tokens (ADR-0124) for its OWN principals
# and reads only their passwords, plus the operator-set inbound SMS gateway token (DEBT-B64).
# slice-1g (DEBT-B89, review K3): NARROWED from `localdev-operator/*` (every operator principal: provisioner,
# scheduler, launcher, kernel, …) to the exact principals app-host signs in as.
path "secret/data/localdev-operator/app-host/*"              { capabilities = ["read"] }   # account holds, scheduler caller
path "secret/data/localdev-operator/embed-service/*"         { capabilities = ["read"] }   # ADR-0124 embed-service
path "secret/data/localdev-operator/sms-gateway/*"           { capabilities = ["read"] }   # inbound channel token (B64)
path "secret/data/localdev-network/component-publisher/*"   { capabilities = ["read"] }
path "secret/data/localdev-developer/dev-sandbox/*"          { capabilities = ["read"] }

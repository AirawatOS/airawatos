# Vault policy for the MODEL-GATEWAY.
# It reads each tenant's provider API key from the per-(tenant, component) secret the Components app's
# "Settings → API keys" UI writes (via the secrets broker), and writes keys via /admin/provider-key to the same place.
# slice-1g (DEBT-B89): NARROWED to the component-secrets mount ONLY (components/data/<tenant>/<component>/<key>).
# Before, `secret/data/+/+/*` matched every platform credential too (secret/data/<instance>/kernel-app/password, the
# provisioner, the audit HMAC key) because they share the 3-segment shape. Platform credentials stay in `secret/`, where
# this service has NO capability. Per-(tenant, component) authorization stays the decision-function follow-up.
path "components/data/+/+/*"     { capabilities = ["create", "read", "update"] }
path "components/metadata/+/+/*" { capabilities = ["read", "list"] }

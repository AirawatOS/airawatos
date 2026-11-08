# Vault policy for the SECRETS broker (ADR-0124).
# slice-1g (DEBT-B89): NARROWED to the component-secrets mount ONLY. Component secrets live in their own KV-v2 mount
# `components/` (components/data/<tenant>/<component>/<name>); platform credentials — DB passwords, every service
# principal's password (provisioner, scheduler, launcher, …) and the trust-plane audit HMAC key — stay in `secret/`,
# where each owner's policy grants only its own path. This broker has NO capability anywhere under `secret/`.
# Per-(tenant, component) authorization (which caller may touch which component's secrets) remains secrets.py's own
# gate — the decision-function follow-up.
path "components/data/*"     { capabilities = ["create", "read", "update", "delete"] }
path "components/metadata/*" { capabilities = ["read", "list", "delete"] }

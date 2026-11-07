# FIX-PLAN L1-1c step 4 — Vault policy for the MODEL-GATEWAY service, NARROWED.
#
# model-gateway reads each tenant's provider API key from the per-(tenant, component) secret path the Components
# app's "Settings → API keys" UI writes to — secret/data/<tenant>/<component>/<key> — and writes keys via
# /admin/provider-key to the SAME path (so a key set in the UI is picked up by the gateway). That path IS the
# component-secret KV plane; provider keys share its 3-segment shape with other per-(tenant,component) secrets
# and even with service passwords, so the key store cannot be moved under a DISJOINT provider-only prefix
# without breaking the "set your key in the UI" contract (model_gateway._vault_key docstring).
#
# NARROWED (slice-1c): from `secret/data/*` (the ENTIRE KV tree, any shape) to the per-(tenant, component) KV
# SHAPE `secret/data/+/+/*` only — model-gateway can no longer read root-level or 1-/2-segment paths, only the
# component-secret shape it actually uses. Per-(tenant, component) AUTHORIZATION (which tenant/component this
# caller may read) is NOT expressible as a Vault path glob here; it is the decision-function follow-up, the
# SAME priority recorded for svc-secrets (ADR-0124 — the KV broker's gate becomes a governed decision).
path "secret/data/+/+/*"     { capabilities = ["create", "read", "update"] }
path "secret/metadata/+/+/*" { capabilities = ["read", "list"] }

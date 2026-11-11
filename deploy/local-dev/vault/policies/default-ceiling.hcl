# Vault 2.2.1 BUILT-IN policy "default-ceiling" — NOT written by the installer and attached to NO service token (roles set
# token_no_default_policy=true). Declared here verbatim so the exact-match check (conformance/vault_scope_test.py,
# slice-1j DEBT-B138) fails on any change to it.
# Allow an entity to inspect its own registration information
path "agent-registry/registration/entity-id/{{identity.entity.id}}" {
  capabilities = ["read"]
}

# Allow an entity to read the default policies
path "policy/default" {
  capabilities = ["read"]
}
path "policy/default-ceiling" {
  capabilities = ["read"]
}

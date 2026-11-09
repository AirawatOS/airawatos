# Persistent single-node Vault for the demo — FILE storage (survives container restarts), no HA.
storage "file" { path = "/vault/data" }
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}
disable_mlock = true
ui            = false
# slice-1j (step 4, approved by the owner 2026-11-09): Vault 2.x requires a token for sys/generate-root by default. A backup
# carries the unseal key but NEVER the root token, so after a restore the entrypoint regenerates one with generate-root —
# which still REQUIRES the unseal key share(s) to complete (the pre-2.x Vault behaviour). LOCAL-DEV ONLY: a real deployment
# auto-unseals, keeps its recovery keys off-box and holds no root token at rest.
enable_unauthenticated_access = ["generate-root"]

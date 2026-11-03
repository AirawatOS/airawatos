# Persistent single-node Vault for the demo — FILE storage (survives container restarts), no HA.
storage "file" { path = "/vault/data" }
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}
disable_mlock = true
ui            = false

#!/usr/bin/env bash
# AirawatOS — zero-repo local bootstrap. Run this on a BRAND-NEW machine that has ONLY Docker.
# It materialises the entire deploy/local/ folder (5 files) into a working dir and brings the stack up.
# The platform images are PUBLIC on Docker Hub, so no git clone and no registry login are needed.
#
#   curl -fsSL <this-file> -o airawatos-bootstrap.sh    # or scp / paste it onto the box
#   bash airawatos-bootstrap.sh                          # brings up the full local stack
#
# Front door lands on http://localhost/ . Re-running is safe (idempotent-ish: reuses the same dir + volumes).
set -euo pipefail

DIR="${AIRAWATOS_DIR:-$HOME/airawatos-local}"
echo "▶ AirawatOS local → $DIR"
mkdir -p "$DIR/vault"
cd "$DIR"

# ── 0 · preflight ──────────────────────────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "✗ Docker not found. Install Docker Desktop / Engine first."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "✗ 'docker compose' (v2) not found."; exit 1; }
# Apple-Silicon / arm64 note: the manishsv/airawatos-* images are amd64 and carry explicit `platform: linux/amd64`
# pins in the compose, so they run emulated regardless. Do NOT set a GLOBAL DOCKER_DEFAULT_PLATFORM=linux/amd64 —
# that would force Vault/Postgres/nginx to emulate too, and Vault's Go binary CRASHES under QEMU/Rosetta. Leaving
# it unset lets those infra images run native arm64 (fast, stable) while the Airawat services stay amd64 via the
# pins. Enable "Use Rosetta for x86/amd64 emulation" in Docker Desktop for speed on the amd64 services.
if [ "$(uname -m)" = "arm64" ] || [ "$(uname -m)" = "aarch64" ]; then
  echo "  (arm64 host — Airawat images run amd64-emulated via compose pins; infra runs native. Enable Rosetta for speed.)"
fi

# ── 1 · write docker-compose.yml (quoted heredoc → ${VAULT_TOKEN} is NOT expanded here) ──────────────
cat > docker-compose.yml <<'COMPOSE'
name: airawatos-local

x-ref: &ref
  image: manishsv/airawatos-reference:0.2.115-settings-fixes
  platform: linux/amd64
  restart: unless-stopped
  depends_on: { kernel: { condition: service_started } }

services:
  postgres:
    image: postgres:16-alpine
    container_name: airawat-postgres
    environment: { POSTGRES_DB: kernel, POSTGRES_USER: kernel, POSTGRES_PASSWORD: kernel }
    volumes: [ kernel_pg:/var/lib/postgresql/data ]
    healthcheck: { test: ["CMD-SHELL","pg_isready -U kernel"], interval: 5s, timeout: 5s, retries: 10 }
    restart: unless-stopped

  vault:
    image: hashicorp/vault:1.15
    container_name: airawat-vault
    cap_add: [ IPC_LOCK ]
    environment: { VAULT_ADDR: http://127.0.0.1:8200 }
    volumes:
      - vault_data:/vault/data
      - ./vault/vault.hcl:/vault/config/vault.hcl:ro
      - ./vault/entrypoint.sh:/usr/local/bin/airawat-vault-entrypoint.sh:ro
    entrypoint: ["/bin/sh","/usr/local/bin/airawat-vault-entrypoint.sh"]
    healthcheck: { test: ["CMD","vault","status"], interval: 5s, timeout: 3s, retries: 30 }
    restart: unless-stopped

  kernel:
    image: manishsv/airawatos-kernel:0.2.8-devgrant
    platform: linux/amd64
    container_name: airawat-kernel
    environment:
      REGISTRY_BACKEND: postgres
      DB_HOST: postgres
      NETWORK_URL: http://network:8090
      IDENTITY_JWKS: http://identity:8093/jwks
      KERNEL_REQUIRE_STEWARD_GRANT: "1"
      DEV_REQUIRE_DEVELOPER: "1"
      SHARED_SCHEMAS: "knowledge.document,knowledge.version,knowledge.chunk,knowledge.embedding,governance.rule,platform.verb_alias,platform.lifecycle"
      EVENT_SINK: http://automation:8098/events
      SECRETS_URL: http://secrets:8102
      SECRETS_INTERNAL: airawat-broker-secrets-internal
      FILESTORE_URL: http://filestore:8095
      EMBED_URL: http://model-gateway:8104
      APPS_OVERLAY: /data/app-bundles/apps
    depends_on:
      postgres: { condition: service_healthy }
      network: { condition: service_healthy }
    restart: unless-stopped

  network:
    image: manishsv/airawatos-network:0.3.5-dev-tenant-ensure
    platform: linux/amd64
    container_name: airawat-network
    environment:
      NET_FILES_DIR: /data/netfiles
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: kernel
      DB_USER: kernel
      DB_PASSWORD: kernel
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
      IDENTITY_JWKS: http://identity:8093/jwks
      IDENTITY_URL: http://identity:8093
      IDENTITY_INTERNAL: airawat-identity-internal
      ENSURE_DEV_TENANT: "1"
      DEV_TENANT: airawatdeveloper
      DEV_STEWARD: ds:airawatdeveloper:participant/developer
    depends_on:
      postgres: { condition: service_healthy }
      vault: { condition: service_healthy }
    healthcheck: { test: ["CMD","python","-c","import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/v1/health').status==200 else 1)"], interval: 5s, timeout: 5s, retries: 20 }
    restart: unless-stopped
    volumes: [ netfiles:/data/netfiles ]

  identity:
    <<: *ref
    image: manishsv/airawatos-reference:0.2.83-auth
    container_name: airawat-identity
    command: ["python","reference/identity.py"]
    environment:
      NETWORK_URL: http://network:8090
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
      IDENTITY_USERS_FILE: /data/identity/identity-users.json
      IDENTITY_PASSWORDS_FILE: /data/identity/identity-passwords.json
      IDENTITY_SEED_DEMO: "1"   # quick-eval stack seeds devrick/steward (ADR-0115); the operator-first production installer omits this.
    volumes: [ identity_data:/data/identity ]
    depends_on:
      network: { condition: service_healthy }
      vault: { condition: service_healthy }

  secrets:
    <<: *ref
    container_name: airawat-secrets
    command: ["python","reference/secrets.py"]
    environment:
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
      SECRETS_INTERNAL: airawat-broker-secrets-internal
      IDENTITY_JWKS: http://identity:8093/jwks
    depends_on: { vault: { condition: service_healthy } }

  filestore:
    <<: *ref
    container_name: airawat-filestore
    command: ["python","reference/filestore.py","--port","8095"]
    depends_on: {}
    environment: { FILESTORE_DIR: /data/filestore }
    volumes: [ filestore_data:/data/filestore ]

  model-gateway:
    <<: *ref
    image: manishsv/airawatos-reference:0.2.95-gwreason
    container_name: airawat-model-gateway
    environment: { GW_REASONING_BUDGET: "1200" }
    command: ["python","reference/model_gateway.py","--kernel","http://kernel:8080","--vault","http://vault:8200","--vault-token","${VAULT_TOKEN}"]

  notify:
    <<: *ref
    container_name: airawat-notify
    command: ["python","reference/notify.py","--kernel","http://kernel:8080"]
  workflow:
    <<: *ref
    container_name: airawat-workflow
    command: ["python","reference/workflow.py","--kernel","http://kernel:8080","--network","http://network:8090"]
  decision:
    <<: *ref
    container_name: airawat-decision
    command: ["python","reference/decision.py","--kernel","http://kernel:8080","--network","http://network:8090","--workflow","http://workflow:8097"]
  automation:
    <<: *ref
    container_name: airawat-automation
    command: ["python","reference/automation.py","--kernel","http://kernel:8080"]
  event-relay:
    <<: *ref
    container_name: airawat-event-relay
    command: ["python","reference/event_relay.py","--kernel","http://kernel:8080","--automation","http://automation:8098"]
  scheduler:
    <<: *ref
    image: manishsv/airawatos-reference:0.2.100-sched-devenv
    container_name: airawat-scheduler
    command: ["python","reference/scheduler.py","--components-root","/app/components","--kernel","http://kernel:8080","--network","http://network:8090"]

  app-host:
    <<: *ref
    image: manishsv/airawatos-reference:0.2.115-settings-fixes
    container_name: airawat-app-host
    command: ["python","reference/app_host.py","/app/components/apps","--port","8099",
              "--network","http://network:8090","--kernel","http://kernel:8080",
              "--identity","http://identity:8093","--scheduler","http://scheduler:8103",
              "--secrets","http://secrets:8102","--decision","http://decision:8096",
              "--workflow","http://workflow:8097","--no-verify-cert"]
    environment:
      FILESTORE_URL: http://filestore:8095
      EMBED_URL: http://model-gateway:8104
      PUBLIC_BASE_URL: "http://localhost"
      TELEGRAM_BOT_TOKEN: ""
      TELEGRAM_WEBHOOK_SECRET: ""
    volumes: [ app_bundles:/data/app-bundles ]
    depends_on:
      kernel: { condition: service_started }
      identity: { condition: service_started }

  nginx:
    image: nginx:alpine
    container_name: airawat-nginx
    ports: [ "80:80" ]
    volumes: [ ./nginx.conf:/etc/nginx/conf.d/default.conf:ro ]
    depends_on: [ app-host, network, kernel ]
    restart: unless-stopped

volumes:
  kernel_pg: {}
  vault_data: {}
  filestore_data: {}
  identity_data: {}
  app_bundles: {}
  netfiles: {}
COMPOSE

# ── 2 · nginx front door ─────────────────────────────────────────────────────────────────────────────
cat > nginx.conf <<'NGINX'
server {
    listen 80 default_server;
    server_name localhost;
    client_max_body_size 64m;
    resolver 127.0.0.11 valid=10s ipv6=off;

    location /network/ {
        set $up_network network:8090;
        rewrite ^/network/(.*)$ /$1 break;
        proxy_pass http://$up_network;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /kernel/ {
        set $up_kernel kernel:8080;
        rewrite ^/kernel/(.*)$ /$1 break;
        proxy_pass http://$up_kernel;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / {
        set $up_app app-host:8099;
        proxy_pass http://$up_app;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
NGINX

# ── 3 · vault config + auto-init/unseal entrypoint ─────────────────────────────────────────────────────
cat > vault/vault.hcl <<'HCL'
storage "file" { path = "/vault/data" }
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}
disable_mlock = true
ui            = false
HCL

cat > vault/entrypoint.sh <<'VENTRY'
#!/bin/sh
set -e
export VAULT_ADDR=http://127.0.0.1:8200
vault server -config=/vault/config/vault.hcl &
VPID=$!
until vault status >/dev/null 2>&1 || vault status 2>&1 | grep -qi seal; do sleep 1; done
if ! vault status 2>&1 | grep -qi 'Initialized *true'; then
  echo "[vault] initializing (first boot)"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > /vault/data/init.json
fi
UNSEAL=$(tr -d '\n ' < /vault/data/init.json | sed 's/.*"unseal_keys_b64":\["\([^"]*\)".*/\1/')
vault operator unseal "$UNSEAL" >/dev/null 2>&1 || true
if vault status 2>&1 | grep -qi 'Sealed *false'; then echo "[vault] UNSEALED"; else echo "[vault] STILL SEALED — check init.json"; fi
export VAULT_TOKEN=$(tr -d '\n ' < /vault/data/init.json | sed 's/.*"root_token":"\([^"]*\)".*/\1/')
vault secrets enable -version=2 -path=secret kv >/dev/null 2>&1 || true
wait $VPID
VENTRY
chmod +x vault/entrypoint.sh

# ── 4 · pull public images ─────────────────────────────────────────────────────────────────────────────
echo "▶ pulling images (public — no login needed; first run ~2 GB)"
printf 'VAULT_TOKEN=\n' > .env          # placeholder so compose can parse before the token exists
docker compose pull

# ── 5 · Vault first → capture its auto-generated root token → .env ──────────────────────────────────────
echo "▶ starting Vault to mint its root token"
docker compose up -d vault
for i in $(seq 1 30); do
  TOKEN=$(docker compose exec -T vault sh -lc \
    "tr -d '\n ' < /vault/data/init.json | sed 's/.*\"root_token\":\"\([^\"]*\)\".*/\1/'" 2>/dev/null | tr -d '\r\n ')
  [ -n "${TOKEN:-}" ] && break
  sleep 2
done
[ -n "${TOKEN:-}" ] || { echo "✗ could not read Vault root token — check: docker compose logs vault"; exit 1; }
printf 'VAULT_TOKEN=%s\n' "$TOKEN" > .env
echo "  VAULT_TOKEN captured into $DIR/.env"

# ── 6 · bring up the rest ────────────────────────────────────────────────────────────────────────────────
echo "▶ starting the full stack"
docker compose up -d

# ── 7 · wait for health + verify ───────────────────────────────────────────────────────────────────────
echo "▶ waiting for the front door (first boot is 1–2 min on emulated amd64)…"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/network/v1/health 2>/dev/null || echo 000)
  [ "$code" = "200" ] && break
  sleep 3
done
echo
echo "── health ──────────────────────────────────────────"
echo "network : $(curl -s http://localhost/network/v1/health 2>/dev/null || echo unreachable)"
echo "kernel  : $(curl -s -o /dev/null -w '%{http_code}' http://localhost/kernel/v1/health 2>/dev/null)"
echo "landing : $(curl -s -o /dev/null -w '%{http_code}' http://localhost/ 2>/dev/null)"
echo "────────────────────────────────────────────────────"
echo
echo "✓ Open http://localhost/  (login → realm 'airawatdeveloper', user 'devrick', blank password)"
echo "  Teardown:  (cd $DIR && docker compose down)        keeps data"
echo "             (cd $DIR && docker compose down -v)     full wipe"

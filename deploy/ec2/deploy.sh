#!/usr/bin/env bash
# Deploy AirawatOS to the EC2 demo box (https://airos.airawat.org). Explicit phases so the destructive steps
# (DB restore) are never accidental. The LIVE stack is compose project `airawatos` at $REMOTE — NOT ~/airos/deploy/ec2
# (a stale DIGIT compose whose `up` fails on a missing third-party image). Images are pulled per-service with --no-deps
# so a broken sibling image can never abort the deploy, and postgres (the DB) is never recreated by a code deploy.
#
#   ./deploy/ec2/deploy.sh dump      # regenerate the local DB snapshot → deploy/ec2/seed/kernel.sql.gz
#   ./deploy/ec2/deploy.sh copy      # scp compose + nginx + the snapshot → EC2
#   ./deploy/ec2/deploy.sh pull      # on EC2: docker pull the 3 airawatos images (:0.1.0 == whatever you pushed)
#   ./deploy/ec2/deploy.sh deploy    # recreate ONLY the airawatos services on the new images (code; DB untouched)
#   ./deploy/ec2/deploy.sh restore   # DESTRUCTIVE: back up the EC2 DB, then restore the snapshot into it
#   ./deploy/ec2/deploy.sh up        # = pull + deploy (a code-only redeploy; no DB change)
#   ./deploy/ec2/deploy.sh verify    # health checks (container health + public URL)
set -euo pipefail
PEM="${PEM:-$HOME/Downloads/airos-ec2-product-dev-3.pem}"
HOST="ec2-user@13.205.13.220"
SSH="ssh -i $PEM -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=8"
SCP="scp -i $PEM -o StrictHostKeyChecking=no -o ServerAliveInterval=15"
REMOTE="/home/ec2-user/airawatos"          # the LIVE compose project dir (services: kernel/network/app-host/…)
HERE="$(cd "$(dirname "$0")" && pwd)"
PGC="airawat-postgres"                      # the registry postgres container (db `kernel`, user `kernel`)
# the services built from our 3 images (kernel/network/reference) — never postgres/vault/nginx
SVCS="network identity kernel app-host automation decision event-relay filestore secrets scheduler model-gateway notify runtime-manager workflow"

case "${1:-}" in
  dump)
    mkdir -p "$HERE/seed"
    echo ">> dumping local $PGC:kernel → seed/kernel.sql.gz (clean/idempotent)…"
    docker exec "$PGC" pg_dump -U kernel -d kernel --clean --if-exists --no-owner --no-acl | gzip > "$HERE/seed/kernel.sql.gz"
    gzip -t "$HERE/seed/kernel.sql.gz" && echo ">> ok: $(du -h "$HERE/seed/kernel.sql.gz" | cut -f1)"
    ;;
  copy)
    [ -f "$HERE/seed/kernel.sql.gz" ] || { echo "no seed/kernel.sql.gz — run './deploy.sh dump' first"; exit 1; }
    $SSH "$HOST" "mkdir -p $REMOTE/seed"
    $SCP "$HERE/docker-compose.yml" "$HERE/nginx.conf" "$HOST:$REMOTE/"
    echo ">> uploading DB snapshot (foreground — a backgrounded scp gets SIGPIPE)…"
    $SCP "$HERE/seed/kernel.sql.gz" "$HOST:$REMOTE/seed/kernel.sql.gz"
    echo ">> copied compose + nginx + snapshot → $HOST:$REMOTE"
    ;;
  pull)
    $SSH "$HOST" "for i in kernel network reference; do docker pull -q manishsv/airawatos-\$i:0.1.0; done; echo 'pulled kernel network reference :0.1.0'"
    ;;
  deploy)
    # recreate ONLY our services on the freshly-pulled images. --no-deps => never touches postgres or a broken sibling.
    $SSH "$HOST" "cd $REMOTE && docker compose up -d --no-deps --force-recreate $SVCS"
    echo ">> recreated app services on the new images (DB untouched)"
    ;;
  restore)
    # DESTRUCTIVE — replaces the EC2 registry DB with the uploaded snapshot. Always backs up first.
    $SSH "$HOST" "set -e; cd $REMOTE
      [ -f seed/kernel.sql.gz ] || { echo 'no seed/kernel.sql.gz on EC2 — run copy first'; exit 1; }
      echo '>> backing up current EC2 DB → ~/kernel-backup-predeploy.sql.gz'
      docker exec $PGC pg_dump -U kernel -d kernel --clean --if-exists --no-owner --no-acl 2>/dev/null | gzip > ~/kernel-backup-predeploy.sql.gz
      echo '>> stopping kernel + dropping connections'
      docker stop airawat-kernel >/dev/null 2>&1 || true
      docker exec $PGC psql -U kernel -d postgres -tc \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='kernel' AND pid<>pg_backend_pid();\" >/dev/null 2>&1 || true
      echo '>> restoring snapshot'
      gunzip -c seed/kernel.sql.gz | docker exec -i $PGC psql -U kernel -d kernel -v ON_ERROR_STOP=0 >/tmp/restore.log 2>&1
      echo \"   restore errors: \$(grep -c '^ERROR' /tmp/restore.log || echo 0)\"
      docker start airawat-kernel >/dev/null 2>&1 || true"
    echo ">> restore done — run './deploy.sh deploy' to bring services onto new code, then 'verify'"
    ;;
  up)
    "$0" pull
    "$0" deploy
    ;;
  verify)
    $SSH "$HOST" 'echo "== unhealthy/restarting airawat containers (none = good) =="; docker ps --format "{{.Names}}: {{.Status}}" | grep "airawat-" | grep -vE "healthy|Up [0-9]" || echo "  all healthy"
      echo "== kernel/network internal health (ports are NOT host-published) =="; docker logs airawat-kernel 2>&1 | grep -c "GET /v1/health HTTP/1.1\" 200" | xargs echo "  kernel 200-health hits:"; docker inspect airawat-kernel -f "  kernel health={{if .State.Health}}{{.State.Health.Status}}{{end}}"
      echo "== app-host certified apps =="; docker logs airawat-app-host 2>&1 | grep -oiE "serving [0-9]+ certified" | tail -1'
    echo "== public =="; curl -s -o /dev/null -w "  https://airos.airawat.org/login → %{http_code}\n" https://airos.airawat.org/login
    ;;
  *) echo "usage: $0 {dump|copy|pull|deploy|restore|up|verify}"; exit 1 ;;
esac

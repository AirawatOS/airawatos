#!/usr/bin/env bash
# Deploy AirawatOS to the EC2 demo box. Assumes images are already pushed (build-push.sh) and
# `docker login` done. Runs in explicit phases so the destructive teardown is never accidental.
#   ./deploy/ec2/deploy.sh copy      # scp compose+nginx+seed to EC2
#   ./deploy/ec2/deploy.sh teardown  # DESTRUCTIVE: stop+remove the AirOS/DIGIT stack (frees :80/:443)
#   ./deploy/ec2/deploy.sh up        # postgres → restore registry dump → bring up the full stack
#   ./deploy/ec2/deploy.sh verify    # health checks
set -euo pipefail
PEM="${PEM:-$HOME/Downloads/airos-ec2-product-dev-3.pem}"
HOST="ec2-user@13.205.13.220"
SSH="ssh -i $PEM -o StrictHostKeyChecking=no"
REMOTE="/home/ec2-user/airawatos"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "${1:-}" in
  copy)
    $SSH "$HOST" "mkdir -p $REMOTE/seed"
    scp -i "$PEM" "$HERE/docker-compose.yml" "$HERE/nginx.conf" "$HOST:$REMOTE/"
    scp -i "$PEM" "$HERE/seed/kernel.sql" "$HOST:$REMOTE/seed/"
    echo "copied compose + nginx + seed → $HOST:$REMOTE"
    ;;
  teardown)
    # DESTRUCTIVE — stop+remove the AirOS/DIGIT/Kong stack + the old airawat-* stack. Leaves jenkins.
    $SSH "$HOST" 'docker ps -a --format "{{.Names}}" | grep -E "^(airos-|kong|individual|notification|workflow-service|account|boundary-service|filestore|idgen|minio|redis|postgres|keycloak|airawat-)" | grep -vE "jenkins" | xargs -r docker rm -f; echo "removed. remaining:"; docker ps --format "{{.Names}}"'
    ;;
  up)
    $SSH "$HOST" "cd $REMOTE && docker compose pull"
    # bring up ONLY postgres first, restore the registry dump into an empty db, THEN the rest
    $SSH "$HOST" "cd $REMOTE && docker compose up -d postgres && sleep 8 && \
      docker exec -i airawat-postgres psql -U kernel -d kernel < seed/kernel.sql >/dev/null 2>&1 && echo 'registry restored' && \
      docker compose up -d"
    ;;
  verify)
    $SSH "$HOST" 'echo "containers:"; docker ps --format "{{.Names}} {{.Status}}" | grep airawat; \
      echo "kernel:"; curl -s localhost:8080/v1/health 2>/dev/null; echo; \
      echo "network:"; curl -s localhost:8090/v1/health 2>/dev/null; echo; \
      echo "app-host via nginx:"; curl -s -o /dev/null -w "%{http_code}\n" localhost/login'
    ;;
  *) echo "usage: $0 {copy|teardown|up|verify}"; exit 1 ;;
esac

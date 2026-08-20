#!/usr/bin/env bash
# Build the three AirawatOS images multi-arch (amd64 for EC2 + arm64 for local) and push to DockerHub.
# Prereq: `docker login` already done (org: manishsv). Run from anywhere.
#   ./deploy/ec2/build-push.sh [TAG]
set -euo pipefail
ORG=manishsv
TAG="${1:-0.1.0}"
PLATFORMS="linux/amd64,linux/arm64"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

docker buildx create --name airawatx --use >/dev/null 2>&1 || docker buildx use airawatx
docker buildx inspect --bootstrap >/dev/null

echo ">> kernel  → $ORG/airawatos-kernel:$TAG"
docker buildx build --platform "$PLATFORMS" -t "$ORG/airawatos-kernel:$TAG" \
  -f kernel/deploy/Dockerfile kernel --push

echo ">> network → $ORG/airawatos-network:$TAG"
docker buildx build --platform "$PLATFORMS" -t "$ORG/airawatos-network:$TAG" \
  -f network/deploy/Dockerfile network --push

echo ">> reference (11 services, one image) → $ORG/airawatos-reference:$TAG"
docker buildx build --platform "$PLATFORMS" -t "$ORG/airawatos-reference:$TAG" \
  -f deploy/ec2/Dockerfile.reference . --push

echo ">> done. Pushed: $ORG/airawatos-{kernel,network,reference}:$TAG"

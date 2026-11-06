#!/usr/bin/env bash
# AirawatOS local-dev bootstrap — now a thin wrapper over the unified installer (docs/operator/INSTALLER.md).
# `bootstrap-dev.sh` == `install.sh --profile dev` + the dev-only extras (platform test users; opt-in perf seed
# via INSTALL_PERF_SEED=1). Run AFTER `docker compose -f docker-compose.dev.yml up -d`.
#
#   cd deploy/local-dev && ./bootstrap-dev.sh
#
# For production / rehearsal installs, call the installer directly: ./install.sh --profile production
set -euo pipefail
exec "$(dirname "$0")/install.sh" --profile dev "$@"

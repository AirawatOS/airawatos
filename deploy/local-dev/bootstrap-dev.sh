#!/usr/bin/env bash
# AirawatOS local-dev bootstrap — thin wrapper over the unified installer (docs/operator/INSTALLER.md).
# `bootstrap-dev.sh` == `deploy/installer/install.sh --profile dev` + the dev-only extras (platform test users;
# opt-in perf seed via INSTALL_PERF_SEED=1). Run AFTER `docker compose -f docker-compose.dev.yml up -d`.
#
#   cd deploy/local-dev && ./bootstrap-dev.sh
#
# For production / rehearsal installs, call the installer directly: deploy/installer/install.sh --profile production
set -euo pipefail
exec "$(cd "$(dirname "$0")/../installer" && pwd)/install.sh" --profile dev "$@"

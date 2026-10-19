# Thin "bake-exactly-running" overlay: the live network image + the dev-tenant provisioning self-heal.
# Base = the EXACT image the EC2 network is running (0.3.5-zoho-keyprefix), so this adds ONLY
# ensure_dev_tenant.py + the gated boot hook — no source drift, no bundled main-upgrade (that is task #277).
# Build (on EC2, where the base image already exists), from a dir containing ensure_dev_tenant.py:
#   docker build -f network-dev-tenant-overlay.Dockerfile -t manishsv/airawatos-network:0.3.5-dev-tenant-ensure .
# The equivalent change is ALSO baked into network/deploy/Dockerfile for the next from-source build.
FROM manishsv/airawatos-network:0.3.5-zoho-keyprefix
COPY ensure_dev_tenant.py /app/ensure_dev_tenant.py
# Default OFF (ENSURE_DEV_TENANT unset) => byte-identical behavior to the base image's `uvicorn api:app`.
# Set ENSURE_DEV_TENANT=1 to self-heal the developer sandbox tenant to environment=development on boot.
CMD ["sh", "-c", "if [ \"$ENSURE_DEV_TENANT\" = \"1\" ]; then python ensure_dev_tenant.py || echo '[ensure-dev-tenant] non-fatal: skipped'; fi; exec uvicorn api:app --host 0.0.0.0 --port 8090"]

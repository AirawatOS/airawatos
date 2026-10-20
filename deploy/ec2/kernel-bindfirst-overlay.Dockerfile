# Thin "bake-exactly-running" overlay: the live kernel image + the bind-first boot fix only.
# Base = the EXACT image the EC2 kernel runs (0.2.10-datasets), so this adds ONLY the patched
# services/registry/pg_store.py (split _DDL → synchronous core + background index/B1 maintenance) — no drift.
# The equivalent change is in the kernel repo source too (kernel/services/registry/pg_store.py).
# Build (on EC2, where the base image exists), from a dir containing the patched pg_store.py:
#   docker build -f kernel-bindfirst-overlay.Dockerfile -t manishsv/airawatos-kernel:0.2.11-bindfirst .
FROM manishsv/airawatos-kernel:0.2.10-datasets
COPY pg_store.py /app/services/registry/pg_store.py

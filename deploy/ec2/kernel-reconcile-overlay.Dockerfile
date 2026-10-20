# Thin overlay: bind-first kernel + the dataset-index reconcile (api/app.py).
# Base already carries the bind-first pg_store.py (0.2.11-bindfirst); this adds ONLY the reconcile app.py.
# Build on EC2 from a dir containing the patched app.py:
#   docker build -f kernel-reconcile-overlay.Dockerfile -t manishsv/airawatos-kernel:0.2.12-reconcile .
FROM manishsv/airawatos-kernel:0.2.11-bindfirst
COPY app.py /app/api/app.py

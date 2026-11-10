# DEV-ONLY stub model provider (the model gateway's south-side contract) — its OWN image, never part of a shipped
# image; only the local-dev stack runs it. Refuses to start under AIRAWAT_ENV=production (stub_provider.py).
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.source="https://github.com/AirawatOS/airawatos" org.opencontainers.image.revision="${GIT_SHA}" org.opencontainers.image.base.name="python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535" org.airawat.dev-only="true"
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pip==26.3 setuptools==84.2.1 wheel==0.48.0
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY stub_provider.py .
USER 65534:65534
ENV PYTHONUNBUFFERED=1
EXPOSE 8110
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8110/healthz').status==200 else 1)"
CMD ["python", "stub_provider.py"]

# perf/ — load harness (Consolidation phase 4)

A latency/throughput harness, **separate from conformance**, that measures each budgeted operation against the
local-dev stack and reports it against the budget in `../docs/performance/PERFORMANCE-BUDGETS.md`.

**Measurement only — no service-code dependency.** `run.py` uses only the stdlib plus, when run inside the
app-host container, the reference `svc_token`/`hostcore` helpers to mint the audience-bound tokens the gated
endpoints need.

## Run

It must reach every service on the compose network and read Vault, so run it **inside the app-host container**:

```
docker cp perf/run.py airawat-ld-app-host:/tmp/perf_run.py
docker exec airawat-ld-app-host python3 /tmp/perf_run.py
# more iterations:
docker exec -e N=200 airawat-ld-app-host python3 /tmp/perf_run.py
```

(Equivalently, a throwaway container on `airawatos-localdev_default` with `-v $PWD/perf:/perf`, the reference
image, `--env-file deploy/local-dev/.env`, `VAULT_ADDR`, and `PYTHONPATH=/app/reference`.)

Output: a table of `p50 / p95 / budget-p95 / PASS|FAIL|BLOCKED` per operation. **BLOCKED** = the bedrock stack
cannot exercise it (no governed schema / endpoint / built feature); the harness never fakes a number.

## Results are INDICATIVE

Single arm64 laptop, all services + Postgres + Vault in one Docker engine, no network latency, no concurrency,
a near-empty registry. The **shapes** (what fails its budget and why) are the signal; the **absolute numbers
are a loose lower bound**, not production SLOs. Re-run against a representative corpus and a production-shaped
deployment before treating any number as an SLO. Latest run + findings: see the budgets doc.

## What it measures

login · service-token mint · authorization decision (cached + uncached proxy) · Kernel record write / read-by-id
/ query / point-in-time · audit-chain verify per 10k · consent check for a personal read (D10) · scheduler
dispatch · automation event handling · file upload/download (1 MB). Budgets live in
`../docs/performance/PERFORMANCE-BUDGETS.md` (the harness mirrors the p95 gate).

## Seeding a realistic corpus

Near-empty reads are a floor, not a measurement. Seed a synthetic, **non-personal, dev-only** corpus first:

```
python3 perf/seed.py --confirm-dev            # ~1M registry_version rows + a point-in-time fixture; idempotent
```

~1,000,260 rows across 5 `perf.*` schemas × 3 synthetic tenants × ~16.7k ids × 4 versions, plus a small
`perf.pit` fixture (owned by `localdev-network`) so the owner-gated history endpoint is measurable. It refuses
without `--confirm-dev` (or `SEED_CONFIRM=1`) and under `AIRAWAT_ENV=production`, writes only `perf.*`/`perfcity-*`,
and prints the one-line DELETE to remove it. Re-running is a no-op once present. **Never run against production.**

## Concurrency pass

`run.py` also fires the core read-path ops under parallel clients and reports p50/p95 + throughput per level:

```
docker exec -e CONC_LEVELS=10,50,100 -e CONC_REQS=300 airawat-ld-app-host python3 /tmp/perf_run.py
```

## Audit-chain verify (out-of-band)

Not an HTTP op — measured by the Kernel's read-only verifier, which recomputes every row's `content_hash`:

```
docker exec airawat-ld-kernel python3 /app/tools/audit_verify.py        # whole table; exit 2 = a hash break
```

See `kernel/tools/audit_verify.py` and OPERATOR-GUIDE §4 (scheduled integrity check).

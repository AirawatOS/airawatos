# Performance budgets (v0.1 proposal)

**Date:** 2026-11-05 · **Scope:** per-operation latency (p50/p95) and throughput targets for the AirawatOS
reference stack. **Measurement only** — these are proposed budgets plus a harness (`../../perf/`) that reports
today's local-dev numbers against them. No feature or service-code changes.

> **Local-dev numbers are INDICATIVE, not production.** The harness runs on a single arm64 laptop with all
> services + Postgres + Vault co-located in one Docker engine, no network latency, no horizontal scaling, and
> a near-empty registry. Treat the shapes (what's fast, what's slow, what fails its budget and why) as the
> signal; treat the absolute numbers as a loose lower bound, not a production SLO.

## Load assumptions (a city deployment)

- **City scale:** one city tenant, ~1–5 M residents. Civic staff: a few hundred concurrent authenticated
  sessions at peak; citizen self-serve: low-thousands of requests/minute at peak, bursty around announcements.
- **Topology:** a single-node reference stack (kernel + network + identity + the reference services + one
  Postgres + Vault) is the unit being budgeted. Production scales the read tier horizontally (ADR-0105); these
  budgets are for **one** node so the per-op cost is visible, not hidden behind replicas.
- **Authorization on every governed op:** each record read/write carries an authorization decision; the role
  read is cached (short TTL) so steady-state is the cached path, with the uncached path paid on cache miss /
  after a grant change.
- **Registry size:** budgets assume a working set of ~10⁷ records in the tenant with the live-schema index
  (`rv_live_schema_id`) present; queries are index-bounded, not cold DISTINCT scans.
- **Steady vs peak:** p50 = steady-state median; p95 = peak-ish tail a user still waits through. Throughput =
  sustained single-node req/s for that op alone.

## Budgets

| Operation | p50 (ms) | p95 (ms) | Throughput (/s, 1 node) | Notes |
|---|---:|---:|---:|---|
| **Login** (password → signed token) | 150 | 400 | 50 | password hash (argon/bcrypt) dominates; deliberately not cheap |
| **Service-token mint** (Vault read + /login, audience-bound) | 60 | 150 | 200 | first mint; cached + re-minted ~1 min before expiry → ~1 ms warm |
| **Authorization decision — role read UNCACHED** | 20 | 60 | 300 | kernel reads the recorded grant from Postgres |
| **Authorization decision — role read CACHED** | 2 | 8 | 2000 | steady state; cache invalidated on grant change |
| **Kernel record WRITE** (validate + bitemporal insert + provenance) | 25 | 80 | 400 | schema validate + signed write + audit |
| **Kernel read by ID** | 8 | 25 | 1500 | single-key, live version |
| **Kernel QUERY** (schema-filtered, index-bounded) | 40 | 150 | 200 | `rv_live_schema_id` pushdown; not a cold scan |
| **Kernel point-in-time (as-of) lookup** | 20 | 80 | 400 | bitemporal version-at-time |
| **Audit-chain verification / 10k events** | 300 | 800 | — | hash-chain recompute over 10k; batch/offline, not hot path |
| **Consent check — personal read (+ DECISION D10 full record)** | 30 | 90 | 500 | cached consent + a full decision record written |
| **Scheduler dispatch** (enqueue/trigger one run; excludes the run) | 30 | 100 | 300 | the gate + enqueue only; the component run is unbounded |
| **Automation event handling** (accept + route one event) | 20 | 80 | 500 | ingress gate + route; downstream effects separate |
| **File upload — 1 MB (current filestore)** | 40 | 150 | 60 MB/s | content-address + write-once |
| **File download — 1 MB (current filestore)** | 20 | 80 | 100 MB/s | immutable, cacheable |

### Kernel-mediated files — future budget (design, not built)

When files become Kernel-mediated records ([[../consolidation/KERNEL-MEDIATED-FILES-DESIGN]]), the budget
shifts: every file op first pays an **authorization decision** (cached ~+2–8 ms, uncached ~+20–60 ms) and, for
**large** files, the Kernel issues a **short-lived signed link** so the bytes bypass the Kernel body. Proposed:
small-file (≤1 MB) read p95 **120 ms** (auth + inline), large-file read = **auth decision p95 ≤ 90 ms + a
rail/store transfer the Kernel does not proxy**; write similar. The point: the Kernel decision is the budgeted
part; the byte transfer is not on the Kernel's critical path for large objects.

## How measured

`perf/run.py` times each operation over N iterations (default 50; audit-chain fewer) inside the local-dev
compose network, computes p50/p95, and compares to the budget here. See `perf/README.md`. Operations that the
bedrock stack cannot exercise (no governed schema to write, consent-enforcement not built, no audit-verify
endpoint) are reported **BLOCKED** with the reason, not faked.

---

## Run — 2026-11-05 (local-dev, INDICATIVE: arm64 laptop, co-located services, near-empty registry, N=50)

| Operation | p50 (ms) | p95 (ms) | budget p95 | result |
|---|---:|---:|---:|---|
| login | 18.7 | 23.9 | 400 | PASS |
| service-token mint | 20.4 | 33.6 | 150 | PASS |
| authz decision — cached | 1.6 | 2.3 | 8 | PASS |
| authz decision — uncached (proxy) | 2.5 | 3.0 | 60 | PASS |
| Kernel record write | 7.7 | 11.9 | 80 | PASS |
| read by ID | 2.8 | 4.7 | 25 | PASS |
| query | 2.0 | 5.6 | 150 | PASS |
| point-in-time | — | — | 80 | **BLOCKED** |
| audit-chain verify / 10k | — | — | 800 | **BLOCKED** |
| consent personal read (D10) | — | — | 90 | **BLOCKED** |
| scheduler dispatch | 2.4 | 53.6 | 100 | PASS |
| automation event handling | 0.4 | 0.9 | 80 | PASS |
| file upload 1 MB | 0.9 | 4.0 | 150 | PASS |
| file download 1 MB | 1.9 | 3.1 | 80 | PASS |

**11 PASS · 0 FAIL · 3 BLOCKED.**

### BLOCKED (cause)
- **point-in-time** — the only black-box as-of surface, `GET /v1/registry/objects/{id}/history`, is
  owner/admin-gated and returned **403** for the component-publisher principal on a record it does not own; a
  plain as-of lookup for an arbitrary id is not exposed unauthenticated. Needs a seeded owned record (or an
  as-of param on `resolve`) to measure.
- **audit-chain verify / 10k** — no audit-chain verification endpoint exists; not black-box measurable
  (budget stated for when it does).
- **consent personal read (D10)** — consent enforcement + the personal-read full-decision-record path are
  not built (ADR-0125/0127 PLANNED).

### Findings (shape, not production numbers)
1. **Login is suspiciously fast (p95 24 ms vs a 400 ms budget).** The budget assumed a deliberately-expensive
   password hash (argon2/bcrypt). 24 ms on this hardware suggests the reference IdP uses a **cheap hash** —
   a **security** finding (brute-force resistance), not a performance one. Worth confirming the KDF/work
   factor before production.
2. **Cached ≈ uncached authz (2.3 vs 3.0 ms).** The uncached-vs-cached gap the budget anticipates does not
   appear because the **registry/role store is near-empty** — the uncached role read is cheap here. The
   cache's value only shows against a populated store; re-measure at scale.
3. **Read/query/write/point-in-time numbers are not representative.** The registry holds a handful of records,
   so reads and queries are a **floor**, not the budgeted 10⁷-record working set. Re-run after seeding a
   realistic corpus (and with the `rv_live_schema_id` index exercised) before treating any read/query number
   as meaningful.
4. **scheduler dispatch tail (p95 53.6 vs p50 2.4).** `/reload` occasionally re-reads schedules from the
   registry; the tail is the cold re-read, still inside budget.
5. Everything else is far under budget on this hardware — expected, since there is no network latency, no
   concurrency, and almost no data. **These are a loose lower bound, not an SLO.**

---

## Run — 2026-11-05 (local-dev, SEEDED ~1M records + concurrency; INDICATIVE: arm64 laptop, co-located, N=50)

Seeded a synthetic, non-personal corpus with `perf/seed.py`: **999,960** `registry_version` rows across 5
`perf.*` schemas × 3 synthetic tenants × ~16.7k ids × 4 versions, **plus 300** point-in-time fixture rows
(`perf.pit` @ `localdev-network`, 50 ids × 6 versions) a harness principal owns — so point-in-time and the
seeded read/query paths are now exercised against a ~1M-row table (the `rv_live_schema_id` index present). The
corpus is dev-only and idempotent (re-run = no-op); remove with the one-line DELETE the seeder prints.

### Single-client (p95 gate)

| Operation | p50 (ms) | p95 (ms) | budget p95 | result |
|---|---:|---:|---:|---|
| login | 18.5 | 20.3 | 400 | PASS |
| service-token mint | 19.1 | 21.0 | 150 | PASS |
| authz decision — cached | 1.4 | 1.7 | 8 | PASS |
| authz decision — uncached (proxy) | 2.1 | 4.4 | 60 | PASS |
| Kernel record write | 6.3 | 34.8 | 80 | PASS |
| **read by ID — `filter:{id}` (no schema)** | **1722.4** | **2065.2** | 25 | **FAIL** |
| query (schema-filtered, `perf.pit`) | 2.8 | 5.5 | 150 | PASS |
| point-in-time (history, `perf.pit` id, 6 versions) | 1.7 | 3.2 | 80 | PASS |
| audit-chain verify / 10k | 251 (tool) | — | 800 | **PASS (tool)** |
| consent personal read (D10) | — | — | 90 | **BLOCKED** |
| scheduler dispatch | 2.2 | 3.4 | 100 | PASS |
| automation event handling | 0.4 | 0.7 | 80 | PASS |
| file upload 1 MB | 0.8 | 1.4 | 150 | PASS |
| file download 1 MB | 0.9 | 1.9 | 80 | PASS |

**11 PASS · 1 FAIL (read_by_id) · 1 PASS-via-tool (audit) · 1 BLOCKED (consent).** point-in-time is now
**unblocked and PASS** (was BLOCKED near-empty: no owned record with history).

### Concurrency (10 / 50 / 100 parallel clients; 300 requests per op·level)

| Operation | clients | p50 (ms) | p95 (ms) | throughput (/s) | ok | bad |
|---|---:|---:|---:|---:|---:|---:|
| authz_cached | 10 | 162 | 292 | 60 | 300 | 0 |
| authz_cached | 50 | 841 | 1488 | 37 | 208 | 92 |
| authz_cached | 100 | 1608 | 1802 | 45 | 212 | 88 |
| read_by_id (`filter:{id}`) | 10 | 5377 | 9655 | 2 | 300 | 0 |
| read_by_id (`filter:{id}`) | 50 | 15373 | 16422 | 1 | 24 | 276 |
| read_by_id (`filter:{id}`) | 100 | 15091 | 16038 | 1 | 24 | 276 |
| query | 10 | 175 | 464 | 49 | 300 | 0 |
| query | 50 | 768 | 1370 | 42 | 206 | 94 |
| query | 100 | 1768 | 2353 | 40 | 216 | 84 |
| point_in_time | 10 | 179 | 333 | 52 | 300 | 0 |
| point_in_time | 50 | 971 | 1639 | 39 | 215 | 85 |
| point_in_time | 100 | 2049 | 2854 | 37 | 230 | 70 |

### Findings (seeded volume + concurrency)

1. **FAIL — resolve-by-id via `filter:{id}` (no schema) seq-scans the whole table.** p95 **2065 ms** at 1 M
   rows (was 4.7 ms near-empty). `EXPLAIN` confirms a **parallel sequential scan** filtering on the
   **unindexed** `object #>> '{id}'`, removing ~333k rows/worker. The resolver's fast path
   (`id = <col>`, index `rv_one_open`) is reached only when the caller passes a dedicated `id_` or **includes
   a `schema`** in the filter; a lone `{"filter":{"id":…}}` falls through to the general JSONB-filter path. The
   **indexed single-key read is fine** — point-in-time/history (which calls `resolve_as_of(id_=…)` → `id =`)
   is **3.2 ms p95 live**, and the raw `id =` query is 4.7 ms by `EXPLAIN`. So this is a **query-routing gap,
   not a storage limit**: either map a lone-`id` filter to the indexed `id` column, add an expression index on
   `object #>> '{id}'`, or require callers to pass `id_`/`schema`. **Reported, not fixed** (measurement-only
   slice; a fix is a separate Kernel code slice). This is the headline value of seeding — invisible at
   near-empty, show-stopping at city scale.
2. **Audit-chain verify now MEASURED (not BLOCKED): ~251 ms per 10k rows** (≈40k rows/s), whole 1M-row table
   in ~25 s, 0 breaks — well inside the 800 ms/10k budget. Measured by the new read-only tool
   `kernel/tools/audit_verify.py` (not an HTTP op; see OPERATOR-GUIDE §4). Tamper-detection verified: a row
   whose bytes were altered without updating its hash is caught (exit 2), and exact restore re-verifies (exit
   0).
3. **Concurrency: graceful-ish degradation + connection-pool saturation.** authz/query/point-in-time hold
   ~40–60 req/s single-node and their p95 grows with clients as expected; past ~pool size (`PG_POOL_MAX=24`)
   the `bad` column climbs (requests time out / are refused) — the tail is pool contention, the signal the
   budget's "one node" assumption anticipates. **read_by_id collapses hardest** (276/300 fail at 50 clients)
   because each request is the ~1.7 s seq scan from finding 1, holding a pool connection for seconds — a direct
   amplification of the routing gap, not an independent issue. Fix finding 1 and this row should rejoin the
   others.
4. **Query/point-in-time stayed fast at 1 M rows** (2.8 / 1.7 ms p50) — the `rv_live_schema_id` partial index
   and the `id =` fast path do their job; the budgeted index-bounded behaviour holds at volume. The earlier
   "reads are a floor, re-measure at scale" caveat is now discharged for these two.
5. **Login/KDF unchanged** (p95 20 ms) — still the KDF-strength security finding, now written up in
   `IDENTITY-KDF-REPORT.md` (PBKDF2-SHA256 @ 200k < ~600k guidance; recommend ≥600k or Argon2id + durable
   lockout counters). Not a perf issue.

**Still laptop-indicative.** Absolute numbers remain a loose bound (co-located services, no network latency,
one Docker engine, one Postgres, `PG_POOL_MAX=24`). What transfers to production is the **shape**: finding 1
(a seq-scan routing bug that only appears with data) and the pool-saturation tail. Re-run on a
production-shaped deployment (horizontal read tier per ADR-0105, tuned pool, real network) before any number
here is treated as an SLO.

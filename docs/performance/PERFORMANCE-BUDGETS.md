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

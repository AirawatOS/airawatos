# ADR-0154 — Data stores by workload: Postgres for records of record, the right tool for each other kind of data

**Status:** Proposed
**Date:** 2026-11-28 (amended the same day after stage 1 on staging)
**Related:** REGISTRY-v0.1 (the single-table bitemporal registry), the registry reviews of 2026-08 and 2026-09 (P4
bitemporal indexes, P5/P6 retention, compaction and partitioning — still open), ADR-0079 (metering), ADR-0136 and
ADR-0139 (organisations' own records), ADR-0142 (quality of life: compute and publish), ADR-0153 (Settings → Storage).

## The problem

Every governed record of every organisation is a version row in one Postgres table, `registry_version`: a text id
(`ds:<organisation>:<path>`), a JSONB object, and the bitemporal columns. On the staging instance on 2026-11-28:

| Measure | Value |
|---|---|
| Rows (versions) | 10.7 million |
| Table size | 59 GB (65 GB with indexes) |
| One organisation (Janaagraha) | 4.8 million versions, 3.8 GB of record content |
| Largest record type | `air.quality` — 3.16 million current hourly readings |
| Next | `geo.osm_feature`, `geo.building` (map features), `city.cell_profile`, `cell.*` (grid-cell feeds) |
| Postgres | stock `postgres:16-alpine`: no PostGIS, no TimescaleDB, no connection pooler; `pg_stat_statements` available but not enabled |

What went wrong that day:

1. **One organisation's sensor feed slows everyone.** Cases, role grants and certificates share a table — and its
   caches and I/O — with millions of hourly readings.
2. **Readings are stored as governed records.** Each reading carries the full machinery of a record: identity,
   versions, transaction time and a JSON body. That machinery exists for cases, certificates and decisions, which are
   corrected, superseded and audited. A reading is appended once and only ever summarised.
3. **The id hides what queries need.** Organisation and record type are inside a text id. Under the database's
   `en_US` collation a "starts with `ds:janaagraha:`" filter cannot use the id index, so each per-organisation
   question scans the whole table. The Settings → Storage report timed out at the gateway (504) for this reason; it is
   now counted in the background once a day (kernel patches K1 and K1b, PQ-140) — about 7 minutes of heavy reading.
4. **Totals are computed by scanning.** Storage, Service Intelligence and counts read rows instead of keeping running
   totals.
5. **Nothing stops one query from hurting all.** 24 connections with no pooler: under heavy reads the kernel refused
   requests ("connection pool exhausted" — hundreds a minute, with and without the storage count). A 14-minute
   unfiltered read of every current record, left by a restarted kernel, blocked the next kernel's start-up DDL for
   three minutes.

None of these is a limit of Postgres. Each comes from putting every workload in one table and one shape.

## Decision

1. **Postgres stays the store for records of record.** Governed records — cases, tasks, credentials, role grants,
   services, decisions, payments, listings — need multi-statement transactions, the one-open-version invariant,
   bitemporal history, JSONB with indexes and tenant isolation. Postgres does all of these and is open, well understood
   and runs in any state data centre or cloud. No change of database.

2. **The organisation and the record type are columns.** `registry_version` gains `tenant` and `schema` columns
   (written by the kernel from the id and the object, backfilled once), indexed as `(tenant, schema, id)` with the
   current-version predicate. Per-organisation and per-type queries use them, never a `LIKE` on the id. Where an id
   prefix is still needed, the index uses a byte-order collation (`COLLATE "C"` or `text_pattern_ops`).

3. **The registry is partitioned.** `registry_version` is list-partitioned by record-type family, so a heavy family
   (sensor readings, map features, grid-cell feeds, events) has its own partition, caches and maintenance; partitions
   above a size threshold are sub-partitioned by transaction month (the reviews' P5/P6). Records of record stay
   together in a general partition.

4. **Time series live in a time-series store, not as governed records.** Readings that are appended, never corrected,
   and only summarised (`air.quality`, weather, grid-cell feeds, metering) go to a **TimescaleDB hypertable** — a
   Postgres extension, the same database and the same backups — with compression and retention per type. What the
   platform governs is the **dataset** (its type, source, licence and retention), and the **derived facts** that
   people act on: an alert, a ward's daily index, a published summary (ADR-0142). Queries ask for ranges and
   aggregates, which a hypertable answers directly.

5. **Places are geometry.** Map features, buildings, wards and cells keep their governed record, and their shape is
   held in a **PostGIS** geometry column with a spatial index, so "what is within this ward" is an index lookup, not a
   scan of JSON.

6. **Analytics read a copy, never the live table.** Service Intelligence, quality-of-life computation, storage and
   usage reports read either a **read replica**, or **columnar extracts** (Parquet) queried with **DuckDB** — the
   archive already writes compressed JSON lines to the file store, so extracts sit beside it. A heavy question never
   competes with the work of the day.

7. **Totals are kept, not counted.** Counts that screens show — per organisation, per type, per service, per role's
   open tasks — are maintained as the kernel writes (a small summary table updated in the same transaction, or a
   continuous aggregate for time series). The storage report reads Postgres' own size statistics plus these counts.

8. **Guard rails for a shared database.** A connection pooler (PgBouncer) in front of Postgres; statement timeouts
   per kind of call (interactive reads short, background jobs explicit); `lock_timeout` on every DDL, so start-up and
   migrations fail fast instead of hanging behind a long read; `pg_stat_statements` on, with slow queries reported in
   Settings → Usage; unfiltered whole-registry reads refused by the kernel (a filter on organisation or type required).

9. **Search, when needed.** Listing search (jobs, services, components) uses Postgres full-text search on the listing
   cache; a separate search engine only if that proves insufficient.

## Amendment (2026-11-28): what stage 1 on staging found

- **The pool that ran out was the kernel's own.** Postgres allows 100 connections and about 12 were in use; the
  kernel's pool allowed 24. A pooler in front of Postgres does not help a single kernel process, so stage 1 raises the
  kernel's pool to 48 and adds time limits; **PgBouncer comes when the kernel runs several workers or replicas.**
- **Every kernel start blocked writes for about 9 minutes.** The start-up index maintenance ran as one batch — one
  transaction — whose first `CREATE INDEX IF NOT EXISTS` took a write-blocking lock even when the index existed, and held
  it through a repair scan of every current version (545 s on staging). Writes queued behind it, holding connections:
  the "connection pool exhausted" bursts. The start-up `ALTER TABLE … ADD COLUMN IF NOT EXISTS` likewise took the
  strictest lock on every start. Both now run only when something is missing, each statement on its own and indexes
  built concurrently (kernel patches K2, K2b). Decision 8 therefore adds: **schema maintenance never runs as one batch
  on an established table, and runs only when needed.**
- **Unfiltered whole-registry reads are logged with their caller** rather than refused, until the callers are known;
  the statement time limit stops them running away.

## Build, in order

| Stage | What | Removes |
|---|---|---|
| 1 | Time limits per connection; fail-fast, only-when-needed start-up DDL and maintenance; kernel pool sized to Postgres; `pg_stat_statements`; unfiltered reads logged, then refused; a pooler once there are several kernel workers | pool exhaustion, hung restarts, writes blocked at every start |
| 2 | `tenant` and `schema` columns + index; kernel queries use them; storage report from size statistics + kept counts | full scans per organisation; the 7-minute count |
| 3 | Kept totals (summary table) for counts shown on screens | scans behind dashboards |
| 4 | TimescaleDB: move `air.quality`, weather, `cell.*` feeds and metering to hypertables; governed datasets + derived facts stay in the registry | most of the table's size and churn |
| 5 | PostGIS geometry for map features, buildings, wards, cells | JSON scans for spatial questions |
| 6 | Partition the registry by record-type family | the remaining cross-workload interference |
| 7 | Analytics on a replica or Parquet + DuckDB | dashboards competing with the day's work |

Stages 1–3 need no new software beyond the pooler and change no record. Stage 4 changes how sensor data is read
(apps use a time-series query instead of the registry) and needs the TimescaleDB image; stage 5 needs PostGIS.

## What changes

| Today | After |
|---|---|
| One table for every record and reading | Records of record in the registry (partitioned); readings in hypertables; shapes in PostGIS |
| Organisation and type inside a text id | Indexed columns |
| Counts by scanning | Kept totals |
| Analytics on the live table | A replica or columnar extracts |
| No pooler, no lock timeouts | Pooler, timeouts per kind of call, fail-fast DDL |

## Acceptance tests

- Settings → Storage for an organisation with millions of records answers in under two seconds, without a background
  count.
- A day's air-quality readings for one ward are returned as hourly averages in under a second, and adding a year of
  readings does not slow a property tax case's read or write.
- A kernel restart while a long read is running starts within its health window.
- "Which buildings lie in ward 169" uses a spatial index.
- Service Intelligence's figures do not change the kernel's response times while they are computed.

## Open questions

1. Which existing record types are really time series (append-only, summarised) and which are corrected and
   audited — a list per domain, owned by the domain owners (ADR-0141).
2. Retention per time-series type, and who sets it (the organisation, the domain owner, the law).
3. Whether the general registry partition should later be sub-partitioned by organisation for very large tenants.
4. Encryption at rest for sensitive JSONB (REGISTRY-v0.1 notes no pgcrypto) — orthogonal, but the same migration
   window.

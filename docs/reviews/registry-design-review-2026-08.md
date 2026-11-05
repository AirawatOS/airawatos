# Native Registry — Design Review (2026-08-26)

> **Point-in-time snapshot.** Some endpoints referenced below (e.g. `/v1/retrieve`, `/v1/resolve-citation`)
> were **retired by PLAT-0004** after this review.

Prompted by a cluster of registry defects surfacing in production use (cross-tenant Inbox leak,
duplicate Knowledge docs, a missing schema index, the `->>`/`#>>` provisioner bug, `valid_to` not
closed on supersede, 2M-row bloat). Three parallel audits (auth/tenant-isolation, bitemporal
correctness, performance/indexing) confirm the pattern is **systemic, not incidental**.

## Root-cause diagnosis — three systemic themes

1. **Authorization is layered per-endpoint, not through one choke point.** Each `/v1/*` route
   re-implements (or forgets) authenticate → scope → tenant-bind. The result is inconsistency: some
   paths fail closed, several fail **open**, and the raw write surface binds nothing. There is no single
   `authorize(caller, verb, schema, id)` that every read and write passes through.

2. **The read path resolves the whole schema into Python, then filters.** Tenant scope, field filters,
   sort, and paging all run in Python over `resolve_as_of(filter={schema})`. So scoping is *post-hoc*
   (easy to skip — that is exactly how the leaks happened) and unscalable (every query is O(all versions
   of the schema)). Indexes on other fields can never be used.

3. **The write path (supersede) conflates two temporal models and isn't atomic.** It does a
   transaction-time supersede (Model A) while stamping a fresh `valid_from` per run (Model B intent),
   producing valid-time gaps; and `autocommit=True` with no lock/unique index makes concurrent writes to
   one id race into a corrupt partition.

Fixing the themes (one auth gate; push scope+filter into SQL; pick one temporal model + make writes
atomic) resolves most individual findings below at once.

---

## Findings (consolidated, severity-ranked)

### Authorization / tenant isolation
- **C1 — CRITICAL — `/v1/registry/resolve` fails OPEN unauthenticated.** `id_prefix = [...] if tn else
  None`; no token → `tn=None` → `id_prefix=None` → returns **all tenants'** rows. **Confirmed live:**
  unauth resolve of `knowledge.document` returned `{airawat:9, kmc:3}`. (app.py:512-528)
- **C2 — CRITICAL — `/v1/registry/objects` (PUT) has no tenant/steward binding.** Only guard is
  `PROV_ENFORCE and not agent`. No check that caller's tenant == `ds:<tenant>:` in `body["id"]`. Forge a
  record in any tenant's namespace. (app.py:220-234)
- **C3 — CRITICAL — `/v1/registry/retract` lets any caller tombstone any tenant's object.** Same missing
  check as C2. Silently retract another city's flood alert / decision. (app.py:237-250)
- **C4 — CRITICAL — broker `/v1/read` + `/v1/write` don't confine the id to the run's tenant.** Confine
  by *scope*, not by the id's tenant. A `bmc` run with write on a shared schema writes `ds:kmc:...`.
  (broker.py:74-87; app.py:616-676) — **this is the direct answer to "does the caller have authorization
  to write that specific registry in that tenant?": today, no.**
- **H1 — HIGH — `…/history` and `…/prov` are fully unauthenticated.** Return every version's full object
  content + author for any id in any tenant. (app.py:253-262)
- **H2 — HIGH — `/v1/resolve-ref` resolves any id unauthenticated.** No token → treated as local+allowed.
  (app.py:367-403)
- **M1 — MEDIUM — `/v1/registry/resolve-by-identifier` fails open unauthenticated.** Leaks natural-key →
  id mapping + which tenant holds a GSTIN/PID/CNR. (app.py:551-584)
- **M2 — MEDIUM — `/v1/registry/schemas/provision` accepts any/anonymous caller.** Runs `CREATE INDEX`
  DDL + rewrites global schema meta with no admin/steward check. (app.py:350-360)
- **L3 — `KERNEL_REQUIRE_STEWARD_GRANT` enforced inconsistently and OFF by default.** Consulted on
  read/write/query, never on put/retract/provision.
- **Verified CORRECT (safe set):** `/v1/registry/query|count|aggregate` (after this turn's fix),
  `/v1/query` (broker, tenant-filtered), `/v1/context|fetch|file|embed|complete|retrieve|resolve-citation`
  (fail closed on run-token), `/v1/components/dev-token` + `_dev_confine`, `schema-cache/refresh`
  (admin-gated).

### Bitemporal correctness
- **B1 — HIGH — non-atomic supersede.** `autocommit=True`, no `FOR UPDATE`/advisory lock/unique index.
  Concurrent writes to one id → two tx-open rows + duplicate version numbers; and a transient window with
  **zero** tx-open rows on *every* supersede (cells blink out mid-run). Fix: wrap put/retract in one txn
  or `pg_advisory_xact_lock(hashtext(id))`; add `UNIQUE INDEX rv_one_open ON registry_version(id) WHERE
  tx_to IS NULL`. (pg_store.py:62,90-95)
- **B2 — HIGH — valid-time gap on re-run.** tx-supersede + engines writing `valid_time={from:now}` each
  run means a superseded row (valid `[t1,∞)`) goes tx-dead, so `resolve(valid_as_of=t1.5, known=now)`
  returns **empty** — valid-time history is lost for every corrected fact. Fix: pick ONE model — either
  the new version inherits the prior `valid_from` (correction semantics, what engines want), or split
  valid-time and keep both rows tx-live. (pg_store.py:80,92-95; flood-risk/run.py:94-95)
- **B3 — MEDIUM — in-memory dedup resurrects tombstones.** Reference store's dedup ignores `retracted`;
  re-put after retract silently swallowed. Postgres store is correct — a reference-vs-prod divergence
  that conformance tests won't catch. Fix: `and not v.retracted` at store.py:104.
- **B4 — MEDIUM — non-uniform ISO timestamps break lexicographic comparison.** `datetime.isoformat()`
  drops the fractional part at whole seconds, so `'…00Z' < '…00.000001Z'` is False → `DISTINCT ON ORDER
  BY tx_from DESC` can pick the older row as latest across a second boundary. Fix: fixed-width
  `%Y-%m-%dT%H:%M:%S.%fZ` everywhere, or `timestamptz` columns.

### Performance / indexing / growth
- **P1 — CRITICAL(scale) — resolve-all-then-filter-in-Python.** Every query/count/aggregate ships +
  deserializes the schema's entire live set; `LIMIT 1` on 500k rows sorts 500k. Fix: push filter/sort/
  keyset-page/aggregation into SQL. (app.py:285-314; query.py:57-97)
- **P2 — CRITICAL(scale) — fake keyset pagination.** Cursor is re-found by linear scan of the fully
  materialized list; deep paging is O(N²/limit). (query.py:82-97)
- **P3 — HIGH — provisioned x-indexes are dead weight.** Operator mismatch is fixed, but predicates never
  reach SQL (P1), so partial indexes are never consulted — pure write-amplification. Becomes live once P1
  lands. (pg_store.py:153-154)
- **P4 — HIGH — bitemporal resolve predicates unindexed.** No index on `tx_from/tx_to/valid_from/valid_to`
  and no composite `(schema,id,tx_from DESC)` to serve the `DISTINCT ON`. Add it. (pg_store.py:182-200)
- **P5 — HIGH — no compaction/retention.** Append-only forever; non-idempotent re-runs + tombstones grow
  unbounded (the 2M-row bloat). Fix: history-retention window per schema, tombstone GC past the horizon,
  partition by `tx_from` month, and/or "latest-only" schemas that hard-replace.
- **P6 — MEDIUM — count/aggregate materialize in Python.** Push to SQL `COUNT(*)`, `GROUP BY`,
  `percentile_cont`.

### Already shipped
- `_asof_rows` fail-CLOSED + tenant scope pushed into SQL via `id_prefix` (fixes the query/count/aggregate
  leak). Verified: unauth tenant-scoped read → 0; authed bmc → own+airawat only, no kmc.
- Base `rv_schema` index; `#>>` provisioner fix (earlier).

### P0 — SHIPPED + VERIFIED (2026-08-26)
One zero-trust gate now fronts every registry read/write (`_read_reach`, `_assert_read_object`,
`_assert_write_own_tenant` + broker id-confinement). All eight findings closed and tested:
- **C1** `/v1/registry/resolve` — fail-closed + id_prefix push-down. unauth knowledge.document: 12→**0**.
- **C2/C3** raw `objects` PUT / `retract` — bound to caller's own tenant. bmc→ds:kmc: **403**; unauth **403**.
- **C4** broker `/v1/read`+`/v1/write` — id steward must be the run's own tenant (+shared steward for reads).
  run-flood-risk@bmc → ds:kmc: read/write **403**; own ds:bmc: read **200**.
- **H1** `…/history` + `…/prov` — now authenticated + steward-scoped (unauth **401**).
- **H2** `/v1/resolve-ref` — local object read gated (unauth **401**).
- **M1** `/v1/registry/resolve-by-identifier` — auth required + scan scoped (unauth **401**).
- **M2** `/v1/registry/schemas/provision` — admin/steward only (unauth **403**).
- Design note: a **tenant** role (tenant_admin/admin/steward) is bound to its own tenant and grants NO
  cross-tenant reach — writes are own-tenant-only for everyone; no role bypass.
- Public `viz.layer`/`ref.*` stay world-readable (regression-checked: 24 rows).

**P0 FALLOUT — app-host read-auth (2026-08-26).** Making the registry fail CLOSED flushed out UI code that
had been *silently depending on the fail-open leak*: the app-host control-plane read helpers `_kv_get` /
`_kv_find` (which read `platform.app_shelf`, `governance.role`, `governance.role_grant`) called
`/v1/registry/resolve` with NO token → after P0 they returned empty → an installed app vanished from the
desktop and Marketplace re-offered "Install" (the shelf WRITE had succeeded; only the read-back was denied).
Fixed: `_kv_get`/`_kv_find` now attach the session token (authenticated + tenant-scoped); audited every
app-host registry read and fixed two more tokenless ones — the dev-tenant **seed-copy** (reads prod rows)
and **schedule save** (reads prior run-stamps). The `viz.layer` catalog read is correctly left tokenless
(public schema). Verified via a real bmc session: `/apps` now returns `city-scan`. Lesson: fail-closed is
correct; any surface that broke was reading tenant data unauthenticated and must now pass a token.

### P1 — SHIPPED + VERIFIED (2026-08-26)
Bitemporal correctness in `kernel/services/registry/{pg_store,store}.py`:
- **B1** atomic supersede — `put`/`retract` now run in ONE transaction (`_txn`, autocommit off) behind a
  per-id `pg_advisory_xact_lock`, so no zero-open window and no double-open under concurrency. Backstop:
  partial `UNIQUE INDEX rv_one_open ON registry_version(id) WHERE tx_to IS NULL`, preceded by an idempotent
  startup REPAIR that closed 339 pre-existing multi-open ids. Verified: after a full 6,797-cell flood re-run,
  **0** ids with >1 tx-open row.
- **B2** valid-from inheritance — a re-write inherits the prior live assertion's `valid_from` (correction
  semantics), so `valid_time={from:now}` per engine re-run no longer creates an unqueryable valid-time gap.
  Verified: cell kept `valid_from` across a re-run while `tx_from`/score advanced; `valid_as_of` between the
  two runs now resolves all 6,797 cells (was a gap).
- **B3** in-memory dedup now skips tombstones (`and not v.retracted`) so an identical re-put after a retract
  resurrects instead of silently dedup-ing to the tombstone (pg store was already correct — reference parity).
- **B4** timestamps compared as `timestamptz` (`NULLIF(col,'')::timestamptz`) in `resolve_as_of`, and `_now()`
  emits fixed-width microseconds — text/chronological order can no longer disagree across a second boundary,
  and mixed second/microsecond legacy rows compare correctly without a data migration. Verified: reads work
  (incl. a row with an empty-string valid_from).

**Still open: P2 (perf P1–P6) — the resolve-all-then-filter-in-Python pipeline, fake keyset pagination,
missing composite bitemporal index, no retention/compaction.** EC2 deploy can proceed with P0+P1 included.

---

## Proposed fix sequence

**P0 — close the security holes (before EC2 deploy):**
1. Extract one gate: `_authz_read(schema, authorization) -> (allowed_stewards | PUBLIC | DENY)` and
   `_authz_write(id, caller) -> ok`. Route C1, H1, H2, M1 through the read gate (fail closed + id_prefix
   push-down, mirroring `_asof_rows`). Route C2, C3, C4 through the write gate: **require
   `_steward_of(id)` == caller's tenant** (own-tenant writes only; shared schemas read-union but never
   write cross-tenant), independent of the `REQUIRE_STEWARD_GRANT` flag. Admin-gate M2.
2. Turn the default posture safe: `REQUIRE_AUTH`/`REQUIRE_STEWARD_GRANT` on for the write surface (or make
   the gate not depend on the flag).

**P1 — bitemporal correctness:** B1 (atomic + unique-open index), B2 (choose the temporal model; align
engines), B3, B4.

**P2 — scale:** P1/P2 (SQL push-down + real keyset), P4 (composite index), P5 (retention), P6.

Recommendation: do **P0 now** (these are live cross-tenant read *and* write holes), land P1 next (data
correctness), and schedule P2 as a focused refactor of the read pipeline (it's the biggest change and is
performance, not safety). EC2 deploy should wait until at least P0 ships.

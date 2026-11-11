# Kernel (Registry Service) — Deep Code Review (2026-09-01)

> **Point-in-time snapshot.** Several endpoints in the tables below (e.g. `/v1/decisions`, `/v1/cases/*`,
> `/v1/registry/aggregate`, `/v1/retrieve`, `/v1/resolve-citation`, `/v1/schemas` GET, `install-pack`,
> kernel `/v1/federation/*`) were **retired by PLAT-0004** after this review.

Scope: `kernel/api/app.py` (1,811 LOC — the entire HTTP surface), `kernel/services/registry/{store,pg_store,query}.py`,
`kernel/services/broker/broker.py`, `kernel/services/authn.py`. Follows up the 2026-08-26 registry design review
(`registry-design-review-2026-08.md`), which closed P0 (auth gate) and P1 (bitemporal correctness). This review
covers the whole kernel surface and re-checks what's still open.

---

## 1. API specification (as-built, from source)

The kernel is one FastAPI app on `:8080`. All bodies are `dict = Body(...)` (no Pydantic models). Auth is one of
three schemes depending on the surface:

- **User/JWT** — `Authorization: Bearer <EdDSA JWT>`, verified against the identity JWKS (`authn.verify`). Carries
  `{sub, tenant, roles}`.
- **Run-token** — `X-Run-Token: <token>`, resolved to a confined run spec (`_run_spec`). The broker surface.
- **Component headers** — `X-Component-Id` / `X-Component-Version`, used to attribute delegated writes.

### Registry — core read/write
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/registry/objects` | JWT (+ optional component hdrs) | Attributed write; own-tenant bound; schema-validated |
| POST | `/v1/registry/retract` | JWT | Soft-delete (tombstone), own-tenant only |
| POST | `/v1/registry/resolve` | JWT / public | Bitemporal resolve by id/filter; grant-gated cross-tenant read |
| POST | `/v1/registry/query` | JWT / public | filter → sort → keyset page over as-of view |
| POST | `/v1/registry/count` | JWT / public | Count (optional distinct) |
| POST | `/v1/registry/aggregate` | JWT / public | group_by + metrics + having + top-N |
| POST | `/v1/registry/resolve-by-identifier` | JWT (required) | natural-key (GSTIN/PID/CNR…) → `ds:` id |
| GET | `/v1/registry/objects/{id}/history` | JWT | Full version lineage |
| GET | `/v1/registry/objects/{id}/prov` | JWT | Write-attribution trail |
| GET | `/v1/registry/capabilities` | none | Conformance classes (core/query/timeseries) |
| POST | `/v1/registry/schemas/provision` | JWT admin/steward | Create x-indexes, capture x-timeseries |
| POST | `/v1/registry/schema-cache/refresh` | JWT admin/steward | Drop schema-def cache |
| POST | `/v1/resolve-ref` | JWT | Scheme/steward/federation-aware reference resolver |

### Broker — confined component surface (run-token)
| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/context` | Run context (no secret/token by construction) |
| POST | `/v1/read` | Capability-checked single-object read, tenant-confined |
| POST | `/v1/query` | Capability-checked query, tenant-confined |
| POST | `/v1/write` | Capability-checked write; component-attributed; emits event |
| POST | `/v1/fetch` | Brokered egress (declared-host allow-list + rate-limit + secret injection + audit) |
| POST | `/v1/file/put` / `/v1/file/get` | Content-addressed blob I/O |
| POST | `/v1/embed` / `/v1/complete` | Metered model access (+ interaction receipt) |
| POST | `/v1/retrieve` / `/v1/resolve-citation` | Semantic retrieval → verifiable citations |

### Lifecycle / governance / federation / decision
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/components/install` | Resolve+verify cert, mint run-token, per-tenant install-as-grant, bundle fan-out |
| POST | `/v1/components/uninstall` | Revoke run-token + steward grants (tenant-admin) |
| GET | `/v1/components` | Installed components |
| POST | `/v1/components/dev-token` | Mint confined dev-token (Developer-only, dev-tenant only) |
| POST | `/v1/schemas/install-pack` | Verify signed pack + members, register vocab + roles |
| GET | `/v1/schemas` | Installed governed vocabulary |
| GET | `/v1/kernel/manifest` / `/v1/kernel/conformance` | Declared ABI + live conformance check (ADR-0059) |
| POST | `/v1/receipts/verify` | Verify a signed receipt |
| POST | `/v1/decisions` / `/v1/decisions/demo` | SPEC-0005 compliance decision (demo) |
| POST | `/v1/cases[...]` | Case lifecycle: open/list/summary/decide/contest/redecide/close |
| POST | `/v1/federation/{trust,directory,send,receive}`, GET `/v1/federation/identity` | Federation client |
| GET | `/v1/health` | Liveness |

~48 routes total.

---

## 2. Is the spec documented, and are code & spec in sync?

**Short answer: there is no single source-of-truth API spec for the kernel, and the machine-readable one that
exists (FastAPI's `/openapi.json`) is nearly contentless.**

What exists today, and where it drifts:

1. **FastAPI auto-`/openapi.json` + `/docs`** — generated, always "in sync" with the routes, but because every
   handler signature is `body: dict = Body(...)` and returns a bare `dict`, the generated schema has **no request
   or response models** — just a list of paths with an untyped object body. It documents *that* an endpoint exists,
   not its contract. Not usable as an integration contract.
2. **MDK SPEC-000x markdown** (SPEC-0002 registry, SPEC-0003 receipts, SPEC-0004 broker, SPEC-0005 decision) —
   referenced in docstrings and `conforms_to` URLs pointing at the upstream `Digital-Statecraft/mdk` repo. These
   are the real behavioural contracts, but they live **outside this repo** and there is no test asserting the code
   still matches them.
3. **ADRs** (0052 attributed writes, 0059 kernel ABI, 0060/0063/0066…) — the design rationale, prose only.
4. **Self-describing ABI** — `_KERNEL_ABI` → `GET /v1/kernel/manifest` (what the kernel claims to implement) and
   `GET /v1/kernel/conformance`, which **live-probes each interface against the network's governed catalog**
   (`/v1/interfaces/resolve`) and checks published + route-exists + shape. This is the **only automated drift check**,
   and it's good — but it covers only the 9 interfaces in `_KERNEL_ABI`, i.e. ~7 of ~48 routes. The case, federation,
   install, dev-token, and most registry-analytics routes are **not** in the ABI and are conformance-checked by nothing.

**Verdict:** partial and fragmented. The behavioural intent is well-documented in prose (SPECs + ADRs) and the ABI
subset is genuinely self-verifying, but there is **no typed, versioned OpenAPI contract** for the kernel and **no
CI drift gate**. Task #74 ("API specs: enrich core harvested specs") is still open but was aimed at the reference/
DIGIT services, not this kernel.

**Recommendation:** introduce Pydantic request/response models for at least the registry + broker surfaces (the
stable, most-integrated ones). That single change makes `/openapi.json` a real contract for free, gives request
validation (replacing the scattered `body["id"]` KeyError→500s, see R2), and lets you snapshot-test the spec in CI.

---

## 3. Security

Overall the auth model is now **sound in shape** — the Aug P0 work replaced per-endpoint ad-hoc checks with one
zero-trust gate (`_read_reach` / `_assert_read_object` / `_assert_write_own_tenant` + broker id-confinement), and
it fails **closed**. The findings below are the residual sharp edges.

### S1 — HIGH — Hardcoded production run-tokens are a latent backdoor (`app.py:24-97`)
`RUN_TOKENS` ships **static string tokens** (`dev-run-cell`, `dev-run-landcover`, `dev-run-heat`, …) baked into the
image, each bound to **`tenant: "kmc"` (a production tenant)** with `dev: True`. `dev: True` skips the steward-grant
check (`broker_write`), and these are literal constants in a source tree. The only thing standing between a caller
who knows the string and a forged production `cell.*`/`geo.*`/`environment.*` write is: (a) network reachability of
`/v1/write`, and (b) `_admit_run` requiring the component be installed in kmc (`COMPONENT_ENFORCE=1`, on by default)
— but for a live city those components *are* installed, so (b) passes. These tokens predate install-as-grant and
should not target a production tenant.
**Fix:** delete the static `dev-run-*` entries (or repoint them at a throwaday dev tenant); rely on
`/v1/components/dev-token` (already Developer- and dev-tenant-gated) and `install-as-grant` for all real runs.
**RESOLVED (2026-09-01, code):** all 9 static `dev-run-*` tokens removed — `RUN_TOKENS` now boots empty and is
populated only by the three attributed runtime paths (install-as-grant / dev-token / INSTALLED-rehydrate). The
now-dead `<base>@<tenant>` onboarding-clone mechanism (`_ONBOARDING_BASES` + the clone branch in `_run_spec`) was
removed with them (nothing constructed those strings; the live City Baseline path uses per-tenant install-as-grant).
`py_compile` clean, no dangling refs, no external importers. **Not yet deployed** — the live `airawatos-kernel:0.1.0`
image still carries the old tokens until rebuilt + redeployed to EC2.

### S2 — MEDIUM — JWT verification skips `aud`/`iss`/`alg`/`nbf` (`authn.py:25-47`)
`verify()` checks signature + `exp` only. It does **not** validate the `alg` header (it always forces Ed25519, so
"alg:none" can't forge a signature — good — but a token minted for a *different audience/client* by the same
identity service is accepted verbatim), nor `iss`, nor `nbf`. Any valid identity-issued token is accepted by the
kernel regardless of what it was minted for. Also the JWKS cache only refreshes on a `kid` miss (`_keys`), so a
**revoked-but-same-kid** key keeps verifying until process restart — there is no revocation propagation.
**Fix:** pin expected `aud` (the kernel) and `iss`; reject if `alg != EdDSA`; add `nbf`; add a short JWKS TTL.

### S3 — MEDIUM — Data-plane certified-writer gate is still shadow-only in prod (`app.py:648-685`)
`DATAPLANE_ENFORCE` is unset on the live EC2 kernel → a **human/tenant-admin JWT can still sideload `cell.*`/`geo.*`
facts directly** via `/v1/registry/objects`, bypassing the "facts come only from certified components" boundary.
It's logged, not refused. This is a deliberate shadow→enforce rollout (matches ADR-0052), but the enforce flip
hasn't happened. Track it (it's the open half of task #143).

### S4 — MEDIUM — SSRF-shaped internal fetches with short-lived, unauthenticated trust (`app.py` federation/schema/store hops)
Many handlers do `urllib.urlopen(f"{NETWORK_URL}{path}")` / `{SECRETS_URL}` / `{FILESTORE_URL}` with values straight
from the environment and, in a few spots, from request bodies (`resolve-ref` builds a canonical id from `ref`). These
are internal service hops so the blast radius is the private network, but there's **no allow-listing of the resolved
host** and **no auth header** on most network hops except where explicitly forwarded. Low priority given the network
topology, but worth a note: a compromised `NETWORK_URL` (or a body that steers a fetch) has broad reach.

### S5 — LOW — `install-pack` / role install writes with no caller-authz check (`app.py:1724-1769`)
`install_pack` verifies the pack + schema signatures against the authority (good) but the only caller gate is
"whatever tenant the token resolves to." Any authenticated user can install a signed pack into their tenant and
**write `governance.role` rows** (`REG.put` at 1765) into that tenant's namespace. Probably intended, but it's an
authenticated-user-writes-governance path that skips the admin/steward check used elsewhere (e.g. `provision`,
`schema-cache/refresh`). Confirm it's meant to be non-admin.

### Confirmed-good
- Zero-trust reads fail closed (`_read_reach` → DENY → empty, never a leak); public catalog allow-list is tight
  (`_public_schema`: `viz.layer`, `intelligence.provider`, `studio.generator`, `ref.*` only).
- Writes are own-tenant-bound independent of any feature flag; cross-tenant needs a **verified steward-signed grant**
  (`_steward_authorizes` — real Ed25519 verification against the tenant's own key).
- Brokered egress is genuinely confined: declared-host allow-list, broker-enforced rate limit, secret injection
  out-of-band (component never sees the key), every call audited to `prov.egress` **without** the key or query string.
- Dev-token minting is triple-gated (dev-tenant + Developer participant + own-tenant caller).

---

## 4. Reliability

### R1 — HIGH — In-memory process state breaks under >1 worker / >1 replica
`RUN_TOKENS`, `CASES`, `_EGRESS_LOG` (rate limiter), `_STEWARD_KEY`, and all schema caches are **module globals**.
Today's deploy is a single uvicorn worker (`Dockerfile` CMD has no `--workers`), so this is correct *now*. But:
- Runtime-minted `dev-token`s and their run-tokens live only in the minting process — add `--workers 2` or a second
  replica behind nginx and a token minted on worker A returns 401 on worker B.
- The egress rate limiter is **per-process**, so N workers = N× the declared vendor limit — the exact thing it
  exists to prevent.
- `CASES` is a live cache over a KV snapshot (rehydrates), so it survives; `INSTALLED` is KV-backed and rehydrated
  at startup (good) — but the *run-tokens* it rebuilds are per-process.
**Fix (before any horizontal scale):** move run-tokens + rate-limit counters to shared state (Postgres/Redis), or
document "single-writer kernel" as an explicit constraint.

### R2 — MEDIUM — Missing-key access → 500 instead of 400
Handlers index bodies directly: `body["id"]` (`registry_put`, `broker_read`, `broker_write`), `body["scope"]`,
`body["case_id"]`, `body["value"]`, `body["participant_id"]`, etc. A missing field raises `KeyError` → FastAPI 500,
not a 422/400 with a useful message. This is both a DX wart and a (minor) way to generate noisy 500s. Pydantic
models (see §2) fix the whole class at once.

### R3 — MEDIUM — `_emit_event` durability gap on the raw write path
`_emit_event` writes the outbox row in a **separate `REG.put`** *after* the main write returns
(`registry_put:236`, `broker_write:878`). If the process dies between the two, the write is committed but **no event
is emitted** — the "durable outbox, never silently dropped" guarantee in the docstring isn't actually atomic with the
write. (The store's own `put` is atomic; the event is a second transaction.) For true at-least-once, the event row
must be inserted **inside** the same `_txn` as the object.

### R4 — LOW — Broad `except Exception: pass` hides failures
`_identifier_schemas`, `_development_tenants`, `_tenant_environment`, `_participant_kind`, `_tenant_steward_key`,
the conformance probe, and several network hops swallow all exceptions and fall back to a default (often "deny" or
"empty"). Safe-by-default, but a misconfigured `NETWORK_URL` or a transient outage degrades **silently** to
"no dev tenants / no steward key / not a developer" — which then manifests as confusing 403s elsewhere with no log.
At minimum log the swallowed exception.

### R5 — LOW — Startup DDL + idempotent REPAIR run on every boot (`pg_store.py:18-58`)
`_DDL` (incl. a full-table `UPDATE` repair and several `CREATE INDEX IF NOT EXISTS`) runs on every construction.
It's idempotent, but the repair `UPDATE … WHERE tx_to IS NULL … rn>1` scans/locks live rows at startup, and
`CREATE INDEX` (not `CONCURRENTLY`) takes an ACCESS EXCLUSIVE lock. On a large table a restart briefly blocks
writes. Move schema management to a migration step (Flyway is already in the stack) rather than app boot.

---

## 5. Performance / scale

This is where the **most work remains** — the Aug review's P2 (perf) findings are still open, confirmed by re-read.

### P1 — CRITICAL(scale) — query/count/aggregate still resolve-all-then-filter-in-Python (`app.py:304-378`, `query.py`)
`_asof_rows` calls `REG.resolve_as_of(filter={schema}, id_prefix=…)` **with no `limit`**, materializes the schema's
entire tenant-scoped live set into Python, then `query.py` does filter/sort/page in Python. So:
- Every `/v1/registry/query` with a `limit` of 20 still deserializes **all** rows of that schema for the tenant.
- Field filters, sort, and paging never touch SQL → the provisioned x-indexes (`P3` below) are dead weight.
- `resolve_as_of` itself does `DISTINCT ON (id) … ORDER BY tx_from::timestamptz DESC` over the whole schema — the
  `::timestamptz` cast in `ORDER BY` (B4 fix) **defeats any btree index** on `tx_from`, forcing a sort.

### P2 — CRITICAL(scale) — keyset pagination is fake (`query.py:82-97`)
The cursor is resolved by a **linear scan** of the fully-materialized list to re-find the last id, then slice. Deep
paging is O(N²/limit) and it still fetched the whole set to page 1. Real keyset paging needs the predicate + `ORDER
BY … LIMIT` in SQL with the cursor as a `WHERE (sort_key, id) > (…)` tuple.

### P3 — HIGH — Provisioned partial x-indexes never used (`pg_store.py:166-201`)
The `#>>`/`->>` operator bug is fixed and the partial indexes are created correctly, but since predicates never reach
SQL (P1), they are **pure write-amplification** — every insert maintains indexes no read consults. They light up only
once P1 lands.

### P4 — HIGH — Bitemporal resolve predicates are unindexed
No index serves `NULLIF(tx_from,'')::timestamptz <= …` / `tx_to IS NULL OR … > …` / valid-time window. `rv_schema`
handles the schema equality; everything else is a scan+filter+sort. A production distribution needs a composite/
expression index aligned to the resolver's exact casts (or, better, store `tx_from`/`tx_to`/`valid_from`/`valid_to`
as real `timestamptz` columns so ordinary btrees apply).

### P5 — HIGH — No compaction / retention (the 2M-row bloat, still open)
Append-only forever; non-idempotent re-runs + tombstones grow unbounded. Needs per-schema history-retention,
tombstone GC past a horizon, monthly `tx_from` partitioning, and/or "latest-only" schemas that hard-replace.

### P6 — MEDIUM — `resolve-by-identifier` scans identifier-bearing schemas with `limit=50000`
`resolve_by_identifier` (`app.py:737-776`) loops every identifier-bearing schema, pulling up to 50k rows each into
Python and string-matching in a loop. Fine at demo scale, a cliff at city scale. Push the identifier match into SQL
(`object #> '{identifiers}' @> …` with the GIN index, or a dedicated identifier index).

**Note:** the store is explicitly a "reference-scale, O(N) over the live set" implementation (its own docstrings say
a production distribution pushes the grammar into SQL). So P1–P6 are *known* and *by-design-deferred*, not
oversights — but they are the gating work before the registry serves a large tenant under load.

---

## 6. Maintainability

### M1 — HIGH — Zero automated tests in the kernel repo
No `test_*.py` anywhere. A service that is the platform's authorization + bitemporal-correctness chokepoint, whose
past bugs were cross-tenant leaks and valid-time gaps, has **no regression net**. The Aug review's fixes were
verified by hand against live data. At minimum: auth-gate table tests (each surface × {unauth, own-tenant,
cross-tenant, admin}), bitemporal correctness (B1–B4 as tests), and a schema-validation on/off/shadow matrix.
**RESOLVED (2026-09-01):** added `tests/` — **71 hermetic tests** (no Postgres/identity/network; `_authenticate`
monkeypatched) covering the auth gate end-to-end (real routes) + via unit helpers, the S1 run-token removal,
broker capability default-deny, bitemporal B1–B4, and the query grammar. Reproduces every 2026-08 finding
(C1–C4, H1) as a passing guard. Wired **GitHub Actions** (`.github/workflows/tests.yml`) on push-to-main + PRs —
**green in CI** (run 33461558903, 14s). Still worth adding: a dedicated `authn.verify` suite (S2) and a
schema-validation strict/shadow/off matrix.

### M2 — MEDIUM — `app.py` is a 1,811-line module doing ~10 jobs
Registry, broker, egress, files, embed/complete, retrieve/citation, receipts, decisions, cases, install, packs,
federation, and the entire authz layer are one file. Function-level imports (`import json as _j` inside dozens of
handlers) and module-global caches are scattered throughout. Split into routers (`registry`, `broker`, `governance`,
`federation`, `cases`) with the authz helpers in one module — this also makes the auth gate independently testable.

### M3 — MEDIUM — Config posture is implicit and inconsistent across defaults
Enforcement is spread over ~10 env flags with **different default directions**: `COMPONENT_ENFORCE` and
`SCHEMA_VALIDATE` default **on/strict**; `PROV_ENFORCE`, `DATAPLANE_ENFORCE`, `KERNEL_REQUIRE_AUTH`,
`REQUIRE_STEWARD_GRANT` default **off/shadow**. The live EC2 kernel sets only `KERNEL_REQUIRE_STEWARD_GRANT=1` and
`DEV_REQUIRE_DEVELOPER=1`. There's no one place that states the intended production posture or asserts it at
startup. Add a startup log (and ideally a fail-fast check) that prints the effective security posture, and document
the target end-state (which shadows should be enforce in prod).

### M4 — LOW — Reference (in-memory) vs Postgres store can silently diverge
Two hand-maintained implementations of the same bitemporal semantics. B3 (tombstone dedup) was exactly this kind of
divergence (memory wrong, pg right). Without a shared conformance test run against **both** backends, the reference
store — which the broker imports directly (`broker.py:13`) — can drift from prod behaviour.

### M5 — LOW — Naming/underscore-import noise
Pervasive `import x as _x` inside functions and `_`-prefixed module aliases (`_t`, `_u`, `_j`, `_q`) reduce
readability and cause the occasional shadowing bug risk. Consolidate imports at module top after the router split.

---

## 7. Prioritized recommendations

**Do now (security + a correctness gap):**
1. **S1** — remove/repoint the hardcoded `dev-run-*` production run-tokens.
2. **S2** — validate `aud`/`iss`/`alg`, add JWKS TTL in `authn.verify`.
3. **R3** — emit the outbox event inside the write transaction (close the durability gap).
4. **M1** — add auth-gate + bitemporal regression tests (highest leverage per hour).

**Next (posture + the enforce flips):**
5. **S3 / M3** — plan the `DATAPLANE_ENFORCE` (and `PROV_ENFORCE`) shadow→enforce flip; add a startup posture log.
6. **§2** — Pydantic models on registry+broker surfaces → real OpenAPI + request validation (kills R2) + CI drift snapshot.
7. **R1** — decide single-writer-kernel vs shared state before any horizontal scale; document it.

**Scheduled refactor (scale — the biggest change, pure performance):**
8. **P1/P2** — push filter/sort/keyset-page into SQL; real cursor predicate. Unlocks **P3**.
9. **P4/P5/P6** — bitemporal indexes (or real `timestamptz` columns), retention/compaction/partitioning, SQL identifier match.
10. **M2** — split `app.py` into routers alongside the SQL push-down.

**Bottom line:** post-P0/P1 the kernel is *safe* (fails closed, own-tenant writes, verified grants) but not yet
*scalable* (the read pipeline is O(all-rows-of-schema) in Python) or *hardened for change* (no tests, one giant
module, no typed contract). The two things I'd act on immediately are the hardcoded production run-tokens (S1) and
the absence of any test net (M1); the rest is well-understood, already-catalogued work.

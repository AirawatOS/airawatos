# High-availability audit — "safe as N copies"

Can each service run as **N≥2 identical copies behind a load balancer** without losing or corrupting state?
This audit (docs only) inventories per-service state held in **process memory**, on **local disk**, or in an
**assumed-singleton** background loop, says what breaks with two copies, and the fix. It is the operational
companion to FND-5 (no silent in-memory authoritative state) and introduces **FND-18** (horizontal safety); the
per-item owners land in [FIX-PLAN](FIX-PLAN.md) under thread **T5**. Evidence is `file:line`.

## a. Per-service state → what breaks with two copies → fix

| Service | State (memory / disk / singleton) | Breaks with 2 copies behind an LB | Fix | HA-status |
|---|---|---|---|---|
| **app-host** | `_SESSIONS` sid→{token,claims} in memory (`hostcore.py:94`); `CERTIFIED` app registry in memory (`:137`); `_ONBOARD_RUNS` | A session opened on copy A is unknown to copy B → round-robin LB causes random logouts / lost CSRF context; CERTIFIED rebuilt per-copy from durable install records (eventually consistent) | **Durable, shared session store** (Postgres/registry or Redis), keyed by sid; or sticky sessions at the LB as an interim. (DEBT-B10/B45) | **HA-blocking** |
| **kernel** | `RUN_TOKENS` in memory, rehydrated from durable KV at **boot** + written to KV on mint (`app.py:57,1882`); adminaudit `_RING` in memory when DB down | A run-token minted on copy A is in KV but only loaded into copy B at B's next boot → a component call routed to B mid-run fails auth until B restarts | **Look up run-tokens from KV on each use** (not just boot rehydrate), or a shared cache with invalidation. Registry itself is in Postgres → already shared. (DEBT-B20/B10) | **HA-blocking (partial)** |
| **network** | Trust store durable (Postgres `network_kv`) ✓; svc_token `_CACHE` per-process ✓; **certificates + publish-requests in memory** (restart wipes — known gap) | A certificate issued / a publish-request decided on copy A is invisible on copy B → certify/publish behaves inconsistently per copy | **Durable certs + requests** in the registry (close the in-memory cert store). svc_token cache is fine per-copy (each mints its own reader/writer token) | **HA-blocking** |
| **identity** | `USERS_FILE` / `PASSWORDS_FILE` on local disk (`identity.py:120`); lockout store **durable Postgres** (ADR-0121) ✓; issuer key in Vault transit ✓ | A `set-password` written to copy A's local file is not on copy B → a user's new password works on one copy, fails on the other; a new account added on A is unknown to B | **Durable user/password store** (registry or DB), not a per-copy local file; or a shared read-only volume as interim. Lockout + JWKS already shared | **HA-blocking** |
| **filestore** | Blob bytes on local disk (`FILESTORE_DIR`, `filestore.py:24`; `localdev_filestore` volume) | A blob written via copy A is **404** on copy B (separate volumes) → uploads/downloads intermittently fail | **Shared object storage** (S3) backing the blob store, or a shared network volume (REG-18 / archival-tiering backlog) | **HA-blocking** |
| **automation** | `_PROCESSED` event-dedup **set in memory** (`automation.py:22`); the single event dispatcher | Each copy has its own dedup → an event seen by both copies fires its action **twice**; both copies act as "the" dispatcher | **Durable shared dedup** (idempotency keys in the registry) + **single active consumer** (leader election / lease) or fully idempotent actions. (DEBT-B10) | **HA-blocking** |
| **event-relay** | `_drain()` outbox loop (`event_relay.py:67,109`), assumed singleton | Two copies both drain the durable outbox → each event delivered to automation **twice** (doubles load; per-copy dedup can't catch it) | **Leader election / row-lease** so one relay drains at a time (`SELECT … FOR UPDATE SKIP LOCKED`), or claim each outbox row | **HA-blocking** |
| **scheduler** | `_RUNS` receipts deque in memory (`scheduler.py:37`); the **clock** that fires installed components | Two copies both fire every scheduled job → **double execution**; receipts split across copies | **Leader election / distributed lock** for the clock (one active firer); **durable receipts** in the registry. (DEBT-B10) | **HA-blocking** |
| **secrets** | none (Vault KV proxy) | — | — | safe as N |
| **model-gateway** | none (Vault + provider; usage print-logged only) | — | — | safe as N |
| **notify** | none (writes `platform.inbox_item` to the kernel) | — | — | safe as N |
| **workflow** | none authoritative (advances cases via the kernel, durable) | — | — | safe as N |
| **decision** | none authoritative (reads/writes via the kernel) | — | — | safe as N |
| **nginx** (edge) | none (reverse proxy) | — | front it with an ALB / run N behind it | safe as N |
| **postgres** | the fact store — single instance | SPOF; a second copy is not just "another replica" | infra: RDS Multi-AZ / streaming replication (§d) | infra |
| **vault** | secrets/transit — single-node file storage | SPOF; file storage is not multi-node | infra: Raft integrated storage + KMS unseal (§d) | infra |

**Assumed-singleton background loops** (must be leader-elected/lease-guarded before N>1): event-relay `_drain`,
automation dispatch, scheduler clock. **Rate limits**, when added to the public front door (DEBT-B46), must use a
shared counter (not per-copy in-memory) to be a real global limit — recorded.

**Net:** HA-blocking = app-host, kernel (partial), network, identity, filestore, automation, event-relay,
scheduler. Already safe as N = secrets, model-gateway, notify, workflow, decision, nginx.

## d. HA infrastructure (configuration, not code)

| Concern | Production configuration |
|---|---|
| **Load balancer** | An ALB (or nginx upstream pool) in front of N app-host + N network copies on the edge network; health-checked; **sticky sessions** until the shared session store lands, then round-robin |
| **Postgres HA** | **RDS Multi-AZ** (managed failover) or Patroni/streaming replication; the Kernel/network/identity DB roles created on the managed instance (installer RDS support — BOM §5 open item); fact store reachable only on the data network (ARC-3) |
| **Vault HA** | **Raft integrated storage** (≥3 nodes) replacing single-node file storage, with **KMS auto-unseal** (RELEASE-PLAN §2c gate); per-service AppRole unchanged (slice-1b); a Vault Agent sidecar per service for token renewal |
| **Shared object storage** | **S3** (or a shared volume) backing filestore blobs + app-bundles, so any copy serves any blob |
| **Multi-host / orchestration** | Either a multi-host Compose with the five ARC networks mapped to overlay networks + SGs, or **ECS/EKS** with the ARC boundaries as security groups / a service mesh and AppRole via a Vault Agent sidecar (BOM §5 open decision) |
| **Leader election** | A lease (Postgres advisory lock, or Vault/Consul session) electing the single active scheduler clock, event-relay drainer, and automation dispatcher |

## e. Proposed conformance test: two copies of each service

Add `conformance/two_copy_test.py` (host-run, local-dev), not built in this docs step:

- **Scale**: bring up a **second replica** of each service (`docker compose up -d --scale <svc>=2`, or a second
  named container on the same ARC networks) and an nginx upstream that **round-robins** app-host + network.
- **Assertions** (each proves FND-18 for one service):
  - **app-host**: log in through replica A, then make an authenticated `/bridge/*` call that the LB routes to
    replica B — expect it to succeed (session visible on both). *Today: XFAIL (in-memory `_SESSIONS`).*
  - **filestore**: upload a blob via A, download it via B — expect 200. *Today: XFAIL (local-disk blobs).*
  - **scheduler**: register a one-shot schedule with two clock copies running — assert the component fires
    **exactly once**. *Today: XFAIL (both copies fire).*
  - **automation / event-relay**: emit one event with two consumers running — assert the action runs **once**.
    *Today: XFAIL (per-copy dedup).*
  - **identity**: `set-password` via A, log in via B with the new password — expect success. *Today: XFAIL
    (local file).*
  - **network**: issue a certificate via A, resolve it via B — expect it present. *Today: XFAIL (in-memory).*
  - **secrets / model-gateway / notify / workflow / decision**: any read/write through either replica succeeds —
    expect **PASS today** (stateless).
- **Encoding**: the XFAILs are the live HA-blocking gaps; each flips to PASS as its fix lands. Wire into the
  matrix under **FND-18** (the rule added in §b). The test is the exit-gate check for "safe as N copies" at each
  layer (FIX-PLAN).

---

*Introduces no code. The spec rule is FND-18 (FOUNDATIONS); per-item owners and the "safe as N copies" exit-gate
clause are in [FIX-PLAN.md](FIX-PLAN.md) thread T5. The two-copy conformance test is proposed here and is a
Layer-1 assurance-net follow-up.*

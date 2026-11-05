# ADR-0105 — Independently-scalable citizen-service tier & registry read/write scaling

Status: Proposed — S1 (read-only `service-gateway` scaffold) drafted; S2–S5 (write paths, read replicas, registry partitioning) planned.
Date: 2026-09-26
Related: [[ADR-0067]] (service directory + gateway + provider case — the domain runtime this fronts), [[ADR-0047]] (service vs solution), [[ADR-0097]] (one interaction spine — the W3 convergence of `service-*` onto generic lifecycle verbs), [[ADR-0058]] (interaction contracts + receipts — governance is unchanged), [[ADR-0020]] (OS/Network split — standalone services precedent), the native bitemporal registry (P0 authz gate #124, P1 bitemporal #125), registry→filestore archival tiering (#201), registry physical layout / partition-by-schema (#202).

## Context

Citizen-service delivery — an agency publishes an offering in **Service Studio** (birth certificate, trade licence, …) as a governed `service.offering`, and citizens (via an aggregator app) **search → init → confirm → status** it across tenants (ADR-0067) — is the highest-volume public-facing path on the platform. At civic scale a single popular service can drive orders of magnitude more traffic than every internal app combined, and it is **read-dominated** (many searches and status-checks per submitted application).

Two things about today's topology limit how that load scales, confirmed by reading the code:

1. **The citizen-service path runs through the shared trusted host.** The `/bridge/service-*` handlers in `app_host` (`service_routes.py`) are a thin **BFF** — they proxy the network gateway, jurisdiction-scope to the citizen's entitlement, attribute the session, and do delegated cross-tenant `platform.case` reads/writes. But because they live in `app_host`, citizen-service traffic **contends for the same process** that serves every app bundle and every other bridge. app_host cannot be scaled for citizen-service load without over-provisioning everything else.

2. **The registry is the ultimate write ceiling.** The domain runtime already lives in a separate service (the `network` gateway, ADR-0067 S4) and is replicable. But every `init`/`confirm` is a write to the single bitemporal `registry_version` table (append-only INSERT under a per-id `pg_advisory_xact_lock`, on one Postgres primary). Reads are served by good indexes (`rv_live WHERE tx_to IS NULL`, the `#>> '{schema}'` expression index, a GIN index) and scale with replicas; **writes do not scale horizontally on a single primary.** Scaling the front tier without addressing this just moves the queue.

Governance is **not** the issue here (that was city-ask — an ungoverned analytics handler, now a routed engine). The `service-*` interactions are already governed (ADR-0058 contracts + receipts). This ADR is purely about **deployment topology and data-tier scaling**, and it must leave the governance and confinement guarantees untouched.

A note on mechanism: an in-process **HANDLERS engine** (the city-intelligence pattern) runs *inside* `app_host` and therefore does **not** scale independently. Independent scaling requires a **standalone service** — its own container, replicated behind a load balancer — which is the established pattern for `network`, `decision-service`, and `mospi-gateway`.

## Decision

Separate the citizen-service path into its own horizontally-scalable tier, and scale the registry along its two independent axes (reads via replicas; writes via partitioning + tiering), while keeping every governance guarantee where it is.

### 1. A standalone `service-gateway` service (read-first)

Peel the citizen-facing `service-*` surface out of the shared `app_host` into a dedicated, stateless, replicable `service-gateway` service (a container like `mospi-gateway`), fronted by a load balancer. Because the path is read-dominated, migrate the **read** interactions first:

- `search` (discover offerings) and `status` (read a provider case) are **stateless and read-only** — they proxy the network gateway (`/v1/service/search`) / registry read path (`/v1/registry/resolve`) and can be replicated freely. **S1 scaffolds these.**
- `init` / `confirm` (the writes) move in a later slice, once the write-tier strategy below is in place; until then they keep flowing through the existing app_host BFF (no behaviour change).

> **Prerequisite surfaced while scaffolding S1 — lift the search scoping out of the BFF.** Today `search` scoping does not live in the network gateway: the app_host BFF (`routes/service_routes.py:_bridge_service_search`) applies, *after* the network call, an **audience gate** (an offering is shown only to viewers holding its governed role, default `civic.resident`) and a **jurisdiction scope** (shown only if its serving jurisdiction is ancestor-or-self of the citizen's residence/property jurisdiction, read from their profile) — both **fail closed**. A read tier that served the raw network catalog would **leak** cross-jurisdiction and officer-only offerings onto a citizen's home. So before `search` is wired onto the public router (S2), that scoping must be **lifted into the network gateway's `/v1/service/search`** (preferred — it becomes governed and centrally testable) or replicated in `service-gateway` against the citizen profile. The S1 scaffold proxies the raw catalog and tags the response `context.scoping = "unscoped-scaffold …"`; it is deliberately **not** registered on the public router until the scoping moves.

The gateway forwards the caller's session token unchanged; **authorization, jurisdiction scoping, and grant-gating are unchanged** — it is a scaling boundary, not a trust boundary. It reads through a configurable endpoint (`KERNEL_READ_URL`) so it can be pointed at a **read replica** (axis A below) without code change.

### 2. Registry reads → read replicas (axis A)

The registry read path (`resolve` by id / by `schema` filter, live-version index) is replica-safe: it never needs the primary. Provision one or more **Postgres streaming read replicas**; route `service-gateway` (and other read-heavy consumers — search, status, dashboards, the analyst) to a replica pool via `KERNEL_READ_URL`. Writes and read-your-write paths keep using the primary. This is the cheapest, highest-leverage lever and unblocks most citizen-service scale.

### 3. Registry writes → partition, split, tier (axis B)

Writes are append-only INSERTs serialized per-id by an advisory lock on one primary. To raise the write ceiling, in increasing order of effort:

- **Split the high-churn, low-value tables out** (#202): `platform.event` and audit/logs are the highest write volume and rarely queried transactionally — move them to their own table/store (or an append-only log) so they don't contend with governed facts for the primary's write path.
- **Partition `registry_version` by `schema` (and/or tenant)** (#202): native Postgres declarative partitioning on the `schema` expression (and tenant prefix) spreads INSERT contention and vacuum load, and lets hot schemas (e.g. `platform.case`, `cell.crowd_density`) sit on their own partitions.
- **Hot/cold tiering to the filestore** (#201): closed/aged cases and superseded bitemporal versions move to cold storage (filestore, content-addressed), keeping the hot partition small and write-fast. History stays retrievable (bitemporality is preserved), just not on the primary's hot path.
- **Eventual tenant sharding**: if a single tenant's write volume exceeds one primary, shard the registry by tenant (the id is already `ds:<tenant>:…`, so the shard key exists). Last resort — the three steps above should cover realistic civic load first.

### 4. What stays exactly where it is

- **Governance**: offerings and interactions remain network-governed (`service.offering`, ADR-0058 contracts + `interaction.receipt`). The scaling tier introduces no new verb and no ungoverned logic.
- **Confinement / trust**: `service-gateway` forwards the caller's token; it holds no elevated authority. Cross-tenant `init`/`confirm` writes stay grant-gated exactly as today.
- **The domain runtime** stays in the `network` gateway (ADR-0067) — `service-gateway` fronts it, it does not replace it.
- **The ADR-0097 W3 convergence** (service verbs → the five generic lifecycle verbs) is orthogonal and still desirable; this ADR is about topology, W3 about verb consolidation. They compose: the lifecycle spine can run behind the same gateway.

## Rollout

- **S1 (this ADR):** scaffold the read-only `service-gateway` (`/health`, `/search`, `/status`) as a standalone stateless service; `KERNEL_READ_URL` points at the primary for now, swappable to a replica. *(drafted)*
- **S2:** lift the `search` audience + jurisdiction scoping into the network gateway (`/v1/service/search`) so it is governed and applied at source (prerequisite above); provision a Postgres read replica; point `service-gateway` reads at it; register the gateway on the public router and load-test search/status off the app_host path.
- **S3:** split `platform.event`/logs out of `registry_version` (#202).
- **S4:** partition `registry_version` by schema (+ tenant) (#202); wire hot/cold tiering (#201).
- **S5:** move `init`/`confirm` writes behind `service-gateway`; retire the app_host `service-*` BFF (coordinate with ADR-0097 W3).

## Consequences

- **Positive:** the highest-volume public path scales independently of the shared host; reads scale linearly with replicas; the write ceiling is raised without changing the data model; governance and confinement are untouched; the change is incremental and reversible (each slice is behind config/topology, not a rewrite).
- **Negative / risks:** read replicas introduce **replication lag** — `status` right after `confirm` may read stale; mitigate by routing read-your-write to the primary or reading the case by id from primary for a short window. Partitioning + tiering are real DB operations with migration cost and vacuum/integrity considerations; they must be staged behind the read-replica win. A second public service tier adds an operational surface (LB, health, deploy) — justified only at the volumes that motivate it, so **S2+ should be gated on real load numbers** (peak req/s, read:write ratio), not built speculatively.
- **Open question:** the exact partition key granularity (schema vs schema×tenant) and the tiering trigger (age vs closed-state) should be decided against measured hot-set size, not guessed.

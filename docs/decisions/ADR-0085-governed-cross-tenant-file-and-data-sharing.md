# ADR-0085 — Governed cross-tenant file & data sharing (a network filestore)

**Status:** Proposed
**Relates to:** ADR-0023 (federation interaction model — Data / Requests / Events), the cross-tenant **aggregator
lane** (`/v1/data-requests` — aggregator asks, target tenant decides), ADR-0052 (attributed, digest-verified writes),
ADR-0030/0079 (broker + universal component delivery — content-addressed source tars), ADR-0084 (local installs as
federated participants), ADR-0083 (Studio publishing), the app-confinement boundary (ADR-0063 — all app I/O via
`/bridge/*`).

## Context

Two needs converge on the same missing primitive:

1. **Federated marketplace publishing (ADR-0084/0083).** A component published from one install must have its **source
   reachable by every other install** so any tenant can rehydrate + run it. Today `_deliver` uploads source to the
   **local** filestore and records a `platform.component_asset` in the **local** registry — so a federated publish
   leaves a catalog listing whose artifact lives on the publisher's box, unreachable by others (probed + confirmed:
   the shared filestore isn't exposed; only `/network`, `/kernel`, `/` are routed).

2. **Tenant-to-tenant file/data sharing.** Tenants on the network need to share **files** (a document, an image set, a
   dataset dump), not just registry facts — and to do it *under grant*: "Tenant A may share these files with Tenant B."
   The aggregator lane already governs cross-tenant **data (registry) reads** via request→decide; there is no
   equivalent for **blobs**.

Both are the same gap: **there is no governed, network-mediated way to move a blob between installs.** And the naïve
fix — expose each filestore publicly — is wrong: it breaks the confinement model (ADR-0063) and lets anyone read/write
arbitrary blobs. User uploads (complaint photos, attachments) already work correctly *mediated* through
`/bridge/file-upload` → the tenant's own (local) filestore, and **must stay tenant-local**; this ADR is **not** about
changing that. It is about the *cross-tenant* / *cross-install* path.

## Decision

Add a **network-hosted filestore** to the shared Network, with **governed, authenticated** upload/download — the
blob counterpart to the aggregator lane. Two access modes over one mechanism:

- **Public artifacts (marketplace):** a published component's source is uploaded to the network filestore and is
  **readable by any participant** (it is a marketplace artifact) — this closes the ADR-0084/0083 federated-publish gap.
- **Private shares (tenant→tenant):** a blob shared from Tenant A to Tenant B is readable/writable **only under a
  grant** A↔B, mirroring the data-requests flow but for files.

The raw per-tenant filestores stay **private + mediated** as today. The Network filestore is the *only* cross-boundary
door, and every hop is authenticated + digest-verified.

### Mechanism

- **Network filestore** — content-addressed blob store on the Network (id = `sha2-256:<hex>`, dedup, immutable),
  reachable via the already-public `/network/` route. Backed by a durable volume (or object store) on the Network host.
- **Endpoints** (all token-verified — ADR-0084 issuer trust):
  - `POST /v1/files` — upload a blob → `{id, size}`. Records who uploaded (attribution) + a visibility (`public` for
    marketplace artifacts, or `share` scoped to a grant).
  - `GET  /v1/files/{id}` — download. `public` blobs: any participant. `share` blobs: only the grant's parties.
  - `POST /v1/file-shares` — Tenant A **requests** to share files with (or read files from) Tenant B: `{from, to,
    purpose, direction, file_ids?|scope}`. Mirrors `/v1/data-requests`.
  - `POST /v1/file-shares/decide` — Tenant B's admin **grants/denies** → a steward-signed grant authorizing the transfer.
- **Attribution + integrity:** every upload carries the actor (ADR-0052) and is digest-verified on read; the
  `component_asset` / share record references the Network `file_id`, so installers + grantees resolve the blob from the
  Network, not the origin box.

### The two flows

```
MARKETPLACE (public):                              PRIVATE SHARE (grant-gated):
 publish (any install) ──POST /v1/files (public)──►  A: POST /v1/file-shares {to:B, file_ids, purpose}
 network filestore stores + records component_asset  B admin: POST /v1/file-shares/decide → grant
 EC2 / any tenant ──GET /v1/files/{id}──► install    A ──POST /v1/files (share=grant)──► network filestore
                                                     B ──GET /v1/files/{id} (grant checked)──► receives
```

## Consequences

- **Federated marketplace works** — a `dev1co` developer's published component is installable on EC2 (source resolves
  from the Network filestore). Unblocks the ADR-0084 grand scenario.
- **Tenants can share files under governance** — the aggregator lane generalises from registry facts to blobs, with the
  same request→grant→audit spine; no raw filestore exposure.
- **Confinement intact** — per-tenant filestores stay private + `/bridge/*`-mediated; user uploads stay tenant-local.
  The Network filestore is a distinct, governed surface.
- **Cost:** the Network now stores blobs (durability, quota, GC) + a new grant type; egress/size limits to set;
  marketplace artifacts are world-readable to participants (fine — they are catalog artifacts, and carry no secrets).

## Rollout (slices)

- **S1 — Network filestore + public upload/download.** `POST /v1/files` + `GET /v1/files/{id}` on the Network (durable
  volume), token-verified, public read. Wire the publish path to deliver component source to the **Network** filestore
  when federated (+ record the `component_asset` referencing the Network `file_id`). Prove: publish from the local
  install → source lands on the Network → resolvable. **This is the ADR-0084 grand-scenario unblock.**
- **S2 — Private shares. ✅ DONE (File Explorer).** `network.file_share` records + `POST /v1/file-shares` (sender
  offers) + `GET /v1/file-shares` + `POST /v1/file-shares/decide` (recipient admin accepts/declines); `GET
  /v1/files/{id}` enforces the grant for any blob that is the subject of a private share (only the sender tenant,
  or the recipient once accepted, may read). Surfaced in **File Explorer**: a per-file **Share** action and a
  **Shares** panel; the app-host mediates the tenant→network→tenant blob hop (`/bridge/file-share`,
  `/bridge/file-shares`, `/bridge/file-share/decide`) and lands accepted files under `/Shared with me`. Proven
  e2e nashik→bmc: pre-accept download 403-gated, accept pulls the blob into the recipient's own filestore, bytes
  match. Remaining (S2+): an Inbox notification for a new inbound offer; X25519 seal of `share` blobs.
- **S3 — Quota, GC, retention.** Per-tenant quota, unreferenced-blob GC, retention policy; large-file streaming.
- **S4 — Cross-install install path.** The runtime-manager/launcher rehydrates component source from the Network
  filestore (not just the local one) when installing a marketplace component on a fresh tenant.

## Open questions

- Storage backend: a durable volume on the Network host (simple, S1) vs. object storage (S3/MinIO) for scale.
- Should the Network filestore *front* per-tenant filestores (proxy + cache) rather than hold a second copy? Start with
  a copy (simple); revisit for large datasets.
- Encryption at rest for `share` blobs (X25519 seal, ADR-0024) — defer to S2+.

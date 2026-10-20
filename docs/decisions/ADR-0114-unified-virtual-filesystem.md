# ADR-0114 — A unified virtual filesystem over the content-addressed store

- **Status:** Proposed (2026-10-20). Design agreed with the product owner in conversation; no implementation yet. Scope below is the model + Phase-1 slice; later phases explicitly deferred.
- **Builds on:** [[ADR-0093]] (component delivery: retire baking → filestore-default, materialize-on-demand), [[ADR-0016]]/[[ADR-0022]] (marketplace / everything-is-a-component; install-as-grant), [[ADR-0051]]/INT-0004 (developer tenant + dev-token + self-serve dev loop), [[ADR-0052]] (authenticated/attributed registry writes), [[ADR-0025]]/[[ADR-0058]] (schemas/interfaces = the governed contract), [[ADR-0103]] (per-object sharing / `access.grant`), [[ADR-0085]] (cross-tenant file sharing = governed door), [[ADR-0049]] (Document Wallet — owner-scoped files), PLAT-0002 (reference File Store). Related surfaces: the **Files** app, the **Console** app, and the `aos` CLI (`/bridge/file-push`).

## Context

The registry disintermediates **all data**: every fact is an attributed, tenant-scoped, bitemporal record addressed by a governed id (`ds:<tenant>:<schema>/<key>`), and apps never see storage — they see governed objects. The product owner's observation: **files deserve the same treatment.** Today "where is a file / a component / my work-in-progress" has three different, half-exposed answers, and no single coherent namespace a person (or an app, or a developer) can navigate like an operating system.

The intuition — "the filestore should expose `/tenant/`, `/tenant/user/`, `/tenant/components/` like any OS" — is right as a **user-facing model** and is already **half-built**. But taken literally ("path-structure the blob store") it would regress the properties that make the platform safe. The resolution is to name the layers precisely.

### An OS filesystem is already two layers — and so is ours

A real filesystem separates **inodes** (content, addressed by number) from **directory entries** (human names pointing at inodes). AirawatOS already has that split:

| OS concept | AirawatOS today | Properties it must keep |
|---|---|---|
| **inode / blocks** | **Filestore** — content-addressed blob, `file_id = sha2-256`, on disk at `$FILESTORE_DIR/<hex[:2]>/<hex>` | dedup (same bytes, one blob), **inherent integrity** (the id *is* the hash), **portability** (deliverable to any host/operator by digest — universal delivery, `NETWORK_FILESTORE_URL`) |
| **directory entry** | **`platform.file`** record `{tenant, kind:file\|folder, owner, name, folder, file_id, …}`, id `ds:<tenant>:file/…` | governed, attributed, owner/tenant-scoped, bitemporal |

So the `/tenant/<user>/...` tree the owner is asking for **already exists** — as a governed naming overlay in the registry (that is how the Files app shows `/inbox/complaints.csv`). It simply (a) does not yet cover **components** or **developer work-in-progress**, and (b) is not presented as one addressable virtual filesystem.

### The trap: do not push paths into the content store

Making the blob store itself path-structured (`/kmc/components/foo`) would:

1. **Kill dedup + integrity** — a path is mutable and per-tenant; the "id is the hash" guarantee (which certification's `evidence_digest` and [[ADR-0093]] digest-verified delivery both depend on) is lost, and identical bytes stored under two paths become two copies.
2. **Break portability/federation** — a digest is meaningful on every host and across operators; a path is meaningful on exactly one host. Cross-host delivery is by digest.
3. **Invite overwrite-in-place** — OS path semantics imply mutation, which fights the platform's append-only, attributed, signed discipline (registry + immutable blobs + audit).
4. **Endanger certified code** — an installed component must be *exactly* its certified digest. A mutable `/tenant/components/foo` path is a tamper surface; the digest-verify gate is what makes delivery trustworthy.

### The real gaps

- **User files:** already `platform.file`, owner-scoped. ✓ (this *is* `/tenant/users/<u>/…`).
- **Components:** stored as `platform.component_asset` blobs (+ the kernel `INSTALLED["<cid>@<tenant>"]` record) and materialized on-host at `/data/app-bundles/.components-cache/<cid>` ([[ADR-0093]]) — **not** navigable as `/tenant/components/…`. Gap.
- **Developer work-in-progress:** the self-serve dev loop stages draft source to the filestore (`source_file_id`) and materializes a dev dir — but there is **no editable, browsable workspace** a developer sees as a folder. Gap.

## Decision

Introduce a **governed Virtual File System (VFS)**: one per-tenant path tree, projected over the existing content-addressed filestore + registry. The VFS is **a naming/resolution overlay, not new physical storage** — exactly the way the registry is an overlay over Postgres. "Registry abstracts all data" → **the VFS is the registry abstracting all files.**

### 1. Three concerns stay separate (this is the whole ADR in one line)

| Concern | Layer | Rule |
|---|---|---|
| **Names / hierarchy** | registry (`platform.fsnode`, below) | governed, attributed, tenant/owner-scoped, bitemporal |
| **Bytes / content** | content-addressed filestore (unchanged) | immutable blob, `file_id = sha2-256`, dedup + integrity + portability |
| **Component trust** | certified digest + install-grant (unchanged) | components appear in the tree **read-only**, writable only in a dev workspace that publishes to a certified digest |

### 2. `platform.fsnode` — generalize `platform.file` into a typed node

A path resolves to a node whose `target` is one of:

- `blob` — a data file: `{file_id}` into the filestore (today's `platform.file kind:file`).
- `folder` — a directory (today's `platform.file kind:folder`).
- `component` — a **read-only mount**: `{component_id}` → resolved to the certified asset blob/tree on read (projection of `INSTALLED` + `platform.component_asset`, materialized on demand, digest-verified).
- `workspace` — a **writable developer draft**: a mutable tree of `blob` children that `publish` snapshots into a certified component (digest).

`platform.file` is retained as the back-compatible shape (a `blob`/`folder` node); `platform.fsnode` is the superset. One resolver walks `folder → name` edges to a node, then yields bytes (blob), a stream of the component tree (component mount), or the workspace children.

### 3. Canonical per-tenant tree (all views, no new physical storage)

```
/<tenant>/
  users/<user>/…                      ← blob/folder nodes, owner-scoped (today's platform.file)
  users/<user>/projects/<proj>/…      ← workspace: a developer's EDITABLE draft (writable)
  shared/…                            ← tenant-scoped blob/folder (access.grant to share wider)
  inbox/…                             ← per-user received files ([[ADR-0085]] cross-tenant door)
  components/<cid>/…                  ← READ-ONLY mount of installed components (certified bytes)
  datasets/<schema>/…                 ← (optional, later) a read-only view bridging to the registry
```

### 4. Components = a read-only projection, never a writable folder

`/<tenant>/components/<cid>/…` lists the tenant's installed components (from `INSTALLED["<cid>@<tenant>"]`) and, on read, streams the **certified** bytes (via `platform.component_asset` → filestore, digest-verified exactly as [[ADR-0093]] materialization does). No write path exists through this mount — it cannot be used to tamper with certified code. This gives the owner the "`/tenant/components`" they asked for, as a safe view.

### 5. Developer work-in-progress = a writable workspace that publishes to a digest

`/<tenant>/users/<dev>/projects/<proj>/` is a `workspace` node: ordinary mutable blob/folder children the developer edits (upload, Console, Studio, `aos`). **Publish** snapshots the workspace tree → a tarball → a content-addressed blob + `evidence_digest` → the existing certify/publish path. This is precisely the self-serve dev loop (INT-0004 / [[ADR-0051]]) given a filesystem face: mutable while you build, immutable + certified once you ship. The dev tenant relaxation already governs who may do this.

### 6. Authorization = registry scoping, reused unchanged

The VFS mints **no new permission engine**. A node's visibility/mutability is the registry's existing gate: `owner` + `tenant` scope for user files, `access.grant` ([[ADR-0103]]) for sharing a node wider or cross-tenant ([[ADR-0085]]), install-grants for the component mount's listing, and the dev-tenant × builder predicate for workspace writes. Every write stays attributed ([[ADR-0052]]) with the caller's own token (as `/bridge/file-push` already does).

### 7. Portability & federation: names are local, bytes are universal

An `fsnode` path is a **local name**; the bytes under it stay **digest-addressed** and are delivered across hosts/operators by digest (universal delivery). Component mounts are host-local **views** computed from governed records — a different operator hosting the same tenant recomputes the same tree from the same registry + fetches the same blobs by digest. Nothing about the path tree is baked into a blob or an image.

### 8. One API surface; three existing apps collapse onto it

A VFS resolver — `stat / list / read / write / mkdir / mount / publish` over a path — backed by `platform.fsnode`. The **Files** app, the **Console** (`ls/cat/cd`), and **Studio**'s project tree all target this one resolver instead of each re-deriving paths from `platform.file`. `/bridge/file-push` and the Document Wallet ([[ADR-0049]]) become VFS writers.

## Reuse vs net-new

| Need | Reuse | Net-new |
|---|---|---|
| User-file path tree | `platform.file` (owner/folder/name/file_id) | — |
| Content storage | content-addressed filestore | — |
| Component bytes + verify | `platform.component_asset`, `INSTALLED`, [[ADR-0093]] materialize | **component mount** projection |
| Dev draft → ship | self-serve dev loop, certify/publish, `evidence_digest` | **workspace node** + `publish` snapshot |
| Authz / sharing | `access.grant`, install-grants, dev-tenant predicate, attributed writes | path→node authz resolver (thin) |
| Node model | — | **`platform.fsnode`** schema (superset of `platform.file`) + **VFS resolver** + API |

## Build plan (phased)

1. **Slice 1 — govern `platform.fsnode`** as a superset of `platform.file` (add `node_type`, `target`); back-compat read of existing `platform.file` as `blob`/`folder`. VFS resolver (`stat/list/read`) + Console/Files read through it. No behavior change for users.
2. **Slice 2 — component mount** (`/<tenant>/components/<cid>`): read-only projection over `INSTALLED` + `component_asset`, digest-verified on read. Console/Files can browse installed component source.
3. **Slice 3 — developer workspace** (`users/<dev>/projects/<proj>`): writable node + `publish` snapshot → certified blob (wires to the existing publish/cert path). Studio project tree targets it.
4. **Slice 4 — unify writers**: `/bridge/file-push`, Document Wallet, Mail attachments become VFS writers; `datasets/` read-only registry bridge (optional).

## Consequences

**Good.** One OS-like namespace for files, data assets, installed components, and dev work — the Files app, Console, and dev loop collapse onto one abstraction (the direction already being built). Content-addressing, integrity, dedup, and portability are **preserved** (the trap avoided). Certified code stays tamper-proof (read-only mount). No new permission engine, no new storage engine — pure overlay, consistent with how the registry already abstracts data.

**Costs / risks.** A resolver + `platform.fsnode` migration is real work; the component mount must materialize lazily and cache (reuse [[ADR-0093]]) or listing a big component over the VFS is slow. "It looks like a filesystem" can tempt callers to expect POSIX semantics (random-access writes, rename-as-move, hardlinks) the governed model does not offer — the API must stay object-shaped (`publish`, not `fsync`). Path collisions / very deep trees need the same `folder`-record discipline `platform.file` already uses.

## Resolved design positions

These four were open questions when the model was drafted; resolved (with the product owner) as below. Every answer points the same way: **keep the three layers separate, reuse the properties/gates the platform already has, and resist re-fusing data-with-files or inventing a second source of truth.**

### R1. No `datasets/<schema>/…` registry-as-files view — defer; if ever, export-not-live

A `datasets/` folder would surface governed rows as "files". **Rejected for now.** It re-fuses the data/file layers this ADR deliberately keeps apart (the Data app already browses datasets), and a "file" that is really a row forces an invented serialization + pagination model duplicating the registry's query API — and rows are bitemporal + relational, so flattening them to files loses exactly what makes them governed data. If genuine demand appears, add an **export-on-demand** folder (a dataset yields a *generated snapshot blob* — a real, content-addressed, shareable file), **never** a live-row-as-file view. An export is honestly a file; a live row masquerading as one is a leaky abstraction.

### R2. Component mount is **role-gated**: source to builders/admins, bundle to everyone

Browsing `/<tenant>/components/<cid>/` is gated by the **same predicate the Console's `describe` already enforces** (source-read is Studio-gated) — so this is applied policy, not new policy. A **builder/admin** role sees the full certified tree (engine/driver source — the "browse what I'm building/debugging" value); an **ordinary civic role** sees only the runnable public assets (the app bundle + declared docs), not source. This protects third-party component IP and shrinks the insider attack surface while keeping full transparency for the people who need it. First-party (`airawatdeveloper`) components may opt into source-visible-to-all; third-party vendors default to source-for-builder / bundle-for-civic. The mount is **read-only** regardless of role — it can never be a write path onto certified code.

### R3. Cross-tenant mounts: **pin the digest (copy semantics), fetch by digest (projection delivery)**

When tenant B installs a solution whose components are stewarded by tenant A, B's mount is **neither** a blind live projection **nor** a full eager copy. Install **pins a specific certified digest** in B's lockfile (correctness — no silent drift when A re-certifies), and the **bytes are fetched lazily by that digest** from whichever filestore has them (dedup + portability — universal delivery, [[ADR-0093]]). The mount therefore shows *the pinned digest*; advancing it is the explicit, admin-gated `component-refresh` action, not an automatic follow. Cross-tenant read authorization goes through [[ADR-0085]] (the cross-tenant door) + [[ADR-0103]] (`access.grant`) — B may read A's bytes only because the install-grant/share says so. This is exactly the behaviour [[ADR-0093]] materialize-on-demand + the install lockfile already have; the VFS just surfaces it.

### R4. Node versioning rides registry **bitemporality** — no second `version` edge

A file that changes over time is simply a `platform.fsnode` whose `file_id` changed; the record is already bitemporal (B1–B4, [[ADR-0052]]), so "show me the version as-of T" is a free as-of query and each version is a distinct immutable blob (content-addressing makes history nearly free). We do **not** add an explicit `versions: [{file_id, at}]` array — that would duplicate bitemporal history and create a second, drift-prone source of truth. Instead a thin **read helper** *presents* the record's history as a version list, giving the UI first-class "file versions" ergonomics without storing them twice.

## Open questions

- Quota / lifecycle: does a tenant get storage quotas at the VFS layer, and does deleting an `fsnode` tombstone-only (bitemporal) while the underlying blob is GC'd by refcount? (Blobs dedup globally, so GC must be refcount-across-tenants, not per-node.)
- Workspace concurrency: two developers editing the same `workspace` subtree — last-writer-wins on a node, or a soft lock? (Likely defer to the [[ADR-0113]] per-component ownership model rather than solving it in the VFS.)

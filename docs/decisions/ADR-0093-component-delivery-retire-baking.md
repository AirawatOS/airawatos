# ADR-0093 — Component Delivery: retire baking, filestore-default, tenant-scoped copy-on-install

**Status:** Proposed
**Date:** 2026-09-18
**Related:** ADR-0085 (universal component delivery / network filestore), ADR-0092 (unified Settings — enumerate installed, not baked), ADR-0080 (publish review).

---

## Context

Today a component's code can reach the runtime two ways, and they are inconsistent:

1. **Baked** — `platform-spec/deploy/ec2/Dockerfile.reference` does `COPY components/ /app/components/`, so the reference image ships the OS **services *and* ~40 components**. Baked components **skip filestore delivery entirely**: the launcher runs universal delivery *only* when there is no on-disk `meta.yaml` (`components/_common/launcher.py:169`).
2. **Delivered** — a published component's source tar lives in the **content-addressed filestore** (with a `__component_source__` pointer record); at run time the launcher fetches it and **verifies its dir-digest == the certificate's `evidence_digest`** before it runs (`launcher.py:110–136`). Trust is the content-address + cert digest, not the transport.

Consequences of the split:
- The image is coupled to a component library it should not know about; adding/removing a component means rebuilding the OS image.
- **Install is grant-only** (`/v1/components/install` mints a tenant run-token + write grant; it copies no source). Source sits in one **shared** content-addressed store; there is **no per-tenant copy**.
- UI surfaces that enumerate the **baked disk tree** (Connections/City-Setup) can't see delivered-only components — the ADR-0092 defect.
- First run of a delivered component depends on a **lazy fetch**; a missing `__component_source__` record fails the run at execution time (observed: exit 87 REFUSE).

## Decision

**One delivery path for every component: the filestore. Nothing is baked.**

### A. Retire baked components
`Dockerfile.reference` copies **`reference/` only** (the OS services). Components are never in the image. Every component — first-party or third-party — is delivered from the filestore and digest-verified at point of use. The launcher already supports this for all component shapes (`_dir_digest` matches flat drivers and multi-dir engines/apps alike, `launcher.py:92–107`).

### B. Delivery default = content-addressed shared filestore (dedup)
Most components are identical bytes for every tenant, so the default stays a **single content-addressed blob** shared across tenants (cheap, simple). Trust is unchanged: `file_id` (content-address) + the cert's `evidence_digest`.

### C. Tenant scope is component-declared → copy-on-install to the tenant filestore
A component whose **meta declares tenant scope** (it embeds or derives tenant-specific material, or must be tenant-private) is, **on install**, **copied into that tenant's filestore partition** (ADR-0085 gives filestore tenant+visibility), and a **tenant-scoped `__component_source__` record** (`ds:<tenant>:platform/component_asset/<slug>--__component_source__`) is written. The runtime resolves the **tenant's** copy. Content-addressing keeps the copy cheap and the digest identical, so the cert gate is untouched. Default (non-scoped) components stay shared.

### D. Materialize on install, not on first run
Install becomes the point where the certified source is **fetched from the Marketplace/Network filestore into the local (or tenant) filestore and the pointer record is written** — so runs never depend on a lazy first-run fetch, and the "missing `__component_source__` → REFUSE at run" failure class disappears. A local `component-cache/` still absorbs repeat runs.

### E. Enumerate installed, not baked (carries ADR-0092)
With nothing on disk, Connections/Settings/City-Setup **must** enumerate the tenant's **installed** components from the registry (kernel `GET /v1/components` + delivered meta), not a baked filesystem scan. This becomes unavoidable once A lands, which is the point.

## Consequences

**Positive**
- The image is "the OS," not "the OS + a component library"; components version independently of the platform.
- Uniform delivery + one trust model (content-address + cert digest) for first-party and third-party alike.
- Tenant isolation *when a component asks for it*; dedup for everything else.
- Install-time materialization removes lazy-fetch run failures.
- Forces the correct enumeration (ADR-0092), killing the baked-scan anomaly.

**Costs / risks**
- **Hard migration gate:** a baked component **cannot be unbaked until its certified source is published to the filestore and proven to run via delivery** — otherwise it fails at run. The sweep (S2 below) is a gate, not a formality.
- First-run/boot latency shifts to install-time fetch (mitigated by D + the local cache).
- Storage grows for tenant-scoped components (accepted trade for isolation).
- Every deploy that previously "just rebuilt the image with new component code" now goes through publish → deliver.

## Migration (local-first; each prod step gated on approval)

1. **S1 — prove one unbaked driver (local).** Take one currently-baked driver (e.g. `osm-roads`): publish its certified source to the filestore with a `__component_source__` record, remove it from the local baked tree, and prove it runs via delivery + digest-verify. Establishes the per-component "unbake" recipe.
2. **S2 — publish + delivery-verify EVERY baked component (the gate).** For each of the ~40 baked components, ensure a certified source + `__component_source__` record exists and a delivered run passes digest-verify. Nothing is unbaked until it clears this.
3. **S3 — flip the image to services-only.** `Dockerfile.reference` → `COPY reference/` only; rebuild + deploy. Now nothing is baked.
4. **S4 — install-time materialization.** `/v1/components/install` fetches source into the filestore + writes the pointer record (no lazy first-run fetch).
5. **S5 — component-declared tenant scope → copy-on-install** into the tenant filestore + tenant-scoped source record; runtime resolves the tenant's copy.
6. **S6 — enumerate installed, not baked** (ADR-0092): Connections/Settings/City-Setup read the registry.

## Notes
This ADR is design-only. No image or prod change happens without explicit approval; S1 is local-first per the project's test-before-deploy rule.

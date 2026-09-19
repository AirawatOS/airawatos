# ADR-0095 — Runtime lifecycle completion: re-home runtimes, filestore-deliver their meta/code, and attest operator host-integrity

**Status:** Accepted — P0 (R1 re-home), P1 (R2 filestore-deliver), **P2 (R3 host-integrity attestation, advisory)** all DONE & verified on EC2 (2026-09-19). R4 (governed provisioning) deferred.

> **R3 delivered (advisory slice):** `POST /v1/runtime/attest` + `GET /v1/runtime/attestations` on the network; the runtime_manager attests on boot which certified runtime IMAGES its node holds (local `docker .Id` == certified `image_digest` AND on-disk source == cert digest); the network re-derives the certified `image_digest` independently from its own filestore copy. `store_resolve` surfaces advisory `attested`/`attested_nodes`; Network Admin's Marketplace tab now lists Runtimes + their attested nodes. NOT yet an install gate (advisory-first, per Open Q2). Full ADR-0086 (per-operator signing key + signed attestation + operator certificate + hosting binding) remains the follow-on; this slice uses an internal token in its place.
>
> **Drift found & fixed:** the live rt-mgr imports launcher/runtimes from the HOST `rt-components/` bind-mount (COMPONENTS_ROOT override), not the image — so P0/R2's launcher+meta changes had never reached the live placement path (they were only ever exercised in throwaway/image containers), leaving runtime placement broken since P0 (retired `ds:airawat` runtime certs → 404). Re-homed metas + current launcher synced onto the host mount; placement restored.
**Relates to:** ADR-0022 (everything-is-a-component), ADR-0030 (clean-room runtime + broker), ADR-0051 (point-of-use cert/image enforcement), ADR-0058 (`platform.runtime_invoke` interface), ADR-0085 (filestore delivery), ADR-0086 (operator certification — host integrity), ADR-0093 (retire baking), ADR-0094 (component stewardship separation).

## Context

A **runtime** is a first-class component (`kind: runtime`) whose deliverable is a **shared, per-profile container image**: drivers/engines declare `runtime.profile: <x>` and are mounted into it read-only (they never ship their own image). The split is deliberate — **filestore = component code, container registry = runtime image.** Five exist today: `earth-observation`, `geospatial`, `media`, `modeling`, `vision`. Meta pins `image` (registry ref) + `image_digest` (`docker image inspect .Id`) + `provides` (libs) + `isolation`/`level` + `implements platform.runtime_invoke@0.1.0`.

The lifecycle works (certify attests the meta incl. `image_digest`; runtimes are hidden from the tenant marketplace and shown only to operators; `store.runtime_requirement` reports availability; install of a runtime-needing component is gated on the operator having provisioned it; the launcher/runtime_manager enforces the runtime cert + **locks to the certified image** — `ENFORCE_IMAGE`: local `docker image .Id` must equal cert `image_digest` — before `docker run` with code mounted read-only, broker as sole I/O, Vault secrets, scoped run-token).

But after ADR-0093/0094, runtimes are the **one kind left out of the uniform lifecycle**, with four gaps:

1. **Stewardship (ADR-0094 gap):** the 5 are still `ds:airawat:runtime/*` — the Network Admin steward that ADR-0094 forbids from publishing software. They must move to `ds:airawatdeveloper:`.
2. **Delivery (ADR-0093 gap):** runtime meta/code is still **baked** in the reference image (`components/runtimes/`), the sole exception to the services-only cutover. The launcher reads `runtimes/` from disk; nothing delivers it from the filestore.
3. **Image provisioning is out-of-band:** "operator ensures the image is on the node" is manual ops (build → push → pull). The launcher *verifies* presence + digest but nothing *delivers* or *records* it.
4. **No host-integrity attestation (ADR-0086):** the marketplace marks a runtime "available" when it is published+certified — it does **not** attest that any operator node actually holds the certified image. A tenant trusts the catalog, not the placement.

## Decision

Bring runtimes fully into the component lifecycle, keeping the image in the registry:

- **R1 — Re-home (ADR-0094).** Move the 5 runtimes `ds:airawat:runtime/*` → `ds:airawatdeveloper:runtime/*`: swap `component_id`+`provider`, re-certify (passes `steward-not-authority`), publish, re-point the operator catalog, retire the old. The `image:` ref is a *field* — re-homing the component id does **not** require re-tagging or rebuilding the image; `image_digest` is unchanged, so the launcher's image lock is unaffected. Mechanical, scriptable (same pattern as the ADR-0094 tail).
- **R2 — Filestore-deliver runtime meta/code; stop baking `runtimes/`.** Store each runtime's `__component_source__` tar (meta + any launcher-side descriptor) in the filestore + set `source_file_id` (as done for the 159 marketplace components). Teach the **launcher/runtime_manager** to *materialize-on-miss* the runtime component dir from the filestore + digest-verify (mirroring app_host `_find_component_dir`). Then extend the `Dockerfile.reference` strip to also drop `components/runtimes/` → the reference image is **fully** services-only. The **image stays in the registry** (content-addressed there already; multi-GB images don't belong in the source filestore), referenced by the certified `image_digest`.
- **R3 — Operator host-integrity attestation (ADR-0086).** On provision, the operator's runtime_manager records a signed **`platform.runtime_attestation`** per (node, runtime, version): the local `docker image .Id`, the certified `image_digest`, match=true/false, node identity, timestamp. The network exposes availability as *"certified AND attested on ≥1 operator node"* — so `store.runtime_requirement` (and install gating) reflect real placement capability, and a tenant trusts that the code will run on the image it was certified against, not just that a catalog entry exists. This is the host-integrity axis ADR-0086 introduced.
- **R4 — (optional) Governed image provisioning.** A first-class operator action `provision-runtime(runtime_id)` that pulls the certified image tag, verifies `.Id == image_digest`, and writes the R3 attestation — turning today's manual ops into one governed, audited step. Marketplace availability then follows attestations automatically.

## Migration (phased, gated, local-first)

- **P0 — R1 re-home (low risk).** Script the 5 runtime re-homes (meta swap → certify → publish → retire; update the operator catalog + any `runtime_profile` references — components resolve `ds:airawat:runtime/<profile>` → change that resolution to `ds:airawatdeveloper:` in `store.runtime_requirement` + launcher profile→id). Verify: a profiled driver (e.g. a `geospatial` engine) still places + runs. **No image rebuild.**
- **P1 — R2 delivery (medium; local-first).** (a) Backfill the 5 runtimes' `__component_source__` tars (as in ADR-0093 (1)). (b) Add materialize-on-miss to the launcher's runtime resolution + digest-verify. (c) Rehearse on the local/shadow stack: strip `components/runtimes/`, confirm a profiled component materializes its runtime meta + the launcher still image-locks + runs. (d) Extend `Dockerfile.reference` strip + cut over (gated, like the S-flip cutover). Rollback = prior image tag.
- **P2 — R3 attestation (ADR-0086).** Govern `platform.runtime_attestation`; runtime_manager writes it on provision/boot; network availability + install-gate read it; operator console surfaces attested-vs-published. Backwards-compatible (absent attestation ⇒ legacy "published=available" until enforced).
- **P3 — R4 governed provisioning (optional).** The `provision-runtime` operator action + audit.

## Consequences

- **Uniformity:** runtimes follow the exact author→certify→publish→deliver→verify lifecycle as every other component; the reference image becomes 100% services-only (closes the last ADR-0093 exception).
- **Trust:** placement is attested (R3), not assumed — a driver runs only on the image its runtime cert names, and the network can *prove* an operator holds it.
- **Registry stays the image store** — deliberately; the filestore carries code/meta, the registry carries images, both content-addressed + digest-gated. No attempt to shove images through the source filestore.
- **Federation-ready:** a re-homed, attested runtime can be advertised + trusted across operators exactly like other `airawatdeveloper` components.

## Open questions

1. **Image digest form** — `image_digest` is the local `.Id` (config digest), not the registry manifest digest; R3/R4 should record both and decide which the availability gate keys on (manifest digest is portable across nodes; `.Id` is what the launcher checks locally).
2. **Enforcement switch** — when does availability *require* an attestation (P2) vs. advisory? Suggest advisory first, enforce after all live runtimes are attested.
3. **Runtime upgrade UX** — a new `image_digest` = new runtime version; define whether profiled components auto-follow the latest attested runtime or pin a version (pin, with an operator-approved bump, matches the rest of marketplace version discipline).

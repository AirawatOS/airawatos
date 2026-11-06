# Kernel-mediated files — design (report only, no code)

**Status:** Proposed design. Supersedes the "wire every filestore caller to an `svc:filestore` pass" approach
(the shadow gate, ADR-0124 item 1, is an interim stopgap). Target: a file is a governed **record** whose bytes
live in blob storage reachable **only by the Kernel**, authorized exactly like any other record.

Today the filestore (`filestore:8095`) is a flat, content-addressed blob service that ~23 callers
(app-host ×16, hostcore ×2, scheduler, kernel ×3, launcher) reach directly over HTTP; the only protection is
the shadow `svc:filestore` ingress gate. There is no owner, no per-file authorization, no consent, no audit,
no encryption or erasure on the bytes. This design folds files into the registry's authorization model.

## a. A file is a record + bytes

A new governed schema **`platform.file`** (the record) carries: `id`, `tenant`/`owner` (principal), `schema`
(the file's declared content type/role), `content_hash` (`sha2-256:…`, integrity), `size_bytes`,
`sensitivity` (public | internal | restricted | secret — drives REG-17), `created_by`/`created_at`, optional
`retention`/`legal_hold`, and a private `blob_ref` (where the bytes sit) that is **never returned to a caller**.
The bytes live in **blob storage** (object store / disk) on a network path reachable **only from the Kernel**
— no service and no component holds a blob URL or a filestore address. The record is the file's identity; the
bytes are an implementation detail behind the Kernel.

## b. Reads and writes use the SAME authorization as records

File access is a registry operation, not a side channel:
- **Write** a file → `REG-5` write authorization on `platform.file` for that `(tenant, schema)` under the caller's
  token/grant, plus the usual bitemporal + provenance stamping; the Kernel stores the bytes and writes the
  record atomically (hash computed server-side).
- **Read** a file → `REG-6` read authorization on the record; **consent** (ADR-0103 `access.grant` / per-object
  sharing) governs cross-owner reads; a **decision record** governs a release that needs a human/however the
  schema's policy dictates; every read/write appends to the **audit** log (who, when, which file, outcome) —
  identical to record audit. No “public blob” — a public file is a record whose read policy is public, served
  by the Kernel after the same check.

## c. Components reach files ONLY via the broker

A component never sees blob storage or the filestore. It calls broker capabilities under its **run token** and
**declared scopes** — `file.read` / `file.write` (already the intended ADR-0030 seam) — and the broker calls
the Kernel, which authorizes against the component's grant exactly as for `data.read`/`data.write`. A file
scope is declared in `meta.yaml` (`scopes: [{verb: read, scope: platform.file/<role>}]`) and awarded at
install like any other. **Component source delivery stops being special:** the **runtime manager** (not the
launcher inside the component sandbox) fetches a component's certified source from the Kernel as a file read
under the runtime-manager's own identity, verifies the dir-digest against the certificate, and places it —
closing gap FIND-R13 (the launcher's direct filestore read from inside the sandbox).

## d. Large files bypass the Kernel body, not its decision

The Kernel always makes the **authorization decision**, but need not proxy large bytes. On an authorized read
(or write) of a large file, the Kernel issues a **short-lived, single-use, signed link** (HMAC/signature over
`{file_id, op, exp, nonce}`, ~30–60s, one-shot nonce burned on use) that the client redeems **directly against
blob storage** (or a thin byte-relay that verifies the signature). Small files stream through the Kernel
inline. Either way the decision, consent and audit happen at the Kernel first; the link carries no standing
authority and cannot be replayed. This keeps big uploads/downloads (media, bundles, archives) off the Kernel's
request path without opening the store.

## e. REG-14/REG-17 encryption + erasure apply to files

Bytes at rest are encrypted per the registry's field-level scheme (ADR-0126 / REGISTRY REG-17): the Kernel
envelope-encrypts the blob with a Vault-transit data key keyed by `(tenant, sensitivity)`; `restricted`/`secret`
files are always encrypted, `public` may be clear.

**Erasure is deletion (REGISTRY REG-17).** Erasing a file **deletes the bytes** — the primary mechanism, not
crypto-shredding. Because content-addressed bytes may be referenced by more than one owner's `platform.file`
record (dedup), the Kernel **reference-counts** them: deleting one owner's record removes that reference, and
the **underlying bytes are deleted only when no remaining owner references them**. **Key destruction is used
only for backups and replicas** — copies that cannot be deleted in place (immutable snapshots, off-site
replicas); there, destroying the per-`(tenant, sensitivity)` data key renders the copy unrecoverable, which is
why the key domain must be narrow enough that shredding one subject's key does not strand another's data.
Legal-hold suspends erasure. (This aligns the files path with REG-17's "erasure = deletion; key destruction only
where content cannot be deleted in place.")

## f. Migration from the current filestore + its ~23 callers

1. Stand up `platform.file` (governed schema) + the Kernel file endpoints + blob storage behind the Kernel;
   keep `filestore:8095` running.
2. Dual-write: the Kernel file-write also writes a `platform.file` record; back-fill records for existing
   content-addressed blobs (owner/sensitivity inferred from the `platform.component_asset`/app-bundle facts
   that already reference them, default `internal`).
3. Move callers off direct filestore HTTP to the Kernel/broker, in dependency order (see below). The shadow
   `svc:filestore` gate stays on throughout as the backstop.
4. Flip reads/writes to Kernel-authorized; turn `filestore:8095` into a dumb blob backend reachable only by the
   Kernel (bind to the Kernel’s network only), or replace it with the object store.
5. Retire the `svc:filestore` ingress gate (DEBT-A72) once no caller talks to the store directly.

## What changes, per component (design only)

- **Kernel:** new `platform.file` schema + `POST /v1/files` (authorized write, hashes + encrypts + writes
  record), `GET /v1/files/{id}` (authorized read; inline small, signed-link large), `DELETE` (REG-17 erasure = delete
  the bytes; reference-counted dedup so bytes go only when no owner references them; key destruction only for
  backups/replicas); REG-5/REG-6/consent/decision/audit reuse; Vault-transit integration; signed-link mint+verify.
- **Broker:** `file.read`/`file.write` capabilities mapped to the Kernel file endpoints under the run token +
  declared file scopes; large-file path returns/redeems the signed link; never exposes `blob_ref`.
- **app-host:** replace all ~16 direct `FILESTORE_URL` reads/writes with broker/Kernel file calls under the
  app-host identity; public-page assets become Kernel reads of `public`-sensitivity files (no change to the
  “App Host proxies, store never public” property — it becomes inherent).
- **launcher:** **stop** reading the filestore from inside the component sandbox (remove the direct source
  fetch); it receives already-placed, digest-verified source from the runtime manager.
- **runtime manager:** fetches component source as a Kernel file read under its own identity, digest-verifies,
  places it for the launcher; owns the one privileged source-read path.
- **blob storage:** a Kernel-only backend (object store or disk), encrypted at rest, reference-counted dedup (bytes deleted only when unreferenced),
  signed-link redemption endpoint for large objects; not routable from any other service.

## Order of work

1. `platform.file` schema + Kernel file endpoints (small-file inline) + blob backend behind the Kernel; audit.
2. Broker `file.read`/`file.write` under run token + scopes; migrate ENGINE/driver reads (closes the
   launcher/runtime-manager split, FIND-R13).
3. REG-17 encryption at rest + erasure-by-deletion with reference-counted dedup (key destruction only for backups/replicas).
4. Large-file signed-link path.
5. Migrate app-host (the 16 sites) to Kernel/broker; back-fill `platform.file` records; dual-write.
6. Seal `filestore:8095` to Kernel-only; retire the `svc:filestore` shadow gate (DEBT-A72) and the interim caller
   wiring.

This replaces the per-caller `svc:filestore` wiring entirely: once files are Kernel-mediated records, there is
no filestore for callers to be allow-listed against — authorization is the registry's, uniformly.

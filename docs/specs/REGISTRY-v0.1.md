# REGISTRY-v0.1 — The governed registry: record rules

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] — the authority model (§3) and principles F1–F17 are assumed, not
restated. This spec governs **the records themselves**: identity, versioning, time, authority on
read/write, provenance, signatures, resolution, schemas-as-records, audit, domain-blindness, personal-data
erasure, public designation, and archiving. Where a rule is an application of a FOUNDATIONS principle, it
cites it (e.g. "F8") rather than re-deriving it.
**Debt references** are to `../consolidation/DEBT-REGISTER.md` (A1–A61 transitional mechanisms, B1–B18
invariant violations). `file:line` live in the per-service nested repos. *(to confirm)* = not traced in
this pass; flagged, not asserted.

**Status legend:** **IN PLACE** (implemented and enforced) · **PARTIAL** (mechanism exists but gated
off/shadow, or only on one path) · **VIOLATED** (the rule is contradicted in live code) · **PLANNED**
(decided/needed, not yet built) · **TO CONFIRM** (not verified this pass).

---

## Record rules

### R1 — Permanent identifiers
Every registry object has a permanent identity that never changes and is never reused. A record is addressed
by `(id, schema, version)`; the id outlives any one version. Deletion/retraction does not free the id.
- **Status: IN PLACE.** Native single-table bitemporal registry keys records by permanent id + schema +
  version (`rv_schema`, `rv_live_schema_id` index). Bitemporal correctness proven (debt task P1 / #125).
- **Refs:** supports F2 (recorded state is the authority); no debt against R1. Reuse-after-retract **(to
  confirm)** — verify retract does not permit an id to be re-bound by a later create.

### R2 — Schema-governed writes
A write is accepted only if it validates against the governed schema named in the record. Schemas are
versioned; a write names the schema version it conforms to. No ungoverned/ad-hoc shapes.
- **Status: PARTIAL.** Schema validation is enforced at write and at certify-time (Tier-4 output
  conformance). The transitional per-schema exception set `SCHEMA_SHADOW_SCHEMAS` is now **empty** (A12), so
  no schema is currently exempted — but the mechanism remains and can re-open exceptions.
- **Refs:** A12 (shadow-schema exceptions, now empty — remove the mechanism); ADR-0025 (signed schema
  catalog). Backward-compat gate at approval is **PLANNED** (diff-gate, task #138).

### R3 — Versions, not edits (supersede / retract)
A record is never mutated in place. A change is a new version that **supersedes** the prior; a withdrawal is
a **retract** that marks the lineage inactive. Prior versions remain addressable (subject to R14/R16).
- **Status: IN PLACE.** Append-only versioning with supersede + attributed retract.
- **Refs:** ADR-0052 (authenticated, attributed registry writes; W3C-PROV; retract). No open debt against
  R3 itself; the authority to supersede/retract is R5.

### R4 — Valid time and recorded time
Every version carries both **valid time** (the period the fact is asserted to hold, `observed_at`/period)
and **recorded time** (when the registry learned it). Queries are answerable "as of" either axis.
- **Status: IN PLACE.** Bitemporal store; time-scrubber and "as-of" reads use `observed_at` as the valid
  period; recorded time is the transaction axis.
- **Refs:** registry bitemporal correctness (B1–B4 of the P1 slice, task #125). No open debt against R4.

### R5 — Write authority
A write is authorized only by a live, recorded grant for (principal, action, schema/scope) — never by the
principal's token role, tenant name, membership, or the data's classification (F2; FOUNDATIONS §3 decision
function). The Kernel is the single enforcement point (F7).
- **Status: PARTIAL / VIOLATED on the authority source.** The single write gate exists (P0, task #124), but
  (a) authority is still largely read from **token role claims**, not recorded grants (B1 — the dominant
  violation); (b) three enforcement switches ship **off/shadow**: `PROV_ENFORCE` (A2), `DATAPLANE_ENFORCE`
  (A3), `REQUIRE_STEWARD_GRANT` (A4); (c) `is_platform_authority` is derived from a **tenant name** (B2,
  A17 — ADR-0122 target: a recorded `platform.authority` role).
- **Refs:** B1, B2; A2, A3, A4, A17; F2, F5-class authority; ADR-0052, ADR-0122.

### R6 — Read authority; no anonymous reads; existence checks are reads
Reads require authority too. There are **no anonymous reads** in production. An **existence/`exists` check,
a resolve, or a count is a read** and is subject to the same read authority as fetching the body — presence
is itself information.
- **Status: VIOLATED (production posture).** `REQUIRE_AUTH` defaults **OFF** (A1), admitting unauthenticated
  tenant reads in transition. Existence/resolve/count paths exist (`/v1/registry/exists`, resolve,
  count pushdowns) but whether each applies read authority **before** answering is **(to confirm)** —
  verify `exists`/`count`/`resolve` are gated identically to body fetch, not treated as metadata.
- **Refs:** A1 (REQUIRE_AUTH off); B6 (unauthenticated **identity** directory disclosure — a sibling
  surface, not the kernel, but the same "presence is information" breach); F8 (fail-closed), F6-class read
  authority. Per-object read authority primitive exists but **0 prod schemas opt in** (ADR-0103 /
  ownership-access status).

### R7 — Provenance
Every version records its provenance: the agent/activity that produced it, inputs/derivation where
applicable, and confidence/lineage pins. A derived record points at what it was derived from.
- **Status: PARTIAL.** W3C-PROV provenance is modelled and written; `prov.derivation` pins lineage and
  confidence. Enforcement that **every** write carries attribution is gated by `PROV_ENFORCE` in
  **shadow** (A2), so unattributed writes are still admitted-and-logged rather than rejected.
- **Refs:** A2; ADR-0052 (attributed writes), ADR-0041 (lineage & confidence); F7/F2. Reference services
  that write **direct to the registry** bypass broker attribution (A40) — **(to confirm)** which paths.

### R8 — Kernel signature (+ participant signature where keyed)
Each committed version is signed by the Kernel so the record is tamper-evident. Where the writing
participant holds keys, the record **also** carries the participant's signature, so authorship is provable
independent of the Kernel.
- **Status: PARTIAL / TO CONFIRM.** Kernel-side attributed-write signing exists (ADR-0052); participant
  message signing (Ed25519 + X25519) exists for federation envelopes. Whether a **registry version** uniformly
  carries a participant signature *where the writer is keyed* (vs. only Kernel attribution) is **(to
  confirm)**.
- **Refs:** ADR-0052; participant message signing (Ed25519/X25519); F7. Dual-signature coverage = **(to
  confirm)**.

### R9 — Idempotent writes
A write is idempotent on content: re-submitting a byte-identical version for the same (id, schema) creates
**no new version**. Only a content change produces a new version (R3).
- **Status: TO CONFIRM.** Content-hash idempotency is the intended behaviour and `write_many` returns a
  server-confirmed count (task #285), but that no identical re-submit creates a version is **not verified**
  this pass — confirm the write path compares a content hash before versioning.
- **Refs:** none asserted; **(to confirm)** against the write path. Relates to R3.

### R10 — Deterministic resolution
Resolving a reference (`id`, identifier, or `ref://…`) yields the same version for the same inputs and as-of
time — resolution is a pure function of recorded state, with a defined tie-break (latest live version at the
as-of instant), never order-of-insertion or node-local state.
- **Status: IN PLACE.** `registry_resolve` / `resolve_by_identifier` resolve deterministically with SQL
  id-prefix pushdown; the federation resolver (`/v1/resolve-ref`, `rule://steward/id` via directory) is the
  cross-participant form.
- **Refs:** C5 (belt-and-suspenders post-filter duplicates the SQL pushdown — a cleanup, not a correctness
  gap); federation-resolve status. No open correctness debt against R10.

### R11 — Schemas are records; scoped ownership; adoption ≠ ownership
A schema is itself a governed registry record (R1–R8 apply to it). A schema has a **scoped owner** (the
steward who may evolve it); **adopting/using** a schema is a separate act from **owning** it — a tenant that
writes records under a schema does not thereby own or control it.
- **Status: PARTIAL.** Schemas are governed records in a signed catalog (ADR-0025). Scoped ownership and the
  adoption-vs-ownership split are modelled, but two grant representations coexist
  (`role_grant`/`role_assignment` vs. the shadow-only `CapabilityGrant` — A18), the `role_assignment@0.1.0`
  `network` field is overloaded (A22), and the per-object ownership/access primitive is **live but adopted
  by 0 prod schemas** (ownership-access status). Enforcement that adoption confers no ownership = **(to
  confirm)**.
- **Refs:** A18, A22; ADR-0025, ADR-0103 (per-object access.grant), ownership-access status; F2.

### R12 — Audit of trust-bearing records
Every create/supersede/retract of a **trust-bearing** record (grants, role assignments, schema changes,
public designations, consents, erasures) is audited: who, under whose authority, when, and the before/after.
The audit is durable and tamper-evident.
- **Status: PARTIAL.** An admin audit trail exists for governance writes, but (a) **failed authentication is
  not logged** (A9 — no trail of forged/failed auth); (b) the audit ring falls back to **in-memory when the
  DB is down** (B10), losing durability exactly when it matters.
- **Refs:** A9, B10; F12 (auditable). Trust-plane role_assignment carries `granted_by`/op_id + audit chain
  (per F14) — coverage across **all** trust-bearing record types = **(to confirm)**.

### R13 — Domain-blind
The registry (and the Kernel enforcing it) carries **no domain vocabulary**. It does not special-case
particular schemas, prefixes, or field names; domain meaning lives in schemas and components, never in the
enforcement core.
- **Status: VIOLATED.** The Kernel is not domain-blind: hardcoded natural-key lists (`_NAT_KEYS`:
  gstin/cnr/udise…), hardcoded data-plane prefixes (`cell./geo./air./…`), event-skip prefixes, and a public
  allow-list (`viz.layer`/`ref.*`) are all baked into the Kernel.
- **Refs:** B8 (kernel not domain-blind), B7 (classification/prefix drives authz); FOUNDATIONS
  domain-blindness principle. Removing these is a decided direction (governed vocab as `ref.domain` data) —
  **PLANNED**.

### R14 — Personal data in a separate, erasable store
Personal data is **not** held in the versioned (append-only) record. The versioned record holds a
**reference and a content hash** only; the personal data lives in a **separate erasable store**.
- **Erasure deletes the content** from the erasable store and **records the erasure** (an audited erasure
  event against the reference), leaving the versioned lineage intact but its content-reference tombstoned.
- **Key destruction is for backups and replicas only** — where content cannot be deleted in place (immutable
  backups, replicas), erasure is effected by destroying the content-encryption key, rendering it
  unrecoverable; this path is **not** a substitute for deleting live content.
- **Erasure cascades to recipients via consent** — recipients who obtained the data under a recorded consent
  (FOUNDATIONS F13 / ADR-0125) are notified/required to erase; the cascade follows the consent graph.
- **Refusal requires a recorded legal basis** — a refusal to erase is itself a recorded, audited decision
  citing the legal ground; silent refusal is not permitted.
- **Status: PLANNED (not yet implemented).** The versioned store is append-only today; a separate erasable
  personal-data store, the reference+hash split, the erasure event, key-destruction-for-backups, and the
  consent cascade are **not built**. Consent exists as a decided primitive but enforcement is pending
  (ADR-0125; B12 for the scope-binding gap). Everything in R14 is **(to confirm)** against any partial
  implementation and otherwise **PLANNED**.
- **Refs:** ADR-0125 (consent primitive, decided; enforcement pending), B12; F13; see **Open item** below
  (DPDP). No erasable-store mechanism exists in the debt register — this rule is new surface.

### R15 — Public is a schema-level designation
Whether records under a schema are public is a property **of the schema**, not of individual records or a
hardcoded list. It is set/changed **only via a ChangeRequest** against the schema and is **audited** (R12).
- **Status: VIOLATED / PARTIAL.** "Public" today is a **hardcoded allow-list in the Kernel**
  (`viz.layer`/`ref.*`), i.e. neither a schema-level field nor changed via ChangeRequest (B8). The
  ChangeRequest spine exists as a decided pattern (every mutation = a CR, ADR-0056) but public-designation
  is not yet routed through it or stored schema-side.
- **Refs:** B8 (hardcoded public allow-list in kernel); ADR-0056 (decided-change-request), ADR-0103
  (per-object sharing/consent); R11, R12. Moving public to a governed schema field changed via CR =
  **PLANNED**.

### R16 — Archiving is in the protocol
Archiving is a first-class, governed operation — not an out-of-band ops action:
- **Archived versions remain resolvable** — a resolve/read of an archived version returns an **identical
  answer** (R10 still holds across the hot/cold boundary).
- **Integrity is verifiable** — an archived version's Kernel/participant signatures (R8) still verify; the
  archive carries the proof.
- **Archiving is not deletion and never bypasses erasure** — archiving moves a version's storage tier; it
  does not remove it from lineage, and it may not be used to evade R14 (an erasure still reaches archived
  copies).
- **Per-schema retention policy** — how long versions stay hot vs. cold, and any retention bound, is a
  governed per-schema policy (R11/R15-style schema-level designation).
- **Archive runs are audited** (R12).
- **Status: PLANNED (not yet implemented).** Hot/cold tiering is a **decided but pending** capability
  (registry = HOT, filestore = COLD) — the governed archive operation, identical-answer guarantee across the
  boundary, per-schema retention policy, and audited archive runs are **not built**. **(to confirm)** against
  any partial tiering.
- **Refs:** registry→filestore archival tiering (task #201, PLANNED); registry physical layout split (task
  #202); R10, R14, R15, R12.

### R17 — Data protection (encryption of sensitive + personal fields)
A schema may mark a field's sensitivity; the Kernel protects marked fields at the write/read boundary so
plaintext never lands in the versioned record or in logs. Two classes, two mechanisms:

- **`x-sensitivity: personal`** — the field value is **not** stored in the versioned record. The versioned
  record holds a **reference + content hash only** and the value lives in the **R14 erasable store**,
  encrypted there with a per-tenant transit key. **Erasure is real deletion** of the value from the erasable
  store (R14), recorded as an audited erasure event. Crypto-shredding is the R14 backups/replicas path only,
  **never** the primary deletion.
- **`x-sensitivity: sensitive`** (non-personal — e.g. a secret, a bearer-ish token, commercially-confidential
  data) — stored **inline** in the versioned record as a ciphertext envelope encrypted with a **per-tenant
  transit key** (`rec-<tenant>`). Inline ciphertext is append-only like any version; it is **not** erasable by
  deleting it (the versioned lineage is immutable), so `sensitive` MUST NOT be used for personal data.
- **Erasure requires the personal store.** A **derived per-person key does NOT provide erasure** — destroying
  a derived key does not delete the value and leaves ciphertext in an append-only version. Per-person
  separation (via a derived key / HMAC context) is a defence-in-depth and uniqueness aid only; **erasability
  comes solely from the R14 erasable store**, where the value can actually be deleted. Personal data therefore
  always uses the erasable store, never inline encryption.

Supporting rules:
- **Idempotency (R9) over protected fields** — content-identity is compared via a **keyed HMAC of the
  plaintext** under a per-tenant key (`idx-<tenant>`), **never** a plain hash of plaintext (which is
  dictionary-attackable for low-entropy PII) and **never** the ciphertext (transit ciphertext is
  non-deterministic, so equal plaintext yields unequal bytes — comparing ciphertext would break R9). The
  write path decrypts/HMACs to decide "byte-identical version?" without emitting a new version.
- **Searchable protected fields (blind index)** — exact-match lookup on an encrypted field uses a **keyed
  blind index**: store `HMAC(idx-<tenant>, normalise(plaintext))` alongside the envelope and query by that
  digest. This supports e.g. **identity-binding uniqueness (ACCOUNT A3)** — "this national-id / handle is
  already bound" — without a plaintext column. Blind indexes allow equality only (no range/prefix/substring).
- **Decrypt authorization.** Reading a `sensitive` field requires a recorded role covering the purpose.
  Reading a **`personal`** field requires **the subject's consent (ADR-0125) OR a recorded role whose grant
  covers that purpose**, and **every decryption of personal data produces a full decision record (DECISION
  D10)** — actor, subject, purpose, legal/role or consent basis, fields, outcome. An unauthorised read returns
  a **redacted placeholder**, never the ciphertext and never the plaintext.
- **Kernel→Vault identity.** The Kernel calls Vault with **its own service identity** (ADR-0124), under a
  policy limited to `transit/encrypt`, `transit/decrypt` and `transit/hmac` on `rec-*` / `idx-*` keys — it
  **never** uses the root token, and **fails closed** (reject the write/read) if Vault is unreachable.
- **Key-use audit.** Every encrypt/decrypt/hmac is audited in **both** the Kernel audit chain (R12) and
  Vault's own audit device, recording `{op, kid, key_version, field_path, record_id, actor, decision}` and
  **never** the plaintext or ciphertext.
- **Filestore blobs — next slice (PLANNED).** Encrypting filestore blobs (per-blob `transit/datakey` + an
  AES-GCM envelope) is noted as a following slice, not part of R17's first cut.
- **At-rest baseline (orthogonal).** Independently of field-level protection, EBS volumes, snapshots and
  database backups MUST be encrypted with a **customer-managed KMS key**. **Status: pending the console check**
  — the instance role cannot read `ec2:DescribeVolumes`; see `deploy/ENCRYPTION-STATUS.md` §5.

- **Status: PLANNED (not yet implemented).** Nothing in R17 is built: no schema `x-sensitivity`/`x-encrypt`
  honouring, no encrypt-on-write/decrypt-on-read in the Kernel, no blind index, no HMAC idempotency, no
  Kernel Vault service-policy for `rec-*`/`idx-*`. Vault `transit` today signs only (no encrypt/decrypt);
  records persist as plaintext JSONB; Postgres has no pgcrypto. See `deploy/ENCRYPTION-STATUS.md`.
- **Refs:** ADR-0126 (this rule's design); R14 (erasable store — personal), R9 (idempotency), R12 (audit),
  ADR-0124 (Kernel service identity), ADR-0125 (consent), DECISION D10 (decision record), ACCOUNT A3
  (identity-binding uniqueness → blind index); DPDP (Open item). New surface — no debt item exists yet.

### R18 — Files are records
A file is a **governed record** (`platform.file`: owner, schema, content hash, size, sensitivity) **plus
bytes** held in **blob storage reachable only by the Kernel** — never a flat, directly-reachable blob store.
A file's **reads and writes use the same authorization as any record** (R5/R6, consent, decision records,
audit); **components reach files only through the Kernel broker** under their run token and declared scopes.
For **large files** the Kernel makes the authorization decision and then issues a **short-lived, single-use
signed link** so the bytes bypass the Kernel body without bypassing its decision. **R17** (encryption of
sensitive bytes at rest) and **R14** apply: **erasure is deletion** — content-addressed bytes are
**reference-counted** and deleted only when **no remaining owner references them**, with **key destruction
only for backups and replicas** that cannot be deleted in place.
- **Status: PLANNED.** The design is specified ([[KERNEL-MEDIATED-FILES-DESIGN]]); today files live in a flat
  content-addressed filestore reached directly by ~23 callers, behind only the interim `svc:filestore` shadow
  gate (ADR-0124 item 1, debt A72). No `platform.file` record, no per-file authorization, no broker file
  capability, no at-rest encryption or erasure on the bytes yet.
- **Refs:** [[KERNEL-MEDIATED-FILES-DESIGN]]; R5/R6 (authority), R14 (erasure), R17 (encryption), R12 (audit);
  ADR-0030 (broker), ADR-0124 item 1 (shadow gate), A72. New surface — no debt item beyond A72.

---

## Summary of status

| Rule | Topic | Status | Key debt |
|------|-------|--------|----------|
| R1 | Permanent ids | IN PLACE | — (reuse-after-retract *to confirm*) |
| R2 | Schema-governed writes | PARTIAL | A12; ADR-0025 |
| R3 | Versions not edits | IN PLACE | ADR-0052 |
| R4 | Valid + recorded time | IN PLACE | — |
| R5 | Write authority | PARTIAL/VIOLATED | B1, B2; A2, A3, A4, A17 |
| R6 | Read authority; exists=read | VIOLATED | A1; B6; exists-gated *to confirm* |
| R7 | Provenance | PARTIAL | A2, A40; ADR-0052/0041 |
| R8 | Kernel (+participant) signature | PARTIAL / *to confirm* | ADR-0052 |
| R9 | Idempotent writes | TO CONFIRM | — |
| R10 | Deterministic resolution | IN PLACE | C5 (cleanup) |
| R11 | Schemas as records; owner≠adopter | PARTIAL | A18, A22; ADR-0025/0103 |
| R12 | Audit of trust-bearing records | PARTIAL | A9, B10 |
| R13 | Domain-blind | VIOLATED | B8, B7 |
| R14 | Personal data erasable store | PLANNED | ADR-0125; B12; DPDP (below) |
| R15 | Public = schema designation via CR | VIOLATED/PARTIAL | B8; ADR-0056/0103 |
| R16 | Archiving in the protocol | PLANNED | tasks #201, #202 |
| R17 | Data protection (field encryption) | PLANNED | ADR-0126; R14; DPDP (below) |
| R18 | Files are records (Kernel-mediated bytes) | PLANNED | KERNEL-MEDIATED-FILES-DESIGN; A72 |

**Tally:** 4 IN PLACE (R1, R3, R4, R10), **6 PARTIAL** (R2, R5, R7, R8, R11, R12), 3 VIOLATED (R6, R13,
R15), **4 PLANNED (R14, R16, R17, R18)**, 1 TO CONFIRM (R9). R5 and R15 carry a secondary VIOLATED.

---

## Open item

**Legal review — key destruction for backups under DPDP.** R14's "key destruction for backups and replicas"
path (erasing by destroying the content-encryption key where content cannot be deleted in place) needs legal
review against the DPDP Act and its Rules: whether crypto-shredding of immutable backups satisfies the
erasure obligation, how it interacts with retention obligations, and what must be recorded as the refusal
legal basis. **The DPDP erasure provisions come into force 13 May 2027** — R14 enforcement (erasable store,
erasure event, consent cascade, backup key-destruction) must be implementable and reviewed before that date.
Resolve with a DPDP-mapping note before building R14/R16 erasure.

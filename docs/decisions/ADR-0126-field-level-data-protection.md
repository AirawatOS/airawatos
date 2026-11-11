# ADR-0126 — Field-level data protection (encryption of sensitive + personal fields)

**Status:** Proposed (design only — not implemented)
**Date:** 2026-11-05
**Relates to:** [[REGISTRY-v0.1]] **R17** (this ADR is R17's design), R14 (personal data in a separate
erasable store), R9 (idempotent writes), R12 (audit of trust-bearing records); [[ADR-0124]] (Kernel/service
minted identities to Vault); [[ADR-0125]] (consent as a first-class authority primitive); DECISION **D10**
(decision record); ACCOUNT **A3** (identity-binding uniqueness); DPDP Act (erasure provisions in force
2027-05-13). Evidence of the current gap: `deploy/ENCRYPTION-STATUS.md`.

## Context
Nothing in the registry is encrypted at the field level today. Records persist as plaintext JSONB
(`kernel/services/registry/pg_store.py:30`); the only record crypto is a sha256 **integrity** hash
(`store.py:37`). Vault `transit` is used **only for signing** (`network/authority.py:53`); there is no
`transit/encrypt`/`decrypt`. Schemas carry no field-sensitivity annotation the Kernel acts on (only a
record-level `classification`/`_SENSITIVITY` visibility tag). Postgres has no pgcrypto. Filestore blobs are
plaintext. At-rest EBS/snapshot encryption could not be confirmed from the instance role.

Two distinct needs are being conflated: **personal data** (must be **erasable** under DPDP — crypto alone is
not erasure) and **sensitive non-personal data** (secrets/confidential — needs confidentiality, not
erasability). They require different mechanisms.

## Decision
Mark field sensitivity in the schema and protect marked fields at the **Kernel** write/read boundary, with
personal data routed to the erasable store and sensitive data encrypted inline — both via **Vault transit**,
both audited, decrypt-authorized.

1. **Schema annotation.** A field may carry `x-sensitivity: personal | sensitive` (implying `x-encrypt`).
   Governed like any schema change (R2/R11), versioned, auditable. The at-rest type of a protected field
   becomes an envelope/reference, so turning protection on is a new schema **version** (R3), not an edit.

2. **Personal → R14 erasable store (erasure = real deletion).** A `personal` field value is **not** stored in
   the versioned record. The versioned record holds a **reference + content hash** only; the value lives in
   the **R14 erasable store**, encrypted there with a per-tenant transit key. **Erasure deletes the value**
   from the erasable store and records an audited erasure event (R14). Crypto-shredding is the R14
   backups/replicas path only — never the primary deletion.

3. **Sensitive non-personal → inline per-tenant ciphertext.** A `sensitive` field is stored **inline** in the
   versioned record as a ciphertext envelope `{"enc":"vault:v<n>:<ct>","kid":"rec-<tenant>","v":<ver>}`
   encrypted with the **per-tenant transit key** `rec-<tenant>`. Inline ciphertext is append-only like any
   version and is **not** erasable in place; therefore **`sensitive` MUST NOT be used for personal data**.

4. **Derived per-person keys do NOT provide erasure (explicit).** Per-person separation (a transit derived
   key, or an HMAC person-context) is defence-in-depth and a uniqueness aid only. Destroying a derived key
   does not delete the value and leaves ciphertext in an immutable version — that is **not** erasure.
   **Erasability comes solely from the R14 erasable store.** Personal data therefore always uses (2), never
   inline encryption, regardless of any per-person key.

5. **Idempotency (R9) via keyed HMAC of plaintext.** The write path decides "byte-identical re-submit?" for a
   protected field by comparing `HMAC(idx-<tenant>, normalise(plaintext))` — **never** a plain hash of
   plaintext (dictionary-attackable for low-entropy PII), and **never** the ciphertext (transit ciphertext is
   non-deterministic, so equal plaintext → unequal bytes, which would defeat R9). Equal HMAC + equal
   non-protected content ⇒ no new version.

6. **Searchable fields via keyed blind index.** For exact-match lookup on a protected field, store
   `blind_<field> = HMAC(idx-<tenant>, normalise(plaintext))` beside the envelope/reference and query by that
   digest. Supports **identity-binding uniqueness (ACCOUNT A3)** — "is this national-id / handle already
   bound?" — with no plaintext column. Blind indexes allow **equality only** (no range/prefix/substring).

7. **Decrypt authorization + decision record.** Reading a `sensitive` field requires a recorded role covering
   the purpose. Reading a **`personal`** field requires **the subject's consent (ADR-0125) OR a recorded role
   whose grant covers that purpose**, and **every decryption of personal data emits a full decision record
   (DECISION D10)**: actor, subject, purpose, consent/role basis, fields, outcome. An unauthorised read
   returns a **redacted placeholder** — never ciphertext, never plaintext.

8. **Kernel→Vault identity (least privilege, fail closed).** The Kernel calls Vault with **its own service
   identity** (ADR-0124), under a policy limited to `transit/encrypt`, `transit/decrypt`, `transit/hmac` on
   `rec-*` and `idx-*` keys. It **never** uses the root token. If Vault is unreachable it **fails closed** —
   a protected write is rejected and a protected read returns the redacted placeholder; neither silently
   stores or returns plaintext.

9. **Key-use audit (both chains).** Every encrypt/decrypt/hmac is audited in the **Kernel audit chain** (R12)
   and in **Vault's own audit device**, recording `{op, kid, key_version, field_path, record_id, actor,
   decision}` and **never** the plaintext or ciphertext.

10. **Key rotation.** `rec-*`/`idx-*` are versioned transit keys; rotation bumps the version, old versions
    decrypt old envelopes, and `transit/rewrap` + lazy re-encrypt-on-next-write migrate forward. Blind-index
    rotation requires re-indexing (recompute `blind_<field>` under the new key) — a governed migration.

### Baseline (orthogonal, decided)
EBS volumes, snapshots and database backups MUST be encrypted with a **customer-managed KMS key**. **Status:
pending the console check** (the instance role lacks `ec2:DescribeVolumes`; steps in
`deploy/ENCRYPTION-STATUS.md` §5). This coarse at-rest layer is independent of, and does not substitute for,
field-level protection.

### Next slice (planned)
Filestore blob encryption — per-blob `transit/datakey` + an AES-GCM envelope — is a **following slice**, not
part of R17's first cut.

## Consequences
- Plaintext PII never lands in `registry_version.object`, in query-able columns, or in logs; personal data is
  genuinely erasable (DPDP), while secrets get confidentiality without pretending to be erasable.
- Protected fields are opaque to filters except equality via a blind index; range/substring search over them
  is out of scope. Query planners must not target encrypted columns.
- A hard Vault dependency on the write/read hot path (mitigated by fail-closed semantics + caching key
  metadata, not plaintext).
- New governed surface: a schema annotation, a Kernel transit policy, the erasable-store reference split
  (shared with R14), and D10 decision records on personal reads. No debt item exists yet; R17 is new.

## Status / implementation
**Not implemented.** This ADR records the design for R17; build is gated behind R14 (erasable store) and the
DPDP timeline (2027-05-13). Conformance cases are registered **NEEDS-BUILD** (see `conformance/run.py`,
REGISTRY R17 / ACCOUNT A3 / DECISION D10).

## Open questions

1. **Per-tenant transit keys as cryptographic tenant separation; crypto-shredding on tenant exit (REG-14)**
   *(added 2026-11-08 with ADR-0130)*. This ADR already chooses **per-tenant** transit keys for field encryption
   (`rec-<tenant>` for inline ciphertext, `idx-<tenant>` for HMAC/blind index; Decisions 2, 3, 5). It is also
   explicit that crypto-shredding is **not** the primary erasure for personal data (Decisions 2, 4: real deletion
   in the REG-14 store). Still open:
   - **Is per-tenant keying a guaranteed property (cryptographic tenant separation) or an implementation
     choice?** As a guarantee, no key may ever be shared across tenants: not for convenience, not for
     platform-level records, not for the filestore blob data keys of the next slice. A tenant's data would then be
     unreadable under any other tenant's key even if a read gate failed (defence in depth for FND-10 / DEBT-B49).
   - **Tenant exit.** When a tenant leaves an installation, are `rec-<tenant>` and `idx-<tenant>` (and the
     tenant's blob data-key wrapping key) **destroyed** after the governed exit export? That would make the
     tenant's inline `sensitive` ciphertext and every backup or replica copy unreadable. It is consistent with
     Decision 2 (shredding is the backups/replicas path) and does not replace REG-14 deletion of the tenant's
     personal values. Open: the exit sequence (export → REG-14 deletion → key destruction), who authorises it (a
     recorded decision by the tenant and the platform authority), and the retention hold that may delay it.
   - **Key scope for the erasable store and blobs.** The same per-tenant key family, or separate keys per store so
     each can be shredded independently?
   - **Hosted participants.** A participant hosted in a shared realm (ADR-0116) is not a tenant; does it get its
     own key, or share the realm tenant's?

## Alternatives considered
- **Application-layer encryption (each service encrypts before write).** Rejected — leaks the obligation
  across every writer, no central audit, and the Kernel can't enforce decrypt-authorization or redaction.
- **Postgres `pgcrypto` / column encryption.** Rejected as the primary mechanism — key management lives in
  SQL, no per-tenant/per-person key story, no blind index, and it doesn't give erasability for personal data.
  (EBS/TDE-style at-rest encryption remains the orthogonal baseline above.)
- **Plain-hash idempotency / ciphertext comparison for R9.** Rejected per decision 5 (dictionary attack;
  non-deterministic ciphertext).
- **Derived per-person key as the erasure mechanism.** Rejected per decision 4 — crypto-shredding a derived
  key is not deletion of an append-only value; erasure must be real deletion in the R14 store.

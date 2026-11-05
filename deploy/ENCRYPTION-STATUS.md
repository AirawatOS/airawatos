# Encryption support — read-only status + field-level design proposal

Snapshot 2026-11-05. Read-only audit of what is / isn't encrypted today, with file:line citations, then a
design-only proposal for field-level encryption via Vault transit. **No code was changed to produce this.**
EC2 was touched only by read-only probes.

---

## What exists today

### 1 · Kernel — record content encryption at write/read: **NONE**
- Records persist as plaintext JSON: `kernel/services/registry/pg_store.py:30` — `object JSONB NOT NULL`; the
  write path `kernel/services/registry/store.py:91` (`put`) stores the object as-is.
- The only record crypto is an **integrity** hash, not confidentiality: `store.py:37`
  `sha256(json.dumps(...))` → `content_hash`.
- `grep -niE 'encrypt|decrypt|cipher|aes|fernet|pgcrypto'` over all of `kernel/` → **zero hits**.
  (`kernel/services/receipts/crypto.py` is receipt **signing**, not record encryption.)

### 2 · Schema format — personal/sensitive field annotation: **NOT SUPPORTED; nothing marked**
- Schemas are JSON-Schema + MDK extensions `x-kind` / `x-subject` (`network/trust/schemas.py:36`). There is no
  field-level `x-sensitive` / `x-pii` / `personal` annotation, and the kernel honours none.
- What exists is **record-level** classification, unrelated to crypto: `network/api.py:1311`
  `_SENSITIVITY = ("public","internal","sensitive")` (INT-0004 seed-copy visibility) and a `classification`
  field on trust membership records. These tag a whole record for visibility/routing — not fields, and no
  encryption.

### 3 · Vault — engines, keys, transit usage
- Mounts (local-dev): `transit`, `secret` (kv v2), `cubbyhole`, `identity`, `sys`.
- transit keys: `airawat-authority`, `airawat-identity`.
- **transit is used only for signing** — every call is `transit/sign/<key>`: `network/authority.py:53`,
  `platform-spec/reference/signing.py:53,88`, `platform-spec/reference/identity.py:363`. There is **no**
  `transit/encrypt` or `transit/decrypt` anywhere. `secret/` (kv) holds service/credential secrets.

### 4 · Filestore — blobs at rest: **NOT encrypted at the app layer**
- Content-addressed, write-once plaintext: `platform-spec/reference/filestore.py:22` (`DATA = FILESTORE_DIR`),
  `:55-59` (`open(tmp,"wb"); f.write(raw)`), `:80` (`open(p,"rb")`).
- local-dev: `FILESTORE_DIR` (default `/tmp/airawat-filestore`; a Docker volume in the dev stack).
- EC2: Docker named volume `airawatos_filestore_data` → `/data/filestore` (`FILESTORE_DIR=/data/filestore`).
  Blobs sit plaintext on that volume (on the instance's EBS).

### 5 · EC2 — EBS / snapshot encryption + KMS key: **IAM-BLOCKED from the instance; check from an operator cred**
- The instance role `AirOS-Jenkins-SecretsReader` is **not authorized** for `ec2:DescribeVolumes`
  (`UnauthorizedOperation`). Instance `i-0870c7bc8bd078a9e`, region `ap-south-1` (az `ap-south-1c`).
- Console: EC2 → Instances → `i-0870c7bc8bd078a9e` → **Storage** → each volume → **Encryption** + **KMS key ID**;
  Snapshots: EC2 → **Snapshots** (owned by self), filter by the volume IDs → Encryption + KMS key.
- CLI (role with the permission):
  ```
  aws ec2 describe-volumes --region ap-south-1 --filters Name=attachment.instance-id,Values=i-0870c7bc8bd078a9e \
    --query 'Volumes[].{id:VolumeId,enc:Encrypted,kms:KmsKeyId,size:Size}'
  aws ec2 describe-snapshots --region ap-south-1 --owner-ids self \
    --query 'Snapshots[].{id:SnapshotId,vol:VolumeId,enc:Encrypted,kms:KmsKeyId}'
  ```
- Interpreting `KmsKeyId`: `alias/aws/ebs` (or the account default EBS key) ⇒ **AWS-managed**; a distinct
  `arn:aws:kms:...:key/...` whose alias you own ⇒ **customer-managed**. `Encrypted:false` ⇒ unencrypted.

### 6 · Postgres — pgcrypto / encrypted columns: **NONE**
- `select extname from pg_extension` → only `plpgsql` on **both** local-dev (`airawat-ld-postgres`) and EC2
  (`airawat-postgres`). No pgcrypto, no encrypted columns, no TDE. EBS-level encryption (§5) is the only
  possible at-rest layer.

### Adjacent (not record-at-rest)
`platform-spec/reference/app_host.py:1077-1100` implements X25519 → AES-256-GCM **sealed-box** encryption and
`:5992` decrypts citizen inputs — that is **federation/embed message sealing in transit** between participants
(reference app-host), not kernel record storage.

## Summary

| area | encrypted today? |
|---|---|
| Kernel registry records (any field) | ❌ plaintext JSONB; sha256 is integrity only |
| Schema field sensitivity annotation | ❌ none; only record-level `classification`/`_SENSITIVITY` |
| Vault transit | signing only (no encrypt/decrypt) |
| Filestore blobs | ❌ plaintext on `/data/filestore` |
| EC2 EBS / snapshots | ❓ IAM-blocked from instance — verify from operator cred (§5) |
| Postgres | ❌ no pgcrypto / encrypted columns |
| Federation/embed messages | ✅ X25519+AES-GCM **in transit** (app-host), not at rest |

---

## Design-only proposal — minimum field-level encryption via Vault transit

Encrypt annotated fields at the kernel boundary so plaintext PII never lands in `registry_version.object` or in
logs, with per-tenant/per-person keys and audited key use. **Design only — not implemented.**

1. **Schema annotation (one new marker).** On a field: `"x-encrypt": true` + `"x-encrypt-scope":
   "tenant" | "person"` (default `tenant`); optionally reuse `x-sensitivity: personal|sensitive` as the human
   label that implies `x-encrypt`. Governed like any schema change (versioned, auditable). The field's at-rest
   type becomes an **envelope object**, so backward-compat = a new schema version.

2. **Kernel write path (encrypt-on-write).** In `registry store.put()`, after schema-validate and before
   persist: walk the live schema for `x-encrypt` fields; for each present plaintext value call
   `transit/encrypt/<key>` and replace it with `{"enc":"vault:v<n>:<ct>","kid":"<key>","scope":"...",
   "ctx":"<b64>"}`. Persist the envelope. **Compute `content_hash` over the envelope** so dedup / immutability /
   bitemporal still hold. If transit is unreachable, **fail closed** (reject the write).

3. **Kernel read path (decrypt-on-read, authz-gated).** On resolve/query, decrypt an enveloped field via
   `transit/decrypt/<key>` **only when the caller is authorized to see that field** (tie to the existing
   per-call authz + the record's tenant/owner). Unauthorized / aggregate / cross-tenant reads get the envelope
   or `"[redacted]"` — never plaintext. Encrypted fields are opaque to filters/queries (document the
   constraint).

4. **Per-tenant + per-person keys (no key explosion).** Use transit **derived keys** (`derived=true`): one
   transit key per tenant (`rec-<tenant>`); for `x-encrypt-scope: person` pass `context = HMAC(person-id)` so
   Vault derives a per-person key from the tenant key — no key-per-person provisioning, and a person's data is
   cryptographically separable (supports per-person erasure by dropping their context lineage). Naming mirrors
   the existing `steward-<tenant>` signing convention (`network/authority.py:226`).

5. **Logged key use.** Every encrypt/decrypt emits a kernel audit event (`platform.audit_event`, the existing
   hash-chained chain) with `{op, kid, key_version, field_path, record_id, actor, decision}` — never the
   plaintext/ciphertext. Also enable the **Vault audit device** for an independent transit-op log. Same
   "provenance via audit link" property ADR-0124 relies on.

**Scope boundaries for the minimum:** kernel registry fields only (filestore blobs would need a parallel
envelope via `transit/datakey` + AES-GCM — out of this slice); EBS/RDS at-rest encryption (§5) is the
orthogonal coarse layer and should be confirmed/enabled regardless; **rotation** rides transit key versions
(`rewrap` on rotate, lazy re-encrypt on next write).

_Read-only status + design. Nothing applied to production._

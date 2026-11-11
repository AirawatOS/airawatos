# FACT migration plan — kv namespaces → governed registry records

**Date:** 2026-11-06 · **Relates to:** [[ADR-0123]] (Kernel holds its own trust records), §Step 4a kv matrix
(`docs/operator/INSTALLER.md`), §Step 4b (split-role DB, SHIPPED), FOUNDATIONS FND-2/FND-7, debt DEBT-B9.

## Why

§Step 4b split the shared `kv` table into `kernel_kv` / `network_kv` so each service owns its own physical
table. That is an **isolation** fix, not a **modelling** fix: the rows inside those tables are still opaque
JSON blobs in a key-value store, outside the governed, bitemporal, attributed, audited registry. Most of them
are **facts** — authoritative state the platform should hold as first-class `registry_version` objects under a
named schema, not as `kv(store,key,value)` tuples.

This plan classifies every `kv` namespace as a FACT with a target registry schema, merges the duplicated
records into canonical ones, and sequences the migration so that **each Kernel→Network authorization call
(ADR-0123 / DEBT-B9) is deleted as soon as the fact it depends on lands in the Kernel registry.**

**Classification principle.** A `kv` namespace is a **FACT** when its rows are authoritative state other code
decides from (identity, authorization, catalog, membership, tenancy). It is **operational/ephemeral** (stays
in kv, or moves to the event/queue spine, not the registry) when its rows are transient request/queue state
with no standing authority. Every live namespace today is a FACT; the empty operational namespaces are marked.

## Namespace → FACT → target schema

Owners/rows from the §Step 4a matrix (live rows as of 2026-11-03).

| namespace | owner | rows | kind | target registry schema | ADR-0123 call it retires |
|---|---|---:|---|---|---|
| `trusted_issuers` | network | 2 | FACT (authority keys) | `governance.trusted_issuer` | `authn.py:103` JWKS/authority-key fetch |
| `certificates` | network | 8 | FACT (certification) | `governance.certificate` | — |
| `roles` | network | 9 | FACT (authority) → **merge** | **`governance.role_assignment`** (canonical) | `app.py` grant/role resolution (DEBT-B9) |
| `participation` | network | 6 | FACT (membership) → **merge** | **`network.membership`** (canonical) | — |
| `networks` | network | 2 | FACT (network identity) → **merge** | **`network.network`** (canonical) | — |
| `tenants` | network | 6 | FACT (tenancy + classification) | `network.tenant` | `app.py:1816,1819` `_net_get("/v1/tenants")` tenant/dev classification |
| `schemas` | network | 21 | FACT (schema catalog) | `platform.schema` (registry already is the schema store; this is the catalog mirror) | `app.py:1287,2243` `NETWORK_URL/v1/schemas` |
| `domains` | network | 5 | FACT (vocabulary) | `ref.domain` (governed vocab already exists) | — |
| `listings` | network | 8 | FACT (marketplace) | `marketplace.listing` | — |
| `tenant_datasets` | **kernel** | 4 | FACT (dataset registration) | `platform.tenant_dataset` | — (kernel-local already) |
| `installed` | kernel | 0 | FACT (install state) ⚠ holds live run tokens — see debt | `platform.install` (token → hash-only, step 5 debt) | — |
| `installed_schemas` | kernel | 0 | FACT (install state) | `platform.install_schema` | — |
| `cases` | kernel | 0 | FACT (case spine) | `platform.case` (schema exists, ADR-0048/0270) | — |

**Operational / not-registry (stay in kv or move to the event-message spine ADR-0089, not here):**
`inbox`, `events`, `email_codes`, `role_requests`, `schema_requests`, `pack_requests`, `interface_requests`,
`store_publish_requests`, `data_requests`, `service_transactions`, `joins` — these are request/queue/outbox
state, not standing authority. The remaining declared-but-empty network namespaces (`participants`,
`offerings`, `packs`, `keystore`, `grants`, `solutions`, `actor_keys`, `interfaces`, `bindings`,
`service_offerings`, `jurisdictions`, `credentials`, `file_shares`, `network_services`) each get a FACT schema
when they first carry rows, following the same pattern; none are migrated until populated.

## Duplicate merges (one canonical record, not three representations)

Three namespaces are **second representations** of state the governed model already names. They do not get a
1:1 schema — they fold into the canonical record and the kv namespace is retired:

- **`networks` → `network.network`.** Network identity (id, slug, name, authority) is already the ADR-0119
  Trust-plane record. The kv `networks` rows are a projection; migrate by writing each as a `network.network`
  registry object (keyed by the ULID, not the slug — net:id ≠ slug, per the Network Console memory), compare,
  then read from the registry.
- **`participation` → `network.membership`.** ADR-0116 made membership tenant-free (`network.participation` /
  `/v1/participation/{request,decide}`). The kv rows become `network.membership` registry objects; the
  request/decide **events** stay operational.
- **`roles` → `governance.role_assignment`.** ADR-0052/0026/0028 already define attributed role assignment.
  The kv `roles` rows (9) merge into `governance.role_assignment` with W3C-PROV provenance (op_id + role.assign
  audit — the `TRUST_ENFORCE_STEWARD_PROVENANCE` path already expects this shape), de-duplicating against any
  assignment already governed.

## Migration order

Ordered so each step unblocks the ADR-0123 call removal that depends on it, trust records first:

1. **`trusted_issuers` + `certificates`** — the authority keys the Kernel verifies tokens/signatures against.
   Landing these locally lets the Kernel verify with **no** Network call → delete `authn.py:103`.
2. **`roles` / `participation` / `networks`** — merge into the canonical records above (authority + membership
   + network identity). Unblocks grant/role resolution moving Kernel-local.
3. **`tenants`** — tenant existence + `environment` classification. Landing this → delete the
   `_net_get("/v1/tenants")` classification call (`app.py:1816,1819`).
4. **`schemas` / `domains`** — the schema catalog mirror + vocabulary. Landing the catalog → delete
   `NETWORK_URL/v1/schemas` (`app.py:1287,2243`). (The registry is already the schema *store*; this removes the
   redundant Network *catalog* read.)
5. **`listings` / `tenant_datasets` / `installed` / `installed_schemas` / `cases`** — marketplace + kernel-local
   install/case state; no ADR-0123 call, lowest risk, migrate last.

## Per-namespace method: shadow → compare → switch

Every namespace migrates the same reversible way (mirrors the ADR-0127 / registry dual-run pattern already used):

1. **Shadow.** On each kv write to the namespace, *also* write the governed registry object (same key → a
   deterministic registry id). Reads still come from kv. No behaviour change; purely additive.
2. **Compare.** A divergence probe reads both and logs any mismatch (count + field-level). Run until the
   divergence log is clean over a full exercise of the write paths (and a backfill of the existing rows is
   present in the registry).
3. **Switch.** Flip reads to the registry behind a per-namespace flag; keep the kv write briefly as a
   fallback. When the registry read is proven, stop the kv write and retire the namespace.
4. **For a Kernel→Network call:** only after the fact's registry read is switched on does the hot-path
   `NETWORK_URL` call get deleted (ADR-0123). The Network keeps the record current by a **governed write into
   the Kernel registry** (direction arrow points down), never by being called back.

Reversible at every step: a namespace can fall back to kv by clearing its flag until the kv write is removed.

## ADR-0123 call-removal map (the point of the ordering)

| Kernel→Network call (DEBT-B9) | file:line | removed once this fact is registry-local |
|---|---|---|
| authority / trusted-issuer key fetch | `authn.py:103` | `governance.trusted_issuer` (step 1) |
| grant / role resolution | `app.py` (DEBT-B9 set) | `governance.role_assignment` (step 2) |
| tenant + dev classification | `app.py:1816,1819` | `network.tenant` (step 3) |
| schema catalog read | `app.py:1287,2243` | `platform.schema` catalog mirror (step 4) |

When all four are gone, the Kernel authorizes from its own registry with no Network reachable (FND-7/FND-8), and the
standalone self-sign fallback can be deleted.

## Risks / open questions

- **`installed` run tokens** are stored in plain form (debt — see `DEBT-REGISTER.md`); the migration to
  `platform.install` must store a **hash only** and deliver the token once (step 5 of this slice).
- **Schema catalog vs store.** The registry is already the schema *store*; `schemas` kv is a Network-side
  *catalog*. Migration = make the Kernel's local catalog authoritative and have the Network govern it by
  write; confirm no consumer needs the Network's catalog shape specifically.
- **Backfill ids must be deterministic** (ULID for networks, not slug) so shadow and backfill converge on the
  same registry id; a non-deterministic id makes the compare step never go clean.
- **Out-of-repo readers.** §Step 4a found no cross-service kv reads in `kernel/` or `network/`; a reader
  outside the repo that expects the kv shape would break at the switch — flagged for review before each flip.

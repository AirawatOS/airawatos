# ADR-0066 — National guidelines & rules as shared network assets (cached + version-pinned at the tenant)

- **Status:** Proposed (2026-08-25)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0023 (federation interaction model — the **Data plane**), ADR-0024/0025
  (participant message signing + signed schema/asset catalog — the trust boundary), ADR-0038 (spec
  governance / packs), ADR-0060 (capability-low / instantiation-high), ADR-0065 / `ontology.md` v3
  (a **rule is a fact**; reconstructability = version-pinning; shared vocabulary lives at the Network layer).

## Context

The flood chain revealed the gap concretely. bmc has `risk.flood` but the flood-advisory skill found **0
rules**: the flood-response thresholds were extracted (via `rule-extract`) from the *National Disaster
Management Guidelines — Management of Urban Flooding*, but that document — and its derived rules — were
ingested **only under `ds:kmc:`**, and the broker **scopes reads to the caller's tenant**. So bmc (and every
other city) sees none of the national baseline.

Re-ingesting the same national PDF and re-extracting the same rules into every tenant is wasteful and, worse,
**invites drift** — Kanpur and Mumbai silently ending up with different "national" thresholds. The NDMA
guidelines are *national*; the thresholds derived from them apply to every Indian city identically.

## Decision

Classify **national guidelines and the rules derived from them as shared network assets**, owned by a network
steward, and made available to every tenant through a **cached, version-pinned local copy**.

1. **Three-tier scope** (capability-low / instantiation-high):

   ```
   national  →  network steward (airawat)          the NDMA baseline — governed once
   state     →  state steward (e.g. Maharashtra)   state amendments        [later]
   city      →  tenant (bmc / kmc)                 local specifics + overrides
   ```

   Rule resolution is a **layered union** — *national ∪ state ∪ city* — with conflicts resolved by
   **specificity, then `priority`**: a city rule may tighten or override the national one, but the national
   baseline is inherited, never re-authored. (A city rule `x-specializes` / adds to the national rule.)

2. **`airawat` owns national assets** (this decision). National knowledge + rules live under `ds:airawat:`
   (`knowledge.*`, `governance.rule` / `rule.*`), authored the sanctioned way — **Knowledge app →
   `rule-extract`**, never hand-seeded.

3. **Shared = read-only to tenants.** Only the network authority writes shared assets; tenants are read-only
   on them. Local (state/city) rules are tenant-authored and win by priority.

4. **Sharing model — cached pack (v1).** A tenant does not resolve national assets live on every read.
   Instead:
   - National knowledge + rules are published as a **signed, versioned `network.pack`** (content-hashed).
   - A tenant **subscribes** and materialises a **local cached copy**, marked *shared/cached* (not
     tenant-authored), carrying the **origin steward + pack version + signature**.
   - **Invalidation is by version, not a time guess:** national guidelines change rarely, so refresh only
     when the network's current pack version-hash differs from the cached one.

   The **cross-tenant sharing test happens at cache-fill**: the tenant fetches `airawat`'s signed pack,
   **verifies the network steward's signature** (ADR-0024/0025) before trusting a fact it did not author,
   then materialises it. Subsequent reads are local (fast). This is the first production exercise of the
   federation **Data plane** for a real payload — deliberately chosen because rules are low-volume,
   read-only, and high-stakes.

## Why the cache is more than a perf hack

Because the cache retains the **exact version used**, a `governance.decision_receipt` can pin the national
rule version **as it was at decision time**, even after NDMA updates the baseline years later — a 2027 flood
decision stays explainable under the 2027 rule, not the 2030 one. The cache is therefore part of the
**historical record**, satisfying ontology v3's version-pinning invariant, not merely a copy.

## Alternatives considered

- **Data-at-source (federated resolve).** bmc resolves each national rule live at the network steward, no
  copy. This is the "true federation" endpoint and the resolver already *routes* it — but **remote fetch is
  stubbed** (LIMITATIONS), and a per-read network round-trip is the wrong default for hot-path rule
  evaluation. **Deferred to a follow-on slice**; the read seam we build now is the same one it plugs into.
- **Re-ingest per tenant.** Rejected — wasteful and drift-prone (the problem that motivated this ADR).
- **Promote rules to the schema/vocabulary layer.** Rejected for v1 — a rule is *data* (a governed fact),
  not vocabulary; it belongs in the registry under a steward, shared by reference, not baked into `network.schema`.

## Consequences

- One real seam: the tenant read path gains **own-tenant ∪ subscribed-shared (verified)**. On the current
  co-located single-registry dev stack the union is trivially satisfied; the **cache-fill + signature-verify
  + version-pin** is the substantive, portable part that also works federated.
- Shared assets need a **writer**: `airawat` runs Knowledge-ingest + `rule-extract` to author the national
  baseline; the pack is signed at publish.
- Tenants gain a **subscription + local cache** of national packs; refresh on version change.
- New provenance fields on cached facts: `origin_steward`, `origin_ref`, `pack_version` (+ retained
  signature) so a cached fact is never mistaken for a tenant-authored one.

## Slice plan

1. **v1 (this ADR):** designate `airawat` as national steward → re-home/ingest the NDMA doc under `ds:airawat:`
   → `rule-extract` → national flood rules (current schema) → publish as a signed national pack → bmc
   subscribes → cached local copies (verified, version-pinned) → re-run flood-advisory → the flood expert
   answers for Mumbai. Closes the flood chain, correctly.
2. **State tier:** add a state steward + the layered-union precedence (city > state > national).
3. **Data-at-source:** unstub federated resolve so a tenant can resolve a national asset live (no cache) when
   it wants freshness over latency.

## Non-goals

- Not the full federation data plane (data-at-source) — that's slice 3.
- Not a general cross-tenant data-sharing grant model — this ADR is specifically **shared, network-owned,
  read-only reference/rule assets**, not tenant-to-tenant sharing of operational data.

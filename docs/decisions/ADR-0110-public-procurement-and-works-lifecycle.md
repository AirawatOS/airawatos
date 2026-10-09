# ADR-0110 — Public procurement & public-works lifecycle: one generic, agency-neutral model

- **Status:** Proposed (2026-10-10)
- **Builds on:** [[ADR-0053]] (data-model taxonomy — the owning *function* names the domain, never geometry), [[ADR-0060]] (L0–L4 ladder + `x-kind`/`x-subject`/`x-layer` facets + the one-subject-one-noun rule), [[ADR-0041]] (lineage & confidence — `prov.derivation`)
- **Relates to:** [[ADR-0109]] (the model is folded into a `platform.service_spec`), [[ADR-0052]] (attributed writes), [[ADR-0103]] (per-object sharing — public read of these nouns), public-apps/`/t/<tenant>` (the citizen surface)
- **First instance:** Janaagraha's Public Expenditure Dashboard (PED) over BBMP road works. BBMP / KPPP / Bengaluru / ward / P-code appear in this ADR **only as example data values** — never as schema identity.

## Context

A citizen cannot today see how public money moves from *a tender advertised* → *a work sanctioned* → *a contract awarded* → *a bill paid* → *a road actually built*. The records exist, but scattered across a procurement portal and a works-bill portal, in incompatible shapes, mostly as scans.

Two concrete sources frame the first instance:

- **A procurement portal** (BBMP's case: the Karnataka e-procurement / KPPP portal). A fellow volunteer's site (TenderSir) already republishes this as **clean, machine-readable Parquet** — ~132,000 tenders, ~7,000 for the city corporation, 42 structured columns (tender ref, value, EMD, fee, published/closing/awarded dates, bidders, documents, corrigenda, topics). This side is **ready to ingest today**.
- **A works-bill portal** (BBMP's "Works Bill Public View"). The authoritative execution→payment lifecycle — ~20 document types per work (tender notification, detailed estimate, administrative & technical sanction, contract agreement, work order, BoQ/Schedule-B, measurement book, running/final bill, completion certificate, QC reports, road-history sheet). Per the field survey, **every file is a scan with no text layer** — Kannada OCR, handwriting recognition, and deskew are unavoidable. This side is a **pipeline, not a V1 ingest**.

The platform already has thin, **network-canonical** nouns for part of this (`procurement.tender`, `works.work_order`, `works.contract` carrying defect-liability, `works.payment`, `works.contractor`, plus `geo.road` / `geo.road_segment`), authored for PED's first money-ledger view. But they were shaped *ledger-first*: `procurement.tender` is even `required: work_order`, which is backwards — a tender exists, and 95% of them stay, with no linked work order. They are not yet a lifecycle.

The goal of this ADR is a **single, agency-neutral lifecycle model** that any procuring entity, in any city or state (or country), reuses unchanged — so adding a second agency is a driver-config change, not a schema change.

### The accountability questions the model must answer

From the Radical Transparency concept note and citizen interviews: *What was the tender amount? When should the work have started and finished, and when did it? What is the defect-liability period? Was it delayed, and was time recovered? Was the final bill more than contracted (excess) or less (savings)? Did required quality tests actually happen? Was the winning contractor even eligible? Is the same road billed twice?* Every one of these falls out of the join keys below.

## Decision

### 1. Two function-domains, named for the function, never the place

Per [[ADR-0053]] §1 a schema's domain is *the authority/function that owns it, not its geometry or its city*. So:

- `procurement.*` — the solicitation/award side (any procurement regime).
- `works.*` — the sanction → execution → measurement → payment → completion side (any public-works function).
- the contractor is a party → extend `works.contractor` (an `entity`); reuse `space.*` for jurisdiction (ward/zone/city/state are **fields**, resolved per-workspace per [[ADR-0060]] §4, never schema segments) and `geo.road` / `geo.road_segment` for the physical asset.

**Agency-neutrality is normative here:** no schema id, and no `const`/enum field value, may encode a specific agency, city, state, portal, or statute. `"Bruhat Bengaluru Mahanagara Palike"`, `"KPPP"`, `"P-3863"`, `"ward 202"`, `"KW4"`, `"KTPP Rules 2000"`, `"M20 / MoRTH"` are **data in a row** or optional free-string fields (`procuring_entity`, `budget_ref`, `regime_ref`, `spec_refs[]`), not identity. A statute- or portal-specific quirk that genuinely has no generic home goes in an **`ext` object** (`x-open` with `x-open-reason`), never a first-class required field.

### 2. The generic join spine

These identifiers are what turn ~20 separate document extractions into **one linked record per work**. Each is an opaque string in the generic model; the BBMP *form* is shown only to make it concrete.

| Generic key | Carried on | BBMP example value |
|---|---|---|
| `work_code` | work_order, sanction, agreement, bill, completion, road_segment | `181-25-000009` (ward-year-serial) |
| `tender_ref` | tender, work_order, agreement | `EE/CMP/TEND/E-PROC/07/2023-24` |
| `sanction_ref` (role-tagged) | sanction, completion, agreement | `AS 327/2020-21`, `TS 276/2020-21` |
| `agreement_ref` (+ `stamp_cert_ref`) | agreement, work_order | `…/AGR/…22-23`; `IN-KA10789068233766U` |
| `budget_ref` | sanction, bill, work_order | `P-3863` (+ scheme name as data) |
| `segment_ref` (+ `street_ref`) | road_segment, completion | `25/S-W1415/S12955` |
| `contractor_tax_id` / `contractor_reg_id` | contractor, agreement | GSTIN; licence `Reg No 325` |

`work_code` is the primary key of a work; `tender_ref` is the only link back to procurement; `budget_ref` is the natural grouping key for a ward/scheme expenditure view. One agreement may carry **several** `work_code`s across several wards — the model is many-to-many there (`agreement.work_codes[]`), not one-work-one-contract.

### 3. The lifecycle nouns (full set, all `x-kind: entity` unless noted)

New nouns are proposed at `@0.1.0`; existing thin nouns are **bumped** to a richer generic version (old version retained; drivers migrate).

**Procurement side**
- `procurement.tender` **(bump → @0.2.0, breaking: `required` becomes `tender_ref`, not `work_order`)** — `tender_ref`, `source`, `procuring_entity`, `jurisdiction_ref`, `title`, `description`, `category`, `sub_category`, `topics[]`, `status`, `invite_type`, `eval_type`, `estimated_value`, `accepted_value`, `tender_fee`, `emd`, `bid_validity_days`, `no_of_calls`, `contractor_class`, `published_at`, `closing_at`, `awarded_at`, `period_year`, `bidders[]`, `num_bidders`, `documents[]{file_name,doc_type,uuid}`, `corrigenda[]`, `work_code` *(optional link forward)*, `prov`, `confidence`, `ext`.

**Works side**
- `works.work_order` **(bump → @0.2.0)** — add `tender_ref`, `agreement_ref`, `contractor_ref`, `accepted_amount`, `premium_pct`, `tax_pct`, `completion_period_days`, **`defect_liability_months`**, `supervising_officer` to the existing fields; keep `work_code`/`work_order_no` required.
- `works.sanction` **(new)** — `work_code`, `sanction_ref`, `sanction_date`, `sanction_kind {administrative|technical}`, `is_modified`, `sanctioned_amount`, `authority`, `order_ref`, `budget_ref`, `scheme_name`, `rate_schedule_year`, `package_ref`, `prov`, `confidence`. One noun covers AS and TS via `sanction_kind` (one-subject-one-noun, [[ADR-0060]] §3a).
- `works.agreement` **(new)** — `agreement_ref`, `agreement_date`, `stamp_cert_ref`, `contract_amount`, `premium_pct`, `tax_pct`, `contractor_ref`, `contractor_legal_name`, `work_codes[]`, `sanction_refs[]`, `budget_ref`, `completion_period_days`, `guarantee_months`, `prov`.
- `works.boq_item` **(new, `x-kind: record`)** — `(work_code, line_no)`, `description`, `unit`, `quantity`, `rate`, `amount`, `spec_refs[]`, `is_modified`, `prov`.
- `works.measurement_bill` **(new, `x-kind: record`, `x-subject: works-bill`)** — `work_code`, `bill_no`, `bill_part`, `work_order_ref`, `budget_ref`, `mb_ref`, `mb_pages`, `value_of_work_done`, `reserve_amount`, `previous_paid`, `deductions{}`, `net_payable`, `cheque_ref`, `paid_at`, `is_final`, `prov`. (Complements the existing `works.payment` summary record; `measurement_bill` is the per-bill line with the deduction memorandum.)
- `works.completion` **(new)** — `work_code`, `estimate_amount`, `accepted_tender_amount`, `claimed_amount`, `excess_amount`, `savings_amount`, `sanction_refs[]`, `funding_source`, `scheduled_start`, `scheduled_completion`, `actual_completion`, `delay_days`, `eot_approved`, `mb_ref`, `contractor_ref`, `certified_satisfactory`, `prov`. **The single richest accountability record** — estimate vs tender vs claimed, and planned vs actual dates, side by side.
- `works.quality_test` **(new, `x-kind: record`)** — `(work_code, test_name, sample_no)`, `boq_quantity`, `required_tests`, `actual_tests`, `sampled_at`, `location`, `chainage`, `result_value`, `conforms`, `lab_name`, `prov`.
- `works.road_segment` — reuse the existing `geo.road_segment` entity for geometry; `works.completion`/`works.work_order` reference it by `segment_ref`. (Asset geometry stays in `geo.*`; the works link is a field.)
- `works.contractor` **(bump → @0.2.0)** — add `trade_name`, `tax_id`, `reg_class`, `reg_category`, `licence_valid_from`, `licence_valid_to` (and a redaction note: `address`, `pan`, DOB are **never** published — [[ADR-0103]]).

**Rollups** (`works.ward_rollup`, `works.city_summary`, `works.contractor_rollup`) are currently emitted by a driver but **ungoverned**. Govern them as `x-kind: record` (they are derived aggregates, not measures of a single entity), each carrying `derived_from[]` + `method` ([[ADR-0041]]).

### 4. Promote the whole set to Network governance, agency-neutral

All nouns are proposed as **network-canonical** `ds:airawat:schema/<noun>@<ver>` under the `procurement` and `works` domains (both already registered), via the proven flow: register domain (steward) → propose (`/bridge/schema-request`) → approve (`/v1/schema-requests/decide`, steward). They are then reusable read-only by **any** tenant/agency; the agency's data lives in that agency's tenant, written by its own certified driver. This is the federation stance ([[ADR-0038]]/[[ADR-0094]]): the Network owns the *vocabulary*; each participant owns its *facts*.

### 5. Ingest is source-configurable, never source-hardcoded

One certified driver per source *shape*, parameterised by config — not one driver per city:

- `procurement-tenders` (new) — reads a procurement feed (the volunteer's Parquet for BBMP; a different portal's export elsewhere) via the broker, filters by `procuring_entity` + `topics`, maps → `procurement.tender`. Source URL, entity filter, and topic filter are **config** (`SOURCE_URL`, `ENTITY_FILTER`, `TOPIC_FILTER`), with the host on the driver's `egress` allow-list and a `ref/source` attribution record. No agency name in code.
- The existing `works-register-extractor` (ledger) and `works-ward-rollup` continue; a later `works-lifecycle-ocr` family populates sanction/agreement/boq/quality from the scanned corpus.

## Enforcement

- The schema linters already enforce agency-neutral identity: id must match `^[a-z][a-z0-9]*\.[a-z][a-z0-9_]*$` (no place segment possible), `x-kind` is mandatory, the `(x-subject, x-layer, x-kind)` collision rule blocks a second differently-named clone, and house-rules R1–R6 hold. This ADR adds one **review-time** check: a proposed noun whose `const`/`enum` field values name a specific agency, city, state, statute, or portal is rejected — those are data, not schema.
- PII fields (`address`, `pan`, DOB, photographs, personal phone) carry a `sensitivity` marker and are excluded from any `public_read` allow-list (the `/t/<tenant>` public path).
- Every ingested fact carries `prov` (source + component@version) and, where derived, `derived_from[]` — so a citizen can trace any number on screen back to the source document.

## Slices

- **V1 — road expenditure, by the November demo (Balaga members).** Govern the full lifecycle (this ADR) so the model is complete; **populate** `procurement.tender` (real, from the Parquet) + the existing `works` ledger; join on `work_code`/`tender_ref`/`budget_ref`; surface *approved → contracted → built* per work on the ward map, with delay and excess/savings where present. Road-only is a **filter** (`topics`/`work_type`), not a schema.
- **V2 — early 2027, more sectors + the document lifecycle.** Add parks/lakes (same schemas, different `topics`/`budget_ref`). Stand up the `works-lifecycle-ocr` pipeline (deskew → Kannada+English OCR → handwriting for measurement books → per-document template extractors) to populate `works.sanction/agreement/boq_item/measurement_bill/quality_test` and the compliance ground-truth (required-vs-actual tests, missing-from-inventory roads, duplication checks).
- **V3 — consolidation.** Extend beyond the city corporation to parastatal agencies as additional tenants federating the same vocabulary — the concept note's consolidated city-level view.

## Consequences

- One vocabulary, many agencies: a second city publishes by deploying the driver with new config; no schema work. The federation story becomes concrete for the fiscal-transparency domain.
- The `procurement.tender@0.2.0` `required`-field change is **breaking** against the thin `@0.1.0`; the PED driver and dashboard migrate to `tender_ref`. Old `@0.1.0` rows remain readable (bitemporal registry); the dashboard reads `@0.2.0`.
- The lifecycle entities are governed now but **sparsely populated until V2** — honest coverage/recency/missing-data markers (per the concept note) are shown per record so an empty completion field reads as *"not yet extracted"*, never as *"on time"*.
- OCR quality sets the ceiling on V2; the model does not pretend otherwise (confidence + source-document link on every derived field).

## Non-goals

- Not building the OCR pipeline in this ADR (V2) — only the schemas it will fill.
- Not modelling budget/AFS fiscal-health indicators (own-source revenue, execution ratios) — concept-note component 5.4, a separate `finance.*` ADR.
- Not asserting correctness of source data — the platform mirrors what the agency published, with provenance; discrepancies (sanctioned vs estimate vs bill) are **surfaced as flags**, not silently reconciled.

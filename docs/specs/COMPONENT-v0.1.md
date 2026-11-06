# COMPONENT-v0.1 — Components: build, run, share, list

**Status:** Draft v0.1 · **Date:** 2026-11-05
**Builds on:** [[FOUNDATIONS-v0.1]] (authority model + F1–F17), [[REGISTRY-v0.1]] (records, authority on
read/write R5/R6, provenance, erasure), [[DECISION-v0.1]] (decision records), [[NETWORK-v0.1]] (certification,
store, contribution), [[PLATFORM-v0.1]] (tenant verification status P9, quotas, policy). Where a rule applies
a principle from those specs it cites it (e.g. "F17", "R6", "P9") rather than re-deriving it.

This spec governs **components** — the unit of executable capability on the platform: what a component *is*,
how it runs **privately** in a tenant, how it is **shared** across tenants, and how it reaches a
**marketplace**. The three lanes are deliberately separate:
- **Private lane** (CP2): a tenant builds, installs, runs and schedules its own components, no certification,
  no store.
- **Sharing lane** (CP8–CP9): any cross-tenant use requires certification; the installing admin consents to
  the declared access.
- **Marketplace lane** (CP10, CP14–CP18): contribution to a shared marketplace, two-level permission, listing
  checks, versioned listings, suspension, terms.

**Debt references** → `../consolidation/DEBT-REGISTER.md`. `file:line` live in the per-service nested repos.
**Status legend:** **IN PLACE** (implemented and enforced) · **PARTIAL** (mechanism exists but gated off /
shadow, or only on one path) · **VIOLATED** (contradicted in live code) · **PLANNED** (decided/needed, not
built) · **TO CONFIRM** (not verified this pass).

---

## Component rules

### CP1 — A component is code + a manifest
A component is code plus a **manifest** that declares everything it may touch: the schemas it **reads** and
**writes**, the **files** it uses, the **egress hosts** it may reach, the **named secrets** it needs, the
**capabilities** it requires (notify, model, payment, proofing, …), and its **resource** envelope. The manifest
declares a **required capability, never a specific vendor** — the platform gateway binds the capability to an
approved provider (PLATFORM P16–P18). The manifest is the whole of its authority surface; a component **never
exceeds its declaration** at runtime.
- **Status: PARTIAL.** `meta.yaml` declares reads/writes/scopes/egress/`confinement_min`; the broker + run
  token enforce reads/writes/egress against the declaration (ADR-0030). Named secrets are declared and
  injected by name. **Resources/quotas are not yet declared or enforced** (see CP5/CP11).
- **Refs:** ADR-0030 (SDK/broker/clean-room); REGISTRY R2 (schema-governed writes); PLATFORM P16–P18
  (capabilities via gateways, never vendors); CP3, CP5.

### CP2 — Private lane: build and run in your own tenant, no certification
A person holding a recorded **`component.builder`** or **`component.operator`** role (both included in
`tenant.admin` and separately delegable) may **build, install, run and schedule** components **in their own
tenant** without certification and without any store listing. Private use never leaves the tenant.
- **Status: PLANNED.** Today the equivalent is gated by a **token claim** (`tenant_env` × builder role) in
  app-host, not by a recorded `component.builder`/`component.operator` role (debt **A28**), and the only
  private run path is the **dev-token** sandbox run (ADR-0051/INT-0004), which additionally requires the tenant
  to be a registered Developer participant (finding **D6**) and cannot install/schedule. A first-class private
  lane — recorded roles, install-as-grant within the tenant, no store — is not built.
- **Refs:** A28 (token-claim authority), A50 (`--sandbox` bypass), ADR-0051; resolves finding **D1** (a
  private install must not need a cross-tenant registry grant — the builder role authorizes writing the
  tenant's own component records). CP3, CP9.

### CP3 — The run token is the intersection of declaration and authority
A component's **run token** grants exactly **manifest declaration ∩ the runner's authority** — never more. A
component can do only what it declared *and* what the identity running it is allowed to do.
- **Status: PARTIAL.** Install mints a run token scoped to the **certified declaration ∩ the steward's
  install-time grant** (kernel `_install_one` → `_mint_run_token`; ADR-0063 install=grant). The intersection
  with the **runner's** authority (who pressed Run) is still an upstream token-role check in app-host, not a
  recorded-grant intersection the runner's identity is bound into (A28).
- **Refs:** ADR-0063 (install=grant), ADR-0124 item 1 (scheduler ingress); A28; CP1, CP4.

### CP4 — Schedules record owner and authority; re-checked before each run
A schedule records its **owner** and the **authority** it runs under. The scheduler acts **on behalf of** that
owner and **re-checks the authority before each run**, **suspending** the schedule if the authority is gone.
- **Status: PLANNED.** `platform.schedule` records exist and the scheduler fires them; ADR-0124 item 1 gated
  the app-host→scheduler hop (audience `svc:scheduler`). But the schedule does **not** record the owner's
  authority, and the scheduler does **not** re-verify it before each run or suspend on revocation — run
  authority is still decided by a token role in app-host (A28).
- **Refs:** A28; ADR-0124 item 1; scheduler-platform-service-reach. CP3, CP12.

### CP5 — Isolated runs
A run is **isolated**: **no network access unless declared** (egress hosts in the manifest), subject to
**resource quotas**, with **no platform credentials** in the sandbox. **Secrets are provided by name** through
the **runtime manager**, never embedded.
- **Status: PARTIAL.** Clean-room runtime + broker-only I/O + declared-egress enforcement are live (ADR-0030);
  secrets are injected by name (the component never holds the value). **Quotas are not enforced** (CP11), and
  the component-source fetch path still runs inside the component rather than via the runtime manager (CP7).
- **Refs:** ADR-0030; driver-secrets-vault; CP1, CP7, CP11.

### CP6 — Records and files only via the Kernel broker
A component touches **records and files only through the Kernel broker**, under its run token and declared
scopes. It never reaches a datastore or a blob store directly.
- **Status: PARTIAL.** Records: **IN PLACE** (all component record I/O is broker `/v1/read|write|query` under
  the run token). Files: **PLANNED** — components and services reach the filestore directly today; the
  interim `svc:filestore` shadow gate (ADR-0124 item 1) is a stopgap, and the
  [[KERNEL-MEDIATED-FILES-DESIGN]] folds files into broker/Kernel-mediated records.
- **Refs:** ADR-0030; ADR-0124 item 1; KERNEL-MEDIATED-FILES-DESIGN; A72. REGISTRY R5/R6.

### CP7 — Signed, content-pinned, immutable packages
A component package is **signed**, **content-pinned** (its id carries its content digest) and **immutable**.
The **runtime manager** fetches and **verifies** the source against the certificate **before** a run; the
**component never fetches its own source**.
- **Status: PARTIAL.** Certificates sign the artifact digest; store listings are immutable + monotone per
  `(id, version)` (network `STORE.version_error`); the launcher digest-verifies source against the cert. But
  today the **launcher runs inside the component context** and fetches from the filestore itself (finding
  **D-R13**); the [[KERNEL-MEDIATED-FILES-DESIGN]] moves the fetch+verify to the **runtime manager** so the
  component sandbox never holds a store path.
- **Refs:** launcher `_fetch_and_verify`; ADR-0093/0095; KERNEL-MEDIATED-FILES-DESIGN (runtime-manager fetch).
  Resolves **D-R13**. CP5, CP8.

### CP8 — Sharing beyond the tenant always requires certification
Any use of a component **outside its owning tenant** requires **certification** — there is **no side-loading**
of a cross-tenant component. The **publisher of record is the developer's tenant**; the platform publisher
service acts **on behalf of** the developer (F17) and records them on the publish decision.
- **Status: PARTIAL.** Certify + store resolve + cert-verify are required before any cross-tenant install
  (kernel `_install_one` refuses without a valid cert); the `component.publisher` service may publish
  on-behalf under any steward (`_require_publisher`, F17). **Contradiction (finding D2):** the conformance
  check `steward-is-publisher` requires the publisher's *tenant* to equal the component's steward prefix,
  which **rejects** the F17 on-behalf cross-tenant lane — so "publisher of record = the developer's tenant,
  acting through the publisher service" is specified here but not yet certifiable. Resolve by making the
  conformance rule accept the recorded on-behalf publisher (F17) as the publisher of record.
- **Refs:** F17 (delegation); `_require_publisher`; network/conformance `steward-is-publisher`. Resolves
  finding **D2**. CP2 (private needs none of this), CP14.

### CP9 — Installing another tenant's component requires informed consent
Installing a component published by **another** tenant requires the **installing admin's informed consent** to
its **declared access** (the reads/writes/egress/secrets the manifest declares).
- **Status: PLANNED.** Install mints the steward grant from the **certified declaration** (so the grant can
  neither forget nor inflate beyond the cert), but there is **no explicit consent capture** — the installing
  admin is not shown and does not record acceptance of the declared access. Per-object consent exists for data
  (ADR-0103) but not for install-time access acceptance.
- **Refs:** ADR-0063 (install=grant); ADR-0103 (consent primitive); DECISION (decision record). CP12, CP16.

### CP10 — Unverified tenants: private only, no marketplace
An **unverified** tenant (PLATFORM P9) may **build and run privately within quotas** but **cannot contribute to
marketplaces**.
- **Status: PARTIAL.** The dev↔prod boundary already refuses store-publish from a development tenant (network
  `store_publish` 403; finding **D5**) — the *correct* behaviour reframed by this rule: **D5 is not a bug**,
  it is CP10. What is missing is the **positive** side — a first-class private lane (CP2) so an unverified
  tenant can actually build/run without the store — and quota enforcement (CP11).
- **Refs:** ADR-0106 (dev↔prod boundary); PLATFORM P9; A50. Reframes finding **D5**. CP2, CP11, CP14.

### CP11 — Platform policy sets quotas and allowed egress by verification status
**Platform policy** sets the **quotas** (runs, concurrency, storage, schedule frequency) and the **allowed
egress** a tenant's components may use, **keyed by the tenant's verification status** (PLATFORM P9).
- **Status: PLANNED.** No quota or status-keyed egress policy is defined or enforced; egress is per-component
  declaration only, unmoderated by tenant status.
- **Refs:** PLATFORM P9 (verification status), P6 (platform authority decides policy). CP5, CP10.

### CP12 — Evidence for every lifecycle step
Every **build, install, run, schedule, publish and consent** produces **evidence** (a decision/audit record);
runs produce **run receipts**.
- **Status: PARTIAL.** Publish/certify/governance produce decision + audit records; the scheduler keeps a
  recent-runs ring (`_RUNS`, in-memory) — **durable run receipts are TODO**; build/install/consent evidence is
  incomplete.
- **Refs:** DECISION (decision records); FOUNDATIONS F12 (everything audited); scheduler `/runs`. CP4, CP9.

### CP13 — Solutions are versioned bundles
A **solution** is a **versioned bundle** of components, schemas, apps and config, pinned together.
- **Status: PARTIAL.** Solutions exist as pinned member graphs with closure rules (ADR-0075/0076); versioning
  and config are modelled. Full version-pinning of every member + reproducible install is partial.
- **Refs:** ADR-0035 (solutions), ADR-0075/0076 (anatomy, closure). CP16.

### CP14 — Contribution needs two-level permission
Contributing a component to a marketplace needs **two** permissions: the **tenant** must hold the role
**`component.publisher`** (outbound — this tenant may offer), **and** the **Network** must hold a **contribute
grant** for it (inbound — this marketplace accepts).
- **Status: PARTIAL.** The outbound side exists (`component.publisher` role, `_require_publisher`); the
  **inbound Network contribute grant** is not a distinct, recorded gate — listing is governed by certification
  + store rules, not a per-Network accept decision.
- **Refs:** `_require_publisher`; NETWORK (contribution); CP8, CP15.

### CP15 — Listing checks
Before a component is **listed**, the Network checks: schemas are **Network-approved**; **conformance tests**
pass in a **sandbox**; **signatures and hash** verify; the **declared access is acceptable under Network
policy**; a **security scan** (planned) passes; **licence/terms** are present. The outcome is a **decision
record**; **failures state reasons**.
- **Status: PARTIAL.** Certify runs the conformance suite (governed-vocabulary, id/steward grammar, digest,
  entrypoint) and **withholds with reasons** on failure (422 with the failed checks — observed in findings D2/
  D3); signature + hash verify at install. **Not yet:** a security scan, a declared-access-vs-Network-policy
  gate, licence/terms capture, and a single listing **decision record** spanning all checks.
- **Refs:** network `/v1/certify` (conformance), `/v1/store/publish`; DECISION. Surfaces findings **D2, D3,
  D4** (certify should 422 with reasons, not 500 on bad input). CP8, CP16.

### CP16 — Versioned listings; more access needs re-consent
Listings are **versioned**. Any update that asks for **more access** than the installed version requires the
installer's **re-consent**. There are **no silent upgrades**.
- **Status: PARTIAL.** `(id, version)` listings are immutable + monotone (no silent overwrite; bump the
  version — network `STORE.version_error`). **Re-consent on an access increase** and the no-silent-upgrade
  guarantee at the **installer** are not built (installs are not auto-upgraded, but neither is re-consent
  captured when a tenant chooses a newer, broader version).
- **Refs:** network `STORE.version_error`; ADR-0098 (versioned app install). CP9, CP13.

### CP17 — Suspension is recorded; installed copies survive
The Network may **suspend** a listing with a **recorded reason**; **installers are notified**; already
**installed copies are never silently deleted**.
- **Status: PARTIAL.** Store **revoke/deprecate** endpoints exist with a reason; installed run tokens persist
  (install is local, not a live store lookup per run), so an installed copy is not deleted. **Installer
  notification** on suspension is not built.
- **Refs:** network `/v1/store/{revoke,deprecate}`; events-and-subscriptions. CP12.

### CP18 — Listing terms may include price; value flows per the settlement model
A listing's **terms may include a price**. Value flow follows the **settlement model**: record the **terms**,
the **commitment**, and the **settlement**; **money moves on rails** (the platform records obligations; funds
move through a payment rail, not the registry).
- **Status: PLANNED.** `component.contract` carries pricing/SLA terms (ADR-0046..0050 marketplace work), but
  there is **no settlement model** — no commitment/settlement records and no payment-rail integration.
- **Refs:** component-contracts (ADR-0027/0046); marketplace-data-model-adrs; federated-program-funding
  (settlement precedent). CP14.

---

## Findings → resolving rules

The sample-component pipeline proof ([[PIPELINE-PROOF-FINDINGS]]) surfaced gaps; each maps to the rule that
resolves it:

| Finding | What happened | Resolved by |
|---|---|---|
| **D1** | delivery 403 writing `platform.component_asset` (publisher lacks a cross-tenant registry grant) | **CP2** — a recorded `component.builder` authorizes writing the **tenant's own** component records in the private lane; no cross-tenant grant needed for private build. |
| **D2** | certify 422 `steward-is-publisher` ("airawatdeveloper vs localdev-network") rejects the on-behalf lane | **CP8** — publisher of record = the developer's tenant, the publisher service acts **on behalf** (F17); the conformance rule must accept the recorded on-behalf publisher. |
| **D5** | store-publish 403 for a development tenant | **CP10** — correct, not a bug: unverified tenants run **privately** (CP2) and **cannot contribute to marketplaces**; contribution is the separate CP8/CP14 path. |
| **launcher** | the launcher fetches component source from inside the component context | **CP7** — the **runtime manager** fetches + verifies the signed, content-pinned package; the component never fetches its own source. |

---

## Summary of status

| Rule | Lane | Status | Key debt / refs |
|---|---|---|---|
| CP1 | all | PARTIAL | ADR-0030; quotas CP11 |
| CP2 | private | PLANNED | A28, A50; D1, D6 |
| CP3 | private | PARTIAL | A28; ADR-0063 |
| CP4 | private | PLANNED | A28; ADR-0124 item 1 |
| CP5 | private | PARTIAL | ADR-0030; CP11 |
| CP6 | all | PARTIAL (records IN PLACE, files PLANNED) | ADR-0124 item 1; A72; KERNEL-MEDIATED-FILES |
| CP7 | all | PARTIAL | D-R13; KERNEL-MEDIATED-FILES |
| CP8 | sharing | PARTIAL | D2; F17 |
| CP9 | sharing | PLANNED | ADR-0103; ADR-0063 |
| CP10 | marketplace | PARTIAL | D5; ADR-0106; A50 |
| CP11 | marketplace | PLANNED | PLATFORM P9 |
| CP12 | all | PARTIAL | DECISION; F12 |
| CP13 | marketplace | PARTIAL | ADR-0075/0076 |
| CP14 | marketplace | PARTIAL | NETWORK contribution |
| CP15 | marketplace | PARTIAL | D2, D3, D4 |
| CP16 | marketplace | PARTIAL | ADR-0098 |
| CP17 | marketplace | PARTIAL | events-and-subscriptions |
| CP18 | marketplace | PLANNED | component-contracts; settlement |

**Tally:** 18 rules — 0 IN PLACE, **13 PARTIAL** (CP1, CP3, CP5, CP6, CP7, CP8, CP10, CP12, CP13, CP14, CP15,
CP16, CP17 — note several carry a PLANNED sub-part), **5 PLANNED** (CP2, CP4, CP9, CP11, CP18). The private lane (CP2) and
certified sharing (CP8) are the two rules whose implementation lets the development-tenant machinery
(`tenant_env` authority, `--sandbox` bypass, dev-token paths, ADR-0106) be retired (debt A28/A50).

# NETWORK-v0.1 — Networks: identity, lifecycle, membership, capabilities, exchange

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (authority model §3; F1–F16), [[REGISTRY-v0.1]] (R1–R16), and
[[DECISION-v0.1]] (D1–D12) — assumed, not restated. A Network, its roles, grants, memberships, and status
are all **governed registry records** (REGISTRY applies), every authorizing act is a **decision**
(DECISION applies), and all authority is **recorded, issuer-scoped, fail-closed** (FOUNDATIONS §3). This
spec adds the Network-specific rules.
**Debt references** are to `../consolidation/DEBT-REGISTER.md` (A1–A61, B1–B18). *(to confirm)* = not traced
this pass. **Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

Context: ADR-0119 (Trusted Network Platform, four planes), ADR-0116 (Participant ≠ Tenant; membership =
`network.participation`, `/v1/participation/{request,decide}`), ADR-0117 (credential & services network),
ADR-0122 (scope types + roles `platform.authority`/`tenant.admin`/`network.creator` + SoD + last-holder
floor). The multi-network console established **net:id ≠ slug** and separated TRUST governance (cross-network
by role) from the LEGACY write path (own-tenant).

---

## Network rules

### N1 — Network identity
A Network has a **generated permanent id** (net:id, REGISTRY R1). The **slug is an alias** for display/lookup
only. The Network id namespace is **separate from the tenant namespace** and the two are **never compared**.
- **Status: PARTIAL / VIOLATED on separation.** net:id exists and the console keys governance on it
  (net:id ≠ slug). But Tenant ≠ Network is **conflated** on legacy paths: the legacy gate keys on
  slug/tenant string while role mode keys on net:id (B11); `cross_network_write_enabled` mixes
  slug/net:id/tenant (B11); and the app-host `networks-mine` fallback **collapses net:id == slug == tenant**
  (B2). The `role_assignment@0.1.0` `network` field overloads slug/net:id (A22).
- **Refs:** B11, B2, A22; ADR-0119. The "never compared" invariant is violated wherever slug/tenant stands
  in for net:id.

### N2 — Creation
Creating a Network requires **both**: platform policy **allows the governing tenant**, **and** the principal
holds **`network.creator`** (or **`tenant.admin`**). The creation **records the governing tenant**. The
**creator becomes `network.admin`**. The Network starts in **DRAFT** with an **empty capability catalog**; a
**draft is invisible and accepts no members**. **draft→active** is a **recorded admin act** requiring **≥1
admin and a non-empty catalog**.
- **Status: PARTIAL / PLANNED.** Network creation records a governing tenant and the creator relationship
  (ADR-0119, console). Roles `network.creator`/`tenant.admin` are defined (ADR-0122) — but `is_platform_
  authority` is still derived from a **tenant name**, not a recorded role (A17; ADR-0122 is the fix). The
  **DRAFT lifecycle, empty-catalog-at-birth, draft-invisible/no-members, and draft→active-requires-catalog**
  gating are **not enforced** — see the **localdev catalog/bootstrap finding** below (the catalog was absent
  on the live network record and had to be seeded out-of-band). So the catalog-prerequisite is **PLANNED**.
- **Refs:** ADR-0122 (roles, SoD), A17 (tenant-name authority); **localdev bootstrap finding** (§Findings).
  DRAFT state machine **(to confirm)** / PLANNED.

### N3 — Roles
Network roles: **`network.admin`**, **`membership.steward`**, **`capability.steward`**, **`grant.steward`**.
A **security-critical assignment** is made via **ChangeRequest approved by a second holder** (separation of
duties). There is **never zero `network.admin`** (last-holder floor).
- **Status: PARTIAL.** The role set and recorded role-assignment path exist; this session proved role-assign
  end-to-end through the console bridges (trust-writer → `/v1/governance/roles`). SoD (second-approver) and
  a last-holder floor are **defined for `platform.authority` and `tenant.admin`** (ADR-0122) — extending the
  **second-holder-CR** and the **never-zero-`network.admin`** floor to the per-Network role set is **(to
  confirm)** / PLANNED. `NETWORK_ADMIN_AUTHZ` still toggles legacy↔role globally (A14).
- **Refs:** ADR-0122 (SoD, last-holder floor), A14 (legacy↔role toggle); F14 (traceable). Per-network SoD +
  floor **(to confirm)**.

### N4 — Status
A Network is **draft / active / suspended / retired**. Network admins change status via **ChangeRequest**.
The **platform authority may suspend any Network** with a **recorded reason (audited)**; **lifting a
platform-imposed suspension requires platform authority**. While **suspended, exchange is refused** but
**governance and history reads continue**.
- **Status: PLANNED / TO CONFIRM.** A status field and the active path exist operationally, but the full
  state machine (suspended/retired), the **platform-suspend-with-recorded-reason**, the **platform-only
  lift**, and the **"suspended ⇒ exchange refused, governance/history reads continue"** behaviour are **not
  verified built** — `TRUST_PLANE_ENABLED` still dark-launches governance (A16), and platform authority is
  tenant-name-derived (A17). Treat as PLANNED pending verification.
- **Refs:** ADR-0119, ADR-0122 (platform.authority), A16 (trust-plane dark-launch), A17; DECISION D4/D6
  (suspend is a decision with a recorded reason). **(to confirm)** against the live status transitions.

### N5 — Membership
Membership is **belonging only** (it confers no capability by itself). Flows: **invite→accept** or
**request→approve/reject**; **suspend**; **revoke**. Members are **existing tenants only**.
- **Status: PARTIAL.** `network.participation` with `/v1/participation/{request,decide}` provides
  request→approve/reject (ADR-0116, Slice 1 live). Membership-confers-nothing aligns with "authority only
  from grants" (F2). **invite→accept**, **suspend**, and **revoke** membership flows, and enforcement that a
  member is an **existing tenant**, are **(to confirm)**. Note the ADR-0116 model treats participation as
  tenant-free (participant ≠ tenant); N5's "existing tenants only" is the Network-of-tenants reading and
  should be reconciled with ADR-0116 in a later revision.
- **Refs:** ADR-0116 (participation request/decide), participant-onboarding; F2. Suspend/revoke/invite +
  existing-tenant check **(to confirm)**.

### N6 — New organisations join via a tenant application + membership request
A new organisation joining via a **join page** creates **two** records: a **tenant application** (under the
**platform onboarding policy**) **and** a **pending membership request** (N5). **Both must be approved
separately.** A **Network admin never creates a tenant or a login.**
- **Status: VIOLATED.** **Join-page finding (below):** the current join path has the **Network → identity**
  provisioning **create a user + password** on participation decide (B9) — i.e. the Network side provisions a
  login, exactly what N6 forbids. There is no separate platform-onboarding **tenant application** gated by
  platform policy; the two approvals are collapsed.
- **Refs:** **B9** (network→identity provisioning creates a user+password — upward control call); ADR-0116,
  network-join-provision; the join-page finding is mapped here. VIOLATED — split into tenant-application
  (platform policy) + membership-request (N5), and remove login creation from the Network side. PLANNED fix.

### N7 — Trusting a member's issuer
**Trusting a member's issuer requires `network.admin`**, and the trust is **scoped to that member's tenant,
in this Network only**.
- **Status: VIOLATED (as stated in the rule).** Today **`membership.steward` can approve** issuer trust
  (not restricted to `network.admin`), and the resulting **trust is service-wide**, not scoped to the
  member's tenant within this Network. `authn.register_issuer` pins the tenant and `verify` rejects a tenant
  mismatch + strips self-asserted roles (F15 PARTIAL), but there is **no per-Network scoping** of the trust.
- **Refs:** **F15** (external issuers scoped — PARTIAL), B13 (assurance), B1; ADR-0117/0119. VIOLATED —
  require `network.admin` and bind the trust to (member-tenant, this-net:id). PLANNED fix.

### N8 — Classifications are descriptive only
Any member/Network **classification is descriptive** — it never confers or withholds authority (FOUNDATIONS
§3 (iii): nothing implied by classification).
- **Status: PARTIAL / TO CONFIRM.** No Network-level classification is known to drive authz **(to confirm)**,
  but the sibling violation in the Kernel — **classification/schema-prefix drives authz** (B7), and authority
  implied by tenant name (B2) — shows the invariant is not uniformly held. Verify no Network classification
  field gates exchange or membership.
- **Refs:** B7 (classification drives authz — kernel), B2; FOUNDATIONS §3(iii). Network-classification-blind
  **(to confirm)**.

### N9 — Capabilities
The **capability catalog** is maintained by **`capability.steward`**; **grants** are issued by
**`grant.steward`**. Grammar: **`service.provide` / `service.call`**, with **no wildcards**, each **pinned to
a capability version**. A **grant is inactive while its holder is not an active member**. **Data
capabilities** are **pending the grant-model ADR**.
- **Status: PARTIAL.** The capability catalog + grant issue/revoke are live and were proven end-to-end this
  session (trust-writer: define capability, issue, revoke). But: the **catalog was missing on the live
  network record** and had to be seeded out-of-band — see **localdev catalog/bootstrap finding** below (so
  `capability.steward`-only authoring isn't enforced at creation, N2); **no-wildcards** and **version-pinned
  grants** are **(to confirm)** (cf. B12 client-asserted `service:"*"`); **grant-inactive-while-not-active-
  member** is **(to confirm)**; and the **data-capability** model is blocked on the **grant-model ADR**
  (two grant representations coexist — `role_grant`/`role_assignment` vs. the shadow-only CapabilityGrant,
  A18).
- **Refs:** A18 (two grant models; CapabilityGrant shadow-only), B12 (unbound/wildcard scope); **localdev
  catalog/bootstrap finding** (§Findings); service.provide/call grammar. Wildcard ban + version-pin +
  inactive-on-non-membership **(to confirm)**.

### N10 — Publishing a Service
**Publishing a Service requires the matching `service.provide` grant.** **Offerings reference a Service** and
carry **eligibility rules**.
- **Status: PARTIAL.** Service publish and Offerings exist (ADR-0047 Service-vs-Solution; W5 Publish-as-
  Service from Studio; offering `scope_map`/eligibility). That **publishing checks a `service.provide`
  grant** is **(to confirm)** — verify publish is gated on the recorded provide grant (N9), not on a token
  role.
- **Refs:** ADR-0047, service-api-specs; offering scope/eligibility (#155/#156). Provide-grant-gated publish
  **(to confirm)**.

### N11 — Every exchange goes through the decision function
Every exchange is authorized by the **one decision function** (FOUNDATIONS §3) over: the **caller's
`service.call` grant**, the **provider's `service.provide` grant**, and **consent when personal data is
involved** (F13 / DECISION D7) — and it **produces a decision record** (DECISION D1/D11).
- **Status: PARTIAL / PLANNED.** The governed bridge / Data Exchange carries declared-interface exchange
  (ADR-0088; data-exchange-network) and the cross-tenant aggregator lane exists. But: **a decision record
  per exchange** inherits DECISION D1 (**PARTIAL/VIOLATED** — routine authz not recorded); **consent-when-
  personal-data** inherits D7/REGISTRY R14 (**PLANNED**); and that **both** call+provide grants are checked
  against recorded grants (not token roles) is **(to confirm)** given B1/B12.
- **Refs:** ADR-0088 (governed bridge), data-exchange-network, cross-tenant aggregator lane; DECISION
  D1/D7/D11; B1, B12, A18. Grant-checked-and-recorded exchange **PLANNED**.

### N12 — Directory visibility
The directory is **members-only by default**. Admins may make **chosen Offerings publicly discoverable** via
**REGISTRY R15** (public = a schema-level designation changed by ChangeRequest, audited). **Member lists stay
members-only.**
- **Status: PARTIAL.** A service directory + search exists (ADR-0067 S1). Making an Offering public depends
  on **REGISTRY R15**, which is itself **VIOLATED/PARTIAL** (public is a hardcoded kernel allow-list, not a
  schema-level field changed via CR) — so public discoverability is not yet governed per R15. **Member-lists-
  members-only** is **(to confirm)**; the sibling risk is B6 (unauthenticated identity directory disclosure
  exposes users/tenants/roles).
- **Refs:** ADR-0067 (directory/search), REGISTRY R15 (VIOLATED/PARTIAL), B6 (identity directory disclosure);
  DECISION D1 (directory reads that aren't public are decisions). Member-list scoping **(to confirm)**.

---

## Summary of status

| Rule | Topic | Status | Key debt |
|------|-------|--------|----------|
| N1 | Network identity (net:id≠slug, never compared) | PARTIAL/VIOLATED | B11, B2, A22 |
| N2 | Creation (policy+role, DRAFT, catalog gate) | PARTIAL/PLANNED | A17; ADR-0122; localdev |
| N3 | Roles (+SoD, never-zero-admin) | PARTIAL | ADR-0122; A14 |
| N4 | Status (draft/active/suspended/retired) | PLANNED/TO CONFIRM | A16, A17; ADR-0119 |
| N5 | Membership (belonging only) | PARTIAL | ADR-0116 |
| N6 | Join = tenant-app + membership req | **VIOLATED** | **B9** (join-page finding) |
| N7 | Issuer trust (admin + tenant+net scoped) | **VIOLATED** | F15, B13, B1 |
| N8 | Classifications descriptive only | PARTIAL/TO CONFIRM | B7, B2 |
| N9 | Capabilities (catalog/grant grammar) | PARTIAL | A18, B12; localdev |
| N10 | Publishing a Service (provide grant) | PARTIAL | ADR-0047; *to confirm* |
| N11 | Exchange via decision function | PARTIAL/PLANNED | ADR-0088; D1/D7; B1, B12 |
| N12 | Directory visibility (members-only+R15) | PARTIAL | ADR-0067; R15; B6 |

**Tally:** 0 fully IN PLACE, 6 PARTIAL (N1-leaning, N3, N5, N9, N10, N12), 2 VIOLATED (**N6, N7**), 2
PLANNED/TO-CONFIRM (N2, N4), 2 mixed (N8, N11). The two hard violations are **N6** (join page provisions a
login) and **N7** (issuer trust under-scoped and under-roled).

---

## Findings mapped

- **Join-page finding → N6 (and N1/N5).** The current join page has the **Network → identity** path
  **create a user + password** on participation decide (**B9**). This violates N6 ("a Network admin never
  creates a tenant or login") and collapses the two required approvals (platform tenant-application +
  membership request) into one. It also feeds N1/N5 confusion by conflating the new org's tenant with its
  Network membership. **Fix:** route org onboarding through the **platform onboarding policy** (tenant
  application) and a **separate** `network.participation` request; remove login creation from the Network
  side.

- **localdev catalog finding → N9 (and N2).** The Network record was **missing its `capability_catalog`**;
  grants could not be issued until a catalog existed. This shows the **catalog-at-creation** invariant (N2:
  DRAFT starts with an empty catalog; draft→active requires a non-empty one) and **`capability.steward`-only
  authoring** (N9) are **not enforced by the creation path** — the catalog was a missing prerequisite rather
  than a governed artifact of creation.

- **localdev bootstrap finding → N2 (and N9).** The catalog (and the trust-reader/trust-writer service
  principals) had to be **seeded out-of-band** by `bootstrap-dev.sh` (capability-catalog init phase) rather
  than produced by the governed creation/DRAFT→active flow. The DRAFT lifecycle, empty-catalog-at-birth, and
  draft→active-requires-catalog gating (N2) are therefore **PLANNED**, not enforced — bootstrap compensates
  for the missing state machine.

---

## Out of scope for v0.1
**Root Trust / Authorized Network Directory** — how Networks themselves are discovered and trusted across the
platform (the directory of Networks, and the root that attests which Networks are authorized) is **deferred**.
This spec governs one Network's internal rules; the inter-Network root-of-trust and authorized-network
directory are for a later spec version. *(Noted for later.)*

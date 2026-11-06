# NETWORK-v0.1 — Networks: identity, lifecycle, membership, capabilities, exchange

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (authority model §3; FND-1–FND-17), [[REGISTRY-v0.1]] (REG-1–REG-18), and
[[DECISION-v0.1]] (DEC-1–DEC-12) — assumed, not restated. A Network, its roles, grants, memberships, and status
are all **governed registry records** (REGISTRY applies), every authorizing act is a **decision**
(DECISION applies), and all authority is **recorded, issuer-scoped, fail-closed** (FOUNDATIONS §3). This
spec adds the Network-specific rules.
**Debt references** are to `../consolidation/DEBT-REGISTER.md` (DEBT-A1–DEBT-A61, DEBT-B1–DEBT-B18). *(to confirm)* = not traced
this pass. **Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

Context: ADR-0119 (Trusted Network Platform, four planes), ADR-0116 (Participant ≠ Tenant; membership =
`network.participation`, `/v1/participation/{request,decide}`), ADR-0117 (credential & services network),
ADR-0122 (scope types + roles `platform.authority`/`tenant.admin`/`network.creator` + SoD + last-holder
floor). The multi-network console established **net:id ≠ slug** and separated TRUST governance (cross-network
by role) from the LEGACY write path (own-tenant).

---

## Network rules

### NET-1 — Network identity
A Network has a **generated permanent id** (net:id, REGISTRY REG-1). The **slug is an alias** for display/lookup
only. The Network id namespace is **separate from the tenant namespace** and the two are **never compared**.
- **Status: PARTIAL / VIOLATED on separation.** net:id exists and the console keys governance on it
  (net:id ≠ slug). But Tenant ≠ Network is **conflated** on legacy paths: the legacy gate keys on
  slug/tenant string while role mode keys on net:id (DEBT-B11); `cross_network_write_enabled` mixes
  slug/net:id/tenant (DEBT-B11); and the app-host `networks-mine` fallback **collapses net:id == slug == tenant**
  (DEBT-B2). The `role_assignment@0.1.0` `network` field overloads slug/net:id (DEBT-A22).
- **Refs:** DEBT-B11, DEBT-B2, DEBT-A22; ADR-0119. The "never compared" invariant is violated wherever slug/tenant stands
  in for net:id.

### NET-2 — Creation (federated: creator's tenant becomes the Network host)
Any tenant holding **`network.creator`** on **any** AirawatOS installation may create a Network and becomes its
**governing tenant (the Network host)**; the Network's **registry, directory and grant/decision records live on
the host's installation** (ADR-0128). The creation **records the governing tenant**. The **creator becomes
`network.admin`**. "Which installation runs the servers" (operator) is independent of "which tenant governs this
Network" (host). The Network starts in **DRAFT** with an **empty capability catalog**; a
**draft is invisible and accepts no members**. **draft→active** is a **recorded admin act** requiring **≥1
admin and a non-empty catalog**.
- **Status: PARTIAL / PLANNED.** Network creation records a governing tenant and the creator relationship
  (ADR-0119, console). Roles `network.creator`/`tenant.admin` are defined (ADR-0122) — but `is_platform_
  authority` is still derived from a **tenant name**, not a recorded role (DEBT-A17; ADR-0122 is the fix). The
  **DRAFT lifecycle, empty-catalog-at-birth, draft-invisible/no-members, and draft→active-requires-catalog**
  gating are **not enforced** — see the **localdev catalog/bootstrap finding** below (the catalog was absent
  on the live network record and had to be seeded out-of-band). So the catalog-prerequisite is **PLANNED**.
- **Refs:** ADR-0122 (roles, SoD), DEBT-A17 (tenant-name authority); **localdev bootstrap finding** (§Findings).
  DRAFT state machine **(to confirm)** / PLANNED.

### NET-3 — Roles
Network roles: **`network.admin`**, **`membership.steward`**, **`capability.steward`**, **`grant.steward`**.
A **security-critical assignment** is made via **ChangeRequest approved by a second holder** (separation of
duties). There is **never zero `network.admin`** (last-holder floor).
- **Status: PARTIAL.** The role set and recorded role-assignment path exist; this session proved role-assign
  end-to-end through the console bridges (trust-writer → `/v1/governance/roles`). SoD (second-approver) and
  a last-holder floor are **defined for `platform.authority` and `tenant.admin`** (ADR-0122) — extending the
  **second-holder-CR** and the **never-zero-`network.admin`** floor to the per-Network role set is **(to
  confirm)** / PLANNED. `NETWORK_ADMIN_AUTHZ` still toggles legacy↔role globally (DEBT-A14).
- **Refs:** ADR-0122 (SoD, last-holder floor), DEBT-A14 (legacy↔role toggle); FND-14 (traceable). Per-network SoD +
  floor **(to confirm)**.

### NET-4 — Status
A Network is **draft / active / suspended / retired**. Network admins change status via **ChangeRequest**.
The **platform authority may suspend any Network** with a **recorded reason (audited)**; **lifting a
platform-imposed suspension requires platform authority**. While **suspended, exchange is refused** but
**governance and history reads continue**.
- **Status: PLANNED / TO CONFIRM.** A status field and the active path exist operationally, but the full
  state machine (suspended/retired), the **platform-suspend-with-recorded-reason**, the **platform-only
  lift**, and the **"suspended ⇒ exchange refused, governance/history reads continue"** behaviour are **not
  verified built** — `TRUST_PLANE_ENABLED` still dark-launches governance (DEBT-A16), and platform authority is
  tenant-name-derived (DEBT-A17). Treat as PLANNED pending verification.
- **Refs:** ADR-0119, ADR-0122 (platform.authority), DEBT-A16 (trust-plane dark-launch), DEBT-A17; DECISION DEC-4/DEC-6
  (suspend is a decision with a recorded reason). **(to confirm)** against the live status transitions.

### NET-5 — Membership (tenant-free; three member modes)
Membership is **belonging only** (it confers no capability by itself). A member is a **participant**, **not a
tenant** (ADR-0116): a registered participant ID in this (the hosting) Network's registry. A participant is
realised in one of **three member modes** (ADR-0128): (1) a **tenant on the host's installation**; (2) a
**tenant on another AirawatOS installation**; (3) an **own system** via the Participant SDK — the Network
treats all three uniformly. Flows: **invite→accept** or **request→approve/reject**; **suspend**; **revoke**.
- **Status: PARTIAL.** `network.participation` with `/v1/participation/{request,decide}` provides tenant-free
  request→approve/reject (ADR-0116, Slice 1 live) for mode-1. Membership-confers-nothing aligns with "authority
  only from grants" (FND-2). **invite→accept**, **suspend**, **revoke**, and cross-installation modes (2)/(3) are
  **PLANNED** (FEDERATION FED3).
- **Resolved (was an open decision): tenant-free wins.** The earlier "existing tenants only" (Network-of-tenants)
  reading is **dropped** — **ADR-0128** makes membership tenant-free and federated, consistent with ADR-0116
  (participant ≠ tenant). The live code already follows this.
- **Refs:** **ADR-0128** (federated), ADR-0116 (participation request/decide), FEDERATION FED3/FED4; FND-2.

### NET-6 — Joining = participant registration in the host's registry (Network creates no tenant/login)
A member **joins by registering as a participant** in the hosting Network's registry (ADR-0128): a
**participant ID**, the **role(s)** sought, **public keys**, and **conformance status** — activated for a role
only after passing that role's conformance suite (PTC-11 / FEDERATION FED3–FED4). A **mode-1** member (a tenant
on the host's installation) may *additionally* go through **platform onboarding** (a tenant application under
platform policy) — but that is the operator/platform's act, separate from the Network membership record. A
**Network admin never creates a tenant, a login, or a participant system** (ADR-0128): the Network records who
may participate, it does not stand up the participant.
- **Status: VIOLATED.** **Join-page finding (below):** the current join path has the **Network → identity**
  provisioning **create a user + password** on participation decide (DEBT-B9) — i.e. the Network side provisions a
  login, exactly what NET-6 forbids. There is no separate platform-onboarding **tenant application** gated by
  platform policy; the two approvals are collapsed.
- **Refs:** **DEBT-B9** (network→identity provisioning creates a user+password — upward control call); ADR-0116,
  network-join-provision; the join-page finding is mapped here. VIOLATED — split into tenant-application
  (platform policy) + membership-request (NET-5), and remove login creation from the Network side. PLANNED fix.

### NET-7 — Trusting a member's issuer
**Trusting a member's issuer requires `network.admin`**, and the trust is **scoped to that member's tenant,
in this Network only**.
- **Status: VIOLATED (as stated in the rule).** Today **`membership.steward` can approve** issuer trust
  (not restricted to `network.admin`), and the resulting **trust is service-wide**, not scoped to the
  member's tenant within this Network. `authn.register_issuer` pins the tenant and `verify` rejects a tenant
  mismatch + strips self-asserted roles (FND-15 PARTIAL), but there is **no per-Network scoping** of the trust.
- **Refs:** **FND-15** (external issuers scoped — PARTIAL), DEBT-B13 (assurance), DEBT-B1; ADR-0117/0119. VIOLATED —
  require `network.admin` and bind the trust to (member-tenant, this-net:id). PLANNED fix.

### NET-8 — Classifications are descriptive only
Any member/Network **classification is descriptive** — it never confers or withholds authority (FOUNDATIONS
§3 (iii): nothing implied by classification).
- **Status: PARTIAL / TO CONFIRM.** No Network-level classification is known to drive authz **(to confirm)**,
  but the sibling violation in the Kernel — **classification/schema-prefix drives authz** (DEBT-B7), and authority
  implied by tenant name (DEBT-B2) — shows the invariant is not uniformly held. Verify no Network classification
  field gates exchange or membership.
- **Refs:** DEBT-B7 (classification drives authz — kernel), DEBT-B2; FOUNDATIONS §3(iii). Network-classification-blind
  **(to confirm)**.

### NET-9 — Capabilities
The **capability catalog** is maintained by **`capability.steward`**; **grants** are issued by
**`grant.steward`**. Grammar: **`service.provide` / `service.call`**, with **no wildcards**, each **pinned to
a capability version**. A **grant is inactive while its holder is not an active member**. **Data capabilities
are CapabilityGrants too** (ADR-0127): a grant to **read/write records of a schema**, scoped as needed, uses
the SAME catalog, issuance and rules as a service capability. Access to a **specific person's** data
**additionally** requires that person's **consent** (the two-key rule, FOUNDATIONS §3); non-personal data
needs the grant only. `access_grant` is the Kernel's **derived** enforcement artefact (grant + consent), not a
separately-issued permission.
- **Status: PARTIAL.** The capability catalog + grant issue/revoke are live and were proven end-to-end this
  session (trust-writer: define capability, issue, revoke). But: the **catalog was missing on the live
  network record** and had to be seeded out-of-band — see **localdev catalog/bootstrap finding** below (so
  `capability.steward`-only authoring isn't enforced at creation, NET-2); **no-wildcards** and **version-pinned
  grants** are **(to confirm)** (cf. DEBT-B12 client-asserted `service:"*"`); **grant-inactive-while-not-active-
  member** is **(to confirm)**; and the **data-capability** model is now **decided by ADR-0127** (data =
  CapabilityGrant + consent-for-personal; `access_grant` becomes a derived artefact) but **not yet cut over**
  — two grant representations still coexist in shadow (`role_grant`/`role_assignment` + `access_grant` vs. the
  CapabilityGrant model, DEBT-A18), migrating via shadow comparison.
- **Refs:** DEBT-A18 (two grant models; CapabilityGrant shadow-only), DEBT-B12 (unbound/wildcard scope); **localdev
  catalog/bootstrap finding** (§Findings); service.provide/call grammar. Wildcard ban + version-pin +
  inactive-on-non-membership **(to confirm)**.

### NET-10 — Publishing a Service
**Publishing a Service requires the matching `service.provide` grant.** **Offerings reference a Service** and
carry **eligibility rules**.
- **Status: PARTIAL.** Service publish and Offerings exist (ADR-0047 Service-vs-Solution; W5 Publish-as-
  Service from Studio; offering `scope_map`/eligibility). That **publishing checks a `service.provide`
  grant** is **(to confirm)** — verify publish is gated on the recorded provide grant (NET-9), not on a token
  role.
- **Refs:** ADR-0047, service-api-specs; offering scope/eligibility (#155/#156). Provide-grant-gated publish
  **(to confirm)**.

### NET-11 — Every exchange goes through the decision function
Every exchange is authorized by the **one decision function** (FOUNDATIONS §3) over: the **caller's
`service.call` grant**, the **provider's `service.provide` grant**, and **consent when personal data is
involved** (FND-13 / DECISION DEC-7) — and it **produces a decision record** (DECISION DEC-1/DEC-11).
- **Status: PARTIAL / PLANNED.** The governed bridge / Data Exchange carries declared-interface exchange
  (ADR-0088; data-exchange-network) and the cross-tenant aggregator lane exists. But: **a decision record
  per exchange** inherits DECISION DEC-1 (**PARTIAL/VIOLATED** — routine authz not recorded); **consent-when-
  personal-data** inherits DEC-7/REGISTRY REG-14 (**PLANNED**); and that **both** call+provide grants are checked
  against recorded grants (not token roles) is **(to confirm)** given DEBT-B1/DEBT-B12.
- **Refs:** ADR-0088 (governed bridge), data-exchange-network, cross-tenant aggregator lane; DECISION
  DEC-1/DEC-7/DEC-11; DEBT-B1, DEBT-B12, DEBT-A18. Grant-checked-and-recorded exchange **PLANNED**.

### NET-12 — Directory visibility
The directory is **members-only by default**. Admins may make **chosen Offerings publicly discoverable** via
**REGISTRY REG-15** (public = a schema-level designation changed by ChangeRequest, audited). **Member lists stay
members-only.**
- **Status: PARTIAL.** A service directory + search exists (ADR-0067 S1). Making an Offering public depends
  on **REGISTRY REG-15**, which is itself **VIOLATED/PARTIAL** (public is a hardcoded kernel allow-list, not a
  schema-level field changed via CR) — so public discoverability is not yet governed per REG-15. **Member-lists-
  members-only** is **(to confirm)**; the sibling risk is DEBT-B6 (unauthenticated identity directory disclosure
  exposes users/tenants/roles).
- **Refs:** ADR-0067 (directory/search), REGISTRY REG-15 (VIOLATED/PARTIAL), DEBT-B6 (identity directory disclosure);
  DECISION DEC-1 (directory reads that aren't public are decisions). Member-list scoping **(to confirm)**.

---

## Summary of status

| Rule | Topic | Status | Key debt |
|------|-------|--------|----------|
| NET-1 | Network identity (net:id≠slug, never compared) | PARTIAL/VIOLATED | DEBT-B11, DEBT-B2, DEBT-A22 |
| NET-2 | Creation (policy+role, DRAFT, catalog gate) | PARTIAL/PLANNED | DEBT-A17; ADR-0122; localdev |
| NET-3 | Roles (+SoD, never-zero-admin) | PARTIAL | ADR-0122; DEBT-A14 |
| NET-4 | Status (draft/active/suspended/retired) | PLANNED/TO CONFIRM | DEBT-A16, DEBT-A17; ADR-0119 |
| NET-5 | Membership (belonging only) | PARTIAL | ADR-0116 |
| NET-6 | Join = tenant-app + membership req | **VIOLATED** | **DEBT-B9** (join-page finding) |
| NET-7 | Issuer trust (admin + tenant+net scoped) | **VIOLATED** | FND-15, DEBT-B13, DEBT-B1 |
| NET-8 | Classifications descriptive only | PARTIAL/TO CONFIRM | DEBT-B7, DEBT-B2 |
| NET-9 | Capabilities (catalog/grant grammar) | PARTIAL | DEBT-A18, DEBT-B12; localdev |
| NET-10 | Publishing a Service (provide grant) | PARTIAL | ADR-0047; *to confirm* |
| NET-11 | Exchange via decision function | PARTIAL/PLANNED | ADR-0088; DEC-1/DEC-7; DEBT-B1, DEBT-B12 |
| NET-12 | Directory visibility (members-only+REG-15) | PARTIAL | ADR-0067; REG-15; DEBT-B6 |

**Tally:** 0 fully IN PLACE, 6 PARTIAL (NET-1-leaning, NET-3, NET-5, NET-9, NET-10, NET-12), 2 VIOLATED (**NET-6, NET-7**), 2
PLANNED/TO-CONFIRM (NET-2, NET-4), 2 mixed (NET-8, NET-11). The two hard violations are **NET-6** (join page provisions a
login) and **NET-7** (issuer trust under-scoped and under-roled).

---

## Findings mapped

- **Join-page finding → NET-6 (and NET-1/NET-5).** The current join page has the **Network → identity** path
  **create a user + password** on participation decide (**DEBT-B9**). This violates NET-6 ("a Network admin never
  creates a tenant or login") and collapses the two required approvals (platform tenant-application +
  membership request) into one. It also feeds NET-1/NET-5 confusion by conflating the new org's tenant with its
  Network membership. **Fix:** route org onboarding through the **platform onboarding policy** (tenant
  application) and a **separate** `network.participation` request; remove login creation from the Network
  side.

- **localdev catalog finding → NET-9 (and NET-2).** The Network record was **missing its `capability_catalog`**;
  grants could not be issued until a catalog existed. This shows the **catalog-at-creation** invariant (NET-2:
  DRAFT starts with an empty catalog; draft→active requires a non-empty one) and **`capability.steward`-only
  authoring** (NET-9) are **not enforced by the creation path** — the catalog was a missing prerequisite rather
  than a governed artifact of creation.

- **localdev bootstrap finding → NET-2 (and NET-9).** The catalog (and the trust-reader/trust-writer service
  principals) had to be **seeded out-of-band** by `bootstrap-dev.sh` (capability-catalog init phase) rather
  than produced by the governed creation/DRAFT→active flow. The DRAFT lifecycle, empty-catalog-at-birth, and
  draft→active-requires-catalog gating (NET-2) are therefore **PLANNED**, not enforced — bootstrap compensates
  for the missing state machine.

---

## Out of scope for v0.1
**Root Trust / Authorized Network Directory** — how Networks themselves are discovered and trusted across the
platform (the directory of Networks, and the root that attests which Networks are authorized) is **deferred**.
This spec governs one Network's internal rules; the inter-Network root-of-trust and authorized-network
directory are for a later spec version. *(Noted for later.)*

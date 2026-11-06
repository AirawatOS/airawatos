# PLATFORM-v0.1 — Platform lifecycle: install, platform authority, tenants, onboarding, administration

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**, the conformance-derived rule × environment matrix (`conformance/run.py --matrix` → `conformance/build_matrix.py`; design: [STATUS-MATRIX-DESIGN.md](STATUS-MATRIX-DESIGN.md)). The inline **Status:** lines below are kept for prose and rationale and may lag; the matrix is authoritative for covered rules (uncovered rules show **NO TEST** there, not an implied status).

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (FND-1–FND-17), [[REGISTRY-v0.1]] (REG-1–REG-18), [[DECISION-v0.1]] (DEC-1–DEC-12),
[[NETWORK-v0.1]] (NET-1–NET-12), [[ACCOUNT-v0.1]] (ACC-1–ACC-9/ACC-W1–ACC-W4), [[CLIENT-v0.1]] (CLI-1–CLI-6) — assumed, not restated.
This spec governs the **platform itself**: what the installer creates, how platform authority is held and
recovered, how tenants are onboarded and given a verification status, and how platform administration is exposed. Every object
here is a governed registry record (REGISTRY), every authorizing act a decision (DECISION), authority only
from recorded grants (FOUNDATIONS §3).

**Every installation is both a Network host and a participant node (ADR-0128, FEDERATION-v0.1).** It **hosts**
the Networks its tenants create (their registry/directory/grants live here) and runs **participant nodes** (its
tenants, or its own systems, acting in Networks hosted anywhere). Consequences for this spec: **tenant
onboarding** (below) applies only to **mode-1** members — tenants standing up **on this installation**;
membership in a Network is a separate participant registration (NETWORK NET-5/NET-6), not onboarding. The **installer
may register an installation's tenants as participants in remote Networks** (hosted on other installations),
distinct from creating local tenants.

**Debt references** → `../consolidation/DEBT-REGISTER.md` (DEBT-A1–DEBT-A74, DEBT-B1–DEBT-B21). *(to confirm)* = not traced.
**Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

---

## Platform rules

### PLT-1 — The installer creates only the minimum
A fresh install creates **only**: keys in Vault; a **required durable store** (fail-loud if absent); **base
schemas**; **exactly one platform tenant**; **service identities with recorded service roles**; **certified
platform apps**. It creates **no other tenants, Networks, memberships, or grants**. **Demo tenants exist only
under the dev profile.** Re-runs are **idempotent**.
- **Status: PARTIAL.** The installer seeds base vocab + base apps in-process (ADR-0115) and bootstrap is
  idempotent; the network requires a durable backend (fail-loud). But: prod-pointing defaults still exist
  (`ds:airawat:identity`/`airawatos`, debt DEBT-A7/DEBT-A8); demo seeding is a flag (`IDENTITY_SEED_DEMO`, DEBT-A32) rather
  than strictly dev-profile-gated; "exactly one platform tenant and nothing else" is **(to confirm)** against
  the seed set. Service identities are **passwordless** today (debt DEBT-A26/DEBT-B14), not credentialed service roles.
- **Refs:** ADR-0115 (installer base-OS seeding), platform-content-reset; DEBT-A7, DEBT-A8, DEBT-A32, DEBT-A26, DEBT-B14; FND-16 (safe
  defaults).

### PLT-2 — First platform.authority via a one-time installer credential
The **first `platform.authority`** is created **once** via a **one-time installer credential that then
expires**; a **second holder is added promptly**.
- **Status: PARTIAL / PLANNED.** ADR-0122 defines the first-grant seed (installer-seeded `platform.authority`),
  but `is_platform_authority` is still derived from a **tenant name** (debt DEBT-A17), not a recorded role, and
  the **one-time-expiring installer credential** + enforced **prompt second holder** are PLANNED.
- **Refs:** ADR-0122 (first-grant seed), DEBT-A17; FND-11 (SoD), FND-14 (traceable).

### PLT-3 — The operator holds no governance role
The **operator** (host/infra) holds **no governance role**. **Identity-service and Vault administration**
require **strong auth**, **audited admin actions**, and **separation from governance roles**.
- **Status: PARTIAL / TO CONFIRM.** The operator model exists (ADR-0086 operator certification; ADR-0096
  operator = `kind:operator`). "Operator holds no governance role" separation is **(to confirm)**; Vault
  admin uses a dev root token today (debt DEBT-A38) — not strong-auth + audited; identity admin audit **(to
  confirm)**.
- **Refs:** ADR-0086, ADR-0096; DEBT-A38 (dev root Vault token); FND-12 (audit). Separation enforcement **(to
  confirm)**.

### PLT-4 — The platform tenant confers nothing
Membership of, or being, the **platform tenant grants no authority** by itself (FOUNDATIONS FND-3).
- **Status: VIOLATED.** Today `is_platform_authority = (tenant == authority_tenant)` and network-admin is
  implied by `tenant == "airawat"` — the platform tenant **does** confer authority (debt DEBT-B2, DEBT-A17).
- **Refs:** **DEBT-B2**, DEBT-A17; FND-3. The fix is PLT-5 (recorded `platform.authority` role) — PLANNED.

### PLT-5 — platform.authority is a recorded role
`platform.authority` is a **recorded role**, with **never zero holders**. A grant requires a **ChangeRequest
approved by a different holder** (SoD); **removing the last holder is refused**.
- **Status: PARTIAL.** SoD + last-holder floor for `platform.authority` are **defined** (ADR-0122) and the
  Trust-plane role path is proven, but the live `is_platform_authority` is still tenant-name-derived (DEBT-A17),
  so the recorded-role form is not yet the enforced one.
- **Refs:** ADR-0122, DEBT-A17; FND-11.

### PLT-5a — Break-glass recovery
A **recovery key split among named custodians**; **quorum required**; it can **only restore a
`platform.authority` holder**; its use is **publicly and permanently recorded**.
- **Status: PLANNED (open item).** ADR-0122 explicitly lists break-glass recovery as an **open item**; no
  custodian-quorum key, restore-only scope, or public record exists yet.
- **Refs:** ADR-0122 (break-glass open item); FND-11, FND-12.

### PLT-6 — What platform authority decides
Platform authority decides: **tenant policy and verification status**, **allowed external issuers and proofing sources**,
**Network-creation permission**, and **tenant/Network suspension with recorded reasons**. **Security-sensitive
policy changes go via ChangeRequest.**
- **Status: PARTIAL / PLANNED.** A governed policy primitive exists (`governance.policy_rule`, rule engine
  ADR-0088 S1) and ChangeRequest is first-class (ADR-0056). But verification status, the allowed-issuer/proofing registry,
  Network-creation permission, and suspension-with-reason (NET-4) are PLANNED; allowed issuers are configured by
  env today (debt DEBT-A5–DEBT-A8), not a platform-authority policy record.
- **Refs:** ADR-0088 (rule engine), ADR-0056 (CR); NET-4; DEBT-A5–DEBT-A8; DECISION DEC-4/DEC-6.

### PLT-7 — Onboarding mode is a recorded policy
Onboarding mode is a **recorded policy**: **invite-only** / **request-and-approve (default)** /
**self-provision**.
- **Status: PARTIAL / TO CONFIRM.** Onboarding composition exists (`f(type)×f(packs)`) and participation
  request/decide is live (ADR-0116), but onboarding **mode** as a single recorded platform policy with those
  three values is **(to confirm)** / PLANNED.
- **Refs:** ADR-0116, onboarding-composition, network-join-provision; PLT-6.

### PLT-8 — Applications are records
A tenant application is a **record**: the **applicant has their own login**; it carries **organisation,
purpose, contact, verification evidence**; lifecycle **submitted → review → approved/rejected**. Reviews are
by a **platform-scoped `tenant.steward`** (**at least one** required); **platform authority reviews only when
no steward is available, and that is recorded**.
- **Status: PLANNED.** Participation request/decide (ADR-0116) is the nearest primitive, and publish-request
  review governance exists for components, but a **tenant-application record** with evidence, the steward
  review queue, the ≥1-steward rule, and the platform-authority-fallback-recorded rule are **not built**.
- **Refs:** ADR-0116, publish-request-review-governance; NET-6 (join); DECISION DEC-1/DEC-11.

### PLT-8a — Verification methods
**Government bodies:** an **official government email domain** plus an **authorising letter**. **Companies:**
a **registration or GST number**. **More methods addable via ChangeRequest.**
- **Status: PLANNED.** No verification-method registry or evidence capture exists; GST appears only as a
  natural-key in the Kernel (debt DEBT-B8), not as a governed proofing method.
- **Refs:** DEBT-B8 (GST baked in kernel), ADR-0056 (CR to add methods); PLT-8, DEBT-A3 (assurance).

### PLT-9 — Tenant verification status (not tiers)
A tenant carries a **verification status**: **verified** or **unverified**. There are no "tiers"; status is a
single recorded property of the tenant. **Unverified** exists **only when self-provisioning is enabled** (an
operator policy, PLT-7) — otherwise every tenant is onboarded through review and is verified. An **unverified**
tenant is restricted to: **quotas** (COMPONENT CMP-11), **no Network creation**, **no own issuer**, and **no
marketplace contributions** (COMPONENT CMP-10). It may still **build and run its own components privately**
within those quotas (COMPONENT CMP-2). Promotion to **verified** is the reviewed onboarding step (PLT-8/PLT-10).
- **Status: PARTIAL.** A tenant `environment` field + dev/sandbox relaxation exists (ADR-0051) and the
  sandbox-privilege rule (`authz = builder-role × dev-env`) is live, but it is modelled as a **dev/prod
  environment tier** (ADR-0051/0106), not as a single **verification status** on the tenant; the restrictions
  (quotas, no Network creation, no own issuer, no marketplace contribution) are only partly enforced — the
  marketplace-contribution block is live (network `store_publish` refuses a development tenant, ADR-0106),
  but **quotas**, **no-own-issuer** and **no-Network-creation** gating by status are **PLANNED**, and the
  private-build lane for an unverified tenant depends on COMPONENT **CMP-2** (PLANNED). The dev/prod environment
  machinery (`tenant_env` authority DEBT-A28, `--sandbox` bypass DEBT-A50, dev-token paths, ADR-0106) is **transitional**
  and retires once CMP-2 (private lane) and CMP-8 (certified sharing) land.
- **Refs:** ADR-0051 (environment field — transitional), ADR-0106 (dev↔prod boundary — transitional);
  sandbox-privilege-rule; DEBT-A28, DEBT-A50; COMPONENT CMP-2/CMP-8/CMP-10/CMP-11; NET-2/NET-9.

### PLT-10 — What approval creates
Approving an application creates: the **workspace**, a **permanent participant identity and keys**, a
**platform-signed directory entry**, and a **recorded `tenant.admin`** for the applicant.
- **Status: PARTIAL.** Provisioning creates a tenant + admin (network-join-provision; dev-tenant
  provisioning) and participants have identities; the **permanent participant keys** and **platform-signed
  directory entry** at approval are **(to confirm)**; the join path also currently provisions a **login**
  from the Network side (debt DEBT-B9 / NETWORK NET-6 violation).
- **Refs:** network-join-provision, dev-tenant-provisioning, ADR-0116; DEBT-B9; NETWORK NET-6, NET-1.

### PLT-11 — Tenant roles
**`tenant.admin`** (never zero; security-critical changes by a second holder) and **`network.creator`**
(subject to verification status and policy).
- **Status: PARTIAL.** Roles are defined (ADR-0122) with SoD + last-holder floor for `tenant.admin`;
  `network.creator` exists. **Verification-status/policy gating of `network.creator`** and the per-tenant never-zero /
  second-holder enforcement are **(to confirm)**.
- **Refs:** ADR-0122; PLT-9, NETWORK NET-3; FND-11.

### PLT-12 — A tenant's own login system
A tenant may run **its own login system only if verification status and policy permit**; it is **scoped to that tenant**,
carries **identity only** (FND-1), and its **approval is recorded** (FND-15).
- **Status: PARTIAL / VIOLATED.** Pluggable IdP + per-tenant realms exist (ADR-0068, ADR-0117,
  identity-login-realms), and `authn.register_issuer` pins the tenant (FND-15 PARTIAL). But issuer trust is
  **service-wide, approvable by membership.steward** today (NETWORK NET-7 VIOLATED), and **verification-status/policy gating**
  of running an own IdP is PLANNED.
- **Refs:** ADR-0068, ADR-0117, identity-login-realms; FND-15, NETWORK NET-7; PLT-9.

### PLT-13 — Suspension and closure
**Suspension** stops a tenant's principals acting; **history stays readable**. **Closure** withdraws
memberships and grants and triggers **erasure subject to legal retention**. A tenant **governing Networks
cannot close until each is transferred or retired**.
- **Status: PLANNED.** The suspend/close lifecycle (principals-halted + history-readable, cascade
  withdrawal, erasure-subject-to-retention, the governing-Network transfer/retire precondition) is **not
  built** — erasure inherits REGISTRY REG-14 (PLANNED) and the suspend semantics inherit NETWORK NET-4 (PLANNED).
- **Refs:** NETWORK NET-4, REGISTRY REG-14, ADR-0125; DECISION DEC-6.

### PLT-14 — Platform Administration
Admin **visibility is computed server-side from recorded roles**; **every action is re-checked server-side**;
**tenant stewards see only the application queue and tenant list**.
- **Status: PARTIAL / VIOLATED.** Apps gate UI by role/session in JS (debt DEBT-B17), and authority is largely
  read from token role claims rather than recorded state (debt DEBT-B1) — so server-side-recheck-from-recorded-
  roles is not uniformly held. The multi-network console computes manageable sets by role, but with the
  app-host `networks-mine` fabrication caveat (debt DEBT-B2/DEBT-A25). Server-side re-check on **every** admin action
  is **(to confirm)**.
- **Refs:** DEBT-B17 (client-side role gating), DEBT-B1, DEBT-B2/DEBT-A25; network-console-multinetwork; FND-2.

### PLT-15 — Public front door
The public front door exposes **only** apply / verify-email / check-status; it is **rate-limited**,
**bot-protected**, and **separate from admin routes**.
- **Status: PLANNED / TO CONFIRM.** Public no-login surfaces exist (`/t/<tenant>` public apps + SSR agency
  presence, public-apps-and-tenant-home, ADR-0111), but a dedicated **apply/verify/status** front door with
  rate-limiting, bot-protection, and route-separation from admin is **not built / (to confirm)**; CAPTCHA/bot
  protection is not present.
- **Refs:** public-apps-and-tenant-home, ADR-0111; PLT-8/PLT-8a; CLIENT CLI-5 (anti-enumeration).

---

## Shared services and providers

### PLT-16 — Capabilities through platform gateways
Components and apps call capabilities — **notify, model, payment, proofing, …** — through **platform
gateways**, **never a vendor directly**. The gateway is the one place a vendor is reached; the caller names a
capability, not a vendor.
- **Status: PARTIAL.** Gateways exist for several capabilities (model-gateway `/v1/complete|/embed`, notify,
  transcription `/bridge/transcribe`, embed) and the broker mediates all component egress; but not every
  capability is gatewayed (some drivers reach declared hosts directly), and the gateway↔provider binding is
  configured operationally, not from a governed catalog (PLT-17).
- **Refs:** ADR-0074 (operator-configurable platform services), model-gateway, notify, driver-secrets-vault;
  DEBT-A41; COMPONENT CMP-1/CMP-5/CMP-6.

### PLT-17 — The platform authority approves the provider catalog
The **platform authority** approves the **provider catalog** — **security review, data-processing terms,
residency** — via **ChangeRequest**, and sets the **defaults** a tenant inherits.
- **Status: PLANNED.** No governed provider-catalog record or CR-approved provider entries exist; providers
  are wired operationally (Vault keys + env), with no recorded security review / DP-terms / residency.
- **Refs:** ADR-0056 (ChangeRequest), PLT-6 (platform authority decides policy); attribution-source-disclosure
  (ref.source precedent).

### PLT-18 — Tenant admins choose among approved providers; BYO accounts
**Tenant admins choose** among the approved providers and **may bring their own accounts**. Credentials are
stored in the **tenant's Vault area**, used **only by the gateway**, and **never given to components**.
- **Status: PARTIAL.** Per-tenant secrets live in the tenant's Vault area and are injected into gateways/
  drivers by name; components never hold the value (ADR-0030, driver-secrets-vault). But "choose among
  **approved** providers" depends on the PLT-17 catalog (PLANNED), so today it is operator configuration rather
  than an admin choice among a governed set.
- **Refs:** driver-secrets-vault, ADR-0030 (no secrets in components), ADR-0074; COMPONENT CMP-5. PLT-17.

### PLT-19 — Networks may set minimum provider requirements
A **Network** may set **minimum requirements** for its members — e.g. **proofing assurance level**, **model
hosting region**.
- **Status: PLANNED.** No network-level minimum-requirement record is defined or enforced against member
  provider choices.
- **Refs:** NETWORK (membership requirements); PLT-8a (verification/assurance methods); PLT-17.

### PLT-20 — Personal data to a provider needs a lawful basis + a decision record
Sending **personal data** to a provider requires a **lawful basis or consent** and produces a **decision
record**; the provider is **recorded as a data processor**.
- **Status: PLANNED.** No lawful-basis/consent gate on provider egress and no data-processor record; provider
  calls are not currently joined to a consent/decision record.
- **Refs:** REGISTRY REG-14/REG-17 (data protection, erasure), ADR-0103 (consent), DECISION (decision record); DPDP
  (processor obligations). PLT-17.

### PLT-21 — Metered, recorded, with tenant-defined failover
Usage is **metered per tenant**; the **provider and version** are **recorded on every call** (for models,
**identity and version per DECISION DEC-3**); **failover is tenant-defined and recorded**.
- **Status: PARTIAL.** A metering hook exists (component-contract metering, ADR-0049 Part D) and the
  model-gateway records the model used; but **per-call provider+version** recording, the DECISION DEC-3
  model-identity-and-version stamp on every inference, and **tenant-defined, recorded failover** are
  PARTIAL / PLANNED.
- **Refs:** DECISION DEC-3 (model identity+version), ADR-0046..0050 (metering), model-gateway-reasoning-split. PLT-16.

**Identity note.** The **home issuer is not swappable** — it is the tenant's root of trust. A tenant's own
**login system** is a **scoped external issuer** (FND-15), trusted only for that tenant and carrying identity
only. **Proofing sources** are **platform-approved providers** (PLT-16/PLT-17), not issuers of home identity. The
provider-gateway model never applies to the home issuer.

---

## Summary of status

| Rule | Topic | Status | Key debt / refs |
|------|-------|--------|-----------------|
| PLT-1 | Installer minimum + idempotent | PARTIAL | ADR-0115; DEBT-A7/DEBT-A8/DEBT-A32/DEBT-A26/DEBT-B14 |
| PLT-2 | First platform.authority via one-time cred | PARTIAL/PLANNED | ADR-0122; DEBT-A17 |
| PLT-3 | Operator holds no governance role | PARTIAL/TO CONFIRM | ADR-0086/0096; DEBT-A38 |
| PLT-4 | Platform tenant confers nothing | **VIOLATED** | **DEBT-B2**, DEBT-A17 |
| PLT-5 | platform.authority recorded, never zero, SoD | PARTIAL | ADR-0122; DEBT-A17 |
| PLT-5a | Break-glass recovery (custodian quorum) | PLANNED | ADR-0122 (open item) |
| PLT-6 | Platform authority decides policy/verification-status/issuers/suspension | PARTIAL/PLANNED | ADR-0088/0056; NET-4; DEBT-A5–DEBT-A8 |
| PLT-7 | Onboarding mode recorded policy | PARTIAL/TO CONFIRM | ADR-0116; onboarding-composition |
| PLT-8 | Applications are records + steward review | PLANNED | ADR-0116; publish-request-review |
| PLT-8a | Verification methods (gov/company) | PLANNED | DEBT-B8; ADR-0056 |
| PLT-9 | Tenant verification status (verified/unverified); unverified only when self-prov on; quotas, no Network/issuer/marketplace | PARTIAL | ADR-0051/0106 (transitional); DEBT-A28, DEBT-A50; COMPONENT CMP-2/CMP-8/CMP-10/CMP-11 |
| PLT-10 | Approval creates workspace+identity+keys+dir+admin | PARTIAL | network-join-provision; DEBT-B9 (NET-6) |
| PLT-11 | Tenant roles (tenant.admin, network.creator) | PARTIAL | ADR-0122; NET-3 |
| PLT-12 | Tenant own login if verification-status+policy permit | PARTIAL/VIOLATED | ADR-0068/0117; FND-15; NET-7 |
| PLT-13 | Suspension + closure + erasure | PLANNED | NET-4; REG-14; ADR-0125 |
| PLT-14 | Platform admin: server-side from recorded roles | PARTIAL/VIOLATED | DEBT-B17, DEBT-B1, DEBT-B2/DEBT-A25 |
| PLT-15 | Public front door (apply/verify/status only) | PLANNED/TO CONFIRM | public-apps; ADR-0111 |
| PLT-16 | Capabilities via platform gateways, never vendors directly | PARTIAL | ADR-0074; model-gateway/notify; DEBT-A41 |
| PLT-17 | Platform authority approves the provider catalog (CR; security/DP-terms/residency) | PLANNED | ADR-0056; PLT-6 |
| PLT-18 | Tenant admins choose approved providers / BYO; creds in tenant Vault, gateway-only | PARTIAL | driver-secrets-vault; ADR-0030; PLT-17 |
| PLT-19 | Networks set minimum member requirements (assurance, region) | PLANNED | NETWORK; PLT-8a |
| PLT-20 | Personal data to a provider needs lawful basis/consent + decision; processor recorded | PLANNED | REG-14/REG-17; ADR-0103; DPDP |
| PLT-21 | Metered per tenant; provider+version per call (models: DEC-3); recorded failover | PARTIAL | DECISION DEC-3; ADR-0046..0050 metering |

**Tally:** 0 IN PLACE, **10 PARTIAL** (PLT-1, PLT-2, PLT-3, PLT-5, PLT-9, PLT-10, PLT-11, PLT-16, PLT-18, PLT-21), 1 VIOLATED (**PLT-4**),
**8 PLANNED** (PLT-5a, PLT-8, PLT-8a, PLT-13, PLT-15, PLT-17, PLT-19, PLT-20), 4 mixed (PLT-6, PLT-7, PLT-12, PLT-14 carry PARTIAL+PLANNED/
VIOLATED). The governing gap is **PLT-4/DEBT-B2/DEBT-A17** — the platform tenant confers authority instead of a recorded
`platform.authority` role (the ADR-0122 cutover closes PLT-2/PLT-4/PLT-5). PLT-16–PLT-21 (shared services + providers) are
almost entirely ahead of the build: gateways exist, but the governed provider catalog (PLT-17), consent-on-egress
(PLT-20) and per-call provider/version metering (PLT-21) are not yet enforced.

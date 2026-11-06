# NETWORK + TRUST review — Consolidation phase 5, slice 3

**Date:** 2026-11-06 · **Scope:** the `network/` service (branch `feat/trust-plane-phase1`) — the NETWORK plane,
the PARTICIPANT + FEDERATION surfaces, and the TRUST plane (ADR-0119) — against the rules the network service is
responsible for: **NETWORK NET-1..NET-12**, **PARTICIPANT PTC-1..PTC-12**, **FEDERATION FED1..FED8**, and the
FOUNDATIONS rules enforced here (**FND-2, FND-3, FND-4, FND-11, FND-14, FND-15**).
**Method:** three fresh, independent reviewer agents (not the authoring session), read-only, findings-only — no
code changed. Evidence is `file:line` in `network/`. The four black-box-reproducible violations were **verified
live** against the running local-dev network service before being encoded as conformance XFAILs.

> **Matrix vs review** (same convention as the kernel/identity slices): STATUS-MATRIX.md is conformance-*measured*
> on the local-dev stack; this review is a code *audit*. New conformance cases (`conformance/run.py` →
> `run_network_review_cases`) encode the reproducible violations as live XFAIL; the rest are SKIP_BUILD with a
> reason + a proposed internal/architectural test. Several TRUST-plane verdicts are **held on local-dev but lax on
> EC2** because the hardened modes (`PLATFORM_AUTHORITY_MODE`, `NETWORK_ADMIN_AUTHZ`, `TRUST_ENFORCE_STEWARD_PROVENANCE`)
> default to the permissive setting on EC2 (documented in `deploy/RELEASE-PLAN.md` / `PRODUCTION-READINESS.md`).

---

## Summary (one page)

**Verdict counts (26 rules):** held **1** (FND-15) · partial **18** · violated **7** (NET-6, NET-7, NET-9, NET-12,
PTC-1, FED7, + FND-11 bootstrap) · not-applicable/PLANNED where noted. No NET rule is fully held; the Network is not
yet a governed lifecycle object, and the one real capability mechanism (`/v1/grants`) and the federation trust
directory (`/v1/participants`) are **unauthenticated**.

**Top risks (most serious first):**
1. **Unauthenticated capability-grant store** (NET-9 — *critical*, **DEBT-B34**). `POST /v1/grants`
   (api.py:2360-2366) stores any id+signature body with no auth, no `grant.steward` gate, no signature verify, no
   grammar/version/wildcard check; `/v1/grants/revoke` (api.py:3089-3096) is unauth delete-by-id. The kernel/broker
   then **enforce** these `governance.access_grant` rows. *Verified live: unauth well-formed POST → 200 `{stored}`.*
2. **Unauthenticated trust-directory admission** (PTC-1/FED7 — *critical*, **DEBT-B33**). `POST /v1/participants`
   (api.py:332-345) binds/overwrites authority-signed participant keys with no auth; that store is what
   `hub.verify_message` and credential verify trust, so attacker-signed federation messages + credentials then pass
   as genuine. *Verified live: unauth POST → 200.*
3. **Zero-holder bootstrap self-escalation to `platform.authority`** (FND-11 — *critical*, **DEBT-B35**).
   `GovernanceService.assign_role` (trust/governance.py:110-137) returns `bootstrap_first_holder` on an empty
   `live_holders` set with no installer/caller-authority check; on EC2 the un-audited seeds read as zero governed
   holders, so the window is effectively always open. ADR-0122's "first grant only to the installer/bootstrap
   authority" is unimplemented.
4. **Network directories + member list public-by-default** (NET-12/REG-15 — *high*, **DEBT-B36**). `GET
   /v1/participation`, `POST /v1/service/search`, `GET /v1/service-offerings`, `GET /v1/federation/offerings` all
   answer unauthenticated. *Verified live: anon → 200.*
5. **Issuer trust is service-wide, not `(tenant, net:id)`-scoped, and approvable by `membership.steward`**
   (NET-7/FED6 — *high*, **DEBT-B37**). An issuer approved by joining one Network is honoured for that tenant across
   every Network on the install (api.py:880-891); authn pins tenant + strips roles (authn.py:162-167) so authority
   doesn't widen, but the trust surface does.
6. **Network mints a login on join/membership approve** (NET-6 — *high*, existing **DEBT-B9**). api.py:898-911 /
   751-766 provision an IdP user + temp password (and `platform.tenant-admin` on join) — membership is being
   conflated with an account.
7. **SoD proposer≠approver not enforced** (FND-11 — **DEBT-B38**); **audit chain never verified at runtime**
   (FND-2/FND-12 — **DEBT-B39**); **`/v1/resolve` substring match** (FED7 — **DEBT-B40**).

**New debt opened:** DEBT-B33 (unauth participant admission), B34 (unauth grant store), B35 (zero-holder bootstrap),
B36 (public directories/member list), B37 (issuer trust not net-scoped), B38 (SoD proposer≠approver), B39 (no audit
verifier), B40 (resolve substring); DEBT-A78 (network not a lifecycle object), A79 (service.provide not a grant),
A80 (no decision/consent ref on exchange), A81 (no presentation binding). **Existing debt confirmed live:** B1, B2,
B6, B9, B11, B12, B13; A14, A16, A17, A18, A70.

**Correctly PLANNED (do not regress to "violated"):** the Network-as-lifecycle-object (no status field),
cross-installation request wiring (FED5 general), per-role conformance gate (PTC-11/FED4), the event spine (PTC-9),
settlement (PTC-10), Network discovery/root-of-trust (FED8). The `service.provide`/`service.call` grammar,
capability catalog, `capability.steward`/`grant.steward` roles, SoD-second-approver and the one decision function
all exist only in the **shadow** `trust/` module (`_TRUST is None` on the live `api.py` path, api.py:3677), so they
gate nothing today.

**What is genuinely sound (credit where due):** JWT verify enforces an explicit alg↔kty allowlist (authn.py:119,138);
FND-15 federated-issuer containment is real — a dynamically-registered issuer may assert only its one recorded
tenant and has **all** role claims stripped (authn.py:162-167); the hub verifies every message signature against
the directory before routing (hub.py:18-30); credential verify does offline issuer-signature + revocation + expiry
(api.py:2911-2945); and the Trust plane's *pure* decision core is grant-based and ignores token roles
(trust/authorize.py:82-117, trust/roles.py:56-66).

---

## Per-rule findings

### NETWORK (NET-1..NET-12)

| rule | verdict | sev | evidence (network/) | debt |
|---|---|---|---|---|
| NET-1 identity (net:id≠slug) | partial | high | legacy gate compares `claims.tenant != network` string (api.py:798); role mode keys role_assignment on resolved net_id (trust_admin_authz.py:224-230); selected globally by `NETWORK_ADMIN_AUTHZ` (default legacy, :68) | DEBT-B11, B2 |
| NET-2 creation (creator role, DRAFT, governing tenant) | partial→absent | medium | `network_register` records only a directory profile, no status/creator/governing-tenant (api.py:961-997); no capability catalog | DEBT-A78, A17 |
| NET-3 roles (+SoD, never-zero-admin) | partial | medium | admin plane knows only network.admin/membership.steward (trust_admin_authz.py:58-59); capability.steward/grant.steward unreferenced on the live path; SoD-second-approver in shadow trust/ (`_TRUST=None`, api.py:3677) | DEBT-A14 |
| NET-4 status (draft/active/suspended/retired) | partial→absent | high | NETWORKS records have **no status field** (api.py:988-996); no suspend/retire; exchange never consults network status; only offering-level suspend exists (api.py:2947-2962) | DEBT-A78, A16 |
| NET-5 membership (belonging only; invite/accept, suspend) | partial | medium | tenant-free request/decide (api.py:813,862), approve/reject/revoke; federated handshake present; invite→accept + suspend absent (seed_base.py:195) | DEBT-A78, ADR-0116 |
| NET-6 join creates no login | **violated** | high | participation_decide mints an IdP user + temp password on approve (api.py:898-911); join_decide provisions a tenant + platform.tenant-admin login (api.py:751-766) | DEBT-B9 |
| NET-7 issuer trust (network.admin only + (tenant,net:id)-scoped) | **violated** | high | service-wide `TRUSTED_ISS`/register_issuer under op=membership (api.py:880-891); admits membership.steward (trust_admin_authz.py:59); no net:id scope | **DEBT-B37**, B13, FND-15 |
| NET-8 classifications descriptive only | partial/to-confirm | low | eKYC auto-admits membership when participant_type.identity==citizen (api.py:936-947); kind==developer gates the dev surface (authority.py:102-103) | DEBT-B7, B2 |
| NET-9 capabilities (catalog/grammar/no-wildcard/version/grant-steward) | **violated** | critical | `POST /v1/grants` + `/v1/grants/revoke` unauthenticated + ungated (api.py:2360-2366, 3089-3096); real grants carry raw schema-id lists, no version pin (api.py:2402-2404); grammar only in shadow | **DEBT-B34**, A18, B12 |
| NET-10 publish Service requires service.provide grant | partial | medium | publish gated on tenant-admin token role (api.py:2672); provide-grant only shadow-logged (api.py:1055); eligibility IS carried (api.py:2720-2742) | DEBT-A79 |
| NET-11 exchange via the one decision function (+decision record) | partial | medium | service_route records a transaction ledger (api.py:3045-3055) but checks no call/provide grant, no consent, emits no governance.decision | DEBT-A80, B12, B1 |
| NET-12 directory members-only (+ member lists) | **violated** | high | `GET /v1/participation` (api.py:952-958), `POST /v1/service/search` (api.py:3000-3023), `GET /v1/service-offerings` (api.py:2750-2757), `GET /v1/federation/offerings` (api.py:3516-3530) all unauth; no REG-15 flag | **DEBT-B36**, B6, REG-15 |

### PARTICIPANT (PTC-1..PTC-12)

| rule | verdict | sev | evidence (network/) | debt |
|---|---|---|---|---|
| PTC-1 registration + keys in platform-signed directory | partial (**directory integrity violated**) | high | request/decide gated (api.py:813-916); **raw admission `POST /v1/participants` unauthenticated + overwriting** (api.py:332-345) | **DEBT-B33** |
| PTC-2 auth = identity only (FND-15) | partial (held at Network boundary) | medium | federated containment strips roles + pins tenant (authn.py:162-167); residual kernel-side issuer+role is DEBT-B1 | DEBT-B1 |
| PTC-3 register Service (iface/endpoint/version/data-use; provide grant) | partial | medium | iface/endpoint/version captured (api.py:1060-1063); gate is membership; provide only shadow-compared; data-use absent | DEBT-A79 |
| PTC-4 offerings per OFFERINGS | partial | info | services only (api.py:1040-1065); Benefit/Information deferred to OFFERINGS | — |
| PTC-5 inbound Network-signed + decision/consent ref; never widen | partial | high | never-widen = offering-scoping + fail-closed (api.py:2500-2545); **no decision-ref/consent-ref verified** | **DEBT-A80** |
| PTC-6 signed responses + fulfilment evidence | partial | low | signed hub responses (hub.py:32-51); grant-checked signed data-read receipt (api.py:3549-3578); evidence not durably joined to a decision | — |
| PTC-7 credential issuance (typed issue grant, signed, revocation) | partial | medium | signed w/ steward key + governed-type + revocation (api.py:2820-2884); gate = member of issuing tenant (any role), no per-type issue grant (api.py:2797-2808) | — |
| PTC-8 presentation verification (holder/recipient/purpose) | partial/**violated** | medium | verify = issuer-sig + revocation + expiry only (api.py:2918-2940); no holder-proof/recipient/purpose/nonce → VC replayable | **DEBT-A81** |
| PTC-9 events (granted types; idempotency) | n/a (PLANNED) | info | no event endpoints (only hub broadcast log) | spec PLANNED |
| PTC-10 settlement references | n/a (PLANNED) | info | absent | spec PLANNED |
| PTC-11 per-role conformance before activation | partial (PLANNED gate) | low | conformance.run is component-only (conformance.py:128-190); participation/decide has no conformance gate (api.py:862-916) | spec PLANNED |
| PTC-12 public versioned protocol; never /bridge | partial | info | no `/bridge/*` in the network service (grep clean); the never-/bridge concern is first-party→app-host, outside this service | app-host |

### FEDERATION (FED1..FED8)

| rule | verdict | sev | evidence (network/) | debt |
|---|---|---|---|---|
| FED1 one governing tenant hosts a Network | partial | info | networks bootstrapped + profile (ensure_install.py:177; api.py:961-996); host-vs-operator framing not modelled | — |
| FED2 creation needs network.creator; never creates tenants | partial (PLANNED) | low | creation via bootstrap + network-admin-gated `/v1/networks` (api.py:785-805); no network.creator capability | — |
| FED3 join = registration in host registry | partial | medium | mode-1 request carries jwks + decide does a trust handshake (api.py:850-893); cross-install registration PLANNED | — |
| FED4 per-role conformance before activation | n/a (PLANNED) | info | no per-role suite/gate (see PTC-11) | spec PLANNED |
| FED5 cross-install requests signed by registered keys | partial | medium | signed-relay primitive verifies against the directory (hub.py:18-30; mail relay api.py:3616-3661); generalised request PLANNED | — |
| FED6 home issuer trusted only for its own participants | partial | medium | FND-15 containment real (authn.py:162-167); but trust is install-wide per-tenant, not per-Network | **DEBT-B37** |
| FED7 host directory authoritative; verify; fail-closed | **violated** | high | hub verifies against the directory (hub.py:20-29); **but admission unauthenticated** (api.py:332-345) and **resolve uses substring match** (api.py:3106) | **DEBT-B33, B40** |
| FED8 directory-of-Networks / root of trust | n/a (DEFERRED) | info | explicitly deferred in spec | spec DEFERRED |

### FOUNDATIONS enforced in the TRUST plane

| rule | verdict | sev | evidence (network/) | debt |
|---|---|---|---|---|
| FND-2 authority from recorded state; tamper-evident | partial (lax on EC2 default) | high | grant-based core (authorize.py:82-117); tenant-name authority in shadow default (trust_wiring.py:67,79-83); audit chain built but **never verified** (audit.py:76-111) | DEBT-B2, **B39** |
| FND-3 nothing implied by tenant/membership/issuer | partial (violated in shadow default) | high | token roles ignored (trust/roles.py:62-66); admin plane never reads token roles (trust_admin_authz.py:230); **tenant→platform-authority in shadow default** (trust_wiring.py:67) | DEBT-B2 |
| FND-4 tenant ≠ network | partial (violated in legacy default) | medium | legacy default = `tenant==network` (trust_admin_authz.py:66-68); `cross_network_write` conflates slug/net:id/tenant (trust_wiring.py:204); role mode resolves slug→net:id (:224-235) | DEBT-B11, B2 |
| FND-11 SoD + last-holder floor | partial (bootstrap gap **critical**) | high | SoD + floor + retire-floor present (platform_authority.py:112-135; governance.py:179-182); but first-holder bootstrap has no caller-authority check (governance.py:119-120) and SoD omits approver≠proposer (platform_authority.py:119) | **DEBT-B35, B38**, A17 |
| FND-14 authority traceable; grantor named | partial | medium | governance path records granted_by+op_id+audit (governed_store.py:283-300); but `TRUST_ENFORCE_STEWARD_PROVENANCE=0` default (EC2) honours un-provenanced seeds (trust/roles.py:31) | DEBT-A70 |
| FND-15 external issuers scoped; identity-only | **held** | info | register_issuer pins tenant + federated flag (authn.py:88-96); verify rejects tenant mismatch + strips all roles (authn.py:158-167) | — |

## Conformance cases added

`run_network_review_cases()` (internal). **Live XFAIL (violation reproduced, verified against the running service):**
`NET-9/DEBT-B34` (unauth `POST /v1/grants` → 200 stored), `PTC-1/FED7/DEBT-B33` (unauth `POST /v1/participants` →
200), `NET-12/DEBT-B36` ×2 (anon `GET /v1/participation` and `POST /v1/service/search` → 200). **SKIP_BUILD**
(reason + proposed internal/architectural test) for every other NET/PTC/FED rule and for FND-2/3/4/11/14 — including
the not-black-box-reachable criticals **DEBT-B35** (zero-holder bootstrap — needs a zero-governed-holder precondition
the seeded stack never has) and **DEBT-B38/B39/B40**. The matrix now shows NET-9, NET-12, PTC-1, FED7 VIOLATED; the
rest PLANNED(needs-build) or (FND-15) HELD.

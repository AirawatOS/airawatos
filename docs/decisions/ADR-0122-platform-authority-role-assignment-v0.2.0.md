# ADR-0122 — `governance.role_assignment` v0.2.0: scoped roles (platform / tenant / network)

**Status:** Accepted (design) — implementation in progress locally (P0–P4). REVISED 2026-11-03.
**Extends:** [[ADR-0119]] (Trusted Network Platform — four planes; `authorize()` candidate-grant model),
[[ADR-0118]], [[ADR-0028]] (civic personas / role grants). Supersedes the inline seed in `deploy/local-dev/PLAN.md`.

## Context

"Who is the authority" is expressed by ambient facts, not recorded grants:
1. `is_platform_authority` = `claims.tenant == TRUST_AUTHORITY_TENANT` (a **tenant-name** check in
   `trust_wiring._actor_context`) — contradicts ADR-0119 D1 ("authority = *holding a live grant*, never
   *being of type X*"), and in local-dev means no principal can be seeded as the first steward unless its
   tenant happens to equal the authority tenant (the step-2 chicken-and-egg).
2. `governance.role_assignment@0.1.0` only carries a `network` (`net:` id) — it cannot express platform- or
   tenant-scoped authority.

## Decision

`governance.role_assignment@0.2.0` carries an explicit **scope** with **three types** and a role set spanning
all three, evaluated by the same `authorize()` / live-assignment path. One schema version covers all scopes.

### Scope (one schema version, three types)
`scope`: `{ "type": "platform" | "tenant" | "network", "ref": <id> }`
- `platform` → `ref` is the platform/install id (a per-install constant or the operator `kind:operator` id).
- `tenant`   → `ref` is a tenant id (`<tenant>`).
- `network`  → `ref` is a `net:<ULID>` id (today's implicit meaning).

### Roles (by the scope they are valid in)
- `platform.authority` — **platform** scope only. The platform's root governance authority.
- `tenant.admin` — **tenant** scope only. Administers one tenant (its users/config/installs).
- `network.creator` — **tenant** or **platform** scope. May create new networks (bounded by scope).
- the existing network stewardship roles — **network** scope only:
  `network.admin`, `membership.steward`, `capability.steward`, `grant.steward`.
- Cross-check enforced at write (422): a role may only be assigned in a scope type its definition permits.

### Schema delta (0.1.0 → 0.2.0)
- Add `scope` object (required). Deprecate the bare top-level `network` field (folded into
  `scope.type:"network"`); still read on 0.1.0 records during the soak.
- `required` → `["schema","id","principal","scope","role","status"]`.
- Role enum extended with `platform.authority`, `tenant.admin`, `network.creator`.
- Validity window + `status` (`active`|`revoked`) unchanged.

### Separation of duties (security-critical grants)
Applies to **every security-critical role** — now including `platform.authority` **and** `tenant.admin`
(alongside `capability.steward` / `grant.steward`):
- **First grant** of a security-critical role in a scope is allowed only when **zero live holders** exist in
  that scope, and only to the installer/bootstrap authority (platform scope) or the parent authority
  (a tenant.admin seed authorized by a platform.authority).
- **Thereafter**, a new grant requires a `governance.change_request` whose approved mutation hash matches,
  **approved by a *different* live holder of the same (role, scope)** than the proposer. Never a self-grant,
  never a token-role, never a tenant-name shortcut.

### Last-holder floor
Revoking/lapsing the **last live holder** of `platform.authority` (per platform scope) **or** `tenant.admin`
(per tenant scope) is refused (`409 last_<role>`). The scope must always retain ≥1 live holder of these two
roles so governance of that platform/tenant can never be locked out.

### Break-glass recovery — EXPLICIT OPEN ITEM (not in this slice)
Dropping a platform/tenant to **zero** holders (full rotation, lost-key recovery, decommission) is deliberately
**out of scope**. It requires a separately-designed, operator-signed, out-of-band path (likely the ADR-0086
operator-attestation seam). Tracked as an open item; the floor above makes the normal path safe without it.

### How authority is evaluated (the behaviour change)
- `is_platform_authority(principal)` ⇔ a **live** assignment `role=="platform.authority"`,
  `scope=={type:"platform", ref:<this platform>}`, `status=="active"`, in-window, for `principal`.
- `is_tenant_admin(principal, tenant)` ⇔ a live assignment `role=="tenant.admin"`,
  `scope=={type:"tenant", ref:<tenant>}`.
- Both evaluated through `live_role_assignments` (the existing path), **issuer-scoped** (honoured only for a
  `iss==HOME_ISS` token). `TRUST_AUTHORITY_TENANT` is retained ONLY as the platform `scope.ref` default, never
  as the authority grant.

### Migration (0.1.0 → 0.2.0): additive, dual-read, non-destructive
- Read: a 0.1.0 record is read as `scope:{type:"network", ref:<network>}`.
- One-time tool (`trust/migration/`): rewrites live 0.1.0 records to the `scope` shape, one
  `platform.audit_event` each; destroys nothing; both shapes validate during a bounded soak.
- The migration does NOT invent a `platform.authority`/`tenant.admin` holder; a deliberate first-grant
  (installer/bootstrap) names the initial holders.

## Implementation plan (phased; each phase its own commit, tests-first)
- **P0** — schema + validators (dual-read 0.1.0; scope/role cross-check). No behaviour change. Red-first tests.
- **P1** — `is_platform_authority` (and `is_tenant_admin`) candidate-grant predicates, run in **shadow**
  alongside the tenant-name check; log disagreements. No decision change.
- **P2** — SoD (different-holder CR) + last-holder floor for `platform.authority` + `tenant.admin` in
  `can_assign_role` / the revoke path. Tests: self-approved CR → deny; different-holder CR → allow; revoke
  last holder → 409.
- **P3** — cut over `_actor_context` to the predicate (drop the tenant-name derivation); run the 0.1.0→0.2.0
  migration; **seed a `platform.authority` record** so local-dev keeps working. Prove a tenant-name-only
  principal is no longer authority and a seeded holder is.
- **P4** — docs + readiness (platform-authority provisioning + break-glass gap); record the installer
  first-grant in bootstrap.

## Risks / open questions
- Platform `scope.ref` identity: pin the stable per-install constant vs operator id.
- CR approver identity must be server-verifiable ("a different live holder approved").
- **Break-glass (zero holders): explicit open item** (above).
- Keep the admin-plane (`trust_admin_authz`, `network.admin`) path untouched — platform/tenant authority is
  orthogonal to per-network admin.

## Consequences
Authority (platform, tenant, network) becomes first-class, auditable, SoD-protected, floor-protected grants
evaluated like every other role — closing the tenant-name ambient-trust gap and the step-2 first-steward
chicken-and-egg. One additive migration + a dual-run soak; rollback = retain the tenant-name derivation (P3
is the only behaviour flip, gated behind the soak + the seeded holder).

# ADR-0122 — `governance.role_assignment` v0.2.0: platform scope + `platform.authority`

**Status:** Proposed (design only — NOT implemented)
**Extends:** [[ADR-0119]] (Trusted Network Platform — four planes; `authorize()` candidate-grant model),
[[ADR-0118]]. Supersedes the inline seed in `deploy/local-dev/PLAN.md`.
**Date:** 2026-11-03

## Context

Today "who is the platform authority" is expressed two ways, neither first-class:
1. `is_platform_authority` is derived in `trust_wiring._actor_context` as `claims.tenant == authority_tenant`
   — a **tenant-name** check (whoever logs in under the `TRUST_AUTHORITY_TENANT` tenant is authority). That is
   an ambient, config-named authority, not a recorded grant, and it contradicts ADR-0119 D1 ("authority comes
   from *holding a live grant*, never from *being of type X*").
2. The admin plane overloads `network.admin` on the network's own `net:` id for per-network administration.

There is no governed record that says "principal P is the authority over this *platform*." `governance.role_assignment@0.1.0`
only carries a `network` field (a `net:` id); it cannot express a platform-scoped authority. We want platform
authority to be a **recorded, auditable, separation-of-duties-protected** grant like every other steward role,
evaluated by the same `authorize()` path.

## Decision

Introduce `governance.role_assignment@0.2.0`: add an explicit **scope** and a `platform.authority` role, and
make `is_platform_authority` read a live platform-scoped assignment instead of a tenant-name match.

### Schema delta (0.1.0 → 0.2.0)
- Add `scope` object: `{ "type": "platform" | "network", "ref": <id> }`.
  - `type:"network"` → `ref` is the `net:<ULID>` id (today's implicit meaning).
  - `type:"platform"` → `ref` is the platform/operator id (e.g. the operator `kind:operator` id, or a
    well-known constant like `platform:<install-id>`).
- Extend `role` enum with `platform.authority` (kept **distinct** from the four network stewardship roles
  `network.admin` / `membership.steward` / `capability.steward` / `grant.steward`; those remain `scope.type:"network"` only).
- `required` becomes `["schema","id","principal","scope","role","status"]`. The bare top-level `network` field
  is **deprecated** (folded into `scope`), still accepted on read for 0.1.0 records during the soak.
- Validity window (`valid_from`/`valid_to`) and `status` (`active`|`revoked`) are unchanged.
- Constraint: `platform.authority` is valid **only** with `scope.type:"platform"`; the four network roles are
  valid **only** with `scope.type:"network"`. Enforced at write (422 on mismatch).

### Who may assign `platform.authority` (separation of duties)
- **Installer bootstrap, once:** on a fresh platform the installer/bootstrap writes the first
  `platform.authority` assignment (the installer *is* the authority — same trust seam as base-OS seeding).
  Allowed only when **zero** live `platform.authority` holders exist (a true first-grant).
- **Thereafter, ChangeRequest-only:** a new `platform.authority` grant requires a `governance.change_request`
  whose approved mutation hash matches the write, AND the CR must be **approved by a *different* existing live
  `platform.authority` holder than the proposer**. Never a self-grant; never a plain token role; never the
  tenant-name shortcut. So a second/third holder is only added with a sitting holder's explicit approval.
- Writing `platform.authority` outside these two paths is refused (403), even for a `network.admin`.

### Revocation floor (last-holder protection)
- Revoking (`status:"revoked"`) or letting lapse a `platform.authority` holder is **refused if it would leave
  zero live holders** (`409 last_platform_authority`). The platform must always retain ≥1 live authority so it
  can never be locked out of its own governance.
- Dropping to zero (decommission / rotate-all) needs an explicit, separately-designed **break-glass** path
  (operator-signed, out of band) — **not** this slice.

### How `is_platform_authority` is evaluated (the behaviour change)
Replace the tenant-name check with a candidate-grant lookup (ADR-0119 D1 style):
> `is_platform_authority(principal)` ⇔ there exists a **live** `governance.role_assignment` with
> `role == "platform.authority"`, `scope == {type:"platform", ref:<this platform>}`, `status=="active"`,
> within its validity window, for `principal`.

- Evaluated through the same `authorize()` / `live_role_assignments` path already used for network roles,
  reusing the mint-on-demand Trust reader.
- **Issuer scope still applies**: the assignment is honoured only for a principal whose token `iss == HOME_ISS`
  (a non-home/federated token can never be platform authority, regardless of a stored row).
- `trust_wiring._actor_context` stops deriving authority from `claims.tenant == authority_tenant`; it calls the
  predicate above. `TRUST_AUTHORITY_TENANT` is retained only as the **install/platform ref** default, not as
  the authority grant itself.

### Migration (0.1.0 → 0.2.0): additive, dual-read, non-destructive
- **Read:** a 0.1.0 record (role on bare `network`) is read as `scope:{type:"network", ref:<network>}`.
- **Write:** new writes use the `scope` shape.
- **One-time migration tool** (`trust/migration/`): rewrites each live 0.1.0 record into the `scope` shape,
  emits a `platform.audit_event` per rewrite; **no 0.1.0 record is destroyed**. Both shapes validate during a
  bounded soak, then 0.1.0 writes are rejected (reads still tolerated).
- The existing prod bootstrap record (`user://airawat/steward` → `network.admin` on `net:KQCP2EWWMSVSAJHK`)
  migrates to `scope:{type:"network", ref:"net:KQCP2EWWMSVSAJHK"}` with no behaviour change.
- **Platform-authority seed:** the migration does **not** invent a `platform.authority` holder. A deliberate
  first-grant (installer bootstrap, item above) names the initial holder explicitly.

## Implementation plan (phased; each phase its own commit, tests-first)

**P0 — schema + validators (no behaviour change).**
`trust/schemas.py`: add v0.2.0 `TRUST_SCHEMAS` entry (scope block, extended role enum, scope/role cross-check),
keep 0.1.0 registered for dual-read. Red-first tests: scope/role mismatch → 422; network role with platform
scope → 422; 0.1.0 record still validates.

**P1 — `is_platform_authority` candidate-grant predicate (dark / dual-run).**
Add the predicate reading a live platform-scoped assignment; run it **in shadow** alongside the current
tenant-name check and log disagreements (DualRunComparator, as ADR-0119 did for authz). No decision changes yet.
Tests: holder → true; revoked/expired/network-scoped/non-home-issuer → false.

**P2 — assign/revoke governance (SoD + floor).**
Enforce: first-grant only at zero holders; subsequent grants require a CR approved by a *different* live holder
(reuse `GovernanceService.verify_and_consume` for the CR hash); revocation refused at the last live holder.
Tests: self-approved CR → denied; second-holder via a sitting holder's CR → allowed; revoke last holder → 409;
revoke with ≥2 holders → allowed.

**P3 — cut over `_actor_context` + migration.**
Flip `is_platform_authority` to the predicate (remove the tenant-name derivation); run the 0.1.0→0.2.0
migration tool (dry-run → apply → dry-run, idempotent, audited) like `seed_trust_schemas`. Soak with dual-read.
Tests: full governance flow (define_capability / issue_grant) still authorized for the migrated holder; a
tenant-name-only principal (no grant) is **no longer** authority.

**P4 — docs + readiness.**
Update ADR-0119 cross-refs; add the platform-authority provisioning + break-glass gap to
`deploy/PRODUCTION-READINESS.md`; record the installer first-grant step in the bootstrap.

### Risks / open questions (to resolve before building)
- **Platform ref identity:** pin exactly what `scope.ref` for `type:"platform"` is (operator id vs a per-install
  constant). Must be stable across restarts and distinct per install.
- **CR approver identity:** confirm `governance.change_request` carries approver identity verifiably so "a
  *different* live holder approved" is checkable server-side (not from the body).
- **Break-glass (zero holders):** explicitly out of scope here; needs an operator-signed path (ADR-0086 operator
  attestation is the likely seam).
- **Interaction with `NETWORK_ADMIN_AUTHZ` role mode:** platform authority is orthogonal to per-network admin;
  ensure the admin-plane path (`trust_admin_authz`) is untouched by this change (it keys on `network.admin`).

## Consequences
- Platform authority becomes a first-class, auditable, SoD-protected grant evaluated like every other role —
  closing the "authority by tenant name" ambient-trust gap (ADR-0119 D1 compliance).
- One more migration + a dual-run soak; no destructive change; rollback = keep the tenant-name derivation (P3
  is the only behaviour flip and is gated behind the soak).

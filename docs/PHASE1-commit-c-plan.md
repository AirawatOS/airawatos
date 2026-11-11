# Phase 1 — Commit C plan: API / enforcement wiring (for review BEFORE touching network/api.py)

- Date: 2026-10-31
- Status: **PLAN — approved to plan; `network/api.py` implementation on HOLD until this plan is signed off.**
- Builds on the Trust-plane core + repository + GovernanceService (branch `feat/trust-plane-phase1`:
  `fb14e21`→`245c4bd`) and the real-kernel contract + strict-schema gates (both GREEN).

## Status at the gate

```
Trust core / adapter / GovernanceService      PASS
Real kernel+Postgres contract (10/10)         PASS   (incl. seq_key ordering, wrong-tenant refusal)
Exact-id resolve correction                   PASS
Strict governed-schema validation             PASS   (4 accept / 7 reject, SCHEMA_VALIDATE=strict)
Commit C planning                             THIS DOC
network/api.py implementation                 HOLD
Participant migration / back-fill             HOLD
```

## The three layers (never collapsed)

```
HTTP endpoint (network/api.py)
   │  authenticate caller token (authn.verify)
   │  read the caller's ACTUAL roles from the token
   │  resolve + verify platform authority (identity fact)
   │  resolve + verify the change-request record (if the op needs one)
   ▼
ActorContext   ← CONSTRUCTED here, from verified facts only
   ▼
GovernanceService   (role / change-request / platform-authority decision)   [trust/governance.py]
   ▼
GovernedRegistryTrustStore   (invariants + persist + audit)                  [trust/governed_store.py]
   ▼
Kernel registry   (platform-service token stays inside HttpRegistryClient)
```

## The hard rule (non-negotiable)

The **endpoint constructs `ActorContext`**. The request body MUST NOT be able to supply any of:
`is_platform_authority`, `change_request_ref`, `token_roles`. These are server-derived from the
authenticated identity + verified records.

```
BAD   POST /v1/governance/assign-role { "principal":"p", "role":"grant.steward",
                                        "is_platform_authority": true, "change_request_ref": "cr1" }

GOOD  POST /v1/governance/assign-role { "principal":"p", "role":"grant.steward",
                                        "change_request": "cr1" }
        → authenticate caller → read real roles → resolve CR cr1 → verify it →
          ActorContext(actor=<verified sub>, token_roles=<verified>,
                       is_platform_authority=<verified fact>, change_request_ref="cr1")
        → GovernanceService.assign_role(ctx, ...)
```
An endpoint handler constructs the context; it never copies these fields from the body.

## Change-request binding (makes an approval non-reusable)

New governed object:
```
governance.change_request {
  id, network, action, target, proposed_mutation_hash,
  status: "approved", approved_by, approved_at
}
```
The endpoint, before setting `ctx.change_request_ref`, recomputes `hash(requested mutation)` (canonical
JCS of the exact mutation it is about to perform) and requires ALL of:
```
cr.status == "approved"
AND cr.network == request.network
AND cr.action == the action being performed
AND cr.target == the target being mutated
AND cr.proposed_mutation_hash == hash(requested mutation)
AND caller is entitled to exercise the CR
```
So an approved CR for "change network name" cannot be replayed to "assign grant.steward" — the
mutation hash (and action/target) won't match.

## Review additions (approved before coding)

**CR consumption / replay protection.** A change-request is single-execution. The object gains
`status: approved | consumed`, `consumed_at`, `consumed_by_op_id`. The flow is: verify CR → create
`op_id` → perform the mutation idempotently → mark the CR `consumed` by that `op_id`. An already
`consumed` CR is refused for a *new* op; replay of the *same* `op_id` (for an inherently idempotent
op) is allowed, but a fresh operation can never be minted from a consumed approval. This reuses the
repository's existing `op_id`, so `GovernanceService` generates one `op_id` and threads it to both the
mutation and the CR consumption.

**Canonical mutation-hash envelope (reproducible at execution).** `proposed_mutation_hash` =
`HASH_SUITE(canonical({network, action, target, mutation}))`, where `mutation` contains ONLY the
caller-supplied intent and EXCLUDES every server-generated value (`op_id`, timestamps, audit ids,
generated grant/record ids, `status`, `grantor`). The endpoint recomputes the hash over the same
envelope at execution; otherwise the approved hash can't be reproduced.

**Defer the public authorize endpoint.** Commit C uses an INTERNAL `authorize(...)` call site only —
no public `GET /v1/governance/authorize`. A generic external authorization oracle is a new public
contract we don't need yet; add an introspection endpoint later with its own access policy if a real
use case appears.

## Endpoints to wire (thin handlers over GovernanceService; no logic in api.py)

Governance writes (each: authenticate → build verified ActorContext → call the service):
- `POST /v1/governance/grants` → `issue_grant`
- `POST /v1/governance/grants/revoke` → `revoke_grant`
- `POST /v1/governance/memberships` → `set_membership`
- `POST /v1/governance/roles` → `assign_role`   (security-critical roles require a verified CR)
- `POST /v1/governance/capabilities` → `define_capability`
- `POST /v1/governance/identity-sources`, `.../assurance` (register IdP / assert assurance)

Reads / enforcement:
- `GET /v1/governance/authorize?...` or an internal `authorize()` call site — the participant check
  used by service-exchange endpoints, over the repository (read-only).

Cross-cutting: the kernel platform-service JWT is configured into the adapter's `HttpRegistryClient`
(env/Vault); it is never returned, logged, or reachable by a steward; a steward only ever presents
their own token to these endpoints.

## Strict-schema prerequisite — DONE for the kernel; governance path is Commit C

The governed `TRUST_SCHEMAS` are proven to accept valid / reject malformed under the real kernel's
`SCHEMA_VALIDATE=strict` (harness seeds the kernel's `installed_schemas`; see
`network/trust/contract/strict_schema_test.py`). In production the same defs are seeded via network
governance (`POST /v1/schemas`) — that governance seeding is part of Commit C's deploy step, not a new
mechanism.

## Sequence after this plan is signed off

```
seed TRUST_SCHEMAS (governed) + strict ON
      ↓
Commit C API wiring (endpoints + verified ActorContext + CR binding)
      ↓
API / enforcement tests (incl. body-cannot-assert-authority; CR mismatch refused)
      ↓
type_capability_map  (per network; Claude Code proposes)
      ↓
migration report  (per type: capabilities/version/scope/grantor/affected-count)
      ↓
HUMAN APPROVAL
      ↓
grant back-fill  (first write that touches existing participants)
      ↓
dual-run (type vs grant) on real operational flows
      ↓
divergence report
      ↓
HUMAN APPROVAL
      ↓
flip enforcement → grant   → one-release legacy shadow → remove type checks
```

Two human gates (migration report; divergence report) are never crossed automatically. No participant
record is written until after the first human approval.

# Phase 1 Detailed Design — Trust Plane (rev 3, for sign-off before code)

- Date: 2026-10-31 (rev 3 — second Phase-1 design review)
- Governs: **Phase 1** of `PLAN-trusted-network-platform-evolution.md` (ADR-0119 D1, D2, D11; the AuditEvent
  contract shared across all phases).
- Status: **Design for sign-off. No code until explicit approval of this rev. Implementation is on HOLD.**
- Design principle: *the Trust plane must remain boring and precise.* Almost everything depends on it.
- Rev-3 changes (all from the second review): (1) per-field mutation authority on `network.network`;
  (2) stewardship-role assignment/bootstrap governance; (3) capability-definition semantic immutability +
  versioning; (4) removed the unenforced `constraints` field; (5) removed `grantable_by` (grant.steward only);
  (6) audit chain partitioned per (network, emitter) + keyed HMAC subject hash; (7) revoked grants are terminal;
  (8) `network.status` participates in `authorize()`.

---

## 0. Storage & identity decisions

All Phase-1 objects are **governed registry records** (bitemporal). Network identity is an **immutable** opaque id
with a mutable slug alias:
```
id    net:01J...   # immutable ULID; the ONLY thing code references
slug  avsar         # mutable alias; operator-scoped; URL/config only
name  Avsar Livelihood Network
```

---

## 1. Schema definitions

### 1.1 `network.network` (v1.0.0) — with per-field mutation authority (rev-3 #1)

A single `network.admin` edit must **not** be able to bypass separation of duties by repointing the catalog,
registering a trusted IdP, or downgrading audit. Mutation authority is per field-class:
```
id                 immutable
slug, name, charter                                  -> network.admin
features (non-security: wallet/individual_identity/event_exchange UI toggles) -> network.admin
classifications, assurance_policies                  -> capability.steward
capability_catalog (the REFERENCE this network points to)  -> GOVERNED CHANGE-REQUEST (ADR-0056)
identity_sources   (add/remove a trusted IdP)        -> GOVERNED CHANGE-REQUEST
planes_used        (what the network may do)         -> GOVERNED CHANGE-REQUEST
features.audit     ('full' -> 'metadata' downgrade)  -> GOVERNED CHANGE-REQUEST
status             (active/suspended)                -> platform authority / governance (see §2 step 0)
```
"Governed change-request" = the ADR-0056 decided-change-request path: it requires the appropriate steward, is
auditable (emits a `governance.change` AuditEvent), and supports optional dual-control. Security-sensitive changes
are therefore never a plain admin field edit. Note the distinction: **editing catalog contents** is
`capability.steward` (§1.4); **repointing `capability_catalog` to a different catalog** is change-request-only —
both guards are needed or an admin could swap the whole catalog.

### 1.2 `network.classification` (v1.0.0) — descriptive vocabulary, zero authorization
`{ network, code, label, description }` · `x_indexes:[network,code]` · edit: `capability.steward`. Never read by
`authorize()`.

### 1.3 `network.membership` (v1.0.0) — the (participant, network) edge
`{ network, participant(->ParticipantIdentity), classifications[], status(pending|approved|suspended|revoked),
since, decided_by, decided_at }` · `x_indexes:[network,participant,status]` · edit: `membership.steward`.

### 1.4 `network.capability_catalog` (v1.0.0) — what is grantable, what each capability MEANS, versioned

A capability string is valid only if it appears here. **Capability definitions are semantically versioned and
become immutable once used (rev-3 #3).**
```
network ref
capabilities [ {
  capability       : string     # governed grammar (below)
  version          : int        # bump to change authorization semantics
  description      : string     # NORMATIVE meaning of holding it
  scope_types_allowed : [enum]  # which scope types a grant may carry
  wildcard         : bool        # default false; explicit opt-in (no implicit inheritance)
  status           : enum        # active | deprecated
} ]
x_indexes: [network, 'capabilities.capability']
```
Edit authority: `capability.steward` (and repointing which catalog the network uses is change-request-only, §1.1).

**Capability grammar.** `<domain>.<action>[:<qualifier>]`, lower-kebab. `domain ∈ {credential,event,resource,
service,offering,network}`; `action` ∈ per-domain governed verbs; `qualifier` = a governed noun id or omitted.

**No implicit inheritance.** `credential.issue` ≠ `credential.issue:work-experience`; the unqualified form confers
no qualified ones. "Any credential type" must be an explicit `credential.issue:*` entry with `wildcard:true`; the
evaluator honours `*` only for a catalog entry that opted in.

**Semantic immutability + versioning (rev-3 #3).** The triple that defines authorization semantics —
`{description(normative), scope_types_allowed, wildcard}` — is **frozen once any grant references
(capability, version)**. To change meaning or scope semantics, publish a **new `version`**; existing grants
continue to evaluate under their pinned version; new grants use the new one. This is schema-versioning for
authority. A used definition may only be `deprecated` (blocking new grants), never silently redefined.

### 1.5 `governance.capability_grant` (v1.0.0) — the single authorization primitive

No generic `constraints` field (rev-3 #4) and no `grantable_by` (rev-3 #5): nothing advisory-looking lives in an
authorization object, and only `grant.steward` mints/revokes.
```
id               string
grantee          ref        # -> ParticipantIdentity
network           ref
capability        string     # must exist (active) in the catalog
capability_version int       # pins the semantics it was granted under (rev-3 #3)
scope             Scope      # discriminated union (§1.6); exactly one shape
valid_from        datetime
valid_to          datetime|null
status            enum       # ACTIVE | REVOKED   (REVOKED is terminal — rev-3 #7)
grantor           ref        # the grant.steward who issued it
provenance        string?
# present only on the REVOKED version:
revoked_at        datetime?  ; revoked_by ref? ; revocation_reason string?
x_indexes: [grantee, network, capability, status]
```
Edit authority: `grant.steward` only. **No delegation** in v1 — a grantee cannot issue or pass on grants.

**Revocation (terminal — rev-3 #7).** Revoke = close the ACTIVE version's tx-window **and** write a new current
version `status:REVOKED` with `revoked_at/by/reason`. A REVOKED grant is **terminal**: authority is never restored
by flipping it back to ACTIVE — restoring authority means issuing a **new grant with a new id**. `grant_revoked`
(a recorded fact) is distinct from `no_grant`.

### 1.6 Scope — discriminated union + one deterministic evaluator per type
```
{type:"network"} | {type:"credential_type",credential_types:[ref]} | {type:"service",services:[ref]}
| {type:"offering_category",categories:[string]} | {type:"event_type",event_types:[ref]}
| {type:"resource",selector:ResourceSelector}     # == ADR-0120 "AuthorityGrant"; evaluator body = Phase 3
```
`scope_matches(scope, context)` dispatches on `scope.type`; one pure evaluator each; deterministic. The `resource`
evaluator's signature is fixed now; its body (exact / hierarchy-with-explicit-descendants / type+jurisdiction /
geometry) lands in Phase 3 — changing no other part of the grant mechanism.

### 1.7 `network.identity_source` (v1.0.0) — assurance ABOUT identity, not an identity
`{ network, code, issuer, jwks, assurances_provided[], status }` · `x_indexes:[network,code,issuer]`.
Registering/removing one is **change-request-only** (§1.1). An IdentitySource asserts facts **about** a
ParticipantIdentity — it never becomes one. Durable assertions:
```
trust.assurance_assertion (v1.0.0):
  participant ref ; identity_source ref ; assurance string ; asserted_at datetime ; evidence_ref ref? ; valid_to datetime?
  x_indexes:[participant, identity_source, assurance]
```
eShram ("worker-verified") and Aadhaar ("identity-proofed") are two assertions about one participant. Session live
assurance = valid assertions ∪ the authenticating IdP's token assurance.

**Live-assurance rule (rev-3.1 #I3).** An assertion contributes to *live* assurance only when
`assertion.valid_to is null OR now < assertion.valid_to` **AND** its `identity_source.status == active`. Revoking
an IdentitySource therefore makes its assertions immediately unusable for **new** authorization decisions, while
the historical assertion records remain in the bitemporal registry for audit (they simply stop contributing live
assurance). Historical evidence is never deleted; it only stops counting.

### 1.8 Stewardship roles — separation of duties
```
network.admin        operational administration (non-security network fields, ops)
membership.steward   approve / suspend / revoke Membership
capability.steward   govern capability_catalog + classification + assurance_policies
grant.steward        issue / revoke CapabilityGrant
```

### 1.9 `governance.role_assignment` — who may assign the steward roles (rev-3 #2)

The recursive question "who assigns the roles?" must be answered or separation of duties collapses. **Reuse the
existing `governance.role_grant` spine (ADR-0028/0026), network-scoped** — do not build a parallel RBAC; extend it
only if it lacks a field below.
```
principal   ref
network      ref
role         enum   # network.admin | membership.steward | capability.steward | grant.steward
granted_by   ref
valid_from   datetime ; valid_to datetime|null
status       enum   # active | revoked
provenance   string # "bootstrap" | change-request id
x_indexes: [network, principal, role, status]
```
Rules:
- **Bootstrap.** At network creation the **platform/network authority** seeds the initial steward set (provenance
  `"bootstrap"`), recorded as role_assignments + a `governance.change` AuditEvent. This is the only non-change-request
  path, and only the platform authority (not a network admin) may do it.
- **Operational roles** (`network.admin`, `membership.steward`): assignable/removable by an existing
  `network.admin`.
- **Security-critical roles** (`capability.steward`, `grant.steward`): assignment/removal is **change-request-only**
  (ADR-0056). A `network.admin` **cannot** self-assign them.
- **No self-escalation.** No principal may assign a role it is not itself authorized to assign; a principal may not
  grant itself a higher-privilege role.
- Every assignment/removal emits a `role.assign` / `role.revoke` AuditEvent.

### 1.10 `governance.assurance_policy` (v1.0.0)
`{ network, code, accepts[], min_level? }` · `x_indexes:[network,code]` · edit: `capability.steward`. Consumed by
the Phase-2 evaluator as a `ContextPredicate`.

---

## 2. Authorization-evaluation contract (the heart of D1)

```
authorize(caller_participant, network, required_capability, context) -> Decision
  Decision := { result: ALLOW | DENY,
                evaluated_grants: [ref],   # ALL candidates considered (rev-3.1 #I1)
                effective_grant: ref|null, # the grant that produced ALLOW (null on DENY)
                reason: enum, explanation: string }
```
Algorithm (**deterministic over all candidates — never DB return order**, rev-3.1 #I1):
0. **Network status (rev-3 #8).** If `network.status != active` → DENY `network_inactive`, **except** a narrowly
   defined governance-recovery allowlist (reactivating the network, steward-role assignment, and other
   `governance.change` actions by the platform authority / an authorized steward) may proceed on a suspended
   network. Ordinary transactions do not authorize merely because grants remain valid.
1. Resolve the caller's Membership; if not `approved` → DENY `not_a_member`.
2. Gather **all** candidate grants where `grantee=caller`, `network`, and the capability **matches**
   `required_capability` — equality, or an explicit `wildcard:true` catalog capability covering it. Never treat
   unqualified as covering qualified. (`evaluated_grants` = this set.)
3. Classify each candidate: *live* iff `status==ACTIVE AND valid_from<=now AND (valid_to IS NULL OR now<valid_to)`.
4. **ALLOW** iff **any** live candidate's scope matches `scope_matches` under its **pinned `capability_version`**
   semantics. The `effective_grant` is chosen deterministically among matching live grants by a total order
   (e.g. narrowest-scope-first, then lowest grant id) so the recorded basis never depends on return order.
5. Otherwise **DENY** with a **deterministic precedence** over the candidate set (specified + tested):
   ```
   a live grant exists but no scope matched   -> scope_mismatch
   else a candidate matched but was expired    -> grant_expired
   else a candidate matched but was revoked     -> grant_revoked
   else                                         -> no_grant
   ```
   (plus the earlier `network_inactive` / `not_a_member`). All distinct for audit/federation; `grant_revoked` ≠
   `no_grant`. The exact precedence is less important than that it is specified and tested; this is it.
6. **Always** emit an `authz.decision` AuditEvent (§3) carrying `evaluated_grants` + `effective_grant`, so an
   auditor can reconstruct *why* the decision occurred.

No participant-type branch anywhere; classification is never read.

---

## 3. AuditEvent — mandatory from the first write; frozen vocabulary

`platform.audit_event` v1.0.0. Append-only, tamper-evident, **metadata + hashes only, never payloads**. Emitted
from the first Phase-1 write (not after a later backend). The vocabulary is frozen across phases; only storage
consolidates later (Phase 5).
```
conforms_to   { schema:"platform.audit_event", version:"1.0.0" }
id            string
ts            datetime                 # RFC3339, kernel clock            -> WHEN
network       ref|null                 # the network id                   -> WHICH NETWORK
actor         { participant, session?, on_behalf_of? }                    -> WHO
action        enum                     # frozen set (below)               -> WHAT
capability    string? ; capability_version int?                           -> USING WHICH CAPABILITY (+ pinned version)
scope         Scope?                                                      -> AGAINST WHICH SCOPE
evaluated_grants [ref]                                                    -> ALL GRANTS CONSIDERED (rev-3.1 #I1)
effective_grant ref?                                                      -> THE GRANT THAT PRODUCED ALLOW (null on DENY)
target_ref    ref?
subject_hash  string? ; subject_hash_kid string?                         # keyed HMAC, see below
decision      enum                     # allow | deny | unknown | n/a     -> DECISION
reason        enum                     # network_inactive|not_a_member|no_grant|grant_revoked|grant_expired|scope_mismatch|ok|... -> WHY
explanation   string
correlation_id string ; causation_id string?                            -> CORRELATION / TXN
emitter       string                   # "network.authz" | "router" | ...
chain         string                   # the chain partition id = (network, emitter)   (rev-3 #6)
seq           int                      # monotonic within `chain`
prev_hash     string ; entry_hash string  # SHA-256 over canonical (JCS) entry incl. prev_hash
x_indexes: [network, action, ts, correlation_id, target_ref, chain]
```
Frozen `action` set: `authz.decision`, `grant.issue`, `grant.revoke`, `membership.decide`, `classification.change`,
`capability_catalog.change`, `identity_source.register`, `identity_source.revoke`, `assurance.assert`,
`role.assign`, `role.revoke`, `governance.change`.

**Hash-chain partition (rev-3 #6).** The chain is **per `(network, emitter)`** — each emitter maintains its own
monotonic `seq`/`prev_hash` chain within a network, avoiding global serialization across distributed emitters.
Cross-chain anchoring (periodic roots) can be added later without changing the record.

**Sequence allocation must be concurrency-safe (rev-3.1 #I2).** `seq`/`prev_hash` allocation per chain must be
**atomic** — three replicas of `emitter=network.authz` must not all read `seq=97` and race to write `98`. Use
either (a) atomic transactional sequence allocation per `(network, emitter)` chain (preferred — it keeps the clean
`(network, logical-emitter)` audit model), or (b) chains keyed at the individual writer-instance level with later
anchoring. The logical `(network, emitter)` model with atomic allocation is the target.

**Subject hashing (rev-3 #6).** Never a bare `SHA-256(subject)` — predictable identifiers are trivially
dictionary-attacked. Use a per-network keyed digest: `subject_hash = HMAC(network_audit_key, canonical_subject)`,
where `network_audit_key` is a per-network secret in Vault; `subject_hash_kid` records the key id so rotation
preserves correlation within a key epoch. This keeps correlation without recovering identifiers.

---

## 4. Type→grant migration runbook

Behind an `AUTHZ_MODE=type|dual|grant` flag; never a flag-day.

**`type_capability_map`** (per network; Claude Code proposes, a human approves **every** mapping before back-fill):
```
net:01J... (avsar):
  insurer:  - { capability: credential.issue:insurance-coverage, version: 1, scope:{type:credential_type, credential_types:[...]} }
            - { capability: service.provide:insurance-enrolment,  version: 1, scope:{type:service, services:[...]} }
  employer: - { capability: offering.publish:jobs, version: 1, scope:{type:offering_category, categories:["jobs"]} }
```
Built by enumerating every current type-based authorization branch (a branch not expressible as a capability is a
finding to resolve first).

**Migration report (human sign-off gate).** Before back-fill, show for every participant type: every capability
to be generated, its `version`, scope, grantor, and the **count of affected memberships**. Human approves; archived
as provenance.

**Steps.** 0 enumerate → draft map → **approve report**. 1 **back-fill** (idempotent) grants per approved
Membership (`grantor=<grant.steward of record>`, `provenance="migration:type=<code>"`). 2 **dual-run**
(`AUTHZ_MODE=dual`): compute legacy + grant decisions, serve legacy, log `authz.decision` with `divergence:true`
on mismatch. 3 **resolve divergence** — run long enough to exercise **real operational cases** (issuance, service
provision, offering publish, membership edges, a suspended-network case), not merely until an automated compare
first reads zero. 4 **flip** (`AUTHZ_MODE=grant`); legacy computed-but-shadow one release. 5 **remove** legacy
checks + CI `grep` gate; retire the flag. **Rollback:** set the flag back — instant; minted grants are harmless
when ignored.

**Acceptance (Phase-1 gate).**
- `insurer` without `credential.issue:insurance-coverage` → DENY `no_grant`; grant → ALLOW; revoke → DENY
  `grant_revoked`; re-authorize needs a **new grant id** (revoked is terminal).
- Unqualified `credential.issue` does not satisfy `credential.issue:work-experience`; explicit `:*` wildcard does.
- Repointing `capability_catalog`, registering an IdentitySource, downgrading `audit`, and assigning
  `capability.steward`/`grant.steward` each **require a change-request** and are rejected as plain admin edits.
- A suspended network DENYs ordinary transactions (`network_inactive`) while still permitting governance-recovery.
- Editing a **used** capability definition's semantics is rejected; a new `version` is required; old grants keep
  evaluating under their pinned version.
- Divergence = 0 over a real-case operational window before flip; CI type-check gate green after step 5.
- One org, two networks, one ParticipantIdentity. Every mutation gated to its steward role. Every decision appears
  as a hash-chained `authz.decision` AuditEvent (correct `chain`/`seq`, HMAC `subject_hash`).

---

## 5. Resolved review decisions

| # | Decision |
|---|---|
| Q1 | Network identity = immutable `net:01J...` + mutable `slug`; code uses `id` only. |
| Q2 | Revocation = close ACTIVE + new terminal `REVOKED` version; authz requires ACTIVE + validity; `grant_revoked` ≠ `no_grant`. |
| Q3 | Four separated stewardship roles. |
| Q4 | `type_capability_map` human-approved; migration report (capabilities/version/scope/grantor/affected-count); dual-run on real cases. |
| +1 | Capability grammar governed; **no implicit inheritance**; wildcards explicit. |
| +2 | Scope = discriminated union; one deterministic evaluator per type; ResourceScope body in Phase 3. |
| +3 | **No delegation** v1; only `grant.steward` mints/revokes. |
| +4 | AuditEvent mandatory from first write; vocabulary frozen. |
| +5 | IdentitySource asserts assurance **about** a ParticipantIdentity; never a replacement identity. |
| **R3-1** | Per-field mutation authority on `network.network`; catalog-repoint / IdP-register / audit-downgrade are change-request-only. |
| **R3-2** | `governance.role_assignment` (reuse ADR-0028 role_grant): platform-authority bootstrap; capability/grant steward assignment is change-request-only; no self-escalation. |
| **R3-3** | Capability definitions are **semantically immutable once used**; change = new `version`; grants pin `capability_version`. |
| **R3-4** | Removed the unenforced generic `constraints` field; typed constraints only arrive with an enforcing evaluator. |
| **R3-5** | Removed `grantable_by`; `grant.steward`-only in v1. |
| **R3-6** | Audit hash-chain partitioned per `(network, emitter)`; `subject_hash = HMAC(network_audit_key, subject)` + `subject_hash_kid`. |
| **R3-7** | REVOKED grants are terminal; restore = new grant id. |
| **R3-8** | `authorize()` checks `network.status == active` first, with a narrow governance-recovery allowlist. |

## 6. Implementation invariants (added at sign-off; NOT ontology changes)

| # | Invariant |
|---|---|
| I1 | `authorize()` is **deterministic over all candidate grants** (never DB return order); specified+tested DENY precedence `scope_mismatch > grant_expired > grant_revoked > no_grant`; audit records `evaluated_grants[]` + a deterministically-chosen `effective_grant`. |
| I2 | Audit-chain `seq`/`prev_hash` allocation per `(network, emitter)` is **atomic/concurrency-safe** (no read-97-write-98 race across replicas). |
| I3 | Revoking an `IdentitySource` immediately invalidates its assertions for **future** live-assurance evaluation (`live ⇔ not expired AND source.status==active`); historical assertions remain for audit. |

## 7. Approved implementation sequence & review gates (sign-off 2026-10-31)

**Phase 1 rev 3 APPROVED FOR IMPLEMENTATION.** Order:
```
schemas → governance roles + role_assignment → versioned capability catalog → authorize()
  → [FIRST REVIEW GATE: Trust-kernel code + authorize() tests, BEFORE touching participants]
  → migration report → [HUMAN GATE] → grant back-fill → dual-run vs legacy
  → divergence report + evidence of real operational flows → [HUMAN GATE]
  → grant enforcement → one-release legacy shadow → remove type-based authorization
```
**Neither human gate is crossed automatically.** The **first review gate is new and highest-value**: after
schemas + role_assignment + catalog + `authorize()` (+ its tests) are implemented, STOP and surface the
Trust-kernel code for review **before** migration/back-fill touches any existing participant. The migration
report and the divergence report (with evidence representative operational flows were exercised) are each
surfaced before their respective gates.

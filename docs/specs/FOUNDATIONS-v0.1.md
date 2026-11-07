# AirawatOS Foundations v0.1

> **Per-rule status is generated, not hand-written** — see **[STATUS-MATRIX.md](STATUS-MATRIX.md)**, the conformance-derived rule × environment matrix (`conformance/run.py --matrix` → `conformance/build_matrix.py`; design: [STATUS-MATRIX-DESIGN.md](STATUS-MATRIX-DESIGN.md)). The inline **Status:** lines below are kept for prose and rationale and may lag; the matrix is authoritative for covered rules (uncovered rules show **NO TEST** there, not an implied status).

**Status:** Draft-for-adoption, 2026-11-03. The invariants the platform is being consolidated onto.
Companion: `docs/consolidation/CURRENT-STATE.md` + `docs/consolidation/DEBT-REGISTER.md` (the `A#`/`B#`
IDs referenced below come from the debt register). Governed by ADR-0118/0119 (Trust Network Platform) and
the three decisions recorded here: **ADR-0123** (Kernel holds its own trust records), **ADR-0124**
(service-to-service auth = short-lived minted tokens, no shared secrets), **ADR-0125** (Consent as a
first-class authority primitive).

---

## 1. Terms

- **Identity** — who a caller is: a verified subject `user://<tenant>/<name>` (or `service://…`) from a
  token signed by a trusted issuer. Identity answers *who*, never *may-they*.
- **Issuer / home issuer** — the signer of a token (`iss`). The **home issuer** is the platform's own
  identity service (`ds:<platform>:identity`); only it may carry privileged authority (issuer-scoping).
- **Tenant** — an administrative owner of data/config/users (`<tenant>`); the steward segment of an id
  (`ds:<tenant>:…`). A unit of *ownership*, not of authority.
- **Network** — a federation/standards body with its own id `net:<ULID>` and a mutable `slug`; it governs
  shared vocabulary and admits participants. **A Network is not a Tenant** (FND-4).
- **Participant** — a member of a Network (tenant-free; ADR-0116). Membership gates *belonging*, never
  *capability*.
- **Record / governed state** — a bitemporal object in the Kernel registry under a steward id. The only
  source of authority (FND-2).
- **Grant** — a recorded authorization object. Three kinds (§3): **RoleAssignment**, **CapabilityGrant**,
  **Consent**.
- **Scope** — what a grant covers: `{type: platform|tenant|network, ref}` (RoleAssignment, ADR-0122) or a
  resource/schema + verb (CapabilityGrant) or a recipient×purpose×service (Consent).
- **Authority** — the right to perform an action. Exists **iff** a live grant is found at decision time
  (FND-2). Never inferred from identity, tenant, membership, classification, issuer, or a token role claim.
- **Run-token** — a high-entropy bearer secret the Kernel mints per component install, carrying that
  component's CapabilityGrant scopes. A credential, never an identifier (`kernel/api/app.py:2056`).
- **Assurance** — the strength of an authentication (AL0..AL3, ADR-0068). A signal, not an authority.

---

## 2. Principles FND-1–FND-17

Status key: **HELD** (upheld in the agreed direction), **PARTIAL** (held in the new surfaces, violated in
legacy/transitional ones), **VIOLATED** (currently contradicted and tracked as debt).

| # | Principle | Status | Debt refs |
|---|---|---|---|
| **FND-1** | **Tokens carry identity only.** A token establishes *who*; it never carries or confers authority. Role claims in a token are not authority. | **VIOLATED** | DEBT-B1 (identity stamps `roles`, downstream enforces off them); DEBT-B12 (client-asserted scope) |
| **FND-2** | **Authority comes only from recorded state** — a live grant found at decision time ("holds a live grant", never "is of type X", ADR-0119 DEC-1). | **PARTIAL** (Trust-plane holds it; kernel admin, network legacy, app-host front-gates, reference services do not) | DEBT-B1, DEBT-B2, DEBT-B3, DEBT-B5, DEBT-B15, DEBT-B17, DEBT-B18 |
| **FND-3** | **Nothing is implied by tenant, membership, classification, or issuer.** None of these, alone, grants anything. | **VIOLATED** | DEBT-B2 (tenant==network, is_platform_authority), DEBT-B7 (schema-prefix classification drives authz), DEBT-B13 (assurance claim) |
| **FND-4** | **Tenant ≠ Network.** Tenant id, Network `net:` id, and Network `slug` are distinct and never conflated; authority on one is not authority on another. | **PARTIAL** | DEBT-B11 (slug/net:id/tenant conflated in legacy gate + predicate); DEBT-B2 (app-host fabricated `network==slug==tenant`) |
| **FND-5** | **No silent in-memory authoritative state.** Authority, sessions, and at-least-once guarantees are durable and recoverable; losing a process never loses or forges authority. | **PARTIAL** (Trust store durable + rehydrated; app-host sessions, kernel dev-tokens, automation dedup are not) | DEBT-B10 |
| **FND-6** | **The Kernel stays domain-blind.** No domain vocabulary or domain logic in the Kernel; it treats every schema as opaque governed substrate. | **PARTIAL** | DEBT-B8 (`_NAT_KEYS`, dataplane/event/public schema-name vocab baked in) |
| **FND-7** | **The Kernel is self-contained for authorization inputs.** It holds its own trust records (authority keys, schemas, grants, tenant classification); it makes no call to a higher layer to decide an authorization. | **VIOLATED** (today the kernel calls the Network for authority key/schemas/grants/tenant-dev) | DEBT-B9; **ADR-0123** |
| **FND-8** | **Fail closed.** Every gate denies on missing, unavailable, or unverifiable authority. No fail-open gate; no enforcement that defaults to off/shadow in production; no unauthenticated privileged endpoint. | **VIOLATED** | DEBT-B4, DEBT-B5, DEBT-B6, DEBT-B14, DEBT-B15, DEBT-B16; DEBT-A1–DEBT-A6, DEBT-A36 |
| **FND-9** | **Service-to-service auth = short-lived, audience-bound tokens from the home issuer, minted on demand from Vault-held credentials.** No shared-secret internal gates; no passwordless service principals. | **VIOLATED** (reader/writer mint pattern exists; shared secrets + passwordless principals still in use) | DEBT-B4, DEBT-B14; DEBT-A26, DEBT-A29, DEBT-A33, DEBT-A36–DEBT-A38; **ADR-0124** |
| **FND-10** | **Least privilege & explicit scope.** Every grant names its scope; reads/writes are own-tenant unless a recorded cross-tenant grant exists; egress is to declared hosts only; credentials are the narrowest that work. | **PARTIAL** | DEBT-B12 (scope not bound to registered client), DEBT-B16 (open egress proxy/SSRF), DEBT-A19 (single global write steward) |
| **FND-11** | **Separation of duties + last-holder floor for security-critical authority.** Granting `platform.authority`/`tenant.admin` needs a ChangeRequest approved by a *different* live holder; the last live holder cannot be revoked (break-glass is separate). | **PARTIAL** (designed/enforced for Trust-plane roles; platform.authority still tenant-based) | DEBT-B18; DEBT-A17; **ADR-0122** |
| **FND-12** | **Every authorization decision is audited** — allow and deny, durably — and failed authentication is logged (issuer, reason, source). | **PARTIAL** (admin-plane allow/deny audited + hash-chained; failed auth and most service gates are not) | DEBT-B5 (no audit on unauth endpoints); DEBT-A9 (failed-auth not logged) |
| **FND-13** | **Consent is a first-class authority primitive.** A subject grants a recipient × purpose × scope × period, revocable, with evidence; cross-party data access is authorized by a recorded Consent. | **PARTIAL** (embed consent exists but scope not bound; no DEPA alignment) | DEBT-B12; **ADR-0125** |
| **FND-14** | **Authority is traceable.** Every authority record names its grantor (`granted_by`/`audited_by`/`decided_by`), and the grantor chain resolves back to the installation bootstrap record (the first-grant seed) — so any live grant can be explained by *who granted it, under whose authority*. | **PARTIAL** (Trust-plane role_assignment carries `granted_by`/op_id + audit chain, and `platform.authority`'s first grant is the installer seed per ADR-0122; but token-role / tenant-name authority has no grantor, and legacy grants are not uniformly chained to bootstrap) | DEBT-B1, DEBT-B2, DEBT-B3, DEBT-B18; **ADR-0122** (first-grant seed) |
| **FND-15** | **External issuers are scoped.** A non-home (federated/external) issuer is bound to a recorded tenant (later: a recorded Network); a token from it that claims a tenant/role outside that binding is **rejected** (and self-asserted roles are stripped) — authority never widens by changing issuer. | **PARTIAL** (held in the Network trust boundary: `authn.register_issuer` pins the tenant, `verify` rejects a tenant mismatch and strips roles, `network/authn.py:163-167`; the Kernel's home-issuer scoping is the matching rule — but there is no Network-scoped binding yet, and the kernel still trusts issuer+role for admin, DEBT-B1) | DEBT-B1, DEBT-B13; **ADR-0117** (credential/services network), **ADR-0119** |
| **FND-16** | **Safe defaults.** No default value points at a specific deployment (no built-in `ds:airawat:identity`, `airawatos`, `airawat` steward); every enforcement check defaults to **enforce**, not off/shadow; and a missing **required** configuration **stops startup** (fail-loud) rather than silently assuming a value. | **VIOLATED** (prod-pointing defaults; enforcement gates default off/shadow; most missing config does not stop startup — only the network durable-backend check fails loud) | DEBT-A1–DEBT-A8, DEBT-A30, DEBT-A36; DEBT-B8; **ADR-0124** (no fail-open), PLAN.md "remove production-pointing defaults" |
| **FND-17** | **Acting on behalf.** An agent — human or AI — is a **principal with its own identity** and acts for another **only via a recorded delegation** (scope, expiry, revocation). Decision records show **both the acting principal and the represented principal**. Some acts are **non-delegable or require step-up**: granting consent for sensitive data, closing an account, and changing the identity binding. An agent can **never create or widen its own delegation**. | **NOT BUILT** (no delegation primitive; agents act under the represented principal's token today, so "actor ≠ represented" is not recorded, and nothing bars self-widening) | DEBT-B1 (token-role authority), DEBT-B3 (authentication ≠ authorization); **DECISION DEC-12** (automated decisions re a person); relates to **ADR-0125** (consent as the sensitive-data step-up) |
| **FND-18** | **Horizontal safety (safe as N copies).** Every service is safe to run as **N≥2 identical copies behind a load balancer**: it holds no authoritative state in process memory or on local disk, runs no assumed-singleton background loop, keeps shared state in a durable concurrency-safe store, and guards singleton work (a clock, an outbox drain, a dispatcher) with leader election or a lease. The operational form of FND-5. | **VIOLATED** | DEBT-B10 (app-host `_SESSIONS`, scheduler `_RUNS`, automation `_PROCESSED` in memory); filestore local-disk blobs; network in-memory certs/requests; identity local user/password files; event-relay/scheduler/automation assumed-singleton loops — see **[HA-AUDIT.md](../consolidation/HA-AUDIT.md)** |

---

## 3. Authority model

### Three primitives (all recorded governed state)
1. **RoleAssignment** (`governance.role_assignment`, ADR-0028/0119/0122) — *standing* authority within a
   scope. `{principal, role, scope:{type:platform|tenant|network, ref}, status, validity}`. Granted by an
   existing authority of that scope (SoD for security-critical roles). Answers: *may this principal act in
   this role on this platform/tenant/network?*
2. **CapabilityGrant** (`governance.capability_grant`, ADR-0119 — "the single authorization primitive") —
   *delegated, bounded* authority to a non-human actor (a component, via its run-token). `{grantee,
   capability, capability_version, scope, status, validity}`. Catalog-bound (the capability must exist in
   the network's capability catalog). Answers: *may this component perform this verb on this schema/resource?*
3. **Consent** (`governance.consent`, ADR-0125) — *subject-granted* authority for a recipient to use the
   subject's data for a stated purpose. `{subject, recipient, purpose, scope, period, status, revocation,
   evidence}`. Granted by the **subject** (not an admin). Answers: *did the data subject authorize this
   recipient, for this purpose, for this period?*

### The decision function
Authorization is a **candidate-grant lookup**, never a type/tenant/issuer test:

```
authorize(token, verb, resource, scope, now) -> allow | deny:
  1. identity, err = verify(token)                 # FND-1: identity only; reject on bad sig/exp/aud/iss
     if err: deny("unauthenticated")               # FND-8: fail closed
  2. if the action needs privileged authority and identity.iss != HOME_ISS:
         deny("non-home issuer")                    # FND-3/FND-7: issuer-scoping
  3. candidates = live grants where
        grant.principal/grantee/subject == identity.sub
        AND grant.status == "active"
        AND is_live_window(now, grant.valid_from, grant.valid_to)
        AND grant covers (verb, resource, scope)    # RoleAssignment | CapabilityGrant | Consent
     read from RECORDED STATE only (FND-2); never token roles, tenant name, membership, or classification (FND-3)
  4. decision = "allow" if candidates else "deny"
  5. audit(decision, identity, verb, resource, scope, matched_grant_or_reason)   # FND-12 (durable)
  6. return decision                                # default path is deny (FND-8)
```

Properties: **fail-closed** (no grant ⇒ deny; reader/store unavailable ⇒ deny, not fall back); **issuer-scoped**
(privileged authority only from the home issuer); **recorded-only** (the lookup never consults the token's
role claims, the caller's tenant, membership, or a data classification); **audited** (every outcome). The
three primitives share this one function — a RoleAssignment, a CapabilityGrant, and a Consent are just three
shapes of "a live grant that covers this action".

**The two-key rule (personal data).** Authority over **services and data is one model** (ADR-0127): a
**CapabilityGrant** covers the action (read/write records of a schema, or call/provide a service), scoped as
needed. For a **specific person's personal data**, the grant is **not enough on its own** — access requires
**two keys**: the holder's **CapabilityGrant** AND **that person's Consent**. **Non-personal** data needs the
grant only. The Kernel does not treat `access_grant` as a separately-issued permission; it **derives** the
access decision from (grant + consent) at enforcement time. This keeps FND-13 (only the subject consents) and FND-8
(default-deny) intact for every personal read or write.

**FND-8 scope — one deliberate, alerted exception (protective counters).** FND-8's fail-closed rule governs
**authorization**: deciding whether an actor may do a thing. Authorization never falls back — no grant, or an
unavailable grant/consent reader, means **deny**. A small, named class of controls is **not** an authorization
gate: a **protective rate/attempt counter** (today, the brute-force login-lockout counter, ADR-0121) only adds
*friction* to an action the credentials otherwise authorize. For these, if the durable counter store is
unavailable, **availability wins over strictness** — a Postgres outage must not lock every legitimate user out
of login — so the counter **may fail open** (skip the lock, record in memory) rather than deny. This is
permitted **only** when the fallback is (1) **deliberate** — enumerated here, not an accident of a bare
`except`; (2) **alerted** — an alert-level event on the transition and periodically until recovery; and (3)
**observable** — the live mode is exposed on the service's health endpoint (identity `/healthz`
`lockout_store`: `durable` | `memory(degraded)` | `memory`). The thing the counter *protects* —
authentication, and every authorization decision after it — **still fails closed**: a wrong password is still
rejected, an unauthenticated or ungranted call is still denied. The carve-out covers the *protective counter's
durability*, never the gate it fronts. Any new fail-open behaviour must be added to this list with the same
three conditions, or it is a straight FND-8 violation. (Implementation + proof:
`../security/IDENTITY-DB-LEAST-PRIVILEGE.md`, `../performance/IDENTITY-KDF-REPORT.md`.)

---

## 4. Debt-register → principle map (DEBT-B1–DEBT-B21)

Every current invariant violation mapped to the principle(s) it breaks (see `DEBT-REGISTER.md` §B for
file:line evidence):

| Debt | Violation (short) | Principle(s) |
|---|---|---|
| **DEBT-B1** | authority from token role claims (identity stamps `roles`, downstream enforces off them) | **FND-1, FND-2** |
| **DEBT-B2** | authority implied by / fabricated from tenant name (`tenant==network`, `is_platform_authority`, app-host `networks-mine` fallback) | **FND-2, FND-3, FND-4** |
| **DEBT-B3** | authority from authentication alone (`decision /decide` records any valid token as the authority) | **FND-2** |
| **DEBT-B4** | internal shared-secret treated as authority, fail-open when unset (secrets `/materialize`/`/fetch`, runtime-manager `/invoke`) | **FND-8, FND-9** |
| **DEBT-B5** | unauthenticated privileged/writing endpoints (filestore, notify, scheduler `/run`, model-gateway, automation, event_relay) | **FND-8** (+ FND-2, FND-12) |
| **DEBT-B6** | unauthenticated identity/role directory disclosure (identity `GET /users`, `/realms`) | **FND-8, FND-3** |
| **DEBT-B7** | classification / schema-prefix drives an authz decision (kernel dataplane prefix, shared-read) | **FND-3** |
| **DEBT-B8** | Kernel not domain-blind (`_NAT_KEYS`, dataplane/event/public schema vocab baked in) | **FND-6** |
| **DEBT-B9** | upward / trust-anchor calls (kernel→network for authority key/schemas/grants/tenant classification; network→identity user-create) | **FND-7** |
| **DEBT-B10** | silent in-memory authoritative state (app-host `_SESSIONS`, kernel dev-tokens + audit ring, automation dedup) | **FND-5** |
| **DEBT-B11** | Tenant ≠ Network conflation (slug/net:id/tenant mixed across modes + predicate) | **FND-4** |
| **DEBT-B12** | client-asserted scope not bound to the registered client's capability (embed `/authorize` + consent `service:"*"`) | **FND-1, FND-10, FND-13** |
| **DEBT-B13** | assurance claim not trustworthy (uniform AL0 / static AL2) | **FND-3** |
| **DEBT-B14** | passwordless full-authority principals (`platform.scheduler`/`platform.steward` mint with no secret) | **FND-9, FND-8** |
| **DEBT-B15** | `GET /v1/components` unauthenticated and serializes `run_token` (a bearer secret) | **FND-8, FND-2** (+ FND-10) |
| **DEBT-B16** | open egress proxy / SSRF (secrets `/fetch`, automation `action.url`, app-host `connect-network`) | **FND-10, FND-8** |
| **DEBT-B17** | client-side-only role gating in apps *(mitigated; verify host re-checks)* | **FND-2** |
| **DEBT-B18** | engines hold write-grant to `governance.decision` ("never decides" now rests on the trigger gate) | **FND-11, FND-2** |
| **DEBT-B19** | one record carries two divergent ids (`object.id` ≠ the canonical registry id for some kinds; slug/net:id/tenant conflation root) — code that filters/joins on `object #>> '{id}'` means something other than the registry id | **FND-4** (+ REGISTRY REG-1) |
| **DEBT-B20** | component run-tokens stored at rest in plaintext in the `installed` KV (bearer secret recoverable from a DB dump) — target: store a hash, deliver the clear token once | **FND-8, FND-10** |
| **DEBT-B21** | identity realms modelled as tenants (a login namespace conflated with an owning organisation; `citizens`/`-participant` exist as `tenant` records only to serve as shared realms) | **FND-3, FND-4** |

---

## 5. Adoption posture
These foundations describe the target invariants and the agreed authority model; they do **not** change code.
The debt register is the backlog to reach them; ADR-0122/0123/0124/0125 **decide** the direction for the
largest violations (FND-7, FND-8, FND-9, FND-11, FND-13, FND-14, FND-16) — **the debt stays open until each is implemented** (the
implementing work is named in each ADR's Consequences). Consolidation sequences the rest.

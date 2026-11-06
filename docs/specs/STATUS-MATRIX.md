# AirawatOS status matrix — rule × environment (GENERATED)

**Generated** by `conformance/build_matrix.py` from `conformance/results/*.json` (written by `conformance/run.py --matrix`). **Do not hand-edit** — regenerate after a conformance run. This is the conformance-derived single source of truth for per-rule status; the specs reference it (ADR: STATUS-MATRIX-DESIGN.md).

- **local-dev** — measured: modes external+internal, git ``, 2026-11-06T15:47:45Z
- **production** — *PROJECTED*: no production conformance run yet; not asserted (stand up per docs/operator/FRESH-INSTALL-TEST.md §Step 3, then run the suite with AOS_ENV=production).

**Derived status:** HELD (all cited cases PASS) · PARTIAL (PASS + known-violation XFAIL) · VIOLATED (only XFAIL — tracked as debt) · PLANNED(needs-build) (only SKIP_BUILD, not black-box reachable) · UNVERIFIED(creds) (only SKIP_CREDS — fix the fixture) · REVIEW (XPASS — spec lags code) · REGRESSION (a FAIL — contradicts spec) · NO TEST (no case cites the rule yet).

## FOUNDATIONS

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `FND-1` | PARTIAL | projected | a roleless-created account has NO roles — no authority by omission [DEBT-B28 fixed]; authenticated session opens (pos); forged role+foreign-iss token rejected ( |
| `FND-2` | HELD | projected | Trust audit chain is verified/reconciled at runtime; dev-sandbox refused a cross-tenant write; valid non-admin session denied governance write (abuse) |
| `FND-3` | PARTIAL | projected | authority only from a recorded grant, never tenant name (TRUST plane); forged role+foreign-iss token rejected (abuse); home-issued admin role-claim (no recorded |
| `FND-4` | PLANNED(needs-build) | projected | tenant != network (authority keyed on net:id, not tenant/slug) |
| `FND-5` | PLANNED(needs-build) | projected | durable authority survives restart |
| `FND-6` | HELD | projected | unknown schema handled opaquely (pos) |
| `FND-7` | PLANNED(needs-build) | projected | kernel authorizes with Network down |
| `FND-8` | PARTIAL | projected | anonymous kernel read denied (internal) [debt DEBT-A1]; anonymous read denied (abuse) [debt DEBT-A1]; anonymous write denied (abuse); unauthenticated /v1/compon |
| `FND-9` | HELD | projected | account-write gate refuses a wrong internal token (fail closed) [DEBT-B29]; no passwordless full-authority mint (residual; write-gate half fixed by DEBT-B29); r |
| `FND-10` | PARTIAL | projected | automation /events accepts without a service token (abuse); filestore refuses a wrong-audience token (abuse); filestore refuses an anonymous call (abuse); model |
| `FND-11` | HELD | projected | SoD for floor roles enforces approver != proposer; component.publisher refused at kernel admin (registry.usage); dev-sandbox refused at kernel admin (registry.u |
| `FND-12` | PLANNED(needs-build) | projected | every authz decision audited (allow+deny); failed-auth logged |
| `FND-13` | NO TEST | projected | — |
| `FND-14` | PLANNED(needs-build) | projected | role assignment names its grantor (granted_by); role assignments carry grantor + governance provenance |
| `FND-15` | HELD | projected | forged role+foreign-iss token rejected (abuse); human (platauth) refused a service audience; scheduler may request its recorded audience (svc:automation); sched |
| `FND-16` | PLANNED(needs-build) | projected | missing config stops startup; safe defaults (no prod-pointing default; enforce-by-default; fail-loud) |
| `FND-17` | PLANNED(needs-build) | projected | agent delegation; no self-widen |

## REGISTRY

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `REG-1` | PLANNED(needs-build) | projected | write then re-read by id — id stable |
| `REG-2` | PLANNED(needs-build) | projected | schema-governed writes; no ungoverned/ad-hoc shapes |
| `REG-3` | PLANNED(needs-build) | projected | supersede creates new version; prior addressable |
| `REG-4` | PLANNED(needs-build) | projected | valid + recorded time |
| `REG-5` | HELD | projected | forged-token write denied (abuse) |
| `REG-6` | VIOLATED | projected | anonymous existence-check denied (abuse) [debt DEBT-A1]; anonymous kernel read denied (internal) [debt DEBT-A1]; anonymous read denied (abuse) [debt DEBT-A1] |
| `REG-7` | PLANNED(needs-build) | projected | written record carries provenance [debt DEBT-A2 shadow] |
| `REG-8` | PLANNED(needs-build) | projected | Kernel/participant signature on each committed version |
| `REG-9` | PLANNED(needs-build) | projected | idempotent writes (content-hash dedup) |
| `REG-10` | PLANNED(needs-build) | projected | deterministic resolution over records (pos) |
| `REG-11` | PLANNED(needs-build) | projected | schemas are records; owner != adopter |
| `REG-12` | PLANNED(needs-build) | projected | trust-bearing write audited |
| `REG-13` | HELD | projected | unknown schema handled opaquely (pos) |
| `REG-14` | PLANNED(needs-build) | projected | personal data by reference; erasure |
| `REG-15` | PLANNED(needs-build) | projected | public = schema flag via CR |
| `REG-16` | PLANNED(needs-build) | projected | archived version resolves identically |
| `REG-17` | PLANNED(needs-build) | projected | Kernel→Vault uses its own service identity scoped to transit encrypt/decrypt/hmac on rec-*/idx-* (never root); fails closed if Vault down; REG-9 idempotency ove |
| `REG-18` | PLANNED(needs-build) | projected | files are records (Kernel-mediated bytes) |

## DECISION

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `DEC-1` | PLANNED(needs-build) | projected | protected authz emits a decision record |
| `DEC-2` | PLANNED(needs-build) | projected | decision record contents |
| `DEC-3` | PLANNED(needs-build) | projected | replayable; model output as input |
| `DEC-4` | PLANNED(needs-build) | projected | decider needs recorded authority [debt DEBT-B3] |
| `DEC-5` | PLANNED(needs-build) | projected | decision records never edited |
| `DEC-6` | PLANNED(needs-build) | projected | denial recorded with reason [debt DEBT-A9] |
| `DEC-7` | PLANNED(needs-build) | projected | personal data in decision by reference |
| `DEC-8` | PLANNED(needs-build) | projected | reason codes; subject reads own decisions |
| `DEC-9` | PLANNED(needs-build) | projected | decisions linked (correlation/op ids) to CRs + audit |
| `DEC-10` | PLANNED(needs-build) | projected | every decryption of personal data produces a full decision record (actor/subject/purpose/basis); personal-data read always full record |
| `DEC-11` | PLANNED(needs-build) | projected | contest flow; reviewer != decider |
| `DEC-12` | PLANNED(needs-build) | projected | automated decision labelled + human authority [debt DEBT-B18] |

## NETWORK

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `NET-1` | PLANNED(needs-build) | projected | slug/tenant not accepted as net authority [debt DEBT-B11/DEBT-B2] |
| `NET-2` | PLANNED(needs-build) | projected | a Network is a governed lifecycle object (creator role, DRAFT, governing tenant, empty-catalog gate) |
| `NET-3` | HELD | projected | admin is a plain network.admin (network.admin role, not platform authority) (pos); anonymous governance role-write denied (abuse); component.publisher refused a |
| `NET-4` | PLANNED(needs-build) | projected | suspended net refuses exchange, allows reads |
| `NET-5` | PLANNED(needs-build) | projected | membership supports invite->accept and suspend |
| `NET-6` | PLANNED(needs-build) | projected | join never creates a login [debt DEBT-B9] |
| `NET-7` | PLANNED(needs-build) | projected | issuer trust admin-only + scoped; issuer trust is network.admin-only and scoped to (member-tenant, net:id) |
| `NET-8` | PLANNED(needs-build) | projected | classifications are descriptive only (never gate exchange) |
| `NET-9` | VIOLATED | projected | capability-grant store POST /v1/grants requires a grant.steward (fail closed); wildcard/unversioned capability grant rejected [debt DEBT-B12] |
| `NET-10` | PLANNED(needs-build) | projected | publishing a Service requires a recorded service.provide grant |
| `NET-11` | PLANNED(needs-build) | projected | exchange runs through the one decision function and leaves a decision record |
| `NET-12` | VIOLATED | projected | member list GET /v1/participation is members-only (not public); service directory POST /v1/service/search is members-only (REG-15) |

## ACCOUNT

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `ACC-1` | NO TEST | projected | — |
| `ACC-2` | VIOLATED | projected | account id is permanent + distinct from the login handle [debt DEBT-B30]; id/handle/binding distinct; handle reserved |
| `ACC-3` | VIOLATED | projected | assurance reflects the real auth method (AL-vocabulary, >=AL1 after password) [debt DEBT-B13]; identity-binding uniqueness via a keyed blind index (HMAC), not a |
| `ACC-4` | PLANNED(needs-build) | projected | login + recovery; per-account-type recovery |
| `ACC-5` | PLANNED(needs-build) | projected | provider connections (consent + confirmation; revocable) |
| `ACC-6` | NO TEST | projected | — |
| `ACC-7` | PLANNED(needs-build) | projected | consent by holder; withdraw->erase |
| `ACC-8` | PLANNED(needs-build) | projected | assisted access via FND-17 |
| `ACC-9` | PLANNED(needs-build) | projected | closure withdraws consents + erases |
| `ACC-W1` | NO TEST | projected | — |
| `ACC-W2` | NO TEST | projected | — |
| `ACC-W3` | PLANNED(needs-build) | projected | presentation bound to recipient/purpose |
| `ACC-W4` | PLANNED(needs-build) | projected | selective disclosure |

## CLIENT

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `CLI-1` | HELD | projected | registered clients with recorded scopes; unregistered client rejected (abuse) [debt DEBT-A47] |
| `CLI-2` | PLANNED(needs-build) | projected | scope bound to registered client, not query (abuse) [debt DEBT-B12] |
| `CLI-3` | VIOLATED | projected | token app-addressed + carries a consent reference [debt DEBT-B31] |
| `CLI-4` | NO TEST | projected | — |
| `CLI-5` | HELD | projected | identity /users directory requires an authorised caller (abuse) |
| `CLI-6` | PLANNED(needs-build) | projected | public versioned protocol, not /bridge/* [debt DEBT-A23] |

## PLATFORM

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `PLT-1` | NO TEST | projected | — |
| `PLT-2` | NO TEST | projected | — |
| `PLT-3` | PLANNED(needs-build) | projected | operator holds no governance role (+ login-namespace != tenant, DEBT-B21) |
| `PLT-4` | HELD | projected | opadmin (operator tenant) sees all networks w/ platform_authority=true (pos); platnone (same tenant, no role) is NOT platform authority (abuse) |
| `PLT-5` | HELD | projected | bootstrap grants no platform.authority when a holder exists (ADR-0122); grant platform.authority without a different-holder CR is refused (abuse); revoking the  |
| `PLT-6` | NO TEST | projected | — |
| `PLT-7` | NO TEST | projected | — |
| `PLT-8` | NO TEST | projected | — |
| `PLT-9` | NO TEST | projected | — |
| `PLT-10` | NO TEST | projected | — |
| `PLT-11` | NO TEST | projected | — |
| `PLT-12` | NO TEST | projected | — |
| `PLT-13` | NO TEST | projected | — |
| `PLT-14` | NO TEST | projected | — |
| `PLT-15` | NO TEST | projected | — |
| `PLT-16` | NO TEST | projected | — |
| `PLT-17` | NO TEST | projected | — |
| `PLT-18` | NO TEST | projected | — |
| `PLT-19` | NO TEST | projected | — |
| `PLT-20` | NO TEST | projected | — |
| `PLT-21` | NO TEST | projected | — |
| `PLT-5a` | NO TEST | projected | — |
| `PLT-8a` | NO TEST | projected | — |

## COMPONENT

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `CMP-1` | NO TEST | projected | — |
| `CMP-2` | NO TEST | projected | — |
| `CMP-3` | PLANNED(needs-build) | projected | run token = declaration ∩ authority |
| `CMP-4` | NO TEST | projected | — |
| `CMP-5` | NO TEST | projected | — |
| `CMP-6` | PLANNED(needs-build) | projected | records & files only via the broker under run token + declared scopes |
| `CMP-7` | NO TEST | projected | — |
| `CMP-8` | NO TEST | projected | — |
| `CMP-9` | NO TEST | projected | — |
| `CMP-10` | NO TEST | projected | — |
| `CMP-11` | NO TEST | projected | — |
| `CMP-12` | NO TEST | projected | — |
| `CMP-13` | NO TEST | projected | — |
| `CMP-14` | NO TEST | projected | — |
| `CMP-15` | NO TEST | projected | — |
| `CMP-16` | NO TEST | projected | — |
| `CMP-17` | NO TEST | projected | — |
| `CMP-18` | NO TEST | projected | — |

## OFFERINGS

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `OFF-1` | NO TEST | projected | — |
| `OFF-2` | NO TEST | projected | — |
| `OFF-3` | NO TEST | projected | — |
| `OFF-4` | NO TEST | projected | — |
| `OFF-5` | NO TEST | projected | — |
| `OFF-6` | NO TEST | projected | — |
| `OFF-7` | NO TEST | projected | — |
| `OFF-8` | NO TEST | projected | — |
| `OFF-9` | NO TEST | projected | — |
| `OFF-10` | NO TEST | projected | — |
| `OFF-11` | NO TEST | projected | — |
| `OFF-12` | NO TEST | projected | — |

## POLICY

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `POL-1` | NO TEST | projected | — |
| `POL-2` | NO TEST | projected | — |
| `POL-3` | NO TEST | projected | — |
| `POL-4` | NO TEST | projected | — |
| `POL-5` | NO TEST | projected | — |
| `POL-6` | NO TEST | projected | — |
| `POL-7` | NO TEST | projected | — |
| `POL-8` | NO TEST | projected | — |

## PARTICIPANT

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `PTC-1` | VIOLATED | projected | trust-directory admission POST /v1/participants requires authority (fail closed) |
| `PTC-2` | PLANNED(needs-build) | projected | Network-boundary auth is identity-only (FND-15) |
| `PTC-3` | PLANNED(needs-build) | projected | Service registration carries iface/endpoint/version/data-use + a provide grant |
| `PTC-4` | NO TEST | projected | — |
| `PTC-5` | PLANNED(needs-build) | projected | inbound request carries a verified decision/consent reference; never widen |
| `PTC-6` | PLANNED(needs-build) | projected | signed responses + fulfilment evidence joined to a decision |
| `PTC-7` | PLANNED(needs-build) | projected | credential issuance requires a typed issue grant; signed; revocation published |
| `PTC-8` | PLANNED(needs-build) | projected | presentation verification binds holder-proof/recipient/purpose/nonce (ACC-W3) |
| `PTC-9` | PLANNED(needs-build) | projected | events: granted types only; interest != authority; idempotency |
| `PTC-10` | PLANNED(needs-build) | projected | settlement references |
| `PTC-11` | PLANNED(needs-build) | projected | per-role conformance before activation |
| `PTC-12` | PLANNED(needs-build) | projected | one public versioned participant protocol; never /bridge |

## FEDERATION

| rule | local-dev | production | cases (provenance) |
|---|---|---|---|
| `FED1` | PLANNED(needs-build) | projected | one governing tenant hosts a Network |
| `FED2` | PLANNED(needs-build) | projected | creation needs network.creator; never creates tenants |
| `FED3` | PLANNED(needs-build) | projected | join = registration in host registry (id, roles, keys, conformance) |
| `FED4` | PLANNED(needs-build) | projected | per-role conformance before activation |
| `FED5` | PLANNED(needs-build) | projected | cross-install requests signed by registered keys |
| `FED6` | PLANNED(needs-build) | projected | home issuer trusted only for its own participants, per-Network |
| `FED7` | VIOLATED | projected | host directory authoritative; resolve uses an exact steward match (no substring collisions); trust-directory admission POST /v1/participants requires authority  |
| `FED8` | PLANNED(needs-build) | projected | directory-of-Networks / root of trust |

## Tally (rules per derived status, per environment)

| environment | HELD | PARTIAL | VIOLATED | PLANNED(needs-build) | UNVERIFIED(creds) | REVIEW | REGRESSION | NO TEST | projected |
|---|---|---|---|---|---|---|---|---|---|
| local-dev | 12 | 4 | 8 | 72 | 0 | 0 | 0 | 63 | 0 |
| production | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 159 |


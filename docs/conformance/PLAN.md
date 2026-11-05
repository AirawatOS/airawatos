# Conformance test plan (Consolidation Phase 3)

**Date:** 2026-11-03 · **Target:** local-dev at `http://127.0.0.1:8080` · **Scope:** black-box only — HTTP
calls, returned records, decision records. No internal code is inspected or called.

Covers every rule in [[FOUNDATIONS-v0.1]] (F1–F17), [[REGISTRY-v0.1]] (R1–R16), [[DECISION-v0.1]] (D1–D12),
[[NETWORK-v0.1]] (N1–N12), [[ACCOUNT-v0.1]] (A1–A9, W1–W4), [[CLIENT-v0.1]] (C1–C6). Debt refs → `../consolidation/DEBT-REGISTER.md`.

## Black-box surface (local-dev)
The only host-published port is the ld edge nginx at `127.0.0.1:8080`, which routes:
- `/kernel/*` → kernel (`/kernel/v1/registry/{resolve,objects,exists,count}`, `/kernel/v1/components`, …)
- `/network/*` → network (`/network/v1/health`, `/network/v1/governance/roles`, `/network/v1/participants`, …)
- `/*` → app-host (`/login`, `/bridge/*`, `/embed/*`)

Identity (`:8093`) and the other reference services (filestore, notify, scheduler, model-gateway, secrets,
runtime-manager, automation, event_relay) are **not** published, so their endpoints are **not black-box
reachable** at `:8080` — cases that need them are classified **NEEDS-BUILD (not reachable black-box here)**.

## Auth model for tests
- **Anonymous** — no token. Used for all "no anonymous X" / fail-closed / disclosure cases.
- **Forged token** — a syntactically-valid JWT with role claims but an invalid signature and/or foreign
  `iss`. Used for the "token role / foreign issuer is not authority" abuse cases.
- **Session (cookie)** — `POST /login {realm,username,password}` opens a browser session; authenticated user
  actions then go through `/bridge/*`. Requires real test-user passwords.
- **Bearer** — a home-issuer token from identity `/realms/<realm>/login`. Identity is not published at
  `:8080`, so bearers are obtained only if credentials are supplied to the harness.

The test users (`admin`, `memsteward`, `xadmin`, `outsider`, `faker` in `localdev-network`) have passwords in
Vault; the harness reads them from the optional env var `AOS_TEST_USERS` (JSON `{"admin":"pw",…}`) or
`conformance/.creds.json` (gitignored). **If no credentials are supplied, every case needing a valid
session/bearer is reported NEEDS-CREDENTIALS (skipped), and the suite still passes on the no-credential
cases.** This keeps the suite runnable and green today without embedding secrets.

## Classification
- **TESTABLE NOW** — executes black-box today; asserts the spec-correct observable; PASS/FAIL.
- **EXPECTED FAIL (xfail)** — a known live violation (cites the debt item); the case asserts the *current
  (wrong)* observable, so it is **green today**. If the violation is later fixed, the assertion flips to an
  **XPASS (unexpected pass)** — the signal that the debt is closed.
- **NEEDS-CREDENTIALS** — testable in principle but needs a supplied session/bearer; skipped without creds.
- **NEEDS-BUILD** — the feature or endpoint does not exist / is not black-box reachable; not executed.

Suite exit: non-zero only on a **FAIL** (a TESTABLE-NOW case that did not behave as the spec requires).
**XPASS** is printed prominently (good news: a debt closed) but does not fail the run.

---

## FOUNDATIONS (F1–F17)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| F1 | forged JWT with `roles:[network.admin]`, bad sig → kernel resolve (abuse) | TESTABLE NOW | reject (401) — role claim is not authority; **live: 401 ✓** |
| F1 | valid user bearer carries identity; privileged action still needs a grant (pos) | NEEDS-CREDENTIALS | allow only with a recorded grant |
| F2 | valid-signature token with a role claim but **no recorded grant** → privileged write (abuse) | NEEDS-CREDENTIALS | deny (debt B1 — may currently allow) |
| F3 | token whose `iss` ≠ home issuer → privileged op (abuse) | TESTABLE NOW | reject (401/403) — **live: 401 ✓** |
| F3 | tenant/membership/classification alone grants nothing (abuse) | NEEDS-CREDENTIALS | deny without a grant |
| F4 | tenant id == network slug used as authority (abuse) | NEEDS-CREDENTIALS | deny — distinct namespaces (debt B11/B2) |
| F5 | durable authority survives restart (pos) | NEEDS-BUILD | out of black-box scope (restart orchestration) |
| F6 | kernel treats an unknown schema opaquely (pos) | TESTABLE NOW | write/resolve of a novel schema is schema-governed, not domain-special-cased |
| F7 | kernel authorizes with no Network call in hot path (pos) | NEEDS-BUILD | requires network-down orchestration (debt B9) |
| F8 | anonymous privileged op → deny (abuse) | TESTABLE NOW | anon write = 403 ✓; anon governance = 401 ✓ |
| F8 | anonymous read → **deny** (abuse) | EXPECTED FAIL (debt A1) | rule: 401; **live: 200** (REQUIRE_AUTH off) → xfail |
| F9 | service-to-service uses minted home-issuer tokens, no shared secret (pos) | NEEDS-BUILD | internal hop, not black-box |
| F10 | scope not widenable beyond grant (abuse) | NEEDS-CREDENTIALS | deny (debt B12) |
| F11 | grant platform.authority needs a 2nd-holder CR; last holder not revocable (abuse) | NEEDS-CREDENTIALS | deny (debt A17; ADR-0122) |
| F12 | every decision audited; failed auth logged (pos) | NEEDS-BUILD | audit store not black-box readable (debt A9) |
| F13 | consent granted only by subject (abuse) | NEEDS-CREDENTIALS | admin cannot self-grant another's consent |
| F14 | authority record names its grantor (pos) | NEEDS-CREDENTIALS | read a role_assignment, assert `granted_by` present |
| F15 | foreign-issuer token with a tenant/role claim → rejected/stripped (abuse) | TESTABLE NOW | reject (401) — **live: 401 ✓** |
| F16 | missing required config stops startup; no prod-pointing default (pos) | NEEDS-BUILD | startup-time, not black-box |
| F17 | agent acts only via recorded delegation; cannot self-widen (abuse) | NEEDS-BUILD | no delegation primitive exists (F17 NOT BUILT) |
| §3 two-key | read a specific person's data with a CapabilityGrant but NO consent → deny (abuse) | NEEDS-BUILD | personal data needs grant AND consent (ADR-0127); access_grant derived, not issued — not built |
| §3 two-key | read non-personal data with the grant only → allow; access_grant is derived (pos) | NEEDS-BUILD | non-personal needs grant only; derived access_grant matches shadow (ADR-0127 migration) |

## REGISTRY (R1–R16)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| R1 | write a record, re-read by id — id stable (pos) | NEEDS-CREDENTIALS | same id resolves |
| R2 | write with an ungoverned/unknown schema → reject (neg) | NEEDS-CREDENTIALS | reject (anon write already 403 ✓ at the gate) |
| R2 | anonymous write → reject (neg) | TESTABLE NOW | **live: 403 ✓** |
| R3 | supersede creates a new version; prior still addressable (pos) | NEEDS-CREDENTIALS | two versions resolvable |
| R4 | as-of read returns the version live at that time (pos) | NEEDS-CREDENTIALS | bitemporal answer |
| R5 | anonymous/forged write → deny (abuse) | TESTABLE NOW | anon 403 ✓; forged 401 ✓ |
| R5 | valid writer without grant → deny (abuse) | NEEDS-CREDENTIALS | deny (debt B1) |
| R6 | anonymous read → **deny** (abuse) | EXPECTED FAIL (debt A1) | rule: 401; **live: 200** → xfail |
| R6 | anonymous existence/count check → **deny** (abuse) | EXPECTED FAIL (debt A1) | rule: 401; live: likely 200 → xfail |
| R7 | every write carries provenance (pos) | NEEDS-CREDENTIALS | written record has prov (PROV_ENFORCE shadow, A2) |
| R8 | committed version is signed (pos) | NEEDS-CREDENTIALS | signature present on read-back |
| R9 | identical re-write creates no new version (pos) | NEEDS-CREDENTIALS | version count unchanged (to-confirm) |
| R10 | resolve same ref twice → same version (pos) | TESTABLE NOW (anon read) | deterministic result for a public/empty resolve |
| R11 | schema is a governed record; adopting ≠ owning (pos/abuse) | NEEDS-CREDENTIALS | non-owner cannot evolve a schema |
| R12 | trust-bearing write is audited (pos) | NEEDS-BUILD | audit not black-box readable |
| R13 | kernel treats a novel schema opaquely (abuse) | TESTABLE NOW | no domain special-casing of an unknown schema name |
| R14 | personal data stored by reference; erasure deletes + records (pos) | NEEDS-BUILD | erasable store not built (PLANNED) |
| R15 | public is a schema-level flag changed via CR (abuse) | NEEDS-BUILD | hardcoded allow-list today (debt B8) |
| R16 | archived version resolves identically (pos) | NEEDS-BUILD | archiving not built (PLANNED) |
| R18 | file write creates a platform.file record + bytes; anon/unauthorized read denied (abuse) | NEEDS-BUILD | platform.file + Kernel file endpoints not built; today a flat filestore behind the svc:filestore shadow gate (A72) |
| R18 | component reads/writes a file only via the broker under its run token + scope (abuse) | NEEDS-BUILD | broker file.read/file.write capability not built |
| R18 | large-file read issues a short-lived single-use signed link; replay/expiry rejected (abuse) | NEEDS-BUILD | signed-link path not built |
| R18 | erasing a file deletes the bytes; shared bytes kept while another owner references them (pos) | NEEDS-BUILD | reference-counted deletion + R14/R17 on files not built |

## DECISION (D1–D12)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| D1 | a protected authorization produces a decision record (pos) | NEEDS-BUILD | decision records not emitted for routine authz (debt A9/B1) |
| D2 | decision record carries request/policy-version/inputs/decider (pos) | NEEDS-CREDENTIALS | fields present on a decision read |
| D3 | same inputs → same outcome; model output recorded as input (pos) | NEEDS-BUILD | replay harness + model-input capture not exposed |
| D4 | decider with no recorded authority → deny / not recorded (abuse) | EXPECTED FAIL (debt B3) | rule: deny; live: authentication accepted as authority |
| D5 | decision never edited; override = new record (pos) | NEEDS-CREDENTIALS | original immutable |
| D6 | a denial is recorded with reason (abuse) | NEEDS-BUILD | denials not logged (debt A9) |
| D7 | personal data in a decision by reference only (pos) | NEEDS-BUILD | inherits R14 (PLANNED) |
| D8 | reason codes present; subject reads own decisions (pos) | NEEDS-BUILD | subject-access not built |
| D9 | decision linked by correlation/op id (pos) | NEEDS-CREDENTIALS | op_id/correlation present |
| D10 | personal-data read always gets a full record (pos) | NEEDS-BUILD | tiered logging not built |
| D11 | contest = recorded request; reviewer ≠ decider; new decision (pos) | NEEDS-BUILD | contest flow not proven |
| D12 | automated decision labelled + contestable; engine needs human authority (abuse) | NEEDS-BUILD | engines write governance.decision (debt B18) |

## NETWORK (N1–N12)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| N1 | net:id ≠ slug; slug/tenant not accepted as net authority (abuse) | NEEDS-CREDENTIALS | deny when slug==tenant is used as authority (debt B11/B2) |
| N2 | create network needs policy+role; draft invisible; draft→active needs catalog (pos) | NEEDS-CREDENTIALS | creation gated; draft has empty catalog |
| N3 | anonymous/forged governance role write → deny (abuse) | TESTABLE NOW | **live: anon governance = 401 ✓** |
| N3 | security-critical role assign needs a 2nd-holder CR; never zero admin (abuse) | NEEDS-CREDENTIALS | deny single-holder self-assign |
| N4 | suspended network refuses exchange, allows governance/history reads (pos) | NEEDS-BUILD | status machine not verified |
| N5 | membership invite→accept / request→approve; members are existing tenants (pos) | NEEDS-CREDENTIALS | participation request/decide |
| N6 | join never creates a login from the Network side (abuse) | EXPECTED FAIL (debt B9) | rule: no login created; live: join path provisions a user+password |
| N7 | issuer trust needs network.admin, scoped to member tenant+net (abuse) | EXPECTED FAIL (debt — N7) | rule: admin-only, scoped; live: membership.steward can approve, service-wide |
| N8 | a classification does not gate exchange (abuse) | NEEDS-CREDENTIALS | deny classification-as-authority |
| N9 | grant with a wildcard / unversioned capability → reject (abuse) | NEEDS-CREDENTIALS | reject `service:"*"` (debt B12) |
| N10 | publish a Service without the provide grant → reject (abuse) | NEEDS-CREDENTIALS | reject |
| N11 | exchange checks call+provide grant + consent, emits a decision (pos) | NEEDS-CREDENTIALS | allow only with both grants |
| N12 | member list is members-only; only chosen offerings public (abuse) | NEEDS-CREDENTIALS | anon cannot read the member list |

## ACCOUNT (A1–A9, W1–W4)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| A1 | account owned by person; cross-network link needs consent (pos) | NEEDS-CREDENTIALS | link only with consent |
| A2 | id ≠ handle ≠ binding; handle unique in namespace; old handle reserved (pos) | NEEDS-BUILD | handle/reservation model not verified |
| A3 | raw identifier never an id / never shown; one identity → one account (abuse) | NEEDS-BUILD | assurance not trustworthy (debt B13); R14 store PLANNED |
| A4 | handle is never a credential; login via approved issuer (abuse) | TESTABLE NOW | `POST /login` with a handle-as-password fails (401) |
| A5 | provider connect needs consent + provider confirm; revocable (pos) | NEEDS-CREDENTIALS | ADR-0067 flow |
| A6 | wallet separate/replaceable (pos) | NEEDS-CREDENTIALS | wallet swap preserves account |
| A7 | consent granted by holder; one withdraw view; withdraw→erase (pos) | NEEDS-BUILD | consent enforcement pending (debt B12); erasure PLANNED |
| A8 | assisted access via F17 delegation (pos) | NEEDS-BUILD | no delegation primitive (F17 NOT BUILT) |
| A9 | closure withdraws consents + triggers erasure (pos) | NEEDS-BUILD | not built |
| W1 | credential verifies offline via Registry keys (pos) | NEEDS-CREDENTIALS | VC verify |
| W2 | revocation checkable (pos) | NEEDS-CREDENTIALS | revoked credential fails verify |
| W3 | presentation bound to holder/recipient/purpose (abuse) | NEEDS-BUILD | recipient/purpose binding PLANNED |
| W4 | selective disclosure (pos) | NEEDS-BUILD | PLANNED |

## CLIENT (C1–C6)

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| C1 | unregistered client → reject; registered client recorded (abuse) | NEEDS-CREDENTIALS | reject unknown client (debt A47 demo client) |
| C2 | app requests scope beyond registered/consented → bounded (abuse) | EXPECTED FAIL (debt B12) | rule: intersection enforced; live: `/embed/authorize` takes scope from query, consent `service:"*"` |
| C3 | token short-lived, app-addressed, identity-only, consent ref (pos) | NEEDS-CREDENTIALS | token claims shape |
| C4 | protocol operations present (pos) | NEEDS-CREDENTIALS / partial | embed/request/offerings live |
| C5 | handle resolution registered-only + anti-enumeration (abuse) | EXPECTED FAIL (debt B6) | rule: gated, minimal, rate-limited; live: directory enumerable (identity not at :8080, but the invariant is unheld platform-wide) |
| C6 | clients use a public versioned protocol, never /bridge/* (abuse) | EXPECTED FAIL (debt A23) | rule: public protocol; live: only /bridge/* + /embed/* exist |

---

## PLATFORM (P1–P21) — see [[PLATFORM-v0.1]]

All Platform rules are governance/installer/onboarding flows that are not built or need a platform-authority
session + onboarding records that do not exist in local-dev → **NEEDS-BUILD**, except the slivers noted.

| Rule | Case (type) | Classification | Expected observable |
|------|-------------|----------------|---------------------|
| P1 | installer creates only the minimum; idempotent (pos) | NEEDS-BUILD | install-time; inspect the seed set (not black-box at runtime) |
| P2 | first platform.authority via one-time expiring installer cred (pos) | NEEDS-BUILD | install-time; one-time cred not built [A17] |
| P3 | operator holds no governance role (abuse) | NEEDS-BUILD | needs operator identity; separation not enforced [A38] |
| P4 | platform-tenant member w/o a grant is denied a privileged act (abuse) | NEEDS-CREDENTIALS | EXPECTED-FAIL [B2/A17] — needs a platform-tenant session (not in local-dev creds) |
| P5 | grant platform.authority needs 2nd-holder CR; last holder not removable (abuse) | NEEDS-BUILD | recorded-role path not the enforced one [A17] |
| P5a | break-glass custodian quorum restores only platform.authority (pos) | NEEDS-BUILD | not built (ADR-0122 open item) |
| P6 | security-sensitive policy change requires a ChangeRequest (abuse) | NEEDS-BUILD | tier/issuer/suspension policy records not built |
| P7 | onboarding mode is a recorded policy (pos) | NEEDS-BUILD | onboarding-mode policy not a single record |
| P8 | application record + ≥1 steward review; authority-fallback recorded (pos) | NEEDS-BUILD | application record + steward queue not built |
| P8a | verification methods (gov email+letter / GST) (pos) | NEEDS-BUILD | no verification-method registry |
| P9 | self-provisioned tenant starts sandbox; sandbox cannot create a Network (abuse) | NEEDS-CREDENTIALS | needs a sandbox-tenant session; tier constraints [A28] *to confirm* |
| P10 | approval creates identity+keys+platform-signed directory entry+tenant.admin (pos) | NEEDS-BUILD | keys + signed directory entry at approval *to confirm* |
| P11 | tenant.admin never zero; network.creator tier-gated (abuse) | NEEDS-CREDENTIALS | needs tenant-admin session; floor/gating *to confirm* |
| P12 | tenant own-login allowed only if tier+policy permit; approval recorded (abuse) | NEEDS-BUILD | tier/policy gating of own-IdP not built; N7 VIOLATED |
| P13 | suspension halts principals, history readable; closure cascades + erases (pos) | NEEDS-BUILD | suspend/close lifecycle not built (N4, R14) |
| P14 | admin visibility + action re-checked server-side from recorded roles (abuse) | PARTIAL / NEEDS-CREDENTIALS | anon governance-write denied (N3) already PASSes as one slice; full recheck needs sessions [B17/B1] |
| P15 | public front door exposes only apply/verify/status; admin routes separate (abuse) | NEEDS-BUILD | apply/verify/status front door + bot-protection not built |
| P16 | component reaches a vendor directly, bypassing the platform gateway (abuse) | NEEDS-BUILD | blocked — capabilities only via gateways; declared-egress does not include vendor hosts for gatewayed capabilities |
| P17 | use a provider not in the CR-approved catalog (abuse) | NEEDS-BUILD | no governed provider catalog exists (PLANNED); nothing to assert black-box |
| P18 | a component receives a provider credential / a non-approved provider is selectable (abuse) | NEEDS-BUILD | creds stay gateway-side in the tenant Vault; selection limited to approved set (depends on P17) |
| P19 | a member using a provider below the Network's minimum (assurance/region) (abuse) | NEEDS-BUILD | no network minimum-requirement record enforced (PLANNED) |
| P20 | personal data sent to a provider without a lawful-basis/decision record (abuse) | NEEDS-BUILD | egress blocked without consent + processor record (PLANNED) |
| P21 | provider + version recorded on every call; per-tenant metering; recorded failover (pos) | NEEDS-BUILD | per-call provider/version stamp (DECISION D3) + tenant failover not fully built; metering hook partial |

Testable-now slivers already covered elsewhere: P14's server-side denial of an anonymous governance write =
the NETWORK **N3** PASS; P4's authority-from-tenant is the same root as the external R6 posture + debt B2.

## COMPONENT (CP1–CP18) — see [[COMPONENT-v0.1]]

Mostly **NEEDS-BUILD**: exercising component rules needs a published/certified/installed component and the
run-token broker path, none of which are black-box reachable on the bedrock local-dev stack (no components
published; app-host 403 on `/bridge/install`; the broker `/v1/*` endpoints need a run token). A few are
reachable with a supplied publisher/dev bearer (**NEEDS-CREDENTIALS**). The [[PIPELINE-PROOF-FINDINGS]] run
established the live responses behind D1–D6.

| Rule | Case (type) | Classification | Expected observable |
| --- | --- | --- | --- |
| CP1 | installed component writing an undeclared schema via the broker → deny (abuse) | NEEDS-BUILD | run token = declaration; write outside declared scopes rejected |
| CP2 | `component.builder` installs+runs in own tenant with NO certificate/store (pos) | NEEDS-BUILD | private lane: build/install/run/schedule succeed in-tenant without a store listing (CP2 PLANNED — not built; D1) |
| CP2 | a principal WITHOUT `component.builder`/`component.operator` runs a component (abuse) | NEEDS-BUILD | deny — authority is the recorded role, not a `tenant_env` token claim (A28) |
| CP3 | run token exceeds manifest ∩ runner authority (abuse) | NEEDS-BUILD | effective caps = declaration ∩ grant; no widening |
| CP4 | schedule fires after its owner's authority is revoked (abuse) | NEEDS-BUILD | scheduler re-checks before each run and SUSPENDS when authority is gone (PLANNED; A28) |
| CP5 | component makes egress to an undeclared host / exceeds quota (abuse) | NEEDS-BUILD | blocked — egress only to declared hosts; quota enforced (quotas PLANNED, CP11) |
| CP5 | component reads a platform credential from its environment (abuse) | NEEDS-BUILD | none present; secrets only by name via the runtime manager |
| CP6 | component reaches the filestore/datastore directly, not via the broker (abuse) | NEEDS-BUILD | only broker `/v1/read|write|query|files` under the run token (files via broker PLANNED; A72) |
| CP7 | runtime manager rejects source whose digest ≠ the certificate (abuse) | NEEDS-BUILD | run refused on digest mismatch; the component never fetches its own source (D-R13; fixed by KERNEL-MEDIATED-FILES) |
| CP8 | cross-tenant install of an UN-certified component (abuse) | TESTABLE NOW | install resolves only from the store + verifies the cert → `install` 404/"no valid certificate" (**live: 404 "not found in the store" ✓**, finding D5/E) |
| CP8 | certify on-behalf: publisher of record = the developer's tenant (pos) | NEEDS-CREDENTIALS | certify accepts the recorded on-behalf publisher (F17) — **today 422 `steward-is-publisher`** (finding D2) → EXPECTED FAIL once asserted |
| CP9 | install another tenant's component without recording the admin's consent (abuse) | NEEDS-BUILD | install blocked until informed consent to the declared access is recorded (PLANNED) |
| CP10 | an unverified/development tenant publishes to the marketplace (abuse) | NEEDS-CREDENTIALS | refuse 403 — **live: network `store_publish` 403 "development-tenant components cannot be published" ✓** (finding D5) |
| CP11 | platform quota/egress policy keyed by verification status (pos) | NEEDS-BUILD | no status-keyed quota/egress policy exists (PLANNED) |
| CP12 | run produces a durable receipt; build/install/publish/consent audited (pos) | NEEDS-BUILD | durable run receipts TODO (scheduler ring is in-memory); decision records exist for publish/governance |
| CP13 | install a solution bundle → all members pinned at their versions (pos) | NEEDS-CREDENTIALS | members resolve at the bundle's pinned versions (ADR-0075/0076) |
| CP14 | contribute with `component.publisher` but no Network contribute grant (abuse) | NEEDS-BUILD | inbound Network contribute grant is a distinct recorded gate (PLANNED; outbound role live) |
| CP15 | certify a component with an UNGOVERNED schema → withhold with reasons (abuse) | NEEDS-CREDENTIALS | 422 conformance withheld, reasons listed — **live: 422 `governed-vocabulary` ✓** (finding D3); also certify 500 on malformed `files` input → should be 422 (D4) |
| CP15 | listing security-scan / declared-access-vs-policy / licence-terms checks (pos) | NEEDS-BUILD | not built (security scan PLANNED; access-policy gate PLANNED; licence/terms PLANNED) |
| CP16 | re-publish same `(id, version)` with changed bytes → reject (abuse) | NEEDS-CREDENTIALS | 409 immutable+monotone (network `STORE.version_error`) |
| CP16 | upgrade to a version asking MORE access without re-consent (abuse) | NEEDS-BUILD | re-consent required; no silent upgrade (PLANNED) |
| CP17 | suspend a listing → reason recorded, installers notified, installed copy survives (pos) | NEEDS-BUILD | revoke/deprecate record a reason (live); installer notification PLANNED; installed run token persists |
| CP18 | a priced listing records terms/commitment/settlement; money on rails (pos) | NEEDS-BUILD | contract terms modelled; settlement model + payment rail PLANNED |

## OFFERINGS (O1–O12) — see [[OFFERINGS-v0.1]]

All **NEEDS-BUILD**: Benefit/Information offering kinds, eligibility-as-policy, funding envelopes, settlement
and the contest flow are not built; Services (O5) exist but exercising them end-to-end needs a provider + call
grant (NEEDS-CREDENTIALS).

| Rule | Case (type) | Classification | Expected observable |
| --- | --- | --- | --- |
| O1 | publish an offering without the matching `*.provide` grant (abuse) | NEEDS-BUILD | refuse — provide grant required (N9/N10); Benefit/Information kinds not built |
| O2 | a terms change re-prices an existing commitment (abuse) | NEEDS-BUILD | commitment keeps its terms version; lifecycle draft/suspended/withdrawn not built |
| O3 | offering terms carry payer/funder, timing, refunds, data-use, licence (pos) | NEEDS-BUILD | terms fields beyond price/SLA not built |
| O4 | eligibility decided without a policy/decision record (abuse) | NEEDS-BUILD | eligibility = POLICY + decision record (D1/D8) — not built |
| O5 | call a Service without a `service.call` grant (abuse) | NEEDS-CREDENTIALS | refuse; ADR-0067 path exists but needs a provider + grant |
| O6 | a benefit sanction exceeds the funding envelope (abuse) | NEEDS-BUILD | draw-down cannot exceed envelope; envelope + D12 sanction + rail not built |
| O7 | information access without consent / beyond the time limit (abuse) | NEEDS-BUILD | scoped, time-limited, consent-gated read not built as an offering |
| O8 | settlement mismatched to the rail reference → exception (abuse) | NEEDS-BUILD | settlement/rail-match/exception records not built |
| O9 | offering visible beyond its N12 audience (abuse) | NEEDS-BUILD | visibility per N12; per-kind not built |
| O10 | offering stays usable after the provider's grant/membership lapses (abuse) | NEEDS-BUILD | auto-suspend on lapse not built (N9 to-confirm) |
| O11 | personal data used under a purpose-mismatched consent (abuse) | NEEDS-BUILD | purpose-matching not built; embed consent unbound (B12) |
| O12 | contest an outcome / claim a refund (pos) | NEEDS-BUILD | D11 contest flow + refund settlement not built |

## POLICY (PL1–PL8) — see [[POLICY-v0.1]]

The rule engine (ADR-0088) is the live nucleus (PL1/PL3/PL4/PL6 partial); fact-provenance, self-assertion,
minimum disclosure, the function catalog and the publish-time test gate are **NEEDS-BUILD**.

| Rule | Case (type) | Classification | Expected observable |
| --- | --- | --- | --- |
| PL1 | a policy carries executable code, not a typed tree (abuse) | NEEDS-BUILD | reject — typed rule tree only; single cross-use tree schema not built |
| PL2 | a self-asserted fact accepted where the policy did not allow it / unsigned (abuse) | NEEDS-BUILD | accept only where allowed, wallet-signed, labelled self-asserted — not built |
| PL3 | same policy version + facts → same result; replay from a decision record (pos) | NEEDS-CREDENTIALS | deterministic (D3); full replay to policy version + facts (to confirm) |
| PL4 | evaluation returns per-clause results + evidence + plain-language reasons (pos) | NEEDS-BUILD | per-clause evidence + D8 subject reasons not built (engine trace only) |
| PL5 | a policy pulls more personal facts than the clauses need (abuse) | NEEDS-BUILD | minimum disclosure (W4) not enforced at evaluation |
| PL6 | the same language expresses eligibility, consent, automation, limits, grant conditions (pos) | NEEDS-BUILD | shared evaluator exists; full reuse across all five not built |
| PL7 | a clause calls a function outside the governed catalog (abuse) | NEEDS-BUILD | governed function catalog not built |
| PL8 | publish a policy whose own tests fail (abuse) | NEEDS-BUILD | publish-time test gate not built |

## Internal runner (step 3)
The reference services are not published at the edge, so external mode cannot reach them. An **internal
runner** executes the same suite (`AOS_MODE=internal`) inside a container on the local-dev docker network
(`airawatos-localdev_default`), against in-cluster addresses. It covers cases that external mode could only
mark SKIP_BUILD "not reachable black-box":
- **F10 / B5** — reference endpoints accept **tokenless** privileged calls (filestore, notify, scheduler
  `/run`, model-gateway `/complete`, automation `/events`).
- **F9 / B4** — fail-open internal-token gates (secrets `/materialize`, `/fetch`; runtime-manager `/invoke`).
  The fail-*open* only manifests when the gate env is **unset**; where the gate is **active** in local-dev
  (e.g. `SECRETS_INTERNAL` set) the tokenless call is correctly rejected (403) and the case is **SKIP_BUILD**
  ("not reproducible without unsetting the gate env"), **not** a pass and **not** a fix.
- **B6** — identity `/users` directory disclosure.

Classifier rule for internal tokenless probes: a handler that **runs without a token** (2xx/400/500/501) =
XFAIL (violation present); **401/403** = gate active → SKIP_BUILD; **404 / unreachable** = SKIP_BUILD.

## Run results — 2026-11-03

**Credentials diagnosis:** `.creds.json` loads correctly (5 users; admin and outsider sessions both open) —
the loader was never broken. The 8 cases that previously showed SKIP_CREDS were **unimplemented stubs
mislabeled**. Fixed: implemented **F2** (valid non-admin session denied a governance write — outsider →
`/bridge/role-grant` 403) and **C1** (unregistered embed client → 400); the remaining six (F14, R1, R3, R7,
N1, N9) are reclassified **SKIP_BUILD** with honest reasons (no black-box registry-write bridge; `/bridge/roles`
and the capability-grant bridge refuse even the tenant admin). Net: **nCRED = 0** — nothing skips for
"missing credentials" any more.

**External mode** (`127.0.0.1:8080`, credentials supplied):

| Spec | PASS | XFAIL | XPASS | FAIL | nCRED | nBUILD |
|------|----|----|----|----|----|----|
| FOUNDATIONS | 5 | 0 | 0 | 0 | 0 | 5 |
| REGISTRY | 1 | 2 | 0 | 0 | 0 | 9 |
| DECISION | 0 | 0 | 0 | 0 | 0 | 9 |
| NETWORK | 1 | 0 | 0 | 0 | 0 | 5 |
| ACCOUNT | 1 | 0 | 0 | 0 | 0 | 7 |
| CLIENT | 1 | 0 | 0 | 0 | 0 | 2 |
| **TOTAL** | **9** | **2** | **0** | **0** | **0** | **37** |

PASS now includes F1 (admin session opens), **F2** (outsider denied governance write 403), **C1**
(unregistered client rejected 400). XFAIL: anon kernel read = 200, anon existence-check = 200 (debt A1).

**Internal mode** (in-cluster, container on the ld network):

| Spec | PASS | XFAIL | XPASS | FAIL | nCRED | nBUILD |
|------|----|----|----|----|----|----|
| FOUNDATIONS | 0 | 3 | 0 | 0 | 0 | 5 |
| REGISTRY | 0 | 1 | 0 | 0 | 0 | 0 |
| CLIENT | 0 | 1 | 0 | 0 | 0 | 0 |
| **TOTAL** | **0** | **5** | **0** | **0** | **0** | **5** |

Internal XFAIL (violations confirmed live): scheduler `/run` 200, model-gateway `/complete` 501, automation
`/events` 200 — all tokenless (F10/B5); identity `/users` 200 discloses the directory (B6); kernel anon read
200 (A1). Internal SKIP_BUILD: filestore (`/` 404 — needs a real privileged route), notify (unreachable),
secrets `/materialize` & `/fetch` (403 — gate active; fail-open needs env unset), runtime-manager (absent
from the ld stack). Both modes exit 0 (no FAIL, no XPASS).

### "Feature not built" vs "now covered by the internal runner"
- **Now covered by the internal runner** (were external SKIP_BUILD "not reachable black-box"): **B5**
  (unauth privileged reference endpoints) → confirmed XFAIL for scheduler/model-gateway/automation; **B6**
  (identity directory disclosure) → confirmed XFAIL; **B4** (fail-open gates) → reachable and probed, but
  SKIP_BUILD where the gate is active (needs the env unset).
- **Genuinely not built / not black-box-assertable** (remain SKIP_BUILD in both modes): the DECISION plane
  (D1,D3,D4,D6,D7,D8,D10,D11,D12 — no decision records emitted), REGISTRY R12/R14/R15/R16, FOUNDATIONS
  F5/F7/F16/F17, ACCOUNT A2/A3/A7/A8/A9/W3/W4, CLIENT C6, NETWORK N4 — each for a stated reason (feature
  PLANNED, startup/restart-time, or audit store not externally readable).
- **B15** (run_token leak): no false pass anymore — SKIP_BUILD. **Apps ≠ kernel-installed components:** the
  bootstrap *certifies and shelves 8 base **apps*** (kind:app — static front-end bundles delivered via
  filestore and made visible per tenant via `platform.app_shelf`); apps get **no runtime container and no
  `run_token`** and are **not** in the kernel `INSTALLED` map. Only **engines/drivers/connectors** installed
  via `POST /v1/components/install` (`_install_one` → `_mint_run_token`) populate `INSTALLED` with a
  `run_token`. So "8 certified apps but INSTALLED empty" is expected, not a bug. B15 cannot be exercised live
  on this local-dev stack for two reasons: (1) **no components are published** — `platform.component` /
  `component.listing` / `marketplace.listing` all return 0 records and `/bridge/components` is empty, so
  there is nothing to install; (2) the admin session is **403 on `/bridge/install`** (lacks the
  `platform.component_install` grant). The leak itself is **structurally confirmed** in code (kernel
  `/v1/components` returns `list(INSTALLED.values())` unauthenticated, and `INSTALLED` entries carry
  `run_token` — debt B15, `app.py:2369/2058`); it only manifests once `INSTALLED` is non-empty. To exercise:
  publish+certify a driver from `components/drivers/*`, grant `platform.component_install`, install it, then
  set `AOS_TEST_COMPONENT` — the suite auto-discovers a cid from `/bridge/components` and will flip B15 to
  XFAIL when `run_token` appears.
- **B4 runtime-manager fail-open** (`RUNTIME_MANAGER_INTERNAL` unset → `/invoke` fail-open): **cannot be
  exercised locally** — there is **no runtime-manager service in the local-dev stack** (not in the ld
  compose). The internal runner records it SKIP_BUILD. This case is **covered by the EC2 hardening task**,
  where runtime-manager runs; the secrets `/materialize` & `/fetch` fail-open likewise needs the gate env
  UNSET, which the EC2 task can assess without a local service change.
- **R10** (determinism): no longer a trivial-on-empty pass — NEEDS-CREDENTIALS/SKIP (anon reads return 0
  rows; a records-returning resolve bridge was not found black-box).

## First-suite scope (what `conformance/` actually runs)
The runnable suite (`conformance/run.py`) implements every **TESTABLE NOW** and **EXPECTED FAIL** case above
that is reachable at `:8080` without credentials. **NEEDS-CREDENTIALS** cases are included but skip unless
`AOS_TEST_USERS` / `conformance/.creds.json` is supplied. **NEEDS-BUILD** cases are listed (as skips with the
reason) but not executed. See `conformance/README.md` to run and to supply credentials.

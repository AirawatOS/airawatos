# ACCOUNT-v0.1 — Person accounts, consent, and the wallet

**Status:** Draft v0.1 · **Date:** 2026-11-03
**Builds on:** [[FOUNDATIONS-v0.1]] (F1–F17; esp. **F13** consent, **F17** acting-on-behalf), [[REGISTRY-v0.1]]
(esp. **R14** personal data by reference), [[DECISION-v0.1]] (**D7** personal data, **D8** subject access,
**D12** automated decisions), and [[NETWORK-v0.1]] (account type is Network-defined). Assumed, not restated.
**Debt references** are to `../consolidation/DEBT-REGISTER.md`; to avoid collision with this spec's rule ids,
debt items are written **"debt A47"** etc. *(to confirm)* = not traced this pass.
**Status legend:** IN PLACE · PARTIAL · VIOLATED · PLANNED · TO CONFIRM.

> Note: this spec's rule ids **A1–A9** (account) and **W1–W4** (wallet) are local to this document and are
> **not** the debt-register A-items.

---

## Account rules

### A1 — Ownership and account type
An account is **owned by the person**, and is **scoped to one Network-defined account type**. A person may
hold **accounts in several Networks**; those accounts are **linked only with the person's consent**.
- **Status: PARTIAL / PLANNED.** A person-centric citizen model exists (jurisdiction & service federation;
  participant ≠ tenant, ADR-0116), and account types are Network-defined in principle (NETWORK N9/N10). But
  **cross-Network account linking under consent** is **PLANNED** — the consent primitive is decided but not
  enforced (ADR-0125), and per-object consent is adopted by 0 prod schemas (ADR-0103). One-account-per-type
  scoping **(to confirm)**.
- **Refs:** ADR-0116, ADR-0117, ADR-0125; NETWORK N9/N10; F13.

### A2 — Identifiers
The **permanent global account id**, the **handle**, and the **identity binding** are **distinct**. The
handle is **unique within its Network namespace**; its **format leaves room for future cross-installation
qualification**; and **old handles are reserved after a change** (never re-issued).
- **Status: TO CONFIRM / PLANNED.** A permanent account id exists (REGISTRY R1). The **three-way distinction**
  (id ≠ handle ≠ binding), **namespace-unique handle**, **cross-installation-qualifiable format**, and
  **old-handle reservation** are **(to confirm)** / not verified as designed; handle uniqueness scoping and
  reservation are likely **PLANNED**.
- **Refs:** REGISTRY R1 (permanent id); NETWORK N1 (net:id namespace separation); debt B6 (identity directory
  disclosure — bears on handle lookup, see CLIENT C5). Distinction + reservation **(to confirm)**.

### A3 — Identity binding and assurance
The identity binding comes from an **approved proofing source** meeting the **account type's assurance
policy**. **Raw identifiers are never used as account ids and never shown to participants**, and are stored
per **REGISTRY R14** (separate erasable store, reference + hash). **One verified identity → one active
account per account type.**
- **Status: VIOLATED / PLANNED.** Assurance is **not trustworthy today** — identity stamps a uniform `A0`
  (debt A34, B13) and Keycloak a static `A2` (debt A35), so an account-type assurance policy cannot rely on
  it. **Raw-identifiers-per-R14** inherits R14 (**PLANNED** — no erasable store yet). **One-identity-one-
  account-per-type** **(to confirm)**.
- **Refs:** debt B13, A34, A35; REGISTRY R14; ADR-0068 (pluggable IdP, assurance), ADR-0049 (VC). Assurance-
  computed-from-method is the fix (B13).

### A4 — Login and recovery
Login is via an **approved issuer** (F1/F15). The **handle is never a credential**. **Every account type
defines recovery.**
- **Status: PARTIAL.** Pluggable IdP with approved issuers exists (ADR-0068 kernel EdDSA+RS256; ADR-0117;
  password-login rollout, reference IdP optional password gate). Handle-not-a-credential holds by design
  **(to confirm)** no path treats the handle as a secret. **Per-account-type recovery** is **PLANNED / (to
  confirm)**.
- **Refs:** ADR-0068, ADR-0117, password-login-rollout; F1, F15. Recovery-per-type **(to confirm)**.

### A5 — Provider connections
Connecting an account to a **provider** requires **the person's consent** **and** the **provider's
confirmation**, and is **revocable**.
- **Status: PARTIAL / PLANNED.** The service init→provider-case flow exists (ADR-0067 S2/S3: init → provider
  case, confirm/status) and carries a fee-quote + consent step (S5). But **consent** as the first-class
  revocable primitive is pending (ADR-0125); **revocation of a connection** **(to confirm)**.
- **Refs:** ADR-0067 (S2/S3/S5), ADR-0125; F13. Revocable connection **(to confirm)**.

### A6 — Wallet is separate and replaceable
The **wallet is a separate component** from the account and is **replaceable** (swapping the wallet does not
change the account or its identity binding). The wallet also **signs self-asserted claims** the holder makes
about themselves: the holder's **wallet key signs the claim**, binding it to them; a **policy decides whether
to accept it for the named fact and labels the fact self-asserted** (POLICY **PL2**) — the signature proves
*who asserted*, not that the claim is *verified*. Verified evidence (a credential) later **upgrades** the fact.
- **Status: PARTIAL.** The Document Wallet is a separate app with native Ed25519 (ADR-0049, LIVE). **Wallet
  replaceability** (account survives a wallet swap; keys re-bindable) is **(to confirm)**; **wallet-signed
  self-asserted claims** into policy evaluation are **PLANNED** (depends on POLICY PL2).
- **Refs:** ADR-0049 (Document Wallet & VCs); W1–W4 below; POLICY PL2 (self-asserted facts), W3/W4.
  Replaceability + self-asserted signing **(to confirm / PLANNED)**.

### A7 — Consents
Consents are **granted by the account holder** (never an admin — F13), **wallet-signed where possible**.
There is **one view to withdraw** them, and **withdrawal triggers erasure where the law requires** (REGISTRY
R14).
- **Status: PARTIAL / PLANNED.** Consent-granted-by-subject is the decided model (ADR-0125, F13), but
  enforcement is pending and embed consent is written unbound (`service:"*"`, debt B12). **Wallet-signed
  consent** **(to confirm)** against ADR-0049 keys; **one withdrawal view** and **withdrawal→erasure** are
  **PLANNED** (erasure inherits R14 + the DPDP timeline).
- **Refs:** ADR-0125, ADR-0049; debt B12; REGISTRY R14, DECISION D7; F13. See DPDP note below.

### A8 — Assisted access (acting on behalf)
Assisted access applies **FOUNDATIONS F17** for consumers: a person can **set up, view, and withdraw
delegations in plain language**, and **operators see clearly what they may do**. (A delegate is a principal
acting for the account holder within a recorded, revocable scope.)
- **Status: PLANNED (not built).** F17 (acting-on-behalf) has **no delegation primitive** today — there is no
  recorded delegation, so assisted access cannot yet show actor-vs-represented or be withdrawn as a
  delegation. Non-delegable/step-up acts (consent for sensitive data, closure, identity-binding change) are
  named in F17 and relate to A3/A7/A9.
- **Refs:** **FOUNDATIONS F17**; DECISION **D12** (automated/assisted decisions re a person); ADR-0125
  (sensitive-data step-up). PLANNED.

### A9 — Closure
Closing an account **withdraws its consents** and **triggers erasure**, **subject to legal retention**.
- **Status: PLANNED.** Account closure with consent-withdrawal + erasure-subject-to-retention is **not
  built** — erasure inherits REGISTRY R14 (PLANNED) and the DPDP timeline; "closing an account" is a
  non-delegable/step-up act per F17.
- **Refs:** REGISTRY R14, ADR-0125, FOUNDATIONS F17; DPDP note below. PLANNED.

---

## Wallet rules

### W1 — Offline verifiability
Participant-signed credentials are **verifiable offline** using keys from the **Registry** (no call to the
issuer at verify time).
- **Status: PARTIAL.** Document Wallet credentials are participant-signed with native Ed25519, and
  cross-state VC verification is demonstrated; offline/edge trust has a device-credential + relay-verify
  slice (ADR-0082 S1). **Verify-offline-via-Registry-keys** end-to-end **(to confirm)**.
- **Refs:** ADR-0049 (VC), ADR-0082 (offline & edge trust). Registry-key offline verify **(to confirm)**.

### W2 — Revocation checkable
A credential's **revocation status is checkable**.
- **Status: PARTIAL.** The credential service issues/verifies/**revokes** (ADR-0049 VC-S2). That a verifier
  can **check revocation** (status list / revocation registry) at verify time is **(to confirm)**.
- **Refs:** ADR-0049 (issue/verify/revoke). Revocation-check path **(to confirm)**.

### W3 — Presentation binding
A **presentation is bound to** the **holder key**, the **recipient**, and the **purpose** (so a captured
presentation cannot be replayed to another recipient or for another purpose).
- **Status: PLANNED / TO CONFIRM.** Holder-key signing exists (Ed25519/X25519 participant signing); **binding
  a presentation to recipient + purpose** is **PLANNED / (to confirm)**.
- **Refs:** ADR-0049, participant message signing (Ed25519/X25519); F13 (purpose). Recipient/purpose binding
  **PLANNED**.

### W4 — Selective disclosure
**Selective disclosure** (presenting a subset / derived predicate of a credential's claims) is **planned**.
- **Status: PLANNED (explicit).** Not built.
- **Refs:** ADR-0049. PLANNED.

---

## Summary of status

| Rule | Topic | Status | Key debt / refs |
|------|-------|--------|-----------------|
| A1 | Ownership + account type | PARTIAL/PLANNED | ADR-0116/0117/0125 |
| A2 | Id / handle / binding distinct | TO CONFIRM/PLANNED | R1; B6; N1 |
| A3 | Binding + assurance; raw ids per R14 | VIOLATED/PLANNED | B13, A34, A35; R14 |
| A4 | Login + recovery | PARTIAL | ADR-0068/0117 |
| A5 | Provider connections (consent+confirm) | PARTIAL/PLANNED | ADR-0067; ADR-0125 |
| A6 | Wallet separate + replaceable | PARTIAL | ADR-0049 |
| A7 | Consents (holder, wallet-signed, withdraw→erase) | PARTIAL/PLANNED | ADR-0125/0049; B12; R14 |
| A8 | Assisted access (F17) | PLANNED | F17; D12; ADR-0125 |
| A9 | Closure (withdraw + erase) | PLANNED | R14; ADR-0125; F17 |
| W1 | Offline verifiable via Registry keys | PARTIAL | ADR-0049/0082 |
| W2 | Revocation checkable | PARTIAL | ADR-0049 |
| W3 | Presentation bound to holder/recipient/purpose | PLANNED/TO CONFIRM | ADR-0049 |
| W4 | Selective disclosure | PLANNED | ADR-0049 |

---

## DPDP Consent Manager (open)
Consent records (A7) must be designed so an Airawat deployment can **either register as a DPDP Consent
Manager** (DPDP Rules, **Rule 4 — in force 13 Nov 2026**) **or integrate with registered ones** — i.e. the
`governance.consent` shape (ADR-0125) and the withdrawal/erasure flow must map to the Consent Manager
artefact and interoperate with external Consent Managers. **Whether a given deployment registers as a Consent
Manager is a legal/organisational decision, recorded here as OPEN.** This complements the DPDP **erasure**
open item in REGISTRY-v0.1 (§Open item, erasure provisions in force 13 May 2027) — Rule 4 (Consent Manager,
13 Nov 2026) governs the consent-management role; the erasure provisions (13 May 2027) govern the deletion
obligation.

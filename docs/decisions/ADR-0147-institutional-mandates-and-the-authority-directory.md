# ADR-0147 — Institutional mandates and the authority directory: who is authorised to do what, and who said so

**Status:** Proposed
**Date:** 2026-11-26
**Related:** ADR-0050 (the decision service), ADR-0138 (roles and capabilities), ADR-0141 (the commons), ADR-0144
(participation credentials; keys), ADR-0145 (custodians), ADR-0148 (delegation), ADR-0149 (interactions and evidence).
Prompted by an external review of the architecture (2026-11-26, §3, §4, §7, §13, §14).

## The problem

A verifier today can establish two things about an organisation: **who it is** (its keys in the directory) and **what it
may do on a network** (its role, through a participation credential and the network's policy). It cannot establish a
third: **whether the organisation is legitimately authorised to perform the function at all**.

- A network role that *provides* `credential.eshram_registration` combines participation with statutory authority. A
  network administrator could give that role to an employer, and the registrations it issued would verify.
- The commons signs the directory with one authority key, so the commons looks like the *source* of every
  organisation's legitimacy, when it should only *publish* authority granted elsewhere.
- Decisions about the commons itself (admitting a wallet provider, adding a role) were made as operator edits, with no
  accountable person behind them.
- Until 2026-11-26 the network service signed offers for organisations hosted on AirawatOS, with keys it held — so the
  network operator's service could sign as those organisations (fixed on staging by patches N19 and 74: hosted
  organisations sign with their own published keys; the network only verifies).

## Decision

1. **Four assertions, kept apart.** Every check distinguishes:

   | Assertion | Establishes | Granted by |
   |---|---|---|
   | Identity | this organisation is who it claims to be, and controls these keys | the organisation (its key set) + domain proof, published in the directory |
   | Mandate | it is authorised to perform this function, in this jurisdiction, for this period | the authority that holds that power (a ministry, regulator, licensing body, municipality) |
   | Participation | it may perform these interactions on this network | the network's governing institution (ADR-0144) |
   | Delegation | it may act for this person, within this scope | the person (ADR-0148) |

   None implies another. Membership of a labour network never makes an employer a registrar.

2. **A mandate is a signed credential from the granting authority.** It names the subject organisation, the function (a
   governed capability: *issue* a type, *decide* a matter, *operate* a service), the jurisdiction (from the jurisdiction
   registry), the legal basis (a reference to the instrument), the validity period, and its status entry. It is signed
   with the **granting authority's own key**, not the commons key. Mandates can be delegated down a chain (a ministry
   mandates a state department, which mandates district offices), each link signed by its grantor and no wider than it.

3. **The authority directory.** Beside the organisation directory, the commons publishes a directory of authorities:
   which bodies may grant which mandates, where. Its entries are *recognitions*, each recording who recognised the
   authority and on what basis. The commons publishes and verifies; it does not originate the power. A verifier decides
   which authorities it recognises for its purpose (its *trust anchors*); a network may set them in its policy.

4. **Vocabulary says which functions need a mandate.** A governed type or interface may be marked *mandated*
   (`x-mandate: required`, with the kind of authority that may grant it). For such a capability, a network role is
   effective only while the member also holds a current mandate for it; the network's policy says so and every verifier
   checks it locally, the same way it checks participation.

5. **More than one trust authority.** The single commons key is a starting point. The directory accepts signatures from
   several recognised trust authorities (federated directory operators), each with its own key and accountability.
   Directory entries record which authority signed them.

6. **Organisations control their own keys.** An organisation's signing key is under its own control, published at its
   key-set address and listed in the directory; no network or operator service signs for it. For organisations hosted on
   AirawatOS, the platform holds the key in its secret store and uses it only on a request authorised by one of that
   organisation's people. An act also carries the acting official's own signature where it is consequential (the
   per-person keys of the signing helper used by the decision service), so accountability reaches the person.

7. **Steward decisions are decisions.** Admitting members to the commons, recognising authorities, adding roles and
   publishing contracts are decisions by named people through the decision service (ADR-0050): signed, recorded with
   their basis, and open to review. Operator edits are for emergencies only, recorded as such.

## What changes on the current build

| Today | After |
|---|---|
| Roles imply authority to issue a type | Roles = participation; mandated types also need a mandate credential |
| The commons authority key signs everything | It signs directory integrity; mandates are signed by their grantors; several trust authorities |
| No record of who authorised an organisation's function | A mandate chain to a recognised authority, with its legal basis |
| Hosted organisations' offers signed by the network service (until N19) | Each organisation signs with its own key; the acting official signs consequential acts |
| Commons decisions as operator edits | Decisions by named stewards through the decision service |

## Acceptance tests

- A correctly signed eShram registration is **rejected** when its issuer holds the issuing role but no mandate from a
  recognised labour authority.
- A mandate revoked by its grantor stops being accepted within the network's revocation window.
- An organisation changes hosting operator and keeps its identity, mandates and memberships.
- No network or operator service can produce a valid signature for an organisation.

## Open questions

1. Who recognises the first authorities (the bootstrap), and how that recognition is itself governed.
2. Representing mandates that come from law directly, with no issuing body online yet.
3. Whether a network may accept mandates from authorities outside its jurisdiction (cross-border recognition).

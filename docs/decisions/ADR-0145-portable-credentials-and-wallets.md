# ADR-0145 — Portable credentials and wallets: the person chooses where their records live

**Status:** Proposed
**Date:** 2026-11-26
**Related:** ADR-0127 (personal data = grant + consent), ADR-0135 (interactive fulfilment), ADR-0137, ADR-0139 (services on
a network), ADR-0140 (listings), ADR-0143 (the Networks app), ADR-0144 (participation credentials). Prompted by *Building
the Networked State: A Playbook* (step 6 and "what to avoid").

## The problem

- **Credentials live in the network.** A person's certificates — a worker registration, a platform's work certificate, an
  insurance enrolment — are held by the network and shown in that network's account. They cannot be taken elsewhere.
- **Each network is a gateway.** To see or use their records, a person signs in to each network's own account. That
  recreates, for people, the silos the networks remove for institutions.
- **The format is ours.** Certificates are signed statements in a format only our SDK reads.
- **Sharing is all or nothing.** A person shares a whole certificate; they cannot prove a single fact (or a range) without
  revealing the rest.

The playbook asks for credentials the person can keep in a wallet or with a custodian of their choice, present wherever
they are admissible, and share selectively — with the network's own account as one optional channel.

## Decision

1. **Credentials use an open standard.** Issued records follow the W3C Verifiable Credentials data model, secured so that a
   holder can disclose selected claims (SD-JWT VC as the default; a Data Integrity proof where a whole record is shared).
   Issuers sign with the keys in the commons directory (ADR-0144); status uses the issuer's status list.

2. **Issuance goes to the person's chosen custodian.** An issuer offers a credential; the person's wallet collects it
   (OpenID for Verifiable Credential Issuance). A custodian may be a personal wallet app, a public wallet (for example a
   national document locker), an assisted channel (a service centre acting for the person under a recorded delegation), or
   the network's own account. A person may use more than one.

3. **The network account becomes optional.** It stays as the default custodian and portal, for people with no other
   channel. Nothing — issuance, linking, applying, receiving an offer — requires it.

4. **Presentation is a request the person answers.** A verifier asks for what it needs: which credential types, which
   claims, for what purpose, under what legal basis (OpenID for Verifiable Presentations). The person's wallet shows the
   request, and the person chooses what to disclose. Where the basis is not consent — a statutory duty, a court order — the
   request says so, and the person is told.

5. **No universal identifier travels.** Each relationship uses its own identifier: the pairwise link ids already used
   between a member and a person (ADR-0137) carry over, and a presentation is bound to the holder without revealing an
   identifier the verifier could correlate across others.

6. **Every disclosure leaves a receipt with the person.** Each presentation produces a receipt — who asked, for what, under
   which basis, what was disclosed — kept by the person's custodian and the verifier. The person can see how their
   information has been used.

7. **Paper stays.** A printed certificate keeps its QR code: a compact signed form a verifier checks against the issuer's
   keys and status list.

## What changes on the current build

| Today | After |
|---|---|
| Certificates held by the network, shown in its account | Issued as VCs to the person's custodian(s); the network account is one custodian |
| Our own signed-statement format | W3C VC, SD-JWT VC; the SDK issues and verifies both during migration |
| Applying = choosing certificates in the network account | A presentation request answered from any wallet; selective disclosure |
| Linking only inside the network's link screen | The same link protocol from any wallet that supports it |
| Consent recorded at linking | A receipt for every disclosure, visible to the person |

## Consequences

- A person's records go with them; a network shutting down or a person leaving a channel loses nothing.
- Networks stop being gateways for people, as ADR-0144 stops them being intermediaries for institutions.
- Members verify standard credentials with standard libraries, not only our SDK.
- More moving parts at the edge (wallets, custodians); the network account remains for people who need a default.

## Open questions

1. **Predicate proofs** ("earnings in a range" without the amount): needs a scheme beyond SD-JWT (for example BBS+);
   adopt when mature.
2. **Feature phones and assisted channels:** the delegation record for a service-centre operator acting for a person.
3. **Agents:** an AI assistant presenting on a person's behalf needs delegated, constrained authority — a separate ADR.
4. **Migration:** re-issuing existing network-held certificates as VCs to each person's chosen custodian.

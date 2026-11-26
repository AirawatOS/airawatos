# ADR-0146 — Responses and offers go between the parties: the network keeps receipts, not contents

**Status:** Proposed
**Date:** 2026-11-26
**Related:** ADR-0137 (participants without AirawatOS; pairwise links), ADR-0140 (listings), ADR-0144 (participation
credentials and local verification — decision 7), ADR-0145 (portable credentials; custodians). Slice 3 of ADR-0144.

## The problem

Under ADR-0140 a person's response to a listing — their name, the certificates they chose, their mobile number — is
stored in the network, and so is every offer and its outcome. The network operator can read who applied for what, with
whom, and what was offered. That makes the network the intermediary ADR-0144 says it should not be, and it means a
person's applications live wherever the network is, not where the person keeps their records (ADR-0145).

## Decision

1. **The person answers through their custodian.** Responding to a listing is a presentation (ADR-0145 decision 4): the
   listing names what its lister may receive (the certificate types the lister's role *uses*, from the network policy),
   and the person's custodian — the network's own account by default, or a wallet — shows the request, and the person
   chooses what to share. The listing's stable respond link opens the person's default custodian; a wallet can be offered
   the same request.

2. **The custodian is a party of its own.** A custodian has its own identifier and key in the directory, and its own
   store; the network operator has no access to it, even when both run on the same installation. The network account is
   one such custodian, operated separately from the network's governance records.

3. **A response is delivered to the lister, not stored by the network.** The custodian sends the response directly to
   the lister's response endpoint, registered in its directory entry (an organisation on AirawatOS receives it in its own
   tenant; an outside platform at its own address). The response carries: the listing, the person's pairwise id for this
   lister, what they chose to share (each certificate as its issuer signed it), a reply address at the custodian, an
   expiry — all signed by the custodian. If the lister cannot be reached the custodian retries; nothing waits at the
   network.

4. **The lister checks the response locally** (ADR-0144 decision 5): the custodian's signature (its key in the directory),
   each certificate's issuer signature, issuer participation credential and status, and that the lister's own role may
   use those types. The SDK does this.

5. **Offers go back the same way.** The lister signs the offer — including the credential it will issue on acceptance and
   an expiry (14 days by default) — and sends it to the reply address. The person accepts or declines at their custodian;
   the custodian returns the signed decision to the lister, and on acceptance keeps the credential. An offer to someone
   already linked goes to the custodian that holds that link.

6. **The network keeps a receipt, not the contents.** For each response, offer and decision, the custodian gives the
   network a receipt: the listing, the kind of act, the time, and a digest of the signed message — no names, no
   certificates, no pairwise ids. The network uses receipts to count (responses per listing, offers made and accepted, for
   oversight) and to settle disputes: either party can later show the signed message, and the digest proves it is the
   one that was sent.

7. **Complaints go to the network with what the complainant chooses to show.** A person or lister may file a complaint
   naming a receipt and, at their choice, attach the signed message. The network decides under its rules (ADR-0138's one
   decision applies); it never needed to hold the message before.

8. **Listings, the discovery feed and search providers are unchanged** (ADR-0140 decisions 7–8). The network still caches
   signed listings for discovery.

## What changes on the current build

| Today | After |
|---|---|
| Responses stored in the network (`listing_responses`) | Delivered by the custodian to the lister; the network keeps a receipt |
| Offers and decisions stored in the network (`listing_offers`) | Exchanged between lister and custodian; the network keeps receipts |
| The network's consent screen | The custodian's screen (the network account is one custodian, separate from the network's store) |
| `list_responses` reads the network | Reads the lister's own inbox (hosted: its tenant; outside: its endpoint); SDK verifies each one |
| Response counts computed from stored responses | Counted from receipts |
| `listing.response` event points to a stored record | The delivery is the response itself |

## Stages

1. **Responses.** The custodian (the network account, with its own key and store), delivery to listers (hosted inbox and
   outside endpoint), receipts and counts, SDK verification; the network stops storing new responses.
2. **Offers and decisions** between lister and custodian; the issued credential kept by the custodian.
3. **Migration** of existing responses and offers to their listers and custodians, then deleting them from the network;
   a wallet answering the same request.

## Consequences

- The network operator no longer sees applications or offers — only that they happened.
- Listers need an endpoint that can receive (hosted organisations get one by default; outside platforms already register
  a notification address).
- A dispute needs one of the parties to show the message; the network cannot reconstruct it alone. That is deliberate.

## Open questions

1. **Delivery when the lister is down for long:** how long the custodian retries, and whether the person is told.
2. **Counts as a privacy risk** for small listings (one response reveals that someone applied): a minimum before counts
   are shown to others.
3. **The custodian's operator** — whether the network account custodian should be run by someone other than the network's
   operator, by rule.

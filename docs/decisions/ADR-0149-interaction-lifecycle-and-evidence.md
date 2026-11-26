# ADR-0149 — The interaction lifecycle and evidence: generic primitives, acknowledgements, and a receipt policy

**Status:** Proposed
**Date:** 2026-11-26
**Related:** ADR-0050 (the decision service), ADR-0140 (listings), ADR-0144 (local verification), ADR-0146 (receipts),
ADR-0147 (mandates), ADR-0148 (delegation). Prompted by an external review of the architecture (2026-11-26, §7–§12).

## The problem

- **The lifecycle stops at an offer.** Listings, responses and offers are generic (listing types are governed
  definitions), but there is no commitment, fulfilment, confirmation, withdrawal or contestation, and no rule for which
  message may follow which.
- **Receipts are ambiguous.** A custodian's receipt shows a message was recorded, not that the recipient received or
  accepted it. Receipts carry the listing, the time and the custodian, with no stated purpose, access rule or retention —
  and timestamps and identifiers can reveal patterns even without names.
- **Three kinds of evidence are conflated.** An interaction receipt, the evidence of the transaction itself, and the
  trace of a consequential decision answer different questions and belong with different institutions.
- **Verification checks too little.** Signature, key and role are checked; recipient binding, transaction binding and
  replay are only partly checked (a nonce is sent but not checked against one issued).
- **Credentials do not travel across networks.** Certificate verification is not public, so a verifier outside a network
  cannot check a credential from it without joining.

## Decision

1. **Generic interaction primitives.** Offer, request, response, commitment, fulfilment, confirmation, withdrawal and
   contestation. A domain's interaction (employment, appointments, procurement) is a governed **protocol** in the
   vocabulary that composes them: the message types, the permitted transitions, expiries and duplicate handling. A
   listing type names its protocol. No network gets domain-specific endpoints.

2. **Every message is bound.** Each message carries: its id (unique per sender), the protocol and step, a reference to
   the message it answers, the sender, the **intended recipient**, the nonce of the request it answers (single use,
   issued by the requester), an expiry, and the policy version. Verifiers keep seen ids for the expiry period.

3. **Acknowledgements are signed by whoever acknowledges.** *Dispatched* (the sender), *received* (the recipient, on
   delivery), *accepted or rejected* (the recipient, with a reason code), *fulfilled* (the party that fulfilled). A sender
   can prove delivery only with the recipient's signed *received*.

4. **Three kinds of evidence, three keepers.**

   | Evidence | Answers | Kept by |
   |---|---|---|
   | Interaction receipt | that an exchange happened (for oversight, counts, disputes) | the network, only as its receipt policy allows |
   | Transaction evidence | what was requested, offered, committed, fulfilled | the parties and their custodians |
   | Decision trace | why a consequential decision was made, under whose authority and which rules | the deciding institution, through the decision service (ADR-0050) |

   A digest in a receipt proves integrity only while the evidence it points to exists; it never explains a decision.

5. **A receipt policy per network.** Each network publishes, in its signed policy: why it collects receipts, which fields
   (default: listing, act, coarse time, digest — no participant ids for people), who may read them, how long they are kept
   (default 180 days), and whether counts are shown only above a minimum (default 5). Collection is off unless the policy
   gives a purpose.

6. **The verifier's checklist.** Signature; key binding; mandate (ADR-0147); participation; role; policy version; status
   freshness under the network's risk policy; recipient binding; transaction binding; replay; delegation (ADR-0148). Each
   network sets freshness per act — cached for discovery, recent for applications, live for statutory or high-value acts
   (the *live* flag of ADR-0144 becomes a freshness requirement).

7. **Credentials travel.** Verifying a credential — signature, issuer, mandate, status — needs no membership and is
   public. *Participating* in a network, *verifying* a credential from it, *using* its restricted services and
   *recognising* its participants' authority are separate permissions; a network's policy may recognise another
   network's credentials for named purposes.

## What changes on the current build

| Today | After |
|---|---|
| Listing → response → offer → accept/decline | Governed protocols over generic primitives, with transitions and expiries |
| Nonce sent, not checked; no recipient binding beyond the address | Single-use nonces, recipient and transaction binding, seen-id stores |
| Delivery shown by the sender's receipt | Signed acknowledgements: received, accepted, fulfilled |
| Receipts with no stated purpose or retention | A per-network receipt policy; minimal fields; retention; thresholds |
| Certificate verification only for members | Public verification; cross-network recognition in policy |

## Acceptance tests

- An insurer outside the labour network verifies a worker registration and accepts it for its own purpose.
- A replayed response or acceptance is rejected.
- The network operator cannot read transaction contents or link one person's interactions across listings.
- A rejected statutory application can be reconstructed from its decision trace, contested and remedied (with the
  decision service and the registrar's correction).
- Permitted interactions continue while the network service is down, within the freshness policy.

## Open questions

1. A standard protocol notation (state machines in the vocabulary) and its compatibility rules across versions.
2. Where dispute evidence goes when both parties have lost it.
3. Aggregate oversight without receipts (for example counts reported by parties under a signed attestation).

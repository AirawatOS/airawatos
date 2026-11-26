# ADR-0144 — Participation credentials and local verification: the network is not the intermediary

**Status:** Proposed
**Date:** 2026-11-26 (amended the same day: keys — the organisation's own key-set address as the source, the directory's
signed snapshot with key history, rotation rules)
**Related:** ADR-0116 (membership), ADR-0137 (participants without AirawatOS), ADR-0138 (roles and capabilities; the one
decision), ADR-0140 (listings), ADR-0141 (the commons network), ADR-0143 (the Networks app), DEBT-B182 (scope and validity
of grants). Prompted by *Building the Networked State: A Playbook* (steps 3, 4 and "what to avoid").

## The problem

Today the network sits in the middle of every interaction:

- **Every check is a live call.** Before a member issues, asks for or uses anything, a service asks the network the one
  question of ADR-0138 (`/v1/participants/authorize`). If the network is slow or down, every member stops.
- **The network sees every transaction.** Responses to listings, offers and their outcomes are stored in the network
  (ADR-0140), so the network operator can observe who applied for what, from whom.
- **An organisation's identity is per network.** An organisation outside AirawatOS registers its keys again on each network
  it joins (ADR-0137).

The playbook says the opposite: the network sets the conditions for interaction; it need not be the intermediary for each
one. Participants should be able to check membership and roles themselves, and the network should see what it needs to
govern — not every transaction.

## Decision

1. **An organisation's identity is established once, in the trust layer.** Each organisation has one entry in the commons
   directory (ADR-0141): an identifier, the domains it proved it controls, and its keys. Networks refer to that entry;
   joining a second network never re-registers keys. Keys are kept as follows (see *Keys and rotation* below):
   - **The organisation is the source.** It publishes its public keys at a key-set address on a domain it controls
     (`/.well-known/jwks.json`), each key with an id and the time it becomes valid, and adds and retires keys when it
     decides — never by filing a request.
   - **The directory publishes a signed snapshot.** It reads that address on a schedule and publishes, signed, the binding
     *this organisation — this domain — this key-set address — these keys*, with **every key's validity window, retired keys
     included**, so records signed before a rotation still verify.
   - **Verifiers use the snapshot**, cached, and fall back to the organisation's own address only for a key they have not
     yet seen.

2. **Membership is a signed credential.** When a network approves or changes a membership, the network's governing
   authority issues a **participation credential** to the member: the network, the member's identifier, its roles, any
   scope (jurisdiction, area, programme), and its validity period. It is short-lived (for example 30 days) and renewed
   automatically while the membership stands. It is signed with the network's key, which is itself in the directory.

3. **A network publishes its policy.** The roles and what each may provide and use (ADR-0138) are published as a signed,
   versioned **network policy**. A participation credential names the roles; the policy says what they allow. Anyone holding
   both can answer the one question without asking the network.

4. **Revocation and suspension are published, not asked.** Each network publishes a signed **status list** for the
   credentials it issued. A suspended or removed member's credential is marked at once; verifiers fetch the list on a short
   schedule and cache it.

5. **Verification is local by default.** A member receiving a signed act from another member — a certificate, a listing,
   an offer — checks: the act's signature (issuer's keys from the directory); the issuer's participation credential (signed
   by the network); its status (the cached status list); and that the network policy lets that role do that act. No call to
   the network. The SDK does all four.

6. **Live authorisation where the risk requires it.** A network may mark a capability *live* in its policy — for example a
   statutory decision, or an act above a value. For those, the verifier also asks the network's one decision at the time of
   the act. Everything else is checked locally.

7. **Interactions go between the parties.** A response to a listing goes to the lister (its endpoint, or the person's
   chosen custodian — ADR-0145), not into the network. An offer goes from the lister to the person. The network keeps what
   governance needs: memberships, policies, status lists, published listings for discovery, complaints and disputes — and
   counts, not contents, for oversight.

## Keys and rotation

- **Overlap.** A new key is published beside the old one for an overlap period (for example 7 days) before the
  organisation starts signing with it, so every verifier's cache has it in time.
- **Retirement.** A retired key stays valid for verifying what was signed before its end date; the directory keeps it.
- **Compromise.** An organisation (or the directory, on evidence) marks a key compromised **from a stated time**: records
  signed with it before that time still verify; records signed after it fail.
- **Unexpected changes are held.** A key that appears without the overlap, or a key set whose domain proof no longer
  passes, is not trusted at once: the directory holds it and asks the organisation to confirm through its registered
  contact. A breached website alone cannot swap an organisation's keys.
- **Organisations hosted on AirawatOS** keep their private keys in the platform's secret store (never readable by
  services or operators' staff), publish their key set the same way, and rotate on a schedule the operator runs; the
  organisation can rotate at any time.
- **The network's own keys** (participation credentials, policies, status lists) follow the same rules, in the same
  directory.

## What changes on the current build

| Today | After |
|---|---|
| `/v1/participants/authorize` on every act | Local check by default; live only for capabilities the policy marks live |
| Membership = a record in the network's store | + a signed participation credential issued to the member, renewed while it stands |
| Role definitions read from the network's store | + a signed, versioned network policy |
| Suspension known only to the network | A signed status list every verifier can fetch |
| Listing responses and offers stored in the network | Sent to the lister and to the person's custodian; the network keeps discovery and governance records |
| Outside participants register keys per network | One directory entry with a key-set address; networks refer to it |
| Current keys only; no rotation rules | Key history with validity windows; overlap, retirement, compromise-from-a-time; unexpected changes held |
| Hosted organisations' keys held by the platform, no rotation | In the platform's secret store, published like everyone's, rotated on a schedule |

## Consequences

- A member keeps working when the network is briefly unavailable; only *live* capabilities need it.
- The network operator no longer sees each application, offer or decision between members.
- Suspension still takes effect quickly: as fast as verifiers refresh the status list (a policy setting per network).
- Members and verifiers carry more logic — kept in the SDK and the specification, so it is written once.

## Open questions

1. **Format.** W3C Verifiable Credentials with a bitstring status list is the default candidate; to settle with ADR-0145.
2. **Refresh interval.** How stale a status list may be, per network and per capability.
3. **Cross-network recognition.** Whether one network may accept another's participation credentials (the playbook's step
   8) — a recognition rule in the accepting network's policy is the likely shape.
4. **Migration.** Moving existing listing responses and offers out of the network to the parties.
5. **Snapshot interval and overlap period** — defaults for the directory's reading schedule and the rotation overlap.
6. **Recovery** — how an organisation that lost every private key proves itself again (the domain proof plus the
   registered contact, decided by the steward).

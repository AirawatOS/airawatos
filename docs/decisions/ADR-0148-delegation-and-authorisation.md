# ADR-0148 — Delegation and authorisation: proof that a person authorised what was done in their name

**Status:** Proposed
**Date:** 2026-11-26
**Related:** ADR-0127 (personal data = grant + consent), ADR-0145 (portable credentials; custodians), ADR-0146 (responses
and offers between the parties), ADR-0147 (mandates), ADR-0149 (interactions and evidence). Prompted by an external
review of the architecture (2026-11-26, §5, §6).

## The problem

A response or decision delivered by a custodian is signed by the custodian. That proves the custodian sent it. It does
not prove the person authorised it. The gap is small for applying to a job and large for accepting an offer, buying
insurance, taking credit or authorising a payment. The architecture also uses *wallet*, *custodian* and *agent*
interchangeably, and makes a custodian part of every interaction.

## Decision

1. **Separate roles.** Holder (the person who holds and presents credentials), wallet (software that manages credentials
   and proofs), custodian (an entity entrusted to store information for someone), agent (an entity authorised to act for
   someone), issuer, verifier, relying party. One provider may play several roles; none implies another.

2. **The custodian is optional.** The primitive is a person able to hold credentials and authorise acts. A wallet on the
   person's own device, with a key only the person controls, presents directly; a custodian is one way to realise the
   capability, not a required hop.

3. **A delegation record.** When a person lets an agent or custodian act for them, the delegation states: the principal,
   the agent, the permitted acts (verbs on governed types), the purpose, limits (value, count, counterparties), the
   validity period, and how it is revoked. It is signed by the person's holder key, or — for a person without one —
   by the institution that authenticated them, recording how (for example an assisted-channel operator under its own
   mandate, ADR-0147). Delegations have a status list.

4. **Per-act authorisation where the risk requires it.** A network's policy marks which acts need the person's own
   approval of *that act* (accepting an offer, consenting to share, paying). For those, the message carries an
   authorisation bound to it: the holder key's signature over the message digest, or the custodian's signed record of the
   person's authentication for that act (method, time, session), under a delegation that allows it. Other acts may rely
   on the delegation alone.

5. **The verifier checks the chain.** Agent's signature → delegation from the principal (valid, unrevoked, covering this
   act and within its limits) → per-act authorisation where the policy requires it. The SDK does this, as it does
   participation and mandates.

6. **Agents, including AI agents, use the same primitive.** An AI assistant acting for a person is an agent with a
   delegation; nothing more privileged.

## What changes on the current build

| Today | After |
|---|---|
| The custodian signs; the person's approval is implicit | A delegation from the person, and per-act authorisation for consequential acts |
| A custodian on every path | Optional; a device wallet presents with the person's own key |
| "Wallet", "custodian" used interchangeably | Holder, wallet, custodian, agent as separate roles |

**First build on staging:** the network account records each authorised act (Aadhaar OTP session, time, act digest) and
signs it as a per-act authorisation; Pocket Wallet gets a holder key in the person's browser, used to sign their
acceptance of an offer; offers to people who answered from another wallet then work, since the acceptance is provably
theirs.

## Acceptance tests

- A recognised custodian **cannot** accept an offer without the person's authorisation of that offer.
- A revoked delegation is rejected within the revocation window.
- A person using a device wallet completes the application and offer lifecycle with no custodian involved.

## Open questions

1. Holder keys on feature phones and in assisted channels.
2. Recovering a lost holder key without letting a custodian impersonate the person.
3. Limits that need context the verifier lacks (for example a monthly spending cap across counterparties).

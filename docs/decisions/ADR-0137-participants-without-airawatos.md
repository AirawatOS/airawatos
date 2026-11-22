# ADR-0137 — Participants without AirawatOS

**Status:** Proposed
**Date:** 2026-11-22
**Related:** ADR-0084 (cross-installation trust handshake), ADR-0116 (tenant-free networks, hosted participants),
ADR-0128 (federation), ADR-0129 (organisations spawn networks; Decision 11, finding and joining), ADR-0135 (external
participants, interactive fulfilment — this ADR amends its Mode B), ADR-0136 (tenant members and network accounts)

## The problem

Until now a participant on a network was assumed to run on AirawatOS, in one of two ways:

| Participant runs | Its identity comes from | Its private key lives | Joining adds |
|---|---|---|---|
| As a tenant on the network's installation | that installation's identity service | that installation's key store — the platform signs for it | only the membership record |
| On its own AirawatOS installation | its own installation | its own installation | trust in its issuer, on approval (ADR-0084) |

Most organisations that should join a public network — a ride-hailing company, a bank, a hospital chain — run their own
systems and will not install AirawatOS to take part. For them there was no path. ADR-0135 Mode B says such a
participant calls the network from its servers with an SDK, but not where its identity and keys come from. In practice
that meant a login we created for it in our identity service: a hosted tenant in disguise, with the network holding its
signing keys.

## Decision

1. **A third kind of participant: one with its own keys and no AirawatOS.** It registers on the network's own pages,
   keeps its private key on its own servers, and gives the network only its public key. The network never holds its
   private key and never signs on its behalf.

2. **Registration on the network's portal**, reached from the network's public address (ADR-0129 Decision 11:
   "No AirawatOS? Register your organisation"). The organisation gives:
   - its name, legal identifier (CIN or GSTIN) and a contact for the network's admin;
   - **its id on the network**, which becomes its client id;
   - **its site** (https), where it proves control;
   - **its public keys (Ed25519)**: preferably a **key-set address on its site**, which the network re-reads, so keys are
     rotated without coming back; or a pasted public key set;
   - **its notification address** and **return addresses** (where members come back after linking), all on its site;
   - the participant type it joins as, and an invitation if the network is by invitation.

   Registration returns a **registration id** — the registrant's handle, shown once, stored only as a hash — and a
   **verification code**.

3. **Proving control of the site.** The organisation publishes the code at `<site>/.well-known/aos-network.txt`. Until
   the network reads it there, the registration is *unverified* and cannot be approved. The network fetches only public
   https addresses (never private, loopback or link-local ones).

4. **Approval is the network admin's**, in the same Membership queue as every other member, showing the verified site
   and legal identifier. Join modes (ADR-0129 Decision 11) apply, except that a registration from outside always
   waits for the admin, even on an open network.

5. **Signing in with its own key.** The SDK uses OAuth client credentials with a **private-key JWT** (RFC 7523): it
   signs a short assertion (iss = sub = client id, aud = the token endpoint, expiry within 5 minutes, a one-time jti)
   and exchanges it at the network's token endpoint for a short-lived access token. The token endpoint accepts only
   assertions signed by a key the participant registered, and only while its membership is approved. There is no
   shared secret and no password.

6. **Its certificates are signed by it.** The participant signs each credential statement (for example a work
   certificate) with its own key. The network authority checks the signature against the participant's registered keys,
   that it is an approved member, and that the credential type is governed and one it may issue; only then does the
   credential reach the person's account. Each credential records the participant's signature, so anyone can verify it
   against the participant's published keys. A new certificate from the same participant to the same person supersedes
   the previous one.

7. **Events are signed by the network.** Events to the participant's notification address carry an Ed25519
   signature by the network runtime's key and the key id; the network publishes its keys at a fixed address. The
   participant stores no secret to check them.

8. **What the participant may do is unchanged.** With the access token it uses the same participant API as a hosted
   participant (ADR-0135, ADR-0136 linking): sealed duplicate-check tokens, link requests, link status. Return
   addresses must be ones it registered.

9. **The portal account for the participant's people.** The registration id is the registrant's only handle until
   the participant portal exists; then the organisation's admin gets a portal sign-in on the network's installation,
   the hosted-participant login of ADR-0116, never a tenant.

10. **Hosted tenants remain** for organisations that want the network's operator to run things for them. This ADR does
    not change them.

## Consequences

- A participant can join a network without installing anything but the SDK, and without the network holding its keys.
- Its credentials are its own signatures, so liability for what a certificate says stays with the issuer.
- Key rotation is the participant's own act: publish a new key in its key set, then retire the old one.
- The network depends on fetching the participant's site; if the site is down, new tokens and certificate checks fail
  until it returns (cached keys bridge short outages).
- The SDK needs an Ed25519 library on the participant's servers.

## Open questions

1. **Stronger organisation checks.** Legal identifiers are shown to the admin, not verified against the registries
   (MCA, GSTN); whether the network should check them, and how.
2. **Revoking a key at once.** Removing a key from the key set takes effect within the cache period (5 minutes); a
   participant may need an immediate "revoke this key" action in the portal.
3. **Mutual TLS or request signing** on top of the access token, for networks that need it.
4. **The participant portal**: what the participant's admin manages there (endpoints, keys, members) beyond what the
   key-set address already allows.

# ADR-0136 — Tenant members and network accounts

**Status:** Proposed
**Date:** 2026-11-20 · **Updated:** 2026-11-21 (tenant home page, registration methods, duplicate prevention, linking)
**Related:** ADR-0068 (pluggable identity, assurance tiers), ADR-0112 (embed SDK, citizen identity), ADR-0117/0118/0119
(credential and services network), ADR-0124 (service identities), ADR-0125 (consent), ADR-0129 (organisations spawn
networks), ADR-0135 (external participants, interactive fulfilment); DEBT-B182 (capability and grant model)

## The problem

Every tenant has people who are not its staff: a ride-hailing company has drivers and customers, a city has citizens, a
hospital has patients. Each tenant needs to register them, let them sign in and give them roles. Today the platform has
one shared "citizen" sign-in, so a tenant cannot shape this for its own people, and every demo builds its own page.

The same people also need an account that is **theirs**, not any one tenant's. A driver's work certificates come from
several platforms, their registration from a government registry and their benefits from schemes. Those must sit in
one wallet the person carries from tenant to tenant, without filling in and proving the same facts again each time.

## Three kinds of role

| | Staff roles | Member roles | Network roles |
|---|---|---|---|
| **Who** | People who run the tenant | The tenant's own users | Parties on a network |
| **Example** | Ola's admin, operations staff | Ola's partners and customers | The driver as *account holder*; Ola as *issuer*; the registry as *service provider*; the ministry as *governor* |
| **Belongs to** | The tenant | The tenant | The network |
| **Set up by** | Tenant admin | Tenant admin | Network governor |

## Decision

1. **Every tenant gets a home page, member sign-in and member registration.** One generic page per tenant, shown with
   the tenant's name, logo and colours. **Sign in** opens the tenant's sign-in page; **Register** lists the member roles
   the tenant admin has opened (for example *partner*, *customer*) and runs the registration the admin configured for
   that role (below). After sign-in the member sees a home for their role, with sections the admin turns on.

2. **A person's network account and wallet belong to the person.** No single tenant configures them. The network
   governor sets the rules: who may hold an account, what registration needs, which credential types exist, the
   consent rules, and which tenants may **provide** accounts and wallets (for example the ministry for a livelihood
   network, or a wallet such as DigiLocker).

3. **Members link to networks; tenants never hold the network account.** The tenant admin chooses, per member role,
   which networks the role may link to. Only networks the tenant has **joined** can be chosen. Linking happens on the
   network's screens; the tenant gets back a **link id that is unique to that tenant**, never the person's network
   account id, so two tenants cannot match up the same person.

4. **Two separate grants from the governor.** A tenant may be an **issuer** (it signs facts it is the authority for:
   "works with Ola since…") and, separately, an **identity attester** (the network accepts its identity facts — name,
   date of birth, how identity was checked — to set up a network account, at the assurance level the governor allows,
   ADR-0068). A tenant that checked identity with Aadhaar eKYC may qualify; one that checked only a mobile number may
   not. Grants are requested by the tenant admin and given by the governor (DEBT-B182).

5. **Who draws which screen.** The tenant draws its own pages: home, sign-in, registration, member home. The network
   draws the person's network steps: network sign-in or registration, consent, sensitive input (Aadhaar number, OTP)
   and the wallet. These run on the network's pages, never inside the tenant's page (amends ADR-0135).

## Registration methods

The tenant admin builds each role's registration from these steps.

| Step | Options | What it proves |
|---|---|---|
| **Contact** | Mobile OTP, email OTP | The person controls this phone or email — not who they are |
| **Identity** | Aadhaar eKYC, DigiLocker, another identity provider | Who the person is, and one account per person (below) |
| **Documents** | Upload listed document types, reviewed by a staff role the admin names | Facts the tenant needs (licence, police verification…) |
| **Approval** | Automatic, or review by a staff role | That the tenant accepts the member |
| **Invitation** | The admin pre-loads a list; only listed people can register | Membership the tenant already decided |
| **Bring a credential** | Sign in to a network and share a credential instead of uploading | Facts already signed by someone the tenant trusts |

The admin also sets each role's profile fields and what the tenant issues on approval (for example a *partner
certificate*).

## Preventing duplicate accounts

**Within a tenant.** The tenant must not store Aadhaar numbers. It uses the identity provider's **per-tenant token**
instead (UIDAI issues a token per requesting entity; DigiLocker and other providers give a per-tenant subject id).

**Within a network.** A tenant's token cannot be used, because it differs per tenant, and a plain hash of an Aadhaar
number is no protection: there are only about 10¹¹ numbers, so a hash can be reversed by trying them all, and the same
hash would let tenants match up people. Instead:

- **Sealed duplicate token (preferred).** During its own identity check the tenant holds the number for that one call.
  It asks the network for a token: the network computes a keyed hash with a secret only the network holds, and
  encrypts the result to itself with fresh randomness. The tenant receives an opaque blob that it cannot reverse and
  that differs every time, and places it in the certificate. At network registration the network opens it and checks
  for duplicates — no Aadhaar entry, no OTP.
- **Fallback.** Without a sealed token, the network's account provider does one identity check of its own at network
  registration (for example one Aadhaar OTP).

## Linking a member to a network

1. After registration the member home shows **"Link to \<network\>"**, for the networks configured for that role.
2. The tenant prepares a certificate, signed with its network participant key, and attaches it to a **link request**.
   It is not yet issued to anyone: the network does not know who the person is.
3. The network's screen opens:
   - **has a network account** → sign in; the network checks the certificate matches the account;
   - **new** → register; the network takes each field its registration needs from the certificate, if the issuer is a
     trusted identity attester at the required level, and asks only for the rest — often nothing.
   The person consents to linking and to receiving the certificate.
4. The certificate goes to the person's wallet; the tenant receives its link id.
5. Actions configured for that network then run on the network's screens (for example registration with the national
   worker registry, from the certificate).
6. Either side can unlink. The tenant revokes what it issued when the membership ends.

## Worked example — a driver joins Ola

1. On Ola's home page the driver taps **Register**, chooses **Partner**, and completes Ola's partner registration:
   mobile OTP, Aadhaar eKYC, licence and police verification documents, approval by Ola's onboarding team.
2. Ola issues a **partner certificate**: identity facts from its eKYC, a sealed duplicate token, and the engagement.
3. The member home offers **Link to Livelihood network**. On the network's screen the driver signs in, or registers
   with nothing to fill in, and consents. The certificate goes to their wallet.
4. Registration with the national worker registry runs from the certificate; the registry's credential comes back to
   the same wallet.
5. Later the driver registers as a Swiggy partner and links the **same** livelihood account; the network recognises
   them, so no second account is created.

## What each admin configures

**Tenant admin** (every tenant):
- the home page: name, logo, colours, sections;
- member roles, and for each: registration steps, profile fields, approval, what the tenant issues;
- per role, which joined networks it may link to, whether linking is optional or required, and when it is offered;
- requests for network grants (issuer, identity attester, use of a network service).

**Network governor** (once per network):
- who may hold a network account, the fields its registration needs and the assurance level each needs;
- which tenants provide accounts and wallets;
- credential types, consent wording and record rules;
- which tenants hold which grants, at what assurance level.

## Consequences

- Tenants control their own journeys and brand; one generic home page replaces per-tenant demo pages.
- People keep one network account across all tenants, and rarely re-enter or re-prove a fact.
- Duplicate prevention works across tenants without any of them holding Aadhaar numbers or comparable hashes.
- Sensitive steps are drawn in one place, so their wording and handling are governed once.
- New platform work: per-tenant home page and member sign-in; registration methods; member-role configuration; the
  two grants; link requests, pairwise link ids and the sealed duplicate token; network-hosted screens in the SDK.
- The shared "citizen" sign-in of ADR-0112 becomes one case: an account provider's network sign-in.

## Open questions

1. Is a keyed, sealed token of an Aadhaar number allowed under UIDAI's rules on storing Aadhaar numbers, or does it
   need to live in an Aadhaar Data Vault? (legal / UIDAI)
2. Which identity checks give which assurance level, and which levels does each network require for which fields?
3. Can one person's network account be provided by more than one provider (the ministry and a wallet app), and how do
   they stay in step?
4. Can a tenant reuse the network sign-in for its own members when it prefers to?
5. When a member leaves a tenant, what happens to credentials the tenant issued (revoke, mark ended, keep)?

## Not decided here

The technical design of member sign-in (realms, tokens), the grant model itself (DEBT-B182), the token's cryptography
and the SDK's hosted-screen API. These follow in their own ADRs.

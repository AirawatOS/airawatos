# ADR-0136 — Tenant members and network accounts

**Status:** Proposed
**Related:** ADR-0068 (pluggable identity, assurance tiers), ADR-0112 (embed SDK, citizen identity), ADR-0117/0118/0119
(credential and services network), ADR-0124 (service identities), ADR-0125 (consent), ADR-0129 (organisations spawn
networks), ADR-0135 (external participants, interactive fulfilment); DEBT-B182 (capability and grant model)

## The problem

Every tenant has people who are not its staff: a ride-hailing company has drivers, a city has citizens, a hospital has
patients. Each tenant needs to register them, let them sign in and give them roles. Today the platform has one shared
"citizen" sign-in, so a tenant cannot shape this for its own people.

The same people also need an account that is **theirs**, not any one tenant's. A driver's work certificates come from
several platforms, their registration from a government registry and their benefits from schemes. Those must sit in
one wallet the person carries from tenant to tenant.

These two needs got mixed up: is the driver's account Ola's or the network's? This ADR separates them.

## Three kinds of role

| | Staff roles | Member roles | Network roles |
|---|---|---|---|
| **Who** | People who run the tenant | The tenant's own users | Parties on a network |
| **Example** | Ola's admin, operations staff | Ola's drivers and delivery partners | The driver as *account holder*; Ola as *issuer*; the registry as *service provider*; the ministry as *governor* |
| **Belongs to** | The tenant | The tenant | The network |
| **Set up by** | Tenant admin | Tenant admin | Network governor |

## Decision

1. **Member identity is a core tenant capability.** Every tenant can define member roles (for example *driver*,
   *delivery partner*). For each role, the tenant admin sets how members register, how they sign in, what identity
   check they need and what the tenant issues to them. The tenant runs these screens under its own brand. The platform
   hosts them as that tenant's, not as a shared login.

2. **A person's network account and wallet belong to the person.** No single tenant configures them. The network
   governor sets the rules: who may hold an account, which credential types exist, the consent rules, and which tenants
   may **provide** accounts and wallets. An account provider is an ordinary tenant (the ministry for a livelihood
   network, or a wallet such as DigiLocker) that the governor has appointed. Its admin configures registration and
   sign-in for network accounts, within the network's rules.

3. **Members link to their network account; tenants never hold it.** A tenant asks a member to link their network
   account at a point the tenant chooses: signing in if they have one, creating one if not. After linking, the tenant
   can send credentials to the account and request proofs, each with the person's consent. The tenant never sees the
   network account's password and cannot read the wallet except what the person shares.

4. **A tenant's network roles are granted by the governor.** For example: *issuer* of work certificates, *verifier* of
   driving licences, *user* of the registry's registration service. A tenant admin requests them; the governor grants
   them (DEBT-B182).

5. **Who draws which screen.** The tenant designs its own member journey (registration, its checks, its dashboard).
   The network draws the screens that belong to the person: network sign-in, consent, anything sensitive the person
   types (Aadhaar number, OTP) and the wallet. These run on the network's own pages, never inside the tenant's page.
   This amends ADR-0135, where the app drew every step of an interactive request: steps carrying consent or sensitive
   input are now drawn by the network, and the app receives only the outcome.

## Worked example — a driver joins Ola

1. The driver registers with **Ola**: Ola's screens, Ola's sign-in (member role *driver*, set up by Ola's admin).
2. **Ola** checks the driver's identity, licence and police verification, as Ola must.
3. Ola's registration is complete. Ola signs a **work certificate**.
4. Ola asks the driver to send it to their **livelihood account**. The driver signs in, or creates an account if new,
   on the network's page. Ola never sees that password.
5. The certificate goes into the driver's wallet (network role: Ola is *issuer*, the driver is *account holder*).
6. With the driver's consent on a network screen, the certificate is used to register on the national worker
   registry or link an existing registration. The registry's credential comes back to the same wallet.
7. Later the driver joins Swiggy: a new **Swiggy** member account, the **same** livelihood account.

## What each admin configures

**Tenant admin** (every tenant):
- member roles, and for each: registration fields, sign-in method, identity check;
- what the tenant issues to members, and when;
- when to ask members to link their network account, and which credentials to send;
- requests for network roles (issuer, verifier, service user).

**Network governor** (once per network):
- who may hold a network account, and the minimum identity check;
- which tenants provide accounts and wallets;
- credential types, consent wording and record rules;
- which tenants hold which network roles.

## Consequences

- Tenants control their own journeys and brand. People keep one account across all of them.
- A person may hold many tenant accounts and one network account per network. The link between them is recorded and
  can be removed by the person.
- Sensitive steps (consent, Aadhaar, OTP) are drawn in one place, so their wording and handling are governed once.
- New platform work: per-tenant member roles and sign-in; account-provider appointment; the link between member and
  network accounts; network-hosted screens in the SDK (sign-in, consent, challenge, wallet).
- The shared "citizen" sign-in of ADR-0112 becomes one case: the account provider's network sign-in.

## Open questions

1. Can one person's network account be provided by more than one provider (for example the ministry and a wallet app),
   and how do they stay in step?
2. Can a tenant's member sign-in reuse the network sign-in (one sign-in for both) when the tenant prefers it?
3. When a member leaves a tenant, what happens to credentials the tenant issued (revoke, mark ended, keep)?
4. Which identity checks may a tenant reuse from another tenant's credential, and who decides?

## Not decided here

The technical design of member sign-in (realms, tokens), the grant model itself (DEBT-B182) and the SDK's hosted-screen
API. These follow in their own ADRs.

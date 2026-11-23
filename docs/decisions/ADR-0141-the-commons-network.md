# ADR-0141 — The commons network: operators, domain owners, component publishers and tenants

**Status:** Proposed
**Date:** 2026-11-23
**Related:** ADR-0038 (the network as standards body), ADR-0094 (component stewardship), ADR-0106 (development and
production governance), ADR-0116 (participants and membership), ADR-0129 (organisations run networks), ADR-0137
(participants without AirawatOS), ADR-0138 (network roles and capabilities).

## The problem

AirawatOS began with one network: Airawat governed it, cities joined it, and "Join" meant joining that network. Since
ADR-0129 every tenant can run its own networks — the Ministry of Labour runs eShram, a city may run one for its water
services — and organisations outside AirawatOS can take part in them. "The network" no longer names one thing, and
three questions have no clear owner:

- **Who may host AirawatOS?** Tenants already choose a host operator when they join, but how an operator becomes one
  that tenants may choose is not defined.
- **Who decides what a record type means?** Schemas, credential types and listing types live in one catalogue, but
  anyone who can publish can publish into any domain.
- **Where do shared things live?** The component marketplace, the governed vocabulary and the directory of
  organisations and keys are shared by every network, yet nothing says who runs them or how one takes part.

## Decision

1. **The commons is a network, run by the Airawat steward.** It is the one network about the platform itself — who may
   host it, define its vocabulary and publish components — not about citizens or services. It uses the same mechanism
   as every network (membership, roles, approval — ADR-0138). It is not a root that other networks hang from: eShram and
   every other network are independent of it and use only its vocabulary and directory.

2. **The commons holds what everyone shares:**
   - the **governed catalogue** — record types, credential types, listing types and interfaces: what makes networks
     interoperable;
   - the **component marketplace** and certification: what makes components reusable by every tenant and network;
   - the **directory** of operators, tenants and their keys: the trust anchor.

3. **Roles on the commons network:**

   | Role | May do |
   |---|---|
   | **Operator** | host tenants — start them, run them, keep their data |
   | **Domain owner** | own the record types in a domain: publish and version them, review requests for new types and fields |
   | **Component publisher** | publish certified components to the marketplace |
   | **Tenant** | use the catalogue, marketplace and directory; run its own networks |
   | **Steward** | run the commons: approve roles, run the catalogue and certification |

4. **Operators.** An organisation that wants to host AirawatOS installs it on its own infrastructure, registers on the
   commons network (its domain and keys, proving the domain is its own), and passes certification — the conformance
   suite run against its installation (security, isolation, the core services). The steward then approves it in the
   Operator role, and it is listed for organisations choosing where to be hosted, with what they need to choose: region,
   where data is kept, support. An operator that fails re-certification or leaves is delisted; its tenants can move.

5. **Tenants choose where they are hosted.** An organisation joining AirawatOS picks an operator from the list; on
   approval its tenant is started on that operator's installation and registered in the directory with its keys. The
   commons itself runs no tenant workloads.

6. **Domain owners.** An organisation claims a domain — a prefix of record types such as `hr`, `health` or `water`, or
   part of one such as `hr.platform_work` — and shows its mandate (the Ministry of Labour for worker records). The steward
   checks the mandate and any overlap and approves it in the Domain owner role for that domain. The domain owner decides
   what is in its domain; the steward makes sure it goes in properly — every published type is versioned and signed by
   the catalogue, so everyone can trust it. Networks and tenants ask for new types through the domain's request process.
   Until a domain has an owner, the steward owns it.

7. **One marketplace.** There is one marketplace, in the commons. A network does not have its own; it may recommend or
   require certified components to its members — a filtered view of the same marketplace.

8. **Networks cross operators.** A network is run by one tenant on one operator, but its members may be tenants on any
   operator or organisations outside AirawatOS. Trust comes from the commons directory and from signed records, not from
   sharing an installation.

9. **Four ways in.** The public entry points are: bring your organisation onto AirawatOS (choose an operator); find a
   network and join it; host AirawatOS (become an operator); own the standards for your sector (become a domain owner) —
   and, for developers, publish components.

## Consequences

- "Join" no longer means one thing; each way in names what is being joined.
- Hosting becomes open to any certified operator, and tenants can choose — and change — where their data is kept.
- Sector bodies own their vocabulary, so the catalogue scales beyond what one steward can judge.
- Existing networks (eShram) are unaffected: they already use the catalogue and directory.

## Open questions

1. **Federation of commons.** Whether several commons (for example per country) can recognise each other's catalogue
   and directory.
2. **Moving a tenant between operators** — the export, transfer and re-keying process.
3. **Operator certification** — the exact suite, how often it re-runs, and who may audit.
4. **Disputed domains** — two bodies claiming the same domain.

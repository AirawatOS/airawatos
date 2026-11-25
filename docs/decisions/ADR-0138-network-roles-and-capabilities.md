# ADR-0138 — Network roles and capabilities

**Status:** Proposed
**Date:** 2026-11-22
**Related:** ADR-0116 (participants and membership), ADR-0118 / ADR-0119 (trusted network platform, the trust plane and
its capability grammar), ADR-0127 (one authority model for services and data), ADR-0129 (organisations run networks),
ADR-0137 (participants without AirawatOS); DEBT-B182 (capability and grant model gaps) — this is the ADR that item
asks for before any change to the network console.

## The problem

Joining a network does not say what a member may do there. A ride-hailing platform on the eShram network may issue work
certificates and ask the eShram registry to register its workers; a scheme provider may not issue work certificates; the
registry is the only one that issues the eShram registration. Today:

- each network lists **participant types** with what each kind *provides* and *consumes*, but **nothing checks those
  lists**, and a member's type is only what it typed when it applied;
- services keep **their own lists** of who may use them (the eShram registry's list of platforms is a file);
- the trust plane has a capability grammar and grants, but capabilities stop at `service.provide` / `service.call`,
  grants have no scope narrower than a whole service, and each service must remember to check (DEBT-B182 a–e).

## Decision

1. **A capability is a verb on a noun, from one side.**
   - The **noun** is a governed schema: a credential type, a record type.
   - The **verb** is what is done with it: *issue* a credential, *request* one, *submit* or *resolve* a case, or a
     governed interface (a request/response or an event).
   - The **side** is **provide** (the member answers the request, issues the credential) or **use** (the member asks,
     receives). Capabilities come in pairs: one member provides *issue eShram registration*, another uses it.
   - In the trust plane's grammar this is `<domain>.<action>:<noun>`, for example `credential.issue:platform_work_certificate`
     and `credential.request:eshram_registration`; for an interface, `service.provide:<interface>` / `service.call:<interface>`.

2. **A network can only name governed nouns and verbs.** A capability that points to a schema or interface that is not in
   the network's governed catalogue is refused when it is defined; govern the noun or verb first (DEBT-B182 c).

3. **Roles bundle capabilities.** Each network defines its roles — the participant types it already has — as a named set
   of capabilities to provide and to use. Roles belong to the network and are defined by its governor.

4. **A member holds one or more roles, and gets their capabilities.** An applicant asks for a role; the network admin
   approves the membership *in that role* (or others) and can change its roles later. A member may hold **several roles**
   at once — a platform aggregator that issues work certificates is often also an employer that posts jobs — and may do
   what **any** of its roles allows: its capabilities are the union of its roles' (see *Amendment 2026-11-25*). What a
   member may do follows from its roles; no service keeps its own list. A network may also give one member an **individual grant** that adds to or narrows its
   role, with a validity window, a scope (an area such as a ward) and a purpose (DEBT-B182 a, b).

5. **Some capabilities need set-up by the providing service.** When a member is given a role that uses a service, the
   service may first have to enrol it — the eShram registry assigns a platform its aggregator and platform ids. The
   service does this when the role is assigned (or on first use) and keeps its own identifiers for the member; it never
   decides *whether* the member may use it — the role does.

6. **One decision.** Every service asks the network the same question before acting: *may this member provide / use
   this capability on this network, now (and here)?* The network answers from the member's role and grants, its
   membership status, and the validity and scope of each grant (DEBT-B182 e). A member that leaves, is suspended or
   loses the role loses the capability at once.

7. **Credentials follow the issuer's role.** A member may issue a credential type only while its role provides it. A
   verifier checks the signature with the issuer's keys and sees whether the issuer still holds the role.

8. **Data access stays on its own path for now.** Installed components reading and writing a tenant's records keep the
   access-grant path; personal data still needs a grant and the person's consent (ADR-0127). Bringing them under one
   model is open (DEBT-B182 d).

9. **Changing roles is governance.** Defining capabilities and roles, and assigning roles, are network-admin acts, recorded
   with who did it and when; a network may require a change request for them.

## Worked examples

**eShram (Ministry of Labour)**

| Role | Provides | Uses |
|---|---|---|
| Platform (Ola, a delivery app) | issue `platform_work_certificate` | request `eshram_registration` |
| Registry (the eShram registry) | issue `eshram_registration` | — |
| Scheme provider | benefit applications | read `eshram_registration` status, with consent |
| Governor (the Ministry) | defines roles, approves members | — |

When the Ministry approves a platform in the *Platform* role, the registry assigns its platform ids, and the platform's
workers can get a UAN from its certificate. A platform that leaves the network can no longer issue certificates or start
registrations; certificates it issued stay verifiable, and verifiers see that it is no longer a member.

**Water complaints (a city)**

| Role | Provides | Uses |
|---|---|---|
| Helpline | — | submit `water.complaint` |
| Ward office | resolve `water.complaint` — scope: its own ward | — |
| Water Department | resolve `water.complaint` — scope: everywhere | — |
| NGO | — | read `water.complaint_statistics` (anonymised) |

## Amendment 2026-11-25 — several roles per member

Holding exactly one role forced a choice that does not match real organisations: on eShram, Ola is a **platform** (it
issues work certificates and links workers) and an **employer** (it posts jobs and makes offers). Splitting it into two
members, or swapping its role, breaks one side.

- A membership carries a **list of roles**. Approving a membership, and changing it later, sets the list; a single role is
  a list of one. Existing memberships with one role are unchanged.
- **The one decision uses the union.** *May this member provide / use this capability?* is answered yes if any of its
  roles provides / uses it. Credentials follow the issuer's roles the same way (decision 7).
- **Grants still narrow or add per member** (decision 4); revoking the membership removes every role at once; removing one
  role removes only what that role alone allowed.
- **Assigning roles stays governance** (decision 9): recorded with who changed the list and when.
- For readers that know only one role, the first role in the list is kept as the member's primary role.

## Consequences

- One place answers "who may do what" for every service on a network; services drop their own lists.
- Applying for a role and approving it is the same act for every network; only the roles differ.
- Existing networks keep working: a network whose roles name no capabilities is checked as before until its governor
  defines them.

## Open questions

1. **Scope types.** Which scopes a network may use (area, programme, category) and how a service declares the scope of a
   request.
2. **Change requests.** Whether role changes on a public network must go through a change request with a second approver.
3. **Data access.** How the access-grant path for components joins this model (DEBT-B182 d).
4. **Interfaces for services without credentials.** The interface catalogue for request/response services (for example a
   benefit application) and how a request names the capability it needs.

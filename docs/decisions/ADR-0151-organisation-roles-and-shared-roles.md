# ADR-0151 — Organisation roles and shared roles: who defines a role, and who decides

**Status:** Proposed
**Date:** 2026-11-27
**Related:** ADR-0048 (role-separated work), ADR-0138 (network roles and capabilities), ADR-0139 amendment (services
belong to their organisation), ADR-0141 (the commons; domain owners), ADR-0143 (the Networks app: vocabulary, roles,
membership), ADR-0147 amendment (a case step under the officer's authority).

## The problem

- **One vocabulary for every role.** The roles a service's steps can be given come only from the network's governed
  role vocabulary (`<domain>.<role>`). A role needed only inside one organisation's own workflow — a volunteer
  coordinator at an NGO, a ward desk officer in one city — must still be agreed for the whole network.
- **The wrong decider.** A new role is requested in Admin → Requests and decided only by the central standards body,
  while record types are now decided by their domain's owner (ADR-0141, ADR-0143). On staging the standards body has no
  person account, so a request cannot be decided at all.
- **No path from where the need arises.** A service builder who needs a role must leave Service Studio, file a request
  in Admin, and wait.
- **Two lists that drift.** Service Studio offers the network's roles; Admin offers only roles registered in the
  organisation (from installed apps, adopted domain packs, and — since 2026-11-27 — saved services). A service could
  assign steps to roles no one in the organisation could be given.
- **Roles carry no permissions.** A role is a name: nothing says which records it may write or which decisions it may
  take, so the only check today is that the officer holds the role a service assigns to the step.

## Decision

1. **Two kinds of role.**

   | | Organisation role | Shared role |
   |---|---|---|
   | Name | `<organisation>.<role>` (e.g. `janaagraha.volunteer-coordinator`) | `<domain>.<role>` (e.g. `urban.revenue-officer`) |
   | Means the same | inside that organisation only | across organisations |
   | Defined by | the organisation's administrators | the domain's owner (ADR-0141) |
   | Available | at once | when the domain owner approves it |
   | May be used in | the organisation's services, member-role reviews, postings, task routing | the same, **and** network policies (ADR-0138), mandates (ADR-0147), certificates and anything another organisation must interpret |

2. **Organisation roles are defined in Org Setup.** A name, a description, and optionally the shared role it
   specialises (*acts as* `urban.revenue-officer` for one ward). They are records in the organisation's own registry,
   effective as soon as they are saved, and visible only to that organisation and its people.

3. **Shared roles are decided by their domain's owner,** through the same request, decide and outcome path as record
   types (ADR-0143 stage 3b; outcomes in the Inbox). The standards body decides only for platform domains and for
   domains that have no owner yet. A request names the domain, the role, what it does, and the record types and
   decisions it is expected to touch.

4. **Service Studio is where the need arises, so it is where roles are added.** A step's role picker lists the
   organisation's roles and the shared roles, and offers *New role…*: **create an organisation role** (administrators,
   immediate) or **request a shared role** (filed with the domain owner). A service may be saved with a requested
   shared role, but not listed on the website or published to a network until the role is approved; in the meantime the
   builder can use an organisation role.

5. **One assignable list.** What Admin and Org Setup offer for posting people is the organisation's roles plus every
   shared role the organisation uses — through an installed app, an adopted domain pack, or a saved service. The same
   list feeds Service Studio, so nothing can be assigned to a step that no one can be posted to.

6. **Roles may carry permissions.** A shared role may carry the domain owner's *recommended* permissions (record types
   it may create or change, decisions it may take); an organisation sets its own permissions for its organisation roles
   and may narrow a shared role's. A case step checks both: the officer holds the step's role, and the role may perform
   the step's effects (ADR-0147 decision 10).

7. **Promotion.** An organisation role that several organisations define the same way may be proposed as a shared role;
   once approved, each organisation can map its role to the shared one without renaming its postings.

## What changes on the current build

| Today | After |
|---|---|
| Service Studio offers only network-governed roles | Organisation roles + shared roles; *New role…* in the step picker |
| New roles requested in Admin, decided by the standards body | Organisation roles created by the organisation; shared roles decided by the domain owner, outcome in the Inbox |
| Admin offers roles registered by apps, packs, saved services | One assignable list: organisation roles + every shared role the organisation uses |
| A role is a name | Optional permissions: recommended by the domain owner, set or narrowed by the organisation |

## Acceptance tests

- An administrator creates `janaagraha.volunteer-coordinator` in Service Studio, assigns a step to it, posts a person to
  it in Org Setup, and that person completes the step — with no request to anyone.
- A request for `urban.tax-inspector` reaches the `urban` domain owner's Inbox; approving it makes it available to every
  organisation; the requester sees the outcome in their Inbox.
- An organisation role cannot be used in a network policy, a mandate or a certificate.
- A service whose step needs a still-pending shared role cannot be listed on the website.
- An officer whose role holds the step's role but lacks permission for the step's effects cannot complete it.

## Open questions

1. Naming collisions: an organisation id that equals a domain name; reserving domain names.
2. Renaming or retiring a role that people are posted to and services use.
3. Whether member roles (ADR-0136) and staff roles share one catalogue.

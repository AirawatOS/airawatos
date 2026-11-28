# ADR-0153 — Organisation and Settings: two administration apps, one place for people and roles

**Status:** Proposed
**Date:** 2026-11-28 (amended the same day: personal settings)
**Related:** ADR-0048 (role-separated work), ADR-0079 (resource metering), ADR-0136 (members), ADR-0151 (organisation
roles and shared roles), ADR-0152 (work allocation, absence and delegation).

## The problem

An organisation's administrator has three apps, and they overlap.

| App | Holds | The question it answers |
|---|---|---|
| Org Setup | units, areas, levels, streams, positions, roles, people, postings, goals | How is the organisation structured, and who works where? |
| Admin | roles by user, roles by role, role requests, app access, usage, storage | Who holds which role, who sees which app, what is used? |
| Settings | personal, components, supply chain, AI model, members, networks | How is the organisation's platform configured? |

- **A role can be given in two ways.** Admin grants a role to a login directly; Org Setup grants it through a posting
  (person × position × unit × area × role). The two disagree: a person granted a role in Admin does not appear among the
  organisation's people or postings, and a role held through a posting is scoped to an area while a direct grant is not.
  On 2026-11-28 Org Setup showed no one holding the roles Janaagraha's property tax service needs, and nothing in either
  app said why.
- **People are kept twice.** Staff are logins in Admin and people in Org Setup, linked only by the "login user" field.
- **Role requests appear in two apps** (Admin → Role requests, and Org Setup → Roles since ADR-0151).
- **Personal settings sit with the organisation's settings**, though they belong to the person — and they duplicate the
  theme and language already in the profile menu of the desktop and the resident home.

## Decision

1. **Two administration apps, by the question asked.**
   - **Organisation** (today's Org Setup) — *who works here and what they may do*: units, areas, levels, streams,
     positions, roles, people, postings, goals, role requests, and which apps each role sees.
   - **Settings** — *how the organisation's platform is set up*: components, supply chain, AI model, members (public
     membership, taking applications), networks, usage and storage.

2. **A person is one record.** Organisation → People shows each person with their login and **everything they hold**:
   roles from postings (with unit and area), roles given directly, roles held on their identity account, and what each
   role acts as (ADR-0151). Creating a person can create their login (as today).

3. **Postings are the normal way to give a role.** A posting carries the position, unit and area, so the scope that
   routes work (ADR-0152) and the record of who works where are the same thing. **A direct grant remains**, for roles
   that have no place in the structure (a developer, an auditor, a temporary charge); it is shown as *given directly*,
   with who gave it and when, and can be turned into a posting.

4. **Roles show their holders and their apps.** Organisation → Roles lists, for each of the organisation's roles and
   each shared role it uses, who holds it (by posting or directly), what registered it (an app, a pack, a service), and
   which apps the role sees.

5. **Admin retires; nothing is lost.** Its *By user* and *By role* become Organisation → People and → Roles; *Role
   requests* is already in Organisation → Roles; *App access* moves to Organisation → Roles; *Usage* and *Storage* move to
   Settings. Admin is marked *deprecated*: hidden from every desktop, its address still working for anyone who kept it.

7. **Personal settings live in the profile menu.** Theme and language are already in the profile menu of the desktop and
   the resident home, for staff and residents alike; Settings → Personal is removed. (My Account, first proposed here, is
   the resident's app and is not on staff desktops.)

6. **No new records.** The same record types (`org.*`, `governance.role`, `governance.role_grant`,
   `platform.member_role`) and the same endpoints serve the new screens; this decision moves screens and settles which
   route is normal.

## Build

1. **Step 1:** Organisation (Org Setup) takes over people and roles — People with logins and every holding (posting,
   direct, identity), direct grants given and withdrawn there; Roles with holders and app access; Admin points to it.
2. **Step 2:** Usage and Storage move to Settings; Settings → Personal is removed (the profile menu has it); Admin is
   marked deprecated.

## What changes on the current build

| Today | After |
|---|---|
| Three apps for administration | Organisation and Settings |
| A role given in Admin is invisible in Org Setup | One list of everything a person holds, by route |
| Postings and direct grants are equal alternatives | Postings are the normal route; direct grants are labelled exceptions |
| Role requests in two places | In Organisation → Roles |
| Personal settings in the organisation's Settings | In the profile menu only |

## Acceptance tests

- A role given directly to a login appears on that person in Organisation → People and is counted under the role in
  Organisation → Roles, marked *given directly*.
- A role held through a posting shows its unit and area; ending the posting removes it from both lists.
- An administrator can do everything Admin did — grant and withdraw a role, see a role's holders, set which roles see an
  app, decide or file a role request, see usage and storage — without opening Admin.

## Open questions

1. Whether a direct grant should require an end date by default (most are temporary).
2. Naming: keep "Org Setup" or rename to "Organisation".

# ADR-0139 — Services on a network

**Status:** Proposed
**Date:** 2026-11-22 (amended 2026-11-27: a service belongs to its organisation; publishing it to a network is a
separate act, and only that act is governed by the network)
**Related:** ADR-0067 (service offerings), ADR-0049 (credentials in the person's wallet), ADR-0127 (one authority model
for services and data), ADR-0129 (organisations run networks), ADR-0137 (participants without AirawatOS), ADR-0138
(network roles and capabilities).

## The problem

A network links people's records — a worker's eShram registration, the work certificates their platforms issued. What
those records are *for* is the services a person can then get: insurance, jobs, welfare benefits. Today:

- an agency publishes a **service offering** to the whole directory; nothing ties it to a network, so the network's
  members and roles play no part in who may offer it or what it may ask for;
- an offering lists the credential **types** it requires, but not **which facts** from them the provider sees, so a
  person cannot be told what they are sharing;
- eligibility is a free reference (`eligibility_ref`) that nothing evaluates, so a person finds out they do not qualify
  only after applying;
- a person has no place of their own on the network to see what they can apply for: they reach the network only through
  a partner's screen.

## Decision

1. **A service can be offered on a network.** A provider that is a member of a network may offer one of its services
   there. The offering then also carries:
   - **who can apply** — simple, checkable rules over the person's credentials on the network (holds an active eShram
     registration; aged between 18 and 70, from a date of birth a credential carries);
   - **what the provider sees** — for each credential, the exact facts (claims) sent to the provider;
   - **how it is decided** — by rules at once, by the provider's staff (a case in its Task Inbox), or by the person
     choosing from options the provider returns (a job list);
   - **what the person gets** — the credential the provider issues at the end.

2. **The role decides who may offer what.** Offering a service is checked with the one decision of ADR-0138: the
   provider's role must **provide** the credential the service issues and **use** every credential the service asks to
   see. A member without that role cannot offer the service; a member that loses the role has its services hidden at
   once.

3. **The network checks eligibility, not the provider.** The network evaluates the rules against the person's own
   credentials. A rule may read a fact the provider never sees — the network checks the age; the provider learns only
   that the person qualifies. Facts used only for eligibility are not sent.

4. **The person sees services in their own account on the network.** The account — opened by the person themselves, with
   an OTP to the mobile on it — lists the services offered on the network: those they qualify for, and the others with
   the reason they do not (yet).

5. **Applying is consent to a named list of facts.** The application screen is the network's own. It shows exactly which
   facts go to which provider and what comes back; only those facts are sent, once, for this application. The person may
   also choose, per linked partner, to tell that partner that the service is done — the partner learns only that, through
   a signed event, never the facts or the result.

6. **Results are credentials.** What a service gives — an insurance enrolment, a benefit sanction, a job application — is
   a credential the provider issues into the person's account, signed by the provider and checkable by anyone the person
   shows it to. Reviews use the provider's own service workflow (case → Task Inbox); a rules decision needs none.

7. **One application at a time per service.** A person who already holds a current credential from the service is told so
   instead of applying again.

8. **Services are discoverable outside the network.** A member whose role **uses** `network.service_offering` may read the
   network's services in its **discovery feed** (ADR-0140) — the same feed that carries listings — and offer them in its
   own search, app or portal. Each service travels as the full record its provider published, with the provider's steward
   signature, which anyone can check against the provider's key in the network directory. The feed says when a service is
   offered, changed or withdrawn on the network, and members get a signed `service.changed` event. A search provider can
   show who can apply; only the network decides whether a person qualifies — it alone reads their certificates — and
   people apply on the network's own screen (each service has a stable link to it).

## Amendment (2026-11-27): a service belongs to its organisation; publishing to a network is separate

**The problem found.** A service existed only as an entry in the network's service directory: the Service Studio's one
action wrote there, and the organisation's own website, its people's "My Services" and the apply and status flows all
read it back from there. So the network's rules — membership, role, jurisdiction, the ban on development organisations —
governed whether an organisation could have a service at all, even on its own site. An NGO with no jurisdiction, or a
development organisation, could not create one.

**Decision.**

1. **A service is the organisation's own record,** kept in its own registry (the governed type
   `network.service_offering`). Creating, testing, listing it on the organisation's website and receiving applications
   need only the organisation's own administrators — no network membership, role or jurisdiction. Development
   organisations build services the same way.
2. **The organisation's site and its people's views read its own records.** Withdrawing a service from a network does not
   remove it from the organisation's site.
3. **Publishing to a network is a separate act, per network.** The organisation sends the network a copy signed with its
   own key (ADR-0147 decision 6). The network's rules apply here and only here: the organisation is a member; its role
   provides what the service issues and uses what it asks to see (decision 2); jurisdiction or a mandate where the
   network's policy requires it (ADR-0147); and a production network refuses development organisations (ADR-0106),
   which may publish to a sandbox network instead.
4. **The network keeps the signed copy for discovery** — its directory and the discovery feed (decision 8) — as it does
   listings (ADR-0140). A change is a new signed version, republished.
5. **Applying.** On the organisation's own site, the application goes to the organisation. Through a network, the person
   answers from their custodian and the application is delivered to the organisation (ADR-0146); eligibility rules are
   evaluated where the person's records are (their custodian), so decision 3's privacy property is kept without the
   network reading the person's certificates.
6. **Existing services move.** Each service now held only in the network's directory is copied into its organisation's
   registry as the source; the network keeps it as that organisation's published copy.

**Stages.**

1. The Service Studio saves to the organisation's registry (*Save* and *List on our website*) and has a separate *Publish
   to a network* step; the organisation's site reads its own records.
2. Publishing sends a copy signed with the organisation's key; the network checks the role, jurisdiction and environment
   then, and caches the copy; the directory and feed serve the copies.
3. The apply and status flows read the organisation's record; existing services are moved.

## Worked example — accident cover on the eShram network

| | |
|---|---|
| Provider | ESIC, a member in the *Service provider* role: provides `insurance_enrolled`, uses `eshram_registration` and `platform_work_certificate` |
| Who can apply | holds an active `eshram_registration`; aged 18–70 (date of birth from a `platform_work_certificate`) |
| Provider sees | from `eshram_registration`: UAN, full name |
| Decided | by rules, at once |
| Person gets | `insurance_enrolled` (scheme, cover, policy number, enrolled on), issued by ESIC |
| Partners told | if the worker chooses: "service completed: accident cover" |

The worker linked through a platform opens their eShram account, sees *Accident cover — you qualify*, sees that ESIC will
receive their UAN and name (and that the network checked their age itself), agrees, and receives the policy as a
credential. The platform, if the worker chose to tell it, receives a signed `service.completed` event.

## Consequences

- A network becomes the place where a person's linked records turn into services, without each provider building its own
  sign-up, eligibility check or consent screen.
- Providers see less: only the facts named for the service, and never facts used just to decide eligibility.
- Existing directory offerings are unchanged; offering one on a network is an addition.

## Open questions

1. **Rule language.** The first rules are "holds", "fact equals" and "age between". Income, location and category rules,
   and who governs the rule vocabulary, are open.
2. **Choice services.** How a provider returns options (a job list) and how the person's choice becomes an application to
   a third party (the employer).
3. **Partner apps.** Whether partners may show a person's services inside their own app through the SDK, and what consent
   that needs.
4. **Withdrawal and renewal.** How a person withdraws an application or renews a time-limited benefit.

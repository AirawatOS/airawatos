# ADR-0143 — The Networks app: one place to run, and take part in, networks

**Status:** Proposed
**Date:** 2026-11-25
**Related:** ADR-0116 (membership), ADR-0129 (organisations run networks), ADR-0137 (participants without AirawatOS),
ADR-0138 (roles and capabilities; amendment 2026-11-25: several roles per member), ADR-0139 (services on a network),
ADR-0140 (listings), ADR-0141 (the commons network).

## The problem

What an organisation does with networks is spread over places chosen by *who it is*, not *what it is doing*:
Settings → Networks for members (join, services, listings), the Network Admin app for the organisation running a network
(profile, roles, membership, publications), public network pages for the public and for organisations outside
AirawatOS, and the SDK for those outside platforms. Daily work — posting jobs, reading applications, offering services —
is buried in Settings; an organisation that runs one network and belongs to another switches apps; nothing shows what
needs attention; and nothing tells a member what its roles let it do.

## Decision

1. **One Networks app** for every organisation on AirawatOS, for running networks and for taking part in them. Settings
   keeps only organisation-wide configuration and links to it; the Network Admin app is folded into it. The public
   network pages stay — they serve the public, people (their own account on a network) and organisations outside
   AirawatOS.

2. **Home** lists the networks the organisation runs and belongs to — each with its roles, status and what needs
   attention — and offers *Find a network* (search, join by address or invitation) and *Start a network*.

3. **Inside a network, the tabs follow the organisation's relationship and roles**, never the network's subject:

   | Tab | Shown when | What it does |
   |---|---|---|
   | Overview | always | the network, its rules, the organisation's roles and what they allow, members |
   | Certificates | a role provides a certificate type | the people who hold the organisation's certificates (linked members) |
   | Services | a role provides a credential a service can issue | offer a service: who can apply, what is seen (ADR-0139) |
   | Listings | a role provides a listing type | post, change, close listings; responses; offers (ADR-0140) |
   | Activity | always | events about the organisation on this network: links, unlinks, applications, offers |
   | Setup | the organisation runs the network | profile, joining rules, roles built from the vocabulary |
   | Membership | the organisation runs the network | applications; approve in roles; change roles; suspend |
   | Developers | outside platforms, and the running organisation | SDK, keys, notification address |

   The app knows a small set of **kinds** of noun — certificate types, listing types, services, record types, components,
   hosting — and shows a tab for each kind the organisation's roles touch. No network gets special-case screens.

4. **Three layers, three owners.**
   - **Vocabulary** — nouns (record, certificate and listing types) and verbs (interfaces) — belongs to the commons:
     each domain's owner publishes and versions its types (ADR-0141); a network *chooses* from it, never defines it.
   - **Roles** — bundles of capabilities (a verb on a noun, provide or use) — belong to each network's administrator
     (Setup → Roles).
   - **Membership** — which roles each member holds, one or several — belongs to each network's administrator
     (Membership).

5. **The commons is a network in the same app.** Every organisation on AirawatOS belongs to Airawat Commons with the
   *Tenant* role; its tabs follow the commons roles: *Vocabulary* and *Marketplace* for every tenant (browse; request a
   new type or field), *My domains* for domain owners, *Components* for publishers, *Hosting* for operators, and *Setup,
   Membership, Certification, Domains* for the steward. Today's publication approvals and the steward's schema
   publishing move there — an audited, role-checked path instead of internal endpoints.

6. **Approvals are tasks.** Membership applications, type requests, applications to a listing and service applications
   decided by staff become tasks in the Task Inbox for the people who decide them; the Networks app shows counts and
   links to them — no second queue.

7. **The same API underneath.** The app calls the network through the same paths as the participant API the SDK uses;
   an organisation on AirawatOS and one outside it are equal participants and see the same results.

## Stages

1. **Taking part:** Home; Overview (roles and what they allow), Certificates (linked members), Services, Listings,
   Activity. Settings → Networks becomes a link.
2. **Running:** Setup (roles from the vocabulary) and Membership; retire the Network Admin app.
3. **The commons:** the commons network with its roles and every tenant a member; Vocabulary, Marketplace, Components,
   Hosting.
4. **Attention:** counts on Home; Task Inbox integration.

## Consequences

- One mental model — *my networks, my roles, what they let me do* — for a ministry, a platform aggregator and an
  insurer alike.
- New kinds of network need configuration (roles from the vocabulary), not new screens.
- Network Admin and Settings → Networks are retired after stage 2.

## Open questions

1. **Other installations.** Organisations hosted by other operators reach the commons (and other operators' networks)
   over the network API; how they sign in to a network run on another installation is open (ADR-0141).
2. **Offers from organisations on AirawatOS** need a signing path for hosted participants (their keys held in the
   platform's secret store).
3. **People.** Whether a person's own view of their networks (today the network's account page) joins this app for
   people signed in to AirawatOS.

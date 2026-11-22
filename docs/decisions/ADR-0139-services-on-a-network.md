# ADR-0139 — Services on a network

**Status:** Proposed
**Date:** 2026-11-22
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

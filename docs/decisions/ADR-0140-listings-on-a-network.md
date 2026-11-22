# ADR-0140 — Listings on a network

**Status:** Proposed (revised 2026-11-22: was "Jobs on a network"; jobs are now the first kind of listing)
**Date:** 2026-11-22
**Related:** ADR-0137 (participants without AirawatOS), ADR-0138 (network roles and capabilities), ADR-0139 (services on a
network).

## The problem

A worker's linked records — the work certificates their platforms issued — are their history. The next thing they are
for is the next opportunity: a job, a training seat, a housing allotment; for a business, a tender. Each of these follows
the same cycle: someone **lists** an opportunity, people **respond** with proof of who they are and what they have done,
the lister **offers**, and the respondent **accepts** — and the outcome should be a certificate the person keeps.

Building each kind as its own feature — its own endpoints, screens and SDK calls — would make every network wait for
code, and the SDK would stop being generic. A network should be able to add a kind of listing by configuration.

## Decision

1. **A listing type is a governed record type that says it is a listing.** Its governed definition carries:
   - its **fields** (name, label, type, required) — what a lister fills in and what people see;
   - its **words** — what the listings are called ("Jobs"), one of them ("job"), the response ("Apply"), the offer
     ("Make an offer");
   - what an **offer issues** — the credential type the lister gives on acceptance (a job placement);
   - the governed types of a **response** and an **offer**.
   Governing a new listing type is the only step that makes a new kind of listing exist.

2. **A network's roles decide which listing types it has and who may list.** A listing type is on a network when one of
   its roles **provides** it; a member may list while its role provides the type, and may offer while its role provides
   the credential the offer issues (ADR-0138). A person may share a certificate type in a response only with a lister
   whose role **uses** that type.

3. **One mechanism for every type.** Listings, responses and offers are records on the network, of the type's governed
   kinds. The network checks fields against the type's definition. The participant API and SDK have one set of calls —
   post a listing of a type, read responses, make an offer, see offers — whatever the type.

4. **People see and respond in their own account.** The account shows each listing type on the network under its own
   name, with its fields. Responding uses the network's consent screen: the name always; the certificates the person ticks;
   the mobile only if ticked. The lister receives only those, with the network's note that each certificate is genuine and
   current. One response per listing.

5. **Offers carry the outcome, signed.** A lister offers to someone who responded, or directly to someone already linked
   to it — by the link id it holds, learning nothing new. The offer carries the credential the type issues, signed by the
   lister. On acceptance the network checks the signature and the lister's role again and puts the credential in the
   person's account; the lister is told by a signed event. Offers lapse after 14 days. A lister can close a listing.

6. **Events** to the lister: `listing.response`, `offer.accepted`, `offer.declined` — each naming the listing type.

## Worked example — jobs on the eShram network

| | |
|---|---|
| Listing type | `hr.job_posting` — fields: title, work, place, pay, openings, description; words: Jobs / job / Apply / Make an offer |
| Response | `hr.job_application` — name, chosen certificates, mobile if chosen |
| Offer issues | `credential.job_placement` — employer, role, pay, starts on, place, offered on; signed by the employer |
| Who may list | members whose role provides `hr.job_posting` (the Platform role) |
| What they may receive | certificate types their role uses (`platform_work_certificate`) |

A platform posts a job; a worker sees it under *Jobs* in their account, applies sharing two work certificates; the
platform offers; the worker accepts and the job placement certificate is in their account. The platform then onboards and
links them, and their new work certificate starts the next cycle.

A training network would govern `skills.training_batch` (issues `credential.training_enrolment`) and add it to a training
institute's role; a city could govern `works.tender` (issues `credential.contract_award`) for its vendors. No code changes.

## Consequences

- New kinds of listing are governed definitions plus role configuration; the SDK stays generic.
- People's history travels as certificates; listers see only what was shared and know it is genuine.

## Open questions

1. **Matching.** Whether the network suggests listings to a person from their certificates.
2. **Organisations on AirawatOS.** Screens for hosted listers (this ADR starts with the SDK).
3. **Withdrawal and disputes.** Withdrawing a response or an accepted offer.
4. **Listing on behalf of others.** A platform listing for the businesses it serves.

# ADR-0140 — Jobs on a network

**Status:** Proposed
**Date:** 2026-11-22
**Related:** ADR-0137 (participants without AirawatOS), ADR-0138 (network roles and capabilities), ADR-0139 (services on a
network).

## The problem

A worker's linked records — the work certificates their platforms issued — are their work history. The next thing they
are for is the next job. Today a platform that wants workers must find them on its own, a worker must re-prove their
experience to every employer, and a platform cannot offer work to the people it already knows on the network without
asking them for their details again.

## Decision

1. **Jobs, applications and offers are records on the network**, of governed types (`hr.job_posting`,
   `hr.job_application`, `hr.job_offer`). The network keeps them; members reach them through the participant API and SDK.

2. **The role decides who may post and offer.** A member may post a job only while its role **provides**
   `hr.job_posting`, and may make an offer only while its role **provides** the result it will issue
   (`credential.job_placement`). A worker may share a certificate type with an employer only if the employer's role
   **uses** that type (ADR-0138).

3. **Workers see open jobs in their own account** on the network and apply there. The application screen is the
   network's own: the worker ticks which work certificates to share as experience, and whether to share their mobile
   number; their name is always shared. The employer receives only those facts, with the network's note that each shared
   certificate is genuine and current. A worker applies to a job once.

4. **An employer is told about applications by a signed event** (`job.application`) and reads them through the SDK. An
   applicant who is not already linked to the employer is known to it only by the application's id.

5. **An employer may offer work** to someone who applied, or directly to a worker already linked to it — by the link id
   it holds, so it learns nothing new about that worker. The offer carries the **job placement certificate, already
   signed by the employer** (employer, role, pay, start date).

6. **The worker accepts or declines in their account.** On acceptance the network checks the employer's signature and
   role and puts the placement certificate into the worker's account; the employer is told by a signed event
   (`job.offer_accepted` or `job.offer_declined`). The employer can then onboard and link the worker, which gives them a
   new work certificate — and the cycle continues.

7. **Closing.** An employer can close a job; open applications to it are closed with it. An offer that is not answered
   in 14 days lapses.

## The cycle

| Step | Who | What moves |
|---|---|---|
| Post a job | employer (role: post jobs) | the posting, public on the network |
| Apply | worker, in their account | name, chosen certificates, mobile if chosen → employer |
| Offer | employer | a signed placement certificate, to an applicant or a linked worker |
| Accept | worker | the placement certificate → the worker's account; "accepted" → employer |
| Onboard and link | employer and worker | a new work certificate → the worker's account |

## Consequences

- A worker's experience travels with them as certificates; no employer has to take it on trust or ask for it again.
- Employers see only what a worker chose to share, and the network vouches that it is genuine.
- One mechanism serves platforms and any other employer; only the role differs.

## Open questions

1. **Matching.** Whether the network suggests jobs to a worker from their certificates (and what it may read to do so).
2. **Organisations on AirawatOS.** Screens for hosted employers (this ADR starts with the SDK).
3. **Withdrawal and disputes.** Withdrawing an application or an accepted offer, and what happens to the placement
   certificate.
4. **Third-party employers through a platform.** A platform posting on behalf of the businesses it serves.

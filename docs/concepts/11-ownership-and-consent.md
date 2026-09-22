# Data Ownership & Consent

*Who owns each piece of data, and why nobody else can see it without their say-so.*

## The problem

[Zero-Trust](/developer/deep-dives/zero-trust/) keeps *code* honest, and every tenant's data is walled off from every other tenant. But that leaves a question it doesn't answer: **inside** an organization, who may see a given record?

If the answer is "anyone in the tenant," that's wrong for a lot of data. My draft document isn't my colleague's business. A citizen's health record isn't readable by every clerk in the building. "Same organization" is far too broad a circle for personal data.

So the platform needs a finer idea than *the tenant owns everything*: **each record has an owner, and only the owner decides who else may see it.** That decision — consent — is enforced in the trusted kernel, underneath every app, so no app (however buggy or malicious) can reveal or share data its owner hasn't agreed to share.

## Who owns a record?

The honest first question is *which* person owns a given row — and it isn't always the same answer. A record's schema (its [governed noun](/developer/deep-dives/shared-vocabulary/)) declares one of **three ownership modes**:

- **Tenant-owned** (the default). The organization owns it: a building footprint, a budget line, a court case. There's no individual owner; it's operational data the agency works with. This is how everything behaved before — nothing changes here.
- **User-owned** (`self`). The **person who created it** owns it: your documents, your files, your notes. You made it, you own it, and only you (and people you share it with) can see it — even other members of your own organization can't.
- **Subject-owned**. The record is *about* a person, and **that person owns it — not whoever typed it in**. A citizen's property record, health record, or grievance is created by a clerk or ingested by a system, but the **citizen** is the owner who consents to sharing it.

That third one is the subtle, important case. If we treated "the creator owns it," the clerk who entered a citizen's record would control the citizen's data — exactly backwards. So for data about a person, ownership points at the *subject*, read from a field on the record (like `citizen` or `subject_ref`), never at whoever created it.

## Consent: the link is not the permission

Once a record has an owner, sharing is simple to state: **only the owner can grant access, and they choose the level** — *view*, *comment*, or *edit*. Access is a decision the kernel makes against that owner-issued grant.

A consequence worth making explicit: **a link to a record carries no authority.** If someone forwards you a link to a record you were never granted, opening it shows you nothing — the kernel checks for a grant, finds none, and refuses. This is the opposite of "anyone with the link can view." Nothing leaks just because a URL got passed around; access always traces back to a permission the owner deliberately gave, and revoking that permission cuts access off at once.

## The custodian: when an agency holds your data

Subject-ownership raises a fair question: if a citizen owns their property record, how does the **property department** — which has to maintain it — get to it?

Through a **custodian role**. A subject-owned record can name a role as its custodian (say, the *records officer*). Whoever the organization assigns to that role — assigned by your tenant's admin, [the same way any role is granted](/developer/deep-dives/participants/) — gets to **read and update** the record as part of their job, without asking the citizen each time.

But the custodian's power stops there: **a custodian may operate the record, but may not share it onward.** Handing the data to a third party is *consent*, and consent stays with the citizen. This mirrors how data-protection law separates the **data subject** (the person), the **controller/custodian** (the agency that holds it), and everyone else.

## A worked example

Ramesh's property record lives in the city's system.

1. A **clerk** creates the record. Because the schema is subject-owned (pointing at Ramesh), the kernel records **Ramesh** as the owner — not the clerk.
2. The **clerk tries to open it** with no role and no grant → **denied.** The person who typed it in does not automatically get to read it back.
3. The city assigns the clerk's team the **records-officer** role (the record's custodian). Now the **clerk can read and update** it — routine agency work, no per-record permission needed.
4. That same officer tries to **share Ramesh's record with an outside party** → **denied.** Operating it is fine; giving it away is not their call.
5. **Ramesh** views his own record any time, and if he wants to share it — with a lawyer, another department — **he** grants *view* (or *comment*, or *edit*). He can **revoke** it whenever he likes, and access ends immediately.

Every one of those checks happens in the kernel, below the apps — so it holds no matter which app is asking.

## How you declare it (for developers)

You choose a noun's ownership when you [govern its schema](/developer/deep-dives/governance/), with a few flags:

- `x-ownership: user` — self-authored; the creator owns it.
- `x-ownership: subject` + `x-owner-field: citizen` — owned by the person named in that field.
- `x-custodian-role: records-officer` — the role whose holders are the custodian of a subject-owned record.
- *(no flag)* — tenant-owned, the default.

Get the choice right per noun: mark a citizen's record `subject`, not `user`, or you'll hand control to the clerk. Personal work products are `user`. Operational, org-level data stays the default.

## Why it's built this way

Putting ownership and consent in the **kernel** — not in each app — is what makes the guarantee real. An app can be careless; the floor beneath it isn't. And because every grant, every access, and every consent decision is a recorded, tamper-evident fact, an organization can show a citizen exactly who their data reached, by whose consent, and let them pull any of it back. Privacy stops being a promise in a settings screen and becomes a property of the system itself.

> Related: [Zero-Trust](/developer/deep-dives/zero-trust/) (how code is kept honest), [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/) (governed nouns), [Governance & Decisions](/developer/deep-dives/governance/) (how rules and roles are governed), and [Participants](/developer/deep-dives/participants/) (how a person is assigned a role).

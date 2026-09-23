# Designing a role (an actor)

*Nouns are the data, verbs are the actions — roles are **who is allowed to act**, and they're governed too.*

A role is a governed name for a *kind of actor* — `urban.pollution-control-officer`, `health.records-officer`, `judge`. Like a noun or a verb, a role is a shared standard: it's proposed, a steward approves it, and it becomes part of the network's **actor vocabulary** ([Governance & Decisions](/developer/deep-dives/governance/)). Apps then gate their actions on roles, so "who may do this" is a governed decision, not code buried in an app.

There are two *kinds* of role, and telling them apart is the main design choice.

## 1. Person roles (what someone's job is)

The everyday kind: a role a **person holds** in an organization — an officer, a clerk, a judge, a manager. These map to real posts. You:

- **Govern the role name** (`domain.role`, on a governed domain) — a proposed → approved standard, so the same "records officer" means the same thing everywhere.
- **Assign it to people** with a `governance.role_grant` — usually not by hand, but wired from **[Org Setup](/developer/deep-dives/governance/)**: when someone is posted to a position, the posting *projects* into a role grant. Assigning the role is the tenant's own decision; the role *name* is the shared standard.
- **Scope it, optionally.** A grant can be tenant-wide, or scoped to an org unit / area / jurisdiction — so a "ward officer" role holds only *in their ward*, not the whole city.

A user's effective roles are their identity roles **plus** any role grants, so giving someone a role takes effect immediately — the role-gated apps and actions light up without touching their login.

## 2. Data-governance roles (what an org *is* to a category of data)

A different, subtler kind — not "what is this person's job," but "what standing does an **organization** have over a class of data." The clearest example is the **custodian**: the agency responsible for holding and operating a category of records. This is the data-protection idea — a *data subject* (the person the data is about), a *custodian/controller* (the agency), and everyone else.

You meet this the moment you design **subject-owned** data (see [Data Ownership & Consent](/developer/deep-dives/ownership-consent/)). A citizen owns their record; the holding agency still needs to work with it. So the schema names a **custodian role**, and whoever the tenant assigns to that role gets operational **read and edit** — *without* asking the citizen each time. But the custodian's reach stops at operating the record: **sharing it onward is consent, and consent stays with the subject.** A custodian may work the data; only the owner may give it away.

These roles are governed and assigned the same way as person roles (dictionary + Org Setup), but they carry a *data-governance* meaning, so name and use them deliberately — a custodian is not a job title, it's a responsibility over data.

## Design considerations

- **Reuse first.** Check the role catalog before proposing. A shared role that already means what you need is worth far more than a new near-duplicate.
- **Name for the actor, not the app.** `health.records-officer`, not `myapp_editor`. Roles outlive apps.
- **Person role or data-governance role?** If it's a job, it's a person role. If it's "who holds/controls this data," it's the custodian (or a controller/processor) — and it belongs on the *schema* (`x-custodian-role`), assigned in Org Setup.
- **Prefer scoped grants over many roles.** One `ward-officer` role scoped per ward beats a hundred `ward-N-officer` roles.
- **Roles gate *who*, not *what*.** A role widens who may act; it never widens what a component may touch — that's still the component's declared capabilities and the kernel's checks. The two compose: a role-holder can advance work an app is built for, and no one else.

## The short version

> A role is a governed name for an actor. Decide whether it's a **person role** (a job — assigned via Org Setup postings, optionally scoped) or a **data-governance role** (a custodian/controller over a data category — named on the schema, consent still the subject's). Reuse before proposing, name for the actor, scope instead of multiplying, and remember: roles decide *who* may act, never *what* the code may do.

Related: [Governance & Decisions](/developer/deep-dives/governance/) (how roles and decisions are governed), [Data Ownership & Consent](/developer/deep-dives/ownership-consent/) (the custodian role), and [Designing a schema](/developer/build/designing-a-schema/) (where `x-custodian-role` lives).

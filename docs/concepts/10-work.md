# Work: Inbox, Cases & Tasks

*How people actually do their jobs on the platform — one shared inbox, and a common structure behind every process.*

## The problem

A platform can hold perfect data and make perfectly accountable decisions, and still be unusable if
every process has its own separate screen, its own separate queue, and its own separate way of asking
someone to do something. People end up hunting across a dozen tools for "what needs my attention."

AirawatOS answers this with one **universal Inbox** and a single, shared structure behind every
process — so whether it's a leave request, a grievance, a permit, or a court hearing, the *shape* of the
work is the same.

## The universal Inbox

The Inbox is the one place a person goes to see everything waiting on them, from every process, across
every solution they use. It works like email in the ways that matter:

- everything needing your attention arrives in **one list**;
- each item tells you what it is, where it stands, and what you can do about it;
- and **"Compose" means "start a new request"** — filing a new leave application, raising a new
  grievance, opening a new case is just composing a new item, the same motion as writing a new email.

That last point is the quiet trick: people already know how to use an inbox, so they already know how to
use the whole system.

## The structure behind the work

Under the Inbox, every process is built from the same small set of pieces, nested:

- a **service** is the outcome someone wants (see [Solutions & Services](/developer/deep-dives/solutions-services/));
- a **case** is one running instance of it — this person's leave request, that citizen's grievance;
- a **workflow** is the path the case follows — its states and the transitions between them;
- a **task** is a single unit of work assigned to a person or role — "approve this", "review that".

Because this structure is uniform, an inbox item from the HR process and an inbox item from the courts
process are the same kind of thing, routed the same way, actioned the same way. A developer building a
new process describes its workflow once (a governed declaration — see
[Interaction](/developer/deep-dives/interaction/)) and gets inbox routing, tasks, and status for free.

## Everything stays accountable

The Inbox is a surface, not a shortcut around the rules. Acting on a task still goes through the normal
machinery: the action is a governed verb, authority is checked, and the result is recorded. Approving a
request from your inbox produces the same accountable outcome as approving it anywhere else — there is no
"back door" that skips the receipt.

**A worked example.** A staff member files a leave request — they *compose* it in their Inbox. That
opens a case on the "leave" workflow, which routes a task to their manager. The task appears in the
**manager's** Inbox, alongside a grievance they're handling and a document awaiting their sign-off — all
in one list. The manager approves the leave from the Inbox; the case advances to "approved", the outcome
is recorded, and the staff member sees the status update on their side. One inbox, many processes, every
step accountable.

## Where this stands today

**Working now:** the universal Inbox with "compose = new request"; the case-and-task structure behind
processes, with tasks routed to the right person or role and actioned in place; and real processes
running on it across several sectors (for example staff leave and expenses, grievances, and court
hearings), each described by a governed workflow declaration.

**Being built:** a single server-side **execution engine** that runs every workflow declaration uniformly
and is the one place actions are authorized — today several processes still run through their own
purpose-built engines while the platform converges them onto one. The structure a developer sees (case,
task, declaration) is stable; the machinery behind it is still being unified.

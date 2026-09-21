# Governance & Decisions

*How the platform turns data into an accountable decision — one a person can explain, contest, and correct.*

## The core promise

AirawatOS can predict and recommend. But a public decision — approve this permit, flag this case, issue
this advisory — is never made by the software alone. The platform's promise is: **AI advises; a named
person decides — and there is a receipt.**

A decision isn't finished when the answer appears. It's finished when it produces an immutable
**receipt** that lets the decision be *explained, reconstructed, contested, and corrected*.

## The shape of a decision: the hourglass

Every decision has the same shape, wide at both ends and narrow in the middle:

- **The top (wide):** many **facts** (records with their provenance and confidence) meet many **rules**
  (thresholds, norms, policy). Analysis and AI pre-apply the rules to the facts and produce a
  **recommendation**.
- **The neck (narrow):** one accountable **decision**. A named authority *admits* the recommendation
  (or amends or rejects it). This is the single point of accountability.
- **The bottom (wide):** the decision fans out into **outcomes** — orders, advisories, tasks, new
  facts.

And because an outcome is written back as a new fact, it becomes the *top of the next hourglass*. A
civic process is a chain of these.

## Who pulls the trigger: a spectrum, one receipt

Not every decision needs a human weighing in personally — but every decision is accountable the same
way. AirawatOS treats this as a spectrum on one primitive:

- **Automated** — a rule fires; the actor of record is the rule/engine.
- **Assisted** — the default: an authority admits, amends, or rejects a recommendation.
- **Discretionary** — an authority decides, with the recommendation as non-binding input.

Whichever it is, the **same receipt** is produced. Accountability doesn't depend on who or what pulled
the trigger.

## The receipt: an evidence manifest

The receipt is the atomic unit of accountability. It pins **both halves** of the decision so it can be
replayed later:

- the exact **facts** used — each at a specific version, with a content fingerprint and its provenance;
- the exact **rules** applied — each at the version that was in force;
- the recommendation, the outcome, the reasoning trace, the deciding authority, a signature, and a link
  to the previous receipt (so receipts chain).

Every field must resolve to a real, trusted record — not free text. The test is strict: a receipt is
only valid if the decision can be *reconstructed* from it. This is the decision-level parallel to the
provenance every fact already carries (see
[The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/)).

## Rules are data, not code

The rules a decision applies are **governed records**, not logic buried in some program. There is one
generic evaluator that reads a rule and evaluates it — the rule says *when* (a bounded set of safe
comparisons like equals, greater-than, in-list) and *then* an effect that the caller interprets.
Importantly, **the engine decides; it does not act** — it returns a result and an auditable trace naming
which rules matched. Because a rule is just a versioned record, you can change behaviour by editing
data, with a full history, instead of shipping new code.

## Nothing writes truth directly

A quietly powerful rule underpins all of this: **every change to authoritative data is itself a decided
request.** A task raises a *change request* (create / update / delete this record); the authority that
owns that data decides it — applying facts and rules — and *only that decision performs the write*,
stamped with the deciding authority. Authorisation and attribution become one object. (Reads are
exempt.) Cross-tenant changes are signed requests the *other* side decides — so data sovereignty is
structural, not a setting.

## When a decision is wrong: contest, correct, complete

Because everything is pinned, a decision can be challenged precisely — at whichever part of the hourglass
is actually wrong:

- the **fact** was stale or wrong → re-derive it;
- the **rule** was superseded or out of scope → re-resolve;
- the **recommendation** was mis-applied → re-run;
- the **choice** itself was in error → review it.

A successful challenge produces a **correction order** that names the authority, the action, and a
deadline — and it isn't complete until a **completion report** is submitted and accepted. The original
decision is **preserved**; a new decision *supersedes* it. History is never erased — it's superseded, in
keeping with the platform's reconstructability guarantee.

## The same machinery governs the platform itself

Here's the elegant part: the platform's *own* standards are governed exactly the same way. Every schema
(data shape), role (who can act), and interface (verb) is a governed record: **public to read, open to
any participant to propose, approved only by the network authority.** A proposal is a signed record, not
a direct edit; approval is what triggers signing, versioning, and publishing. Even the controlled
vocabularies the naming rules enforce are governed data. The system uses its own decision spine to
evolve its own rules.

## Where this stands today

**Working now:** the "AI advises, human decides" loop with signed decision receipts *within a
deployment* (live in the flood and air-quality recommendation loops); rules-as-data with a first generic
rule engine and live domain rule engines; the record-integrity fingerprinting that lets a receipt pin
exact versions; the spec-governance backend where schemas are proposed and approved; and the
decided-change-request pattern proven in participant registration.

**Being built:** the full contest → correct → complete → audit loop is designed but not yet built; a
contracting layer (who is *entitled* to use a certified component, with settlement) is a direction, not
yet built; a decision receipt on *every* recommendation, and a single stored-and-executed change-request
writer, are still being rolled out. The richer rule model (rule strength, structured four-way
contestation) is a proposed, phased extension.

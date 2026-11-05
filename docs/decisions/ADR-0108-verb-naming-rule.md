# ADR-0108 — Verb Naming Rule: governed verbs are *plane verbs*; domain actions are *transitions*

- **Status:** Proposed (2026-09-28)
- **Refines:** [[ADR-0091]] (interaction verb taxonomy), [[ADR-0091-V3]] (lifecycle plane)
- **Enforced under:** [[ADR-0097]] (one interaction spine — clean-cut convergence on `platform.workflow` graphs)
- **Relates to:** [[ADR-0101]] (governed verb binding, domain-blind host), #263 / #266 / #267 / #269

## Context

The Network today governs ~100 interface ids, and many are shaped `domain.action_noun` —
`funding.release_tranche`, `project.proposal_draft`, `hr.leave_apply`, `waste.compliance_rank`,
`welfare.deprivation_scan`. Each such id is a **separately governed verb**: it must be certified,
authorized, documented, conformance-tested, and learned by every caller. Every new domain invents a fresh
set of these, so the vocabulary grows without bound and nothing composes across domains.

Dropping the `domain.` prefix (`release_tranche → release`, `proposal_draft → draft`) does **not** fix
this: every domain still invents its own action words (`release`, `draft`, `disburse`, `rank`, `scan`,
`file`, `close`…) and you have the same explosion one level down.

## Decision — the Verb Naming Rule

A governed verb names **the kind of interaction**, drawn from a small fixed set (the *plane verbs*).
Everything domain-specific moves out of the verb name into three other governed places.

| Layer | Answers | Vocabulary | Where it is governed |
|---|---|---|---|
| **Verb** | *what kind of interaction?* | fixed, tiny (below) | `network.interface` |
| **Workflow** | *which process?* | one per domain process | `platform.workflow` declaration |
| **Transition** | *which step? (the readable action)* | free — `draft`, `submit`, `release`, `approve`, `close` | inside the workflow declaration |
| **Noun** | *on what record?* | governed schema | `network.schema` |

**The fixed plane-verb set** (the only verbs a new interface may be named after):

- **Lifecycle plane** — `lifecycle.request`, `lifecycle.decide`, `lifecycle.update`, `lifecycle.withdraw`, `lifecycle.status`
- **Compute plane** — `compute.run` (the recipe name is a parameter, not a verb)
- **Decision / evaluation** — `decision.route`, `governance.evaluate`, `governance.decide`
- **Data plane** — `registry.query`, `registry.read`, `registry.write`, `registry.retract`

Adding a *new* plane verb is a deliberate standards-body act (a new row in the canonical set), not something
a domain does incidentally by publishing an interface.

### The naming test (one line)

> **If the word could be a *value* of a status field — `draft`, `submitted`, `released`, `approved`,
> `closed` — it is a transition, not a verb.**

`release`, `draft`, `submit`, `approve` all pass that test → they are transitions on a workflow. `request`,
`decide`, `run`, `route` do not → they are verbs.

## A simple example — the government office

Picture a government office. A citizen only ever does a handful of *things* at the counter:

- **submit** a form,
- **check** where it stands,
- an officer **decides** it,
- you **update** or **withdraw** it.

The office does **not** build a new counter for every form — a "Tranche Release Counter", a "Leave
Application Counter", a "Proposal Draft Counter". That would mean thousands of counters, each with its own
signboard, its own trained clerk, its own rulebook — and a citizen would have to learn a different counter
for every task. Instead there are a **few counters** (Submit · Decide · Update · Withdraw · Status). The
**form** you carry says which process you're in (leave, tranche, proposal); the **step printed on the form**
("draft", "released", "approved") says where you are.

Map it to the platform:

| Office | Platform |
|---|---|
| the few counters | the fixed **plane verbs** (`request/decide/update/withdraw/status`, `compute.run`, …) |
| the form | the **record schema** (`project.proposal`, `finance.tranche`) |
| the process rulebook | the **`platform.workflow`** declaration |
| the step printed on the form | the **transition** (`draft`, `release`, `approve`) |

So `funding.release_tranche` becomes: verb `lifecycle.update`, workflow `funding.disbursement`, transition
`release`, record `finance.tranche`. `project.proposal_draft` becomes: verb `lifecycle.request`, workflow
`project.proposal`, transition `draft`. You still *read* "release" and "draft" everywhere — they've just
moved onto the form, off the counter signboard.

## Why it has to be this way

1. **Learn once, works everywhere.** Anyone — a person, an app, an AI agent — who learns the ~10 plane
   verbs can operate *every* process on the network: leave, tranche release, proposals, court cases. With
   `domain.action_noun`, to talk to funding you must learn `release_tranche`; to talk to projects,
   `proposal_draft`. Nothing you build for one domain works for the next.
2. **A new domain adds data, not code.** A new process is a new `platform.workflow` *declaration* (governed
   data) plus its schema — no new verbs, no new engine, no new certification/authz/conformance work. This is
   what lets the platform scale to hundreds of domains.
3. **Bounded governance surface.** Every governed verb costs certification, authorization rules, docs,
   conformance suites, and version discipline. A fixed set keeps that cost constant instead of growing with
   every feature.
4. **Cross-cutting tools become possible.** One Inbox, one approvals screen, one audit trail, one
   status-tracker, written once against `request/decide/status`, works for all domains — because the shape
   of "an approvable request" is the same everywhere.

The cost is a real one and we accept it: the migration is a **breaking rename** of existing verbs, and the
domain meaning now lives in declarations that must be authored and read. ADR-0097 already commits to that
clean cut.

## Enforcement

The interface linter (`network/api.py`) gains rule **IV5**: a *new* interface id must be one of the
canonical plane verbs. Interfaces that already exist are **grandfathered** (they are being migrated, not
re-created), so nothing breaks mid-flight. Like the schema house-rules, it ships **warn-shadow first**
(`VERB_NAMING_ENFORCE=0`) and is flipped to hard-reject once the migration below is done. The advise path
(`/v1/interfaces` dry-run) surfaces IV5 immediately, so a developer drafting `funding.release_tranche` is
told to use `lifecycle.update` + a workflow transition instead.

## Migration order

Grouped so each wave is coherent and independently shippable. Old verb → (verb, transition).

- **Wave 0 — done.** `hr.leave`, `hr.expense`, `campaign.verify`, `project.proposal_submit` route through
  the lifecycle verbs (via the ADR-0091-V3 alias seeds; ADR-0097 will convert these from `platform.lifecycle`
  + `platform.verb_alias` to `platform.workflow` graphs and retract the aliases).
- **Wave 1 — finish lifecycle singles.** `project.proposal_decide → decide/approve`,
  `project.proposal_draft/save → request|update/draft`, `org.posting_apply → request/apply`,
  `hr.attendance_mark → update/mark`, `campaign.create → request/create`, and make `justice.file_case`
  *real at runtime* (it is catalogue-deprecated but not yet rerouted).
- **Wave 2 — compute plane (#267).** Convert the scans/rollups/rankings already flagged
  `→ compute.run` into real `compute.run` recipes: `project.evaluate/review/rollup`, `tax.gap_scan`,
  `waste.compliance_rank`, `welfare.deprivation_scan/gap_scan/prioritise/prioritise_cells`.
- **Wave 3 — money workflows (hardest, multi-record).** `funding.*` (11: `publish_program`, `subscribe`,
  `received`, `record_receipt`, `award`, `commit_revenue`, `release_tranche`, `milestone`, `monitor`,
  `stack`, `revoke_subscription`) and `finance.*` (9: `advance_*`, `flow_*`, `payroll_*`, `post`) onto
  lifecycle transitions and/or `compute.run`.
- **Wave 4 — converge the service runtime (ADR-0097 W3, #269).** Delete `service-init/confirm/status/route/
  consent` and their handlers; express provider fulfilment as a `platform.workflow` graph.
- **Governance cleanup.** Make `governance.rule_eval` and `org.policy_resolve → governance.evaluate` real at
  runtime (currently catalogue-deprecated only).

Out of scope for collapse (they are already their own coherent planes, not lifecycle actions):
`registry.*` (data), `chat.*`/`mail.*` (messaging — a candidate for a future `message.*` plane, tracked
separately), `network.*` (federation ops), `platform.*` (infra), `intelligence.*` (AI/compute).

## Consequences

- **+** One small verb vocabulary; new domains are declaration-only; cross-cutting tooling composes.
- **+** The network catalogue stops doubling as a domain glossary; domain meaning lives in workflows + schemas.
- **−** Breaking renames; callers (apps/engines) must migrate in lockstep with each workflow.
- **−** Readability moves from the verb id into the workflow declaration — good tooling (Studio workflow view,
  the reference catalogue) must surface transitions well so humans still see "release"/"draft"/"approve".

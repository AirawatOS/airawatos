# Designing a verb (an interaction)

*If a schema is a noun, a verb is a governed way to **act**. The golden rule: you almost never need a new one.*

Nouns are the data; **verbs** are the governed *interactions* — the actions components expose to each other and to people ([interfaces](/developer/deep-dives/interaction/)). A verb binds a request/response (or event) contract to a name, and it's governed exactly like a noun: you *propose* it, a steward *approves* it.

But the single most important thing to understand about verbs is the opposite of nouns:

## Verbs are few; nouns and configuration proliferate

The systems that scaled kept a **small, fixed verb set** and let the *nouns* multiply. HTTP has ~9 methods over infinite URLs. Beckn books a ride, a meal, and a clinic visit with the *same* ten verbs — the difference is entirely in the schema and the tags, never a `book-ride` verb.

AirawatOS follows the same discipline. Domain-specificity is expressed as **data** — a schema, a ruleset, a workflow declaration, a payload contract, tags — **never as a new verb**. So before you reach for a verb, the honest first question isn't "what should I name it" — it's *"am I sure this is a new interaction shape, and not just a new domain wearing one I already have?"* Almost always, it's the latter.

## The five planes (and their generic verbs)

Every interaction fits one of five planes, each with a tiny, load-bearing verb set:

- **Data** — `read`, `write`, `history`, `retract`. CRUD over the bitemporal registry; kernel-native. This is how you touch nouns.
- **Lifecycle** — `request`, `decide`, `update`, `withdraw`, `status`. The universal request→decide→transition state machine ([Work: Inbox, Cases & Tasks](/developer/deep-dives/work/)). A leave application, a grievance, a funding proposal are all `request(kind)`; approving any of them is `decide(case, transition)`. The *domain* is the workflow declaration, not the verb.
- **Compute** — running a recipe/analysis over data (a scan, a rollup, a model inference).
- **Policy** — evaluating a ruleset. "Resolve this policy," "check this authorization" are the *same* `evaluate` over different rulesets, not different verbs.
- **Messaging** — emitting and subscribing to events.

So `leave-apply`, `expense-apply`, `proposal-submit` aren't three verbs — they're one `request`, three workflow declarations. `policy-resolve` and `authz-check` aren't verbs — they're rulesets fed to `evaluate`.

## When a new verb *is* justified

Only when you have a **genuinely new interaction shape** — a way of interacting that none of the five planes' verbs express. That's rare, and it's a real design signal: it usually means a new plane or a new contract, worth a steward's scrutiny. If you can express what you want as *(a generic verb) + (a schema/ruleset/workflow/payload)*, do that instead — your interaction instantly composes with everything already built on that verb.

## If you do propose one

A verb is a governed interface, so the shape mirrors [designing a schema](/developer/build/designing-a-schema/):

- **Name it** `<domain>.<subject>` on a governed domain, in the actor·verb·noun grammar the linter checks — the same naming discipline as nouns.
- **Declare its contract**: the modality (a request/response, or an event), and the **request** and **response** schemas — which reference governed nouns, so the verb is typed end-to-end.
- **Propose → approve**: file an *interface-request*; only the standards body publishes it (entering a verb into the catalog is an authoritative act, steward-gated like a schema). Version it `@0.1.0`; verbs carry a lifecycle (active → deprecated → retired).

## How a verb reaches your code

Publishing a verb doesn't run anything by itself. A verb is **bound** to the component that implements it — a governed `platform.verb_binding` record maps the verb to your engine. When someone calls the verb, the platform dispatches it to the bound engine, and every write it makes is attributed to that component on the caller's behalf. On the interaction paths that carry them today — service transactions, personal-agent actions, and consented data-reads — the call also leaves a signed **receipt** proving who invoked what against which contract; generalising receipts to every verb invocation is being rolled out. So a verb is a *promise* (the contract) and a *binding* (who fulfils it), increasingly backed by a *receipt* (that it happened) — all governed data, none of it hard-wired.

## The short version

> Reach for a verb last, not first. Express your domain as a **noun + config** over an existing generic verb (`request`/`decide`, `read`/`write`, `evaluate`, `run`, `emit`). Propose a genuinely new verb only for a genuinely new *interaction shape* — and when you do, it's a governed, typed, steward-approved contract, bound to an engine, exactly like a noun is a governed shape.

Related: [Interaction: verbs & events](/developer/deep-dives/interaction/) (the concept), [Designing a schema](/developer/build/designing-a-schema/) (the noun it acts on), and [Work: Inbox, Cases & Tasks](/developer/deep-dives/work/) (the lifecycle plane in action).

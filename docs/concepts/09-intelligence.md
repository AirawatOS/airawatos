# Intelligence & AI

*How the platform makes sense of data — analysis, prediction, and AI assistants — without ever letting the AI make the call.*

## Where intelligence sits

The registry holds facts; governance turns decisions into receipts. **Intelligence** is the layer in
between that *makes sense of the data*: it analyses, it predicts, and it recommends. Its firm boundary,
inherited from the platform's core promise, is simple: **intelligence advises; it never decides.** Every
recommendation it produces is an *input* to a decision (see
[Governance & Decisions](/developer/deep-dives/governance/)), never an exercise of authority.

## The reasoning loop

At the heart of the layer is one loop:

**facts × rules → a recommendation.**

Some component reads the relevant facts, applies the relevant rules, and produces a **recommendation** —
a cited suggestion of what to do. It does not act on it. It hands it to a person (or, for low-stakes
routine cases, to an automated decision) who accepts, amends, or rejects it — and *that* step, not the
recommendation, is what carries weight.

## The pieces

- **Skill** — the atomic reasoner. A skill takes facts and rules and produces a cited recommendation.
  It is confined like any other component: it reads what it declared, writes what it declared, and its
  output points back at the evidence it used.
- **Agent ("AI Expert")** — an installable domain assistant. An Expert bundles a *persona* and a set of
  *skills*; installing it fans out to its skills. The Expert itself doesn't reason — its skills do. In
  its current form an Expert **reads and recommends**; it does not take actions on its own.
- **Model** — a large language or machine-learning model, reached through a single guarded gateway (so
  model calls are mediated and recorded like any other outside call).

## Grounded, cited, and recorded

Two disciplines keep AI trustworthy here:

- **Grounded and cited.** An AI answer or recommendation must be built from *governed data* and must
  cite it. A useful assistant that answers "which areas breached the limit last week?" should draw only
  from the registry and show which facts it used — not improvise from thin air.
- **Recorded.** Every call to a model produces an **interaction receipt** with fingerprints of the
  request and response, the model used, and the component that asked. When a fact is later produced from
  a model's output, it points back to that receipt — so even "this suggestion came from a model" is
  provable and traceable, and flows into the evidence a decision pins.

## Uncertainty is first-class

Facts can carry a **confidence**, and a recommendation carries its reasoning. A prediction is not
dressed up as certainty; a low-confidence input stays visibly low-confidence all the way to the person
deciding. This is what lets a human weigh a recommendation properly rather than rubber-stamp it.

**A worked example.** An "air-quality expert" watches PM2.5 facts for an area. When measured readings
cross a governed threshold rule, its skill produces a recommendation — "issue a public health
advisory" — citing the exact readings and the rule. That recommendation lands in a named
official's inbox as a task. The official reviews the cited evidence and decides. The AI found the
pattern and explained it; the person made the call; the receipt records both. The same shape works for a
flood advisory or a welfare-eligibility flag — different facts, different rules, same loop.

## Where this stands today

**Working now:** the facts × rules → recommendation loop, live in real "sense → recommend → a person
decides" flows (for example air-quality and flood advisories), with recommendations cited and routed to
an inbox; AI Experts and skills as installable components; grounded AI assistants embedded in apps that
answer from governed data; and interaction receipts on model calls, with produced facts citing them.

**Being built:** richer prediction and simulation; the ability for an agent to *act* (rather than only
read and recommend) under tightly scoped authority; and broader "train a model on your governed data"
tooling. Treat prediction/recommendation-with-a-human as live, and autonomous action as planned.

# Interaction: verbs & events

*How one part of the platform asks another to do something — and how a request finds the code that handles it.*

## The web pattern, applied to public services

The web works because a browser and a server never need to know each other in advance — they agree on a
small set of verbs (GET, POST) and exchange typed documents. AirawatOS uses the same idea for public
services: **providers** expose capabilities, **consumers** ask for them, and they meet through a small
set of shared **verbs** carrying typed data — the same governed data shapes from
[The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/).

The consumer never needs to know *which* provider or *which* engine will answer — only the verb and the
data shape. That's what makes the pieces swappable.

> "Public services" here means the civic outcomes people consume — not the platform's own infrastructure
> processes, and not the packaging size also called a "service". Those three senses are teased apart in
> [Solutions & Services](/developer/deep-dives/solutions-services/).

## Few verbs, domain in the data

A tempting mistake is to invent a new verb for every action: `apply-for-leave`, `submit-grievance`,
`file-case`, and hundreds more. AirawatOS deliberately goes the other way: **a handful of load-bearing
verbs**, with the specific domain carried in a governed *declaration*, not baked into the verb name.

For step-by-step processes (a leave request, a grievance, a court case), the generic verbs are things
like:

- **request** — start something;
- **decide** — approve or reject it;
- **update** — record progress;
- **withdraw** — cancel it;
- **status** — ask where it stands.

The difference between "a leave request" and "a court case" isn't a different verb — it's a different
**declaration**: a governed record describing the states, the transitions, who may make each one, and
what each one writes. One engine reads that declaration and runs the process. Add a new kind of process
by publishing a new declaration — no new verb, no new engine.

**A worked example.** A staff-leave request and a court case look completely different to a person, but
to the platform they're the same five verbs over two declarations. Applying for leave is `request` on
the "leave" declaration; a manager approving it is `decide`. Filing a court case is `request` on the
"court case" declaration; a judge ruling is `decide`; asking "where is my case?" is `status`. The leave
declaration says a manager approves; the court-case declaration says a judge rules — the rules about
*who* and *what states* live in the declaration, not in the verb. Build a new process — a grievance, a
permit, a grant application — and you write a new declaration, not new plumbing.

## Interfaces: the contract behind a verb

A verb isn't loose. Each one is defined by a governed **interface** — essentially "two data shapes plus
a direction": what the request looks like, what the response looks like, and whether it's a
request/response, a stream, or an event. A provider *implements* an interface; a consumer *depends on the
interface* — never on the concrete provider. Because the dependency is on the governed contract, the
implementation behind it can be swapped for a better one without breaking anyone, as long as the new one
conforms.

## How a request reaches the right code

When an app needs something done, it calls the platform's single guarded channel — the **broker/bridge**
— with a verb (for example, `/bridge/request`). Now the key question: how does the platform know *which
engine* handles that verb?

Not from a hardcoded list. The host is **domain-blind** — it carries no sector logic of its own. It looks
up the verb in **governed binding records** in the registry: "this verb is implemented by that engine."
Those bindings are data. So when a developer publishes a new engine, publishing **registers its verbs**,
and the host starts routing to it within seconds — **no change to the platform, no image rebuild.**

This is a direct payoff of treating everything as governed data: the routing table for the whole
platform is itself editable, versioned records rather than code someone has to redeploy.

## One universal verb: resolve

Across the wider network, there's one verb every provider understands: **resolve** — "given this
reference (and optionally, as of this time), give me the record." Resolvable identifiers are the
network's equivalent of web addresses. A consumer can follow a reference to a fact held by another
participant without knowing anything about that participant's internals — the reference resolves, subject
to that participant authorising the read (see [Participants & the Network](/developer/deep-dives/participants/)).

## Not just asking — reacting to events

So far this is all *request*-shaped: one part asks, another answers. But much of public-interest work is
*reactive* — something changes in the world, and that should trigger attention somewhere. Alongside
request/response verbs, the platform routes **events**. A component **declares the events it subscribes
to** right in its description (`subscribes:`), and the platform **auto-wires the governed subscription
when the component is installed** — no glue code. This is how "a threshold was crossed" becomes "a task
appeared in the right official's inbox" without the sensor and the inbox knowing anything about each
other. (The mirror half — a component declaring the events it *emits* — and visually wiring events in
Studio are still being added; see the status note below.)

## Every interaction leaves a receipt

Some calls don't go to the registry at all — most notably, asking an AI model to complete something.
These get their own **interaction receipt**: a record with fingerprints of the request and the response,
which provider and model answered, and which component asked. When a fact is later produced from that
call, it points back to the receipt. So even "this rule was suggested by a model" is provable and
traceable — the AI is inside the same accountability net as everything else, feeding the evidence a
decision pins (see [Governance & Decisions](/developer/deep-dives/governance/)).

## Why this matters for a developer

You don't wire your engine into the platform by editing platform code. You:

1. build an engine that **implements** one or more governed interfaces (verbs),
2. declare those verbs in your description file,
3. publish.

The governed bindings do the rest. And because consumers depend on the interface, not on you, a better
implementation can take over later without breaking the apps that use it.

## Where this stands today

**Working now:** the domain-blind host that routes each verb to its engine from governed binding records
in the registry — live, so a newly published engine's verbs go live within seconds with no platform
edit; the generic lifecycle verbs served by a single engine, with the first domains migrated onto them
non-breakingly; the **subscribe** half of the event path — a component declares `subscribes:` and the
platform auto-wires the governed subscription at install; and interaction receipts on the AI-model path,
with produced facts citing them.

**Being built:** completing the migration of every domain onto the generic verb set (several are done,
several are in progress); promoting the *interface* to a fully governed artifact through the same
propose→approve flow as schemas and roles; the *emit* half of the event path (declaring the events a
component publishes) and visually wiring events in Studio; and behavioural conformance checks that let
one engine be swapped for another with confidence.

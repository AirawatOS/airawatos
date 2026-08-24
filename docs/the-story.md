# The Airawat Stack — the story (start here)

*A plain-language tour for someone who has never seen it. The precise version lives in the ADRs and specs; this
is the map you read first.*

## In one line

**The *Airawat Stack* is a set of horizontal **layers** that provide the shared machinery (identity, trust,
storage, rules) once, so any public-interest **field** (cities, health, justice, environment, finance, mobility…)
can plug in as a **vertical** and be built quickly and be trusted. **AirawatOS is just *one* of those layers —
the platform/machinery layer** — so the stack is bigger than the OS. **Cities (the *urban* domain) are the first
vertical we've built — an example, not the definition.**

## Why a "stack"?

Think of how a computer works: hardware at the bottom, an operating system on top of it, apps on top of that —
each layer does one job, so you never rebuild the lower ones. The Airawat Stack is that idea for public-interest
software: instead of every project re-solving identity, trust, storage, rules, and data standards from scratch,
the stack provides them **once**. The twist is the other axis — **fields don't sit *on top*, they cut *through*.**

## The Airawat Stack — horizontal layers (shared machinery)

Five layers, most general at the bottom to most specific at the top, each its own Airawat product. **Every field
reuses all of them:**

- **Airawat Network** — *who is in the federation, the shared language, and trust.* The register of participants,
  the agreed vocabulary everyone speaks, and the signing that lets anyone verify who produced what.
- **AirawatOS** *(the platform layer)* — *the machinery.* Build, check, sign, publish, install, and run software;
  store every fact in a record book. The "operating system" part — and *only* one layer of the stack.
- **Airawat Intelligence** — *making sense of the data.* Analysis, prediction, and AI agents.
- **Airawat Governance** — *the decision lifecycle, start to finish.* The **rules** that apply; the **decision**
  (facts + rules → a recommendation → a named authority accepts it, with its evidence attached); the **audit**
  trail (an immutable receipt of who decided what, on what evidence, under which rule); and **appeals** (a
  governed way to contest a decision → review → remedy → a *superseding* decision, with the original preserved).
  Plus the **consent + authority** that says who may decide at all. *(Facts themselves live in the registry —
  Governance binds them as a decision's evidence, it doesn't own them.)*
- **Airawat Interaction** — *how people and systems actually engage.* The apps, maps, and inboxes on top.

## Domains — the verticals (each cuts across every layer)

A **domain** — urban (cities), health, justice, environment, finance, mobility — is **not a layer**; it's a
**vertical slice that runs through all of them.** Each domain plugs its own field-specific content into each
layer: its **vocabulary** (data shapes) into Network, its **components** into Platform, its **models** into
Intelligence, its **rules** into Governance, its **apps** into Interaction.

```
   domains →           urban          health         justice      …   (verticals cut down ↓)
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │ Airawat Interaction│ city maps    │ clinic apps  │ court UI    │               │
  │ Airawat Governance │ zoning rules │ triage rules │ case rules  │               │
  │ Airawat Intelligence│ flood model │ outbreak fcst│ risk score  │               │
  │ AirawatOS (platform)│      shared: build · certify · install · run · registry          │
  │ Airawat Network     │      shared: participants · language · trust                      │
  └──────────────────────────────────────────────────────────────────────────────┘
     lower layers = almost entirely shared   ·   higher layers = each domain fills in more
     (component → solution → service = a separate "packaging" axis — how much you consume at once)
```

So a new field (say, public health) **reuses the whole stack** and only supplies its own vertical — new
vocabulary, components, models, rules, and screens. The machinery underneath never changes.

## Two promises everything rests on

1. **Everything is standardized and traceable.** Every fact has an agreed shape, a known source, and a record of
   who produced it and when. Nothing is a mystery blob.
2. **AI advises; a person decides.** The system can predict and recommend — but a named human makes the call, and
   there's a receipt showing what they decided and why.

## See it work — any agency, end to end

The clearest way to feel the stack is to watch **any agency** use it — a city, a water utility, a health
department, a disaster authority. The steps are identical whatever the field; only the pack differs (a city
installs flood monitoring, a health department installs outbreak tracking). We'll follow "the agency."

1. **An agency signs up** and gets its own **private, walled-off workspace** — its data is isolated from every
   other participant. *(network + platform)*
2. **It opens the marketplace** — an app store for capability — and installs the **pack** it needs (say, flood
   monitoring) in one click. *(platform)*
3. **Installing pulls in the pieces** — the small programs that fetch the data the pack needs (satellite imagery,
   maps, forecasts) — and gives each one **permission, signed by the agency**, to work with **its** data and
   nobody else's. *(platform + governance)*
4. **Activating runs them in order**, building the layers and drawing them on a map, with a progress bar as each
   layer lights up. *(platform + intelligence)*
5. **It's live.** When a threshold is crossed (heavy rain forecast, cases spiking), the system flags what needs
   attention and opens a task in an official's inbox. *(intelligence + interaction)*
6. **A person decides — and can be held to account.** A named official reviews the recommendation and its
   evidence and *chooses* to act; the system records who decided, on what, and why (the **audit** trail). If
   someone later disputes the call, there's a governed way to **appeal** it — reviewed, and if wrong, remedied by
   a new decision that supersedes the old one (without erasing it). *(governance)*

Adding **Heat maps** or **Mobility** later is the same motion, and each pack reuses what earlier ones built. Swap
"city / flood" for "hospital network / outbreak" and only the top layers change — the stack underneath is identical.

## Who's involved

A handful of roles, like any marketplace:

- **The standards body** (*AirawatNetwork*) — sets the shared rules and vocabulary and vouches for who is who.
  Think building codes + a notary. *(the network layer)*
- **Operators** — run the platform and set participants up.
- **Developers** — build the packs and the pieces inside them, and publish them to the marketplace.
- **Participants who consume** — a city, a health department, an agency — install and use packs.
- **Residents** — file reports and grievances, hold documents, and receive services.

> Today the standards body, an operator, and a developer all happen to be *us* (three separate accounts on
> purpose), so the model still works when they become genuinely different organizations later.

## Why you can trust it

- **Everything is checked and signed.** Before a pack can be sold or run, it's tested against the rules and
  stamped by the standards body. Anything unsigned is refused — it won't run.
- **Your data is yours.** A participant owns its data; nothing touches it without a **permission slip it signs
  itself**. A developer's pack running in an agency's workspace needs *that agency's* permission — the developer's
  say-so isn't enough.
- **Nothing is lost.** The record book keeps history: a correction never erases what came before, and every fact
  remembers where it came from.

## The building blocks (three sizes)

You consume capability at whatever size you need:

- a **component** is one part (e.g. "fetch buildings from satellites");
- a **solution** (a "pack") bundles parts into a working capability (e.g. "Flood monitoring") — what most people
  install;
- a **service** is the biggest: an outcome *run for you* over time against a service-level agreement, possibly
  spanning several packs and providers.

Parts and packs you *install*; a service is *operated for you*.

## The words you'll meet (a mini-glossary)

| the system's name | in plain words |
|---|---|
| **Airawat Stack** | the whole thing — the five horizontal layers of shared machinery |
| **layer** | one Airawat product / horizontal job: Airawat Network · **AirawatOS** (platform) · Airawat Intelligence · Airawat Governance · Airawat Interaction |
| **AirawatOS** | the *platform* layer — build · certify · install · run · registry. One layer, **not** the whole stack |
| **domain** | a field (urban, health, justice…) — a **vertical** that plugs its own vocabulary, components, models, rules, and apps into every layer |
| **component → solution → service** | the *packaging* axis: a part → an installable bundle → an operated outcome (not a layer) |
| **participant** | anyone in the network — a city, a health dept, a developer, an operator, a resident |
| **tenant** | a participant's private, walled-off workspace (its data lives here) |
| **steward** | a participant's authority over its own data — the one who signs permission slips |
| **schema** | the agreed *shape* of a kind of fact (a "building", a "flood risk score") |
| **grant** | the signed permission slip letting a component touch a tenant's data |
| **component / app / solution** | a confined worker · a screen you use · a bundle you install |
| **registry** | the record book — every fact, with history and source |
| **decision** | a recommendation a named human formally accepted, with its evidence attached |

## What's real today, and what's coming

**Working now:** the network register + signing; private workspaces; the marketplace with checked, signed packs;
installing a pack and granting its pieces permission; running them to build a domain's base layers (for cities:
maps, buildings, roads, population, heat, hydrology); the record book with history + source; and the "AI advises,
human decides" loop. The **urban** domain is the furthest along.

**Being built:** turning packs into fully self-describing installers; richer prediction and simulation; connecting
participants to share data across boundaries; the full "service run for you" tier; and more domains beyond urban.
Wherever the deeper docs say **[target]**, it's on this list.

---

*Want the rigorous version? Read the ADRs in `decisions/` for the reasoning and exact governed names, and the
specs for how each layer's contracts work.*

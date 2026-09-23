# Designing a schema (a governed noun)

*A record's schema is a contract everyone shares. Here's what to think about before you propose one.*

On AirawatOS, data isn't stored in an app's private table — it's stored in the shared registry as **governed nouns** ([the Shared Vocabulary](/developer/deep-dives/shared-vocabulary/)). A schema you propose becomes a word the whole network can read, write against, and build on. That's powerful, and it's why a little design thought up front saves a lot of pain later.

This is a checklist of the considerations, roughly in the order you'll hit them.

## 1. First — don't invent one

The best schema is often one that already exists. Before proposing, **search the catalog**. If a noun already means what you need (a `geo.building`, a `platform.case`, a `governance.recommendation`), reuse it — your data instantly interoperates with everything already built on it. Propose a new noun only when nothing fits. Studio's schema assistant will actively try to talk you into reuse; let it.

## 2. Name it well

A noun is `domain.name` — `air.quality`, `hr.leave_request`, `geo.property`. The **domain** must already be governed (it's the namespace roles and schemas hang off); if yours doesn't exist, that's a separate, deliberate step. Keep names lowercase, singular, and about the *thing*, not the app that happens to write it (`doc.document`, not `myeditor_file`). The name is forever-ish — renaming a governed noun is expensive.

## 3. Decide what *kind* of thing it is

This is the most consequential choice, because it changes how the record behaves. Declare it with `x-kind`:

The governed values are **`entity` · `measure` · `event` · `record` · `fragment`** (anything else is rejected at propose time):

- **`entity`** — a thing with a stable identity that changes over time: a building, a case, a person's document. You update it; the registry keeps every version.
- **`measure`** (often per **cell**) — a value attached to a place-and-time on the H3 grid: air quality in a cell, rainfall, population. A sensor reading is a `measure`.
- **`event`** — something that happened at a point in time: a payment, a status change. You *append* these; you don't edit yesterday's.
- **`record`** — a governed transactional/administrative object (e.g. a case, a receipt) where the row itself is the artefact.
- **`fragment`** — a reusable value-object embedded inside other schemas (not a standalone record): an address, a money amount, a credential's claims.

Getting this right up front keeps the data honest: entities accumulate history, events accumulate rows.

## 4. Give it an identity people can find

Every record's id is `ds:<tenant>:<schema>/<local>` — resolvable across the whole network. Beyond that machine id, if your noun has a **natural key** a human or another system already uses — a case number, a property PID, a GSTIN — declare an `identifiers[]` block so it can be looked up by that key. That's the bridge between "the number on the paper form" and the system record.

## 5. Decide who *owns* each row — before anything else about privacy

This is the question that most often gets skipped and most often bites. Read the [Data Ownership & Consent](/developer/deep-dives/ownership-consent/) deep dive, then choose the mode with `x-ownership`:

- **tenant** (default) — org-owned operational data (buildings, budgets, cases). Visible to the organization.
- **user** — self-authored personal content (documents, files, notes). Only the creator + people they share with.
- **subject** (+ `x-owner-field`) — data *about* a person, owned by **that person**, not whoever created it. Use this for a citizen's records, and add `x-custodian-role` so the holding agency can still operate them.

Mark a citizen's record `subject`, not `user`, or you'll accidentally hand control to the clerk who typed it. Personal work products are `user`. Everything operational is the default. This choice is enforced in the kernel, so it has to be right in the schema.

## 6. Shape it tightly

Set `additionalProperties: false` — a governed noun should be a closed, predictable shape, not a grab-bag. List the truly-`required` fields (usually just `schema`, `id`, and the one or two things that make the record meaningful); make the rest nullable. Model timestamps, references, and enums explicitly. A tight schema is one others can trust and validate against.

## 7. Think about who writes it, and how truth accumulates

Two things happen automatically, but design for them:

- **Attribution.** Every write records *who* wrote it (a person, a component, or a component acting for a person). You get provenance for free — lean on it instead of stamping "created_by" yourself.
- **Data-plane discipline.** **Fact/measure** schemas must be written by a **certified component**, not hand-typed — so real-world data always traces to code that was reviewed. Entity/governance nouns can be written by apps on a person's behalf. Decide which yours is.

And because the registry is **bitemporal**, never design around overwriting: write a new version (entities) or a new row (facts). History is a feature, not clutter.

## 8. Say where the data came from

If your noun carries data pulled from a source — a government API, a satellite product, a dataset — plan to cite it (the platform has a source/attribution catalogue). Data whose origin you can't state is data no one can trust; design the fields to carry the provenance you'll need.

## 9. If it goes on the map, it needs a display descriptor

A schema alone doesn't tell the map how to draw it. If your noun is spatial and you want it visible in City Scan, you also provide a **`viz.layer`** descriptor (colours, ranges, grouping, an explanation). Treat that as part of the deliverable, not an afterthought — a layer with no descriptor is invisible.

## 10. Govern it — and plan for change

Proposing a schema is a governed act: you **propose**, a steward **approves**, and only then is it a real noun. Version deliberately (`@0.1.0`). The safe changes are **additive** — new optional fields don't break anyone. **Breaking** changes (removing a field, tightening a type, renaming) need a new version and a migration story, because other people's components may already depend on the old shape. Design as if someone you'll never meet is already building on your noun — because on a shared network, they might be.

## The short version

> Reuse first. Name it for the thing. Pick the right *kind*. Give it a findable identity. **Decide who owns it.** Keep the shape closed. Let attribution and history work for you. Cite your sources. Draw it if it's spatial. Govern it, and change it additively.

Related: [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/) (why nouns are shared), [Working with governed data](/developer/build/governed-data/) (reading and writing them), and [Data Ownership & Consent](/developer/deep-dives/ownership-consent/) (the ownership modes).

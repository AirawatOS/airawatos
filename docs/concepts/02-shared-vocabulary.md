# The Shared Vocabulary

*Why every piece of data in the platform has an agreed shape, a known source, and a history.*

## The problem

When many different organizations and many different pieces of software all work with the same data,
they need to *mean the same thing* by the same word. If one component's idea of a "building" has a
height field and another's doesn't, they can't work together. And if a number appears on a screen with
no record of where it came from, no one can trust it enough to act on it.

AirawatOS solves this by keeping **all** data in one shared record book — the **registry** — where
every entry follows an agreed shape and carries its own history.

## Everything is a "fact"

In AirawatOS, every stored piece of data is a **fact**: an *attributable, versioned assertion*. Read
that carefully — "fact" here means **someone asserted it**, not that it is automatically, objectively
true. A rain measurement, a building outline, a prediction, a rule, even a decision — all of them are
facts in the same uniform frame.

Every fact sits inside a fixed **envelope**. The author fills in some fields; the registry stamps the
rest and won't let you fake them:

- **You provide:** the fact's type, the payload (the actual content), when it applies in the world,
  and its provenance (where it came from).
- **The registry stamps:** which tenant owns it, the exact time it was recorded, who wrote it, which
  version of the type it used, a content fingerprint, and its version number.

## The type is the shape

A fact's **type** is a **schema** — a shared, agreed shape for one kind of thing (a "flood risk score",
a "building", a "payment"). Because the type is shared and governed, a building means the same thing to
every component and every agency. You build against these shared types; you don't invent your own
private formats. When your component needs a type that doesn't exist yet, that's a governance step —
someone proposes the new shape and it becomes a shared standard, not a private one.

Types follow a simple naming grammar so they read consistently: a namespace and a term joined by a dot,
like `geo.building`. Actions (verbs) are named too, and reference fields are explicit — a field that
points at one other record ends in `_ref`, a field pointing at many ends in `_refs`.

**A worked example.** Suppose an air-quality driver records a sensor reading. The fact it writes might
carry a type of `air.sensor_reading`, a payload like `{ station: "CPCB-42", pm25: 180, unit: "µg/m³" }`,
and a valid-time of when the reading was taken. The registry then stamps the rest: which tenant owns it,
the exact recording time, that it came from the air-quality driver at version 0.2.1, a content
fingerprint, and a version number. Anyone reading it later gets not just "180" but *who measured it,
when, and how it got here.* A "court hearing" fact or a "welfare payment" fact has a different payload
and a different type — but the exact same envelope around it. One frame, every kind of data.

## Provenance: where every fact came from

Every write records its **provenance** — the story of how the fact came to exist:

- the **method** (was it reported, observed, imported, or *computed/derived* from other facts?),
- who **asserted** it,
- and for anything derived, **which facts it was derived from** and **which run produced it**.

This is what makes a number on a screen traceable all the way back: a dashboard value → the engine that
computed it → the exact inputs and the exact code version. Nothing is a mystery blob. (Every write is
also stamped with its author by the broker — see
[Zero-Trust Architecture](/developer/deep-dives/zero-trust/).)

**A worked example.** A flood-risk score for an area is a *derived* fact. Its provenance says method
`derived`, names the engine that computed it, and lists the facts it was derived from — the rainfall
forecast and the terrain data, each at a specific version. So if someone questions the score, you can
follow the trail: this score came from that engine, using this rainfall forecast (from that weather
driver, at that hour) and this elevation data. Re-run the same engine on the same inputs and you get the
same score. That is what "reproducible" means in practice.

## History is never erased

The registry keeps history. A correction never overwrites what came before — it records a new version
and marks the old one as superseded. This gives the platform two guarantees it treats as
non-negotiable:

- **Reconstructability** — you can always explain a past decision using the facts, rules, and software
  versions that existed *at that time*. A correction made in 2030 must not silently rewrite what an
  officer actually saw in 2027.
- **Learnability** — new evidence can improve future models, rules, and vocabulary *without* rewriting
  the historical record. As the design phrases it: "learning proposes; governance and certification
  admit."

To make this precise, each fact tracks up to three separate clocks: when the observation was made, when
the asserted state applies in the world, and when the registry recorded it. Concretely, that CPCB-42
sensor reading might be **taken at 08:00** (observation time), **apply to the 08:00 hour** (valid-time
in the world), and be **recorded at 08:05** (the registry's transaction time) — three distinct
timestamps on one fact. That's what lets the registry answer both "what do we believe now?" and "what
did the record say at the moment of that decision?"

## Writing data, in practice

For a developer, working with governed data is straightforward: you read and write facts through the
registry, and you supply a natural key so that re-running the same job **updates** rather than
duplicates (writes are idempotent). On every write the registry validates your payload against the
schema, checks your permissions, binds it to your tenant, stamps the un-fakeable metadata, and records
a new version instead of mutating the old one.

## The vocabulary is itself governed

The list of types isn't code baked into the platform — it's **data**. The network publishes a signed,
versioned catalogue of schemas; each deployment pulls it, verifies the signature, and applies it. Even
the controlled lists behind the naming rules (the valid domains and facets) are registry records, read
at runtime. Changing the vocabulary is a curated, approved write — never a silent edit and never a
redeploy. How that approval works is the subject of
[Governance & Decisions](/developer/deep-dives/governance/).

## Where this stands today

**Working now:** the registry itself — typed storage, idempotent versioned writes, a per-record
provenance envelope, multi-tenant isolation, and the append-a-new-version-never-overwrite timeline; and
the signed, published schema catalogue that each deployment syncs (with the first-party commons schemas
already bootstrapped).

**Being built / evolving:** the full propose→review→approve workflow for changing the vocabulary is
partly in place and partly still maturing; a content fingerprint on *every* single write path, and a
decision receipt on *every* recommendation, are designed but not yet emitted everywhere. Some older
naming (like putting the map grid in the type name) is being migrated to the current grammar, so you may
see both old and new names in live data during the transition.

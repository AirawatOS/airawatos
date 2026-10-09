# AirawatOS Documentation

The single home for how AirawatOS works — the source the book is written from.

## Structure

- **`decisions/`** — Architecture Decision Records (ADRs): the *why* behind each design choice, at the
  point it was made. Authored natively for AirawatOS; numbering continues from the legacy AirOS series
  (0062+). See [`decisions/index.md`](decisions/index.md), which also tracks the **migration backlog** of
  legacy AirOS ADRs (0001–0061) to be rewritten for AirawatOS.
- **`specs/`** *(to be migrated)* — the **normative** reference: *how it works*. The legacy normative specs
  (00 protocol, 01 registry, 03 driver, 11 engine, 14 decision, 15 app, 16 runtime, glossary) live in
  `AirOS/specs/` and are being rewritten for AirawatOS. These are the book's reference chapters.

- **Operations** — [`deployment-requirements.md`](deployment-requirements.md): what to provision to run a
  pilot (one Docker host; server spec, OS, stack, network, access). Cloud-neutral, with notes for the
  DJB / Oracle Cloud engagement.

## The book — how the pieces map

The book explains AirawatOS to a reader who has never seen it. Two layers feed it:

- **Reference chapters** come from `specs/` — the contracts, normative and implementation-agnostic.
- **Rationale / design narrative** comes from `decisions/` — why the system has the shape it does, what
  was rejected, and what each choice bought.

As we build, every load-bearing decision is captured as an ADR here **before or with** the code, and the
normative consequences are reflected into the relevant spec chapter. Nothing important should exist only
in code or only in a commit message — if it shapes how AirawatOS works, it is written down here.

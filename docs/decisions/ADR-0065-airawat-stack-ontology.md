# ADR-0065 — Adopt the Airawat Stack ontology (v3): five layers · two constitutional guarantees · the decision receipt · the circulation

- **Status:** Proposed (2026-08-23; revised 2026-08-24 to adopt ontology **v3**)
- **Deciders:** Airawat (platform steward), product owner
- **Supersedes:** ADR-0055 (layered reference architecture — the earlier six-layer model with `domain` as a
  horizontal layer).
- **Composes / absorbs:** ADR-0022 (everything-is-a-component → one certify spine), ADR-0025 (signed schema
  catalog), ADR-0038 (spec governance / the change loop), ADR-0058 (interfaces = the verb leg), ADR-0062/0063
  (invoke + govern-the-verbs), ADR-0060 (L0–L4 ladder), ADR-0029/0046 (decision spine + hourglass → the
  **decision receipt**), ADR-0017 (envelope · resolvable ids · signed facts), ADR-0052 (attributed writes),
  ADR-0041 (lineage & confidence → provenance envelope), ADR-0026 (agent delegation), ADR-0049 (verifiable
  credentials → `credential.verifiable`), ADR-0064 (solution-driven activation).
- **Faces:** [`the-story.md`](../the-story.md) is the plain-language face; [`ontology.md`](../ontology.md) is the
  precise face (v3, §§1–117). This ADR records the *decision* to adopt them as the reference model, and the
  migration path.

## Context

The system grew a rich set of ADRs but no single, coherent model of *what it all is*. ADR-0055 gave a first cut —
six horizontal layers including `domain` — but successive focused design passes (captured in `ontology.md`,
now at **v3**) refined it substantially and, more importantly, made it **internally consistent**, **generative**
(you can derive where a new concept belongs rather than argue it), and **machine-checkable** (the naming and
layering rules are mechanical). This ADR adopts **ontology v3** as the foundation everything else is read against.

**What v3 changed from the earlier drafts this ADR first recorded.** The first version of this ADR described the
model as "four atoms · **three templates** · the circulation." That framing is now wrong in two ways, and the
headline claim has moved:

- The **purpose** is stated as two constitutional guarantees — *reconstructability* and *learnability* — with the
  **decision receipt** as the load-bearing artifact. This is the spine v3 is built around; it was implicit before.
- There are **two universal envelopes, not three templates**: `network.fact` and `network.interaction`.
  `network.definition` is **not** a third persistence envelope — it is the metamodel payload; a definition is a
  fact whose `schema = network.definition`.
- The type system is **three meta-relations** (`x-specializes` / `x-has-facet` / `x-realizes`) plus the rule that a
  fact's `schema` field *is* its instance relation (no persisted `x-instance-of`).

## Decision

Adopt the **Airawat Stack ontology v3**. Its load-bearing claims:

1. **Two constitutional guarantees.**
   - **Reconstructability** — every consequential decision must be reproducible from *version-pinned* references to
     the evidence, rules, authority, process, recommendations, models, and software executions **as they existed at
     the time**. Current truth and historical decision context are separately queryable (bitemporal registry).
   - **Learnability** — outcomes, appeals, corrections, audits, and usage improve the *future* language, machinery,
     intelligence, governance, and interactions **without rewriting history**. *Learning proposes; governance and
     certification admit.*
2. **The decision receipt is the accountability spine.** Every consequential `governance.decision` seals a
   `governance.decision_receipt` — a durable, immutable, signed reconstruction manifest (`evidence_manifest[]`,
   `rule_manifest[]`, `process_manifest`, `run_refs[]`, `finding_manifest[]`, `discretion_manifest`) pinning exact
   versions/hashes. Corrections *supersede*; they never erase (a 2027 receipt survives a 2030 review).
3. **Four semantic primitives.** `fact · verb · role · rule`, defined once at Network (`network.schema` ·
   `network.interface` · `network.role` · `rule.*`). A rule is itself a fact. Everything above is a composition.
4. **Two universal envelopes + the metamodel payload.** `network.fact` (the base — id · schema · valid_time ·
   prov · confidence? · signature? · payload, plus a registry-stamped half) and `network.interaction` (verb-typed
   exchange). `network.definition` is the metamodel payload, **carried by** `network.fact` — so definitions, rules,
   predictions, decisions, and receipts are *all* facts. Semantic schemas are **carried by** the envelope, never
   `x-specializes` it.
5. **Three meta-relations + the instance rule.** `x-specializes` (is-a, only between semantic contracts),
   `x-has-facet` (has-this-aspect), `x-realizes` (implementation → capability); a fact's `schema` field is its
   instance relation.
6. **Five horizontal layers, one vertical.** **Network → AirawatOS → Intelligence → Governance → Interaction**
   are the horizontal *machinery* layers; a **domain** (urban, health, justice…) is a **vertical** that cuts
   *across* all of them. **AirawatOS is one layer (the platform), not the umbrella.** *(This is the substantive
   change from ADR-0055.)* The **epistemic/normative boundary** is the seam between L3 and L4: Intelligence changes
   what is *believed*; Governance changes what is *institutionally binding*. Intelligence never creates authority;
   deterministic computation is not Intelligence.
7. **Strict downward dependency, machine-checkable.** A schema owned by layer L may reference/specialize/require
   only concepts from L or below (`Interaction → Governance → Intelligence → Platform → Network`). This is a lint
   rule, not a guideline.
8. **The circulation.** Two triggers (a party interacts, or the world changes → optionally an `intelligence.signal`)
   → governed attention → a **case** where handling is required → *evidence + rules + authority* → **decision** →
   **receipt** → order/commitment → act → observe → **learn**. Intelligence is not mandatory middleware; a
   deterministic rule can trigger Governance directly.
9. **A governed naming grammar.** `<namespace>.<term>`; a dot descends into an attribute
   (`platform.component.kind`), an underscore joins a compound term (`governance.decision_receipt`); and every
   governed reference field is explicit — `foo_ref` (one) / `foo_refs[]` (many) / bare `foo` (embedded/value). No
   field mixes reference and value semantics; nothing `x-specializes` an envelope; no upper-layer dependency.
   These are the **ontology lint rules** (ontology §111).
10. **Every layer is a learning loop.** Network (proposals + trust evidence), Platform (conformance + corrections
    + telemetry), Intelligence (predictions vs outcomes), Governance (audit → rules; appeals → corrections),
    Interaction (feedback + demand). Not static shelves — self-improving, but always through governed admission.

## Consequences

- **A generative *and* enforceable reference.** New concepts are *placed*, not argued — run the layering + naming
  rules. The lint rules (ontology §111) and the target machine-checkable metamodel (ontology §117) turn "where does
  this belong / is this named right" into a check, not a debate.
- **`the-story.md` + `ontology.md` (v3) become canonical**, feeding the book (ADR-0055's role, now fulfilled).
- **The decision receipt becomes a build target**, not just a principle — it is what makes reconstructability an
  institutional guarantee (ties off ADR-0029/0046).
- **The verb leg has a home.** `network.interaction` is the exchange template; ADR-0063's "govern the verbs" work
  is where the code catches up to it.
- **Renames are owed** (see below) — the model uses cleaner names than the running code; those are governed schema
  renames, done through the change loop (ADR-0056), not silent edits.

## Migration — reconciliation with the code

The running system predates this model and uses different names for several nouns. The **ordered migration list
lives in `ontology.md` §114 ("Migration Priorities")** and is the bridge artifact. Highest-leverage first:
`signal.alert → intelligence.signal`; `governance.recommendation → intelligence.recommendation`; `platform.case →
governance.case`; `platform.task → governance.task`; drop `platform.inbox_item` (inbox is a *view*); `component →
platform.component | platform.app | platform.solution`; `marketplace.component → marketplace.listing`; then
**introduce `governance.decision_receipt`** as the reconstructability artifact. Each rename is a **decided
change-request** (ADR-0056) against a governed schema — propose → approve → publish, with a compatibility window,
not a find-and-replace.

## Slice plan

1. **Adopt** — merge `the-story.md` + `ontology.md` (v3) as canonical; retire ADR-0055's horizontal-`domain`
   framing.
2. **Lint the grammar** — wire ontology §111 into the schema-publish path (naming grammar, `_ref`/`_refs`,
   no-envelope-specialization, no-upper-layer-dependency), regenerating the linter vocabulary from `network.domain`.
   *(Builds on task #36.)*
3. **Rename in tranches** — the §114 order, highest-leverage first, each a governed change-request with a compat
   window.
4. **Introduce the decision receipt** — `governance.decision_receipt` schema + seal-on-finalize + completeness
   rules (`rule.decision_evidence` / `_authority` / `_process` / `_reason`), on the existing decision spine.
5. **Machine-checkable metamodel** *(ontology §117, [target])* — grow the lint into a validator that rejects an L2
   schema referencing `governance.decision`, a schema specializing `network.fact`, a derived fact without lineage,
   a consequential decision without a receipt, an ambiguous ref field, an incompatible specialization.

## Non-goals

- **Not a re-implementation.** This is the reference model + the migration target, not a rewrite order.
- **Not a big-bang rename.** Renames are governed, staged, back-compatible.
- **Not the execution engine** (ADR-0050) or solution-driven activation (ADR-0064) — those build *on* this model.

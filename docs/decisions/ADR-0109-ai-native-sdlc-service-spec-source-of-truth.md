# ADR-0109 — AI-native SDLC: the Service Specification is the source of truth

- **Status:** Proposed (2026-10-04)
- **Builds on:** [[ADR-0044]] (Solution Architect agent), [[ADR-0058]] (interaction contracts as first-class specs), [[ADR-0090]] (interface bindings + conformance), [[ADR-0088]] (rule engine), [[ADR-0067]] / [[ADR-0097]] (service + one interaction spine), [[ADR-0076]] (solution anatomy, document-first), [[ADR-0045]] / [[ADR-0106]] (solution = declaration / deploy), [[ADR-0041]] (lineage & confidence), [[ADR-0038]] (spec governance), [[ADR-0022]] (everything-is-a-component certify spine)
- **Relates to:** [[ADR-0108]] (verb naming), [[ADR-0056]] (decided change-request), the `aos` build SDK (code-is-source-of-truth / derived meta)

## Context

The industry is shifting from "humans write code with AI assistance" toward an **AI-native / spec-driven SDLC**: humans author **intent, constraints, architecture and acceptance criteria**; agents **plan → decompose → code → test → validate → iterate**; and the **specification becomes a living, executable source of truth** that code is continuously reconciled against (GitHub Spec Kit's *Specify → Plan → Tasks → Implement*, Kiro's requirements/design/tasks, etc.).

The hard problem is **not** code generation. It is three things:
1. making the specification **machine-actionable** (not a prose document that rots),
2. keeping the implementation **reconciled** to it,
3. doing both **reliably on a regulated, non-greenfield system**.

Generic spec-driven development on an unconstrained repo hits the well-known walls — specification completeness, architectural divergence (many implementations satisfy the same functional spec), under-specified non-functionals, and **impl-and-test sharing the same misunderstanding** because one agent wrote both.

**AirawatOS is unusually well-positioned**, because the machine-actionable layer already exists and is *governed*: schemas (nouns), interaction contracts ([[ADR-0058]]), workflow / lifecycle declarations, policy rules ([[ADR-0088]]), roles (`network.role`), the one interaction spine ([[ADR-0097]]), conformance suites ([[ADR-0090]]), provenance/lineage ([[ADR-0041]]), and a generate→certify→publish pipeline (the Solution Architect, [[ADR-0044]]). We are most of the way to the substrate the industry is reaching for.

Three things are missing, and one tension is unresolved:
- **Missing:** a single authored umbrella — the **Service Specification** — that composes the governed pieces; **spec↔implementation traceability**; and an **explicit constitution**.
- **Tension:** the `aos` SDK just moved to *code is source of truth, meta derived from code* (code-first) — the opposite of spec-first generation. This ADR resolves that tension rather than leaving it implicit.

## Decision

### 1. The Service Specification is a first-class governed object
Introduce `platform.service_spec` — the primary human-authored artifact for a civic service. It **references, does not duplicate**, the governed pieces already in the registry:

```
Service Specification
├── Domain schema(s)          (governed nouns)
├── Registry references       (what it reads/joins)
├── Roles                     (network.role)
├── Eligibility / business rules  (governance.policy_rule — ADR-0088)
├── Workflow / state machine  (platform.workflow — ADR-0097)
├── Documents / credentials   (ADR-0049 wallet/VCs)
├── Fees                      (service fee quote — ADR-0067 S5)
├── SLAs
├── Events emitted            (ADR-0089)
├── Privacy rules
└── Acceptance criteria       (conformance suite — ADR-0090)
```

It is versioned, certifiable, portable across tenants, and is the **input to generation** and the **anchor for reconciliation**.

### 2. Stratified source-of-truth (resolves spec-first vs code-first)
We do **not** pick one globally. We stratify:

| Layer | Source of truth | Direction |
|---|---|---|
| Service / interaction (schemas, interfaces, workflow, rules, roles) | **the Specification** | spec-first — generate down |
| Component internals (engine/driver code) | **the code** | code-first — `aos check` derives meta |
| Between them | **conformance** ([[ADR-0090]]) | reconciliation seam |

Conformance is the seam because the **spec and the check come from different authorities** (the governed contract vs the certify suite). That is our structural answer to the "impl and test share the same misunderstanding" risk: they cannot, by construction.

### 3. The Constitution, made explicit
Promote the implicit house-rules into a **versioned, machine-inherited `constitution`** that every generation agent is bound by and that certify enforces: audit-every-write, privacy/PII handling, governed-vocabulary-only, the verb grammar ([[ADR-0108]]), async-where-possible / event-on-state-change ([[ADR-0089]]), OIDC-mandatory, accessibility ([[ADR-0077]]), no-synthetic-data, source attribution. Today these are enforced ad hoc at certify; make them an **authored governance artifact** the agent reads as inherited context.

### 4. The traceability graph (the regulated-sector differentiator)
Because every governed object already carries a `ds:` id (rule, interface, schema, component, decision, test), wire `prov.derivation` ([[ADR-0041]]) links so the chain is queryable end to end:

```
Policy requirement → Business rule → Feature → Acceptance criterion → API/interface → Code → Test → Deployment
```

Target queries: *"show me the code implementing Rule PT-37"* and *"which regulatory requirement has no corresponding test."* No low-code platform offers this; it is mostly **connecting ids we already mint**.

### 5. The generation + reconciliation loop
Extend the Solution Architect ([[ADR-0044]]) from *description → graph* into the full loop:

```
Service Spec → generate(schemas, interfaces, workflow, engine, app, tests) → certify → reconcile
```

Add a **reconciliation check** that diffs the running implementation against its spec and raises a **decided-change-request** ([[ADR-0056]]) on drift — closing the feedback loop (telemetry / new requirements re-enter the spec) rather than being one-way.

### Why AirawatOS is the right substrate (not Spec-Kit-on-a-blank-repo)
Generic spec-driven dev generates into an unconstrained space, which is why it hits the completeness / architecture / verification walls. AirawatOS generates into a **narrow, governed, independently-checkable** space: governed vocabulary + certified components + one interaction spine + conformance. The constraint is the feature. This is the concrete realization of the idea that **the platform becomes the constrained execution substrate while the Service Specification becomes what humans author.**

## Slices

- **S1 — `platform.service_spec`**: govern the schema + a Studio authoring surface that composes the existing governed pieces (ADR-0067 service + ADR-0076 anatomy are ~80% of it).
- **S2 — Traceability graph**: `prov.derivation` links across rule / interface / schema / component / decision / test ids + a query endpoint and a Studio view.
- **S3 — Constitution**: author it as governed data, bind the generation agent to it, enforce at certify.
- **S4 — Proving slice (Property Tax)**: reverse-author the Property Tax Service Specification from the already-built Tax Gap Finder implementation; run spec → generate → certify → reconcile; demonstrate the traceability queries; diff the generated service against the live one. This makes the distinction between **today's low-code configuration** and **true spec-to-system generation** undeniable — on a service we can check, not a toy.

## Consequences

- **+** Human effort moves upstream (domain modelling, constraints, invariants, acceptance); agents absorb implementation, tests, migration, repetitive integration. Good architecture becomes **more** valuable, not less.
- **+** Regulated-sector traceability: audit, procurement and compliance become **spec-anchored** ("which requirement lacks a test").
- **+** Portability: a governed Service Spec is tenant-independent; generation re-targets per operator.
- **+** Risk mitigation is structural: the constrained substrate blunts the completeness / architecture / verification failure modes.
- **−** Real build: the `service_spec` object, traceability wiring, and constitution authoring are new work.
- **−** Discipline required: generation must **always** pass through certify/conformance — no ungoverned bypass — or the guarantees evaporate.
- **Risk:** over-promising "author a spec → get an app." S4 must show the human-in-the-loop reality honestly (specification completeness and architecture choice remain human judgment).

## Non-goals
- Replacing the `aos` code-first inner loop for component internals (it stays; see §2).
- A universal natural-language-to-system claim. The spec is structured and governed, not freeform prose.

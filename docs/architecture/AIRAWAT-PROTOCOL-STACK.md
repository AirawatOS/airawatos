# Airawat Protocol Stack & Airawat Stack — working architecture note

> **STATUS: DRAFT / working architecture note — NOT a normative specification.**
> This note captures a *working concept* so we can refer to it and evolve it. It does **not** change any
> existing ADR or specification semantics, does not rename any component, and does not alter implementation
> code. Where the terminology proposed here conflicts with terms already in use, the existing terminology is
> preserved and the conflict is flagged in **[Open terminology questions](#open-terminology-questions)** and
> **[Open questions](#open-questions)** below — not silently rewritten.
>
> Date: 2026-11-02 · Scope: concept + vocabulary, pre-decision.

---

## 1. The two names

**Airawat Protocol Stack** — a *family of interoperable specifications*. The protocols and data contracts that
define how an Airawat-style trusted network behaves, independent of any one codebase. A specification says
*what* must be true (objects, operations, invariants, wire contracts, conformance criteria), not *how* it is
built.

**Airawat Stack** *(in the sense proposed by this note)* — the *reference implementation* of the Airawat
Protocol Stack: the concrete kernel, network runtime, SDKs, and apps in this monorepo that implement the
specifications and are validated against their conformance suites.

> ⚠️ **Terminology conflict (do not adopt yet).** "Airawat Stack" is **already defined** in the canonical docs
> (`docs/ontology.md` "The Airawat Stack — Ontology v3"; `docs/the-story.md`) to mean *the five horizontal
> capability layers / the whole platform* — **not** "the reference implementation." Adopting the meaning in
> this note would redefine an established term. See [Open terminology questions](#open-terminology-questions).
> Until resolved, read "Airawat Stack (reference implementation)" explicitly wherever this note uses it.

The long-term point of separating the two: **another organization should be able to implement the Airawat
Protocol Stack and interoperate with the Airawat Stack (reference implementation)** — different code, same
protocols, able to exchange trust, data, requests, and events.

---

## 2. Specification vs conformance suite vs reference implementation

Three distinct artifacts, deliberately not conflated:

| Artifact | What it is | Authority |
|---|---|---|
| **Specification** | the normative contract — objects, operations, invariants, wire formats | the standard |
| **Conformance suite** | executable tests any implementation must pass to claim conformance | the proof |
| **Reference implementation** | one conformant codebase (this repo) | an existence proof, not the standard |

A reference implementation is *an* answer, not *the* answer. A behavior is normative only if it is in the
specification and checked by the conformance suite — never merely because the reference implementation does it.

There is prior art for this shape in-repo: the Trust-plane contract harness
(`network/trust/contract/`) already separates a spec-like set of invariants from the kernel that implements
them and runs them against a real kernel; the service test suite (`github.com/AirawatOS/tests`, black-box) is
an early conformance-suite shape. These are seeds, not a finished conformance program.

---

## 3. Initial working specification family (Airawat Protocol Stack)

Proposed members. Names are working titles; each needs its own spec document and conformance suite over time.

| Specification | Scope (what it standardizes) |
|---|---|
| **Airawat Registry Specification** | the bitemporal, authenticated, attributed object registry: put/query/resolve wire contract; PROV object kinds; supersede-on-write; strict schema validation; tenant/steward scoping |
| **Airawat Decision Specification** | the decision lifecycle + its trace: facts + rules → recommendation → named-authority decision, with evidence bound and an immutable, attributable trail (provenance/receipts) |
| **Airawat Network Specification** | membership/participation, classifications, stewardship roles, capability catalog + grants, identity sources + assurance, directory/resolution, service offerings + exchange — i.e. what makes a *network* a governed trust boundary |
| **Airawat Account Specification** | the aggregated consumer/citizen account: a stable, network-independent account identity, handles/aliases, links-by-reference to external service accounts, wallet/credential holding, find-or-create/de-duplication by authoritative identity |
| **Airawat Participant Protocol** | how a *provider* participant integrates: authenticate, register/manage services + offerings, receive and fulfil requests, publish/subscribe events, exercise capability grants, expose health/conformance |
| **Airawat Client Protocol** | how a *consumer-facing* client (an embedding app) integrates: citizen auth, offering discovery, request creation, credential presentation/verification |

Candidate future standalone specs — **candidates, not decisions** — are listed in [§7](#7-candidate-specs-not-decisions).

---

## 4. Reference-implementation mapping (Airawat Stack → specs)

How today's code maps onto the proposed specs. "Partial/absent" is stated honestly; this is a map of intent,
not a claim of completeness. (See the TNP end-to-end assessment,
`network/trust/migration/TNP-END-TO-END-ASSESSMENT.md`, for the detailed status.)

| Specification | Reference implementation today | Maturity |
|---|---|---|
| Registry Spec | **Airawat Kernel Registry** (`kernel/` — `registry_version`, bitemporal put/query/resolve, strict validation, P0 authz gate, ADR-0052 attributed writes) | **implemented** |
| Decision Spec | **Airawat Kernel decision/trace capabilities** — W3C-PROV attributed writes (ADR-0052), lineage/confidence (ADR-0041); **plus** the Governance decision spine (ADR-0029/0046, `governance.decision`) which today lives above the kernel, in the platform/network layer, not in the kernel itself *(boundary to resolve — see Open questions)* | **partial / split** |
| Network Spec | **AirawatOS Network runtime** (`network/` — the federation authority: directory, participation/joins, offerings/exchange, and the ADR-0119 Trust plane: `network.network`/membership/classification/role_assignment/capability_grant) | **implemented (legacy) + Trust plane shadow** |
| Account Spec | **future AirawatOS Account runtime** — does not exist yet; today an "account" is collapsed into an IdP `sub` + a holder-filtered credential query (no Account object, handle, or service-link) | **not built (design-required)** |
| Participant Protocol | **Airawat Participant SDK** — the `aos` Build SDK (`components/_common/aos/`): engine/driver/connector authoring, broker I/O, connector warm-serve, Blueprints deploy, CLI | **partial (P1 prototype)** |
| Client Protocol | **Airawat Network Client SDK** — the participant-embed SDK (ADR-0112, served at `/embed/sdk.js`): citizen auth (OIDC+PKCE), discover, request, wallet/proof | **partial (S1)** |

---

## 5. Layering (proposed runtime view)

Proposed top-to-bottom runtime layering for the reference implementation:

```
  Experience / Application      — apps, maps, inboxes, consoles, embedding client apps
  Network / Domain platform     — the governed trust boundary + domain configurations on top of it
  AirawatOS                     — build · certify · sign · publish · install · run · the platform services
  Kernel / Foundation           — the domain-blind registry + trust/validation primitives
  Infrastructure                — compute, storage, Postgres, Vault, networking
```

> ⚠️ **This differs from the established layering.** `docs/the-story.md` / `docs/ontology.md` define the
> **five horizontal capability layers** as **Airawat Network · AirawatOS · Airawat Intelligence · Airawat
> Governance · Airawat Interaction** (a capability decomposition, with Network at the *bottom*), and ADR-0119
> defines the **four planes** (Trust · Knowledge · Governance · Exchange). The runtime layering above is a
> *different axis* (infra→kernel→OS→network→experience) and must be reconciled with — not substituted for —
> those models. See [Open questions](#open-questions).

### 6. The kernel stays domain-blind

A load-bearing principle, and one already stated in-repo (`domain-blind` appears across the docs and in the
layering ADRs): the **Kernel/Foundation knows nothing about any domain.** It stores, validates, scopes, and
attributes governed objects; it does not know what "water" or "justice" or "livelihood" mean. All domain
meaning — vocabulary, rules, models, apps — is supplied *above* the kernel, as governed configuration and
components. This is what lets one kernel serve every domain and every network without change, and what keeps
the specifications domain-neutral.

---

## 7. Candidate specs (NOT decisions)

These may or may not become standalone specifications. Listed as **candidates** to track the question, not to
pre-decide it. Each currently exists as design and/or partial implementation under other ADRs.

- **Airawat Events Specification** — a public event/subscription contract (today: ADR-0120 event plane + ADR-0089 event/message spine, PROPOSED; no public `/v1/events`).
- **Airawat Credentials Specification** — verifiable-credential issue/verify/revoke + presentation + wallet-provider interface (today: ADR-0049 wallet/VC, ADR-0117 credential-&-services network; credential service LIVE, wallet-provider interface design-only).
- **Airawat Policy / Requirements Specification** — requirement/eligibility expressions + a policy/rule evaluator (today: ADR-0088 rule engine; `RequirementExpression`/`eligibility_ref` declared but not evaluated).
- **Airawat Trust Federation Specification** — cross-network/cross-operator trust, root-of-trust, an authorized-network directory (today: ADR-0119 Trust plane in-network; cross-network root-of-trust is only a `governance_tenant` hook — design-required).

Marking these as candidates keeps the initial spec family (§3) small and buildable while leaving room to split
these out when their contracts stabilize.

---

## 8. Domain Networks are configurations, not new OSes

A **Domain Network** — Livelihood, Health, Education, etc. — is a **configuration/extension of the Airawat
Network Specification**, not a separate operating-system implementation. It plugs domain vocabulary,
classifications, roles, capabilities, offerings, rules, and apps into the *same* Network runtime and the *same*
domain-blind kernel. This matches the existing position that a domain is a **vertical that cuts across the
layers** (`docs/the-story.md`) and that an "Avsar-class" credential-&-services network is "purely a
configuration" (ADR-0117). "Livelihood Network" ≈ the Airawat Network Spec + a Livelihood configuration, run on
the Airawat Stack — not a fork of it.

---

## 9. Long-term interoperability objective

The reason to maintain the specification/implementation split at all:

> A second, independent implementation of the **Airawat Protocol Stack** should be able to interoperate with
> the **Airawat Stack (reference implementation)** — exchanging participants, trust assertions, governed data,
> service requests, and events — by conforming to the specs and passing the conformance suites, without sharing
> any code.

This is an objective to design *toward*, not a claim about today. It is the test that keeps each spec honest:
if a behavior cannot be specified and conformance-checked independently of this repo, it is not yet a protocol —
it is an implementation detail.

---

## Open terminology questions

Short list of proposed-vs-existing term conflicts to resolve **before** any of this is adopted normatively.
Existing meanings are preserved here; nothing above renames or redefines them in code or ADRs.

1. **"Airawat Stack"** — *already means* the five horizontal capability layers / the whole platform
   (`docs/ontology.md`, `docs/the-story.md`, ADR-0117). This note proposes it mean *the reference
   implementation of the Protocol Stack*. **Direct conflict.** Options: keep "Airawat Stack" = the layered
   platform and use a distinct term for the implementation (e.g. "Airawat Reference Implementation" /
   "Airawat Reference Stack"); or redefine deliberately with a migration of the existing docs. **Unresolved.**
2. **"Protocol Stack"** — currently unused in docs (0 hits), so no conflict; free to adopt for the spec family.

## Open questions

Material inconsistencies between this proposed model and existing ADRs/spec files, for later resolution:

- **"platform-spec" is the reference implementation, not the specs.** The repo named `platform-spec/`
  (`platform-spec/reference/` — app_host, identity, governance seed) is a *reference implementation*, despite
  the "-spec" name. This note's "Airawat Protocol Stack" is the thing that name implies but that repo is not.
  Naming to reconcile: spec documents vs `platform-spec` the code repo.
- **Kernel vs AirawatOS boundary.** Existing docs treat "AirawatOS" as the platform layer that *includes* the
  registry (`docs/the-story.md`: "store every fact in a record book" under AirawatOS), while this note (and the
  layering ADRs / ADR-0031 layering kernel·specs·distros) separate a **Kernel/Foundation** (registry + trust
  primitives) *below* AirawatOS. The Registry Spec → Kernel mapping assumes the latter. Boundary needs an
  explicit, single definition.
- **Decision trace / provenance.** The "Airawat Decision Specification" spans two things today that live in
  different places: the kernel's **attributed/bitemporal provenance** (ADR-0052 W3C-PROV, ADR-0041 lineage) and
  the **Governance decision spine** (ADR-0029/0046 `governance.decision`, which runs *above* the kernel). The
  phrase "decision trace" is new (0 hits); existing terms are "decision spine", "provenance", "receipt",
  "audit". The spec must say which half is kernel-level (domain-blind provenance) and which is network/platform-
  level (the decision lifecycle), consistent with §6.
- **Network vs federation.** "federation" is used heavily (40+ docs); the `network/` service is literally the
  "MDK federation authority (SPEC-0006)". "Airawat Network" is simultaneously (a) the *bottom capability layer*
  in the-story.md, (b) the *federation authority service*, and (c) the proposed **Network Specification**. Three
  senses of one word — needs disambiguation in the spec.
- **SDK / public-protocol terminology.** Existing: the `aos` **Build SDK**, the **Network Client SDK** /
  participant-embed SDK (ADR-0112), the Component SDK + broker (ADR-0030). This note adds **Participant
  Protocol** (the wire contract) vs **Participant SDK** (a client of it), and **Client Protocol** vs **Network
  Client SDK**. The protocol-vs-SDK distinction (the contract vs a library that speaks it) is new and should be
  made explicit so "SDK" stops standing in for "protocol".
- **Four planes vs layers vs this note's layering.** ADR-0119 (Trust/Knowledge/Governance/Exchange planes),
  the-story.md five capability layers, and §5's infra→experience runtime layering are three overlapping
  decompositions. They are not contradictory but they are not yet reconciled into one canonical picture; this
  note deliberately does not pick a winner.

---

*This is a living note. Evolve it in place; promote parts into real spec documents + conformance suites as
their contracts stabilize. It changes nothing normative until the open questions above are resolved.*

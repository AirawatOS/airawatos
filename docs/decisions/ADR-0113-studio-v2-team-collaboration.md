# ADR-0113 — Studio v2: team collaboration (multi-member solutions, roles, per-component ownership)

- **Status:** Proposed (2026-10-18). Design agreed with the product owner; Phase 1 scoped, Phase 2 (git) explicitly deferred. No implementation yet.
- **Builds on:** [[ADR-0035]] (solution = pinned member-graph), [[ADR-0037]] (Studio project-first developer model), [[ADR-0022]] (everything-is-a-component), [[ADR-0025]]/[[ADR-0058]] (schemas/interfaces as the governed contract), [[ADR-0090]] (interface bindings + conformance suites), [[ADR-0028]] (civic personas + RBAC; roles = governed actor vocab), [[ADR-0103]] (per-object sharing / `access.grant`), [[ADR-0056]] (decided change-request = every mutation is a reviewed CR), [[ADR-0048]] (universal Inbox & Case), [[ADR-0098]] (versioned install + lockfile), [[ADR-0083]] (Studio Git integration / git-publisher — the Phase-2 rail), INT-0004 (developer tenant + dev-token), [[ADR-0106]] (`aos` SDK deploy-to-sandbox).

## Context

Solution Studio today is designed for **one developer**. A single `studio.project` record, authored and deployed by one person into one tenant. Real civic solutions are built by **teams** — a product manager who owns the outcome, a business analyst who owns the data contract, several developers who each own components, a test engineer who gates quality, a project manager who assigns and tracks. They work **concurrently**: different members on different components, sometimes the same component, and they need to work **independently and then converge** without stepping on each other.

The naïve reading is "Studio needs a VCS, a ticket tracker, and a permissions system bolted on." That is wrong for this platform. **The hard parts of team development are already dissolved by AirawatOS's spec-first design**, and the collaboration primitives already exist as governed capabilities:

> Components communicate **only** through governed schemas and interfaces ([[ADR-0025]]/[[ADR-0058]]). Two developers building two different components are therefore **decoupled by contract** — they never touch each other's code. The merge problem that dominates ordinary team development mostly **does not arise**: agree the contract, split the components, build in parallel.

What is missing is not infrastructure — it is the **team-facing surface** over primitives the platform already has: tenants (isolation), components (unit of work), schemas/interfaces (the contract), `access.grant` (per-object sharing), change-requests (review), conformance + certification (quality gate), the versioned lockfile (integration), Inbox/Case + the Project layer (project management), and governed roles (who may do what). Studio v1 simply never exposed them to more than one person.

A second observation shaped the design. **Per-developer isolation is situational, not permanent.** When each developer owns a *different* component, they can share one workspace — no isolation needed. When every developer must build the solution *end-to-end* (a training cohort), each needs a full, isolated copy. The design must serve both without two mechanisms.

## Decision

Build **Studio v2** as a *collaboration view* over existing primitives. Introduce **no new isolation model, no new VCS, no new permission engine** — compose what exists. The unit of each concern:

| Concern | Unit | Backing rail |
|---|---|---|
| **Agreement** | the **contract** — schemas + interfaces | [[ADR-0025]]/[[ADR-0058]] governance, [[ADR-0090]] conformance |
| **Parallelism** | the **component** (driver/engine/app), decoupled by contract | [[ADR-0022]] |
| **Isolation / workspace** | the **tenant** | INT-0004 dev tenant + dev-token |
| **Membership & roles** | the multi-member `studio.project` | [[ADR-0028]] roles, [[ADR-0103]] grants |
| **Review / quality gate** | **change-request + conformance suite + certification** | [[ADR-0056]], [[ADR-0090]] |
| **Project management** | tasks, assignments, status | [[ADR-0048]] Inbox/Case + Project layer (dogfooded) |
| **Integration / release** | the **pinned `solution.yaml` lockfile** | [[ADR-0098]], Marketplace promotion |

### 1. The tenant is the workspace; collaboration is additive

A developer starts **solo and isolated** — their own tenant, their own solution. To collaborate, the **owner invites members**, who then see the solution **in their own Studio** and can act on it. Isolation is not a global switch; it is simply "nobody has been invited yet." This yields both required modes from **one** mechanism:

- **Team project** — one shared workspace, owner + invited members, components split by ownership. No per-developer isolation is needed when members own different components.
- **Training** — each trainee is a solo owner of their own copy, builds end-to-end, invites no one. Same machinery.

**Phase 1:** an invited member is a **user inside the owner's workspace tenant** (they sign in to the shared workspace; Studio already lists `studio.project` by the signed-in tenant, so it appears for them with no new cross-tenant plumbing). Cross-tenant membership (a member staying in their own tenant with granted access to a shared solution) is **deferred to Phase 2** with git, where it is the natural fit.

### 2. Multi-member `studio.project`: owner + roles + per-component ownership

`studio.project` already carries a `members: []` field. Studio v2 elevates it to carry, per member, a **governed project role** and, per `build` member (component), an **owner/assignee** and **status** (`draft → in-review → certified → integrated`). The solution **owner** is the project admin (invite/remove members, set component policy).

### 3. Access model: build only what you own or are granted

A member may edit/build a component only if they **own** it or hold an **`access.grant`** ([[ADR-0103]]) on it. Studio enforces this at the action level (the host already does per-action role authz on `/bridge/save`). The owner (or PM) sets, **per component**, one of:

- **exclusive** — a single owner edits; others are read-only (**default**);
- **shared** — multiple grantees may edit (see §5 on concurrency).

This directly answers "can everyone build every component, or only one?" — it is a **per-component policy**, not a global one.

### 4. Schema-first is the coordination gate

Because components couple **only** through contracts, the team **agrees the schemas and interfaces first** (the BA's responsibility), governs them, and *only then* are components assignable and buildable. The governed contract is the shared, versioned artifact that lets everyone build in parallel without reading each other's code. This is not new process — it is how the platform already works, made explicit as a project gate.

### 5. Concurrency without git: exclusive-owner avoids merge

- **Different components** → inherently parallel-safe (separate source, decoupled by contract).
- **Same component, concurrently** → Phase 1 uses **exclusive ownership by default**, with an optional **soft checkout/lock** (a member checks a component out to edit; others wait). Because there is a single editor per component at a time, **there is no merge** — which is precisely what makes deferring git safe. True concurrent divergent editing + merge is the capability git unlocks in Phase 2.

### 6. Roles as governed project personas (capability matrix)

Five project roles, governed via [[ADR-0028]], enforced by Studio's per-action authz:

| Role | Owns | May do |
|---|---|---|
| **Product Manager** | outcomes, backlog, acceptance criteria | edit goal/brief, prioritize backlog, sign off releases |
| **Project Manager** | assignments, milestones, merge gates | invite members, assign components, set per-component policy, track status, approve change-requests |
| **Business Analyst** | the contract (schemas, interfaces, taxonomy/config) | propose + own schemas/interfaces via governance |
| **Developer** | assigned component(s) | build in the workspace, open change-requests |
| **Test Engineer** | conformance + acceptance suites | author the suites that gate certification/integration |

A person may hold several roles; roles widen **who** may act, never **what** a component may write (the component's declared `writes` + kernel grants still bound that).

### 7. Project management is dogfooded, not bolted on

The team board — backlog → assigned → building → in-review → certified → integrated — is a **view over the platform's own Inbox/Case + Project layer** ([[ADR-0048]]). Assignments route as inbox items to members; approvals are change-requests ([[ADR-0056]]); status transitions are governed objects. No external tracker; the platform manages its own build the way it manages a grievance or a court case.

### 8. Integration & release

The **integrated version** is a `solution.yaml` whose every member is **pinned to a certified version** ([[ADR-0098]] lockfile). A component joins the integrated set when its change-request is approved (PM), its **conformance suite passes** (Test Engineer), and it is **certified**. Release = Marketplace promotion (dev → published). In Phase 1's single shared workspace there is no divergent-copy merge; the integrated solution is the live shared set at its current pins.

### 9. Phase 2 — git-backed branching & merge (deferred)

The owner links the solution to a **git repository**; the end-state maps **tenant → git org, solution → repo, solution owner → repo owner, each member ↔ a git collaborator**, driven by the git-publisher engine ([[ADR-0083]]) + a provider token. This is what enables real branching, concurrent divergent edits on the same component, cross-tenant membership, and pull-request merge. It is **feasible** (medium effort — mostly identity mapping + permission sync) but **out of scope for Phase 1**; the Phase-1 exclusive-owner rule is explicitly the interim that git later replaces.

## Reuse vs net-new

**Reuse (already exists, ~80%):** tenants + dev-token (isolation) · schema/interface governance (contract) · `access.grant` per-object sharing · conformance + certification (quality gate) · change-request spine (review) · versioned lockfile (integration) · Inbox/Case + Project layer (PM) · RBAC/personas (roles) · Marketplace (promotion) · `aos` deploy `--studio` (project registration).

**Net-new (the Studio v2 surface):**
1. Multi-member `studio.project` — members with roles + per-component owner/assignee + status.
2. Invite flow (owner adds a member-user to the workspace tenant).
3. Per-component access/ownership policy (exclusive / shared) + optional soft-lock.
4. Schema-first project gate (contract agreed before components assignable).
5. Team board (view over Inbox/Case/Project layer).
6. Role-aware UX (PM sees assignments; dev sees their components + CRs; test sees conformance status).
7. Integration view — the pinned lockfile as a living release-candidate with per-member version/drift.

## Build plan

- **Phase 1 — collaborate in one workspace (no git):** multi-member project + roles + invite + per-component ownership (exclusive default) + schema-first gate + team board + integration/pin view. Prove on **Water Intelligence** with a small team (PM/BA/dev/test).
- **Phase 2 — git-backed:** repo linkage, org/repo/member mapping, branch + PR merge, concurrent same-component editing, cross-tenant membership.

## Consequences

- **Positive:** collaboration ships mostly as wiring over proven rails; the spec-first architecture means parallel work rarely conflicts; one mechanism serves both team and training modes; PM is governed like everything else (full provenance); release is reproducible (pinned lockfile).
- **Costs / risks:** Phase 1 exclusive-ownership constrains two people hacking the *same* component simultaneously (accepted until git); members-as-users-in-one-tenant means the workspace tenant is the trust boundary (fine for a team that trusts each other; cross-tenant isolation waits for Phase 2); provisioning member logins + training tenants is identity/tenant provisioning (operator-run, `IDENTITY_INTERNAL`-gated).

## Phase 1 — implementation backlog (vertical slices)

Each slice is independently shippable and demoable, ordered by dependency. Grounded in the live surfaces:
`components/apps/studio/dist/index.html` (Studio SPA: `q`/`save`/`post` helpers, `newProject`, `members`),
`platform-spec/reference/app_host.py` (`_bridge_save` per-action authz, `/bridge/component-save`,
`/bridge/component-scaffold`), the `studio.project` record (`ds:<tenant>:studio/project/<slug>`, `members:[]`),
`access.grant` ([[ADR-0103]]), `platform.inbox_item` ([[ADR-0048]]), conformance suites ([[ADR-0090]]),
and the `solution.yaml` lockfile ([[ADR-0098]]).

> **Operator prerequisite (outside the slices):** provisioning member **user logins** in a workspace tenant (and
> per-trainee tenants) is `IDENTITY_INTERNAL`-gated identity/tenant provisioning — operator-run, not in-app.

| Slice | Goal (vertical outcome) | Key build | Demo / acceptance | Size |
|---|---|---|---|---|
| **S0 — roles + membership model** | the data model everything hangs off | govern 5 `studio.*` roles (role-pack, [[ADR-0028]]); extend `studio.project` → `owner`, `members:[{sub,role}]`, per build-member `{owner,status,policy}` | a project stores owner + members-with-roles; the 5 roles resolve in governance | S |
| **S1 — invite → appears in their Studio** *(headline)* | owner shares a solution; a teammate sees it | owner-only `/bridge/project-invite` writing `studio.project.members`; Studio **Members** panel (add by username, pick role) | owner adds `devB`; `devB` logs in → sees the solution in their project list with their role | M |
| **S2 — per-component ownership + access** | "build only what you own/are granted" | per build-member `owner`+`policy` (exclusive default); enforce editor∈{owner, grantee via `access.grant`, project owner/PM} on `component-save`/`-scaffold`/`doc-save`; tree shows owner badge + lock | `devB` edits only their component; editing `devA`'s returns 403 unless granted | M |
| **S3 — schema-first gate** | contract agreed before parallel build | build-members declare the schemas/interfaces they need; check those are governed; **advisory** flag first (warn), toggle to **enforce** (block "building") — the ADR open Q | a component whose schema isn't governed shows "contract pending"; BA governs `water.complaint` → it flips to "ready" | S |
| **S4 — status lifecycle + team board** | PM assigns; everyone sees state; dogfood PM | status `draft→assigned→building→in-review→certified→integrated`; assignment emits a `platform.inbox_item` to the assignee; a **Board** view (columns=status) over components | PM assigns a component → assignee gets an Inbox task → marks `building`→`in-review`; board reflects it live | M |
| **S5 — review gate (conformance + certify)** | nothing advances unverified | `in-review→certified` requires the component's **conformance suite to pass** ([[ADR-0090]]) + a **CR approved** ([[ADR-0056]]); card shows conformance status + role-gated certify | a non-conformant component can't reach `certified`; passing + PM-approved CR → `certified` | M |
| **S6 — integration view (pinned lockfile)** | the living release candidate | compute the integrated `solution.yaml` pin-set from certified versions; show per-member version + **drift** ("2 behind latest certified"); "build integrated" deploys the pinned set | integration tab shows pins + drift; emits a reproducible `solution.yaml` | M |
| **S7 — role-aware UX** | each role sees their job | thread roles through Studio: PM→assignments, dev→my-components+CRs, test→conformance, BA→contracts; prominent **Share** entry | each of the 5 roles logs in and lands on a view scoped to their work | S |

**Milestone (Phase-1 "done"):** a PM, a BA, two developers and a test engineer build **Water Intelligence**
together in one workspace — contract agreed first, components split by owner, assignments in Inbox, the board
tracking status, the review gate blocking non-conformant work, and an integration view producing a pinned
`solution.yaml`. Proves the whole model end-to-end with no Git.

**Critical path:** S0 → S1 → S2 are the backbone (model → share → ownership); S3–S7 can be built in parallel once
S0–S2 land. S1 is the earliest user-visible win (it directly answers "make it show in my teammate's Studio").

## Open questions

- Exact governed role ids (`studio.product-manager`, `studio.project-manager`, `studio.analyst`, `studio.developer`, `studio.test-engineer`?) and whether they live in a Studio role-pack.
- Soft-lock vs exclusive-only for Phase 1 (lean exclusive-only first; add soft-lock if a real need appears).
- Whether the schema-first gate is enforced (block assignment until contract governed) or advisory (warn) in Phase 1.

# ADR-0083 — Solution Studio: developer-owned Git integration & in-tenant project collaboration

**Status:** Proposed
**Relates to:** ADR-0034 (Studio authoring), ADR-0037 (Studio developer model — project-first), ADR-0044
(Solution Architect agent), ADR-0016 (Store / certification / signing), ADR-0030/0051 (broker + certified
components + sandbox tenants), ADR-0052 (authenticated, attributed registry writes — W3C-PROV), ADR-0041
(lineage & confidence), ADR-0026 (agent = signed scoped delegate), ADR-0028 (civic personas & RBAC —
`governance.role_grant`), INT-0004 (developer tenant: dev/prod isolation), ADR-0075 (solution contributions),
universal component delivery (`platform.component_asset` → filestore, digest-verified source).

## Context

Solution Studio is where developers author solutions and components inside a **developer tenant** (e.g.
`airawatdeveloper`). Two gaps have surfaced:

**1. The code developers build is not in their own version control.** A Studio project is a `studio.project`
registry record; publishing a component writes its source as a `platform.component_asset` (a digest-verified
tar in filestore) plus a catalog entry. Getting that source into Git is today a **separate, manual step** done
outside the platform. Consequences observed in practice:
- Source-of-truth drift — components that ran live but were never committed (e.g. the `deliv-proof` test driver
  existed only as a filestore asset, absent from the `components` repo until an audit found it).
- No developer-owned history, review, branching, or backup of what they built.
- Recovery of authoring state depends entirely on the platform Postgres volume.

The platform holds the source (filestore) and the authoring graph (`studio.project`), but there is no governed
bridge from those to **a Git repository the developer controls**.

**2. A Studio project has a single implicit owner; there is no way to collaborate.** Projects are created by
one developer and keyed `ds:{tenant}:studio/project/<name>`. Another developer in the *same* tenant cannot be
granted access to co-author, publish, or even view a colleague's project. Real teams need shared projects with
differentiated rights — without weakening the tenant boundary.

Both gaps share one principle: **developers should remain in control of their code and collaborate on it,
within their tenant, without the platform diluting its trust or isolation guarantees.**

## Decision

Add two related, governed capabilities to Solution Studio, both scoped strictly to a single developer tenant:

**A. Developer-owned Git integration.** A Tenant Admin binds the tenant to a Git repository they control; the
platform then mirrors every component (and its project manifest) built in that tenant into that repo, on
publish, with per-developer attribution. The developer's Git repo becomes an automatic, attributed mirror of
what the tenant produces — replacing the manual commit step.

**B. In-tenant project collaboration.** A project gains an explicit **owner** and a **role-scoped sharing**
model built on the existing `governance.role_grant` spine, so an owner can share a specific project with named
developers in the same tenant as *viewer*, *editor*, or *maintainer* — never across the tenant boundary.

### A. Git integration — the model

- **Binding (`dev.git_binding`, governed record, one per tenant).** Fields: `repo_url`, `default_branch`,
  `path_convention` (default mirrors today's layout `components/<kind>/<name>/`), `credential_ref` (a **Vault
  secret id** for a deploy key / fine-grained PAT), and `include_project_manifest` (bool). The credential is
  stored in Vault exactly like driver/camera secrets — **never stored raw in the registry, never surfaced to an
  agent or the UI**. Configured in a "Developer Settings → Git" screen; a **Test connection** action does a
  scratch-ref push to validate before the binding is saved.
- **Publisher (`git-publisher`, a certified engine — engines-as-components).** On a successful Studio
  **publish** (hooking the existing publish gate, ADR-0037/0044), it: (1) pulls the component's source tar from
  filestore by digest, (2) lays it into the repo working tree per `path_convention`, (3) commits — **author =
  the publishing developer**, message carries `component_id`, version, and the source **digest** (verifiable
  against the `platform.component_asset`), tying the commit to the attributed-write chain (ADR-0052/0041), and
  (4) pushes to `default_branch`. When `include_project_manifest` is set, the `studio.project` graph is written
  as committed JSON so the *authoring state*, not just outputs, is versioned.
- **Confinement.** All Git egress goes through the **broker** with `git_host` on the tenant's egress allow-list
  — the same confinement every outbound call uses (ADR-0030). The publisher runs as a certified runtime, not in
  the host.
- **Isolation.** A tenant can push **only** to its own bound repo with its own credential. No shared/central
  repo, no cross-tenant push. This directly realises "the developer remains in control of their code."
- **Direction.** Primary path is **platform → Git** (export/mirror). Git → platform (import / round-trip
  authoring) is explicitly deferred to a later slice.

### B. In-tenant project collaboration — the model

- **Ownership.** `studio.project` gains `owner` (the creating actor). The owner may edit, publish, delete, and
  **manage sharing**.
- **Sharing via `governance.role_grant` scoped to the project resource.** Sharing a project grants a role on
  the resource `ds:{tenant}:studio/project/<name>` to another **user in the same tenant**:
  - `studio.viewer` — read the project graph + its components (no edit, no publish).
  - `studio.editor` — edit the graph, author/modify components, run validation (no delete, no re-share).
  - `studio.maintainer` — editor + publish + manage sharing (not delete; only the owner deletes).
- **Enforcement.** The Studio app-host bridge checks the grant on every project operation (open/edit/publish/
  delete/share) against `governance.role_grant`, reusing the RBAC spine (ADR-0028) and the governed role vocab.
  Absent a grant (and not owner), a project is invisible/inaccessible — fail-closed, same posture as registry
  reads.
- **Tenant boundary preserved.** Grants may only name principals **within the tenant**. Cross-tenant sharing is
  not collaboration; it is federation/solution-contribution (ADR-0075/ADR-0023) and stays out of scope here.
- **Git interplay.** Because the repo binding is at the **tenant** level, all collaborators on a shared project
  push to the *same* tenant repo, and each commit is attributed to the individual developer who published —
  giving a shared repo with correct per-author history.

## Architecture (text figure)

```
Developer Tenant (e.g. airawatdeveloper)                         Developer's own Git host
┌───────────────────────────────────────────────┐               ┌──────────────────────────┐
│  Solution Studio (app-host)                     │               │  github.com/<dev>/<repo> │
│    ├─ studio.project  (owner + role_grants) ────┼──[B] RBAC     │   components/<kind>/<n>/  │
│    │      share → governance.role_grant         │   check       │   projects/<name>.json    │
│    │        (viewer|editor|maintainer, in-tenant)               └──────────▲───────────────┘
│    └─ PUBLISH ──gate──► platform.component_asset │                          │ push (author=dev,
│                              (source tar, digest)│                          │  msg=id+ver+digest)
│                                    │             │                          │
│   dev.git_binding (repo_url, branch,│            │        ┌─────────────────┴──────┐
│     path_convention, credential_ref─┼─► Vault    │        │  git-publisher ENGINE  │
│     include_project_manifest)       │   (secret) │        │  (certified component) │
└─────────────────────────────────────┼───────────┘        │  filestore→worktree→   │
                                       └── on publish ──────►│  commit→push (broker   │
                                                             │  egress: git_host)     │
                                                             └────────────────────────┘
```

## Rollout (slices)

- **S1 — Bind & authorise.** `dev.git_binding` schema (governed) + Vault-stored credential + Tenant-Admin
  "Developer Settings → Git" UI + **Test connection** (scratch-ref push). No auto-sync yet.
- **S2 — Publish one, by hand.** `git-publisher` engine + a manual **"Push to Git"** action for a single
  component: filestore → worktree → attributed commit → push, with a status record (last-pushed commit per
  component).
- **S3 — Auto-mirror on publish + collaboration.** Hook the publish gate so publishing auto-pushes; also push
  the `studio.project` manifest. Ship project **ownership + role-scoped sharing** (`governance.role_grant` on
  the project resource; Studio "Share" UI; bridge enforcement).
- **S4 — Reconcile & round-trip.** Scheduled full-tenant mirror ("push everything") + a **drift view** (what
  the tenant has published vs what the repo contains — the automated form of this ADR's audit). Optional
  Git → platform import as a distinct, later step.

## Consequences

- **Developers own their code.** The Git repo is theirs, credentialed by them, per tenant — the platform is a
  mirror, not the custodian. Backup, review, branching, and history become native.
- **Drift becomes visible, then impossible.** S4's drift view surfaces exactly the `deliv-proof`-style gap this
  ADR was motivated by; auto-mirror on publish (S3) prevents it recurring.
- **Teams can collaborate** within a tenant with differentiated rights, reusing the RBAC spine — no new
  authorization system, tenant isolation intact.
- **Trust is preserved.** No secrets in the registry (Vault only), all Git egress broker-confined and
  allow-listed, commits carry verifiable digests + per-author attribution, and every check fails closed.
- **Cost:** a new certified engine with outbound Git egress, credential lifecycle to manage (rotation,
  revocation on offboarding), and merge/conflict semantics to define for the eventual import direction (S4+).

## Open questions

- Commit granularity: one commit per publish vs. squashed per session — and whether to sign commits (verifiable
  provenance) in addition to embedding the digest.
- Monorepo-per-tenant vs. repo-per-solution — start with monorepo-per-tenant (mirrors the current `components`
  layout); allow per-solution repos later via `path_convention` / multiple bindings.
- Offboarding: revoking a departed developer's `role_grant`s and ensuring their Vault-held Git credential (if
  any) is rotated.

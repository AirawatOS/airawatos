# ADR-0106 — Declarative solution manifest, one-command sandbox deploy, and the dev↔production governance boundary

Status: Proposed — the Build-SDK P3 slice. Depends on the P1/P2 SDK core (committed: `components/_common/aos`).
Date: 2026-09-26
Related: [[ADR-0051]] (tenant `environment: development|production` + sandbox), INT-0004 (developer tenant + dev-token + broker confinement), [[ADR-0075]] (solution install = closure fan-out + steward grant per component), [[ADR-0097]] (one `platform.workflow` graph spine — what a solution wires), [[ADR-0093]] (filestore component delivery), [[ADR-0094]] (steward-gated publish), [[ADR-0104]] (lifecycle `on_install` hooks), the certify-time governed-vocabulary gate (`network/conformance.py:128-203`), and `aos.policy` (the SDK-side mirror of the boundary defined here). Companion to the Build-SDK proposal (artifact) and ADR-0030 (the component SDK/broker this rides).

## Context

Standing up a governed vertical today — a decision-support system or a citizen service — means a developer hand-assembles ~13 governed schemas and ~10 certified components on the shared spine, and **governance sits on the critical path**: `network/conformance.py` withholds a certificate until every schema, role and interface a component declares is *published*, and each publication is a `request → decide` pair approved out-of-band by the `airawat` standards body. Verticals ship per-vertical hand-written `govern_*.py` scripts (welfare-spine has eight). And the sandbox that INT-0004 built (dev-token, broker-confined, verified) tests **one component from source at a time** — there is no "install the whole solution into my sandbox and exercise it as a bundle."

The P1/P2 SDK (`aos`) already unified the authoring model, made `meta.yaml`/scopes derived, and encoded the dev↔prod publish boundary in `aos.policy`. What's missing is the **declaration** that describes a whole solution, the **pipeline** that stands it up in a sandbox in one command, and the **platform-side governance boundary** that lets a developer govern-and-run freely inside their own tenant while never letting unreviewed work — or a half-built app — reach a shared production surface.

Governance policy for this ADR was set by the platform owner (2026-09-26): **a developer may build, govern, install and test a whole solution inside their own development tenant with governance auto-approved there; a developer may not publish anything into the Marketplace or the Service Directory; anything running in a development tenant is clearly marked "Under Development" to end users.**

## Decision

Add a single declarative solution manifest, a one-command sandbox deploy that stands the whole thing up, and a broker/network-enforced governance boundary between development and production — with the "Under Development" marking travelling on the artifact.

### 1. `solution.yaml` — one declarative manifest (the lockfile for a vertical)

One file describes the whole solution, so the govern-schemas-then-wire-members-then-seed-layers assembly stops being per-vertical imperative scripts:

```yaml
solution: water-safety
environment: development           # stamped onto every produced artifact (§4)
schemas:                           # inline governed-noun definitions (dev: auto-approved §3)
  - id: cell.flood_risk   { x-kind: measure, properties: {...} }
roles: [water.duty-officer]
interfaces: []                     # governed verbs this solution defines (if any)
workflow: workflow.graph.yaml      # a platform.workflow graph (ADR-0097)
members:
  reuse: [lifecycle-engine, decision-router, effectiveness-engine]   # certified spine — not rebuilt
  build: [engines/infer, app/]                                       # the domain delta, SDK-authored
viz_layers: [cell.flood_risk]      # descriptors seeded on install (no longer forgotten)
decider: water.duty-officer        # the DECIDER wiring, declared
subscriptions: [{on: governance.recommendation, do: decision.route}]
contributions: [rulesets/thresholds.json]   # governed records seeded into the tenant at install
```

The SDK reads it end-to-end; `reads`/`writes`/`scopes` for each member come from the code (P1), not the manifest. `solution.yaml` is the reproducible source of truth for the vertical — a build from it yields the same solution.

### 2. `aos deploy --sandbox` — stand up the whole solution in one command

One idempotent pipeline over `solution.yaml`, all confined to the developer's tenant:

1. **govern** — register the manifest's schemas / roles / interfaces (dev: auto-approved in place, §3).
2. **build + certify** — the `build` members via the SDK; `reuse` members are resolved from the marketplace.
3. **compose + install** — compose the solution and run the ADR-0075 install closure **into the dev tenant** (grant-per-write, app shelf, roles, subscriptions).
4. **seed** — `viz_layers` descriptors, `contributions` records, the `decider` wiring, and any `on_install` lifecycle hooks (ADR-0104).
5. **open** — return the app URL(s) so the developer exercises the *whole* solution live.

`aos destroy --sandbox` tears the closure down (idempotent). This is the "deploy & test the entire solution in your sandbox" capability that does not exist today; it closes the INT-0004 gap (component-from-source → whole-solution install).

### 3. Dev-tenant governance is auto-approved *in place* — and quarantined to that tenant

INT-0004's dev-token already confines every registry read/write/query to the developer tenant and skips the steward-grant. Extend that to **vocabulary governance**:

- In a `development` tenant, a schema/role/interface declared by `solution.yaml` is **governed locally, self-service** — recorded as approved **scoped to that dev tenant's namespace** (`ds:<devtenant>:…`), never written into the shared production catalog.
- The certify-time `governed-vocabulary` / `governed-roles` / `governed-interfaces` gate (`conformance.py:173-203`) is satisfied for a **dev-token certification** by that tenant-local governed vocabulary — so the developer gets a (dev-scoped) certificate and can install + run, with **no out-of-band human on the path**.
- This is **quarantine, not a bypass**: dev-governed vocabulary is visible only inside the dev tenant; it cannot be referenced by a production component, and it is never signed by the standards body. Promotion to production (a later, separate flow — not this ADR) **re-governs** the vocabulary through the real `request → decide`, and re-certifies under production authority.

Net: governance stops being a critical-path blocker for *iteration*, without weakening the shared catalog for *production*.

### 4. The production publish boundary (belt-and-suspenders) + the "Under Development" marking

- **The boundary.** The network refuses any `POST /v1/store/publish` (Marketplace) or `POST /v1/service-offerings` (Service Directory) whose publishing tenant's `environment == development`; the app_host marketplace/service bridges never forward a development-tenant publish. `aos.policy.check_publish` mirrors this SDK-side for a fast local failure, but **the network gate is the authority** (`aos.policy.PROD_PUBLISH_GATES` names the exact hooks). A developer therefore cannot, by SDK, CLI, or hand-rolled call, place unreviewed work on a shared production surface.
- **The marking travels on the artifact.** Every artifact produced in a dev tenant carries `environment: development` + a `ui_badge {label:"Under Development", tone:"warning"}` (`aos.policy.stamp_dev`). Surfaces render it: the Studio shelf, City Scan, Jan Seva, and — critically — a dev-tenant `service.offering` is **never discoverable in the production Service Directory** and, if surfaced in any dev-facing catalog, shows the badge. Users can always tell a sandbox build from a published service.

### 5. What stays exactly where it is

- **Production governance** is unchanged: the standards-body `request → decide` (`network/api.py`) remains the only path to shared-catalog vocabulary and to a production certificate.
- **Confinement/attribution** (ADR-0030, INT-0004): the broker still enforces dev-token→dev-tenant isolation both ways; a production token can never touch a dev tenant, and a dev token can never touch production.
- **Solution install** is the ADR-0075 closure — `aos deploy` orchestrates it, it does not replace it.

## Rollout

- **S1 — `solution.yaml` schema + `aos deploy --sandbox` (govern→build→compose→install→seed) against a dev tenant**, reusing INT-0004's dev-token; prove on the effectiveness/decision-support members already SDK-ported.
- **S2 — dev-tenant vocabulary auto-approval** — the conformance relaxation for dev-token certification + tenant-scoped governed-vocab records (§3). Prove: a brand-new schema in `solution.yaml` certifies + installs in a dev tenant with no standards-body call, and is invisible outside it.
- **S3 — the production publish gates** — network refuses dev-environment publishes to store + service-offerings (§4); app_host bridges likewise. Prove: `aos publish` and a raw call both blocked from a dev tenant.
- **S4 — the "Under Development" marking rendered** in the Studio shelf, City Scan, Jan Seva; dev offerings excluded from the production directory search.
- **S5 — `aos destroy --sandbox`** (clean teardown) + the reproducibility check (deploy from `solution.yaml` twice → identical closure). **DONE + proven live** (airawat-local, `airawatdeveloper`): destroy reverses the closure — unseed viz/contributions (registry retract via the identity token, own-tenant tombstone) → uninstall = revoke every member's grants (`grants/revoke-for`) → decertify build members (`certificates/retire`) → retract dev vocab (`schema-requests/retract`, the inverse of the S2 auto-approve) + roles; every step best-effort/idempotent. Verified: destroy → viz resolve 404 → redeploy reproduces the identical closure → 2nd destroy idempotent.

Promotion (dev → production: re-govern + re-certify + first prod install) is deliberately **out of scope** here — it is its own ADR, gated on this boundary being solid.

## Consequences

- **Positive:** a developer stands up and exercises a whole governed solution in their sandbox in one command, with governance off the iteration critical path — while the shared catalog and production surfaces stay standards-body-gated and un-pollutable. `solution.yaml` makes verticals reproducible and reviewable. The dev↔prod boundary is enforced in the network (authority), the broker (confinement), the SDK (fast-fail), and the UI (the badge) — four layers, one rule.
- **Negative / risks:** (a) **dev-vocab leakage** — the quarantine (tenant-scoped records + re-govern-on-promote) must be airtight, or a dev schema could masquerade as governed; the certify relaxation must key strictly on `dev-token ∧ environment==development ∧ same-tenant namespace`. (b) **"works in my sandbox" drift** — a solution that installs in dev may still fail production re-governance; promotion must re-run the full standards-body path, not trust the dev cert. (c) a second install path (`aos deploy`) alongside the existing UI install must converge on the *same* ADR-0075 closure, not fork it.
- **Open questions:** where do tenant-local governed-vocab records live — a per-tenant schema catalog, or the existing registry with an `environment`-scoped visibility filter? Should `reuse` members pin versions in `solution.yaml` (a true lockfile) from S1, or later? Does `aos deploy --sandbox` install the certified marketplace copy of a `reuse` member, or the developer's local source when they're iterating on it?

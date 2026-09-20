# ADR-0099 — Platform software supply chain: two lanes + host↔component contract compatibility

**Status:** Proposed (2026-09-20)
**Relates to:** ADR-0030 (component SDK + broker clean-room), ADR-0063 (`/bridge/*` = the app confinement boundary), ADR-0020 (OS/Network split), ADR-0058 (interaction contracts), ADR-0059 (the kernel publishes its interfaces + declares conformance), ADR-0090 (interface bindings + conformance), ADR-0093 (component delivery — retire baking), ADR-0096 (platform operator model — trust rooted in the node CLI), ADR-0095 (runtime lifecycle), ADR-0098 (versioned app install + admin-gated upgrades), #137 (marketplace version discipline), #138 (schema backward-compat diff-gate at approval).

## Context

Two kinds of software reach a running deployment, by **two deliberately separate supply chains**:

1. **Service / runtime images** — `airawatos-reference` (which runs `app_host`, `scheduler`, `runtime-manager`, `event-relay`, …), `kernel`, `network`, and the per-profile runtime images. These are **container images**: the platform developer builds + tags + pushes them; the **operator** pulls + recreates. This lane is *not* the marketplace — it is governed by the **operator trust model** (ADR-0096): the node-side `airawat` CLI verifies the image digest and records a host-integrity attestation before running it (`provision-runtime` = pull → verify → attest).

2. **Components** — drivers, engines, apps, agents. Published via Studio → **certify** → **filestore**, with version-immutable store listings (#137), installed/pinned **per tenant** (ADR-0093 delivery, ADR-0098 pin). Fully governed by the marketplace/cert spine.

These two lanes meet at a small, fixed set of **seams**. A confined component never calls the platform (or another component) directly — it reaches everything through one mediated door:

| Interaction | Seam | Mediator |
|---|---|---|
| **App → platform** | `/bridge/*` HTTP endpoints | app-host (the app confinement boundary, ADR-0063 D3) |
| **Driver/engine → platform** | the **broker** (thin SDK over the broker HTTP contract) | broker (only I/O; clean-room, ADR-0030) |
| **Component → component (data)** | write/read a governed **noun** (schema/fact) | kernel registry (writer-taxonomy + grants + attribution) |
| **Component → component (behavior)** | invoke a governed **verb** | kernel/host resolves the governed **binding** to the impl (conformance-gated, ADR-0090) |
| **Authorization of both** | **roles** (grants) | kernel enforces; Network governs the vocabulary |

So the *runtime* plane is intermediated by the **kernel** (registry reads/writes, verb dispatch, authz); the *vocabulary* — which nouns/verbs/roles exist — is governed by the **Network** (ADR-0020). Components interact with their runtime through `/bridge/*` (apps) or the broker (drivers/engines), and with **each other** only through governed **role / verb / noun**, never a direct call.

### The problem

A bug fix in `airawatos-reference` (or kernel/network) flows down Lane 1 — new image, operator pull, recreate. But the reference image touches components in two ways, and both are coupling hazards:

1. **Baked components.** Historically the image *baked* some drivers/engines/apps into `/app/components`. That welds the two lanes: a service release drags a component snapshot with it, and a component fix needs a whole new image. (ADR-0093 is retiring this; runtimes are the last baked exception per ADR-0095.)

2. **The seams themselves are contracts.** Even with baking fully retired and components delivered separately, a reference change that alters a **seam** — a `/bridge/*` request/response shape, the broker contract, the SDK, or a governed schema/verb — can break an **already-installed** component that was delivered down the other lane. Today a service upgrade is a `docker pull` + recreate with **no check** that the seams it provides still satisfy the components running against them. The break surfaces at runtime, in a tenant, after rollout.

## Decision

### 1. Keep the two lanes separate; never re-couple them by baking

Service images carry **services only** (ADR-0093). Components travel the governed lane and are **pinned per tenant** (ADR-0098). A service release and a component release move **independently** — neither drags the other. (This ADR does not re-open ADR-0093/0098; it depends on them.)

### 2. Every host↔component seam is a **versioned contract**, published by the host

The coupling surface is exactly the seam table above. Each seam carries an explicit contract **version**:

- **`/bridge/*`** — the app-facing bridge surface is versioned; the app-host **publishes** the bridge contract + version it serves (extends ADR-0059: the kernel/host publishes its interfaces and declares conformance).
- **Broker contract + SDK** — versioned; the broker publishes the contract version it enforces.
- **Nouns (schemas)** — already versioned + governed; backward-compat enforced at approval (#138).
- **Verbs (interfaces)** — governed interaction contracts (ADR-0058) with binding + conformance (ADR-0090); the impl declares which interface version it conforms to.

A component **declares the contract versions it consumes** (bridge vX, broker vY, schema vZ, verb-interface vW). The host **declares the versions it provides**. Compatibility is then a checkable relation, not a hope.

### 3. A **compatibility gate** at both release time and install/upgrade time

- **At component certify** — the candidate's declared seam-versions are checked against the platform's currently-provided contracts (the ADR-0090 conformance gate, widened from verbs to *all* seams). A component that needs a contract the platform doesn't provide fails certification.
- **At service release** — a reference image release **declares the seam-contract versions it provides**; a release that **drops or breaks** a contract an installed/certified component depends on is flagged (the #138 diff-gate, generalized from schemas to bridge/broker/SDK/verb seams). Breaking a contract requires a **version bump**, not a silent change — components negotiate against the version.
- **At operator upgrade** — because component upgrades are **per-tenant opt-in** (ADR-0098) and the service image is delivered via **attested provision-runtime** (ADR-0096/0095), the operator can pull the new image in **staging**, run the compat gate against installed components, and only then roll — instead of a big-bang where a host fix silently breaks live components.

### 4. Deliver the service lane through the operator trust root, not ad-hoc docker

The app-host **service** itself should be delivered the same way runtimes are (ADR-0096/0095): build-from-source → push → operator `provision-runtime` (pull → **verify digest** → **attest host-integrity**) → recreate. `docker commit` + hand-edited compose (the current dev shortcut, e.g. the 0.2.31 bake) is explicitly **not** the production flow.

## Consequences

- **Positive:** a platform bug-fix can ship without fear of silently breaking tenant components — the compat gate catches a broken seam at release/certify, not at runtime; the two lanes stay decoupled so cadence is independent; operators get staged, attested, reversible upgrades.
- **Costs:** every seam must carry and honor a version (real discipline on `/bridge/*`, broker, SDK); the compat gate + a machine-readable "provided contracts" manifest per image must be built; more release ceremony than `docker pull`.
- **Migration:** seams are versioned incrementally (schemas + verbs already are; `/bridge/*` and the broker are the new work). Until the gate exists, service releases remain manually vetted — this ADR names the gap; #138 + ADR-0090 are the primitives to close it.

## Status of the pieces today

- **Live:** two lanes physically exist; universal component delivery (Lane 2) is live; per-profile runtimes attested via `provision-runtime` (ADR-0096); schemas versioned + governed; verb bindings + conformance proven (ADR-0090).
- **Partial:** de-baking (ADR-0093) and per-tenant app pin (ADR-0098) are partial; the app-host **service** is still deployed by hand (the 0.2.31 bake), not via `provision-runtime`.
- **Not yet built:** versioned `/bridge/*` + broker contracts; a machine-readable "contracts provided" manifest per service image; the release-time + certify-time **compat gate** that blocks a reference release which breaks an installed component's seam.

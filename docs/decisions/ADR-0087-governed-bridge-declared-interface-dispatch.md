# ADR-0087 — Governed Bridge: declared-interface dispatch (collapse the app-host BFF)

Status: Proposed (2026-09-15)
Related: ADR-0058 (interaction contracts / interfaces), ADR-0022 (everything-is-a-component), ADR-0030 (component SDK + broker clean-room), ADR-0052 (attributed writes), ADR-0020 (OS/Network split)

## Context

A sandboxed app reaches the platform only through the app-host's `/bridge/*` surface. That surface has grown to
**~89 bespoke, hand-written handlers** in `app_host.py`. Adding *any* new app capability today means (a) writing a
new verb + handler in the host and (b) **rebuilding the user-facing service** (the app-host backs all of
airos.airawat.org). That is an anti-pattern — the host has become a god-object BFF, and "add an app feature" wrongly
means "do surgery on the shared host + redeploy the whole UI." It is the same coupling flagged for hardcoded
`ENGINE_VERBS`, one layer up, and it contradicts ADR-0022/0030/0058 (capabilities are governed + declared, not
hand-wired into infra).

Crucially, the debt is NOT the routing *table*: the host already maps `verb → governed verb`
(`query→registry.query`, `save→registry.write`, `resolve→registry.read`, `change-request→network.change_request`,
`decide→governance.decide`, `fetch→platform.fetch`). The debt is the **per-feature handler for each verb** — most of
which are thin proxies to a governed verb the platform already exposes.

## Decision

The app-host bridge layer becomes a **generic, declaration-driven governed-interaction proxy**:

1. An app DECLARES, in its certified manifest, the governed **interfaces it calls** (ADR-0058 `calls: [interface@ver]`).
2. A `/bridge/<verb>` request is dispatched generically:
   - resolve `verb → governed interface/verb` (the existing map, promoted to interface ids),
   - VERIFY the calling app's certificate declares that call AND the governed verb is on the allow-list,
   - PROXY to the kernel / network / broker with the caller's **session token + `component://<app> obo user://<sub>`
     attribution** (ADR-0052) — the same identity + grant checks as today.
   No per-feature handler; no host rebuild for a new governed capability.
3. Genuinely host-internal logic (Studio authoring `component-save`/`project-publish`, `ai-assist`, `transcribe`,
   file upload) stays as host services OR migrates to **certified engines** (ADR-0030) — it is NOT a governed
   passthrough and does not belong in the generic path.

## Migration — additive first (no regression)

- **R1 (additive, safe):** add the generic dispatcher as a **fallback** — a `/bridge/<verb>` NOT matched by an
  existing bespoke handler, that maps to a governed verb the calling app declares, is proxied generically. The 89
  existing handlers are **untouched** → zero behavioural change for live apps. New capabilities use the generic path.
- **R2 (later):** migrate the pure-passthrough handlers (the `registry.read/write/query` + `network.change_request`
  verbs — the bulk of the 89) onto the generic path and delete them, shrinking the host. Domain flows with real logic
  (`service-*`) become engines or stay, case by case.
- **R3 (later):** the `verb → interface` table itself becomes data (a governed interface registry), so even the map
  is not code. — **Delivered by ADR-0101** (`platform.verb_binding`: the verb→engine default binding + allow-list are
  governed data; `ENGINE_VERBS` shrinks to a ~7-verb bootstrap floor; publish self-registers a component's verbs).

## Data Exchange rides R1 (the proof case)

Instead of bespoke `net-offer`/`net-request`/`net-decide` handlers:
- Govern a `network.data-exchange` interface set (publish-offering, discover, request, decide, retire, revoke) — these
  are `network.change_request`-class mutations + directory reads, verbs the platform already has.
- The **Data app declares** `calls: [network.data-exchange@0.1.0]`.
- Its offerings/requests/grants operations flow through the **generic proxy** — **zero bespoke host code**, and after
  R1 no further app-host rebuild for Data Exchange or any future network capability.

## Consequences

- Apps stop touching `app_host.py`; "add an app capability" becomes a *declaration*, not host surgery.
- The host shrinks toward a thin, auditable, allow-listed proxy — attribution + grant checks enforced centrally.
- One-time, carefully-verified app-host rebuild for R1; thereafter governed capabilities are declaration-only.
- Risk: R1 must fail-closed (undeclared call → refuse) and must not widen reach beyond what the app's cert + the
  tenant's grants already permit — it reuses the SAME identity/obo/grant path, only removing the per-verb handler.

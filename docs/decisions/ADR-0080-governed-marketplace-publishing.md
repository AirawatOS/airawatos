# ADR-0080 — Governed marketplace publishing (publish-request → approve)

**Status:** Proposed
**Relates to:** ADR-0016 (store / cert / signing), ADR-0038 (AirawatNetwork = standards body; propose→approve→sign),
ADR-0030/0051 (certified components), the Studio project model (ADR-0037), the steward console.

## Context
Marketplace publishing today is a **direct push**: `POST /v1/store/publish` lists a component once it is
certified, and it is **namespace-gated** — `_require_publisher` allows the call only under the caller's own
steward name. Two problems follow:
1. A developer **cannot publish under a first-party namespace** (`ds:airawat:*`) — publishing platform apps or
   edits requires the `airawat` steward key, which developers must not hold. (This is the exact wall that
   blocked publishing the Admin/Usage app from a developer's Studio project without hand-wielding the steward.)
2. There is **no review gate**: whatever a developer can publish under their own name goes straight to the
   catalog with no standards-body approval — inconsistent with how *everything else* on the platform is governed.

Every other addition to the shared namespace already goes through a **propose → decide** gate run by the
network standards body: `schema-requests → decide`, interface change-requests → decide, `pack-requests →
decide`, `role-requests → decide`. Marketplace publishing is the missing member of that family.

## Decision
Add a **publish-request → approve** gate for the store, mirroring `schema-requests`:

- `POST /v1/store/publish-requests` — a developer **files** a request `{component_id, version, kind, provider,
  title, description, notes}`. **No publisher/steward authority required** — they are *asking*, not publishing.
- `GET /v1/store/publish-requests[?status=]` — the steward console lists pending requests.
- `POST /v1/store/publish-requests/decide` — the **network steward** (`_require_admin("airawat")`) approves or
  rejects. On **approve**, the server performs the privileged act **on the authority's behalf**: verify the
  certificate + marketplace version discipline, then `STORE.publish(...)`. The listing becomes marketplace-
  available. On **reject**, review notes return to the developer.

The developer never holds the steward key; the steward's **approval is the authority**. Because approval runs
server-side under the steward, `STORE.publish` executes past the per-caller namespace check — so a request may
target **any namespace, including first-party `ds:airawat:*`**.

### Review = automated gates + human judgement
Approval composes the checks that already run at certify — Tier-4 output-schema conformance, the axe a11y
gate, digest verification, the ADR-0075 solution-closure rule, and version monotonicity — **plus** a human
approve/reject with notes. It is a reviewed gate, not a rubber stamp.

### Surfaces
- **Studio** — a project's *Publish* becomes **"Submit for review"** (`project-publish` files a
  publish-request instead of calling `store/publish` directly). The developer sees status: pending → approved
  / rejected(+notes).
- **Steward console** (network-admin / the standards-body surface that already lists schema + role requests) —
  a **"Publish Requests"** tab: review the component (cert, conformance report, diff vs the live version),
  approve or reject with notes.

## Consequences
- Resolves the fork-vs-steward-key dilemma: a developer publishes **any** component — including into first-party
  namespaces — by *submitting*; the steward *approves*. No key sharing, no forced rename.
- Marketplace becomes a **reviewed, trusted** catalog (matches the north-star: core = spec impl + **certified**
  third-party plug-ins), consistent with schema/role/pack governance.
- Fully auditable: each listing carries who requested, who approved, when, and against which certificate.
- Back-compat: `store/publish` stays for first-party/bootstrap flows; the request gate is the developer path.

## Slice (this ADR)
1. **Backend gate** — `store/publish-requests` file/list/decide in the network (mirrors `schema-requests`;
   approve side-effect = certificate check + `STORE.publish`).
2. **Studio** — `project-publish` → "Submit for review" (files a request); show request status.
3. **Steward console** — Publish Requests tab (review + approve/reject).

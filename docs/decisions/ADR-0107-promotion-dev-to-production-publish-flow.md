# ADR-0107 — Promotion: the reviewed dev→production publish flow

Status: Proposed — the door through the ADR-0106 sandbox boundary. Depends on ADR-0106 (S1–S4 sandbox deploy + dev governance + publish gates) being live.
Date: 2026-09-26
Related: [[ADR-0106]] (the sandbox side + the S3 gate this is the reviewed exception to), [[ADR-0094]] (steward-gated publish — who may publish under a name), [[ADR-0075]] (solution install = closure fan-out + grant per component), [[ADR-0051]] (tenant environment), [[ADR-0093]] (filestore component delivery), the standards-body governance path (`network/api.py` schema/role/interface `request → decide`), the certify-time conformance gate (`network/conformance.py`), and `aos.policy` / `network.devgov` (the SDK + network sides of the boundary).

## Context

ADR-0106 built the sandbox: a developer governs, installs, and exercises a whole solution inside their own `development` tenant with governance auto-approved and quarantined (`ds:<devtenant>:vocab/*`), and S3 **refuses** any development-tenant publish to the shared Marketplace or Service Directory. That is deliberately a wall with no door: the dev vocab was never standards-body-reviewed, the components carry only a dev-scoped certificate, and everything is stamped "Under Development."

So the open question — *"how does a solution that works in my sandbox get published?"* — has no answer yet. This ADR is that answer: a **promotion** flow that is a **governed transition, not a copy**. Its guiding rule, stated in ADR-0106 §3: *promotion re-governs; it never trusts the dev cert.* "Works in my sandbox" is a precondition for asking, not evidence for production.

## Decision

Promotion turns a sandbox-proven solution into a production edition through four reviewed steps, then publishes and installs it. It is driven by `aos promote` (and a Studio "Submit for Production" surface), and it produces a **distinct production artifact** — the dev edition stays in the sandbox, still marked "Under Development."

### 1. Promotion is a governed transition (never trust the dev cert)

The dev tenant's local governance and dev-scoped certificate confer **nothing** in production. Promotion re-derives every guarantee under the real authorities:

```
dev tenant (Under Development)                         production
──────────────────────────────                         ──────────
solution.yaml + sandbox-green  ── aos promote ──▶  1. canonicalize vocab
                                                   2. standards-body re-govern (request→decide)
                                                   3. re-certify under production authority
                                                   4. publish (store / service-offerings) + install
                                                   → production edition · badge cleared
```

### 2. Canonicalize the vocabulary (§dev-scope → canonical noun)

Dev-governed schemas/roles/interfaces live at `ds:<devtenant>:vocab/<noun>` (ADR-0106 §3). Promotion maps each back to its **canonical** form (`<domain>.<subject>`), and partitions them:
- **already governed** in the shared catalog → reuse as-is (no re-submission);
- **new** → carried into step 3 for standards-body review.

The map is deterministic (strip the `ds:<tenant>:vocab/` prefix). A canonicalized noun that **collides** with a *different* existing governed definition is a hard stop — the developer must reconcile (rename or align to the governed shape) before promotion proceeds.

### 3. Standards-body re-governance (the human review)

For each *new* schema/role/interface, promotion files the real `request` and blocks on the standards-body `decide` (`airawat` admin) — the exact production path that exists today, no relaxation. This is where a human reviews what the developer invented in their sandbox. Promotion **cannot** self-approve here; that is the whole point of the wall having a reviewed door rather than a hole.

### 4. Re-certify under production authority, then publish + install

Once the vocabulary is governed in the shared catalog:
- **re-certify** each `build` member under production authority — a fresh certificate against the shared catalog only (the dev-vocab union of ADR-0106 §S2 does not apply); a component that only certified because of dev-local vocab fails here, honestly.
- **publish** — `store/publish` (Marketplace) and/or `service-offerings` (Service Directory). The ADR-0106 S3 gate now **passes** because the publishing context is production (the steward publishing under ADR-0094, targeting a production tenant), not a development tenant.
- **install** — the ADR-0075 closure into the target production tenant(s), grant-per-write, roles, subscriptions, viz.layers — the same fan-out `aos deploy --sandbox` used, now against production.

### 5. The two editions, and clearing the badge

Promotion yields a **production edition** distinct from the dev edition:
- the dev edition stays in the sandbox, still `environment: development`, still badged "Under Development" — the developer keeps iterating;
- the production edition carries no dev marking (its `environment` is the target production tenant's), so the "Under Development" badge (ADR-0106 S4) is **absent** wherever it renders;
- a **promotion receipt** (signed) links the two — dev source solution.yaml + digest → the production certificate ids + published listing — so the lineage of a live service back to its sandbox is auditable.

### 6. Gates, idempotency, partial promotion, rollback

- **Precondition:** the solution passed a sandbox deploy (green) — promotion of an unexercised solution is refused (fail-fast, before bothering the standards body).
- **Idempotent + resumable:** re-running promotion skips already-governed vocab and already-published members; a promotion interrupted at the standards-body wait resumes when the decisions land.
- **Partial:** a solution whose vocab is *partly* governed promotes only the delta.
- **Rollback:** promotion never mutates the dev edition; a failed/withdrawn promotion leaves production untouched (nothing is published until every member re-certifies and every vocab item is governed). Un-publishing a production edition is the existing steward retire/deprecate path (ADR-0094 / marketplace governance), out of scope here.

### 7. What stays exactly where it is

- **Standards-body authority** over the shared catalog and production certificates — unchanged; promotion *uses* it, never bypasses it.
- **ADR-0094 steward publish** (who may publish under a name), **ADR-0075 closure** (how a solution installs), and the **ADR-0106 S3 gate** (dev tenants blocked) — all intact. Promotion is the *only* sanctioned way a sandbox artifact reaches production, and it does so by becoming a production artifact first.

## Rollout

- **S1 — `aos promote --dry-run`:** canonicalize + partition vocab, report what would be re-governed / reused / collides, and the members that would re-certify. No writes. The developer sees the production gap before asking.
- **S2 — re-governance:** file the real `request`s for the new vocab; surface the pending standards-body decisions (in Studio + CLI); resume on approval.
- **S3 — production re-certify + publish:** re-certify each member under production authority; publish to store / service-offerings (S3 gate passes for the production context); write the signed promotion receipt.
- **S4 — install into the target production tenant** via the ADR-0075 closure; verify the badge is absent on the production edition.
- **S5 — Studio "Submit for Production":** the guided surface over `aos promote` — the reviewed counterpart to "Publish as Solution / as Service," making the dev→prod boundary visible and legible to the developer.

## Consequences

- **Positive:** the sandbox story is complete end-to-end — a developer builds and proves freely in their tenant (ADR-0106) and ships through a single reviewed door that re-establishes every production guarantee from scratch. Nothing unreviewed reaches a shared surface; the dev↔prod lineage is auditable via the receipt; the dev edition keeps iterating independently of the promoted one.
- **Negative / risks:** (a) **reviewer load** — every new vertical's vocab lands on the standards body; batching + a clear diff (S1 dry-run) matter, and a large solution may stall on many pending decisions. (b) **canonicalization collisions** — a dev noun that clashes with an existing governed one blocks promotion; good error messages + a rename path are essential. (c) **dev↔prod drift** — a solution can pass in the sandbox (dev-vocab union) yet fail production re-certification; that is *intended* (the dev cert is not trusted) but must be communicated so it is not a surprise. (d) two editions of the same solution existing at once needs clear identity so operators never confuse the sandbox build for the live service.
- **Open questions:** who is the promotion *requester* vs the standards-body *approver* vs the production-tenant *installer* — one person wearing three hats in dev, but three parties in a real federation; does the model force that separation from S1? Should promotion pin the exact dev-tested member versions into the production edition (a lockfile promotion) so what ships is byte-for-byte what was proven? And where does the promotion receipt live — a governed `network.promotion` record, or an attestation alongside the certificate?

# ADR-0103 — Owner-granted per-object sharing, consent-on-demand, and the audit loop

Status: Proposed
Date: 2026-09-21
Related: [[ADR-0085]] (cross-tenant file & data sharing — the tenant-level lane this generalises), [[ADR-0052]] (attributed, digest-verified writes), [[ADR-0026]] (delegated `component:// obo user://` authority), [[ADR-0049]] (verifiable credentials / consent), [[ADR-0029]]/[[ADR-0046]] (decision spine / hourglass), [[ADR-0088]] (rule engine — `governance.policy_rule`), [[ADR-0089]] (event/message spine), the runtime auditor + automated containment (#69), the universal reference resolver (`/v1/resolve-ref`).

## Context

A user must be able to share **any** governed object — a File, a single registry row (a property record, a case, a claim), a Doc, a Sheet, a Slide — with a **specific person**, inside or across tenants, scoped to **view / comment / edit**, and to do so by handing over an embeddable link. Symmetrically, someone who receives a link they were never granted must be able to **request access**, and the **owner alone** decides whether to grant it, for how long, and at what scope. Every step must be logged and continuously audited so that violations are caught and corrected. This is the privacy foundation: *your data moves only by your consent, and that consent is verifiable after the fact.*

Today the platform cannot express any of this. From the kernel up (confirmed by reading `kernel/api/app.py` + `kernel/services/registry/pg_store.py`):

- **The kernel enforces tenant isolation only.** A row's identity is `ds:<tenant>:<schema>/<local>`; every authorization decision is a string-prefix match on that tenant (`_read_stewards` → `id LIKE 'ds:<tenant>:%'`; `_assert_write_own_tenant`). There is no owner column and no per-object anything.
- **"Owner" is an app-host convention, not a kernel fact.** For `personal: true` apps the host injects `filter.owner = sub` into reads and forces `obj.owner = sub` on writes (`app_host.py:1399-1402`, `4120-4123`). The kernel stores `object.owner` opaquely and never reads it for a decision. Bypass the host and the clamp is gone.
- **Grants are `(component × schema × tenant)`, never per-object or per-user.** `governance.access_grant` (steward-signed, verified by the kernel in `_steward_authorizes`) authorises a *component* to read/write a *schema* for a *whole tenant*. No object id, no end-user grantee.
- **No share-link, invite, consent-on-demand, type→viewer, or per-object audit** exists anywhere (repo-wide greps: zero).

So owner-granted, per-object, per-user sharing is a **new kernel primitive**, not a tweak. Two design truths shape it: (1) **the link is not the permission** — access is a kernel decision against an owner-issued grant, so a forwarded URL leaks nothing; (2) **not every row is user-owned** — a Doc belongs to its author, but a property or case record belongs to the *agency/tenant*, so "who may share" is a property of the noun, declared in governance.

## Decision

Add one primitive — an **owner-issued, per-object capability grant** — enforced in the trusted kernel, reached by two doors (push and pull), rendered by a universal Opener, and watched by an audit→correct loop. Six parts.

### 1. Ownership is declared per schema; the kernel stamps the concrete owner

A governed schema declares its ownership model:
- `x-ownership: user` — each row belongs to the **person** who created it (Docs, Sheets, Slides, Files, a citizen's own records). That person shares it.
- `x-ownership: tenant` — each row belongs to the **agency/tenant** (a building, a tax row, a court case). Sharing outward stays the admin-gated cross-tenant lane ([[ADR-0085]]); an individual cannot unilaterally share it.

For `x-ownership: user` schemas the **kernel stamps `owner` at write time** from the verified `user://<tenant>/<sub>` in `_writer_agent` (never from client-supplied data), and maintains an **owner index** `object_id → owner` so authorization can consult ownership without reading the payload. This is the answer to "where is ownership defined": **in the governed schema (the noun), with the concrete owner fixed by the kernel from identity.**

### 2. `access.grant` — the per-object capability record

```
access.grant = {
  object_id:  "ds:<tenant>:<schema>/<id>",      // the universal handle — ANY noun
  grantee:    "user://<tenant>/<sub>"           // a specific person (any tenant → cross-tenant for free)
              | "role://<tenant>/<role>"          // everyone holding a role
              | "link:<token>",                   // opt-in "anyone with the link" (see §5)
  scope:      "view" | "comment" | "edit",       // a ladder: edit ⊃ comment ⊃ view
  granted_by: "<owner sub>",                      // MUST equal owner(object_id)
  reason, issued_at, expires_at, revoked
}
```

The grant is **owner-signed** (or steward-signed on the owner's behalf, reusing the `_issue_grant` pattern) so a grantee in another tenant's kernel can verify it, resolved via the network grant resolver exactly as `governance.access_grant` is today.

### 3. Kernel enforcement — a new authorization axis, owner-only issuance

Two hooks, at the gates the kernel already has:
- **Read** (`_read_scope` / `_read_reach` / `_assert_read_object`): allow if own-tenant **OR** the caller principal holds a `view|comment|edit` grant on this `object_id`. This lets a shared row cross the `owner==sub` clamp — and because a grantee can be a `user://` in another tenant, **cross-tenant per-object sharing falls out of the same mechanism** with no separate lane.
- **Write** (`_authorize_component_write` / `_assert_write_own_tenant`): a non-owner may mutate the object only with an `edit` grant; `comment` is a **constrained write** — it appends an `annotation` record that references the object, it never mutates the object; the owner always can.

The load-bearing invariant — **only the owner may grant** — is enforced *in the kernel*: a write of an `access.grant` is refused unless `granted_by == owner(object_id)`. Privacy sits below the app: even a rogue or buggy app cannot hand out access to data it does not own.

### 4. Two doors to the same grant: push and pull

- **Push (owner shares first).** A "Share…" action (one shared widget wired into File Explorer, Docs, Sheets, Slides, the Data browser) writes an `access.grant` and sends an invite (Inbox/mail) with the link.
- **Pull (consent-on-demand).** A forwarded link opens in the **Opener** (§5); resolution returns "consent required"; the viewer files an **access-request** (the request→decide shape from `/v1/data-requests` and `/v1/file-shares`, now at object+user granularity); the owner is notified out-of-band and **accepts / rejects / grants-for-a-period** (§6), which writes the `access.grant`.

Push and pull are **the same record reached two ways** — one primitive, two entry points, one audit trail.

### 5. The Opener — a universal type→viewer, with minimal disclosure

A default component resolves a link, reads the object's schema, and dispatches to the **governed type→viewer binding** (schema/noun → renderer, the OS's "Open With"). One Opener serves a property row, a Doc, or a File.

Before consent it must leak nothing it shouldn't. A per-schema **`x-share-disclosure`** knob sets the level: `opaque` ("someone shared an item — request access?"), `typed` (reveal the noun kind only), or `labelled` (reveal a title/owner — fine for "Team offsite", wrong for a health record). Correspondingly the kernel returns **404 (doesn't exist to you)** for sensitive nouns and **403 (exists, consent required)** for shareable ones — because a bare 403 confirms existence.

An `link:<token>` grant (opt-in, off by default) is the *only* place the platform adopts link-as-capability: the owner consciously chooses "anyone with the link may view", and it stays scoped, expiring, and revocable.

### 6. Out-of-band consent — the decision link is the one legitimate bearer token

The owner is notified over **Inbox (always)** plus **channel adapters** (SMS / WhatsApp / email). The notification carries a **decision link** that lets the owner accept/reject/grant without a full login — so it *is* a bearer capability, and is therefore **signed, single-use, short-TTL, and authorizes only the decision action, never data access.** This is the deliberate inverse of the data link (which carries no authority). Keeping that distinction crisp is the whole security of the flow.

### 7. The audit → correct loop — privacy made self-enforcing

Every access-request, grant, decision, and read is an **append-only, tamper-evident event** (the kernel's bitemporal immutability gives this for free for records; `platform.event` for the stream). A certified **auditor** component watches and can contain — the same pattern as the runtime broker auditor (#69):

- **The auditor reads access *metadata*, not payload.** It reasons over who asked, what was granted, who read, when, how much — never the object's contents. The watchdog is least-privilege; if it could read the data it would be the exact bypass this design prevents.
- **Detections are governed rules** (`governance.policy_rule`, [[ADR-0088]]) — a new check ships as approved data, not baked code. Examples: a grant attempted by a non-owner (kernel already blocks it — the auditor flags the *attempt*), access continuing past `expires_at`, a decision-link replayed, one requester fanning out across many owners, a component reading beyond its grant, an unusual exfiltration path.
- **Corrective actions split by reversibility.** Safe/reversible ones auto-fire (revoke the grant, expire the session, throttle the principal, alert the owner). Irreversible or outward-facing ones open a `platform.case` for a human (the decision spine, [[ADR-0029]]/[[ADR-0046]]).
- **Two clocks.** Stream events for fast containment; sweep them in batch for slow pattern detection.
- **The auditor is governed like everything else** — no self-exemption, its own actions logged, its grant revocable. "Who audits the auditor": its actions are in the same append-only log, reviewable by the steward.

## Consequences

- **Privacy becomes a kernel property, not an app promise.** Owner consent is required, owner-issued, kernel-enforced, and continuously audited — provable to a citizen as "here is everyone your data reached, by your consent, revocable now."
- **One primitive covers all data** (File, any row, Doc/Sheet/Slide) because it keys on the universal `ds:` id; cross-tenant sharing is the same mechanism as within-tenant.
- **The `owner==sub` clamp relaxes safely** — reads/writes honour grants, with scope enforced at the write path — without weakening tenant isolation (still the default).
- **New surface to defend:** a per-object grant store + lookup on the hot read/write path (needs an index, not a scan), the decision-token signer, and channel-provider secrets. The auditor is new attack surface too — hence least-privilege on it.
- **Cost:** grant-lookup latency on reads (mitigated by an owner/grant index keyed on `object_id`); a messaging provider (SMS/WhatsApp) integration; a modest new noun set (`access.grant`, `access.request`, `annotation`, the type→viewer binding).

## Reuse vs. build

**Reuse:** the `ds:<tenant>:<schema>/<id>` id + `/v1/resolve-ref` as the object handle/embed target; the request→list→decide lane shape (`/v1/data-requests`, `/v1/file-shares`); the steward-signed + kernel-verified authorization pattern (`_issue_grant` / `_steward_authorizes`); `governance.consent` as the nearest existing "sub → grantee → scope → expiry" record to generalise; Inbox + Mail for invites; the runtime auditor + rule engine + decision spine + `platform.case` for the audit loop.

**Build:** a grantee that is a **specific end-user** and an **object id** (nothing today is object- or user-scoped); kernel owner-stamping for `x-ownership: user` schemas + an owner/grant index; the read/write grant checks + owner-only-issuance invariant; the Opener (type→viewer) + `x-share-disclosure`; the signed single-use decision token; SMS/WhatsApp/email channel adapters.

## Open questions (decide before/at S1)

1. **Unknown-requester identity.** A grant must target a *principal*. If the forwarded-to person has no AirawatOS identity, do we require sign-in first, or capture a verified contact (email/phone) that binds to an identity on later sign-in? "Request access as an anonymous phone number" is a trap — you'd grant to a contact, not a person.
2. **Channel provider** for SMS/WhatsApp (and its secret/consent-to-contact posture). Inbox works today with no dependency; the external channel is a real new integration.
3. **Where the grant lives + cross-tenant resolution.** Kernel-local index for same-tenant grants vs network-published (signed, resolvable) for cross-tenant grantees — likely both, mirroring `governance.access_grant`.
4. **`comment` scope** needs a small `annotation` noun; ship it in S1 as a first-class scope or defer comment to a later slice (view/edit first).
5. **Disclosure defaults** per schema family (personal office docs vs civic records) — pick safe defaults so a new noun isn't accidentally `labelled`.

## Rollout (slices)

- **S1 — Kernel primitive.** Govern `access.grant`; add `x-ownership` to schema governance; kernel stamps owner on `x-ownership: user` schemas + owner/grant index; enforce the read + write grant checks and the owner-only-issuance invariant. **Prove:** a Doc shared user→user — grantee reads it (view honoured), edit denied without an `edit` grant, owner can revoke.
- **S2 — Push share + invite.** The shared "Share…" widget + `/bridge/share` + Inbox/mail invite + the `/share/<ref>` open route, wired into Docs first; cross-tenant grantee.
- **S3 — The Opener + pull/consent-on-demand.** Universal type→viewer + `x-share-disclosure` + `access.request` (request→decide) + the signed single-use decision link; Inbox decision surface.
- **S4 — Channels + generalise.** SMS/WhatsApp/email adapters for the decision link; wire Share/Open into File Explorer, Sheets, Slides, the Data browser; the opt-in `link:<token>` mode.
- **S5 — Audit → correct.** The access-audit event feed + a certified auditor over governed `governance.policy_rule` detections → auto-revoke / alert / open a `platform.case`; a "shared with me / shared by me / who accessed my data" console + one-click revoke.

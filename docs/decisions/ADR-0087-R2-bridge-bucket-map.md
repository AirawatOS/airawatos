# ADR-0087 R2 — app-host bridge bucket map (migration plan)

Status: Proposed (2026-09-15) · Source of truth: `platform-spec/reference/app_host.py` `BRIDGE_VERBS` + `ENGINE_VERBS`

## Does R2 require any component (app) code change?

**No — for the migratable bucket, zero app changes.** R2 keeps every `/bridge/<verb>` URL, its
request/response payload, and its authorization gating (the app-level allow-list `required_schemas` /
`data_browser`, plus the kernel's RBAC/tenant scoping) **identical**. What changes is *internal to the host*:
the ~50 near-identical bespoke handler methods are replaced by ONE table-driven generic proxy keyed off the
`BRIDGE_VERBS` map that already exists. An app still calls `POST /bridge/query {app_id, schema, …}` exactly
as today.

Note the distinction from the R1 `/bridge/gov` path: the base registry/directory verbs (`query`/`save`/
`resolve`/…) are the broker's **implicit clean-room surface** every app has (ADR-0030), gated by the app's
schema allow-list — they do **not** require a `calls: […]` declaration. Only NEW governed network/kernel
capabilities (like `network.data_exchange`) are declared and go through `/bridge/gov`. So R2 adds **no**
manifest declarations to existing apps.

## Buckets (115 bridge paths)

### Bucket A — thin governed passthroughs → MIGRATE to one generic dispatcher (no app change) — ~50
Handlers that forward the user token + `component://` obo to a single governed kernel/network verb and return
the result. They differ only in the target verb + a schema/param or two — exactly what a table collapses.

- **reads → `registry.read`** (~27): resolve · ~~resolve-citation~~ · participant-resolve · ~~retrieve~~ · original ·
  catalog · components · connections · market · participants · roles · role-members · user-roles · users ·
  schemas · schema-history · schema-resolve · interfaces · interface-resolve · runs · schedules ·
  change-requests · role-requests · component-read · component-preview · jurisdictions · credential-verify
- **reads → `registry.query`** (~7): query · service-status · service-search · profile-get · my-credentials ·
  service-transactions · service-offerings
- **writes → `registry.write`** (~11): save · schedule · role-grant · service-init · service-confirm ·
  service-route · service-consent · profile-save · citizen-app-add · citizen-app-remove · credential-accept
- **`network.change_request`** (~7): change-request · change-request-decide · store-revoke · store-deprecate ·
  schema-request · role-request · role-request-decide
- **`governance.decide` / `governance.task_complete`** (~4): decide · approve-rule · approve-rules · complete
- **`platform.fetch`** (1): fetch

Migrate in three sub-slices, safest first: **A1 = reads** (no mutation, ~34) → **A2 = change_request +
governance decides** (~11) → **A3 = registry writes** (~11). Each sub-slice deletes the dead handlers and
re-verifies every live app path before the next.

**Flag / verify individually before moving (clean governed target but may carry pre/post logic):**
`secret` (→ `platform.secret`, Vault write — treat as B for now), the `service-*` verbs and `profile-*`
(cross-tenant / consent gating), `my-requests` / `publish-request(s)` / `publish-decide` (confirm their verb
tag; not in the core map excerpt).

### Bucket B — app-internal host logic → KEEP in host now (candidates to become engines later) — ~35
Not thin proxies; they do real work in the host (write source, call the certifier, stream a model, touch
Vault/filestore, mint logins, ingest media). ADR-0087 says these stay as host services or migrate to certified
ENGINES — never onto the generic passthrough.
component-save · component-scaffold · project-compose · project-publish · project-test · project-delete ·
seed-test-data · solution-generate · solution-expert · service-expert · expert-chat · schema-advise ·
agent · agent-brief · ai-assist · complete? (verify) · user-search · file-upload · upload-chunk · file ·
asset · tile · original? · ingest-document · reprocess · transcribe · voice-config · i18n-translate ·
set-locale · set-theme · citizen-register · service-offering-save · service-offering-manage · secret ·
git-binding · git-push · camera-configure · camera-delete · message-intake · sms-intake · whatsapp ·
offline-relay · provision-device · data-schemas (host helper) · gov + verbs (R1 infra, stay)

### Bucket C — already engine-dispatched (route c) → LEAVE — ~30
Everything in `ENGINE_VERBS` (dispatched first in `do_POST` via the engine loader): news-reclassify ·
leave-apply/decide · attendance-mark · expense-apply/decide · policy-resolve · finance-post · posting-apply ·
authz-check · employee-provision · proposal-submit/save/decide · project-rollup/review/evaluate/adjust ·
allocation-set/list · payroll-preview/apportion/schedule · matchpolicy-get/set · match-preview · gap-scan ·
campaign-create/assign · (chat-*/mail-* engine verbs). These are the *target state* for Bucket B logic.

### Bucket D — KNOWN GAPS: no governed verb yet → govern the verb FIRST, then migrate — ~4
install (`gap:platform.component_install`) · app-install / app-uninstall (`gap:platform.app_shelf`) ·
city-onboard (`platform.workflow_instantiate` — confirm governed) · the `platform.runtime_invoke` trio
(run · reprocess · ingest-document) mint run-tokens via the scheduler, so they carry logic → treat as B/C.
Each needs its governed interface published (exactly like we did for `network.data_exchange`) before it can
ride the generic path.

## R2 execution plan (hold for approval before editing the live host)

1. **A1 — reads:** add a generic `_bridge_passthrough(verb)` driven by `BRIDGE_VERBS`; route the ~34 read
   verbs through it; delete their bespoke handlers. Re-verify a representative app per verb-family (Data,
   City Scan, Inbox, Studio read paths). One app-host image bump; UI intact check.
2. **A2 — change_request + governance decides.** 3. **A3 — registry writes.** Same pattern, mutations get
   extra before/after verification.
4. Leave B (host logic) and C (engines) untouched. Address D by governing verbs (separate ADR work).
5. (R3, later) promote the `BRIDGE_VERBS` table itself to a governed interface registry so even the map is data.

Net effect: the host shrinks by ~50 hand-written handlers to a thin, auditable, allow-listed proxy; no app
changes; behaviour identical; every mutation still identity + obo + grant-checked exactly as today.

## A1 outcome (2026-09-15) + key finding

**Shipped (reference:0.2.12):** the 5 genuinely-uniform directory reads — `interfaces`, `jurisdictions`,
`interface-resolve`, `schema-resolve`, `credential-verify` — now dispatch through one `DIR_READS` table +
`_bridge_dir(verb)` (3 modes: get_list / resolve_id / post_through). 5 bespoke handlers deleted, no app change,
behaviour byte-identical (verified live: interfaces/jurisdictions list, interface-resolve returns the record,
schema-resolve 200 on a real schema + faithful 400/404, credential-verify faithful passthrough).

**KEY FINDING — reads do NOT collapse into one clean table.** The host's bulk is not a swarm of identical
proxies; it is many handlers each with a little bespoke request/response shaping. Only a minority of "reads"
are truly uniform. The rest split into:
- **logic-bearing reads that must STAY** (own handlers): `query` (allow-list + personal owner-scoping + inbox/
  task role-expansion + pagination), `resolve` (inbox logic), `retrieve`, `participants`/`participant-resolve`
  (session filter/enrich), `schema-history` (multi-call), `resolve-citation`, `my-requests`, `schemas`
  (two-upstream reshape `{schemas,pending}`).
  > **Since retired (PLAT-0004):** `retrieve`, `resolve-citation`, and the kernel `schemas` GET no longer
  > exist — the schema catalogue read moved to the network. This "must STAY" list predates that retirement.
- So the realistic R2 for reads = **dedup the uniform boilerplate (done) + leave logic handlers in place**, not
  a grand generic dispatcher. The big registry verbs (`query`/`resolve`/`save`) carry real logic and are NOT
  safe table-collapse candidates — they'd need their logic preserved handler-side regardless.

**Revised plan:** A2 (change_request + governance decides) and A3 (registry writes) are still worth doing —
those handlers ARE largely uniform proxies to a single governed verb — but expect the same pattern: a faithful
table for the uniform ones, hands off the few with pre/post logic. The dramatic-shrink premise from the
original R2 pitch is overstated; the honest win is incremental dedup + keeping the boundary auditable via the
`BRIDGE_VERBS` map (already exposed at GET /bridge/verbs). Recommend pausing broad migration and instead
governing the Bucket-D gaps (install / app-shelf) next, which removes real "gap" debt.

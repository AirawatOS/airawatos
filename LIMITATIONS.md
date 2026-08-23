# AirawatOS — Known Limitations & Tech Debt

A living backlog of things we built as walking-skeletons or deferred on purpose. Each item:
**what's limited → why it matters → the fix.** Keep appending as we go; don't silently ship past these.

Legend: 🔴 security/trust · 🟠 correctness/robustness · 🟡 completeness · 🔵 ops/infra · ⚪ cosmetic

---

## Security & Trust

- ✅ **[DONE] Key publication is access-controlled (anti-impersonation + proof-of-possession).** `POST
  /v1/keys` now requires BOTH: (1) an identity token whose `sub` IS the actor id (you can only publish
  your own id's key), and (2) a signature over a one-time server challenge (`POST /v1/keys/challenge`),
  verified against the submitted pubkey (you must hold the private key). Verified: genuine own-key
  publish = 200; impersonation (anita→kanpur-admin id) = 403; no token = 401; bad PoP = 403; replayed
  challenge = 400. The offline-verify story is now "verifiable AND unspoofable". Remaining: PoP proves
  control of the *Vault-held* key (the platform signs the challenge on the user's behalf after verifying
  their token) — true human-held-key PoP is the wallet path (ADR-0049); challenges are in-memory (fine,
  120s TTL).

- 🔴 **Vault is dev-mode (in-memory).** The CA key, identity key, and (future) steward keys live in
  Vault transit, but `server -dev` loses everything on a Vault restart → all signatures invalidated.
  **Fix:** Vault with persistent storage (Raft/file) + auto-unseal; back up/rotate the transit keys.
- ✅ **[DONE] Steward signing key is a per-tenant Vault transit key** (`steward-<tenant>`, non-exportable),
  provisioned on tenant register; grants signed via Vault transit. (The old fixed-seed demo path is
  superseded.)
- 🔴 **Identity login is passwordless dev auth** over a fixed user list (`identity.py USERS`). **Fix:**
  front with Keycloak/an OIDC provider; the token + JWKS contract stays the same.
- ✅ **[DONE] Certify/publish/retire are PUBLISHER-gated (no publishing in someone else's name).**
  `/v1/certify`, `/v1/store/publish`, `/v1/store/retire`, `/v1/certificates/retire` now require an identity
  token whose tenant == the id's **steward prefix**, with a publisher role — so only the steward of
  `ds:<steward>:…` may certify/publish/retire it. Verified: genuine own-steward = 200; cross-steward
  (kmc→airawat, airawat→kmc) = 403; no token = 401. (Reference gate = identity token tenant match; a fuller
  model would sign the request with the participant's directory key, like ADR-0024 participant signing.)
- ✅ **[DONE, tiers 1-3] Verified certify — the CA runs a conformance suite and refuses to sign failures.**
  `network/conformance.py` runs STATIC checks the CA can trust: **manifest & identity** (required fields,
  id grammar `ds:<steward>:<kind>/<local>`, known kind, kind matches id, steward == publisher),
  **vocabulary** (every declared read/write/required_schema is GOVERNED in the catalog), **artifact
  integrity** (the checked meta.yaml is the artifact's — its hash is in the file set; entrypoint present;
  the certified digest is **recomputed from the content manifest** with the same formula as
  `package.artifact_digest`). `POST /v1/certify` with `{meta_yaml, files}` runs it and returns **422** on
  failure (`conformance.verified=true` on the cert when it passes). `platform-spec/reference/conform.py`
  is the developer client. Verified: inbox app → certified (digest == host admission digest); ungoverned
  schema → 422; unknown kind → 422. Legacy digest-only path still allowed but marks `verified:false`.
- ✅ **[DONE] Conformance tier 4 (BEHAVIOURAL).** `platform-spec/reference/conformance_run.py` RUNS the
  component confined against a recording/ENFORCING test-broker (its real door) with a fixture and asserts
  it only reads declared scopes, only writes declared schemas (+ output schema-valid), and only egresses
  declared hosts — any undeclared attempt is denied AND recorded as a violation → fail. Verified: terrain
  driver PASS; a bad driver FAILs on undeclared-write + undeclared-egress. GAPS: the behavioural report
  isn't yet folded into the signed certificate (a signed behavioural attestation from a trusted runner);
  it exercises ONE fixture path (not fuzzed/branch-covered); the CA still can't recompute the artifact
  digest without the upload (host enforces it at admission).

## Secrets & external egress (drivers that call out)

- ✅ **[DONE] Per-tenant, per-component secrets — tenant sets at install, admin rotates, broker injects.**
  Components DECLARE `egress: [<hosts>]` + `secrets: [<NAMES>]` in the manifest (checked by conformance,
  static `external-contract` + behavioural egress enforcement). `platform-spec/reference/secrets.py`
  stores values in Vault (KV v2) at `secret/<tenant>/<component>/<name>` — never in the registry/code/
  component. `/set` + `/rotate` (tenant-admin only) + `/status` (names+version, NEVER values). Brokered
  egress `/fetch` reads the secret, INJECTS it (query/header), fetches, and returns only the result with
  the key REDACTED — the component never sees the raw key. Verified: set → status(v1) → fetch (injected,
  egressed to earthengine, key redacted) → rotate → fetch uses v2; non-admin set = 403; unset secret
  fetch = 400.
- ✅ **[DONE] Brokered egress is in the KERNEL broker with RUN-TOKEN isolation.** `POST /v1/fetch`
  (X-Run-Token) resolves the run's `(tenant, component, egress)` from the run record — the component
  presents only `{url, inject.name}`, it CANNOT forge tenant/component — refuses hosts outside the
  component's declared egress, and delegates to the secrets service (internal-token-gated so only the
  broker may `/fetch`) which injects `secret/<tenant>/<component>/<name>`. So a run can only egress to its
  declared hosts and only inject its OWN secrets. Install now records the RUNTIME tenant (from the
  installing admin) + egress on the run token (fixing a latent bug where the broker derived tenant from
  the component's publisher steward, wrong after ids moved to ds:airawat:). Verified: genuine fetch
  (run-terrain, tenant kmc) injects GEE_API_KEY (egress earthengine); undeclared host = 403; no run token
  = 401; direct-to-secrets without the internal token = 403. Also fixed a mutate-after-sign bug —
  `conformance` is now inside the CA-SIGNED certificate core (was appended after signing → broke the
  kernel's cert verification at install).
- ✅ **[DONE] Egress + secret-use are audited (prov.egress) and the tenant can VIEW them.** Every broker
  `/v1/fetch` (allowed OR denied) writes a governed `prov.egress` record — run, tenant, component, host,
  path, secret NAME, outcome, reason, upstream_status — NEVER the key or the query string. The **Components
  app** (`ds:airawat:app/components`) is the tenant's console: per installed component it shows the declared
  egress, lets a tenant-admin SET/ROTATE its API keys (`/bridge/secret`), and renders its external-call log
  (`prov.egress` via `/bridge/query`, tenant-scoped so kmc sees only kmc's). Verified: allowed (earthengine,
  path only) + denied (evil.example.com, egress-not-declared) rows captured; Components lists the 3 drivers/
  engines with contracts. (Renamed from "Audit" — a decision's audit is its case history/receipt, distinct.)
  GAPS: no per-egress rate-limit/quota; the log isn't yet exportable/signed; a cross-component "all activity"
  view would need an admin-wide query surface.
- 🔴 **Component Host confinement is L1/L2 only.** L1 (shim) is bypassable by native code; L2 (container)
  shares the host **kernel** (a kernel exploit escapes). **Fix:** L3 (microVM/gVisor) / L4 (Wasm) for
  higher-sensitivity components; let a tenant require a minimum level.
- 🟠 **User-facing authz is tenant-scope only.** `/v1/registry/resolve` scopes to `claims.tenant`; there's no role-based
  authz, no ADR-0028 role-grants, no row-level policy. **Fix:** a policy layer (roles × scope × action).
- 🟠 **Only `/v1/registry/resolve` enforces user authz.** Other read surfaces are unguarded. **Fix:**
  route all reads through the same authn/authz.
- 🟠 **Kernel derives + scopes tenant but doesn't validate `claims.tenant` against the registry.**
  **Fix:** reject tokens whose tenant isn't a registered, active tenant.
- ✅ **[DONE] Steward write-grants are issued at install time** — `POST /v1/components/install` (with a
  tenant-admin token) auto-issues the steward-signed grant from the component's declared writes
  (`/v1/grants/issue`). Steward key is a per-tenant **Vault** transit key (non-exportable), provisioned
  on tenant register. ✅ solution-pack install DONE; ✅ uninstall→revoke DONE (`/v1/components/uninstall` de-registers
  the run-token + revokes grants; `/v1/solutions/uninstall` revokes all members — both admin-gated).
  ✅ reads-as-grants DONE (grant carries reads+writes; broker /v1/read enforces the read grant too).
- 🟠 **Grants have no expiry or scope-narrowing** — issue-time only, no `not_after`, no per-cell/row
  constraints. **Fix:** add `expires_at` + optional constraints; kernel checks them.
- 🟠 **Registry does not validate objects against installed schemas.** The kernel registry is
  schema-flexible; a write isn't checked against the governed `geo.terrain` definition. **Fix:** validate
  writes against the installed vocabulary (the pack the tenant installed).
- 🟡 **No edge gateway (Kong/Envoy).** By design the kernel enforces (zero-trust), but an edge layer for
  TLS termination, rate-limiting, and coarse authn is still worth adding — as an optimization, never the
  sole authority.

## Platform Services (PLAT-0002)

- ✅ **[DONE] Notification service** — writes items into the unified inbox (reference `notify.py`).
- 🟡 **LLM-gateway** — not built (needed for intelligence-layer agents; brokered + metered).
- 🟠 **File store reached directly in the demo.** Should be reached via broker `file.read`/`file.write`
  capabilities (tenant-scoped), like every other component I/O — not a bare HTTP call.
- 🔵 **Reference services run as host processes, not in compose.** `identity :8093`, `filestore :8095`,
  `app-host :8099` are launched by hand (die if not backgrounded; not orchestrated/restarted). **Fix:**
  give them Dockerfiles + compose services (or a distro `install.sh`).

## Multi-tenant & Federation

- 🟡 **No cross-operator data-migration path.** `rehost` re-points the host binding, but there's no
  export-(tenant-signed)-facts-from-A → import-and-verify-on-B flow. **Fix:** a portable, self-verifying
  tenant data export/import (the thing that makes a move actually carry the data).
- 🟡 **Operator is not a first-class participant kind.** We used `ds:airawat:operator/*` ids but the
  directory doesn't model operators (hosting inventory, endpoints, role). **Fix:** participant `kind:
  operator`; network resolves `tenant → current operator endpoint` so clients find where a tenant lives.
- 🟡 **Tenant lifecycle** (suspend/delete/transfer-of-steward) not wired.
- 🟡 **`environment: dev|prod` is stored but unused.** ADR-0051's sandbox relaxation (a dev tenant runs
  its own uncertified drafts) isn't implemented.
- 🟠 **Reference resolution is *routed* but not *fetched-at-source* across participants.** `POST
  /v1/resolve-ref` is the one resolver every inbox item / task subject goes through. It correctly
  classifies a `ref`: `ds:<mytenant>:…` → local registry (returns the object); `ds:<other-steward>:…`
  → `remote` (looks up the stewarding participant in the network directory); `<scheme>://<steward>/id`
  → `connector` (a resolvable entity, ADR-0015). **But the actual cross-participant object fetch — send
  a signed federation request to the steward's resolve endpoint and get the object back, data-at-source
  (ADR-0023) — is NOT built.** Neither is the entity **connector** side (`building://…` → the agency's
  system-of-record adapter). Today remote/connector refs return a routing stub, not the subject.
  **Fix:** per-steward resolve endpoint + signed Data-interaction request + `resolve_via` endpoint
  discovery in the directory; connector adapters per scheme. This is the federation data plane and the
  thing that makes the platform federated rather than a single-tenant monolith.
- 🟡 **Inbox item → task handler dispatch is not built (declaration-driven rendering).** The item now
  carries `handler` + `actions`, and clicking resolves the subject + shows the declared action buttons,
  but pressing an action is a no-op stub. The design: each item names a **handler** — a governed
  interaction/task declaration (ADR-0045) the inbox renders generically, or `app://<steward>/<app>/<route>`
  it dispatches to — and each action posts a **decided change-request → decision → receipt** (ADR-0056).
  So "approve building plan" vs "decide on flood pumps" live in each *solution's* declaration, not in
  the inbox. **Fix:** wire the case→task→inbox loop + the handler registry + action→decision→receipt
  (planned for M3 Citizen Service / M4 Flood Response).

## Decision / execution engine (ADR-0045/0046/0050)

- 🟠 **The decision-service writes directly to the registry, not through the broker.** Like the other
  reference services (notify), `decision.py` PUTs the governance.decision / task / case via
  `/v1/registry/objects` — so there's no steward grant check and no attributed provenance (ADR-0052) on
  those writes. It DOES verify the user token, so the recorded `authority` is authentic. **Fix:** make
  the decision-service a certified component writing through the broker with a grant + `component://…`
  attribution.
- ✅ **[DONE] Decisions AND orders are signed by the acting OFFICIAL's own key (per-user).** Shared
  `signing.py` signs the canonical object (RFC8785 JCS + Ed25519) with a per-user Vault transit key
  `user-<tenant>-<local>` (non-exportable, born on first use); `signature.key_id` = the person
  (`user://<tenant>/<sub>`), so a decision/order carries real non-repudiation, not just a tenant vouch.
  `POST /verify {obj}` is generic (works for any signed object). Verified: decision + order both signed by
  `user://kmc/kanpur-admin`; genuine → valid (response AND registry round-trip); tampered → invalid.
  ✅ **Pubkeys published to the directory for OFFLINE verify.** On first sign, `signing.py` publishes the
  actor's pubkey to the network's authority-signed key directory (`POST /v1/keys`); `signing.verify`
  resolves it from `POST /v1/keys/resolve` (no Vault). Verified: a third party with ONLY the public
  directory + `crypto` verifies genuine=True / tampered=False; `/verify` reports `source: directory`.
  Remaining: (a) ✅ DONE — `/v1/keys` is now access-controlled (identity token + proof-of-possession; see
  the dedicated entry under Security & Trust). (b) keys are **server-side in
  Vault**, not client-held — true end-user non-repudiation signs in the wallet/device (ADR-0049). (c) fixed
  the "mutate-after-sign" footgun: `triggered_workflow` is a separate response field, never in the signed
  object.
- ✅ **[DONE / partial] Decision → order → SOP workflow → agency tasks → fulfilment.** The back half is
  built on a DOMAIN-AGNOSTIC engine: `workflow.py` (ADR-0050) loads a `platform.workflow`, issues a
  **steward-signed `governance.order`**, instantiates a `platform.task` per step **routed to that step's
  role**, notifies each, and rolls step-completion up to fulfil the order + close the case. The decision-
  service triggers it generically (if the selected recommendation carries `sop_workflow`); else it closes
  the case as before. Verified: flood decision → signed order → 3 tasks to water/sanitation/disaster
  roles → complete all → order fulfilled, case closed. Remaining engine gaps below.
- ✅ **[DONE] `/complete-task` enforces RBAC.** Only the task's assignee may complete it: a user-addressed
  task → `claims.sub == assignee`; a role-addressed task (`role://<tenant>/<role>`) → the role is in
  `claims.roles` AND the tenant matches. No admin bypass. A `blocked` task is rejected 409. Verified:
  clerk→disaster task = 403, wrong-agency = 403, blocked = 409, correct role = 200. (Delegation via
  ADR-0026 would extend `_authorized` later; role→user resolution assumes the identity token's `roles`
  claim, which is the dev identity's fixed list — a real IdP/role-grant store replaces that.)
- ✅ **[DONE] The workflow interpreter runs the declaration as a DAG.** `platform.workflow` steps carry
  `after: [step_ids]`; `instantiate` creates each task `open` (deps satisfied) or `blocked`; `complete-task`
  ADVANCES — unblocks every blocked task whose `depends_on` are all done — then rolls up. State lives in
  the registry (task statuses), transitions in the declaration; the engine is stateless between events
  (crash-safe, resumable). Verified: sequence (assess→desilt→pumps), fan-out (advisory ∥ desilt), and JOIN
  (standdown after [pumps, advisory]) all gate correctly. Remaining: no timeouts/SLA/escalation, no
  branching/conditionals (only AND-joins), no cycle validation, no rollback/compensation. **Fix:** add
  guards/SLA timers + conditional edges when a vertical needs them.
- ✅ **[DONE] Orders are signed by the issuing authority (per-user)** — see the decision/order signing
  entry under Security & Trust. `issued_by` is now also a signer (their `user-<tenant>-<local>` Vault key).
- 🟡 **Demo super-user holds all agency roles.** `kanpur-admin` was given water/sanitation/disaster roles
  so one session sees the SOP fan-out; real deployment routes each step to a separate agency user
  (identity has `water-engineer`/`sanitation-officer`/`disaster-officer` accounts for that).
- 🔵 **Identity dev key is ephemeral → restarting `identity.py` invalidates all tokens** against any
  verifier that cached its JWKS (notably the long-running **kernel** container → "bad signature" until
  restarted). Front with a real OIDC provider (persistent keys); dev workaround = restart the kernel
  after restarting identity. (Also observed: intermittent verify failures under short token TTL.)
- 🟡 **Contestation/correction not built.** A decision receipt is recorded but there's no contest → review
  → corrected-decision loop yet (ADR-0046). The `decision` inbox item exists; the flow behind it doesn't.

## Flood-forecast pipeline (sense → predict → detect → advise)

- 🟡 **The pipeline is one process, not certified components chained by events.** `components/pipelines/
  flood-forecast/run.py` runs all four stages in-process and writes via `/v1/registry/objects` directly.
  Production = four certified components (weather driver · flood-risk engine · threshold rule · guideline
  engine) through the broker with steward grants + attributed provenance, **triggered by events** (a
  forecast fact → a rule → a prediction → an alert → recommendations). The event/trigger fabric
  (ADR-0014 decision loop + alert engine) is NOT built — the pipeline is run manually, not auto-fired.
- 🟠 **Weather + prediction are synthetic/offline.** `met.forecast` is a fixed rainfall figure and
  `risk.flood` is a deterministic terrain×rainfall susceptibility score — no real met feed, no hydrology
  model, no ponding-site or prior-incident inputs (the schema has the fields; the engine doesn't use
  them yet). **Fix:** real forecast ingestion + a calibrated flood model via brokered egress.
- 🟡 **Knowledge base is a handful of seeded `knowledge.guideline` records, not the spec-13 knowledge
  layer.** Recommendations cite a guideline id + clause, but there's no corpus/citation-contract/
  versioning behind it. **Fix:** wire the real knowledge layer so citations resolve to governed docs.

## Events & automation (the trigger fabric)

- ✅ **[DONE] Every registry write emits an event; subscriptions react.** Kernel `registry_put` fires a
  `platform.event` (fire-and-forget, skips event-on-event) to the automation service; `automation.py`
  persists each event (queryable stream / audit), matches `platform.subscription` records (WHEN → THEN),
  and fires actions (HTTP). Verified: the flood pipeline stops at `signal.alert`; the write emits an event
  → the subscription (severity∈{high,severe}) fires the flood advisor → recommendations + case + decision
  task appear with NO hard-coded call. 86 events captured across all schemas. Subscriptions hot-reload.
- ✅ **[DONE] Delivery is durable (outbox + retrying relay + idempotent consume).** The kernel persists
  every `platform.event` as `status=pending` in the registry (the durable outbox) as part of the write;
  `event_relay.py` drains it AT-LEAST-ONCE — deliver → `delivered` on ack, else retry with exponential
  backoff, `deadletter` after 6 attempts. The automation consumer dedups on event id. Verified live: with
  automation DOWN, a flood alert's event stayed `pending` (not lost) and the relay retried; bringing
  automation UP delivered it → advisor fired → case opened ("started late, not never"); a re-delivered
  event returns `duplicate:true` (no double-fire). Remaining: (a) NOT a true single-txn outbox — the object
  write and the event write are two sequential registry puts (a crash between them loses the event);
  **fix:** same-transaction append. (b) relay POLLS the registry (`status=pending` scan) every 1s — fine
  for the reference, not for volume; **fix:** an indexed queue / real broker (Kafka/NATS) behind the same
  seam. (c) only the kernel→automation hop is durable; automation→advisor is still best-effort within
  automation. (d) `_PROCESSED` dedup set is in-memory + unbounded.
- 🟠 **The kernel→automation webhook is unauthenticated**, and `/events` trusts whatever it receives.
  **Fix:** sign/authenticate the event; the automation should verify it came from the kernel.
- 🟡 **Subscription match is equality-only** (`subject_schema` + `where` field∈values). No operators
  (>=, ranges), no cross-field logic, no rate-limit/debounce. **Fix:** a small predicate language.
- 🟡 **Single automation instance, in-memory subscription cache.** No sharding/leader-election; a restart
  reloads from the registry (fine) but concurrent instances would double-fire. **Fix:** idempotent action
  keys + a scale story.
- 🔵 **`docker-compose.yml` (untracked) now also carries `EVENT_SINK`** — the kernel→automation wiring
  isn't version-controlled (same root issue as the compose file itself).

## Runtime & Ops

- 🔵 **`docker-compose.yml` (workspace root) is untracked** — the stack wiring, incl. the Vault service,
  isn't version-controlled. **Fix:** move it into a repo (a `deploy/` or distro repo).
- 🔵 **Service-layer case orchestration state is in-memory** (process-lifetime); only facts persist.
- 🟠 **app-host browser bridge uses the same-origin CSP-locked ("trusted") tier.** The stricter
  null-origin + `postMessage` ("sandboxed") tier didn't deliver reliably in-browser and was set aside.
  **Fix:** revisit the sandboxed tier for genuinely-untrusted third-party apps.

## Data & UI

- 🟠 **`geo.terrain` elevation is a synthetic surface** (deterministic, offline) so the driver runs
  confined. **Fix:** real DEM ingestion (SRTM/Copernicus/Open-Elevation) via a brokered egress capability
  or a bundled DEM baked into the driver image.
- ⚪ **Explorer render is a dependency-free canvas hexmap**, not deck.gl/MapLibre (kept CSP-clean). Fine
  for the skeleton; a richer client is a later polish.
- ⚪ **Leftover test cell** `ds:kmc:geo/terrain/grant-probe` (h3="x", no boundary → invisible on the map)
  from write-authz testing. Harmless; delete when convenient.

---

## Design note — "Install = grant" (the intended fix for manual grants)

When a **tenant installs a component or solution pack**, that install *is* the moment the tenant grants
the component permission to read/write the specific registries (schemas) it declares. The flow:

1. A component/solution manifest declares `reads: [...]` / `writes: [...]` (schemas it needs).
2. Installing into tenant T = the tenant's steward **reviewing and signing a grant** for exactly those
   scopes (like app permissions at install time) — not a separate manual step.
3. The kernel then enforces those steward-signed grants on every write (already built).
4. Uninstall / revoke = delete the grant.

This unifies the certified supply chain (certify → publish → **install-as-grant** → run) with tenant
sovereignty: the vendor declares what it needs, the **tenant decides** whether to allow it, and the
grant is the artifact of that decision. Solutions grant all members' needs in one step.
**Status: BUILT** (components AND solutions). Install issues the grant(s) — tenant-admin approval →
steward Vault key signs the declared writes; `/v1/solutions/install` fans out to every member with one
approval. TODO: reads-as-grants, uninstall=revoke, grant expiry.

## Component scheduling — the clock-driven trigger (platform.schedule + scheduler)

**Status: BUILT.** A component now runs three ways: **manual** ("Run now" in the Components app),
**event** (platform.subscription → automation), and **schedule** (cron). The schedule leg:
`platform.schedule` (tenant-owned config: cron + component + enabled/overlap) → a generic `scheduler`
reference service (:8103) ticks each minute, fires due schedules through the SAME confined run path a
manual/event trigger uses (kernel run-token → host → broker), and stamps last_run/next_run/last_status
back onto the record. Manual + scheduled runs are identical: cert-verified admission, broker-mediated
I/O, `component://…` attribution (ADR-0052), prov.egress audit. Domain-agnostic — the scheduler knows
nothing about the component; "terrain nightly at 02:00" is one data record. Verified live: terrain fires
by cron AND by Run-now, writes attributed geo.terrain, RBAC refuses a non-admin, edits preserve stamps.

Reference shortcuts (production hardening TODO):
- The scheduler resolves a component's artifact from a **local COMPONENTS_ROOT path** (`<root>/<kind>s/
  <name>`). Production runs the **signed package** fetched from the marketplace, not a host path.
- **Run receipts are in-memory** (a 200-entry ring per scheduler process). Production persists each run
  as a durable record (start/finish/exit/attribution) so history survives restarts.
- **catch_up** is declared on the schema but not yet honored — a tick missed while the scheduler was
  down is skipped, never replayed. **overlap=skip** IS enforced (in-flight guard).
- Timezone (`tz`) is declared but the tick evaluates cron in **UTC** only.
- The scheduler reads/writes the registry **unauthenticated** (reference, like automation.py); it should
  act under its own service identity so its writes are attributable.

## Steward grants now cover READS, and are issued by the DATA-OWNER (runtime) tenant

Two correctness fixes surfaced while wiring scheduled runs:
- The install-time grant is now issued for the **runtime tenant** (the data owner, e.g. kmc) — NOT the
  software publisher's steward prefix (e.g. airawat). A driver published by `airawat` running in `kmc`
  reads/writes *kmc's* data, so **kmc's** steward must consent. The broker's point-of-use authz now
  checks the run-token's runtime tenant too (both sides aligned). Previously the grant was issued for
  the publisher tenant, silently failed (publisher tenant has no steward), and every brokered read/write
  404'd/403'd — no component could actually run confined. Now grants carry `reads` + `writes` and the
  broker honors both. TODO (unchanged): uninstall=revoke, grant expiry.

## Roles are governed ACTOR vocabulary (actor·verb·noun) — Slice 1

Roles are no longer free-form strings a developer types into meta.yaml. A role is the ACTOR leg of the
actor·verb·noun ontology and is now GOVERNED like nouns (schemas): a canonical role lives in the network
catalog, signed by the standards body (`network.role`, `AUTH.sign_role`). To add a role a developer files
a change-request; only the standards body can sign it in (POST /v1/roles is steward-gated — a developer
token gets 403). Certification enforces it: conformance tier-2 `governed-roles` refuses any component whose
`meta.roles` contains a role not in the canonical catalog (verified: ungoverned `flood-marshal` → 422;
after the role is published → certifies). The per-tenant `governance.role` catalog becomes the INSTALLED
SUBSET — because certify guarantees an app only declares governed roles, only governed roles ever reach it.
Endpoints: POST/GET /v1/roles, POST /v1/roles/resolve. Seeded canonical set: tenant_admin, resident, clerk,
water-engineer, sanitation-officer, disaster-officer, steward.

Deferred (next slices): roles pinned into DOMAIN PACKS (install a pack → tenant gets its roles) rather
than lit up ad-hoc at app install; a role naming lint (`<domain>.<role>`); a developer-facing "request a
role" surface (network.role.request record + admin approve) instead of the standards body POSTing directly;
role VERSIONING (schemas are versioned; roles are single-version today).

## Domain packs carry ROLES; install lights them up — Slice 2

A domain pack is the SECTOR unit (urban, health, justice…) and now pins both SCHEMAS (nouns) and ROLES
(actors). `AUTH.sign_pack` includes `roles`; `POST /v1/packs` validates each role is canonical + is
standards-body-gated (non-steward → 403). Installing a pack (`kernel /v1/schemas/install-pack`, now
tenant-authenticated) registers the pack's roles into THAT tenant's `governance.role` catalog (the
installed subset the Admin app assigns from), stamped `source_pack` + `domain`. Verified: `urban` pack
(water-engineer, sanitation-officer, disaster-officer) installed into kmc → all three appear in kmc's
catalog with domain=urban, source_pack=urban; Admin "By Role" lists them. Coarse-sector model: `urban`
holds all three; `platform` pack holds tenant_admin+steward (baseline every tenant). Slice-1 roles
re-tagged to coarse domains (urban/platform/civic).

Still deferred: role naming lint (`<domain>.<role>`); developer "request a role/pack" surface (a
network.role.request record + admin approve) vs the standards body POSTing directly; role/pack versioning
semantics; pack `extends` for sub-packs (urban-water) if a sector grows; app-install `_ensure_role` still
runs as a fallback (packs are now the primary path to populate the tenant catalog).

## Request-a-role flow (decided change-request) — Slice 3

A developer/tenant-admin can now REQUEST a canonical role instead of the standards body inventing it out
of band. `network.role.request`: POST /v1/role-requests (any signed-in participant files; recorded with
requested_by; 409 if already governed), GET /v1/role-requests, POST /v1/role-requests/decide (standards-
body-gated — approve SIGNS the role into the canonical catalog = the publish; reject records a reason; the
decision is stamped onto the request). Admin app gains a "Role Requests" tab (file + track status +
decide buttons that the server refuses unless you're the standards body). Verified: tenant admin files
health-inspector → pending → tenant-admin decide 403 → steward approve → role governed + request approved;
duplicate file → 409. NB: approval truly belongs on a NETWORK-ADMIN surface (the standards body isn't a
tenant admin); the tenant Admin app files+tracks, and the decide buttons work only for a standards-body
session — a dedicated network-admin app is the proper home for approvals (not yet built).

Still deferred: role naming lint; the same request→approve pattern for PACKS + schemas (schemas are still
direct-POST in this reference); role/pack versioning.

## Network-Admin app — the standards body's console

The AirawatNetwork standards console: review + DECIDE role change-requests (Change Requests tab) and
browse the canonical catalogs (Roles, Domain Packs tabs). `ds:airawat:app/network-admin`, scoped
`roles:[steward]`, NON-system — installed onto the network's OWN surface, invisible to tenants. Runs on a
SEPARATE app-host instance whose session is the standards body (steward), reflecting the OS/Network split
(ADR-0020): `app_host.py <apps> --port 8091 --session-user steward`. New `/bridge/catalog?kind=roles|packs`
proxies the network's signed catalogs. Verified: file `ward-officer` on the tenant surface (:8099,
kanpur-admin) → Network Admin (:8091, steward) sees it pending → approve → role published; tenant surface
never shows network-admin; network surface shows ONLY network-admin.

**Desktop visibility is now STRICT** (behavior change): a user sees an app iff it is unscoped OR they hold
one of its roles (identity ∪ granted) — the blanket "tenant admins see all" bypass is REMOVED, so a tenant
admin can't see a steward-only console and the steward can't see tenant apps. Caveat: the Admin app's "App
Access" management tab reads the same filtered /apps, so a NARROW tenant_admin (holding only tenant_admin,
no agency roles) won't see agency-scoped apps there to re-scope them; the demo admin holds all roles so it's
unaffected. Proper fix = a dedicated admin listing (all installed apps, unfiltered) for App Access — TODO.

Deferred: a second app-host for the network is launched manually (no compose service yet); same
request→approve pattern for PACKS + schemas from this console; the Marketplace showing an app's audience.

## Request→approve console extended to SCHEMAS + PACKS

The decided-change-request pattern now covers all three spec kinds, not just roles. New network endpoints
mirror the role flow: network.schema.request (POST /v1/schema-requests, GET, .../decide → sign_schema on
approve; 409 if already published) and network.pack.request (POST /v1/pack-requests, GET, .../decide →
validates member schemas published + roles governed, then sign_pack; 409 if already published). Both
decide endpoints are standards-body-gated. The Network-Admin console's "Change Requests" tab is now a
UNIFIED queue (kind = role|schema|pack) via /bridge/change-requests + /bridge/change-request-decide (routes
by kind). Filing via /bridge/change-request {kind, payload}. Verified: tenant admin files a schema +
a pack → console shows both pending → tenant-admin decide 403 → steward approves schema then pack →
both published (pack approve enforced member-schema-published + role-governed ordering).

NB: legacy direct POST /v1/schemas (ungated) + POST /v1/packs (gated) still exist for bootstrap/seeding;
the request→approve flow is the governed path. Pre-existing unrelated bug: GET /v1/schemas (list
projection) 500s on some records — resolve + membership checks work, so it doesn't affect certify/packs/
console (which use resolve, not the list). Deferred: dedup a request vs an in-flight duplicate; a Studio
(developer) surface for filing schema/pack requests (today filed via the tenant Admin bridge).

## Role naming lint — roles are now <domain>.<role> (governed-domain namespaced)

Roles migrated from bare slugs to the governed grammar `<domain>.<role>` (both kebab-case), matching the
schema grammar. New governed-DOMAIN vocabulary (POST/GET /v1/domains, standards-body gated;
_governed_domain_ids); seeded platform, urban, civic, health, governance, environment, mobility, finance,
justice. `_lint_role` enforces the grammar + a governed domain at role PUBLISH, request FILE, and request
APPROVE (verified: bare `firemarshal`, ungoverned `space.marshal`, non-kebab `urban.Water_Eng` all 422).
Canonical roles re-seeded prefixed (platform.tenant-admin, platform.steward, urban.water-engineer, …).
Migrated everywhere: identity USERS issue prefixed roles; the admin gate is now ADMIN_ROLES =
{platform.tenant-admin, platform.steward, admin} (app_host, secrets, network _require_admin/_require_publisher);
storefront/admin roles:[platform.tenant-admin], network-admin roles:[platform.steward]; urban+platform packs
re-published with prefixed roles; kmc catalog re-installed. Verified end-to-end: visibility, admin gates,
grants, and the cross-surface request→approve flow all work under the new ids.

Cleanup debt: the OLD bare roles remain in the durable network catalog + old bare governance.role records
remain in the kmc catalog (no role/record DELETE endpoint) — dead weight, nothing references them; the
catalog queries that matter filter to prefixed. Existing bare role_grants are likewise stale. A deprecate/
purge path is TODO.

---

## Registry read authorization is tenant-level only 🔴
**What's limited:** the kernel scopes reads by the caller's tenant — `/v1/registry/{resolve,query}` keep only
rows where `_steward_of(id) == claims.tenant` (id namespace `ds:<tenant>:…`), derived from the verified
token, not the body. Good tenant isolation (verified: a `kmc` token can't see `airawat` `ref.source`). BUT:
(1) granularity is **tenant-level only** — every authenticated user of a tenant sees ALL that tenant's rows
for the schemas their app may read; no general per-user/per-role/row-level read filter (inbox is a
per-schema exception). (2) an **unauthenticated** read (no token) is **not scoped** — the kernel returns
everything (`if claims:` guard); unreachable through the app-host (always sends a token) but the endpoint
should default-deny. (3) effective access = `tenant ∩ app.required_schemas` (the app allow-list is the 2nd
gate). `ref.*` is intentionally cross-tenant readable (public catalogue).
**Why it matters:** "you only see what you can access" holds at the tenant boundary, not within it — any
tenant user with an app that reads a schema sees every record in it. Not enough for sensitive per-record data.
**The fix:** default-deny unauthenticated reads; add row/role-level read predicates (e.g. actor/owner/role
scoping like the inbox) as a general capability, not per-schema special cases.

## Data App / bridge pagination caps at 5,000 rows 🟠
**What's limited:** the kernel HAS unbounded keyset pagination (`/v1/registry/query` → `page(rows,limit,
cursor)`, REG-QUERY). But the app-host `/bridge/query` (what the Data App + Components-log use) does NOT call
it — it calls `/v1/registry/resolve` with `fetch_limit=5000` and paginates **in memory** (sort id-desc, slice
by cursor). The UI paginates correctly (25/page, cursor, Load more) but only over the first 5,000 rows;
larger datasets are **silently truncated** (tail unreachable). Code comment admits it: "production pushes it
into SQL."
**Why it matters:** any dataset > 5k rows (readings, buildings, cells) looks complete but isn't.
**The fix:** have `/bridge/query` delegate to the kernel's native `/v1/registry/query` keyset endpoint,
passing `cursor`/`limit` straight through — store-side paging, no cap.

## Marketplace "certified" ≠ actually serveable (digest divergence) 🟠 — FIXED 2026-08-19
**What's limited:** the store listing's `certified` flag means only *"a valid certificate RECORD exists for
this id"* — `store_publish` checks `CERTIFICATES.get(cid).status == valid`, and the listing even carried
`cert_digest: None`. Serveability is a STRICTER, separate check: the app-host re-hashes the CURRENT bundle
at scan time and admits only if a cert's `evidence_digest` matches (ADR-0051 point-of-use). These diverge:
a **stale certificate** (bound to an older bundle, persisted in postgres across sessions/rebuilds) makes a
component show **"certified" in the Marketplace but refuse to install/serve** ("app not certified/serveable")
— observed on air-explorer (listing certified=True, current bundle `2a69…` had no matching cert → `/apps/
air-explorer` 404). Fixed that instance by certifying the current bundle.
**Why it matters:** users see Install on things that can't install; "certified" isn't trustworthy as shown.
**The fix (DONE):** (1) `store.publish` now binds the certificate's `evidence_digest` onto the listing
(was `null`). (2) `/bridge/market` reconciles each APP listing against the app-host's own digest-verified
admission (`CERTIFIED`) and **downgrades `certified`→false + adds `cert_note` + `serveable:false`** when the
listed cert doesn't match the current bundle — the host is the point-of-use authority (ADR-0051). (3) the
storefront disables Install ("Unavailable") and shows "⚠ cert stale" for non-serveable apps. So the
Marketplace can no longer offer Install on something the host will refuse. Verified: all 9 apps report
`serveable:true`; listing carries `evidence_digest`. STILL TODO (hardening): non-app components (drivers/
engines) can't be host-verified (no bundle at the app-host) — their `certified` is still cert-row-only until
the executor/filestore checks the digest at install; and re-publishing a changed artifact against a stale
cert is allowed (should require a fresh cert for the new digest).

## Knowledge ingest (URL/upload) — 2026-08-19
- **Embedding downgrades under load, mixing vector models in one store.** When the hosted provider hits a
  transient error/rate-limit during a burst, `embed-chunks` falls back to the *labeled* `bow-hash-256`
  (256-dim) instead of `bge-m3` (1024-dim). It is honest (the `model` field records which was used, never
  silent-synthetic), but it leaves some chunks with only a `bow-hash-256` vector — invisible to a `bge-m3`
  query, so semantic Search silently misses them. bge-m3 itself is healthy (verified direct). FIX: retry the
  provider on transient errors in `embed-chunks`, and/or a re-embed sweep that upgrades any non-primary-model
  chunk. Retrieval should also assert query-model == chunk-model.
- **Chunker does not size-split large pages.** A 137 KB extracted HTML page (Wikipedia) produced a SINGLE
  `knowledge.chunk` ("part 0"). That over-long chunk is truncated by the embedding model and gives weak
  retrieval + coarse citations. FIX: hard size cap (e.g. ~1–2k chars/tokens) with overlap in
  `engines/doc-chunk-version`, on top of the structure-aware (stage/section/paragraph) split.

## Rule extraction generalized (2026-08-19)
- rule-extract now domain-agnostic: extracts threshold|requirement|prohibition|permission with an inferred
  `<domain>.<subject>` applies_to, from ANY document (verified on URDPFI → real urban-planning norms). Cited +
  proposed + human-approved as before.
- BOUNDARY: only QUANTITATIVE rules (operator+value) are machine-evaluable by the deterministic rules engine,
  and only when a matching fact stream exists (e.g. air.quality/pm25). Qualitative requirements/prohibitions are
  recorded, cited, approvable, and human-readable, but not auto-evaluated — they need either a fact stream for
  their metric or a separate obligation/checklist evaluator. Extraction is also LLM-per-section (sampled, capped).

## Studio publish integrity + dev-testing gap (2026-08-20)
- **Publish verifies the MANIFEST + digest, not that the code runs.** This let an untested scaffold STUB be
  published (osm-roads). FIXED: `/bridge/project-publish` now refuses a component whose run.py still has the
  "TODO: implement" stub marker. But this is a marker check, NOT a real test gate.
- **No dev-sandbox: a component can only run after install (which needs certify+publish).** Run-tokens are
  minted at install; there is no path to run an uncertified draft. So "Test" on a scaffolded/edited component
  returns "not installed" — you can't truly Test before Publish. This is the coupling that made publish-without-
  test possible. PROPER FIX = ADR-0051 dev-sandbox: a dev-tenant run-token that runs uncertified own-drafts
  directly (then Publish can require a green Test). `/bridge/project-test` now surfaces this reason instead of a
  blank "error".
- **Process lesson**: never publish to demonstrate a pipeline with non-working code; if code isn't run+verified,
  say so explicitly and do not publish.

## INT-0004 dev-token (slice 1) — one-way isolation only, so far
- **What works:** a dev-token is minted only for an `environment: development` tenant, is broker-confined to that
  tenant (`_dev_confine`), and skips the steward-grant *within* it. Dev code can't read/write production; a prod
  tenant can't obtain a dev-token. Verified E2E.
- **Residual (honest gap):** the *reverse* edge is not yet enforced — a production run-token that holds a write
  grant could store an id in the `ds:airawatdeveloper:` namespace, because prod writes don't bind the object-id's
  tenant to the token's tenant (pre-existing; not introduced by slice 1). Prod tokens still cannot *read* dev data
  (reads/queries are tenant-filtered). Close in slice 4 by binding write-id↔token-tenant for ALL tokens.

## INT-0004 slices 4a+4 — Developer-only + publish hardening (residuals)
- **Enforced now**: dev-token requires an authenticated `developer`-kind participant minting for their OWN
  development tenant (anon→401, wrong-tenant→403); publish requires a green dev-Test; production tokens can't
  write into a development tenant (two-way isolation).
- **Single-session reference harness**: app_host holds ONE session (`SESSION_USER=anita`, a citizen). To operate
  Studio AS a developer the session must be the developer — the reference conflates citizen vs developer logins.
  The full auth'd chain was verified with the developer's token directly; the auth-gated Studio bridge UI needs a
  developer session. Real fix: per-user login, not a global SESSION_USER.
- **Ephemeral test-receipt**: the publish "green Test required" gate reads the scheduler's in-memory `_RUNS` ring —
  a restart loses green-run history. A durable, signed test-receipt keyed to the artifact digest is the hardening.
- **Reverse isolation scope**: covers the broker `/v1/write` path (components), not the direct admin
  `/v1/registry/objects` path.
- **Per-developer tenant provisioning is MANUAL**: the enforcement supports N private developers, but only
  `airawatdeveloper` is provisioned. Onboarding developer B = register participant `kind=developer` + provision a
  `development` tenant stewarded by them + add their identity. A one-call provisioning helper is not built yet.

## Runtime & Invocation (ADR-0062)

- 🟠 **One remaining bespoke run path — knowledge ingest.** `app_host._run_ingest_pipeline` still spawns its
  engines (`doc-chunk-version`, `embed-chunks`, `rule-extract`) as raw `python3 run.py` subprocesses and
  hardcodes `WRITE_TENANT="kmc"` — it predates the broker/host model and does NOT go through
  `platform.runtime_invoke`. Per ADR-0062 there must be exactly one way to run a component; the scheduler +
  city-baseline paths were converged (Slice 1), this one was not. **Fix:** make it a declared pipeline whose
  members route through the manager (like `pipelines/city-baseline`), and parameterise the tenant.
- 🔵 **Trigger sources not yet unified as declared bindings.** Schedule/manual go through the verb now, but
  the one event case (flood advisor) is still hand-wired and there is no governed `platform.trigger` record or
  outbox dispatcher. **Fix:** ADR-0062 Slice 2.
- 🔵 **Manager routing is a launch-env, not a service default.** The scheduler and app_host route through the
  runtime-manager only when `RUNTIME_MANAGER_URL` is set in their launch environment; restarted without it,
  they fall back to the local host path (no secret materialisation). **Fix:** bake the manager URL into the
  service definitions so the verb is the default, not opt-in.
- ✅ **[DONE] Event-triggered runs receive the event payload (`SUBJECT_REF`).** The dispatcher passes the
  triggering subject id; the scheduler threads it into the component env as `SUBJECT_REF`. Verified end-to-end
  (flood event → governed verb → componentized advisor read the alert). Reusable for any event-triggered run.
- ✅ **[DONE] INSTALL = GRANT is wired.** Install now auto-issues a populated steward write-grant: certify
  records the certified `declares` (reads/writes/scopes) in the signed cert; publish auto-fills the listing
  scopes from the cert (can't be forgotten or inflated); the kernel install already calls `/v1/grants/issue`.
  Verified: flood-advisor installed into kmc → grant for its 4 writes + 2 reads → event-triggered run wrote an
  attributed case + task + recommendations. `flood-advise` migrated onto the governed verb and
  `SUBSCRIPTION_ENFORCE` flipped **strict** (both subs governed, zero refused). Remaining niceties: install a
  component into a tenant it wasn't yet in still requires an explicit `tenant` (cross-tenant install), and
  dev-tenant drafts still bypass grants by design (ADR-0051).

## Data conformance (ADR-0063 §2b)

- 🟠 **Write-time schema validation is SHADOW, not strict yet.** The registry now validates every written object
  against its governed JSON-Schema at the `Registry.put` chokepoint (both broker + raw paths, both backends);
  `SCHEMA_VALIDATE=shadow` logs non-conformance but still stores. To flip **strict** (`SCHEMA_VALIDATE=strict`,
  refuse non-conforming writes) two things are needed: (a) **tighten loose schemas** — many governed schemas
  have `additionalProperties: true` and thin `required`, so stray/misnamed fields (e.g. the `subject_ref` inbox
  bug) pass; only missing *required* fields + type/enum errors are caught today. Tighten via the governed
  change-request flow. (b) **Fix the real violations shadow surfaces first** — e.g. the outbox writes
  `platform.event` with `tenant: None` (schema wants a string). Turn strict on per-schema as each is cleaned.

## Nashik baseline remediation (2026-08-23)

- ✅ **[FIXED] Filestore had no persistent volume — uploads lost on any container recreate.** 🔵🔴
  `FILESTORE_DIR` defaulted to `/tmp/airawat-filestore` inside the ephemeral container FS. Recreating
  containers during the runtime-manager deploy WIPED every uploaded blob (incl. the 209 MB Nashik OSM
  PBF), while the Postgres `platform.component_asset` records survived pointing at now-dead `file_id`s →
  `/v1/file/get` 404 → `osm-roads`/`osm-facilities` crashed with `HTTP 404`. **Fix:** added a named
  volume `filestore_data:/data/filestore` + explicit `FILESTORE_DIR` in `deploy/ec2/docker-compose.yml`,
  then re-fetched the PBF (content-addressed → same id → existing asset records resolve). Uploads now
  survive recreates. *Follow-up:* a periodic reconciler could detect asset records whose blob is missing.

- 🔴 **GEE service-account private key passed as `docker run -e` → leaked into logs.** Materialised
  secrets were appended as `-e KEY=VALUE` to the `docker run` argv, so the full GEE private key appeared
  verbatim in the runtime-manager logs (and in the `subprocess.TimeoutExpired` exception, `docker
  inspect`, `ps`). **Partial fix:** `components/_common/launcher.py` now writes all env (config + secrets)
  to a private 0600 `--env-file` and passes only the path in argv; timeouts return a clean message with no
  argv. **Still owed:** the exposed key should be **rotated** (it was already printed to historical logs),
  and secret materialisation could move to a mounted tmpfs file the driver reads, so a value never lands
  in an env table at all.

- 🟠 **Steward grants are built from the CERTIFIED listing's declared scopes — a stale/under-declared
  manifest silently 403s at run time.** `coverage-qa` read 12 nouns but declared 6; `cell-indexer`'s
  cert predated its `cell.heat` scope → both got `403 (write/read) not authorized by the tenant steward`.
  **Fix:** widened `coverage-qa`'s `reads`/`scopes` to every noun it reads (kept in lock-step with
  `LAYERS` in run.py), re-certified + re-installed. *Systemic gap:* nothing checks that a component's
  declared scopes actually cover what its code reads/writes — a conformance test (grep the run.py broker
  calls vs declared scopes) would catch this at certify instead of at run.

- 🟡 **`buildings-footprints` fetches Open Buildings ONE H3 cell at a time via GEE `getInfo` (~5 s/cell)**
  — 250 cells ≈ the old 1200 s docker-run cap, so it timed out. **Fix:** raised `LAUNCH_TIMEOUT`→1700
  (+ scheduler invoke→1900, app-host /run→2200 to keep the chain ordered). It's bounded + resumable, so
  this finishes a central patch; **the real fix is a single bbox export grouped to H3** instead of
  per-cell round-trips (won't scale to a full metro otherwise).

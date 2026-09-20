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

- ✅ **[FIXED] Registry query applied LIMIT before tenant-scoping → big multi-tenant layers returned 0
  for smaller tenants.** 🟠 `registry_resolve` fetched a `limit`-capped window ordered by id, THEN
  filtered to the caller's tenant. `geo.osm_feature` totals 81k rows (bmc 67k sorts before nashik's
  14.5k), so a 50k window was entirely bmc → nashik's road lines came back empty in City Scan (density
  cells worked because cell.roads is only ~8k total, under the window). **Fix:** push tenant scoping
  INTO the query (`id_prefix` → `id LIKE 'ds:<tenant>:%'`) in both registry backends so the LIMIT is
  per-tenant; `registry_resolve` passes the authenticated tenant's prefix. Verified: nashik
  geo.osm_feature 0 → 14502. *Systemic:* this affected ANY layer whose cross-tenant total exceeded the
  fetch window — the fix is general, not roads-specific.

- **Registry query = full seq-scan by schema (missing index) + a dead x-index feature (2026-08-25).**
  Every `resolve_as_of` filter emits `object #>> '{schema}' = <code>`, but `registry_version` had **no
  index** on that expression (the GIN `jsonb_path_ops` only answers `@>` containment) — so a per-schema
  read was a seq-scan of ALL versions of ALL schemas. Harmless at 20k rows; at **2.03M rows** (bitemporal
  history + repeated engine re-runs) it timed out / dropped connections and made City Scan's flood layer
  crawl. **Fix:** base index `rv_schema ON registry_version((object #>> '{schema}'))` in `pg_store.py`
  `_DDL` (full-layer read 518→209ms). **Also found:** `provision_schema` created per-schema `x-indexes`
  with a `WHERE object->>'schema'=…` predicate (`->>`) that can NEVER match the resolver's `#>>` query —
  so *every* x-index ever provisioned (incl. air.*/demographics) was unusable dead weight. Fixed the
  predicate to `#>>`; recreated the hot `h3_id` partials → cell-drill 518ms→**1.9ms**. Both live on the
  local DB; **EC2 kernel still needs an image rebuild** (`build-push.sh` + redeploy) to ship the `_DDL` +
  provisioner fixes. Durable via `_DDL` (auto-runs on every kernel start) + schemas declaring `x-indexes`.

- **`registry_version` bloat: 2.03M rows (2026-08-25).** The store keeps every version (correct,
  bitemporal). But repeated non-idempotent engine runs balloon it — the flood-risk engine has no RESUME
  and rewrites all cells each run (I ran it 3×), and the buildings work added 130k+130k. No compaction /
  retention job exists. A vacuum/history-retention policy (or at least tombstone pruning for superseded
  non-decision facts) is worth adding before this grows unbounded on a busy tenant.

- **Brokered egress `/v1/fetch` silently dropped the request METHOD + BODY (2026-08-25).** A confined
  component calls `/v1/fetch {url, method:"POST", body:<payload>}`, but the kernel broker (`broker_fetch`,
  `kernel/api/app.py`) rebuilt the payload to the secrets service with only `url/inject/user_agent/auth`
  — **`method` and `body` were dropped** — and the secrets `/fetch` did a bare `Request(url, headers=…)`
  (no `data`). Result: every POST degraded to an **empty GET**, so Overpass received an empty query and
  answered *"Your input contains only whitespace."* This silently broke ALL POST-body egress (osm-roads /
  osm-facilities only worked because their data was extracted on EC2 and migrated in; local Overpass
  extraction never worked). **Fix:** broker now forwards `method` + `body`; secrets builds
  `Request(url, data=…, method=…)` with a sane Content-Type. Also the timeouts were too short for metro
  Overpass tiles (broker→secrets **12s**, secrets→Overpass **15s**) and the broker only caught `HTTPError`,
  so a slow tile threw an uncaught `TimeoutError` → **500**. Bumped to 135s / 120s and the broker now
  returns a graceful **504** on timeout/unreachable. Verified: osm-drainage extracted 755 waterways +
  1,188 `cell.drainage` cells for bmc over live Overpass. **EC2 kernel needs an image rebuild to ship this**
  (secrets is a host process there too — restart after pull).

- **`risk.flood` supersede closes tx-time but leaves valid-time open (2026-08-25).** After the T2 run,
  `WHERE valid_to IS NULL` returned **13,594** rows for **6,797** cells: each re-run of the engine
  (`valid_time {from: now}`, no `to`) inserts a new open valid-interval and closes the prior row's
  **transaction** time (`tx_to`) but NOT its **valid** time (`valid_to`), so multiple valid-open versions
  coexist. **Reads are correct** — `resolve_as_of` filters `tx_to IS NULL` + `DISTINCT ON (id) ORDER BY
  tx_from DESC`, so the chat/map/verification all see the right 6,797 current cells (I re-verified against
  `tx_to IS NULL`). But (a) the valid-time history is malformed (overlapping open valid intervals — a real
  bitemporal-correctness bug if anyone ever queries `as_of` a past valid time), and (b) it compounds the
  `registry_version` bloat above. Fix: on supersede, close the prior row's `valid_to` (not just `tx_to`),
  or make the engine idempotent/RESUME-aware.

- **Registry authorization was inconsistent / fail-open — P0 hardening (2026-08-26).** A design review
  (3 audits, docs/reviews/registry-design-review-2026-08.md) found the fail-open read leak was NOT
  isolated to `_asof_rows`: `/v1/registry/resolve` (confirmed live — leaked kmc+airawat), `…/history`,
  `…/prov`, `/v1/resolve-ref`, `/resolve-by-identifier` all returned cross-tenant data unauthenticated;
  and worse, the raw write surface (`/v1/registry/objects`, `/retract`) had NO tenant binding and the
  broker `/v1/read`+`/v1/write` confined by SCOPE but not by the id's TENANT — so a bmc run could
  read/overwrite ds:kmc: rows. **P0 fix shipped + verified:** one zero-trust gate — reads decide reach
  before any row (fail-closed unauth, id_prefix pushed into SQL), writes are OWN-TENANT-ONLY for everyone
  (a tenant_admin role grants NO cross-tenant reach; shared national schemas are read-only to tenants).
  All 8 findings (C1–C4,H1,H2,M1,M2) tested. **Still open: P1 bitemporal (non-atomic supersede →
  double-open rows + transient empty reads; `valid_time={from:now}` per engine re-run → valid-time gap /
  empty historical reads; in-memory dedup resurrects tombstones; non-uniform ISO timestamps break
  lexicographic ordering) and P2 perf (resolve-all-then-filter-in-Python; fake keyset pagination; missing
  composite bitemporal index; no retention/compaction).**

- **Registry bitemporal correctness — P1 hardening (2026-08-26).** Fixed the four bitemporal defects from
  the design review (docs/reviews/registry-design-review-2026-08.md): **B1** non-atomic supersede
  (autocommit + no lock → double-open tx rows + transient empty reads) → `put`/`retract` now single-txn +
  per-id advisory lock + `UNIQUE(id) WHERE tx_to IS NULL` backstop + idempotent startup repair (closed 339
  pre-existing multi-open ids). **B2** `valid_time={from:now}` per engine re-run left an unqueryable
  valid-time gap → the new version now INHERITS the prior live assertion's `valid_from` (correction
  semantics). **B3** in-memory reference dedup resurrected tombstones → now skips retracted. **B4**
  non-uniform ISO timestamps broke lexicographic ordering across a second boundary → `resolve_as_of`
  compares `NULLIF(col,'')::timestamptz`; `_now()` emits fixed-width microseconds. Verified on a 6,797-cell
  flood re-run: 0 double-open rows, valid_from inherited, historical `valid_as_of` resolves the gap window.
  NOTE: B2 uses CORRECTION semantics (a re-write corrects the current fact over the same valid period);
  true valid-time VERSIONING (each write = a new period, closing the prior) would be a distinct explicit
  op — none of today's engines need it. **Still open: P2 perf** (resolve-all-then-filter-in-Python; fake
  keyset pagination; missing composite `(schema,id,tx_from)` index; no retention/compaction).

- **Studio end-to-end walkthrough surfaced + fixed 9 platform bugs (2026-08-27).** Building one simple
  solution (reuse a driver + build an app → compose → install into a city) in Studio exposed nine real
  bugs; the BUILD side (Studio) was solid, the rough edges were all on install/marketplace/solution-runtime:
  (1) Compose published the solution to the store but never registered it in /v1/solutions → invisible in
  the Solutions tab + not fan-out-installable → FIXED (compose now POSTs /v1/solutions). (2) Studio Publish
  didn't call reload_apps() → a freshly published app showed "cert stale" until a host restart → FIXED
  (publish reloads apps for kind=app). (3) "My Requests" filtered by the browser user's sub, but spec
  requests are filed via the dev PARTICIPANT (spec_contributor), so a developer never saw their own → FIXED
  (on_behalf_of stamped by app_host + stored by network + matched in my-requests). (4) Request-schema
  template shipped an `id` without the R2 resolvable-id pattern → tripped Advise on first try → FIXED
  (template now includes the pattern). (5) New-component id defaulted to the SANDBOX tenant (ds:airawatdeveloper:)
  not the publishable vendor ns (ds:airawat:), and re-scaffolding a name under a new id kept a STALE
  meta component_id → Publish "source not found" → FIXED (default ds:airawat: + scaffold forces meta
  component_id to the requested id, still non-destructive of code). (6) Editor Test/Publish shown on REUSED
  components (you don't test/publish what you reuse) → FIXED (reused → Configure only). (7) air-sensors driver
  HARDCODED ds:kmc: (AOI default + write id) → P0 correctly 403'd its cross-tenant write from a non-kmc
  tenant → FIXED (tenant from /v1/context, discover AOI per-tenant, write ds:{T}:). (8) Storefront install
  spinner never cleared for a solution because /v1/solutions/install returns `members` as an INT count and the
  JS did `(r.members||[]).filter` → TypeError → FIXED (handle int|array + try/catch). (9) Solution fan-out
  issued grants but never SHELVED app members → an installed solution's app never appeared on the desktop →
  FIXED (fan-out shelves app members). Verified: solution install returns shelved_apps + app on desktop.
  Shipped local + EC2 (reference+network images; kernel unchanged).

## Air Intelligence walkthrough (W2, 2026-08-27) — built end-to-end, 20 findings

Built the iDSS **Air Intelligence** solution in Studio (govern `air.hotspot` → build `air-hotspot`
engine → reuse 5 components → compose → certify → install into Kanpur `kmc` production → run on real live
iDSS data → 12 hotspots + sensor readings in City Scan). 20 findings; **FIXED** shipped locally, **OPEN**
are follow-ups.

FIXED this session:
- **Dev-sandbox egress was totally broken** (biggest): the kernel dev-token honoured `body["egress"]` but
  the scheduler sent none → every dev run got `egress:[]` → broker 403'd ALL external calls → no egress
  driver (OpenAQ/iDSS/Overpass/Open-Meteo) could be Tested pre-publish. Fixed: scheduler reads the
  component's declared egress (+auth profile) from meta.yaml and passes it. Confined to the dev tenant,
  own-secrets, host-allowlisted, rate-limited, audited — narrower than the wildcard capability dev already had.
- **De-Kanpur sweep missed 3 more components**: `kanpur-idss`, `station-interpolation` (both hardcoded
  `ds:kmc:` AOI + WRITE_TENANT + fixed res) and the scaffold template (tenant-pinned write scope). All now
  derive tenant from `/v1/context` + write `ds:{T}:` + cell at the AOI's res. Audit ALL drivers, not the
  one that surfaces.
- **Interpolation trusted raw + stale LCS points**: added QC (drop pm25 ≤0 / ≥985 device faults) so a
  faulty 999 sensor can't seed a false hotspot; dedup to latest-reading-per-station (was counting every
  historical reading as a separate station, diluting the surface).
- **Studio Test showed bare "✗ error"**: frontend ignored `r.detail` (where the scheduler puts the reason).
- **New-component id namespace mismatch**: Build-card member (`ds:airawatdeveloper:`) vs scaffold id
  (`ds:airawat:`) → "no source found". Repointed; the two id-minting paths must agree.
- **City Scan**: no viz.layer descriptor for air schemas (added air-quality + air-hotspot); choropleth too
  opaque + no show/hide + flat 3D (opacity slider moved to a top pill, click-active-to-hide, taller towers);
  layer panel regrouped by domain (Air Quality group = Air Sensors readings + PM2.5 + Hotspots), descriptions
  only on select, sensor points with PM2.5 hover values.

OPEN (follow-ups, prereq- or infra-gated):
- **Studio/Solution Expert should PROMPT for the viz.layer descriptor** when a component writes a map-able
  (space-block) schema — rendering is part of the deliverable, not a later manual step. See
  memory `viz-layer-is-part-of-deliverable`.
- **Solution Expert reuse-miss**: reused drivers but proposed to BUILD engines/skills/apps that already
  exist; also truncated mid-decomposition (needed "continue"); "fix-and-propose" doesn't auto-fix the
  mechanical R-rules (R6 event occurrence-time). Index engines/skills/apps for reuse, not just drivers.
- **Marketplace/solution install** issues grant+run-token+cert but the new component isn't listed in
  `/v1/components` (invisible in the Components UI; fan-out "N installed" count unreliable).
- **EO re-baseline gated**: buildings/built-up/green/population are Earth-Engine (L2) drivers; a plain
  scheduler run lacks TENANT (must go via runtime-manager). GEE key now set, runtime-manager+image present,
  but the local `earth-observation` runtime source has DRIFTED from its certified digest → manager refuses
  to host → must **re-certify the runtime**. Roads/facilities/flood still need the OSM PBF. A full res-9
  re-baseline of a production city is deliberate batch work.
- **Coverage & trust report** empty for a fresh tenant (coverage-qa not run) + its assessed-layer list is
  hardcoded (doesn't rate air.quality). Should assess ANY installed map layer.
- **Production AOI as a first-class setup choice**: kmc shipped a tiny res-8 core AOI; enlarged to a proper
  Kanpur res-9 extent (1→12 hotspots) but other layers still lag at res-8/old extent + 72 stale res-8
  air.quality cells linger (retract to clean). AOI res+extent must be a deliberate per-city decision.

## Air Intelligence — Action loop + platform hardening (W2 part 2, 2026-08-27)

Continued the Air Intelligence session into the ACTION half + physical re-baseline + marketplace
governance. 8 more findings (W2-21..28); FIXED shipped locally, OPEN are scoped follow-ups.

FIXED:
- **EO runtime re-certified** (W2-21): earth-observation runtime source had drifted from its certified
  digest → runtime-manager refused to host. Pulled the certified image, stamped the local image's actual
  `.Id` into meta (Docker config `.Id` is env-unstable — should pin the registry RepoDigest), re-signed via
  /v1/certify. Runtime now hosts EO drivers (GEE key + tenant materialised in the L2 container).
- **Config-as-first-class at publish** (W2-27): a component's `config:[…]` now flows meta → certified
  `declares` → store listing (store.py + conformance.py + api.py, hot-patched into the dockerised network;
  durable Postgres state intact). Verified `config:['DECIDER']` on decision-router@0.2.0. (Last mile below.)
- **Governed the pollution-control-officer role** + made it tenant-grantable (declared on air-explorer,
  registered in kmc). **Advisory chain-of-thought blob** (W2-22) → clean 3-sentence advisory (tag-delimited
  + reasoning-stripped). **Inbox** (earlier) paginated + kind/status/relative-time. **Air Explorer** rebuilt.

OPEN (scoped follow-ups):
- **EO ingest still blocked** (W2-21): the EO driver IN-CONTAINER can't see kmc's space.aoi (container↔kernel
  registry-visibility / run-token scope — likely the host-process vs docker-kernel split). Roads/facilities/
  flood need the OSM PBF (uploaded) + geospatial runtime re-cert (same as EO).
- **Config last mile** (W2-27): setup panel must render listing.config; a per-holder config SET path; run-time
  env INJECTION. ADR-0027's config was declaration-only.
- **Studio mis-proposes a ROLE as a SCHEMA** (W2-23): the propose flow only knows network.schema; must branch
  by artifact kind (schema|role|interface|pack) and file a role via /v1/role-requests.
- **Role not tenant-grantable without an app declaring it** (W2-25): Studio should bind the wizard's "who
  uses it" → governed role → onto the serving app's meta, so install surfaces it automatically.
- **Marketplace governance** (W2-24 + W2-28): store overwrites by component_id (no version history, no
  "update available", no upgrade action); publishing should MANDATE a version bump; the Network Steward needs
  a marketplace console (catalog counts, per-provider stats, publish-activity audit, governed revoke/delist).
- **Router correctness**: decision-router doesn't re-address a task when the DECIDER changes (idempotency
  keyed only on the recommendation) → the air task stayed on the old decider; and stale air.quality (a res-8
  Aug-19 cell set) lingers next to the res-9 grid, keying the advisory's recommendation to an old obs.
- **Install not listed in /v1/components** (W2-15) makes a newly-installed component invisible/unconfigurable
  in the Components app — compounds the config + run-it-yourself gaps.

## Marketplace governance — BUILT (2026-08-27, follow-on to W2-24/28)
Implemented the marketplace/version governance layer (hot-patched into the dockerised network + host app-host;
durable state intact):
- **Version discipline**: /v1/store/publish rejects re-publishing an existing (id, version) → 409; requires a
  higher semver. A signed listing is immutable. (network/store.py version_error + api.py gate.)
- **Version history + audit**: every listing carries history[] + published_by (from the publisher token).
- **Lifecycle** active→deprecated→revoked, role-gated + audited: POST /v1/store/deprecate (publisher; sunset_at
  + superseded_by; kept resolvable, hidden from NEW installs) and POST /v1/store/revoke (network steward only;
  pulled from discovery, record kept). browse() hides revoked; include_all for the console.
- **Steward roll-up**: GET /v1/store/stats (total, by_kind, by_provider, by_status, recent publishes).
- **Authz PROVEN with negative tests**: publish/deprecate/retire ⇒ the component's steward (_require_publisher);
  revoke ⇒ the network steward (_require_admin airawat); developer denied 403 on both; no-token 401.
- **Steward console UI**: network-admin → 🛒 Marketplace tab — catalog + counts (kind chips, top providers),
  lifecycle summary, per-component version/status/publisher + Deprecate/Revoke buttons (app-host bridges
  /bridge/store-revoke|deprecate forward the steward's token; the NETWORK enforces the gate).
STILL OPEN (deliberate follow-ons, not built): enforce schema backward-compat at approval (diff-gate); pin
solution member versions (real lockfile) for coexistence + "update available"; per-tenant installed-version
tracking so a tenant sees & pulls upgrades.

## FIXED (2026-08-27): solution installs — member apps invisible on the desktop
Symptom: installing the "Air Intelligence" solution in kmc reported success, but its apps (Air Explorer)
never appeared on the admin's desktop.
Root cause (app_host.py `_app_required_roles`): an app is shelved with an EXPLICIT audience-roles list
where `[]` MEANS "open to everyone in the tenant". The code did `(entry.roles) or app.declared_roles`, so
an empty `[]` (falsy) fell back to the app's DECLARED audience role (`air-explorer` →
`urban.pollution-control-officer`) — re-locking an app the tenant had shelved as open. The admin (who lacks
that operational role) was then filtered out by `_may_access_app`, so the freshly-installed app was hidden.
Fix 1 (correctness): honour an explicit shelf entry — `[]` = open to all; only fall back to the declared
audience when the app is NOT on the shelf.
Fix 2 (robustness): a TENANT ADMIN always sees/opens apps installed in their OWN tenant, so a fresh install
that scopes an app to an operational role never hides it from the admin who installed it. Scoped to
own-tenant; developer_only stays gated; regular users remain strictly role-gated; data access still
governed by grants. Verified: kanpur-admin `/apps` now lists air-explorer + inbox (10 apps).

## FIXED (2026-08-27): scheduler stopped firing after P0 zero-trust (idss never pulled)
Symptom: "is the idss driver pulling at intervals?" → No. The scheduler's live /schedules was empty; the
last successful fire of ANY schedule was 2026-08-26. kanpur-idss had never run (last_run=None, 0
air.sensor_reading rows in kmc).
Root cause: `scheduler.py:_find`/`_put` sent NO auth token. After the P0 zero-trust registry gate, an
UNauthenticated read fails CLOSED → returns empty → the scheduler loaded 0 schedules and fired nothing.
(Same tokenless-read footgun as the app-host shelf; second service.)
Fix — the scheduler is now a PLATFORM SERVICE (as agreed):
 - New least-privilege identity principal `airawat-scheduler` (role `platform.scheduler`, tenant airawat).
 - Kernel: a SCOPED platform-service reach — a caller with a platform-service role may READ and STAMP a
   tight control-plane allow-list (`PLATFORM_CONTROL_SCHEMAS = platform.schedule`) across ALL tenants.
   `_read_reach` returns a distinct `PLATFORM` mode (so the SCOPED own-tenant post-filter doesn't re-drop
   the rows); `_assert_write_own_tenant(oid, auth, schema)` allows cross-tenant writes only for that
   allow-list. NOT a blanket admin bypass — tenant DATA and every other schema stay strictly own-tenant.
 - scheduler.py signs in as `airawat-scheduler`, caches the token, and sends it on `_find`/`_put`.
Verified: scheduler loads all 3 schedules with next_run; a manual kanpur-idss run ingested 82 REAL
air.sensor_reading points from live Kanpur iDSS into kmc (228 rows now); control-plane cross-tenant write
→ 200, data cross-tenant write → 403 refused; platform-service read of air.sensor_reading → 0 (confined).
DURABILITY: kernel is hot-patched (docker cp) — survives restart, NOT a force-recreate/rebuild; source
files (kernel/api/app.py, scheduler.py, identity.py) are edited so a rebuild-from-source carries it. Must
ride the next EC2 deploy.

## kmc cadence audit (2026-08-27) — air pipeline made a live loop
Finding: raw sensors refreshed hourly but the DERIVED air engines were UNscheduled, so air.quality &
air.hotspot were frozen ~6h stale while air-quality-advisory pointlessly re-ran every 15 min on stale data.
Applied (kanpur-admin owns kmc's platform.schedule records; own-tenant writes):
 - terrain (geo.terrain, static DEM, superseded by terrain-dem): schedule DISABLED (enabled=false).
 - Air chain now staggered hourly so each step runs on fresh upstream:
     :00 kanpur-idss → air.sensor_reading   (kept)
     :10 station-interpolation → air.quality (NEW schedule)
     :20 hotspot-detection → air.hotspot     (NEW schedule)
     :30 air-quality-advisory → recommendation (retimed from */15 → hourly)
 - Left correctly UNscheduled: landcover/heat/cell-indexer/coverage-qa/doc-acquire (static/derived/on-demand);
   decision-router/flood-advisor/governance-rules (event-driven, not clock-driven); air-sensors (would
   synthesize without real CPCB/OpenAQ keys — keep off per no-synthetic pref).
Verified: manual chain run green (interp 8789 cells/89 stations; hotspot 6 clusters; advisory Moderate);
air.quality & air.hotspot freshened 01:47Z → 07:32Z.
LIMIT: pure-cron can't express "run after upstream COMPLETES" — staggering is a workaround. Proper fix =
event-driven triggers (ADR-0062: engine subscribes to upstream platform.event writes). Follow-on.

## kmc baseline rerun at res-9 + res-8 cleanup (2026-08-27) — DONE, surfaced 3 latent bugs
Goal: regenerate kmc City Baseline cell.* layers at H3 res-9, remove stale res-8. AOI was already
h3_res=9; res-8 cells were leftover from an earlier run. Regenerated:
 - cell.builtup + cell.greencover ← landcover-dw (Dynamic World/GEE, earth-observation runtime): 6500 res-9 each.
 - cell.heat ← cell-indexer IDW over environment.lst_observation: 8789 res-9.
 - Retracted 113 old res-8 rows (61 builtup + 16 greencover + 36 heat). Final: res-8=0 across all three.
Generate-first, delete-after (never removed old baseline before res-9 replacement existed).

Three latent bugs fixed to get there (all durable code edits — must ride next EC2 deploy):
 1. IDENTITY EPHEMERAL KEY: identity (platform-spec/reference/identity.py) has no VAULT_ADDR → falls back
    to an in-process Ed25519 key that ROTATES on every restart. Restarting identity (done earlier for the
    scheduler principal) invalidated the JWKS cached by the NETWORK at startup → all admin tokens got
    "bad signature", blocking grant issuance. Fix now = restart the network (re-fetches JWKS; durable
    stores reload from PG). PROPER fix (TODO) = wire identity to Vault transit so the key is stable, OR
    make JWKS consumers re-fetch on verify-failure. Any startup-JWKS-cacher (llm-proxy) is also at risk.
 2. INSTALL GRANT not landing: install-as-grant depended on #1; landcover-dw installed but its space.aoi
    read grant failed silently → broker 403. Re-issued via network /v1/grants/issue after #1 fixed.
 3. SCHEDULER couldn't run config-driven HOST components: host.py starts components in a CLEAN env and
    injects ONLY --set KEY=VALUE vars, but scheduler.py `_invoke` host-path passed run config via the
    subprocess env (which host.py discards). So cell-indexer never received TENANT/INPUT_SCHEMA/OUTPUT_SCHEMA
    and refused to run (only the baseline PIPELINE, which uses --set, could run it). Fix: scheduler `_invoke`
    now forwards env as --set args. (Runtime-container components were unaffected — the runtime manager
    forwards env itself.)
Also: landcover-dw now INSTALLED for kmc (modern baseline path); population-ghsl still uninstalled →
cell.population is 0 (separate follow-on if a population layer is wanted at res-9).

## City Scan temporal animation made GENERIC (2026-08-27)
Was: the time scrubber only animated ONE data shape — cells carrying an embedded `series` array — and read a
HARDCODED `precip_mm` field (built for cell.weather_forecast). Any other temporal layer (e.g. air.quality,
which is per-cell DATED SNAPSHOTS: separate records per observed_at) could not animate.
Now (components/apps/city-scan/dist/index.html `parseCells`): temporal is detected GENERICALLY from the data,
driven by the layer's declared value_field — no per-layer code:
  (A) embedded per-cell series (forecast), OR
  (B) DATED SNAPSHOTS — group records by observed_at into frames.
Any layer whose data has >1 observed_at frame gets a scrubber automatically. Also de-hardcoded the legend
units (L.fmt) and scrubber subtitle ("N/M frames").
Authored viz.layer descriptors (the per-layer DECLARATION every map layer needs — data, not code):
air-quality-pm25 (source air.quality, value_field pm25, ramp aqi) + air-hotspots (air.hotspot, value `value`,
ramp reds). Verified the grouping on REAL data: air.quality → 3 frames (72/8861/8789 cells), thi=94.8 µg/m³.
LIMITS:
 - Client loads ALL rows per layer (q limit 50000) then groups → bounded by MAX_FRAMES=48 client-side. As
   hourly frames accumulate (8789 cells/frame), this caps ~5 full-res frames before the 50000 fetch truncates.
   DURABLE fix = server-side per-frame load (query by observed_at as you scrub) — deferred.
 - This is a hot-edit to the kmc city-scan app (app-host serves off disk, --no-verify-cert). The generic
   engine should land in the Studio app TEMPLATE so every generated City Scan gets it; and viz.layer
   descriptors should be emitted by Studio when a component writes a space-block schema (see
   viz-layer-is-part-of-deliverable). Must ride next EC2 deploy.

## Air-chain scheduling + marketplace + run-timeout fixes (2026-08-27)
1. SCHEDULER DRIFT (root cause of "no new Air Quality data"): the tick loop ran each component SYNCHRONOUSLY
   inline, so a slow run (station-interpolation ~35s over 8789 cells; the LLM-backed advisory) blocked the
   minute clock and every exact-minute cron in the blocked window was skipped. Proof: advisory (*/15, 4
   chances/hr) fired 10× while station-interpolation (:10, 1 chance/hr) fired 0× — so air.quality never
   refreshed. Fix (scheduler.py): the tick now DISPATCHES each due run in a daemon thread (`_fire`); the
   minute clock never blocks; the _INFLIGHT guard still prevents overlap. (ADR-0062: scheduler = trigger
   source, not executor.) Manual /run stays synchronous by design.
2. MARKETPLACE audience scoping (network-admin showed in kmc's storefront): listings had only
   visibility=public and the /bridge/market handler applied NO tenant filter. Added `audience_tenants` to a
   listing (network/store.py set_audience + POST /v1/store/audience, steward-gated) and a filter in
   app_host /bridge/market (hide a listing whose audience_tenants is set and excludes the caller's tenant).
   Scoped ds:airawat:app/network-admin → ["airawat"]. Verified: hidden for kmc (52), shown for airawat (53).
3. "RUN NOW" TIMEOUT (Components manual run): _bridge_run used the generic self._http (timeout=10s) but a
   normal engine run takes ~35s → UI timed out while the run kept going server-side. Gave _bridge_run its own
   urlopen(timeout=2000) matching the scheduler's run cap. Verified: bridge run completes (27s, status ok).
All durable-state intact; hot-patched (network docker + host scheduler/app_host). Must ride next EC2 deploy.
OPEN: user reports the Kanpur AOI was "expanded" but space.aoi still holds the OLD bbox
[80.15,26.35,80.48,26.6] (version 2) — the expansion never reached the authoritative record. Re-running all
layers for a new AOI is blocked until the new bounds are set. Also: cell.population still 0 (population-ghsl
not installed for kmc).

## Expanded-AOI (v1→v2) re-ingest for kmc, all res-9 (2026-08-27)
The kmc AOI was expanded v1 [80.3,26.44,80.38,26.5] (tiny core) → v2 [80.15,26.35,80.48,26.6] (full city).
Layers from before the expansion covered only the v1 core. Re-ran every physical layer against v2 (AOI
h3_res=9 ⇒ every cell layer is res-9 automatically). Result — all full-extent, res-9, res8=0:
  air.quality, cell.builtup, cell.greencover, cell.heat, demographics.population (GHSL), geo.terrain
  (Copernicus DEM via terrain-dem), cell.weather_forecast (Open-Meteo 48h), cell.buildings (Open Buildings
  v3, 8789 cells), geo.facility (519 OSM POIs, full extent). Retired stale res-8/v1 rows (geo.terrain 72,
  legacy geo.landcover 92). Installed+granted the drivers that weren't (population-ghsl, terrain-dem,
  weather-forecast, buildings-openbuildings, osm-facilities, osm-roads); GEE runs via runtime-manager,
  host runs via scheduler /run.
Fixes required to get here (durable code, must ride EC2 deploy):
 - ASSET-INJECTION P0 (3rd instance of the tokenless-read footgun): scheduler `_component_assets` read
   platform.component_asset with NO token → post-P0 empty → OSM_PBF_FILE_ID never injected → osm drivers
   failed "not set". Fixed: authenticate that read (service token) + add platform.component_asset to the
   kernel PLATFORM_CONTROL_SCHEMAS (platform-service reach).
 - HOST-RUN TIMEOUT: scheduler `_invoke` host-subprocess cap was 180s; osmium-over-PBF and large IDW exceed
   it and were silently killed. Now HOST_RUN_TIMEOUT=900s (env-overridable).
NOTES / still open:
 - buildings-openbuildings writes cell.buildings (per-cell coverage). geo.building (individual footprint
   POLYGONS) is 0 — that's the separate buildings-footprints ENRICHMENT driver (runs after cell.buildings;
   long GEE job). Not run yet.
 - osm-roads → geo.osm_feature: running (background) at time of writing.
 - hydrology (hydro-merit / osm-drainage) not started; rainfall NOT published to store (can't install).
 - The uploaded PBF `central-zone-260824.osm.pbf` happens to cover the full v2 AOI (facilities span the box).
 - SCHEDULER is single-threaded on /run (synchronous) — a long run blocks health checks + other runs and it
   proved fragile under load; restarted several times. A proper fix = run manual /run off-thread too (the
   TICK already dispatches async) or a run queue.

## Nashik baseline for Kumbh (2026-08-27) — AOI set, keyless done, GEE+OSM blocked on user
Nashik tenant existed (steward ds:nashik:steward) but had NO AOI. Provisioned `nashik-admin`
(POST /users, internal-gated — avoids the identity-restart→JWKS-rotation cascade) and set
space.aoi `ds:nashik:space/aoi/nashik-kumbh` bbox [73.48,19.85,73.88,20.08] h3_res=9 — covers BOTH
Nashik (73.79/19.997) and Trimbakeshwar (73.53/19.94), the two Kumbh sites (~42×26 km).
Installed+granted the 6 baseline drivers (landcover-dw, terrain-dem, population-ghsl,
buildings-openbuildings, weather-forecast, heat) + cell-indexer for nashik. Ran the KEYLESS ones:
cell.weather_forecast = 11007 res-9 cells (full AOI); heat lst 36 pts. (cell.heat IDW re-index errored
once — minor, revisit.)
BLOCKED on user (per no-raw-credentials pref):
 - GEE layers (buildings/terrain/population/landcover): no GEE_SERVICE_ACCOUNT_KEY in Vault for nashik →
   user must set it via Connections → API keys (same as kmc). Drivers are installed+granted, so it's a
   one-command run each once the key is in.
 - OSM layers (roads/facilities/drainage): need a Nashik .osm.pbf uploaded (the kmc one is Kanpur).
Also: kmc expanded-AOI re-ingest FULLY COMPLETE — geo.building 65676, cell.hydrology 8789,
geo.hydro_feature 154 (buildings-footprints + hydro-merit GEE pair finished).

## Nashik baseline COMPLETE (2026-08-27) — 10/11 layers, res-9, both Kumbh sites
User set the GEE key + uploaded a correct Nashik PBF (western-zone-260821.osm.pbf; the first upload was
mistakenly the Kanpur central-zone file — caught via identical content hash). Final Nashik baseline, all
res-9 over AOI [73.48,19.85,73.88,20.08] covering Nashik + Trimbakeshwar:
  cell.builtup 11007, cell.greencover 11007, geo.terrain 11007 (Copernicus DEM), demographics.population
  11007 (GHSL), cell.weather_forecast 11007, cell.buildings 11007 (Open Buildings v3; resumed after the GEE
  batch was killed at 5400), geo.facility 650, geo.osm_feature/roads 16645, geo.hydro_feature 168,
  cell.drainage 1125. → parity with Kanpur; the physical substrate for the Kumbh crowd-safety solution.
KNOWN MINOR GAP: nashik cell.heat = 0. cell-indexer IDW re-index 403s on a broker call despite a correct
grant (reads environment.lst_observation/geo.landcover/space.aoi; writes cell.builtup/greencover/heat).
Same engine worked for kmc, so it's nashik-grant/steward-key specific — not diagnosed (log doesn't print the
403'd URL). Heat SOURCE (environment.lst_observation, 36 pts) IS ingested; only the derived interpolation is
missing. Low priority.
Nashik provisioning: nashik-admin via identity POST /users (no restart); tenant already existed.

## Crowd-safety mass-gathering solution — WORKING DEMO CORE (2026-08-28)
Built the sense→cells→intelligence→decision loop for the Nashik Kumbh, on SIMULATED data (every row
prov.source="simulation", scenario-tagged — NOT a real feed). Grounded in research: ~2.5M peak Shahi Snan,
Ramkund/Kushavarta hotspots, documented 1-2PM ghat pinch-point.
 - Schemas (network-published, kernel cache refreshed): cell.crowd_density (temporal), cell.crush_risk.
 - components/sim/kumbh_crowd_sim.py — peak-day timeline (13 frames 06:00→18:00), gaussian blobs at the two
   ghats, build→13:00 peak→dissipation; ~2.54M peak headcount; scenarios: baseline (5.2/m² danger),
   ramkund-crush (7.6/m² critical). Writes cell.crowd_density + derived cell.crush_risk.
 - viz.layer crowd-density (reds, value_field density_sqm) → animates in City Scan via the generic scrubber.
 - components/sim/crowd_recommender.py — reads crush state, finds the critical moment/site, emits a CITED,
   GRADED governance.recommendation (cites governance.rule crowd-crush-density-bands + the density-cell
   facts). Danger→divert/hold/pre-position; Critical→halt/relief-exit/108/surge/pause-batches.
 - Demo control (CLI for now): `python3 components/sim/kumbh_crowd_sim.py --scenario baseline|ramkund-crush
   --tenant nashik --clear` then `python3 components/sim/crowd_recommender.py --tenant nashik`.
Schema type gotchas: governance.rule.value = ARRAY; governance.recommendation for_facts=OBJECT,
evidence=ARRAY, proposed_action=STRING (additionalProperties:false on both). viz.layer color_scale enum =
viridis/reds/blues/aqi only; category enum excludes "environment"/"crowd" (used "people").
TODO (next slices): in-app demo-control panel + command-center ops app; bus-bunching + medical scenarios;
recommendation→commander ADMIT→governance.decision→platform.task fan-out to roles (Inbox); real-time path.

## Crowd Command app + demo-control + Inbox loop (2026-08-28)
Built components/apps/crowd-command (deck.gl ops picture): animated crowd-density heatmap + crush-risk
outlines + ghat markers + roads context + timeline scrubber; right panel = situation + crush alerts + the
cited governance.recommendation with an Admit & Dispatch button; bottom demo-control = scenario buttons
(Baseline / Ramkund crush). app_host bridges added: /bridge/crowd-scenario (runs kumbh_crowd_sim.py +
crowd_recommender.py for the tenant) and /bridge/crowd-admit (writes governance.decision + platform.task +
platform.inbox_item per role → lands in Inbox). Verified end-to-end: run ramkund-crush → CRITICAL rec →
Admit → 3 tasks + 3 inbox_items to role://nashik/{health.medical-responder, mobility.transport-controller,
safety.ground-marshal}. Shelved on nashik desktop; served in --no-verify-cert mode (not yet certified/
published). NEXT: certify+publish the app + bundle the whole thing as a `mass-gathering-safety` solution;
bus/medical scenarios; real-time trigger path.

## Crowd-safety: closed the case loop + human/system actor split (2026-08-28)
Answered "task to a human or a system?": BOTH, bound per role. Reworked _bridge_crowd_admit — orders carry
an actor kind: transport → a connected SYSTEM (assignee `system://nashik/msrtc-scheduler`, NO human inbox
item, routed to the system); medical + marshal → HUMANS (assignee role://, land in Inbox). Added
_bridge_crowd_complete (mark task done + roll up case → close when all tasks done) and
components/sim/transit_actuator.py (stands in for the MSRTC scheduler: polls system:// crowd tasks →
"re-times buses" → marks done → rolls up case). Verified: admit → system auto-actuates bus order + humans
complete Inbox tasks → case auto-CLOSES. Schema field gotchas: platform.task additionalProperties:False —
use done_at/completed_by (NOT completed_at/completion_note); status enum [blocked,open,claimed,done,
cancelled]. platform.case status enum [open,active,blocked,closed,cancelled] (NOT "resolved") + closed_at.
Also created nashik card viz.layers (task/case/decision/rec-card) so Inbox renders the subjects, and the
admit now writes the platform.case record (fixes the "subject not found (pending)").

## Crowd-safety decision receipt — reconstructable evidence manifest (2026-08-28)
The commander's `_bridge_crowd_admit` now writes a governance.decision whose `evidence_manifest`
pins the full basis — [recommendation, governance.rule, ...N crush_risk fact cells] — and whose
`rationale` carries the human DISCRETION narrative (facts seen · rule applied · what was chosen ·
orders dispatched). The Inbox renders a "Decision receipt — reconstructable basis" panel that
RESOLVES each manifest ref (recommendation title/action, rule bands, representative fact density/band)
and makes every entry drillable, so from the decision you can walk back to every input.
Honest limits:
- Reconstruction is LIVE-RESOLVED at view time, not SNAPSHOTTED. If the rule or a fact row is later
  retracted/superseded, the historical receipt resolves to the current version (or shows "pending"),
  not the exact bytes relied on at decision time. True point-in-time reconstruction needs the manifest
  to pin schema_version + a content hash / value snapshot per ref (ADR-0057 content-anchored citations).
- The facts panel drills at most 10 fact-cell chips in the UI; all ids remain in the manifest.
- Applies to the crowd-safety admit path. The generic Inbox decide flow (`/bridge/decide`) still writes
  a thinner manifest; harmonising both onto the same receipt-builder is a follow-up.

## Crowd-safety solution ported to certified components (2026-08-28)
The sideloaded crowd-safety demo was reconstituted as a Studio project in the airawatdeveloper sandbox
and published PROPERLY: 5 members (kumbh-crowd-sim driver, crush-risk-engine, crowd-safety-advisor skill,
transit-actuator driver, crowd-command app) each ported to the broker/run-token contract, dev-tested,
certified, and composed into solution ds:airawat:solution/mass-gathering-safety-kumbh (verified).
Fixes made along the way + honest limits:
- PUBLISH-AUTHZ BUG FIXED: _bridge_project_publish used _dev_token() (steward=airawat) for ALL publishes,
  so it could only publish ds:airawat:* components; a developer publishing under their OWN namespace
  (ds:airawatdeveloper:*) was refused by network _require_publisher. Now publishes as _developer_token()
  (devrick/airawatdeveloper) when the id's steward != airawat. Reference-host fix; the general rule is
  "publish as the participant whose tenant == the id's steward prefix."
- Governed NEW vocabulary to pass certify: domain `safety` + roles safety.incident-commander,
  safety.ground-marshal, health.medical-responder, mobility.transport-controller (POST /v1/domains,
  /v1/roles as steward). LIMIT: network ROLES/DOMAINS are in-memory dicts — a network restart loses these
  runtime additions unless seeded at boot; needs persistence for durability.
- App orchestration MOVED into the crowd-command frontend (generic /bridge/save writes case+tasks+inbox+
  decision as the commander; /bridge/run fires the certified chain). Added a GENERIC `env` pass-through to
  /bridge/run (forwards --set to the scheduler). The bespoke _bridge_crowd_scenario/admit/complete host
  bridges are now DEAD CODE — still present (so the old nashik demo keeps working until the certified
  solution is installed + verified in Nashik), to be REMOVED after that verification.
- LIMIT: scenario re-run no longer bulk-clears prior sim rows (idempotent same-id overwrite only); switching
  baseline↔crush can leave stale cells from the other scenario. Seed rule crowd-crush-density-bands must be
  present in the install tenant (engine falls back to 4.5/6.0 bands if absent).
NEXT: install the solution into Nashik + seed the rule → verify the certified demo end-to-end → remove the
dead crowd bridges from app_host. THEN enforcement A+B, then multi-AOI + dev cross-tenant read.

## Crowd-safety solution INSTALLED + VERIFIED in Nashik (2026-08-28)
Removed all old code from nashik (1637 sideloaded rows retracted; host _bridge_crowd_* removed;
components/sim/*.py deleted), then installed the certified solution and verified the certified pipeline
end-to-end in nashik (production tenant):
- Solution install issued capability GRANTS but did NOT kernel-install runnable members (no run-token) —
  had to install each of the 4 runnable members individually via /v1/components/install. GAP: the
  solution fan-out (/v1/solutions/install) should mint per-tenant run-tokens for runnable members, not
  only grants + app-shelf. (Apps ARE shelved by the fan-out.)
- SCOPE-TENANT BUG (mine): meta.yaml write scopes must NOT hardcode `tenant:` — install binds the write
  scope to the INSTALL tenant only when the scope has no tenant (like the baseline drivers). I'd written
  `tenant: airawatdeveloper`, so the nashik run-token carried a airawatdeveloper-scoped write cap →
  broker 403. Fixed: stripped tenant from scopes, bumped to 0.1.1, re-published + re-installed → caps
  now `tenant: nashik`. (Listings are immutable per version, so any scope fix needs a version bump.)
- VERIFIED GREEN in nashik via /bridge/run (the app's runScenario path): sim→1536 cell.crowd_density,
  engine→90 cell.crush_risk, advisor→CRITICAL recommendation — ALL writes ATTRIBUTED to
  `component://ds:airawatdeveloper:...` (NOT a human token). This is the enforcement gap closed in
  practice. Admit via generic /bridge/save → governance.decision with a 22-item evidence_manifest that
  RESOLVES (rec+rule+facts) = reconstructable receipt. transit-actuator (system actor) fulfilled the
  transport order → task done.
- OPEN: human-task completion → case-close. The Inbox `/bridge/complete` forwards to the workflow-engine
  `/complete-task`, which 401s tasks the app created via the generic registry bridge (they aren't
  registered with the workflow engine). The removed bespoke _bridge_crowd_complete used to close the case
  via a direct registry write+rollup. FOLLOW-UP: either the crowd-command app should complete+rollup via
  generic /bridge/save (like it now does for admit), or tasks must be registered with the workflow engine.
  Case correctly stays OPEN until human orders are fulfilled (human-in-the-loop), so this is the mechanism,
  not the semantics.

## Case-close seam CLOSED (2026-08-28)
Fixed the human-completion→case-close gap: /bridge/complete now tries the workflow-engine first (unchanged
for SOP tasks it manages), and on failure falls back to a GENERIC completion — marks the platform.task done
as the signed-in actor + rolls up the case (closes it when every sibling task is done) + marks the actor's
inbox item done. Verified in nashik: both human tasks completed "via generic", the last one CLOSED the
crowd-safety case (status=closed, closed_at set). The certified crowd-safety loop is now fully closed
end-to-end: sense (attributed) → derive → advise → admit (reconstructable decision) → dispatch → fulfil
(system actuator + human via Inbox) → case closes.

## Data-plane certified-writer gate — A written + B shadow-shipped (2026-08-28)
A (finding+design): docs/reviews/dataplane-certified-writer-gate.md. Root gap: registry WRITE trust
boundary = (token, own-tenant, schema-valid), NOT (certified component) — a human/tenant token can PUT any
schema-valid FACT into a production tenant via /v1/registry/objects, bypassing the certify spine (the
original crowd-safety sideload). PROV_ENFORCE only blocks ANONYMOUS writes, not human-writes-facts.
WRITER TAXONOMY (key design point, incl. user's aggregator input): certified-component (facts,
component://) | human-authority (governance/decisions, user://) | AUTHORIZED CROSS-TENANT SERVICE /
aggregator (unified citizen app, call-centre, unified billing — the GPay/PhonePe-over-banks pattern,
service://, writes across MANY agency tenants on a citizen's behalf). Enforcement must admit all three.
B (shadow shipped, kernel hot-patched + restarted): kernel/api/app.py _is_dataplane_schema +
_assert_dataplane_writer, called in registry_put. Data families (cell./geo./obs./air./environment./met./
demographics./risk., env DATAPLANE_SCHEMAS) written by a non-component:// agent → shadow-log once per
(schema,agent); 403 under DATAPLANE_ENFORCE=1. component:// (broker) + development tenants exempt;
governance/platform/viz/ref/space schemas untouched. VERIFIED: human cell.crowd_density write →
"[dataplane] SHADOW: uncertified data write" logged (not blocked); governance.decision write untouched.
Limits: SHADOW only (read blast radius from logs before enforce); the aggregator lane (cross-tenant
service-authorization grant) is NOT built — enforce is GATED on it landing, else it'd block legitimate
shared-service-provider writes; retract path not gated; hot-patch on local kernel container only (EC2 needs
same docker cp + restart). Consider making "authored-by: component" a governed schema attribute vs a
kernel prefix list.

## Cross-tenant aggregator lane — slice 1 (2026-08-28)
Built by REUSING existing mechanisms (per user: "the Data App had request+approve access — reuse it"):
- REQUEST→APPROVE→GRANT (network/api.py): new /v1/data-requests {file, list, decide} mirroring
  role-requests; approve calls the EXISTING _issue_grant → steward-signed governance.access_grant. A shared
  service provider/aggregator (unified citizen app; GPay/PhonePe-over-banks) files for a component's declared
  scopes in a TARGET tenant; that tenant's admin approves.
- KERNEL cross-tenant enforcement (kernel/api/app.py _assert_write_own_tenant): a delegated write
  (component:// obo user://) into ANOTHER tenant is allowed IFF the component holds a valid steward-signed
  grant FROM THE TARGET tenant for (write, schema) — reuses _steward_authorizes. No grant → 403 as before.
- app publish now synthesises scopes from writes/required_schemas (platform-spec _bridge_project_publish)
  so an app's grant authorises its delegated writes.
VERIFIED: caller in tenant airawatdeveloper, acting through crowd-command, wrote governance.decision INTO
nashik → stored, attributed `component://…crowd-command@0.1.1 obo user://airawatdeveloper/devrick`;
ungranted schema (cell.crush_risk) refused; ungranted component (transit-actuator) refused.
LIMITS / next slices: (1) WRITE path only — cross-tenant READ (unified VIEW across agencies, the more common
aggregator need) not yet done: /v1/registry/query + resolve don't carry component headers or check grants.
(2) No aggregator-facing UI yet (reused backend endpoints; extend admin "requests" tab / a new aggregator app).
(3) Grant is PER-COMPONENT, not per-citizen — the `obo user://` is in attribution but the grant authorises the
component broadly; fine-grained per-citizen consent (VC/consent) is a deeper layer. (4) Relaxation is on the
delegated /v1/registry/objects path; the broker /v1/write cross-tenant gate (:839) is NOT relaxed (headless
components still own-tenant only). (5) Kernel trusts X-Component-Id (app_host sets it for certified apps) —
crypto-verify the component identity is the hardening follow-up. Docs: reviews/dataplane-certified-writer-gate.md.

## Cross-tenant READ slice (aggregator unified view) — 2026-08-28
Mirror of the write lane on the READ path: a certified component (unified citizen app) may READ another
agency tenant's rows IFF it holds that tenant's signed READ grant for the schema.
- kernel _asof_rows + registry_resolve: `tenant` in the query body names the TARGET agency; with X-Component-Id
  + a valid read grant → reach scoped to ds:<target>:; no grant → returns NOTHING (fail closed, never falls
  back to caller's own tenant). Own-tenant reads unchanged.
- app_host /bridge/query stamps X-Component-Id (calling app) + forwards `tenant` → a unified app fans out
  per agency.
VERIFIED: crowd-command (granted read cell.crowd_density from nashik) reading nashik from an airawatdeveloper
session → 5 rows; no X-Component-Id / ungranted schema / ungranted component → 0; own-tenant + nashik-local
queries unaffected (regression clean).
LIMITS: grant reads = the component's declared required_schemas (coarse; per-record/per-citizen scoping is the
VC/consent layer). Query targets ONE tenant at a time (the app fans out). resolve-by-id cross-tenant uses the
id's steward as target. Still per-component grant, not per-citizen consent.

## Civic service federation (ADR-0067) — S1: directory + search (2026-08-28)
network/api.py: `network.service_offering` directory — POST /v1/service-offerings (steward-gated + steward-
SIGNED), GET /v1/service-offerings (discover by domain/service/tenant), POST /v1/service-offerings/resolve;
POST /v1/service/search = the Beckn-adapted `search`→`on_search` (returns the matching provider catalog in a
context+message envelope). Register "service_offerings" in the _NS name-list.
VERIFIED: nashik published water-new-connection (urban) + grievance-file (safety), both signed by ds:nashik:
steward; search{domain:urban}/query:water/query:grievance return the right providers with their interaction
models + endpoints.
LIMITS / next slices: S1 is DISCOVERY only — no transaction lifecycle yet (init→case, confirm/status). search
is synchronous over on-platform offerings (async provider search for data_at_source/connector = later).
network.service_offering not yet published to the schema catalog (record shape is de-facto; govern it S2).
Endpoints are declared (solution://tenant/name) but not yet routed to (the gateway/router is S4).

## Civic service federation (ADR-0067) — S2: init → provider case (2026-08-28)
platform-spec /bridge/service-init: the `init` interaction. A certified aggregator resolves a service
offering from the directory (S1), then opens a platform.case IN THE PROVIDER tenant via the DELEGATED
cross-tenant write (component://app obo user://citizen) — grant-gated by the provider's platform.case write
grant. Returns the on_init transaction handle {transaction_id, provider case ref, status:initiated}.
VERIFIED: citizen (airawatdeveloper/devrick) init'd nashik's water-new-connection via crowd-command →
case ds:nashik:case/svc-<txn> created AT NASHIK, attributed component://…crowd-command@0.1.1 obo
user://airawatdeveloper/devrick; service/status/step correct. transaction_id carried in the case id (the
case IS the provider-side transaction record — data-at-source).
LIMITS / next: S2 handles ON-PLATFORM providers (case written via delegated cross-tenant write); DATA-AT-
SOURCE / heterogeneous providers need the S4 gateway to route init to a real endpoint (declared but not yet
called). Intent/form payload not persisted (case carries service+who+when only; application-body schema =
follow-up). No provider-side solution logic invoked yet (eligibility/case-numbering/workflow) — the aggregator
drops the case; provider-mediated fulfilment (BPP runs its logic) is S4. Next: S3 confirm/status + receipts.

## Civic service federation (ADR-0067) — S3: confirm/status + receipt (2026-08-28)
platform-spec /bridge/service-confirm + /bridge/service-status: the `confirm` and `status` interactions.
- confirm: READ the provider case cross-tenant (grant-gated; pass filter.schema=platform.case because the
  id segment is short "case" not "platform.case" — _schema_of_id mismatch), ADVANCE it (status active /
  step confirmed) via the DELEGATED write, and write an interaction.receipt (BAP-side provenance, citizen's
  own tenant). Returns on_confirm.
- status: READ the provider case cross-tenant (grant-gated) → on_status {status, current_step, service}.
- interaction.receipt (ADR-0058) reused: mapped service semantics onto {interface:service.<action>@0.1.0,
  modality:request, provider, agent:component://app obo user://citizen, run:txn/<id>, request_digest:case,
  response_digest:on_<action>:<txn>, at}. response_digest is REQUIRED by the schema.
VERIFIED: init→submitted; confirm→provider case advances to active/confirmed + receipt written; status
reflects it; receipt carries the obo agent + txn. Aggregator grant needed READ platform.case too (added
platform.case/platform.task to crowd-command required_schemas → republish 0.1.2 → re-grant).
LIMITS / next: still on-platform provider (delegated write); provider-side fulfilment logic + heterogeneous
routing = S4 (gateway). No provider-side receipt yet (BAP-side only). Next: S4 gateway/router + S5 fee/consent.

## Civic service federation (ADR-0067) — S4: gateway + provider-side fulfilment (2026-08-28)
network /v1/service/route = the GATEWAY (BG): resolves offering → provider+endpoint, verifies the action,
RECORDS a network.service_transaction (correlation ledger; GET /v1/service/transactions to look up), returns
the routing decision. platform-spec /bridge/service-route + _provider_fulfil = the PROVIDER-SIDE fulfilment:
the provider's own solution (reference BPP) creates the case WITH ITS OWN authority + a case NUMBER — the S4
distinction from S2 (aggregator dropped the case). VERIFIED: BAP(devrick via crowd-command) → gateway →
nashik BPP → case ds:nashik:case/water-new-connection-<NUM>, attributed component://ds:nashik:solution/
water-new-connection obo user://nashik/nashik-admin (the PROVIDER, not the aggregator); gateway ledger recorded
{txn, bap, case, status:received, history:[init]}.
LIMITS: (1) the reference BPP (_provider_fulfil) STANDS IN for the provider's real solution — ADR-0050
execution engine would run the provider's declaration; here app_host acts as the provider (logs in as
<provider>-admin). (2) On-platform only: real HETEROGENEOUS providers = the gateway POSTs the message to the
offering's real HTTP endpoint (the endpoint is in the routing decision — the seam exists — but the external
HTTP forward + async on_<action> callbacks are not built; it's synchronous + in-process). (3) init only in the
reference BPP (confirm/status still via S3). (4) Message signing (ADR-0024) not enforced on the gateway yet.
(5) BPP holds provider creds via login — a real BPP is the provider's own service with its own key.
NEXT: S5 (fee via `select` + per-citizen consent VC); async callbacks + real endpoint HTTP forward + gateway
signature verification = productionization of S4.

## Civic service federation (ADR-0067) — S5: fee quote + per-citizen consent (2026-08-28)
platform-spec: (a) `select` → _quote_fee: the provider returns ELIGIBILITY + an itemized FEE quote pre-commit
(no case). Reference fee table (production: derive from offering.fee_ref / finance.* rules). (b) per-citizen
CONSENT: /bridge/service-consent — the citizen issues a governance.consent {citizen, aggregator, service,
provider, expires_at, status} into their OWN tenant, attributed component://app obo user://citizen. A
COMMITTING action (init/confirm) via /bridge/service-route now passes a CONSENT GATE (_verify_consent): a
valid, unexpired consent from the citizen authorising THIS aggregator for THIS service must exist, else 403.
VERIFIED: select→₹1500 itemized quote; init WITHOUT consent→403; consent issued; init WITH consent→provider
fulfils (case + provider reference).
LIMITS: consent is a governance.consent RECORD verified BAP-side (app_host reads the citizen's own consent) —
production consent = a signed Verifiable Credential in the citizen's wallet, independently verified by the
PROVIDER (ADR-0049 credential service, which lives in legacy AirOS, not this stack). governance.consent is
UNGOVERNED (no schema in the catalog → registry skips validation); govern it + finance.fee as a follow-up.
Fee is quoted only (no payment capture). This COMPLETES ADR-0067 S1–S5 (reference-grade).

## Jan Seva citizen app + governed ADR-0067 schemas (2026-08-28)
Built the jan-seva citizen front door via Studio (scaffold→author→publish): components/apps/jan-seva
(certified app, BAP). Governed the 3 previously-ungoverned ADR-0067 schemas directly against the network
authority so the app could publish (certify enforces "all declared schemas governed"): governance.consent
(sensitive; defined to match /bridge/service-consent writes exactly — registry-validated), plus permissive
network.service_offering + network.service_transaction (network-held records, not registry-validated).
Refreshed the kernel schema-cache so consent writes validate. VERIFIED served at /apps/jan-seva/ + full
complaint flow (search→consent→file→track) through its bridges. LIMIT: published schemas + service offerings
live in the network's in-memory store (reseed after a network restart). The Studio Solution Expert had guessed
service.offering/service.transaction (wrong domain) because these were ungoverned — now governed under the
correct network.* names.

## Person-centric citizen + hierarchical jurisdiction (ADR-0067) — 2026-08-29
Built the jurisdiction-scoped citizen model. network/api.py: a governed HIERARCHICAL jurisdiction registry
(/v1/jurisdictions publish/list + /v1/jurisdictions/resolve returns the ancestor chain; nation→state→city→ward);
register "jurisdictions" in the _NS name-list (KeyError otherwise). Service offerings now carry `jurisdiction`
(code they serve, default=agency tenant) + `entitlement` (residence|property). platform-spec: /bridge/profile-save
+ profile-get (the citizen's PERSON-CENTRIC civic.profile — residence[] + property[] jurisdiction codes, written
to their OWN tenant obo the citizen); /bridge/service-search now JURISDICTION-SCOPES to entitlement (a service at
jurisdiction J is visible iff J is an ancestor-or-self of the citizen's residence — or property — jurisdiction;
national=root visible to all). Governed civic.profile (registry-validated) + network.jurisdiction schemas.
VERIFIED: Pune-resident+Nashik-property-owner sees national + nashik-property + NOT nashik-residence services;
after a MOVE to nashik, nashik-residence services appear — same identity/profile, one attribute changed.
This is the answer to "citizen moves cities": identity/history/wallet/open-cases persist (person-centric +
data-at-source + ledger keyed by citizen); only visible services change with the verified jurisdiction.
LIMITS: jurisdiction is self-declared+verified flag (real KYC/address-proof = follow-up); jan-seva has no profile
UI yet (search auto-filters if a profile exists, else unfiltered); legacy offerings without a jurisdiction show
to all; move-time "change of address as a cross-agency service" not built (natural next). In-memory network store.

## Citizen self-signup + profile/location UI (one slice) — 2026-08-29
Closed the "register as a citizen" gap end-to-end. identity.py: PUBLIC `POST /register {username,name,contact}`
— self-signup that can ONLY mint a `civic.resident` in the fixed `CITIZEN_REALM` (=`citizens`), auto-issues a
token (no internal token, unlike POST /users). app_host: `/bridge/citizen-register` (signup → verify → open a
browser session → write civic.profile with chosen residence, all in one call, no prior session) + `/bridge/
jurisdictions` (city picker) + a shared `_write_civic_profile` helper reused by profile-save. jan-seva 0.1.2:
first-run "Join & set your location" screen (name/username/contact + residence + optional property city),
identity bar ("📍 <city> · I moved · Sign out"), and an "I moved" flow (profile-save new residence). New
`citizens` tenant registered at the network (person-centric: citizen identity is network-level, NOT a city).
VERIFIED as a BRAND-NEW self-registered citizen (not a seeded user): Join(user://citizens/asha)→discover
(grievance[nashik/residence]+property-tax[nashik/property]+passport[in])→file(real ds:nashik case)→MOVE to
pune(keep nashik property)→grievance GONE, property-tax+passport STAY. All writes attributed
`component://…jan-seva@0.1.2 obo user://citizens/<sub>`.
LIMITS/GOTCHA: restarting identity.py ROTATES its signing key unless started with VAULT_ADDR+VAULT_TOKEN
(local-dev backend = fresh key each boot) → downstream services that CACHE JWKS (the kernel's `_authn.verify`
does NOT self-heal on bad-signature like reference/tokens.py does) reject the new tokens with "bad signature"
until they refetch; the kernel needed a restart to repick the key. FIX FORWARD: always start identity with
Vault (stable key) + port the self-healing refetch into the kernel's _authn. Self-signup KYC = self-declared
+ verified flag (no real ID proof); `citizens` realm is in-memory in the network (reseed on restart); jan-seva
still published at 0.1.1 cert while disk meta is 0.1.2 (local --no-verify-cert serves disk; republish to align
the marketplace certificate).

## Citizen home + per-citizen marketplace — 2026-08-29
Citizens now get a consumer HOME distinct from the operator desktop. app_host: `_is_citizen(claims)` (holds
civic.resident, NOT admin/dev/steward) → `/` serves `citizen-home.html` instead of the operator `desktop.html`.
PER-USER app shelf `ds:citizens:app_shelf/<sha1(sub)>` (each citizen curates their OWN home, unlike the shared
per-tenant operator shelf). `_civic_catalog()` = apps that are `public` OR target civic.resident, minus
system/developer_only/rogue — this is the citizen marketplace. New endpoints: GET /citizen/apps {mine, catalog}
+ /bridge/citizen-app-add|remove (only civic-catalog apps allowed on a citizen home). New certified app
`my-requests` (roles [civic.resident], reads the ADR-0067 transaction ledger → cross-agency request tracker).
jan-seva Join now redirects to `/` (the citizen home). VERIFIED: new citizen → home serves "My Services",
starter set [jan-seva, my-requests], add/remove persists per-user, My Requests opens (200), operator apps
NOT leaked into the citizen catalog.
LIMITS: civic catalog currently = jan-seva + my-requests only — **Document Wallet (ADR-0049) and Field Report
were built in the OLDER stack, NOT ported into this components/apps deployment**, so they don't appear yet
(porting them = follow-up; then they auto-appear via roles:[civic.resident]). No "sign back in" for a RETURNING
citizen whose cookie expired (Join mints a new account; a citizen login screen against the `citizens` realm is
the follow-up). citizen home chrome is minimal (no notifications/profile-edit beyond jan-seva's "I moved").

## Recertified jan-seva + my-requests through the certify spine — 2026-08-29
Closed the cert drift for the two citizen apps. Via /bridge/project-publish as devrick (steward of the
airawatdeveloper namespace): walk source → POST /v1/certify (conformance runs: well-formed + governed vocab
+ digest-from-content → CA-signs, pinning the bundle digest) → /v1/store/publish → reload_apps. Both now
`verified:true`. PROVED: package.artifact_digest(dir) == certificate.evidence_digest for jan-seva (2303841)
and my-requests (2660f0c) — i.e. they'd PASS a verify-on host (load_apps digest check), not be REFUSED.
HONEST WIDER STATE: the rest of the local app tree is cert-DRIFTED from continuous dev editing — admin, chat,
inbox, studio, storefront, network-admin, city-scan, air-explorer all show disk≠cert (would be REFUSED on a
verify-on host); city-explorer/city-setup/connections/roads-viewer have no resolvable certificate. This is
exactly why the reference app_host runs `--no-verify-cert` locally. Flipping verification ON would refuse those
drifted apps until each is republished — a full-tree recertify sweep is the follow-up to run before any
verify-on / production deploy.

## Full-tree recertify sweep + enforcement ON — 2026-08-29 (RESOLVED)
Republished all drifted/uncertified apps (bumped the 8 signed ones to 0.1.1 — marketplace listings are
IMMUTABLE, a changed bundle needs a NEW semver; the 4 never-published went through as-is). Restarted the
app-host WITHOUT --no-verify-cert: 20 apps load "certified · digest OK"; the ONLY refusal is `rogue-app`
(ds:acme:app/rogue-app, the adversarial test app with no certificate) — i.e. enforcement is ON and PROVABLY
working (rejects the uncertified/foreign one, admits the rest). Reference host now runs in true enforcement
mode. NB: keep it OFF only when actively editing app bundles (edit → republish → it passes again).

## National services always visible + citizen browse — 2026-08-29
Fixed: a NATIONAL (root-jurisdiction) service was dropped for a citizen whose residence chain didn't resolve
up to the nation (e.g. residence stored as "Kanpur" not the code "kanpur" → resolve fails → "in" absent →
passport hidden). Root cause: entitlement filter required the service's jurisdiction to be in the citizen's
ancestor set, which depends on the chain resolving. Fix (_bridge_service_search + _national_roots): a service
whose jurisdiction is a nation-level/root code is visible to EVERYONE, independent of the citizen's chain —
so national services always show even with a malformed residence. City-scoping unchanged (nashik-residence
still hidden from a Kanpur resident). Also: discovery was QUERY-GATED (network service_search matches the
query substring) with NO browse, so a citizen had to guess "passport" — jan-seva now runs an empty-query
BROWSE on load ("services available to you"). VERIFIED: Kanpur browse shows passport-seva[in]; broken
residence ['Kanpur'] still shows passport; nashik grievance not leaked to Kanpur.

## Untagged-offering leak fixed (fail-closed) — 2026-08-29
Two untagged test offerings (nashik grievance-file, water-new-connection — seeded pre-jurisdiction) were
leaking into EVERY city because the entitlement filter showed jurisdiction=None offerings to all. Retired
both (agency retire endpoint) AND hardened _bridge_service_search: an untagged offering now FAILS CLOSED
(hidden) instead of shown-to-all; only NATIONAL (root) + the citizen's-jurisdiction services show. VERIFIED:
Kanpur browse = [passport-seva] only; Nashik browse = [grievance-redressal(nashik), passport-seva]. New
offerings always carry a jurisdiction (registration defaults it to the agency tenant), so untagged = stale data.

## Workflow interpreter (declarative, tenant-configured) — 2026-08-29
Built the multi-step workflow interpreter. An offering carries fulfillment.workflow = ordered [{step, role,
task}] (a DECLARATIVE config — tenant-admin-editable, the "simple service, no developer" path). On submit the
provider opens the case + first step's task→role inbox (attributed to the bound CERTIFIED solution). On each
task completion (_bridge_complete step 0, BEFORE the SOP engine), _advance_service_workflow reads the offering's
workflow, marks the task done, and creates the NEXT step's task+inbox for the next governed role — or closes
the case after the last step. Network validates every workflow step's role is governed. VERIFIED 3 hops:
triage(civic.grievance-officer)→field-visit(urban.sanitation-officer)→verify(civic.grievance-officer)→closed,
each landing in the correct role's inbox, all attributed to component://…grievance-handling@0.1.0 obo the
completing officer. LIMITS: linear steps only (no branches/parallel/conditions/decisions); no SLA timers or
reminders; completion is a simple "done" (no per-step form/decision capture yet); citizen isn't notified on
close (cross-tenant). These + a Service Studio (tenant-admin UI to author form+workflow) are the follow-ons.

## Service Studio + generic declarative-service runner — 2026-08-29
Built the no-code service path. (1) `ds:airawatdeveloper:solution/declarative-service` — a GENERIC certified
solution (trust anchor) that fulfils any config-driven service; the form (request_schema) + workflow
(fulfillment.workflow) live as governed config on the offering, run by the interpreter. (2) Service Studio app
(`ds:airawatdeveloper:app/service-studio`, roles platform.tenant-admin/steward): form builder + workflow
builder (steps→governed roles, reorder) → publishes a steward-signed offering bound to declarative-service —
NO solution developer. VERIFIED: a tenant admin authored "Birth Certificate" (form child_name/dob + verify→
issue workflow) bound to the generic runner; a Nashik citizen discovers it. No backend bridge changes needed
(service-offering-save forwards the full body; catalog?kind=roles + jurisdictions drive the pickers).
TWO-TIER MODEL LIVE: simple services = tenant-admin config on the generic runner; complex = bespoke certified
solution. LIMITS: jan-seva still submits a fixed {description} — it doesn't yet RENDER request_schema as the
intake form (citizen-side dynamic form = next); workflow is linear (no branches/decisions/SLAs); Service Studio
has no fee/eligibility builder yet; birth-cert demo reused civic.grievance-officer (no registrar role governed).

## Jan Seva renders the authored intake form — 2026-08-29
Jan Seva now RENDERS the offering's request_schema (authored in Service Studio) as the citizen intake form —
one input per property (text/textarea via x-widget/number/date/format, required markers), instead of the fixed
{description} box (kept as fallback when a service has no request_schema). On submit it collects the values into
message.form + a labelled human summary (message.description). VERIFIED end-to-end: admin authored Birth
Certificate (Child name, Date of birth) → citizen sees those exact fields → officer's inbox shows "Child name:
Aarav Patil · Date of birth: 2026-08-01". jan-seva recertified 0.1.4. LIMIT: the submission is persisted as the
human summary on the inbox_item body (officer-visible); STRUCTURED on-case persistence needs a form/data field
on platform.case (strict schema) or a governed service.submission schema — the honest follow-on. No client-side
validation beyond required-marking; no file-upload field type yet.

## Verifiable Credentials: issue-on-completion → wallet (ADR-0049 slice 1) — 2026-08-29
Native VC layer wired to the service rail. Governed civic.credential + civic.submission. Network: /v1/credentials/
issue (signs a VC with the ISSUER tenant's Vault steward key — same key published in the directory), /v1/credentials
(holder-scoped wallet read), /v1/credentials/verify (verifies against the issuer's PUBLISHED directory key —
key_source:directory, exactly as another operator would; falls back to local signer only if unpublished). app_host:
_provider_fulfil persists the citizen's structured civic.submission; the interpreter, when a workflow step declares
`issues: <type>`, mints a signed VC (claims = the submission) into the citizen's wallet; bridges my-credentials +
credential-verify. New app my-documents (citizen wallet, roles civic.resident, on the citizen home starter set);
Service Studio 0.1.1 adds an "issues" field per workflow step (no-code). VERIFIED: citizen applies for Birth
Certificate → verify→issue workflow → VC ds:nashik:credential/... issued with claims {child_name, dob} → appears in
My Documents → citizen verifies offline: verified True, key_source directory. LIMITS: reference WALLET = holder-scoped
rows in the network credential store (not a holder-controlled/tenant wallet; portability is by the signed VC itself);
no revocation/expiry/selective-disclosure; issuance authz = any member of the issuer tenant (reference); SLICE 2
(consume: an offering declares required_credentials → Jan Seva presents the wallet VC → provider verifies → no
re-collection, e.g. School Admission reuses Birth Certificate) NOT built.

## VC reuse — required_credentials on apply (ADR-0049 slice 2) — 2026-08-29
Consume side built. An offering carries required_credentials:[type]. Jan Seva reads the citizen's wallet, PRESENTS
the matching VC on apply (or blocks + explains if missing), and sends credential_refs. The provider RE-VERIFIES
each (app_host _verify_required_credentials → network /v1/credentials/verify): signature valid + held by THIS
citizen + correct type — no document upload; the verified VC ids are attached to the case as subjects (evidence).
Service Studio adds a "requires documents" field (no-code). VERIFIED: citizen holding a birth-certificate VC →
School Admission accepts it (case created, reused not re-collected); citizen WITHOUT → blocked; citizen presenting
ANOTHER holder's VC → blocked (holder mismatch). The Birth Certificate → School Admission reuse chain works.

## OPEN — credential schema governance (raised by user): civic.credential + this session's other schemas
(network.service_offering, network.jurisdiction, network.service_transaction, governance.consent, civic.profile,
civic.submission) were published via the DIRECT steward path POST /v1/schemas (signed + name-linted, so they ARE
governed) — but NOT through the ADR-0056 decided change-request loop (POST /v1/schema-requests → /decide →
governance.decision). For network-wide trust-critical schemas they SHOULD carry a network APPROVAL decision.
FOLLOW-ON: re-route these through propose→decide so each has a governance.decision record.

## Credential types governed + enforced (propose→approve) — 2026-08-29
Made credential TYPES governed vocabulary and ENFORCED it. A credential type = a governed `credential.<snake>`
schema (x-kind:fragment — the claims value-object contract), created via the PROPER ADR-0056 loop: developer
files POST /v1/schema-requests → the NETWORK decides POST /v1/schema-requests/decide (a decided change-request;
trail records requested_by + decided_by). credential.birth_certificate approved this way. ENFORCEMENT (network):
/v1/credentials/issue rejects a type that isn't a governed credential.* schema; /v1/service-offerings rejects a
workflow step `issues:` or a `required_credentials` entry that isn't governed. VERIFIED: issue governed type ✅;
issue 'fake-cert' 🔒; offering requiring 'not-governed' 🔒; full chain (issue credential.birth_certificate →
wallet → reuse for School Admission) ✅. Domain `credential` governed. NOTE: the ALREADY direct-published civic.*
+ network.* schemas from earlier still lack an approval decision (can't re-propose at same version, line 733);
new schemas now go through propose→approve. Claims aren't yet validated against the type's fragment schema at
issue (type-governed, not claims-validated) — a fast follow.

## Holder-controlled wallet: accept-into-own-tenant (ADR-0049) — 2026-08-29
Wallet is now holder-controlled, not a shared-store view. Network: issuance creates an OFFER (status "offered",
NOT auto-landed); POST /v1/credentials/accept (holder-gated) marks it accepted + returns the signed VC. The
SIGNED core is now IMMUTABLE FACTS ONLY — `status`/`accepted_at` moved OUTSIDE the signature (fixed a real bug:
mutating status on accept previously broke the signature; verify strips lifecycle fields). app_host: /bridge/
credential-accept DEPOSITS the citizen's own signed copy into THEIR tenant (ds:citizens:credential/<h>, a
civic.credential wrapper carrying the original signed `vc`), attributed component://…my-documents obo the
citizen — a genuine own-tenant write, not a network-store row. Wallet (my-documents 0.1.1) shows OFFERS (Accept)
+ HELD (own tenant, Verify). Reuse now PRESENTS the held signed VC OBJECT; the provider verifies its signature
offline (not by network id). VERIFIED: issue→offer→accept(deposit ds:citizens:credential/…)→held→verify(True,
directory key)→reuse for School Admission ✅. LIMITS: citizens share one `citizens` tenant, so held-credential
reads are holder-FILTERED not row-authz'd (a citizen querying civic.credential without a holder filter could see
others' — needs per-citizen tenant or row-level ACL); no revocation/expiry/selective-disclosure; storage is
still server-side (citizen's tenant), not a device/edge wallet.

## Fix: Approve advances the workflow (was closing the case, skipping issuance) — 2026-08-29
BUG: the Inbox 'Approve' on a plain review task calls /bridge/decide → the decision service closed the case as
'decided', BYPASSING the service-workflow interpreter — so a birth-certificate approved at 'verify' closed
before reaching the 'issue' step, and NO credential was ever offered (nothing to Accept in My Documents).
FIX: _bridge_decide now intercepts service-workflow tasks (case has workflow+service) — approve → advance via
_advance_service_workflow (verify→issue→mint VC offer); reject → close the case rejected. VERIFIED via the real
Inbox path: file → Approve verify (→issue) → Approve issue (→ credential offered) → offer appears in the citizen's
My Documents. WHERE TO ACCEPT: My Documents app (citizen-home tile) → "Offered to you" → Accept into my wallet.
OPEN: My Requests shows the stale submit-time transaction status, not the live case current_step (should read the
case); no citizen notification when a credential offer is ready (inbox_item to the citizen = follow-on).

## Live My Requests status + credential-ready prompt — 2026-08-29
(1) LIVE TRACKER: the workflow interpreter now syncs the network service_transaction on every transition —
new POST /v1/service/transactions/status {case,status,step} (token-gated), called from _advance_service_workflow
(advance→in_progress, close→resolved) and the decide-reject path (→rejected). My Requests (reads the txn ledger)
now shows received→in_progress→resolved/rejected instead of the frozen submit-time status. No My Requests app
change (it already renders x.status). (2) CREDENTIAL-READY PROMPT: the citizen HOME shows a banner "🎫 N
documents ready to accept → My Documents", computed from GET /v1/credentials?status=offered&holder=me. VERIFIED:
filed=received → approve verify=in_progress → approve issue=resolved + prompt shows 1 offer.
NOTE: the prompt is a COMPUTED home banner, NOT a stored platform.inbox_item in the citizen's inbox — a real
cross-tenant inbox write (nashik officer → citizens tenant) is BLOCKED by the own-tenant gate; a genuine pushed
notification would need a platform-service writer or a steward grant into the citizens tenant (follow-on).

## Inbox UI: Approve now works for workflow steps + shows submitted details — 2026-08-30
Fixed 3 UI symptoms from real browser use: (1) clicking Approve "did nothing" — the Inbox decide() assumed a
decision RECEIPT in the response (r.json.decision.id) and threw silently on the service-workflow response
({advanced_to, via:workflow}); the backend advanced the task but the UI never updated (refresh showed 'done').
Now decide() handles via:workflow → shows "Approved — advanced to <step>" / "credential issued" + reloads.
(2) officer couldn't see the applicant's submission (name/DOB) — the drawer showed the task subject only; now it
renders the inbox_item body ("Submitted by applicant: …") so the officer sees the form. (3) no citizen banner —
was a consequence of (1): a 2-step service (verify→issue) needs BOTH approvals; the credential is only minted at
the issue step. Inbox recertified 0.1.2. NOTE: officer sees the SUMMARY (inbox body); rendering the structured
civic.submission (typed fields) in the case view is a follow-on.

## Citizen navigation + login + case application view — 2026-08-30
Four UX fixes from browser testing: (1) run_shell back link is now ROLE-AWARE — a citizen sees "← My Services"
(→ /, the citizen home), staff see "← Desktop" (→ /desktop), anonymous hidden; kept for citizens (was hidden
for public apps), only the identity BADGE is hidden on public apps (overlap). (2) Jan Seva gate is now LOGIN-FIRST:
"Sign in" (username → POST /login {realm:citizens}) with a link to "Create an account"; sign-out lands here (a
login page, not the signup form). Returning-citizen login verified. (3) Inbox: opening a CASE now renders the
citizen's submitted application (resolves the linked civic.submission by id-stem: case/→civic/submission/, shows
typed fields). (4) [prior] Approve advances workflow + shows submitted body on the task. inbox 0.1.3, jan-seva
0.1.7. NOTE: returning-citizen login is passwordless (reference IdP, username only) — real auth = Keycloak/OIDC.

## Citizen home is now a consistent SPA shell (like the operator desktop) — 2026-08-30
Root cause of the "inconsistent header": the operator desktop.html is a SPA shell (persistent top bar + a window
with a titlebar "← Desktop" + an iframe that loads apps IN PLACE); the citizen home was just a tile grid that
NAVIGATED AWAY to the run-shell per app, so it had no persistent chrome. Rebuilt citizen-home.html on the SAME
pattern: sticky bar (🇮🇳 My Services · name·city · Sign out) + a window with a "← My Services" titlebar + an iframe
loading /apps/<id>/ in place. Sign out → the citizen login (jan-seva gate). VERIFIED: / serves the shell (bar +
win + iframe + "← My Services"); apps load 200 via the iframe path. The run_shell.html role-aware back link
(citizen→My Services) still covers direct /run?app=X deep links. NOTE: an app with its OWN in-frame header (e.g.
jan-seva's "I moved · Sign out") now shows alongside the shell titlebar — minor redundancy; the shell bar is the
primary Sign out.

## Service Studio redesign (3-pane + AI Expert + governed required-docs) — 2026-08-30
Rebuilt service-studio (0.2.0) to mirror the Solution Studio: LEFT nav (my services + "＋ New Service"), CENTER
Service Editor (basics · intake form builder · workflow builder with governed role + governed "issues" credential
dropdowns · required-documents), RIGHT Service AI Expert panel (collapsed by default). Preview button (citizen-view
modal: required docs + form + workflow). Required Documents is now a MULTI-SELECT of network-APPROVED credential
types (new bridge /bridge/catalog?kind=credential-types → credential.* schemas) — NOT free text. Service AI Expert
(new _bridge_service_expert, LLM via the model gateway EMBED_URL/complete): from a description/conversation it
returns {reply, spec, new_credential_types}, GROUNDED in the governed roles + credential types (only valid values);
"Apply to editor" fills the whole form; a suggested NEW credential type shows a "Propose to network" button that
files a schema-request (propose→approve). VERIFIED: catalog credential-types returns credential.birth_certificate;
service-expert returns reply+spec (gateway :8104 up); app serves 200 to an agency admin. LIMITS: AI depends on the
model gateway (fails loudly if down); the AI's proposed spec should be reviewed before Publish (not auto-published);
no diff/versioning of edits; the credential-type "Propose" files pending → a network admin still approves it.

## Service Studio: agency-scoped jurisdiction + governed domain + layout/version — 2026-08-30
Fixes from agency-use feedback: (1) JURISDICTION is no longer an all-cities picker — Service Studio derives the
AGENCY'S OWN jurisdiction (the jurisdiction record whose tenant==the agency, else jurisdiction code==tenant name)
and shows it READ-ONLY ("📍 Nashik — your agency's jurisdiction"); only if the agency has SUB-jurisdictions (e.g.
wards) does it become a dropdown constrained to its jurisdiction + descendants. Nashik can't publish for Ahmedabad.
(2) DOMAIN is now a dropdown of GOVERNED domains (ref.domain via /bridge/catalog?kind=domains), not free text with
hardcoded examples. (3) LAYOUT: the AI panel width looked off because the editor was max-width-capped, leaving a
gap so the panel floated off the right edge — now the editor fills (cards centered at max-width:760, min-width:0)
and the panel pins right; collapses to a 40px strip (flex min-width:0 fix). (4) APP VERSION now visible: config.json
carries `version`; the desktop + citizen-home window titlebars show "App · v<x>". service-studio 0.2.2.

## Service Expert one-shot fix + governed Audience (who-sees-it) — 2026-08-30
(1) SERVICE EXPERT "keep saying continue": the model gateway routes to a reasoning model (Kimi) that emits
chain-of-thought before the JSON; with max_tokens=1800 it truncated mid-thought, `{.*}` found no closed JSON,
and the bridge dumped `content[:800]` — the raw THINKING — as the reply, so the user kept typing "continue".
Fixed in `_bridge_service_expert`: max_tokens→4000, strip `<think>…</think>` (closed AND truncated), extract the
JSON even inside a ```json fence / stray text (greedy largest block), and on parse-failure show a clean actionable
nudge — NEVER the raw reasoning. Now one-shot.
(2) "Who sees it" was mislabeled: it was wired to `entitlement` (residence|property), which is a SCOPING PREDICATE
the gateway uses to match a service's jurisdiction against where the citizen LIVES vs OWNS PROPERTY — not a role.
Split into two governed fields: **Audience** = the GOVERNED role that may discover/apply (network→roles, default
`civic.resident` — yes, resident IS a governed role), validated at `service_offering_publish` (422 on non-governed)
and enforced in citizen discovery (`_bridge_service_search` hides an offering whose audience role the viewer doesn't
hold); and **Qualifies by** = the residence/property predicate, relabeled honestly ("Lives in / Owns property in the
jurisdiction"). offering gains `audience`; `_offering_public` exposes it. Service Studio 0.2.3. No `civic.business`
role exists yet — a business-applicant audience would need a role governed first.

## Org Foundation (Basic ERP) — Slice 1 backbone, built via AirawatDeveloper in Studio — 2026-08-30
Dogfooded the whole governance+Studio spine to stand up an org/ERP backbone that ANY tenant can install.
- Governed a new **`org`** domain + 5 entity schemas (propose as devrick via /bridge/schema-request → approve as
  steward via /v1/schema-requests/decide): `org.org_unit` (dept/team, self-ref parent = variable depth),
  `org.area` (zone/ward/locality/street, self-ref parent), `org.employee`, `org.posting` (employee×unit×area×role),
  `org.goal`. All pass house rules R1–R6. Reproducible via `components/solutions/org-foundation-basic-erp/govern_schemas.py`.
  Schemas persist in the network KV (`_DURABLE=True`), survive restart.
- Studio project `ds:airawatdeveloper:studio/project/org-foundation` (devrick-owned) → open in Studio to ENHANCE.
- `Org Setup` app (`ds:airawatdeveloper:app/org-setup`, v0.1.0): tenant-admin UI with Units tree / Areas tree /
  People / Postings / Goals; reads via /bridge/query, writes via /bridge/save. meta declares `writes:` (authority
  scope) + `roles:[platform.tenant-admin]`. Certified + published.
- Composed → `ds:airawat:solution/org-foundation-basic-erp`; installed into nashik (1 approval → 1 grant covering all
  5 org.* writes). Verified end-to-end write: `component://…org-setup obo user://nashik/nashik-admin`; app shelved on
  the admin desktop; read-back OK.
LIMITS / next slices: (1) `org.posting` records the role assignment as ERP DATA — it does NOT yet emit a
`governance.role_grant`, so a posting does not grant platform RBAC. Next: formally govern `governance.role_grant`
(add `org_unit` scope leg) and project postings → grants (the highest-leverage follow-up). (2) Boundaries use a
tenant-owned `org.area` hierarchy (fully tenant-controlled), NOT the standards-body-gated `network.jurisdiction`;
areas may optionally carry a `jurisdiction` code to anchor to the federated city. (3) Modules Finance / Assets /
Payroll / Leave / Attendance / Expense / Travel / Procurement are NOT built — each is a follow-up slice (governed
schema + intake form + platform.case/task/workflow approval + role-scoped app), added in the same Studio project.
(4) Org Setup has no row-DELETE (add/edit only); left one test unit "Revenue Department" in nashik.

## Org Foundation: postings → LIVE RBAC role-grants — 2026-08-30
Formally governed `governance.role_grant@0.1.0` (record; under the already-governed `governance` domain) — a
BACK-COMPAT closed contract matching every legacy writer `{schema,id,tenant,subject,role,granted_by?,revoked?}`
plus new optional `scope{org_unit,area,jurisdiction?}` + `source` (provenance) + `granted_at`. Verified it passes
strict write-time validation (kernel SCHEMA_VALIDATE=strict) so existing role-grant / dev-provisioning writers
don't break. Reproducible: `components/solutions/org-foundation-basic-erp/govern_role_grant.py`.
PROJECTION: new host bridge `_bridge_posting_apply` (`/bridge/posting-apply`, admin-gated) turns an `org.posting`
into a `governance.role_grant` — subject = the employee's LOGIN sub (`org.employee.citizen` = user://<tenant>/<name>),
role = posting.role, scope = {org_unit, area}, source = posting id, idempotent per posting. Posting active+role+linked
login → grant (revoked:false); posting ended / role cleared / no login → revoke. The Org Setup app (v0.2.0) adds a
"Login user" field on the employee form, calls posting-apply on posting save (toast: live / "pending login"), and shows
an RBAC column (● live / pending login / revoked). Enforcement is the EXISTING `_effective_roles` (identity ∪ non-revoked
role_grant) — verified end-to-end: an employee with NO identity roles gained `urban.ward-officer` purely from the posting
(via `/bridge/user-roles`), and ending the posting revoked it.
LIMITS: (1) enforcement is role-membership only — `scope{org_unit,area,jurisdiction}` is RECORDED on the grant but NOT
yet enforced (scope-aware authz = a further step; today a granted role holds tenant-wide). (2) The employee→login link
is manual (admin types the username); no auto-provisioning of the account. (3) Projection fires when the admin saves a
posting via the app (or calls the bridge); there is no background reconciler if postings are written by another path.

## Org RBAC: scope-aware enforcement (PDP + inbox) — 2026-08-30
Role grants may carry a SCOPE {org_unit, area, jurisdiction} (from an org.posting). A scoped grant holds the role
only WHERE that scope reaches — the grant's node must be an ancestor-or-self of the target's node in the
org-unit / area / jurisdiction hierarchy. Identity roles + UNSCOPED grants hold tenant-wide.
- DESIGN: read-free containment via MATERIALISED ancestor paths. A scoped WRITER stamps a record's scope with
  `<dim>_path` arrays (`_scope_materialize`, walking the org tree with its own read access); the reader-side check
  (`_grant_covers`) is then pure set-membership — so an officer who cannot read the org tree can still be enforced.
- PDP: `_authorize_scope` + `/bridge/authz-check {role, scope}` → {allowed, via:identity|grant, grant_scope}. Any app/
  service calls this to gate a scoped action. Proven: ward-officer grant scoped to zone-3 → ALLOW ward-31 (child) &
  zone-3, DENY zone-5; sanitation-officer (identity) → ALLOW tenant-wide; unheld role → DENY.
- APPLIED (inbox): the inbox now expands EFFECTIVE roles (identity ∪ non-revoked role_grant — so posting-granted
  roles surface work, a real fix from identity-only) and scope-filters role-addressed items: an item with a
  materialised scope shows only to holders whose grant COVERS it; unscoped items stay visible to all holders;
  personal items are never scoped out. Proven: officer scoped to zone-3 sees a Ward-31 task, not a Zone-5 task.
- Governed `platform.inbox_item@0.2.0` = 0.1.0 + optional `scope` object (work location + materialised paths).
  NOTE: bumping a core schema needed a one-time KERNEL restart to refresh its per-schema cached validator
  (`_SCHEMA_VALIDATORS` keys by schema id, not version) — a deploy step, not a code change.
LIMITS: (1) only the INBOX consumes the PDP so far — data reads, task claiming, and other surfaces still enforce
role-MEMBERSHIP only; adopting `/bridge/authz-check` at each is incremental. (2) Scoped WRITERS must materialise
`_path` (call `_scope_materialize`); items with a scope but no `_path` are treated as unscoped (shown), not
fail-closed. (3) platform.task / platform.case don't carry `scope` yet (only inbox_item) — add when workflows stamp
the work location. (4) jurisdiction containment uses the network resolver (cached), org_unit/area walk the registry.

## Org RBAC: employee login auto-provisioning + scope on tasks/cases — 2026-08-30
TASK 1 — auto-provision employee logins. New host bridge `_bridge_employee_provision` (`/bridge/employee-provision`,
admin-gated) mints a real tenant login for a staff member via the identity provisioner (POST /users + internal token,
same path as join-approve). Idempotent — never touches an existing account (won't clobber roles). The account is
created with NO identity roles (roles come from POSTINGS/grants). Org Setup app (v0.3.0) calls it on employee save
(toast: created / exists). FIXED a real latent bug: identity `roles = body.get("roles") or [...]` treated an explicit
`[]` as "use default" → every provisioned staff account became `platform.tenant-admin`; now honours an explicit empty
list (only omitted roles fall back). Verified: a brand-new username can't log in before, can after (roles=[] + posting
grant = its role); provisioning an existing user is a no-op. Identity is Vault-backed so its signing key survived the
restart (existing tokens/JWKS intact).
TASK 2 — scope on tasks/cases. Governed `platform.task@0.3.0` + `platform.case@0.2.0` = prior def + optional `scope`
(needed a one-time kernel validator refresh). The service-workflow now PROPAGATES scope: if a submission declares a
location (`message.scope` {org_unit/area/jurisdiction}), the open writer materialises it once (provider token) and
stamps it on the case + first task + inbox_item; `_advance_service_workflow` carries `case.scope` onto every advanced
task + inbox_item. Added a scope filter to "my tasks" queries (platform.task with no case/assignee filter) mirroring the
inbox — verified: officer scoped to zone-3 sees an "Inspect Ward 31" task, not "Inspect Zone 5".
LIMITS: (1) the end-to-end LIVE workflow submit (citizen submission → scoped case/task/inbox) was not run this session —
each constituent was verified separately (schemas accept scope; writers stamp it [code]; both filters enforce it). A
submission only carries scope if `message.scope` is provided (citizen apps don't send it yet — a form→scope mapping is
the next wire). (2) the task/inbox scope filters only apply in apps whose read allow-list includes that schema
(inbox→platform.inbox_item, crowd-command→platform.task). (3) employee→login is provisioned passwordless (dev identity).

## Form→scope mapping (citizen submission → scoped case) — 2026-08-31
An offering declares `scope_map` {org_unit|area|jurisdiction: <form field key>} (network.service_offering). At submit,
`_provider_fulfil` reads the field off the citizen's form → derives `message.scope` → materialises + stamps the case +
task + inbox (the scope-propagation from the prior slice). Service Studio (v0.2.4): each intake field has a 📍 Location
marker (— / Area / Jurisdiction / Org unit) → sets `scope_map`; round-trips on load. PROVEN LIVE END-TO-END: a citizen
files a Ward-31 grievance (ward-grievance offering, scope_map area←ward, routes to urban.ward-officer) → case scope
materialises to area_path [ward-31, zone-3] → the officer scoped to zone-3 SEES it in their inbox; zone-5 denied.
IMPORTANT FIX: `_grant_covers` is now ITEM-DRIVEN — for each axis the ITEM localises on (its `*_path`), if the grant
constrains that axis the item must be within it; axes the item omits don't exclude it (but it must overlap ≥1
constrained axis). This is why a posting-scoped officer (org_unit+area) correctly sees an area-only grievance. The prior
grant-driven check wrongly hid it (item had no org_unit).
LIMITS: (1) the 📍 location field's VALUE must be a valid area id / jurisdiction code — Service Studio does NOT yet bake
the agency's org.area options into the field (citizen currently needs the code; next: an Area picker populated from the
agency's org.area). (2) area/org_unit scope_map needs the citizen submission to yield a real code; jurisdiction is
governed+public so it's the easiest to wire to a citizen picker. (3) local-dev flakiness noted: chaining separate curl
invocations with a shared cookie jar intermittently lost the app_host session — use one process/jar per session.

## Area picker baked into Service Studio — 2026-08-31
The 📍 Location field is now a real PICKER, not a free-text code. Catalog bridge gains kind=areas / kind=org_units
(reads the agency's own org.area / org.org_unit with the admin session token). Service Studio loads AREAS/UNITS on boot
and, when a field is 📍-marked (area | org_unit | jurisdiction), BAKES the options into that field at publish:
request_schema[field] = {type:string, enum:[ids/codes], x-enum-labels:{id:name}} (jurisdiction uses the governed CITIES).
Jan Seva renders any enum field as a labelled <select>. Proven live: agency re-publishes ward-grievance → ward field
carries enum [ward-31, zone-3] + labels; a citizen PICKS Ward 31 → case scope area_path [ward-31, zone-3] → the zone-3
officer sees it. Service Studio 0.2.5, Jan Seva 0.1.9.
LIMIT: options are a SNAPSHOT baked at publish time — if the agency adds/renames areas later, the offering must be
re-published to refresh the picker (no live lookup at render). Area labels come from org.area.name at publish.

## First ERP module: Leave & Attendance — 2026-08-31
Governed `hr` domain + `hr.leave_request` + `hr.attendance`. NEW pattern vs the civic grievance flow: internal +
PERSON-routed (to the employee's reporting MANAGER, resolved from org.employee.manager), not role-routed.
- SELF-SERVICE writes: `_bridge_leave_apply` / `_bridge_leave_decide` / `_bridge_attendance_mark` — NOT admin-gated
  (unlike /bridge/save); any authenticated staff acts on their own records, authorised by the HR-Desk component's
  grant (ADR-0052: component://hr-desk obo the employee). leave-apply resolves the manager + notifies their inbox;
  leave-decide verifies the caller IS the manager, sets status, notifies the applicant.
- `HR Desk` app (ds:airawatdeveloper:app/hr-desk v0.1.0): Leave (apply + my requests) · Attendance (check in/out +
  history) · Approvals (a manager's team queue). Installed into nashik via `/v1/grants/issue` (single-component
  install) + shelved. PROVEN LIVE: Asha applies → Sanjay (manager) approves → Asha sees approved + checks in.
- Also FIXED a blocking Org Setup bug the user hit: the Add buttons (Units/Areas/People/Postings/Goals) were dead —
  `onclick="addRow("units")"` had nested double quotes that broke the attribute; single-quoted it. org-setup v0.3.1.
LIMITS: (1) manager-scoping of the Approvals queue is APP-enforced (query filter manager_login==me) + a server check
in leave-decide — the registry doesn't per-record-restrict who can read a leave (the HR-Desk read grant covers the
schema tenant-wide; the app filters). (2) no leave BALANCE tracking / accrual; days is a simple date diff. (3) HR
Desk not yet added to the Org Foundation solution graph (installed standalone via grants/issue) — fold it in on the
next compose. (4) attendance has no geofence/scope; one record per employee-day.

## Classification layer: Job Level × Career Stream × Position — 2026-08-31
Chose the fuller HR model (position SLOT, not just attributes) + a coming unified Policy engine. Governed
`hr.job_level` (grade/band; `rank` orders seniority so policy can say ">= N"), `hr.career_stream` (job family),
`org.position` (a job SLOT = stream × level × org_unit + `eligible_roles[]` + `reports_to`). Bumped `org.posting@0.2.0`
with an optional `position` ref (kernel validator refresh). Org Setup (v0.4.0) gains Levels / Streams / Positions
sections; the posting form has a Position picker that prefills the unit + constrains the role dropdown to the
position's eligible_roles + prefills designation. Folded via the auto-bumping compose (solution 0.3.0) + reinstall
(org-setup now granted 8 schemas). PROVEN: level L4 + Sanitation stream + "Ward Officer" position (eligible for
urban.ward-officer) + a posting linked to it all persist.
NEXT (per the plan): unified `org.policy` engine + Policy Console (leave/travel/expense, applies_to level≥/stream/
role/unit) → leave balance/accrual from policy → goal templates keyed by (level × role) instantiated on posting.
LIMITS: role∈eligible_roles is UI-constrained only (not enforced at posting-apply); position doesn't yet drive
employee.level/stream derivation or goal-template instantiation (that lands with the policy/goals slices).
Also improved: `project-compose` now AUTO-BUMPS the solution minor version on re-compose (store is immutable).

## Unified Policy engine + Policy Console — 2026-08-31
Governed `org.policy` (one schema for ALL policy domains): {domain, applies_to{min_rank,max_rank,stream,role,org_unit},
rules(domain-specific), priority, status}. `_bridge_policy_resolve` = the ENGINE: given (domain, employee) it resolves
the employee's CLASSIFICATION context (seniority rank via posting→position→level, stream, role, unit) and returns the
active policies whose applies_to matches, sorted MOST-SPECIFIC first. Consuming modules (HR Desk leave, Travel, Expense)
call it for entitlements/limits — "manage all policy in one place". `Policy Console` app v0.1.0: CRUD by domain
(Leave/Travel/Expense/Attendance) with applies_to pickers (min level / stream / role / unit) + domain-specific rule
forms + a "Resolve for employee" preview. Folded into Org Foundation solution (recompose auto-bumped); installed.
PROVEN: L4-posted employee resolves earned-leave 30 (L4+ policy first) then 15 (all-staff); travel L4+ matches;
an employee with no position resolves only the all-staff policy (rank=None). LIMITS: (1) policy-resolve reads the org
tree with an ELEVATED tenant-admin token (an authz-style computation) — prod wants a dedicated policy-reader principal,
not tenant-admin. (2) role context = the employee's posting role(s) only (not their full effective role_grants). (3)
rules payload is app-shaped per domain (leave/travel/expense/attendance have typed forms; others fall back to raw JSON).
NEXT: HR Desk consumes policy-resolve for leave BALANCE/accrual (entitlement − taken); goal templates keyed by level×role.

## Leave balance/accrual wired into HR Desk (consumes the policy engine) — 2026-08-31
Refactored the policy engine into a shared `_policy_resolve(tenant, sub, domain, employee_id)` + `_leave_balance(...)`
helper. HR Desk (v0.2.0) Leave tab now: calls policy-resolve(leave) → shows a BALANCES table per type (entitlement /
accrued / taken / pending / available), annotates the type dropdown ("— N left"), and blocks over-application. ACCRUAL:
if the leave policy sets accrual_per_month, accrued = min(annual, accrual_per_month × month-of-year); else full annual.
ENFORCED SERVER-SIDE in `_bridge_leave_apply` (not just the UI) — a direct API call can't overspend. Untyped/unpaid
leave (no policy) = uncapped. Also hardened `policy-resolve`: non-admins may only resolve THEMSELVES (the employee arg
is ignored unless caller is admin — Policy Console preview still resolves anyone). PROVEN: L4 earned=30; apply 5→pending
(25 left); apply 31→BLOCKED with the arithmetic; unpaid→allowed.
LIMITS: (1) balance counts THIS calendar year only; carry-forward (carry_forward_max) is stored on the policy but NOT
yet added to accrued (needs prior-year close-out). (2) taken/pending summed from hr.leave_request via elevated read.
(3) no leave-year config (assumes Jan–Dec). (4) accrual is proration-by-month, not date-precise.

## Finance core — double-entry-ready ledger + budgets + settlement seam — 2026-08-31
Chose "thin Finance core first, then Expense, then Travel" — but built the ledger DOUBLE-ENTRY-READY per user guidance
(they'll need full double-entry eventually). Governed `finance.account` (chart of accounts: type asset/liability/equity/
revenue/expense + normal balance), `finance.transaction` (a JOURNAL ENTRY with balanced debit/credit `lines[]`;
status committed|posted|void; convenience `amount`/`direction`/`budget`/`source` tags), `finance.budget` (allocation on
an expense account; available = allocated − committed − spent). `_bridge_finance_post` = THE SETTLEMENT SEAM (component-
attributed): mode (a) explicit `lines[]` (raw GL, must balance) or (b) CONVENIENCE {direction,amount,budget|account,
contra_account} → auto-builds the balanced 2-line entry; validates Σdebit=Σcredit; checks + rolls budget committed/spent
(blocks overspend unless allow_overspend). `Finance Console` app v0.1.0: Accounts (chart + seed-defaults) / Budgets
(allocated/committed/spent/available bars) / Journal (entries with visible Dr/Cr lines + New-entry). Folded into the
Org Foundation solution + installed. PROVEN: ₹30k travel posts a balanced Dr Travel/Cr Payables entry + commits to the
budget (available 100k→70k); ₹90k over budget BLOCKED; an unbalanced explicit entry BLOCKED.
EXTENDS TO FULL DOUBLE-ENTRY with no rework: entries already ARE balanced lines over a chart of accounts — full DE just
adds trial-balance/P&L reports + multi-line UI + period close. NEXT: Expense module (claim→policy limit + budget check→
approve→finance-post committed; payment→posted), then Travel (same seam). LIMITS: (1) committed→posted transition (pay a
committed entry) not yet wired (needs a 'pay'/settle action moving committed→spent). (2) no fiscal-period close / trial
balance report yet. (3) finance-post reads/writes with the caller COMPONENT grant (Console has it); Expense/Travel will
each need finance.transaction+finance.budget write grants. (4) single currency assumed.

## Expense module (approval + policy limit + double-entry settlement) + project tag — 2026-08-31
Govern `hr.expense_claim` (v0.2.0 +`project`). Bridges `_bridge_expense_apply` (employee→manager, like leave) +
`_bridge_expense_decide`: on APPROVE it (1) enforces the APPROVER's expense `approval_limit` policy (policy-resolve for
the manager, most-specific), (2) SETTLES via the shared `_finance_post` helper — a committed double-entry expenditure
(Dr expense account / Cr Payables) against the chosen budget, budget-availability enforced by the seam. Refactored the
settlement seam into `_finance_post(kwrite,kget,tenant,sub,body)` (used by /bridge/finance-post AND expense-decide);
`_first_account(tenant,type)` finds the Payables contra. HR Desk v0.3.0: Expenses tab (claim + my claims) + expense
approvals in Approvals (budget picker); meta writes now include finance.transaction+finance.budget so the settlement
posts under the hr-desk grant. PROVEN: ₹30k travel claim → approved → Dr Travel/Cr Payables balanced (project P-ROADS),
budget committed 100k→70k; ₹80k over the L4 approval limit → BLOCKED.
PROJECT TAG: added optional `project` to finance.transaction@0.2.0 + hr.expense_claim@0.2.0 NOW (fresh schemas) so
outlays carry org_unit + project from day one — no retrofit for the coming Project layer.
NEXT — PROJECT LAYER (per user): govern `org.project` {code,name,org_unit(owner),sponsor,dates,status,outputs[],
outcomes[]}; org.allocation (employee↔project %, for salary apportionment); add `project` to finance.budget (budget per
unit×project×account); a Project Console; rollups = revenue/expenditure BY project and BY unit×project from
finance.transaction (which already carries both). Plan (budget alloc + planned outputs) vs Actuals (posted txns) →
variance. "Project links outlays→outputs→outcomes." Then TRAVEL module (same expense pattern via finance-post).
LIMITS: expense committed→posted (pay) not wired; approver escalation (if over limit, route higher) not built —
currently just blocks; no itemised expense lines (single amount).

## Componentize engines S1: host engine-dispatch + hr-workflows engine — 2026-08-31
Addressing the valid concern that server-side LOGIC was living in the reference host (not Studio-authorable). Built the
mechanism: `ENGINE_VERBS` maps verbs → a certified engine component; the host `_dispatch_engine(verb)` loads that
engine's run.py (`_load_engine`, cached) and calls `HANDLERS[verb](ctx)`. `ctx` = component-attributed registry I/O
(kwrite/kfind/kget with X-Component-Id=the ENGINE) + shared host helpers (policy_resolve / finance_post / first_account
/ leave_balance) so engines compose. Migrated leave/attendance/expense apply+decide into
`ds:airawatdeveloper:engine/hr-workflows` (kind:engine, run.py HANDLERS); DELETED the 5 host bridge methods. The engine
is a SOLUTION MEMBER (Studio-editable, versioned) and HOLDS the write grants (apps=screens, engine=logic). PROVEN: all
HR flows still work; leave record `wrote_by: component://…engine/hr-workflows@0.1.0 obo user://nashik/asha` (was the
app before). Studio loop for logic: edit engine/hr-workflows/run.py → Publish → Compose → upgrade.
GOING FORWARD: build every new solution's server logic as engine components (not host bridges).
LIMITS/next: (1) engine run.py is loaded from its dir + executed IN the host process (not broker-sandboxed) and NOT
digest-verified against the cert yet — same trust as host code; proper isolation = the ADR-0030 broker + ADR-0050
execution engine (unbuilt). (2) `_ENGINE_MODS` caches the module per host process — a Studio edit+republish needs a host
restart (or a cache-bust on reload) to take effect. (3) STILL host methods (migrate next): policy_resolve, finance_post,
first_account, leave_balance (shared engines), posting-apply, authz-check, employee-provision, the service-workflow
interpreter. (4) hr-desk meta still lists finance writes it no longer uses (harmless; trim later).

## Componentize engines S2: policy/finance/org-rbac engines + engine composition — 2026-08-31
Migrated the remaining SHARED logic out of the host into certified engine components. Host mechanism upgraded:
`_engine_ctx(eng_id,claims,body)` builds a ctx attributed component://<eng> obo user (gated by THAT engine's OWN
grants) + `ctx["call"](engine_id, verb, payload)` so engines COMPOSE; `_invoke_engine` runs any engine's handler.
New engines (all solution members, Studio-editable): `policy-engine` (policy-resolve — reads org tree via its OWN read
grants, NO elevated tenant-admin token anymore), `finance-engine` (finance-post — the double-entry seam; owns contra
lookup), `org-rbac-engine` (posting-apply → governance.role_grant). Refactored `hr-workflows` (v0.2.0) to DELEGATE:
expense-decide → ctx.call(policy-engine) for the limit + ctx.call(finance-engine) to settle; leave balance → ctx.call(
policy-engine); dropped its finance/org-tree grants. DELETED 7 host methods (_policy_resolve, _finance_post,
_first_account, _leave_balance, _bridge_policy_resolve, _bridge_finance_post, _bridge_posting_apply). PROVEN: all flows
work; expense ledger entry `wrote_by: component://…engine/finance-engine obo user` (composed hr→policy→finance). Grants
land per-engine (finance-engine=ledger writes, org-rbac-engine=role_grant, policy-engine=read-only, hr-workflows=HR only).
STILL host (deliberately, with reasons): authz-check (scope PDP — its `_effective_grants`/`_grant_covers`/`_scope_*`
helpers are module-level + shared with the host inbox/query enforcement); employee-provision (needs the identity
provisioner SECRET, not a grant); the service-workflow interpreter (`_provider_fulfil`/`_advance_service_workflow` — woven
into the ADR-0067 gateway bridges; a bigger lift). GAPS unchanged: engines run in-host (not broker-sandboxed) + not
digest-verified vs cert; `_ENGINE_MODS` cache needs a host restart after a Studio edit+republish.

## Componentize engines S3: authz-check + employee-provision → org-rbac-engine — 2026-08-31
The last two migratable host exceptions are now the org-rbac-engine's (v0.2.0, 3 handlers). authz-check (the scope-aware
PDP) + its containment IP moved into the engine; `grant_covers`/`scope_has_paths` are module-level there so the HOST
inbox/task filter IMPORTS them as a library (single source of truth; fallback pass-through if the engine is absent —
safe, because without it no scopes exist). employee-provision's LOGIC moved to the engine while the identity provisioner
SECRET stays host-side, exposed only as the `ctx["provision_login"]` capability (host holds the key, engine holds the
logic + admin gate) — the pattern for any secret-touching engine. Added `ctx["network_url"]`. DELETED host methods:
_bridge_authz_check, _bridge_employee_provision, _authorize_scope, _grant_covers, _scope_has_paths. KEPT (write-time,
used by the `_provider_fulfil` gateway writer): _scope_materialize + _node_ancestors + _juris_ancestors; KEPT (platform
role resolution): _effective_grants, _effective_roles. PROVEN: authz-check allowed on the granted area / denied off it
(engine read role_grant + materialised the target through the org tree via its OWN grants); employee-provision provisions
+ refuses a non-admin; inbox scope filter unbroken.
DELIBERATELY host (correct classification, NOT a gap): the service-workflow interpreter (_provider_fulfil ~700 lines +
_advance_service_workflow) — ADR-0067 federation RUNTIME (cross-tenant provider-admin token minting, credential
verification, VC issuance), generic platform-gateway plumbing used by any service across any solution, same category as
the kernel/scheduler. Migrating it would move a privileged cross-tenant secret surface into certified code — opposite of
the security goal. So all SOLUTION logic is now Studio-authored engines; only platform RUNTIME (kernel, gateway,
scheduler, identity) remains host, as it should.

## Project layer (results-contract lifecycle) — 2026-08-31
Built the Project layer via Studio into the Org Foundation solution: `project` domain + 5 schemas (project.project,
project.proposal[versioned baseline embedding outcomes/outputs/milestones/deliverables/outlay], project.review,
project.evaluation, project.allocation) + finance.budget@0.2.0 (+project). `project-engine` (certified, Studio-editable)
has the lifecycle: proposal-submit → proposal-decide (approve ⇒ governance.decision [a decided change-request, ADR-0056]
+ project active + budget committed from outlay) → project-rollup (Plan vs Actual, by project + by owning org_unit) →
project-review (RAG vs plan) → project-evaluate (outcomes/outputs/VfM + recommendation) → project-adjust (re-baseline,
new version supersedes on re-approval). Project Console app = Portfolio/rollup · Propose (results-chain authoring) ·
Approvals · detail drawer (Review/Evaluate/Adjust). PROVEN end-to-end on REAL data: actuals = posted finance.transactions
tagged `project` (finance-engine); all writes wrote_by component://…engine/project-engine.
HONEST LIMITS:
- ACTUALS = posted transactions only. Salary/travel/expense/asset apportionment to a project shows up in `spent` ONLY
  when a real transaction is posted tagged with that `project` (expense/finance already carry it). project.allocation
  (employee→project %) is captured but NOT yet auto-apportioned into `spent` (no payroll-cost × allocation posting job);
  labour-from-allocation is a planned/forecast figure, not an actual. Wire a payroll→project apportionment posting next.
- ROLLUP `planned_to_date` is NOT time-phased — it compares spend against the FULL allocation, not a schedule-to-date
  curve, so the RAG status is coarse (overspend / >80% used) rather than earned-value.
- Cost is attributed at PROJECT level only (finance links to project). Output-level cost (outlay `output` refs exist in
  the baseline but transactions don't carry an output ref) is not rolled up. Split outlay into a linked schema for that.
- Lifecycle transitions are guarded lightly (review/evaluate require an approved baseline; no full state-machine gate,
  e.g. you can review a project already recommended-close). project.allocation has no console screen yet.
- One stale test project (DRAIN-26) remains in the nashik dev tenant from a first run that failed on the governance.
  decision `task`-required constraint (since fixed); /bridge/retract isn't exposed to clean it. Harmless dev data.

## Payroll → project apportionment — 2026-08-31
Labour cost now flows into project actuals (closes the prior "salaries not apportioned" gap). `hr.compensation`
(employee monthly_cost, effective-dated) = the REAL cost source. `payroll-engine` (Studio-editable, composes
finance-engine): payroll-preview + payroll-apportion — for a period, each active project.allocation → a project-tagged
salary finance.transaction (monthly_cost × percent), idempotent per (allocation, period) via a deterministic txn id
(finance-engine 0.2.0 accepts optional `id`). NO fabrication: allocations without compensation/budget are reported
skipped. UI: Project Console "Team" (allocations via project-engine 0.3.0 allocation-set/list); Finance Console 0.2.0
"Payroll" tab (set compensation + run). PROVEN e2e on nashik (Asha @50% × ₹120k → ₹60k on DR-27; re-run posts 0; salary
txn wrote_by finance-engine, tagged project + source_kind=payroll).
REMAINING LIMITS:
- The payroll run is MANUAL per period (a button). No scheduled monthly cron yet — wire platform.schedule → payroll-
  apportion for automatic month-end runs.
- Apportionment is FLAT monthly_cost × allocation%. It does NOT prorate for mid-month start/end, leave without pay, or
  attendance; effective-dating picks the latest comp row on/before the period but within-month changes aren't split.
- Still project-level, not output-level (the salary txn carries `project`, not an output ref) and NOT time-phased.
- Only LABOUR is apportioned via allocations. Travel/expense reach a project only when a claim is filed with that
  `project` tag (already supported); asset depreciation apportionment is not modelled.
- Compensation is a single monthly_cost (cost-to-org), not a structured pay package (basic/allowances/employer contrib).

## Scheduled monthly payroll run — 2026-08-31
The payroll apportionment now runs automatically. payroll-engine v0.3.0 has a HEADLESS main() (broker /v1/query+/v1/write
under its run-token) that the platform scheduler fires via the app-host launcher (confined L1, certificate VERIFIED). A
platform.schedule (cron `0 2 28 * *`, tenant nashik) drives it; next run 2026-09-28. main() defaults PAYROLL_PERIOD to
the current month. PROVEN: scheduler /run posted the 2026-09 apportionment headless (₹60k → DR-27, wrote_by
component://payroll-engine). Two install requirements captured: (1) the engine needs a `reads:` meta field so the
run-token gets read grants (interactive user-token path used required_schemas; a headless cron has no user token); (2)
the scheduler finds installs via kernel `/v1/components`, which the SOLUTION install does NOT populate with a run-token —
you must also POST `/v1/components/install {component_id}` per tenant to mint it.
REMAINING LIMITS:
- The platform.schedule was created for nashik by hand (kernel write). No UI yet to enable/disable the monthly run per
  tenant, and no auto-creation of the schedule on solution install — a new tenant must have the schedule + the per-
  component install registered. Add a "Payroll schedule" toggle to the Finance Console Payroll tab + create-on-install.
- HEADLESS composition imports finance-engine's run.py from the sibling dir (works in local-dev subprocess). In a
  containerized runtime (RUNTIME_MANAGER_URL set) the payroll container would need finance-engine bundled, OR a headless
  finance broker verb — otherwise the in-process ctx.call import fails. Interactive path is unaffected.
- Headless salary txns are attributed to payroll-engine (its run-token), NOT finance-engine as in the interactive path —
  two attribution models for the same logical write, by path. Acceptable (payroll IS the batch writer) but noted.
- Proration/attendance still not applied (flat monthly_cost × %); cron is fixed 28th (no last-day-of-month).

## Self-serve payroll schedule toggle — 2026-08-31
The monthly run is now toggled from the UI. Finance Console v0.3.0 "Payroll" tab shows an "Automatic monthly run" card
(on/off + day-of-month 1–28 + next/last run) → `payroll-schedule` verb (payroll-engine v0.4.0: get/set the
platform.schedule, admin-gated). Enabling also ensures the scheduler's run-token via a new host capability
`ctx["ensure_install"]` (registers the per-tenant install-as-grant; mirrors provision_login) — so enabling is turnkey,
no manual /v1/components/install. PROVEN e2e: get → off → on(day25) → scheduler cron `0 2 25 * *`; non-admin refused.
REMAINING LIMITS:
- Day-of-month capped at 1–28 (5-field cron can't express "last day of month"); time fixed 02:00 UTC (not tenant-local).
- The schedule/toggle is per-tenant but NOT auto-created on solution install — a tenant admin must open the Payroll tab
  and turn it on once (which then creates the schedule + install). No bulk/default-on across tenants.
- ensure_install uses the clicking admin's session token for the control-plane call — fine (they're a tenant admin), but
  it's not a dedicated service principal; a headless/no-session caller could not enable a schedule this way.

## Payroll proration for mid-month joiners/leavers — 2026-08-31
payroll-engine v0.5.0: apportioned cost = monthly_cost × percent × (active_days_in_month / days_in_month), where active
days are the overlap of the allocation [from_date, to_date] with the run month (day granularity, calendar.monthrange for
month length). A mid-month JOINER (from_date inside the month) and LEAVER (to_date inside the month) are charged pro-rata;
a whole-month allocation gets factor 1.0. The posted memo carries "N/Md pro-rata"; preview + rollup reflect it. PROVEN:
Oct joiner @100% ₹124k → ₹64,000 (16/31 days).
REMAINING LIMITS:
- Proration is by CALENDAR days only — it does NOT account for attendance, leave-without-pay, or working-day calendars
  (a person on approved LWP for half the month is still charged the full month unless their allocation dates change).
- Comp is still the single latest effective row for the month — if monthly_cost CHANGES mid-month, the whole month uses
  the latest rate (no within-month comp split); pair with allocation dates for finer control.
- Idempotency is per (allocation, period) via a fixed txn id: if an allocation's dates change AFTER the month was
  already apportioned, a re-run will NOT re-post/adjust the existing entry (no correction/reversal path yet).

## Inbox ↔ ERP integration — 2026-08-31
ERP approvals now surface AND are actioned in the universal Inbox (ADR-0048), and users file leave/expense from it.
Mechanism: platform.inbox_item.actions (existing array[string]) carries each action as a JSON string {label,verb,args,
style,params?} — no bump of the shared core schema. Inbox app v0.2.0 renders JSON actions as buttons that call /bridge/
<verb> (a `ref` param fills selects from a schema, e.g. expense→finance.budget). hr-workflows v0.3.0 attaches approve/
reject to leave+expense manager items; project-engine v0.4.0 routes proposal approvals to the sponsor/admin + notifies on
decide (holds a platform.inbox_item grant). Inbox "＋ New request" files leave/expense (leave-apply/expense-apply).
PROVEN: project proposal→inbox→approve-in-place→active+budget+notify; leave filed from inbox→manager item w/ actions.
LIMITS:
- "＋ New request" only offers Leave + Expense (hardcoded REQS in the inbox app) — not project proposals, attendance, or
  a governed request catalog; extend REQS to add more. It's ERP-specific UI living in the shared Inbox app.
- Project proposals with no sponsor login are role-addressed to platform.tenant-admin (every admin sees them; the scope
  filter still applies). No per-approver routing/round-robin.
- Expense in-inbox approve needs the manager to pick a budget (a `ref` param) — fine, but there's no default/last-used.
- Notifications are inbox items only (no email/push). Acting in the inbox calls the domain verb, which re-checks
  authority (e.g. only the manager may decide) — so a wrongly-addressed item's action will 403, by design.

## Tax Gap Finder — slice 1 (config-driven candidate spine) — 2026-08-31
Greenfield property-tax enforcement solution ds:airawat:solution/tax-gap-finder (old KMC schemas were wiped in the reset).
DONE: tax+util domains + 6 schemas (tax.match_policy is the config backbone) + tax-gap-engine v0.2.0 (fuzzy record-linkage
mobile/name/address weighted + point-in-polygon spatial join + geometric hygiene + geocode banding + footprint centroid-
join + change signals → scored tax.candidate + governance.recommendation) + Tax Config Console (Thresholds/Match tester/
Scan/Candidates). Every threshold + weight is tenant-editable via tax.match_policy — nothing hardcoded. PROVEN on a
labelled fixture (P-B conf 0.9, 3 signals). NO fabrication — gap-scan reads real records only.
NOT BUILT YET (next slices):
- INGEST DRIVERS: geocode-ledger (address_string → lat/long via a real geocoder, fail-loud on miss) + ingest-utilities
  (lat/long-or-geocode). Until these exist, tax.assessment/util.connection must be loaded externally.
- CHANGE-DETECT engine on REAL AlphaEarth embeddings (currently tax.change_signal is consumed but not produced; wire to
  geo.landcover / the landcover-dw GEE runtime for embedding-delta scoring).
- FIELD CAMPAIGN app: campaign.campaign + campaign.assignment schemas + the officer assignment→Inbox→ground-truth→
  governance.decision→reassess loop (reuses the actionable Inbox + scope-aware RBAC + decision spine).
LIMITS of the spine as built:
- gap-scan is interactive (admin-triggered); a scheduled/large-city run needs the headless pattern (reads grant already
  declared) + batching (it loads all parcels/records into memory — fine for a ward, not a metro in one shot).
- under_assessed signal is declared + weighted but NOT computed yet (needs a rate card: built_area × ready-reckoner).
- estimated_revenue on a candidate is null (needs the rate card too).
- geocode band/geometry-hygiene are computed per record but not yet persisted back onto tax.assessment/util.connection
  (the join is recomputed each scan); persist on ingest once the drivers exist.

## Tax Gap Finder — slices 2-4 (ingest drivers, AlphaEarth change-detect, field campaign) — 2026-08-31
INGEST: geocode-ledger + ingest-utilities drivers (real Nominatim geocoding via broker egress, CSV-or-existing, fail-loud
— proven geocoding a real Nashik address). CHANGE-DETECT: change-detect-alphaearth driver (real AlphaEarth embedding
cosine-distance per parcel → tax.change_signal; earth-observation GEE runtime; fail-loud, no synthetic). FIELD CAMPAIGN:
campaign domain + 2 schemas + campaign-engine (create/assign/verify-submit/progress) + Tax Gap Campaign app; the officer
verifies IN their Inbox (reuses the actionable-inbox "Record verification" action) → governance.decision → candidate
verified/dismissed. PROVEN full loop on nashik.
REMAINING LIMITS:
- geocode_confidence from Nominatim `importance` came back 0.0 in testing — the confidence→band mapping needs calibration
  (use place_rank or a match-quality heuristic). The POINT is correct (what the spatial join uses); only the band is off.
- change-detect-alphaearth needs the earth-observation runtime (earthengine-api) + a GEE service-account key + geo.parcel
  cadastre loaded to produce REAL signals; not runnable in the bare local dev env (fails loud, as designed).
- No CSV UPLOAD UI yet — LEDGER_FILE_ID/UTIL_FILE_ID expect a platform.component_asset file_id (the Settings upload flow);
  a "load ledger" button in the Tax Config Console would make data-loading self-serve.
- verify-submit on `confirmed` sets candidate=verified + estimated_revenue=assessed_value but does NOT yet auto-create a
  new tax.assessment / reassessment (the "→ reassess" step). Wire it to raise a draft assessment for the revenue office.
- Campaign assignment is 1 candidate → 1 officer (manual). No bulk-assign, route optimization, or officer workload view.
- No map view in the Tax Gap Campaign app (candidates are listed, not plotted); wire viz.layer + City Scan for the map.

## Studio project membership gotcha — 2026-08-31
studio.project.members[].layer is an enum (network|platform|domain|intelligence|governance|interaction). Tagging a
driver member layer "observation" 422s the WHOLE /bridge/save (rolls back → project silently keeps its last valid member
list). Drivers→domain, engines→intelligence, apps→interaction. Orchestration scripts MUST check the save return — a 422
there is easy to miss, so components can be published+installed yet missing from the Studio project/solution graph. Fixed
tax-gap-finder (was showing 2 of 7 members).

## Scheduler asset-injection was fail-closed (missing IDENTITY_URL) — platform-wide
The `airawat-scheduler` container ran with no `IDENTITY_URL` env, so `scheduler.py`'s
`_svc_token()` defaulted to `http://localhost:8093` and failed. Because the registry
read fails CLOSED under zero-trust (P0), `_component_assets()` swallowed the error and
returned nothing — so **no scheduler-triggered driver run ever received its uploaded
data-file assets** (e.g. `OSM_PBF_FILE_ID`). Symptom: osm-facilities/roads reported
"FATAL: OSM_PBF_FILE_ID not set" even though the `platform.component_asset` record was
correctly bound. The City-Baseline path masked this because it runs through app-host
(correct env), not the scheduler. Fix: added `IDENTITY_URL: http://identity:8093` to the
scheduler service in docker-compose. Watch for the same missing-env fail-closed pattern
on any service that authenticates to the registry/identity by localhost default.

## Large OSM PBF (regional/zone extract) 504s the osmium drivers
pyosmium `apply_file(locations=True)` over a 300MB–1.5GB PBF builds a full node-location
index and blows the 180s host-subprocess cap → HTTP 504 (seen on new-delhi's ~1GB
northern-zone auto-download). Fix: osm-facilities/roads/drainage now `osmium extract -b
<aoi-bbox> -s complete_ways` to clip the PBF to the AOI before the expensive pass, guarded
on the `osmium` CLI being present (added to reference image 0.1.1) and file >150MB. City
Setup's OSM URL picker can still hand a driver a coarse zone file; the clip makes that safe.

## Registry resolve fetched the WHOLE table on every query (no SQL LIMIT) — big-layer perf cliff
`pg_store.resolve_as_of` built a WHERE (schema + tenant id-prefix + filters) but ran `cur.fetchall()`
with NO `LIMIT` and NO keyset — it loaded every matching row from Postgres, then sliced `[:limit]` in
Python. The `cursor` arg was never used in the query, so pagination re-fetched the same window (effectively
broken). For a metro road layer (new-delhi `geo.osm_feature` = 100k+ line features) every query loaded all
100k rows → 9s+ and HTTP 502 above ~5k (payload). City Scan's Drainage/roads overlays (`q()` at limit 50000)
therefore 502'd and hung the tab. Fix (hot-patched live, backward-compatible): push `LIMIT (limit+1)` +
keyset `id > cursor` into the SQL; wire `cursor` through `/v1/registry/resolve`; app-host `/bridge/query`
forwards `cursor`/`next_cursor`; City Scan loads big vector layers page-by-page (progressive render, 40k cap).
Roads page now returns in ~0.8s with real disjoint keyset pages. **Hot-patched, NOT yet baked into the kernel
image** — lost on a kernel image rebuild; fold pg_store.py/store.py/api/app.py + app_host.py + the city-scan
bundle (and its re-cert) into the images on the next rebuild.

## City Scan Drainage froze the tab — a hydro polygon with 65k+ vertices (deck.gl tessellation)
The real cause of the Drainage hang was NOT fetch volume (new-delhi geo.hydro_feature = 28 features) but
GEOMETRY COMPLEXITY: hydro-merit writes streams as Polygons, and one carried ~65,855 coordinates. deck.gl's
GeoJsonLayer earcut-tessellates each polygon on the MAIN THREAD, so one 65k-vertex ring froze the browser for
seconds. First attempt (0.3.3) uniform-stride-decimated the rings — WRONG: it collapsed thin ribbon-polygons into big
blobs ("drainage lines became area shapes"). Correct fix (0.3.4): render drainage as LINES via a PathLayer over
the geometry rings (`hydroPaths()`), never a filled polygon — no earcut tessellation (no freeze) and the channel
shape stays true. RESOLUTION: the FIX is purely in the client render (City Scan 0.3.4 draws geo.hydro_feature as PathLayer LINES,
not filled polygons — no earcut freeze). The DATA stays as the raster stream-mask POLYGONS, which are connected +
complete. A driver "centreline" experiment (hydro-merit 0.2.0, scipy Voronoi medial axis) was tried and REVERTED
(0.2.1): on blocky 90 m MERIT raster it fragmented streams into disconnected, lossy segments — worse than the
polygons. So: keep polygons, render as lines. GOTCHA discovered: GEE drivers run in the EO runtime container that
BIND-MOUNTS the HOST dir `/home/ec2-user/airawatos/rt-components` — NOT `/app/components` inside the app-host/
scheduler containers; update rt-components on the host or the change is ignored. Migrating a tenant = retract old
geo.hydro_feature first, then re-run (else features double up).

## ADR-0073 M1 — Air Intelligence PM2.5 foundations (2026-09-05)
- **PM2.5 label column is null (0 labelled cells).** `pm25-features` joins a `pm25_obs` label from
  `air.sensor_reading`, but new-delhi has NO CPCB ground truth ingested (needs a real Delhi CPCB/CAAQMS key).
  The feature matrix is therefore **inference-ready but not yet trainable** — model milestones (M4+) are blocked
  on real Delhi station data. No fabricated labels.
- **Feature matrix is NDJSON, not Parquet.** The runtime that runs engines (runtime-manager in-process) has no
  `pyarrow`/`duckdb`. `pm25-features` already branches on `OUT_FORMAT=parquet` and falls back to NDJSON; M3 must
  stand up a feature runtime image WITH pyarrow to emit real Parquet.
- **cams-regional / era5-pblh use Open-Meteo, not GEE.** Open-Meteo's air-quality API is CAMS global (~40 km)
  and its weather API serves ECMWF `boundary_layer_height` — same real sources, keyless, no GEE quota. Values are
  the coarse regional field (spatially smooth over a city AOI by design; `native_resolution_km` carried). This is
  regional CONTEXT, not a local measurement — AOD/CAMS ≠ local PM2.5 (ADR-0073 §2).
- **cell.cams / cell.boundary_layer are a single hour (nowcast snapshot).** id = `ds:<tenant>:cell/<subject>/<h3>`
  (no hour in the id), so a re-run supersedes the latest hour rather than accumulating a history. Historical
  hourly backfill (needed for training/lags) is M3.
- **No viz.layer yet for cell.cams / cell.boundary_layer.** They are feature INPUTS, not the presented deliverable
  (the map layer is the future `air.pm25_estimate`, M5). They won't render in City Scan until a viz.layer exists.
- **BAKE-LIST (hot-patch drift):** `cams-regional`, `era5-pblh`, `pm25-features` were deployed to the HOST
  `rt-components` (durable, bind-mounted → runtime executes from here) and docker-cp'd into the scheduler's baked
  `/app/components` (ephemeral — lost on recreate, but the prod run path derives kind from the install record, not
  the baked meta, so this copy is non-load-bearing). All three are committed in the repo working tree
  (`components/{drivers,engines}/`) so the next reference-image build includes them.

## ADR-0073 M2 — CPCB + AOD + fire drivers (2026-09-05)
- **CPCB ground truth is LIVE** via `air-sensors@0.2.0` (49 real Delhi stations → air.sensor_reading; pm25-features
  labels_present:49). data.gov.in had re-keyed the value field `pollutant_avg`→`avg_value` (fixed, accepts both).
- **Per-component Vault secret isolation is a real onboarding cost for shared credentials.** The ONE Google
  service-account key is stored separately under every GEE driver (hydro-merit/terrain-dem/landcover-dw and now
  must be under maiac-aod too); the CPCB key is under air-sensors only. A new driver reusing a shared key needs the
  key re-bound to ITS component — Claude must NOT copy the raw value (that would expose it). Consider a future
  tenant-level / shared-secret grant to remove this friction.
- **maiac-aod + firms-fire are staged (certified+published+installed) but UNRUN — each gated on its key:**
  maiac-aod needs GEE_SERVICE_ACCOUNT_KEY; firms-fire needs a NASA FIRMS MAP_KEY, both bound to their own component
  in Connections for new-delhi.
- **Secrets `as: template` inject mode added (HOT-PATCH).** `services`/`platform-spec/reference/secrets.py` now
  supports `inject={as:"template", placeholder:"{KEY}"}` for path-key APIs (NASA FIRMS puts the key in the URL
  path). Hot-patched into the `airawat-secrets` container (`.bak-tmpl` backup) + committed in the repo; BAKE into
  the secrets image on next rebuild. The egress audit logs the pre-substitution placeholder path, so the key is
  never recorded.
- **signal.fire is per-detection event, not per-cell.** pm25-features does NOT yet consume it; wind-aware
  fire→cell transport features are M3.

## Connections app visibility = app-host's OWN /app/components (2026-09-05)
`/bridge/connections` builds the Connections list by SCANNING the **app-host container's** baked
`/app/components` (drivers/engines/…) for any component declaring `secrets` or `assets` — it does NOT read the
store or install records. So a new driver is INVISIBLE in Connections until its dir is also present in app-host,
even if it's installed + running. A component now needs its code in THREE places, each for a different function:
(1) HOST `rt-components` (bind-mounted) — runtime-manager EXECUTES from here; (2) scheduler `/app/components`
(baked) — cid→kind resolution for `/run`; (3) app-host `/app/components` (baked) — Connections secret/asset
listing. Baking all three into the reference image on rebuild removes this drift; until then docker-cp to all
three. (maiac-aod + firms-fire were run-installed but only appeared in Connections after the app-host copy.)

## ADR-0073 M3 — feature store (2026-09-05)
- **pyarrow hot-patched into runtime-manager** (the in-process engine runtime) for Parquet output — BAKE into the
  reference image on next rebuild. pm25-features falls back to NDJSON if pyarrow is ever absent (graceful).
- **Temporal lags = coarse point-series.** cams/pblh write the hourly series only at the ~25 AOI sample cells
  (reusing cell.cams/cell.boundary_layer with hour-keyed `/series/` ids), not all 24k cells — CAMS/PBLH are ~40km
  fields so lags are regional. pm25-features assigns each cell its NEAREST anchor's lags. Cheap (~1350 facts/driver
  for 54h) + honest. The `/series/` facts coexist with the hour-less current-hour facts in the same scope; the
  nowcast join filters by observed_at==target so they don't interfere. AOD lags stay per-cell (M-later; satellite
  is genuinely 1km, no cheap coarse shortcut).
- **Series depth is bounded by Open-Meteo past_days** (SERIES_HOURS_BACK, default 48 → ~54h available). Deeper
  history (for real training) needs repeated scheduled runs accumulating hours, or the archive API.
- **M3.4 wind-transport not built.** signal.fire is ingested but not yet a feature; needs a per-cell wind field.

## ADR-0073 M3.4 — roads + building-height + nightlights (2026-09-05)
- **Schema-cache staleness after an in-place schema bump.** The kernel caches the schema VERSION map ~300s and
  validates writes against it. After governing cell.buildings@0.2.0 (new mean_height_m/built_volume_m3), the kernel
  kept validating vs 0.1.0 → writes 422'd on the new fields. FIX: `POST /v1/registry/schema-cache/refresh` (admin/
  steward) forces a re-fetch immediately. Do this after ANY in-place governed-schema update before writers use it.
- **buildings-openbuildings@0.2.0** adds Open Buildings 2.5D Temporal `building_height` band to its GEE reduce →
  per-cell mean_height_m + built_volume_m3. The temporal-collection `.mosaic()` + masked reduce is SLOW (full 24k
  backfill = a long GEE run). Optimization: pin one recent year instead of mosaicking the whole collection.
- **cell.roads was already produced by osm-roads** (length/density per cell) — not a new build, just needed a
  re-run for new-delhi. Roads are 100k+ geo.osm_feature; the per-cell rollup MUST be done in the driver's PBF pass,
  never post-hoc (a registry resolve of the full set times out at 120s).
- **Nightlights DONE** (econ.nightlight → nightlight_radiance). pm25-features → 0.6.0 joins nightlight + roads +
  building height; matrix ~33 features once the roads + full-height backfills finish.

## M3.5 — historical label corpus (openaq-archive)
- **openaq-archive driver LIVE + run for new-delhi**: 2,791 REAL hourly PM2.5 readings (station 8118, New Delhi)
  from OpenAQ's anonymous S3 archive (s3://openaq-data-archive), window 2026-05-04..2026-09-01, ~96% hourly.
  Total new-delhi air.sensor_reading = 2,840 (49 live CPCB snapshot + 2,791 archive). Source-attributed
  (source=openaq-archive, prov.source_ref→ref.source/openaq, ODbL-1.0, s3_key anchor). Bootstrap = ONE station;
  scale to all Delhi stations (drop LOCATION_IDS → keyed bbox discovery, or pass the full id list) is a config-only rerun.
- **BROKER binary-body fix (as-yet HOT-PATCHED, not baked)**: platform-spec/reference/secrets.py /fetch used to
  decode every upstream body as UTF-8 → corrupted gzip. Now returns `body_b64` (base64) for binary content-types
  (gzip/octet-stream/zip/parquet or NUL-in-first-2KB), else `body` as before. The .csv.gz archive rides through
  the broker intact. MUST be baked into the `reference` image (currently docker cp'd into airawat-secrets).
- **FEATURE↔LABEL TEMPORAL ALIGNMENT GAP (blocks real supervised M4)**: the archive gives MONTHS of historical
  hourly LABELS, but the feature drivers (CAMS/PBLH/AOD/…) currently write only the LATEST-hour snapshot per cell
  (+ a coarse 48h series at sample points). Supervised training needs features time-aligned to each label hour.
  Next: backfill HISTORICAL features over the same window — CAMS/ERA5 reanalysis is available via the Open-Meteo
  ARCHIVE API (air-quality-archive / archive-api) for the exact hours — before the leave-station-out + temporal-
  holdout numbers mean anything. Until then M4 metrics remain the honest-but-poor snapshot-only baseline.
- **openaq-archive grant is WRITE-ONLY on air.sensor_reading** (reads only space.aoi) — correct least-privilege;
  verified the corpus via the pm25-features reader token, not the driver's own.

## Federated Mail signed-relay (ADR-0023/0024) — first slice, 2026-09-07
- **Signed, not sealed.** A cross-tenant `mail.message` is delivered via a federation envelope SIGNED by the
  sender tenant's steward (Ed25519) — origin is proven and tamper is rejected — but the body is NOT encrypted.
  `/v1/federation/inbox` is pollable by participant_id, so envelope bodies are readable to anyone who can poll
  that steward inbox. In-transit + at-rest-in-transit confidentiality (X25519 sealing) is a later ADR-0024 track.
- **Recipient-pull delivery.** A federated message lands only when the recipient's Mail inbox is opened (the
  mail-engine `listing` handler drains + delivers). No push/notification yet; a scheduled drain per tenant is the
  follow-up so mail arrives without the recipient opening the app.
- **Same-kernel deployment.** On this single-operator deployment all tenants share one kernel; the recipient
  delivers into its own tenant with its own authority (no cross-tenant kernel write). Multi-operator delivery
  (routing an envelope to the kernel that actually hosts the recipient tenant) needs operator endpoint discovery
  in the directory — not yet built.
- **Steward signing needs Vault.** `_steward_signer` has no non-Vault fallback (by design — a dev fallback that
  persisted a key seed locally was rejected at review), so the relay requires a Vault-backed network service.

## Building-footprint ingest is capped by the GEE free-tier daily quota
- `buildings-footprints` (Google Open Buildings v3 via GEE) reads footprints server-side one tile at a time
  (`getInfo`). On the **noncommercial (free) GEE tier**, a single day's ingest exhausts the project's daily
  compute quota after roughly **one full run (~40k footprints / ~35 of 112 tiles for the Nashik+Trimbakeshwar
  AOI)**. Once depleted, GEE enters "restricted mode" and subsequent `getInfo` calls hang/throttle to a near-halt —
  the driver authenticates and prints its tile plan, then makes **no further writes** (observed on both a full
  RESUME run and a small 12-tile targeted run). It is NOT a driver/platform bug: the first run succeeded; the
  quota is the ceiling.
- **Consequence:** covering a whole city AOI takes **multiple days** of RESUME runs (each resumes cheaply, skipping
  done tiles via a per-tile `h3_id` existence check), OR a **commercial/paid GEE project** with a higher quota.
- **Nashik status (2026-09):** 40,698 real footprints across 1,864 res-9 cells — southern band (lat 19.85–19.94)
  incl. the **Trimbakeshwar** Kumbh side. The **northern Nashik urban core (~20.0°N, Ramkund/Panchavati) is not
  yet covered** — needs a RESUME run after the daily quota resets. Chained-RESUME driver + targeted-bbox recipe:
  `/tmp/bldchain.py` / `/tmp/bldcbd.py` on EC2 (scheduler `/run` with env `RESUME`/`RUN_BUDGET_S`/`FOOTPRINT_BBOX`).

## MoSPI CPI slice (data-provider tenant) — 2026-09-10
- **mospi-gateway is now a compose-managed service (durable).** Added to the EC2 stack
  `docker-compose.yml` (name `airawatos`, service `mospi-gateway`, `restart: unless-stopped`, stock
  `python:3.12-slim` bind-mounting `services/mospi-gateway/app.py` — the ref-overrides pattern). It comes up
  with `docker compose up -d` and survives restarts/recreates. Snippet in repo:
  `services/mospi-gateway/compose.snippet.yml`. (Still source-bind-mounted rather than baked into an image;
  fine for this stack, which bind-mounts all editable reference code.) Separately, the driver/reader SOURCE
  staged under `~/airawatos/rt-components/{drivers,engines}` and `docker cp`'d into `airawat-app-host` is still
  a manual staging step for publish — universal delivery means the RUNTIME rehydrates from the filestore, so
  that staging is only needed at (re)publish time, not for running.
- **`stat-reader` engine was published with a `/v1/query` body-key bug** (`scope` instead of `filter.schema`).
  Fixed in the local source; the *published/filestore* copy still has the old key. The sharing capability was
  proven via a DIRECT `/v1/registry/query` (correct key), not by invoking the engine, so the demo stands — but
  re-publish stat-reader before relying on the engine's own run output.
- **National-statistics sharing uses the aggregator lane (per-component grant), not SHARED_SCHEMAS.** The
  ADR-0066 shared-schema path has a single global `SHARED_STEWARD` (airawat), so it can't host MoSPI as its own
  steward without a code change to support per-schema-prefix stewards. A cleaner future model: let national
  reference schemas (`stat.*`) declare their authoritative steward so every tenant reads them directly
  read-only, instead of each consumer installing a reader + grant.
- **Broker egress cannot reach legacy-TLS hosts directly.** `secrets.py`'s egress `urlopen` uses strict TLS;
  hosts needing `OP_LEGACY_SERVER_CONNECT` (e.g. api.mospi.gov.in) must be fronted by a dedicated gateway
  service (as done here). A general fix — a fallback legacy-TLS context in the broker egress, cert-verify kept
  ON, fallback-only — was drafted but deferred (security-sensitive; kept out of the shared broker by choice).

## Verb-governance rollout — Studio publish gate (2026-09-11)
- **~~payroll-engine published via the DIRECT certify path~~ RESOLVED (2026-09-11) — now publishes via Studio.**
  Its headless `main()` ran the real apportionment whenever `RUN_TOKEN` was set (both the cron AND the dev Test),
  so the dev sandbox run failed and blocked the Studio publish. Fixed by making `main()` **self-test when there is
  no target tenant**: a real scheduled run has `WRITE_TENANT`/`TENANT` injected (the tenant `_headless_ctx` writes
  to); a dev Test has a clean env (no target) → prints handlers + returns 0. Preserves the production cron exactly
  (it still sets the tenant) while the dev Test goes green. General lesson: **a data-dependent headless engine's
  `main()` must guard the real work behind the presence of its run-target signal, so it self-tests in the sandbox.**
- **The `airawat-scheduler` container carries a SECOND copy of `components/engines/` that drifts from app-host.**
  Newer engines (chat/mail/fund-flow) were absent there, so their dev Test errored until the source was `docker cp`'d
  into the scheduler too. Engine source must be staged to BOTH airawat-app-host and airawat-scheduler (bind-mount/cp
  deploys) — to be resolved at reference-image rebuild.

## ref-override clobber: live app_host was ahead of the repo (2026-09-11)
- `/bridge/agent-brief` + the personal-agent read tools `list_civic_issues` / `list_updates` existed ONLY in the
  live `~/airawatos/ref-overrides/app_host.py` on EC2 (hand-added a prior session, never committed to the repo).
  This session's Data-app deploys `scp`'d the repo `app_host.py` over that ref-override and CLOBBERED them — the
  personal assistant regressed to the catch-block greeting. Rebuilt in the repo (durable) + redeployed.
- **Rule:** the bind-mounted ref-override files (`app_host.py`, broker.py, several app index.html) can be AHEAD of
  the repo. Before overwriting one with the repo copy, `diff` it first and back-port any live-only edits. A repo↔box
  reconciliation pass (and retiring ref-overrides at the next reference-image rebuild) is overdue.

## News → City Scan geocoded civic-issue overlay (2026-09-11)
- **Geocoding yield is inherently partial.** `news-geocode` (ds:airawat:engine/news-geocode) puts a civic.issue on
  the map ONLY when the model can extract a specific sub-city locality from the headline/summary AND Nominatim
  resolves it inside the city AOI. Most news-sourced civic.issue name the whole city, the state, or another city
  (e.g. Nashik's feed carried "Deputy CM's speech", "Bengaluru pourakarmikas", "Mumbai-Goa highway") → NO pin, by
  design (never guessed). So the "Civic Issues" overlay is honestly sparse from news alone; field-report incidents
  (which carry real GPS) are the naturally-mappable source. Tuning each tenant's news QUERIES to hyperlocal,
  civic-focused terms raises yield. News is pulled + categorised PER TENANT.
- **`civic.issue` bumped to @0.2.0** to add optional `geometry` (GeoJSON Point) + place_label + geocode_confidence
  + geocoded_at + geocode_method (0.1.0 was additionalProperties:false and rejected the write). Backward-compatible
  (same required set). NOTE: the kernel caches schema defs ~300s — after publishing a new schema version, POST
  /v1/registry/schema-cache/refresh (admin) or wait out the TTL, else writes 422 against the stale def.

## ADR-0085 S4 federated install (2026-09-14) — DEPLOYED + FULL-CHAIN e2e PROVEN
- Cross-install component delivery is code-complete + deployed at every layer (network 0.2.4 listing carries
  `source_file_id`; EC2 reference 0.2.1 + local 0.2.1-local wire publish→listing and consume→network-filestore).
- PROVEN LIVE: a real dev1co driver (`ds:dev1co:driver/hello-federation`) published from the LOCAL install
  (cert + source→network filestore + listing carries source_file_id) → installed on EC2 tenant `bmc` (no on-disk
  source on EC2) → run via the EC2 scheduler → launcher fetched the source from the network filestore +
  digest-verified vs dev1co's cert → ran (exit 0, marker printed on bmc). The launcher is fail-closed (REFUSE on
  any miss/mismatch), so exit-0 is proof the network-filestore fetch + digest-verify path executed.
- BUILD GOTCHA: the reference image's full amd64 build SEGFAULTs (exit 139) when cross-building the heavy ML deps
  (xgboost/pyarrow) under QEMU on an arm64 Mac. Workaround for pure-Python changes: build a thin overlay
  `FROM manishsv/airawatos-reference:<base>` that only COPYs the changed .py files (no pip step → no emulation
  crash). Full/native rebuilds should run on the EC2 host (amd64) — but EC2 `~/airawatos` has drifted from the
  `platform-spec/reference` + `components` layout the Dockerfile expects, so a clean on-EC2 build needs a source sync first.

## ADR-0086 operator certification — PROPOSED, not built (2026-09-14)
- The network verifies only the tenant ISSUER signature; there is NO operator/origin/runtime-integrity check. An
  "operator" is a mutable directory string, not a gate; "tenants only run on certified operators" is not enforced.
  ADR-0086 (digest-attestation → operator cert → certified-hosting binding) is the design; unbuilt.

## Governed engine-publish loop is broken in services-only deployment (2026-09-20)
- After the ADR-0093 S-flip (reference image ships services-only; engines materialize to the app-host's
  `/data` cache on install), the Studio dev-Test → Publish loop for ENGINES no longer works out of the box.
  The scheduler's dev-run (`run_component_dev` → `_find_dir` walks its OWN `--components-root /app/components`)
  finds NO source: the scheduler container has no engine source and there is NO shared components volume between
  app-host and scheduler. So `/bridge/project-test` returns "no source found — add it to a project", which gates
  `/bridge/project-publish` (INT-0004 slice-4 green-test requirement). Net effect: the ONLY convenient way to
  update a live engine became `docker cp` hot-patching — which silently drifts the running host from the Store.
- Concrete drift found & fixed this session: campaign/lifecycle/project engines had been hot-patched; the Store
  still held older code (campaign at the SAME version 0.1.2 as the new code — an immutability violation). Fixed by
  bumping versions and republishing through the real path, but only after manually `docker cp`-ing the draft
  source into BOTH the app-host and the scheduler container. That manual placement is the workaround, not a fix.
- Also observed: every pre-existing engine Store listing has `source_file_id`/digest = **None** — publishes before
  ADR-0085 S4 carried no content digest, so drift between Store and running code is undetectable by digest. The 3
  republished engines now DO carry `sha2-256:` source ids.
- Proper fixes: (a) **FIXED (2026-09-20, platform-spec 9cf1057)** — a shared draft-source channel: the app-host
  stages the working draft to the content-addressed filestore (`_stage_draft`) and threads its file_id to the
  scheduler's `/run`; the scheduler materializes+runs it (`_materialize_dev_dir`, preferring the staged draft >
  published `__component_source__` > network listing). Proven on EC2: campaign/project/lifecycle dev-Test green
  with source REMOVED from the scheduler container ("dev-materialised … from filestore" in the log). No shared
  volume, multi-host-correct. **Baked durable in `manishsv/airawatos-reference:0.2.34` (sha256:7aef65c8…);
  compose repointed app-host 0.2.33→0.2.34 + scheduler 0.2.30→0.2.34; pushed. Proven on FRESH 0.2.34 containers
  (no docker cp): all 3 engines dev-Test green, scheduler logs "dev-materialised … from filestore".**
  (b) **DRIFT CHECK BUILT (2026-09-20, platform-spec c7d6a1a; baked in reference:0.2.35 sha256:5ff0e805…):**
  `POST /bridge/component-drift` (admin-only, read-only) compares each on-host component's
  `package.artifact_digest(dir)` (baked + /data-cache) to the Store listing's `certificate.evidence_digest` →
  ok / drift / unverifiable / unpublished. Proven: clean OK→DRIFT→OK perturbation on lifecycle-engine; it
  immediately found 3 real drifts among 71 components — campaign/project stale cache (remediated by
  re-materialise → now ok) and hr-workflows baked ≠ certified 0.3.2 (a same-version drift; **RECONCILED** —
  republished as 0.3.3 from the current source + rebaked in reference:0.2.36; host now 0 drift / 70 ok / 1
  unpublished, the latter being the `ds:airawat:solution/tax-gap-finder` solution artifact, expected). **Surfaced in the UI: Settings → Supply chain tab (settings app 0.1.6,
  published→live) — per-component status, drift-first table, red banner + same-version ≠ flag, re-scan.** No
  scheduled/periodic run yet. `source_file_id` on old listings turned out to be present (not None) — but
  `evidence_digest` is the digest the check uses. (c) **DONE (2026-09-20, network store.version_error digest-aware;
  baked airawatos-network:0.2.15 sha256:21c2eb5f…):** version-bump-on-change enforced at POST /v1/store/publish —
  same version + identical source = idempotent no-op (was a hard 409); same version + CHANGED source = 409
  "the source changed, bump the version"; lower = monotone-blocked. So a changed component can never re-publish
  under an existing version. Proven on EC2 (campaign 0.1.3: identical→200, +1 comment→409, survives fresh
  container). Residual: this guards the PUBLISH path only; the bake/hot-patch BYPASS is covered by the drift
  check (detective) — a load-time refuse-on-drift would be the belt-and-suspenders preventive (not built).

- 🟡 **Service-request interpreter extracted to the engine but not yet live-e2e'd.** ADR-0097: the
  ADR-0067 service workflow interpreter (open + advance) moved out of `app_host`
  (`_provider_fulfil`, `_advance_service_workflow`) into `lifecycle-engine` 0.1.18
  (`service-open`/`service-advance`). Proven by a 34-check parity unit test + local-stack load, but
  NOT driven through a live BAP→BPP flow because the service runtime is dormant (0 `service.offering`
  records on any tenant). **Fix:** seed one real 2-step offering + consent + certified aggregator and
  drive route(init)→complete→complete→close on EC2 after the reference bake. Until then, the port is
  behaviour-proven, not traffic-proven.

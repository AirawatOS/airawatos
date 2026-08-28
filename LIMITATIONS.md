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

# ADR-0063 — Govern the control-plane verbs (the platform holds itself to actor·verb·noun)

- **Status:** Proposed (2026-08-22)
- **Deciders:** Airawat (platform steward), product owner
- **Composes:** ADR-0058 (interfaces are first-class governed specs — the *verb* leg), ADR-0062 (one invoke
  verb; the enforcement that closed the verb leg for **components**), ADR-0038 (spec governance — the loop each
  verb is proposed through), ADR-0030 (broker = the only I/O surface for components), ADR-0056 (decided
  change-request).

## Context

ADR-0062 closed the actor·verb·noun triad for **marketplace components**: certify now refuses a component that
declares an ungoverned schema (noun), role (actor), or interface (verb). But the **platform's own control
plane exempts itself**. Two facts, both observed in the running system:

1. **11 governed verbs vs dozens of ungoverned ones.** The catalog governs `registry.read/write/query/retract`,
   `platform.event/fetch/file/runtime_invoke`, `intelligence.completion/embed`, `justice.file_case`. Meanwhile
   the reference services expose and call each other through ungoverned bespoke HTTP: `/run` `/schedules`
   `/reload` (scheduler), `/events` (automation), `/materialize` `/set` `/rotate` `/status` (secrets),
   `/complete` `/decide` `/notify` `/instantiate` (workflow), `/advise` (flood), the whole `/bridge/*` surface
   (app-host), plus the network's own `/v1/*` control verbs.
2. **A governed binding points at an ungoverned verb.** A `platform.subscription` (a governed *noun*) fires an
   `action.url` of `http://localhost:8103/run` with `interface: null` — the binding names a raw endpoint, not a
   governed verb. The noun is governed; the verb it invokes is not.

The rule the platform enforces on others, it must obey itself: **the only ways to interact are governed verbs
(and the broker's own surface).** Every semantic inter-service call is a `network.interface`; a component,
service, or binding may only name a governed verb.

## Decision

### 1. Classify every control-plane endpoint: semantic verb vs transport plumbing.

Not every HTTP path is a governed verb. **Transport plumbing** — liveness, key distribution, session mechanics,
read-only introspection — is infrastructure, not a semantic interaction, and stays exempt. **Semantic verbs** —
anything that *runs, mutates, decides, or moves value/state across a service boundary* — must be governed.

| Endpoint(s) | Service | Class | Governed verb |
|---|---|---|---|
| `/v1/invoke` | runtime-manager | semantic | `platform.runtime_invoke` ✓ (exists) |
| `/run` (fire a component) | scheduler | semantic | **delegates to** `platform.runtime_invoke` (no new verb) |
| `/events` (deliver an event) | automation | semantic | `platform.event` ✓ (exists; service must *declare* it) |
| `/materialize` `/set` `/rotate` | secrets | semantic | **`platform.secret`** (methods: materialize/set/rotate) |
| `/complete` `/complete-task` | workflow | semantic | **`governance.task_complete`** |
| `/decide` | workflow/decision | semantic | **`governance.decide`** |
| `/instantiate` | workflow | semantic | **`platform.workflow_instantiate`** |
| `/notify` | workflow | semantic | **`platform.notify`** |
| `/advise` | flood pipeline | semantic | *retire* → run as a component via `platform.runtime_invoke` (ADR-0062) |
| `/v1/certify` | network | semantic | **`network.certify`** |
| `/v1/store` (publish) | network | semantic | **`network.publish`** |
| `/v1/join` | network | semantic | **`network.join`** |
| `/v1/schema-requests` `/v1/role-requests` `/v1/pack-requests` (+ decide) | network | semantic | **`network.change_request`** (file + decide) |
| `/v1/keys` | network | semantic | **`network.key_publish`** ✓-ish (has PoP; formalize) |
| `/v1/messages` | network | semantic | **`network.message`** (signed participant messaging) |
| `/bridge/*` | app-host | semantic | each maps to a governed verb (`/bridge/run`→`platform.runtime_invoke`, `/bridge/write`→`registry.write`, `/bridge/decide`→`governance.decide`, …); the bridge is the app confinement boundary, so this mapping IS the app-side enforcement |
| `/healthz` `/jwks` `/login` `/logout` `/session` `/realms` `/users` `/whoami` `/v1/context` `/reload` `/runs` `/schedules` `/status` | various | **plumbing** | exempt (liveness, identity mechanics, read-only introspection) |

### 2. A binding may only name a governed verb.

`platform.subscription.action` (and any future trigger action) must carry an **`interface`** that is a governed
`network.interface`; the dispatcher resolves interface → endpoint. A subscription whose action names an
ungoverned/raw verb is **rejected** — the same refusal certify gives an ungoverned component. This closes the
"governed noun → ungoverned verb" leak directly.

### 2b. A governed schema is a governed *shape*, not just a governed name (write-time conformance).

Governing the noun leg had a hole: certify enforced that a component only *declares* governed schema **names**,
and the steward grant enforced **who** may write them — but nothing checked that the **object actually conforms
to the schema**. A component could write `subject_ref` (not even a field of `platform.inbox_item`) or omit a
required field, and the registry stored it. "Governed schema" meant governed *vocabulary*, not enforced *shape*
(the static conformance suite even says output-shape validation "needs a sandboxed run — not here yet").

**Decision:** validate every written object against its governed JSON-Schema **at the registry write
chokepoint**. The registry is the single point *all* writes funnel through — `broker.write → Registry.put`
**and** the raw `/v1/registry/objects → REG.put` — so the check lives in `Registry.put` (a shared hook across
the in-memory *and* Postgres backends), and **no write path can bypass it** (this is the answer to "shouldn't
the registry enforce this?": yes — it is the enforcement point). `SCHEMA_VALIDATE = off | shadow | strict`;
default **shadow** (logs non-conformance, still stores) so we can see every current violation before flipping
strict — the same rollout as `COMPONENT_ENFORCE`/`SUBSCRIPTION_ENFORCE`. The schema def comes from the kernel's
local installed catalog first, else the network authority (cached). *Verified:* in shadow it caught the missing
required fields + type/enum violations on both write paths — and immediately surfaced a **real** pre-existing
bug (`platform.event` written with `tenant: None`). **Two follow-ups to flip strict:** (a) tighten loose schemas
(many, incl. `platform.inbox_item`, have `additionalProperties: true`, so a stray field like `subject_ref` isn't
flagged — only missing *required* fields are) via the governed change-request flow; (b) fix the real violations
shadow surfaces (e.g. the `platform.event` tenant) before enforcing.

### 2c. Fixed house rules every schema must follow, enforced at design & approval (the meta-schema).

Data-shape validation (§2b) checks *data vs schema*. But nothing checked *schema vs house rules* — so schemas
(and the drivers that write them) drifted: an object with no closed contract, a measure with no provenance
(this is exactly why `geo.terrain` data lacked `prov`/`observed_at` — the schema never required them, so the
driver never wrote them). **Decision:** a fixed set of house rules that *every* governed schema must satisfy,
enforced in the same lints that run at schema **propose + approve** (`lint_house_rules` alongside the ADR-0060
`x-kind`/measure/collision lints). A schema that breaks them cannot be filed or approved — schemas are
production-ready *by construction*.

The rules (`HOUSE_RULES_ENFORCE=1` strict, `0` shadow):
- **R1 object** — a schema is `type: object`.
- **R2 envelope** — `required` includes `schema` + `id` (every object self-identifies and is addressable).
- **R2b id-grammar** — the `id` property must constrain to a **resolvable, steward-scoped id** (`pattern`
  `^ds:[a-z0-9-]+:\S+$` → `ds:<steward>:<kind>/<local>`), so an id is globally unique *across the federation* and
  addressable — not merely unique as a registry key, and not an arbitrary string. Enforced at the design gate
  *and* at every write (verified: non-resolvable id → 422 at both).

**System id vs natural key (2026-08-22).** The `ds:` id is the *system* identity; a **business/natural
identifier** (case number, property PID, CNR, UDISE) is domain data, never the key. Modeled as a governed
reusable **fragment** `platform.identifier` (`{scheme, value, authority}`, `x-kind: fragment`) embedded as an
`identifiers[]` block on every **entity** schema (added to all 14). A **fragment** is a value object embedded in
other schemas — it has no own id/schema, so it is EXEMPT from R2/R2b/R5/R6 (a fifth `x-kind`). The `<local>`
segment of a `ds:` id is **derived from the primary natural key** (a slug) for a human-readable, deterministic
id — codified in the shared helper `components/_common/ids.py` (`slug`, `object_id`, `identifiers`, `entity`),
which a driver uses to mint an entity whose `id` comes from its natural key *and* whose `identifiers[]` carries
every key. Verified round-trip: `entity("kmc","justice/case",…,[("filing_no","CS/1234/2026",…),("cnr",…)])` →
id `ds:kmc:justice/case/cs-1234-2026` → write → `resolve-by-identifier(cnr)` returns it; same natural key ⇒ same
id (idempotent). `POST /v1/registry/resolve-by-identifier {value, scheme?, schema?}` bridges
natural-key → `ds:` id (scans `identifiers[]` + common natural-key fields; scoped to identifier-bearing entities;
the federation bridge of ADR-0015). Verified: CNR / filing_no → the case's `ds:` id.
- **R3 closed** — `additionalProperties: false` (no stray/misnamed fields — this is what would have caught the
  `subject_ref` inbox bug at design time), unless `x-open: true` with a reason.
- **R4 typed** — every property declares a type (`type`/`enum`/`const`/`$ref`/`one|any|allOf`).
- **R5 measure** — a `measure` requires `observed_at` + `prov` (provenance + observation time; ADR-0053/0041).
- **R6 event** — an `event` requires an occurrence time (`at`/`observed_at`).

*Audit (2026-08-22):* run against the live catalog, **0 of 56 schemas pass** — R3 (closed) fails on all 56,
R2 on 27, R5 on 7, R6 on 6. So the gate is correct and the existing catalog needs a **migration**.

**Migration — DONE (2026-08-22): all 56 → house-rule compliant.** A governed re-sign path
(`POST /v1/schemas/resign` — a one-off migration tool, since retired; see PLAT-0004 — admin-gated, ran the same lints incl. house rules — so a migration can only make
a schema *more* compliant) + a data-driven tighten (close each schema to the fields its records actually use,
add the envelope, add `observed_at`+`prov` to measures / a time to events, type every property). Applied
domain by domain; **final audit: 56/56 clean.** *Sequencing note:* the tightened schemas now live in the
network (source of truth, gate, audit); the kernel still validates data against its **locally-cached** defs, so
the migration broke **no** running driver. The remaining production step is a **driver-conformance pass**: sync
the tightened defs to the kernel, fix drivers to write conforming data (envelope present, measures emit
`observed_at`+`prov`, no stray fields — e.g. `terrain-dem`, `risk.flood`, `governance.rule`), delete + refill
(data is disposable), then flip `SCHEMA_VALIDATE` strict against the tightened catalog. The gate is live for all
*new* schemas immediately.

### 3. Services declare the verbs they serve and consume; callers resolve by interface, not URL.

Each reference service declares which governed interfaces it **implements** (serves) and **calls** (consumes).
Callers resolve an interface id to an endpoint through a directory, replacing hardcoded `localhost:PORT`. This
makes the seam auditable and lets the same governed-interfaces conformance check (ADR-0062 §6b) apply to
platform services, not just marketplace components.

## Consequences

- The platform obeys its own rule: every semantic interaction is a governed verb; no service invents a method.
- Bindings (subscriptions, triggers) reference verbs, not URLs — location-independent and auditable.
- Cost: ~10 new `network.interface` proposals through the spec loop (each an approval gate), plus rewiring the
  subscription action shape and the service call sites. Sequenced in batches below; **no big-bang**.

## Slice plan (each interface proposal is an approval gate)

- **Batch A — the run/secret/event core — BUILT (2026-08-22):**
  - **Verb-governance parity (the meta-fix):** `POST /v1/interfaces` was an *unauthenticated open POST* — anyone
    could add a governed verb. Now steward-gated, and a developer proposes a verb via the new
    `POST /v1/interface-requests` → **admin decides** flow, mirroring schema-requests exactly (list + decide,
    wired into the Console's Change Requests queue). Verified: open publish → 401; `platform.secret` filed by
    the developer → pending → visible+reviewable in the Console.
  - **`platform.secret` proposed** (materialize/set/rotate/status) — pending the standards-body approval.
  - **`platform.runtime_invoke` covers `/run`:** the scheduler run path (Slice 1, ADR-0062) already delegates
    to the manager's invoke verb; the dispatcher resolves the verb → that endpoint.
  - **Subscription action → governed verb:** the dispatcher now requires `action.interface` to be a governed
    verb and resolves it to an endpoint (no raw URL). SHADOW by default (`SUBSCRIPTION_ENFORCE` flips strict) so
    live flows don't break mid-migration. Migrated `recommendation-to-router` → `platform.runtime_invoke`;
    verified it fires through the governed verb. (`flood-advise` still names a raw `/advise` — warns in shadow;
    retired in Batch B.)
  - *Remaining in A:* formally declare `platform.event` as *implemented by* the automation service (service
    declaration — folds into Batch D); flip `SUBSCRIPTION_ENFORCE` strict once `flood-advise` is migrated.
- **Batch B — governance verbs — FILED (2026-08-22, pending approval):** `governance.decide`,
  `governance.task_complete`, `platform.notify`, `platform.workflow_instantiate` proposed through the
  interface-request flow; all four pending the standards-body approval in the Console (reviewable with the
  View panel). Once approved, the workflow service *declares* it implements them (service-declaration, Batch D).
  - **`SUBJECT_REF` event-context passing — BUILT + PROVEN (2026-08-22).** The dispatcher now includes the
    triggering subject id in the fired action; the scheduler's run path threads it into the component's env as
    `SUBJECT_REF` (+`EVENT_ID`). Verified end-to-end: a flood event fired through the governed verb
    (`platform.runtime_invoke`), the scheduler ran the componentized advisor, and it received + read the
    specific alert. Reusable for ANY event-triggered component. `flood-advisor` was componentized
    (certified + published + installed), replacing the raw `/advise` handler.
  - **`/advise` retired + `SUBSCRIPTION_ENFORCE` strict — DONE (2026-08-22).** Wiring **INSTALL = GRANT** closed
    the last gap: `conformance.run` now returns the component's certified `declares` (reads/writes/scopes);
    `certify` carries it in the signed cert; `store_publish` auto-fills the listing scopes **from the cert** (so
    the steward's install-time grant covers exactly what was certified — can't be forgotten or inflated). The
    kernel install already calls `/v1/grants/issue`. Verified: installing `flood-advisor` into kmc issued a grant
    for its 4 writes + 2 reads; a flood event then drove event → subscription → `platform.runtime_invoke` →
    `SUBJECT_REF` → the advisor wrote an attributed case + decision task + 3 recommendations
    (`produced_by: component://flood-advisor`). `flood-advise` migrated off `/advise` onto the governed verb, and
    `SUBSCRIPTION_ENFORCE` was flipped **strict** — both subscriptions fire through governed verbs, zero refused.
    (Cross-tenant note: an `airawat` component is installed *into* kmc, so its run-token + grant are kmc-scoped.)
- **Batch C — network control verbs — FILED (2026-08-22, pending approval):** `network.certify`,
  `network.publish`, `network.join`, `network.change_request`, `network.message`, `network.key_publish` — all
  six pending in the Console. Prerequisite done: the **`network` domain** was registered as a governed domain
  (it was implicitly used by `network.schema/role/interface` but never formally governed).
  - **Gap surfaced — domains have no propose→approve flow.** `POST /v1/domains` is a *direct* admin publish,
    so the domain vocabulary (the namespace for every noun/verb/role) is **less governed** than the artifacts
    inside it — the opposite of the intended hierarchy. **Follow-up:** give domains the same decided
    change-request loop (`network.domain.request` → admin decide) as schemas/roles/interfaces.
- **Batch D — the app-host bridge map + service directory:**
  - **D1 — verb→endpoint directory — BUILT (2026-08-22).** The network serves a **binding directory**
    (`POST /v1/interfaces/bind` operator-gated, `GET /v1/interfaces/bindings`): a governed verb → the endpoint
    that serves it *in this deployment*. Only a governed verb may be bound. Seeded all 13 control-plane verbs.
    The automation dispatcher no longer hardcodes any `host:port` — it resolves the verb through the directory
    (verified: `platform.runtime_invoke` → `:8103/run` resolved from the directory and fired). **Nothing is
    removed** — the endpoint is what the verb resolves TO; the directory + signed contract are added *around*
    the unchanged HTTP call.
  - **D2 — service self-declaration + conformance — BUILT (2026-08-22).** `platform-spec/reference/services.yaml`
    declares, for all 10 reference services, the governed verbs each `implements` (serves) and `calls` (consumes);
    `conformance_services.py` fetches the catalog and REFUSES any service serving/consuming an ungoverned verb —
    the ADR-0062 §6b triad extended from marketplace components to the platform's own services. Verified: all 10
    conform (identity exempt as `plumbing`); a rogue service consuming `some.rogue_verb` → FAIL. The platform now
    holds itself to the same rule it enforces on others.
  - **D3 — app-host `/bridge/*` map — BUILT (2026-08-22).** All 56 bridge paths (the app confinement boundary —
    the only I/O an app gets) are now classified in verb terms via `BRIDGE_VERBS` + `GET /bridge/verbs`:
    **19 governed mutations** (`/bridge/run`→`platform.runtime_invoke`, `/bridge/decide`→`governance.decide`,
    `/bridge/secret`→`platform.secret`, `/bridge/change-request`→`network.change_request`, …), **25 reads**
    (`registry.read`/`query`), **9 app-host-internal** (Studio authoring + AI expert), **3 known gaps**. Verified:
    every governed verb the boundary names is in the catalog.
  - **Gaps surfaced (honestly, not hidden) → filed (2026-08-22, pending approval).** The three install-family
    endpoints collapse to **two** honest verbs, not three — because *everything is a component* (ADR-0022) and
    `app-install` was never a second install path:
    - **`platform.component_install`** (method install|uninstall) — the ONE kind-agnostic install; an app
      installs exactly like a driver. Covers `/bridge/install`.
    - **`platform.app_shelf`** (method add|remove) — add/remove an *already-certified* app on a tenant's desktop
      **shelf** (visibility/placement + role wiring), which `/bridge/app-install`+`/bridge/app-uninstall` actually
      do. Named for what it is, not a fake "app install".

## Non-goals

- Transport plumbing (§1 last row) is not governed — it is infrastructure, not a semantic verb.
- No change to the broker contract or to how components do I/O (ADR-0030 unchanged).

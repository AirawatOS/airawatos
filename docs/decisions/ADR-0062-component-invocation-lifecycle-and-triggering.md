# ADR-0062 — Component invocation, lifecycle & triggering (one invoke verb; declared triggers; engine-owned lifecycle)

- **Status:** Proposed (2026-08-22)
- **Deciders:** Airawat (platform steward), product owner
- **Composes:** ADR-0030 (Component SDK + broker — the broker is the ONLY I/O surface a component gets), ADR-0045 (the solution declaration — roles, interactions, tasks, workflows, **triggers**, decisions), ADR-0050 (the execution engine — *what runs a declaration*; single writer of case state), ADR-0058 (interaction contracts — `platform.runtime_invoke` is a first-class governed interface/verb), ADR-0052 (authenticated & attributed registry writes — every effect is attributed), ADR-0056 (every authoritative mutation is a decided change-request), ADR-0016 (certify/install — trust is established before a component may run), ADR-0060 (the City Baseline — the motivating case).

> **This is the first ADR authored natively for AirawatOS.** The 0001–0061 records live in the legacy
> AirOS repo and are a **migration backlog** to be rewritten for AirawatOS (see `docs/decisions/index.md`).
> Numbering continues unbroken so cross-references stay stable as the back-catalog is migrated in.

## Context

A component (driver, engine, agent, pipeline, app-side job) must be **run**. Today there are **three
different ways it gets run, and they do not share one path** — which is both an architectural smell and
the direct cause of a real failure:

| Trigger source | Where | How it *actually* runs the component |
|---|---|---|
| **Scheduled (cron)** | `scheduler.py` — 5-field cron, `tick()` each minute | `subprocess.run(cmd)` — a raw host subprocess. **Bypasses** cert-check, image-lock, and secret-materialization. |
| **Event** | one hand-wired case (`flood-forecast/advisor.py` on a `signal.alert`) | bespoke HTTP handler; **no general event→handler binding**. |
| **Direct / manual** | `/bridge/run`, `/bridge/city-onboard` → scheduler; **and** the runtime-manager `/v1/invoke` | two different paths: the bridge/scheduler spawn subprocesses; the manager implements the governed verb. |

There is exactly **one** governed invocation verb — `platform.runtime_invoke` (ADR-0058; launcher = reference
impl, runtime-manager = the trusted holder). It does the right things: cert-check → image-lock → materialize
secrets → place. **But only the runtime-manager and a pipeline's `_place()` honor it.** The scheduler and the
app-host bridge run components their own way, as a bare `subprocess.run` under a minted dev-token.

**The symptom.** City Baseline (ADR-0060) returned "3 of 5 steps." The two Google Earth Engine drivers
(`landcover-dw`, `terrain-dem`) failed with `424 secret not configured` — although both keys *are* in Vault.
A GEE driver can only obtain its key through `materialize`, which lives **behind** the invoke verb. Any path
that runs it as a bare subprocess gets 424. The key exists; the run never asked the one service allowed to
hand it over. **The bug is not the driver — it is that there is more than one way to run a component.**

Two design questions must be answered together:

1. **How does a component expose "run"?** In-process lifecycle callbacks (`on_init`/`on_run`) the engine calls,
   or a single external entrypoint?
2. **How is a run triggered by an event?** Does a driver subscribe itself to a registry write, or is the
   wiring declared elsewhere and enforced by the engine?

## Decision

### 1. One invocation verb. No component is ever run any other way.

Every run — scheduled, event-driven, or manual — goes through `platform.runtime_invoke`. The scheduler and
every `/bridge/run`-style endpoint become **callers of the verb**, not runners. `subprocess.run(<component>)`
is removed from the trigger surfaces. This makes cert-check, image-lock, attribution, and
secret-materialization **uniform for every run regardless of why it fired** — and closes the 424 gap
permanently, for all trigger sources, not just the button.

### 2. The invocation seam is a process + token boundary, not a function call.

A component is a **certified, confined, language-agnostic process** that talks to the platform **only through
the broker** (ADR-0030). The engine therefore cannot — and must not — reach *into* it and call a method. The
contract is:

- **Down (engine → component):** spawn the entrypoint with an `env` (AOI, tenant, config) **+ a scoped
  run-token**. That is the entire input contract.
- **Up (component → platform):** **only** via the broker (`read`/`query`/`write`/`fetch`) under its token,
  plus its **exit code** and logs. The component's "return value" is the **attributed writes** it made; the
  engine observes those + the exit code.
- The component **never imports or calls** the engine; the engine **never imports** the component.

This is *why* the model is language-agnostic and confineable: the seam is spawn-down / broker-up, nothing
else. **We therefore reject in-process lifecycle callbacks (`on_init`/`on_run`).** You cannot call
`on_run()` on a Rust container behind an image-lock.

### 3. Multiple phases = multiple declared invocable verbs, invoked the same way.

Where a component genuinely needs distinct phases (e.g. `migrate`, `healthcheck`, `teardown`), it **declares
extra invocable verbs** in its meta, and the engine invokes each **the same way** — spawn the entrypoint with
a `MODE` — never as an in-process hook. This gives the expressiveness of `on_init`/`on_run` while keeping the
one process+token boundary. `run` is simply the default verb.

### 4. Triggers are declared, not coded — and the binding is the existing governed noun, not a new one.

There are three legitimate **trigger sources** — `schedule` | `event` | `request` — and all three resolve to
(1)+(2). The binding "*this happened → run that*" is a **governed registry record**, not code and not a
subscription the driver holds. **We reuse the vocabulary that already exists — inventing a new noun here
would be exactly the drift this ADR exists to prevent:**

- **event** → **`platform.subscription`** (already a governed `network.schema`): a `WHEN` (match:
  `subject_schema` + `where` conditions on the subject) → `THEN` (action). The action targets the one run
  path (`/run` → `platform.runtime_invoke`) with `{component, tenant}`. A live example already runs a
  component on an event: `governance.recommendation` written → run `decision-router`.
- **schedule** → **`platform.schedule`** (the scheduler's cron records). *Gap:* this noun is **not yet
  governed** — it must be proposed through the spec loop so the clock leg matches the triad. Until then the
  scheduler reads an ungoverned schema.
- **request** → an inbound governed interface call (ADR-0058), resolved the same way.

The registry-write-as-event instinct is **correct about the source** and **wrong about where the wiring
lives**. When City Setup writes a `city.onboarding_request`, that write *is* the event (persisted to the
kernel's durable **outbox** as a `platform.event`, drained by the **event relay** to the **automation**
matcher) — but the binding "*this event → run the baseline*" is a **declared `platform.subscription` owned by
the solution/tenant**, not a subscription the drivers hold. The drivers stay dumb: handed an env + token and
told to run. This preserves **authority** (who authorized the run — ADR-0056), **attribution & receipts**
(ADR-0052), **single-writer** state (ADR-0050), and **auditability** (why did this run? — the matched
`platform.subscription` + the receipt).

> **Superseded within this ADR:** an earlier draft proposed a new `platform.trigger` schema. It is dropped —
> `platform.subscription` already covers the event binding, and `platform.schedule` the clock binding. The
> only governance work is to **govern `platform.schedule`**, not to add a noun.

### 5. The execution engine is the single resolver.

The engine (ADR-0050) watches the trigger sources — the registry **outbox** for `event`, the clock for
`schedule`, inbound governed requests for `request` — matches each against **installed** `platform.trigger`
records, and for each match: **mints a scoped run-token → calls `platform.runtime_invoke` → records the
receipt → advances case/workspace state.** The engine is the **single writer of case state**; the invoked
components write only their **domain** data (attributed). The scheduler is demoted from a *runner* to one
*trigger source* feeding the engine.

### 6b. "No custom methods" is enforced at certify, not by discipline.

The rule that a component may only use governed interfaces must be a **gate**, not a convention — authors
(human or AI) drift and reach for ungoverned methods. The certify conformance suite already refused
ungoverned **nouns** (`reads`/`writes` → published `network.schema`) and ungoverned **actor roles**
(`roles` → canonical `network.role`). It now also refuses ungoverned **verbs**: every interface a component
declares it `implements`/`calls`/`consumes` must be a published `network.interface`, or the certificate is
**withheld** (422). No certificate → the launcher/kernel refuse to run it (`COMPONENT_ENFORCE`). This closes
the actor·verb·noun triad: a component that invents a method cannot be certified, installed, or run. (Static
declaration honesty is the certify leg; the broker's read/query/write/fetch surface + declared egress are the
runtime leg — together they mean the *only* ways to interact are governed ones.)

*Verified (2026-08-22):* against the live catalog, a component declaring `platform.runtime_invoke` certifies;
one declaring `my.custom_method` is refused with "ungoverned interface — request them via the spec".

### 6. Component lifecycle is engine-owned and external.

```
author (sandbox) → register → certify(conformance+CA-sign) → publish → install(tenant)
                                                                            │
                    ┌─────────────── per invocation (a "run") ─────────────┘
                    ▼
  trigger fires → engine matches DECLARED trigger → mint scoped run-token →
  resolve placement (profile → certified container, image-lock) → materialize secrets →
  SPAWN entrypoint(env, MODE) → [component does broker I/O under token] →
  exit code + attributed writes → engine records receipt, advances case/workspace state
                    │
                    ▼
  retire / uninstall
```

"on_run" is just *invoke the entrypoint via the one verb*. "on_event" is the *engine* matching a declared
trigger, then invoking that same entrypoint. Lifecycle is a sequence of governed states the engine drives the
component **through**, from the outside — never methods the component implements.

## Consequences

- **Uniform trust for every run.** Cert-check, image-lock, attribution, receipts, and secret-materialization
  apply identically whether a run was scheduled, event-fired, or manual. The 424 City Baseline gap is closed
  at the root, for all sources.
- **No bespoke run methods.** `subprocess.run(<component>)` leaves the scheduler and bridge; there is one way
  to run anything. New trigger *sources* may be added, but never new *run mechanisms*.
- **Language-agnostic & confineable** is preserved by construction — the seam is a process boundary.
- **Auditable causal chains.** "Why did this run?" resolves to a single `platform.trigger` + its owning
  declaration + the receipt — not scattered subscriptions.
- **Cost:** the scheduler and the bridge endpoints must be rewritten as verb-callers (Slice 1), and a real
  `platform.trigger` binding + outbox dispatcher must be built (Slice 2). Until Slice 3, the pipeline script
  still writes workspace state; that write moves into the engine.

## Non-goals / what stays unchanged

- The **broker** I/O contract (ADR-0030) is untouched — it remains the only up-seam.
- **Secrets** still flow only through `materialize`, behind the invoke verb; no component reads Vault directly.

## Slice plan

- **Slice 1 — BUILT (2026-08-22):** the **scheduler** (`run_component`, hence manual "Run now" *and* the cron
  tick) now fires through `platform.runtime_invoke` via the runtime-manager; the `/bridge/run` path forwards
  to it. City Setup's pipeline members already route via `_place()` → manager. Verified: a manual run of an
  installed GEE driver through the scheduler materialised its Vault key and ran (exit 0, 0 batches failed) —
  the path that previously returned `424`. The bare `subprocess.run(<component>)` is gone from the scheduler's
  certified-run path; a direct-host fallback remains **only** when no manager is configured (local dev).
  - *Deliberate exception:* `run_component_dev` (uncertified sandbox drafts) stays on the host `--dev` path —
    an uncertified draft cannot pass the verb's cert/image-lock; this is the ADR-0051 dev relaxation.
  - *Known remaining bespoke path (follow-up):* `app_host._run_ingest_pipeline` still spawns knowledge-ingest
    engines as raw `python3 run.py` subprocesses (and hardcodes `WRITE_TENANT="kmc"`). It predates the broker
    model and must be converged onto the verb like the city-baseline pipeline. Logged in LIMITATIONS.
- **Slice 2:** the governed **`platform.trigger`** binding schema + an **outbox dispatcher** (the ADR-0050
  event slice): registry-write-as-event → engine matches installed triggers → invoke. Ports the one hand-wired
  flood advisor onto it.
- **Slice 3:** move **workspace/case state** writes out of the pipeline script into the engine, making the
  engine the single writer of case state.

## Reflected into the normative specs

- **spec 16 (Runtime & Compute Provider):** placement & invocation — the one invoke verb, the process+token
  seam, MODE-selected invocable verbs.
- **spec 11 (Analytics/Data Engine → Execution Engine):** orchestration & triggers — declared `platform.trigger`
  sources resolving to the invoke verb; the engine as single resolver and single writer of case state.

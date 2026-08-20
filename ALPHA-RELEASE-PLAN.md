# AirawatOS — Alpha Release Plan

> **LOCKED (2026-08-18):** scope = **Balanced** (M1–M6, two flagships + anti-lock-in demo).
> Build order chosen: **start at M2** (Storefront + Inbox + Notification), then M1 (dev loop), M3–M6.
> Progress: M2 — Inbox DONE; Storefront DONE (browse + install-as-grant, pricing metadata). Next: case→task→inbox wiring, then M1 dev loop.

## The one goal (thesis)

> A **solution developer** can build a component/solution against the AirawatOS SDK, test it in a
> **development-environment sandbox tenant**, certify + publish it to the **marketplace**, and a city
> tenant can **install and run** it — demonstrated by a small set of flagship solutions that together
> prove the platform enables *diverse* interactions across Registration/Records, Finance, Services,
> Environment, and Economy.

Alpha is **not** "implement every use case." It's "the platform is real enough that others build on it,"
proven by demonstrators — the rest is a governed backlog (Beta+).

## Acceptance criteria (Alpha is "done" when…)

1. **Dev loop works end-to-end**: `scaffold → build → run in a dev sandbox → certify → publish → install`
   — a developer with the SDK + docs does this without our help, for a driver, an engine, and an app.
2. **Dev sandbox is real**: a `development` tenant runs a developer's *uncertified* drafts; a `production`
   tenant refuses them (ADR-0051 point-of-use enforcement).
3. **Marketplace is browsable + installable** (a storefront app), listings carry kind, provider, pricing
   metadata, and certification status.
4. **Tenant sovereignty holds** through the loop: install = steward grants (reads+writes), uninstall =
   revoke, all admin-approved (already built).
5. **The flagship solutions run** and each demonstrates its distinctive capabilities live (below).
6. **Anti-lock-in is demonstrable**: two vendors' interchangeable components, a tenant swaps one for the
   other with no code change; a tenant moves operators (rehost) keeping identity + data.

## Distinctive capabilities × your 5 categories (coverage matrix)

Legend: ✅ built · 🔨 build for Alpha · ⏭️ Beta

| Capability | Status | Demonstrated in |
|---|---|---|
| Certified marketplace + install-as-grant | ✅ | all |
| **Dev sandbox (env: development)** | 🔨 | dev loop |
| **Developer SDK / CLI loop** | 🔨 | dev loop |
| Decision → receipt → **contest → correct** | ✅ spine, 🔨 UI | Citizen Service |
| **Intelligence ladder** (descriptive→diagnostic→predictive→prescriptive; deterministic→stochastic) | ✅ engine, 🔨 the 4 levels | Flood Response |
| **Event-triggered, cross-agency coordination** | 🔨 (triggers + tasks) | Flood Response |
| **Unified Inbox** (all tasks/notifications, one place) | ✅ case, 🔨 inbox+notify+UI | all |
| **AI-assisted form filling** | 🔨 | Citizen Service |
| **Anti-vendor-lock-in / competing components** | ✅ portability+certs, 🔨 demo | Marketplace demo |
| Procurement: free / priced-feature | 🔨 listing metadata | Marketplace demo |
| Procurement: market-per-request auction | ⏭️ | — |
| Citizen participation → **points → pay/priority** | ⏭️ | (Beta) |
| Service models: one-time (transactional) | 🔨 | Citizen Service |
| Service models: connection (utilities) / appointment (doctor/MRI) | ⏭️ | (Beta) |
| Agency **ERP-by-configuration** (registries/workflows/rules/roles) | ✅ emergent | *property of* every solution |
| Commerce / wallet / billing | ⏭️ | (Beta) |

Category coverage by the flagship demonstrators: **Registration/Records + Services** (Citizen Service),
**Environment + Services** (Flood Response), **Economy** (Marketplace demo), **Finance** (optional
Property-Tax demonstrator, Broad scope only).

## Flagship demonstrators (the minimum that proves the thesis)

Each is a **solution** (pinned member components + schemas) installed into the Kanpur tenant. They share
the built spine; only their declarations differ — which is itself the point (ERP-by-configuration).

1. **Citizen Service — "Birth/Address Certificate"** (Registration/Records + Services)
   Citizen initiates via an **AI-assisted form** → a **Case** → a **rule-based (deterministic) Decision**
   → a signed **Receipt**. Deny path: citizen **contests** → review → **correction** → re-decision. Every
   task/notification lands in the **Unified Inbox** (citizen + clerk). *Proves: services, decision spine,
   receipts, contest/correct, inbox, AI form, one-time service model.*

2. **Flood Response — "Forecast → Pump Dispatch"** (Environment + Services + cross-agency)
   **Descriptive** terrain (built) → **predictive** rainfall forecast (stochastic engine) over low-lying
   cells → **diagnostic** drainage → **prescriptive** "deploy pumps" **Recommendation** → an Authority
   **Decides** → Receipt. A forecast crossing a threshold **event-triggers** a Case that fans **tasks** to
   two agencies (Water Dept + Disaster Mgmt) via the Inbox. A citizen **waterlogging report** feeds the
   same case. *Proves: full intelligence ladder, event-trigger, cross-agency, decision/receipt, inbox,
   citizen participation (lite).*

3. **Marketplace / Anti-lock-in demo** (Economy)
   Two vendors publish **interchangeable** flood-risk engines (same output schema; one free, one with a
   priced feature). The Flood solution runs with either; the tenant **swaps vendors** with no code change;
   the tenant **rehosts** to another operator keeping identity + data. *Proves: market competition,
   anti-vendor-lock-in, procurement (free/priced), portability.*

*(Broad scope only)* 4. **Property Tax** (Finance) — a records + revenue demonstrator: assessment Decision
+ Receipt + a finance ledger fact. Hits the Finance category explicitly.

## Platform gaps to close for the developer loop (the real Alpha build)

- 🔨 **Dev sandbox**: use `tenant.environment`; host/app-host serve a `development` tenant's *own*
  uncertified drafts; `production` refuses (ADR-0051).
- 🔨 **Developer SDK/CLI**: `airawat init|run|test|publish` — scaffold a component from a template, run it
  in the Component Host locally, publish (certify→list). Thin wrapper over what exists.
- 🔨 **Marketplace storefront app** (browse/install; shows pricing + cert status).
- 🔨 **Unified Inbox app** + **Notification service** (platform) + the case→task→inbox wiring.
- 🔨 **Decision/Case app** (see a decision, its receipt, contest it, see the correction).
- 🔨 **AI-assisted form** (a schema-driven form + an LLM-gateway platform service to prefill).
- 🔨 **Rule engine** (deterministic decisions from declared rules) — the Citizen Service decision.
- 🔨 **Forecast engine** (stochastic predictive) + **event trigger** runtime (threshold → case).

## Milestones (sequenced; each is a shippable slice toward Alpha)

- **M1 — Developer loop + dev sandbox.** SDK/CLI + `environment` sandbox relaxation. *Unblocks everyone.*
- **M2 — Storefront + Inbox + Notification.** The two apps + notify service + case→task→inbox.
- **M3 — Citizen Service solution.** AI form + rule engine + decision/receipt/contest/correct, in the inbox.
- **M4 — Flood Response solution.** Forecast engine + intelligence ladder + event trigger + cross-agency tasks.
- **M5 — Marketplace/anti-lock-in demo.** Two competing vendors + pricing + vendor swap + operator rehost.
- **M6 — Alpha hardening + demo.** Docs, a scripted end-to-end demo, close top LIMITATIONS.md items
  (Vault persistence, registry schema-validation-on-write, grant expiry).

## Explicitly deferred to Beta (write it down so it's a decision, not a gap)

Citizen **points economy / wallet / commerce / billing**; **market-per-request auctions**; **connection**
(utilities) & **appointment** (doctor/MRI) service models; multi-city federation of data-sharing; L3/L4
confinement; full ERP-config authoring UI. All are *enabled by* the Alpha spine; none are required to
*prove* it.

## Alpha demo script (what a viewer sees, ~15 min)

1. A **developer** scaffolds a component, runs it in a **dev sandbox** tenant, publishes it → it appears
   in the **marketplace** (dev). A production tenant refuses the uncertified draft.
2. A **city admin** installs the **Citizen Service** solution → grants issued automatically.
3. A **citizen** files a certificate request via an **AI-assisted form** → sees a **Decision + Receipt**
   in their **Inbox**; on denial, **contests**; a clerk's **correction** flips it; the citizen sees the
   re-decision — all in one inbox.
4. A **weather forecast** crosses a threshold → the **Flood** solution auto-opens a case, runs the
   **intelligence ladder** over terrain, recommends pump deployment; **two agencies** get tasks in their
   inboxes; an Authority decides; a citizen's waterlogging report is attached.
5. The city **swaps** the flood-risk engine from **Vendor A → Vendor B** (no code change), then **rehosts**
   the tenant to another **operator** — identity, data, and receipts intact. *No lock-in.*

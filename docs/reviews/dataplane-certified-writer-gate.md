# Data-plane certified-writer gate — finding + fix (ADR-0052 extension)

Status: **A = written · B = shadow shipped** (2026-08-28). Enforce (`DATAPLANE_ENFORCE=1`) deferred until
the blast radius is measured and the writer taxonomy below is implemented.

## The finding (A)

The trust boundary on the registry **write** path is `(authenticated token, own tenant, schema-valid)` —
**not** `(certified component)`. Concretely:

- `POST /v1/registry/objects` (`registry_put`) gates on: a verified writer agent exists (only under
  `PROV_ENFORCE`), the write is bound to the caller's own tenant (`_assert_write_own_tenant`, P0), and the
  object validates against its governed schema. **None of these check that a *fact* was produced by a
  certified component.**
- The certified-component RUN path *is* gated: `_admit_run` (`COMPONENT_ENFORCE=1`) refuses a run whose
  `component_id` isn't certified+installed, and component writes flow through the **broker** (`/v1/write` →
  `b.write`), which stamps `component://…` attribution and enforces per-run scopes.
- But those two paths sit **side by side**. A bare human/tenant token (e.g. a city admin, or a script
  holding that token) can `PUT` straight to `/v1/registry/objects` and inject **any schema-valid fact**
  into a **production** tenant — `cell.*`, `geo.*`, sensor readings — completely unattributed to a
  certified component. This is the sideload hole demonstrated by the first crowd-safety build (the sim
  scripts wrote `cell.crowd_density` into Nashik as `nashik-admin`, bypassing the whole certify spine).

`PROV_ENFORCE` does not close this: it refuses only *anonymous* writes (`agent is None`); a human
`user://…` agent writing facts passes.

## The writer taxonomy (why it's not "component vs not")

Enforcement must not assume every legitimate writer is a confined component. There are (at least) **three**
legitimate write archetypes, and the gate has to admit all three:

| Archetype | Writes | Identity (agent) | Example |
|---|---|---|---|
| **Certified component** | FACTS / measures / derived cells | `component://<id>@<ver>` (via broker) | a sensor driver → `cell.crowd_density`; a crush-risk engine → `cell.crush_risk` |
| **Human authority** | GOVERNANCE / decisions / cases / seed rules | `user://<tenant>/<sub>` | an incident commander admitting a `governance.decision`; a steward seeding a `governance.rule` |
| **Authorized cross-tenant service / aggregator** | unified reads **and** writes spanning MANY agency tenants | `service://<provider>/…` | a unified citizen app, a call-centre, unified billing — the "GPay/PhonePe over banks" pattern: each agency owns its tenant, an aggregator offers citizens one interface across them |

The third archetype is the one that breaks a naive "facts ⇒ certified component only" rule. A shared
service provider is **not** a confined driver and is **not** writing into its own tenant — it holds a
*federated authorization* to act across several agencies' tenants on a citizen's behalf. Today the only
cross-tenant write mechanism is the dev-token (confined to a *development* tenant) and the scoped
platform-service exception (`PLATFORM_CONTROL_SCHEMAS`, control-plane only). Neither models an aggregator.

## The fix — shape

1. **Classify schemas.** Fact/measure families (`cell.`, `geo.`, `obs.`, `air.`, `environment.`, `met.`,
   `demographics.`, `risk.`) are **component-authored**. Governance/console/catalog families
   (`governance.*`, `platform.*`, `viz.*`, `ref.*`, `studio.*`, `network.*`, `space.*`) stay
   **human/service-authorable**. (Env-overridable: `DATAPLANE_SCHEMAS`.)
2. **Gate the human write path** (`registry_put`): a write to a component-authored schema by a
   non-`component://` agent is the hole. **Shadow-log** it now; `403` under `DATAPLANE_ENFORCE`. Dev
   tenants exempt (sandbox authoring).
3. **Before enforce, add the aggregator lane** (net-new, tracked separately): a **cross-tenant
   service authorization** — a signed grant that a participant (the aggregator) may read/write specific
   schemas in a set of *other* tenants, on a citizen's behalf, with every write attributed
   `service://<provider>` **and** stamped with the acting-on-behalf-of subject (PROV `actedOnBehalfOf`).
   This is a federation-interaction concept (ADR-0023/0026 family), not a driver install. The broker's
   reverse-isolation + own-tenant rules (`/v1/write`) are the model to generalise: today a run writes only
   its own tenant; an aggregator run writes a **granted set** of tenants.

## The rollout — B (shipped, shadow)

`kernel/api/app.py`:
- `_is_dataplane_schema(sch)` — prefix match against `DATAPLANE_PREFIXES`.
- `_assert_dataplane_writer(schema, agent, tenant)` — no-op for non-data schemas; pass for `component://`
  agents and development tenants; else **shadow-log once per (schema, agent)**, or `403` under
  `DATAPLANE_ENFORCE`. Called from `registry_put` after `_assert_write_own_tenant`.
- Same rollout shape as `PROV_ENFORCE` / `COMPONENT_ENFORCE`: ship dark, watch the `[dataplane] SHADOW:`
  lines to size the blast radius (which apps/admins/services write facts directly today), fix each writer
  to go through a component or an aggregator grant, then flip enforce.

## Known limits / follow-ups

- **Shadow only** — nothing is blocked yet. Blast radius must be read from logs before enforce.
- **Aggregator lane not built** — flipping enforce before the cross-tenant service-authorization exists
  would block legitimate shared-service-provider writes. Enforce is gated on that lane landing.
- **Retract path** not yet gated (only `put`); a human retracting facts is a separate correction surface.
- **Schema classification is coarse** (prefix-based). `space.*` is left human/service-authorable because
  `space.aoi` is set at onboarding; revisit per-schema if needed.
- Consider making the data-plane families a **governed** attribute of the schema itself (a
  `x-authored-by: component` flag in the schema record) rather than a kernel-side prefix list.

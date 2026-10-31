# Phase-1 Trust-plane migration report — `type_capability_map`

**Status:** FIRST MIGRATION HUMAN GATE — analysis only. **No registry writes. No back-fill. No enforcement flip.**
**Question answered:** *If we replace today's type-based authorization with explicit `CapabilityGrant`s, exactly what authority will every existing participant receive?*

Companion machine-readable artifact: `network/trust/migration/type_capability_map.json`
Deterministic generator (reads real config, not names): `network/trust/migration/build_migration_report.py` · rules: `map_rules.py` (tests `test_map_rules.py`, 6/6).

---

## 0. Headline

Two findings decide this report, and both reduce migration risk:

1. **Today's type authority is almost entirely _declarative_.** A participant type's authority is its
   `provide[]` / `consume[]` matrix (`network/api.py:912-927`), whose legs reference governed nouns
   (schemas) and verbs (interfaces). **`grep` across `network/`, `kernel/`, `broker/` finds no code that
   reads those legs to gate a runtime action.** The real runtime gate is *membership*
   (`_is_member`, `api.py:957`) plus the service provider's own decide (`api.py:1079`). A joined
   member's record even stores `scopes: []` (`api.py:791`). So "type → authority" is, today, a catalog
   the join page renders — not an enforced permission.
2. **The enforced-authority build is not deployed.** The live authority (`airos.airawat.org/network`)
   404s on `/v1/networks` and exposes only the pre-ADR-0116 surface (`/v1/join`, `/v1/participants`).
   So there are **zero** ADR-0116-typed participants in production to migrate right now.

Consequence: migrating legs to `CapabilityGrant`s is not a like-for-like copy — it would **begin
enforcing** authority that is advisory today. That is a behaviour change, not a translation, so the
map is **YELLOW/RED-dominated with no clean GREEN rows**. Back-fill is low-urgency; the real work is a
set of human scope decisions.

---

## 1. Discovery path (config, never the name)

```
participant_type  (configured per network via POST /v1/networks, api.py:901)
      ↓
actual authorization/config rules
      ├─ provide[] / consume[] legs → governed noun/verb refs   (api.py:912-927)   ← the only declared authority
      ├─ identity:"citizen"         → eKYC auto-admit workflow   (api.py:876)       ← workflow flag, not authority
      └─ membership status==approved → the real runtime gate     (api.py:957,1079)  ← migrates to Membership, not a grant
      ↓
observed enforcement = MEMBERSHIP ONLY (legs are not read anywhere)
      ↓
proposed capability mapping (mechanical, below)
```

No authority is inferred from a type's name. The transform consumes only the declared legs.

---

## 2. The transform (what each leg becomes)

Capability grammar `<domain>.<action>[:<qualifier>]`; scope types
`network | credential_type | service | offering_category | event_type | resource` (resource selector
is a Phase-3 stub).

| Declared leg | Direction | Proposed grant | Scope | Verdict |
|---|---|---|---|---|
| `{kind:'verb', ref:<iface>}` | provide | `service.provide:<iface>` v1 | `service:<iface>` | **YELLOW** |
| `{kind:'verb', ref:<iface>}` | consume | `service.call:<iface>` v1 | `service:<iface>` | **YELLOW** |
| `{kind:'noun', ref:<schema>}` | provide/consume | `data.write/read:<schema>` v1 | *(none exists)* | **RED** |
| `'*'` wildcard | provide/consume | — | *(unbounded)* | **RED** |

Grant defaults (both need human confirmation): `grantor = <network>:grant.steward`;
`validity = {valid_from: <migration-instant>, valid_to: null}`.

---

## 3. The three cases — applied

### 🟢 GREEN — maps cleanly to an existing capability
**Count: 0.** No leg qualifies today: interface ids and schema ids are not capability strings, so every
verb leg needs a newly-minted capability, and no noun leg has a representable scope. GREEN only becomes
reachable after capabilities are minted and enforcement intent is settled (i.e. after the YELLOW
decisions below are made).

### 🟡 YELLOW — behaviour exists, scope/meaning ambiguous → human decision
**All verb legs.** A verb leg maps to a `service.provide`/`service.call` capability, **but**:
- the capability string must be **newly minted** (new capability + a v1) — an interface id is not a
  governed capability today;
- **`service` vs `event_type` scope** can't be told from the ref alone (an event verb would scope to
  `event_type`);
- converting it **starts enforcing** a leg that is purely declarative today.

### 🔴 RED — unrepresentable without new semantics → do NOT auto-migrate
- **Noun (data-sharing) legs.** Per-schema data access has **no scope type** in the Phase-1 model
  (scopes are network/credential_type/service/offering_category/event_type/resource; the resource
  selector is a Phase-3 stub). Representing "may read `insurance.policy` data" needs a new scope
  concept. Raise a Change Request to extend the model; do not migrate in Phase 1.
- **Wildcard (`'*'`) legs.** A blanket catalog-wide grant has no bounded scope. Requires an explicit
  human decision: enumerate into discrete grants, or deliberately mint a network-wide wildcard.

---

## 4. Per-type report format

For every configured `(network, participant_type)` the generator emits:

```
Participant type:  <id>            (network: <net>)
Legacy permissions discovered:     <its provide[]/consume[] legs, verbatim from config>
Proposed CapabilityGrant(s):
   capability / capability_version / scope / validity / grantor
Verdict per leg:                   GREEN | YELLOW | RED  (+ the human question)
Not-a-grant notes:                 membership → Membership object; identity:'citizen' → eKYC flag
Affected participants:             <count from a participants export; else "unknown">
```

**Discovered instances right now: none** — the ADR-0116 surface is not deployed and no participant-type
config is committed to the repo (types are created at runtime). The live generator run returns an empty
set with that note. To populate against a current-source deployment:

```
python3 network/trust/migration/build_migration_report.py \
    --base https://<authority>/network \
    --participants participants_export.json     # optional, for affected-counts
```

### Illustrative only (NOT a discovered type) — the `insurer` example

```
Participant type:  insurer
Declared legs:     provide [{verb svc.insurance-enrolment}]   consume [{noun insurance.policy}]
Proposed grants:
  1. 🟡 capability: service.provide:svc.insurance-enrolment   v1   scope: service:svc.insurance-enrolment
  2. 🔴 (would be data.read:insurance.policy) — no scope type for schema data → do NOT auto-migrate
```

---

## 5. Summary

| Metric | Value |
|---|---|
| Legacy participant types found (discovered, live) | **0** (ADR-0116 surface not deployed; none committed in repo) |
| Clean mappings (GREEN) | **0** |
| Ambiguous mappings (YELLOW) | **0 discovered** — *rule: every verb leg* |
| Unrepresentable mappings (RED) | **0 discovered** — *rule: every noun leg + every `'*'`* |
| Existing participants affected | **Requires a live authenticated query — not run at this gate** |
| Proposed grants to create | **0 discovered** (one per YELLOW verb leg once types exist) |
| New capabilities required | **0 discovered** (one per distinct verb interface) |
| New capability versions required | **0 discovered** (a v1 per new capability) |

> Counts are **not fabricated**. Where a number needs the live registry it says so, with the exact
> command to produce it. The `0`s are a true statement about today's deployment + repo, not an estimate.

### The requested master table (schema; rows populate from a live/current-source run)

| Legacy type | Legacy authority (declared leg) | Proposed capability | Ver | Scope | Participants | Confidence | Decision needed |
|---|---|---|---:|---|---:|---|---|
| *(verb-leg row)* | `verb <iface>` (provide) | `service.provide:<iface>` | 1 | `service:<iface>` | *live* | YELLOW | mint capability; service-vs-event scope; enforce-vs-declare |
| *(verb-leg row)* | `verb <iface>` (consume) | `service.call:<iface>` | 1 | `service:<iface>` | *live* | YELLOW | as above |
| *(noun-leg row)* | `noun <schema>` | `data.read/write:<schema>` | 1 | *none* | *live* | RED | extend model (new scope) before migrating |
| *(wildcard row)* | `'*'` | — | — | *unbounded* | *live* | RED | enumerate or mint network-wide wildcard |

---

## 6. Open decisions for the reviewer (before any back-fill)

1. **Enforce-vs-declare.** Do we *want* provide/consume legs to become enforced authority? (Today they
   are advisory; grants would gate real calls.)
2. **Verb scope.** Confirm `service` scope for request/response interfaces and a rule for routing event
   verbs to `event_type` scope.
3. **Capability minting.** Approve the `service.provide:*` / `service.call:*` capability family and
   their v1 catalog entries (a prerequisite the back-fill depends on).
4. **Noun legs (RED).** Approve a Change Request to add a data/schema scope (or adopt the Phase-3
   resource selector) — or decide data-sharing legs are out of scope for Phase 1.
5. **Wildcards (RED).** Decide enumeration vs an explicit network-wide wildcard grant.
6. **Membership.** Confirm membership migrates to the `Membership` object (already built) and is *not*
   a `CapabilityGrant`.

---

## 7. Gate

```
Generate type_capability_map   ✅ (rules + generator + tests; discovered instances empty today)
Generate migration report      ✅ (this document)
        ↓
NO BACK-FILL                    ✅ (nothing written; shadow authorize stays observational)
        ↓
HUMAN REVIEW                    ← WE STOP HERE
```

The Commit-C shadow `authorize()` call site stays observational; it is not touched by this report and
remains log-only until grants are human-approved and back-filled.

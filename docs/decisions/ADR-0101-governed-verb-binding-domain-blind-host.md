# ADR-0101 — Governed verb binding: the app-host is a domain-blind dispatcher

**Status:** Accepted — implemented, live on reference image `0.2.47` (2026-09-20)
**Relates to:** ADR-0087 (governed bridge — **this delivers its R3**: the verb→impl map becomes data) · ADR-0090 (interface bindings + conformance — the per-tenant *override*, unchanged) · ADR-0091 / ADR-0091-V3 (few generic verbs, domain expressed as data) · ADR-0093 (retire baking — nothing domain-specific baked into a platform service) · ADR-0094 (stewardship separation — components author their own declarations) · ADR-0022/0030 (everything-is-a-component; clean-room engines behind the broker)

## Context

The reference **app-host** dispatches every `/bridge/<verb>` call. For engine-backed verbs it resolved the target from two module-level Python dicts baked into the host:

- `ENGINE_VERBS` — `verb → engine component id` (the default binding + the router's verb allow-list).
- `BRIDGE_VERBS` — `verb → governed interface label` (the confinement/audit map, and the interface used for per-tenant binding swaps).

`ENGINE_VERBS` had grown to **~70 domain verbs across 21 engines** — `funding-*`, `welfare-*`, `gap-scan`, `campaign-*`, `payroll-*`, `chat-*`, `mail-*`, and so on. That is **domain solution logic baked into a platform service**: adding a domain verb, or installing a solution that introduces one, required editing the shared host and **rebaking + redeploying the reference image**. This is the same coupling ADR-0087 flagged for `ENGINE_VERBS` "one layer up," and it contradicts ADR-0091 (domain in config, not code), ADR-0093 (nothing baked), and ADR-0094 (a component declares its own capabilities).

ADR-0090 had already made the *per-tenant override* governed data (`governance.interface_binding`, conformance-gated), and ADR-0091-V3c made *verb aliases* governed data (`platform.verb_alias`, read via `_alias_specs()`). But the **default binding + allow-list** — the floor those resolvers fall back to — was still the hardcoded dict. ADR-0087 named the finish line as **R3: the map itself becomes data.**

A prerequisite landed first: the 7278-line `app_host.py` was split into `hostcore.py` (shared foundation) + `routes/*` mixins (see [[app-host-modularization]]), making the host structurally "boring" enough to carry only platform machinery.

## Decision

**The default verb→engine binding and the verb allow-list are governed data, not host code.**

1. **Schema `platform.verb_binding`** — `{ verb, component, interface, scope: "default", enabled }`. Governed through the network like any platform schema. Records are the *platform default* (the floor); they do **not** replace ADR-0090's per-tenant `governance.interface_binding` override, which stays exactly as-is and still gates the *actual* implementation on conformance.

2. **The host reads it** — `_verb_bindings()` mirrors `_alias_specs()`: a short-TTL (30s) cache over `platform.verb_binding`, exposing `{verb→component, verb→interface}`. `_active_impl` resolves the default from this governed map **first**; the `do_POST` router admits a `/bridge/<verb>` if it is in the governed map **or** the baked dict.

3. **The dict becomes a bootstrap floor** — `ENGINE_VERBS` is shrunk from ~70 entries to **the ~7 generic platform verbs** (`evaluate`, `rule-eval`, the five `lifecycle-*`). These stay baked so the platform can dispatch its generic planes even when the registry is cold or unreachable; the reader also degrades to its last-good cache. Everything domain-specific is data.

4. **Publish self-registers** — `project-publish` calls `_register_verb_bindings(cid, meta)`: for each entry in the component's `meta.verbs`, it writes a `platform.verb_binding` (owned by the platform authority, `ds:airawat`, with the steward token — the same tenant the reader uses) and busts the cache. So a newly-published engine's verbs dispatch **immediately, with zero app-host edit and no reference-image rebake.**

`BRIDGE_VERBS` is deliberately **retained**: it is the broader *confinement/audit* label map (it labels host-native handlers and `app-internal`/`gap:` paths, not only engine verbs), a separate concern from the domain-engine coupling this ADR removes; `_active_impl` still reads its interface labels for the swappable generic verbs.

## Consequences

- **A new generic verb is now pure governance, end-to-end** — author → publish → live within one cache TTL. Adding a verb in the network never touches the host. This is ADR-0087 R3, delivered.
- **The host is domain-blind for dispatch** — it carries a 7-verb floor + a governed read; it no longer knows about `funding`, `welfare`, `tax`, `chat`, … The domain lives in the components + their governed bindings.
- **Resilience is explicit, not accidental** — the bootstrap floor + last-good cache keep the platform dispatchable through a registry outage; only *newly-added* domain verbs wait on the registry (acceptable — they are solution features, not platform-critical).
- **Security is unchanged** — `platform.verb_binding` sets only the default; the *actual* implementation a tenant runs is still selected by `governance.interface_binding` and admitted only on a passing conformance result (ADR-0090). The record is a governed, attributed write.
- **Migration** — a one-time backfill seeded a `platform.verb_binding` for each former `ENGINE_VERBS` entry (`platform-spec/reference/seeds/verb_binding_backfill.*`); parity was asserted (all verbs resolve to the same engine). Going forward, publish emits the records, so the seed is not re-run.

### Follow-ups (minor)

- Prune the retired `*-legacy` dead handlers left over from the ADR-0091 verb-consolidation migration.
- Consider governing `BRIDGE_VERBS` (the confinement/audit label map) the same way — a separate, larger slice, since it also labels host-native surfaces.
- Consider making `platform.verb_binding` **platform-visible** (readable by any authenticated token, like the interface catalog) so third-party developers' bindings need not be re-homed to `ds:airawat`; today the host writes them under the platform authority to match its steward-scoped read.

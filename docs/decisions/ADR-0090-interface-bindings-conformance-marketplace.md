# ADR-0090 — Governed interface bindings + conformance suites: engines as interchangeable marketplace parts

Status: Proposed (2026-09-16)
Related: ADR-0058 (interaction contracts / interfaces) · ADR-0059 (kernel publishes interfaces + declares
conformance) · ADR-0022 (everything-is-a-component) · ADR-0030 (SDK + broker clean-room) · ADR-0016/0080
(marketplace / store + publish review) · ADR-0087 (governed bridge — R3 = the verb→impl map becomes data) ·
ADR-0088 (rule engine + domain-services spectrum)

## Context

Engines are certified components that **implement a governed interface** (e.g. `rule-engine` implements
`governance.rule_eval@0.1.0`; a workflow engine would implement `platform.workflow_run@…`). In principle any
developer can ship a competing implementation of the same interface and a tenant can install the best one — the
callers depend on the *interface*, not the vendor. Two things block that from being real today:

1. **The binding is code, not data.** The app-host hardcodes `ENGINE_VERBS[verb] = <one cid>`. There is no
   per-tenant/per-solution way to choose *which* certified implementation of an interface is active. (The
   network already has an `interface → endpoint` binding registry + `/v1/interfaces/bind|resolve`, unused by the
   host dispatch.)
2. **Conformance is structural, not behavioral.** Certify checks request/response *shape*. It does not prove two
   implementations of `governance.rule_eval` return the *same decision for the same rules* — so swapping them
   isn't provably safe.

This ADR closes both, turning "engines could compete" into "engines are interchangeable, certified marketplace
parts a tenant can choose."

## Decision

### 1. `governance.interface_binding` — the active implementation is governed data (ADR-0087 R3)
A binding says "for interface X, in scope Y, the active implementation is component C@v." Signed like a grant.
```jsonc
{ "schema": "governance.interface_binding",
  "id": "ds:kmc:binding/governance.rule_eval",
  "interface": "governance.rule_eval@0.1.0",
  "component": "ds:acme:engine/fast-rule-engine", "version": "1.2.0",
  "scope": "tenant", "tenant": "kmc",            // platform (default) | tenant (override)
  "status": "active", "bound_by": "user://kmc/admin", "bound_at": "…" }
```
- **Resolution order** (host dispatch): tenant binding → platform default binding → the reference implementation.
  So with no binding, behaviour is exactly today's (the reference engine) — non-breaking.
- **Host change (R3):** `_dispatch` resolves `verb → interface → active component` from the binding registry
  (cached), replacing the constant `ENGINE_VERBS` lookup. Same identity/obo/grant path; only the *target* is now
  data. `installing an implementation` = writing a binding.
- **`binding_policy` on the interface** governs who may bind what:
  - `open` — any implementation that is **conformant** (below) may be bound by a tenant admin (rule, workflow, ML).
  - `locked` — only the platform reference implementation may be bound (security-critical engines, e.g. the
    authz/scope resolver). Same substrate, stricter policy.

### 2. `governance.conformance_suite` — behavioral contract an implementation must pass
An interface carries (or references) a governed suite of behavioral cases owned by the interface's steward
(the standards body), versioned with the interface.
```jsonc
{ "schema": "governance.conformance_suite",
  "id": "ds:airawat:conformance/governance.rule_eval@0.1.0",
  "interface": "governance.rule_eval@0.1.0", "version": "0.1.0",
  "cases": [
    { "name": "first-match", "input": {"ruleset":"t","facts":{"a":1}}, "seed_rules":[…], "expect": {"decision": {"effect":"deny"}, "trace_len": 1} },
    { "name": "most-specific wins", "input": {…}, "expect": {…} },
    { "name": "no match → null", "input": {…}, "expect": {"decision": null} }
  ],
  "properties": [ "same rules+facts ⇒ same decision (determinism)", "trace names only matched rules" ] }
```
- **Certify runs it.** When a component declares `implements: [iface@ver]`, the certifier executes the interface's
  conformance suite against the candidate (in the clean-room / a dev-run) and issues the certificate with an
  attestation **only if every case passes**:
  ```jsonc
  "implements_verified": [ { "interface": "governance.rule_eval@0.1.0", "suite_version": "0.1.0", "at": "…" } ]
  ```
  Structural shape check stays (S-tier); this adds the **behavioral** gate.
- **A binding is only admissible if the component's cert carries `implements_verified` for that interface@ver.**
  So a tenant can only bind engines that provably behave to spec — swapping is safe by construction.
- Suites are **versioned and grow**: "conformant" always means "against suite vX." A new edge case → suite vX+1 →
  implementations re-verify. Property-based cases (determinism, trace correctness) complement example cases.

### 3. Marketplace surface
The store already lists components; add a **"implementations of interface X"** view (filter `implements=iface`)
showing each candidate's `implements_verified` badge + optional advisory benchmarks (latency/cost — metadata,
NOT part of pass/fail). A tenant admin (or a solution at install) **picks one → writes a binding**. Champion/
challenger is a natural extension: bind one as active, run a second in **shadow** and compare (reusing the
ADR-0088-S2b shadow-compare pattern) before switching.

## Worked example — two rule engines competing on `governance.rule_eval`
1. Airawat ships the reference `ds:airawat:engine/rule-engine@0.2.0`, conformant to suite 0.1.0 → platform
   default binding.
2. Acme builds `ds:acme:engine/fast-rule-engine` (RETE-net, 10× faster). At publish, certify runs the
   `governance.rule_eval@0.1.0` suite → passes → cert gets `implements_verified`. It appears in the marketplace
   under the interface with a "conformant + 10× faster" card.
3. `kmc` admin binds `fast-rule-engine` for tenant kmc. Every `rule-eval` call in kmc now routes to Acme's
   engine — hr-workflows, Data-Exchange, data-visibility all keep working unchanged, because they depend on the
   *interface*, and the suite guarantees identical decisions.
4. `nashik` keeps the reference. Same platform, different engine, both safe.
Meanwhile `authz.check` is `binding_policy: locked` → no tenant may swap the authz engine.

## Migration — staged, non-breaking
- **R3a — binding-as-data (fallback):** add `governance.interface_binding`; host resolves binding → falls back to
  today's hardcoded default. Zero behaviour change; the seam is now data. (Pairs with ADR-0087 R2/R3.)
- **R3b — conformance suite for ONE interface:** add `governance.conformance_suite`; author the
  `governance.rule_eval@0.1.0` suite; make certify run it + attest `implements_verified`. Re-certify the
  reference rule-engine so it carries the badge.
- **R3c — prove competition:** build a *second* rule engine (even a trivially-different one), pass conformance,
  publish, bind it in a sandbox tenant, and show `rule-eval` routing to it with identical results (shadow first).
- **R3d — marketplace surface + `binding_policy`:** the "implementations of interface X" store view + tenant bind
  UI (Setup); mark authz/security interfaces `locked`.

## Consequences
- Engines become **interchangeable, certified parts**: a tenant installs the best rule/workflow/ML engine like
  any component; the platform trusts its own enforcement + the conformance attestation, not the vendor.
- The verb→implementation map is finally **data** — completing ADR-0087's collapse (no hardcoded engine wiring).
- A real plug-in market for the *reusable engine layer*, with the security-critical engines fenced off (`locked`).

### Risks / honest edges
- **A suite only proves the cases it covers.** A conformant engine can still differ on an untested input.
  Mitigation: property-based invariants (determinism, trace correctness), versioned suites that grow from real
  incidents, and shadow-run before cutover.
- **Behavioral conformance is clean for PURE engines (rule, workflow, classify); murky for effect/capability
  services** (notification, model-gateway — nondeterministic / side-effecting). Those stay single-impl or test via
  contract mocks; the marketplace sweet spot is the pure-compute engines. (Matches the ADR-0089 "pure vs
  capability" split.)
- **Selection criteria beyond pass/fail** (speed, cost) are advisory metadata, not conformance — don't fold them
  into the gate.
- **Binding lookup on the hot path** must be cached (like the schema/def caches) or dispatch slows.
- **Non-goal:** opening every interface. `binding_policy: locked` is the default for anything security- or
  consistency-critical; interfaces are opened to competition deliberately.

## Recommended first build
R3a + R3b on **`governance.rule_eval`**: add `governance.interface_binding` (host resolves with fallback) +
`governance.conformance_suite`, author the rule-eval suite, make certify run it and attest, and re-certify the
reference engine. That makes the seam data + gives the first interface a behavioral contract — the two
prerequisites for a real engine marketplace — without yet opening a live interface to third parties.

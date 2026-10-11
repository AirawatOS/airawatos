# ADR-0111 — Agency public presence as channel-agnostic public-interaction infrastructure

- **Status:** Proposed (2026-10-11, rev.2 — adopts the four-layer / three-abstraction refinement)
- **Builds on:** [[ADR-0077]] (design system + WCAG 2.2 AA), [[ADR-0067]] (service directory), [[ADR-0058]] (interaction contracts), [[ADR-0048]]/[[ADR-0270]] (universal Inbox + `platform.case`), [[ADR-0041]] (lineage/`prov.derivation`), [[ADR-0057]] (content-anchored citations), [[ADR-0056]] (decided-change-request = governed approval lifecycle), [[ADR-0081]] (Personal Agent), [[ADR-0100]] (Campaign), [[ADR-0072]]/[[ADR-0087]] (cross-tenant federation), i18n spine, public-apps/`/t/<tenant>`.
- **Compliance baseline:** GIGW 3.0; National Government Services Portal (cross-institution service discovery).

## Context

Every tenant gets a no-login public home at `/t/<tenant>`. The ask is to grow it into a configurable government website. But a **website is one channel**; agencies also reach the public via chat/WhatsApp, mobile, call-centre, social, and — increasingly — **AI assistants** acting on a citizen's behalf. If we build "a website framework" we solve one channel and rebuild the rest.

The correct abstraction is therefore **not a site but an *Agency Public Interface*** — the governed projection of an institution's identity, information, services, and interactions — of which a website is **one representation**. A website has pages, menus, and sections; a public interface has **information, capabilities, interactions, policies, and state**. Pages are only one way to organise those.

AirawatOS already holds most of the substance as governed data + declared interactions. The design leverage is to treat every channel as an **adapter over a channel-agnostic capability spine**, and to keep **capabilities separate from their presentation**.

## Decision

### 1. Four layers; capabilities separated from presentation

| Layer | Responsibility | AirawatOS implementation |
|---|---|---|
| **1 · Institutional model** | Who the agency is, its jurisdiction, authority | `platform.agency_profile` (governed this ADR), tenant/participant, roles ([[ADR-0028]]) |
| **2 · Public capability model** | What it publishes, provides, discloses, accepts | `platform.capability` (**index**) over service offerings, publications, datasets, engagement forms |
| **3 · Experience composition** | How capabilities are organised per audience/context | `platform.experience` (web config = `platform.site` within it) |
| **4 · Channel adapters** | How capabilities are presented + interactions executed | Website (SSR), PWA, WhatsApp, voice/IVR, social, APIs/MCP |

The worked example: a **water-connection** capability declares eligibility, documents, fees, application schema, provider, workflow, tracking, policies — **once**. The website renders a form; WhatsApp a conversational flow; an AI agent discovers the contract and invokes authorized operations; a call-centre operator a guided interface. One capability, four renderings. No per-channel reimplementation of the service.

### 2. Three first-class abstractions + a publication contract — as *views over existing rails*, not a new store

The governing discipline (per the one-subject-one-noun rule, [[ADR-0060]] §3a): **`platform.capability` is a typed discovery *index* that references existing records — never a copy.** Each new noun passes the reuse-or-propose gate.

| Abstraction | Status | Reconciliation (extend, don't fork) |
|---|---|---|
| `platform.agency_profile` | ✅ governed | Institutional identity. Done. |
| `platform.capability` | **new (index)** | Points at a **service offering** ([[ADR-0067]]) · a `platform.publication` · a **dataset/`viz.layer`** · an **engagement form / `platform.case` type** ([[ADR-0048]]). The registry is a *projection*. |
| `platform.experience` | **new** | Composition; `platform.site` becomes one channel config inside it. |
| `platform.publication` | **new** | A **derived, approved projection** (`prov.derivation`, [[ADR-0041]]) of a system-of-record fact, with the **decided-change-request** ([[ADR-0056]]) as its approval lifecycle. Not the system of record. |

### 3. The canonical `platform.capability` model (the pivotal spec)

A capability is the atom of the public interface: the unit a web composer *and* an AI agent discover. It is an `entity` (index record) with these facets:

- **Identity & type** — `capability_id`, `publisher` (→ agency), `type ∈ {information, service, disclosure, dataset, consultation, grievance, subscription, map, directory}`, `title`, `summary`, `icon`.
- **Applicability** — `jurisdiction`, `audience[] ∈ {citizen, business, institution, visitor}`, `languages[]`, `effective_from`/`effective_until`.
- **Binding (the reference, never a copy)** — `target_ref` + `target_kind` pointing at the real record: `service_offering@id` | `publication@id` | `schema`+`app_id` (dataset) | `case_type` (engagement) | `viz.layer@id` (map).
- **Interactions** — `operations[]` drawn from the bound record's **interaction contracts** ([[ADR-0058]]): e.g. `discover`, `read`, `apply`, `pay`, `track`, `subscribe`, `respond`. Each carries `authorization` (none / identified / role) + `consent_required`.
- **Channel compatibility** — `channels[] ⊆ {web, whatsapp, voice, app, social, machine}` (not every capability fits every channel).
- **Discovery metadata** — `keywords[]`, `topics[]`, `related[]`, and the structured-data mapping (schema.org type) for the machine surface.
- **Trust** — `source` (authoritative record id), `approval` (decision id), `provenance_contract: true`.

Relationships: a capability **references** a service offering (transactional), a publication (informational), a dataset/layer (data), or a case-type (engagement) — it **unifies discovery** across the service directory, Knowledge layer, publication lifecycle, and engagement system without owning any of them. The **Public Capability Registry** is `GET` over `platform.capability` filtered by audience/jurisdiction/channel — the one discovery interface web composition and AI agents both use.

### 4. `platform.publication` — the public projection

Publishing ≠ composing. A publication is governed public information with a lifecycle independent of its system of record: `publisher`, `content_type` (notice / order / scheme / budget / rate / plan / eligibility), `jurisdiction`, `audience`, `language` variants, `effective_from`/`effective_until`, `published_at`, `review_due_at`, `source` (authoritative record), `approval` (decision), **immutable `version`**, `status ∈ {draft, approved, published, superseded, archived}`. A municipal budget stays in finance; the publication is its *approved public projection* — preserving the system-of-record / system-of-interaction split.

### 5. Experience composition + archetypes

`platform.experience` declares audience & purpose, the discoverable capabilities, navigation/hierarchy, presentation components, interaction journeys, supported channels, and localization/accessibility requirements. A website is one experience config. **Agency archetypes** (municipal corporation, development authority, water utility, district administration, state department, regulator, public institution) share the same design tokens, accessibility rules, identity components, search, and content primitives, and differ only in **default composition** — selecting an archetype *provisions* a sensible default experience the agency then configures. The homepage splits into a **universal agency shell** (identity, jurisdiction, language, search, accessibility, primary nav, contact, mandatory disclosures, footer) and a **configurable experience** (priority services, notices, transparency dashboards like PED, maps, campaigns, agency apps).

### 6. Channels, continuity, and the trust envelope

- **Adapters** render capabilities; they never hold authoritative state.
- **Interaction continuity** reuses the existing channel-independent spine — **`platform.case`** ([[ADR-0048]]/[[ADR-0270]]): a service instance *is* a case; the only net-new piece is a thin **cross-channel session/identity token** that stitches an anonymous web start → a WhatsApp number → an at-counter identified citizen onto the same case.
- **Trust as an interaction contract, not an AI feature.** Every public response — web, chat, or AI summary — cites the **same `publication.version`**, traceable to (1) issuing authority, (2) authoritative source, (3) approved publication version, (4) jurisdiction + validity. A **public-response envelope** separates *authoritative source statement* from *AI interpretation*. This extends the platform's existing stance (`prov` on every fact; content-anchored citations [[ADR-0057]]; the assist is forbidden from inventing figures).

### 7. Machine surface (additive, not MCP-only)

Conventional, documented surfaces are primary: **schema.org JSON-LD**, `sitemap.xml`, **OpenAPI** over the public read + service operations, and structured metadata. An **agents manifest** / MCP endpoint is *one additional* adapter. **Read is open; any state-changing operation requires explicit authorization + user consent** (reusing [[ADR-0067]] S5 consent). Slice-1 already ships the read-only web + JSON-LD + sitemap + agents-manifest surface.

## Enforcement

- **GIGW from the start** (not deferred to the end): accessibility (WCAG 2.2 AA + axe gate — have), mandatory institutional disclosures, content ownership, security, and publication controls are enforced from slice 1; comprehensive GIGW conformance checks phase in.
- **One-subject-one-noun gate** on every new abstraction (capability/experience/publication) — reuse-or-propose ([[ADR-0038]]/[[ADR-0060]]).
- **Consent + authorization** on any non-read operation exposed to any channel, including AI.

## Slices (re-sequenced)

1. `platform.agency_profile` + Gov theme + **agency archetypes** — consistent public identity. *(profile + SSR web adapter + machine surface already live; theme/archetypes next.)*
2. **Public Capability Registry + `platform.publication` contracts** — the channel-independent foundation.
3. `platform.experience` + Site Studio — configurable composition.
4. SSR + search + structured data + public discovery APIs (OpenAPI) — discoverability. *(web+JSON-LD+sitemap+manifest done; OpenAPI + full SSR of pages next.)*
5. **Conversational channel adapter** — validates genuine channel-independence.
6. Unified Engagement Console — consolidate inbound/outbound.
7. Additional adapters (voice/IVR/social) + cross-agency experiences.

## Consequences

- **From websites to digital public institutions.** Every tenant becomes a digitally accessible institution that progressively activates capabilities (profile → notices → tax → grievance → PED → GIS → participatory planning); each new capability auto-composes into supported channels, subject to publication + access policy.
- **Cross-agency experiences are reachable on existing rails.** A *"Moving to a New Home"* experience composing property registration + tax + water + electricity + address-update across agencies is the **person-centric jurisdiction/service federation** already in flight (+ the cross-tenant aggregator lane, [[ADR-0072]]/[[ADR-0087]]) — `platform.experience` composes capabilities across tenants through federation/grant rails, preserving each institution's authority and records.
- A real SSR path now coexists with the sandboxed CSR apps; the two compose as SSR shell → optional CSR island.

## Non-goals

- Not making `platform.capability`/`publication` systems of record — they are indexes/projections over existing stores.
- Not a generic page-builder CMS beyond the governed capability/section model (constrained for consistency + accessibility).
- Not building all channel adapters now (slices 5–7); the read-only web + machine surface ships first.

# ADR-0111 — Agency public presence: one design system, many channels, a machine-readable surface

- **Status:** Proposed (2026-10-11)
- **Builds on:** [[ADR-0077]] (governed design system + WCAG 2.2 AA), [[ADR-0067]] (service directory + init→provider→fulfil), [[ADR-0048]] (universal Inbox + Case), [[ADR-0058]] (interaction contracts), [[ADR-0081]] (Personal Agent), [[ADR-0100]] (generic Campaign), public-apps/`/t/<tenant>` (the no-login tenant home)
- **Relates to:** [[ADR-0056]] (decided-change-request = governed publishing lifecycle), [[ADR-0028]] (roles/RBAC), [[ADR-0100]]/[[ADR-0110]] (transparency surfaces: Campaign, PED), i18n spine, [[ADR-0057]] (content-anchored citations)
- **Compliance baseline:** GIGW 3.0 (guidelines.india.gov.in), National Government Services Portal (services.india.gov.in) — user-centric IA, accessibility, multilingual, lifecycle, interoperability.

## Context

Every tenant already gets a no-login public home at `/t/<tenant>` that lists its public apps (built alongside [[ADR-0110]]). The ask is to grow that into a full, **configurable agency website** — municipal corporation, development authority, water board, transport dept, district admin, regulator — so each agency keeps its identity while citizens get a familiar experience.

But a website is **one channel**. Agencies also reach the public via chat/WhatsApp, a mobile app, a call centre, and social media; and increasingly via **AI assistants** that answer questions and transact on a citizen's behalf. If we build "a website framework" we solve one channel and rebuild the rest. The platform already holds most of the substance as **governed data + declared service interactions**, so the leverage is to treat the website as a **renderer over a channel-agnostic public-interaction spine**, not as the system of record.

**What already exists** (reuse, don't rebuild): the governed design system + WCAG gate ([[ADR-0077]]), i18n (en+hi), the service directory ([[ADR-0067]]), the universal Inbox/Case ([[ADR-0048]]), Campaign ([[ADR-0100]]), News (`news.item`), geography (`space.ward`, `viz.layer`, `geo.facility`), transparency surfaces (PED, procurement.tender, finance/budget), the Personal Agent ([[ADR-0081]]) + grounded assist, governed writes + RBAC + the decided-change-request lifecycle ([[ADR-0056]]), and publish→live app bundles. The genuine gaps are four: a **site-composition construct**, **server-side rendering + a machine-readable surface**, a **GIGW theme pack + conformance gate**, and **channel adapters + an engagement console**.

## Decision

### 1. Author once (a channel-agnostic spine); render many (adapters)

An agency's public presence is **governed content + services + engagement**, authored once and rendered by per-channel **adapters**. The website is the first adapter; chat, mobile, IVR, social, and a **machine/AI surface** are peers. One publish → every channel. No channel is the system of record.

### 2. Three architecturally-separable layers (shared chrome)

- **Presentation — a GIGW "Gov" theme pack over `aos.css`.** The GIGW header (national emblem + configurable agency identity + jurisdiction), mega-menu, breadcrumbs, mandatory footer (RTI, accessibility statement, policies, contact), an **accessibility toolbar**, and a language switcher. *One design system; per-agency identity override* via `agency.profile` (name, seal/logo, colours, jurisdiction, contact). WCAG 2.2 AA is already enforced; a GIGW checklist gate joins the axe gate at publish.
- **Structure — `platform.site`.** A governed declaration of the agency's **menu + pages + sections**, each section binding to a content type or an **installed public app** (PED, a service, a map). Generalises the hardcoded `/t/<tenant>` page into a configurable site, authored in a Site Studio, published→live via the existing bundle/overlay. The three website functions stay separable: **institutional presence** (mandate, org, officials), **public information & engagement** (notices, schemes, consultations, news), **service delivery** (apply/pay/track).
- **Substance — the governed spine.** Small content types (`site.page`, `site.notice`, `gov.scheme`, `gov.official`, `gov.office`, `gov.consultation`) + the service directory + engagement (grievance/consultation/feedback → Inbox/Case). These are data and declared interactions, never web-specific.

### 3. The machine-readable surface makes it AI- and search-native (the wedge)

Because services are **declared interaction contracts** over **governed structured data**, an assistant — ours on-site, or an external search/AI assistant — can **discover and transact**, with provenance, not just read text. Every agency site therefore emits:
- **schema.org JSON-LD** — `GovernmentOrganization` (identity) + an `ItemList` of `GovernmentService` (its public services/apps) + `Dataset` for each transparency dataset (e.g. PED). *(search + AI understanding)*
- **`/t/<tenant>/sitemap.xml`** + crawl directives + canonical URLs. *(search indexing)*
- **An agents manifest** (`/t/<tenant>/.well-known/ai-plugin.json`, an OpenAI-plugin-shaped descriptor pointing at the public-read query + grounded-assist + service endpoints). *(external AI can act on a citizen's behalf)*
- **Server-side rendering** of public *pages* (the site shell is already SSR; transactional apps stay CSR behind SSR shells). *(crawlers/AI see real content, not an empty SPA)*

This is the differentiator: most government sites are human-only and SPA-opaque. Answer-engine-ready, machine-actionable public services are rare.

### 4. Channels as adapters; one engagement console

- **Web** — the SSR site (primary).
- **Chat/WhatsApp** — the Personal Agent + grounded assist over the service directory (discover → apply → track, cited).
- **Mobile/PWA** — app-host bundle.
- **Call-centre/IVR** — scripts generated from the service declarations; the same agent backs a human console.
- **Social** — Campaign auto-drafts posts from new notices.
- **Engagement Console** — the agency authors content once, sees inbound across channels in the **universal Inbox**, and schedules outbound via **Campaign**. One tool to manage public communications, not five.

### 5. Cross-cutting guarantees

Multilingual (i18n + per-locale content + MT fallback + `hreflang`); mobile (responsive `aos.css` + PWA); accessibility (WCAG 2.2 AA + axe gate + GIGW toolbar + conformance gate); governed lifecycle (decided-change-request + RBAC + Inbox approvals — GIGW's approval/lifecycle requirement).

## Slices

1. **SEO/AI-discoverable site (this ADR's first build).** Govern `platform.agency_profile`; make `/t/<tenant>` render a full SEO head + **schema.org JSON-LD** + identity chrome; add `/t/<tenant>/sitemap.xml` and the **agents manifest**. Proves the wedge end-to-end on janaagraha, with PED as the first `Dataset`/service.
2. **`agency.profile` + GIGW Gov theme pack** — identity-configured, GIGW-compliant shell.
3. **`platform.site` + Site Studio** — configurable menu/pages/sections.
4. **Channel adapters + Engagement Console** — chat over the service directory; unified inbound/outbound.
5. **GIGW conformance gate** — a publish-time checklist alongside the axe gate.

## Consequences

- A second agency (water board, dev authority, district admin) is **config over the same spine** — the federation story applied to public presence.
- The machine surface turns every agency into an **AI-actionable public service**, not just a readable page — a structural advantage as answer engines mediate more citizen interactions.
- SSR + a governed site construct add a real server-render path distinct from the sandboxed CSR apps; the two must compose cleanly (SSR shell → optional CSR app island).
- GIGW compliance becomes a gate, not a one-time audit.

## Non-goals

- Not replacing the transactional apps' CSR runtime — only server-rendering the site *pages* and wrapping apps in SSR shells.
- Not building all channel adapters now (slice 4); slice 1 ships web + the machine/AI surface.
- Not a generic page-builder CMS beyond the governed section/content model (deliberately constrained for consistency + accessibility).

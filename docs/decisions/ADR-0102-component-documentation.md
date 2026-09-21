# ADR-0102 — Component documentation: packaged, authored in Studio, rendered by a shared engine

Status: Proposed (Slice 1 implemented)
Date: 2026-09-21
Related: [[ADR-0093]] (retire baking / filestore delivery), [[ADR-0034]]/[[ADR-0037]] (Studio authoring), [[ADR-0092]] (unified config), the developer portal ([[developer-portal]])

## Context

Every component and solution needs documentation — how to configure it, what it reads/writes, how
to operate it. Today there is no first-class place for it: the platform's own docs live in a
separately-built static portal (the developer portal), and individual components carry no docs at all.

We already made the developer portal a **filestore-delivered component** whose content is authored as
markdown and rendered to HTML by an in-repo builder (`build_portal.py`). The user's direction: this
should not be a portal one-off. **Documentation is a generic capability every component and solution
uses, it should be authored in Studio, and it should be packaged as part of the component** so it
travels with the artifact through certify → publish → install.

## Decision

Treat documentation as a **first-class, per-component artifact** with three parts, all reusing existing
machinery:

1. **Packaged with the component (a `docs/` convention).** A component's source may include a `docs/`
   folder of markdown (`docs/index.md` + optional further pages). `meta.yaml` may declare
   `documentation: docs/` (default when the folder exists). Because publish already tars the whole
   source dir into the content-addressed filestore ([[ADR-0093]] `_store_bundle`), **docs travel with
   the component automatically** — no separate store, digest-verified like the rest of the artifact.

2. **One shared rendering engine.** The markdown→HTML renderer is extracted from `build_portal.py`
   into a shared module (`docrender.py`) and exposed as a host capability:
   - `POST /bridge/doc-render` — `{markdown}` → `{html}` (a pure render; used for live preview).
   - `GET /bridge/component-docs?component=<cid>[&page=<slug>]` — locate the component's source,
     render its `docs/` into a themed doc view (page nav + content). So **any** component with a
     `docs/` folder gets a rendered documentation site at a stable URL, with zero per-component code.
   The developer portal's builder becomes one consumer of the same renderer (no duplicate markdown
   engine).

3. **Authored in Studio.** Editing docs reuses Studio's existing component-source seam:
   `/bridge/component-save` writes `docs/<page>.md`; `/bridge/doc-render` gives live preview; publish
   packages the updated docs with the component. A Studio "Docs" surface lists the component's pages,
   edits markdown, previews, and publishes — the same lifecycle as its code.

The **developer portal** is then just the platform's own documentation component: the aggregate,
curated rendered site, built from its `docs/` (the concept articles) by the shared renderer.

## Why this shape

- **Reuses everything.** No new delivery path (filestore + `_store_bundle`), no new edit path
  (`component-save`), no new renderer (extracted from `build_portal`). The capability is mostly wiring
  existing seams together behind a `docs/` convention.
- **Docs are versioned + attributed + digest-verified** exactly like code, because they are part of
  the same artifact — the platform's own guarantees ([[shared-vocabulary]]) apply to docs for free.
- **Generic from day one.** A driver, an engine, an app, a solution — all document the same way; the
  marketplace can show a "Documentation" tab that reads `/bridge/component-docs` for any component.

## Slices

- **S1 (DONE): the reusable core.** `docrender.py` (shared renderer); `/bridge/doc-render` (live
  preview) + `/bridge/component-docs` (render any component's packaged `docs/`); the `docs/` convention;
  `build_portal.py` reuses the shared renderer. The developer portal ships packaged docs.
- **S1a (DONE): AI-agent-friendly docs.** Optional YAML **frontmatter** (title, summary, audience,
  keywords, related ids) that a doc declares about itself; `/bridge/component-docs?...&format=md` (raw
  markdown — clean text for agents) and `&format=json` (a machine index: pages + summaries + frontmatter,
  `format: airawat.docs/1`); an `llms.txt` at `/developer` (the index agents look for).
- **S1b (DONE): the Docs Assistant.** `POST /bridge/doc-ask {question, component?}` — grounded Q&A over
  a component's packaged docs. It retrieves the most relevant pages, feeds ONLY those to the confined
  model, and returns the answer **with citations** (the pages used). The AI never acts and never invents;
  if the docs don't cover it, it says so. Retrieval is dependency-free keyword scoring today; the
  platform embed service is the drop-in upgrade for large corpora.
- **S2 (DONE): Studio Docs editor — a tab INSIDE Studio, not a public page.** Right-click a component →
  **📝 Docs…** → a component's `docs/*.md` open as normal Studio file tabs with a markdown editor +
  **live preview** (`/bridge/doc-render`); **Save** (`/bridge/doc-save` writes `docs/<slug>.md`), **Check
  vs code** (`/bridge/doc-review` — deterministic: which declared reads/writes/egress/secrets/verbs are
  undocumented + coverage %), **Publish docs** (`/bridge/doc-publish` re-`_store_bundle` → filestore +
  overlay, live, no rebake). The backend endpoints were proven authenticated end-to-end
  (save→live→publish). **The editor is an authoring tool, so it lives in Studio (authenticated) — it was
  briefly served at the public `/developer/editor/` and that was removed** (docs site ≠ authoring tool).
- **S3 (DONE): "Documentation" tab in the Settings/Components console.** Selecting a component shows a
  **Documentation** tab alongside Configure/Sources/Schedule: it renders the component's packaged docs
  (page nav + `doc-render` of each page) and an inline **Docs Assistant** box (`doc-ask`, cited). When a
  component ships no docs yet, it points the reader to Studio → 📝 Docs. Pure frontend on the existing
  endpoints (`settings` app, served /apps/settings/).
- **S4 (DONE): Developer portal renders from the shared engine at request time.** The
  `/developer/deep-dives/<slug>/` pages are now rendered by app_host from the portal's PACKAGED
  `docs/*.md` through `docrender` + a build-emitted shell template (`deep-dives/_shell.html` +
  `_map.json`) — one runtime source. Editing a concept via Studio (📝 Docs on the developer-portal
  component) goes live on the pretty page with **no rebuild** (proven: a saved marker appeared on the
  rendered page, then vanished on restore). The statically-built deep-dive pages remain as a cold-start
  fallback (any miss/error falls through to them).

## Consequences

- A `documentation:` field is added to the (informal) component manifest vocabulary; absence is fine
  (no docs). No schema-registry change is required for S1 — docs are files in the artifact, not a new
  governed noun. A governed `component.doc` index can come later if we want cross-component doc search.
- The shared renderer is intentionally small (zero-dependency markdown subset). Rich content
  (diagrams, embeds) is a later enhancement, not a blocker.

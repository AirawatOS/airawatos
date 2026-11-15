# ADR-0133 — File associations: apps declare what they open

**Status:** Proposed · **Date:** 2026-11-15
**Builds on:** ADR-0030 (no secrets in components), ADR-0085 (file shares), ADR-0114 (virtual file system),
ADR-0126 (field-level protection), ADR-0130 (trusted core, gateways and components).
**Affects:** app `meta.yaml` (a new `opens` field), the App Host (handler table, `/run` and the run shell, a `media` CSP
profile), the Files app, a new Workplace Media Viewer app.

---

## Context

Clicking a file in Files downloaded it. Users expect a photo to show, a PDF to open and a recording to play, and
other apps (Docs, Sheets, a future Media Viewer) should be able to open the files they understand.

Four facts constrain the design, each checked on staging:

1. **Nothing associates a file type with an app.** No app declares what it can open, and Docs, Sheets and Slides
   cannot import uploaded files.
2. **The run shell passes nothing to the app.** `/run?app=x` always loads `/apps/x/`; an app cannot be told which
   file to open.
3. **Apps are sandboxed, and the sandbox follows them.** The app frame is
   `sandbox="allow-scripts allow-same-origin allow-forms allow-popups"`, so a tab an app opens inherits the sandbox.
   Chrome refuses to show a PDF there ("This page has been blocked by Chrome").
4. **The default app CSP allows images only.** `img-src 'self'`; audio, video and frames fall back to
   `default-src 'none'`.
5. **`/bridge/file` trusts the link.** It checks only that the caller is signed in: not that the file is theirs,
   nor their tenant's. It serves the bytes with whatever `type` the link names, so a file served inline as
   `text/html` or SVG would run as an AirawatOS page with the viewer's session.

**Step 1 is already built** (Files 0.1.3, run shell `airawat-open-file`). Files shows images in its own viewer. For a
PDF, audio, video or text file it asks the shell, which is not sandboxed, to open the file in a new tab. The shell
honours only a same-origin message from its own app frame, and only for a `/bridge/file` link served inline.
Anything else downloads. Because of fact 5, the shell opens only types that cannot run code: PDF, raster images,
audio and video, with text shown as `text/plain`. Files never asks it to open HTML, XML, SVG or scripts.

This ADR decides the general mechanism that step 1 stands in for.

## Decision

**Apps declare the file types they open. The host keeps a handler table per tenant. Files opens a file with the
default handler, or with any handler the user picks. The shell hands the file to the app by reference, and the app
reads it only through the host, under the user's rights.**

### 1. Apps declare what they open

```yaml
opens:
  - types: ["image/*", "audio/*", "video/*", "application/pdf", "text/plain"]
    label: View
  - types: ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
    extensions: [".csv", ".xlsx"]
    label: Open as a sheet
    action: import          # view | edit | import
```

- **The declaration is part of the certified manifest**, so it is signed and versioned with the app.
- **`types` are MIME patterns;** `extensions` cover files uploaded without a reliable type.
- **`action` says what happens:** `view` opens read-only; `edit` changes the file in place; `import` creates the
  app's own record from it and leaves the file unchanged.

### 2. The host keeps the handler table

- **Built at install,** from the `opens` of every app installed for the tenant, and rebuilt on install, update or
  removal.
- **Defaults are chosen in this order:**
  1. the user's choice for that type;
  2. the tenant admin's default;
  3. the only installed handler, when there is one;
  4. the shell's built-in viewing (step 1);
  5. download.
- **Users only ever see handlers they may run.** Apps whose role the user lacks are left out (the same check `/run` makes).

### 3. Opening a file

`/run?app=<handler>&open=<platform.file record id>`

- **The shell passes the record id to the app after the app says it is ready,** with a same-origin
  `postMessage`, never in the frame URL.
- **The app reads the file through the host by record id,** never by a raw filestore id. The host checks that the user
  owns the record or holds a share for it (ADR-0085) before serving the bytes, and takes the type from the record,
  served as an attachment unless it is on the safe-inline list. This closes both halves of fact 5.
- **For `edit`, the app saves a new version through the host;** the record keeps its id and history.

### 4. A `media` CSP profile

An app that declares `csp_profile: media` gets `media-src 'self' blob:` and `worker-src 'self' blob:` on top of the
default. That lets it play audio and video and render PDFs with its own bundled viewer (pdf.js, served from the app).
It does not get `frame-src`: Chrome would still block a PDF framed inside the sandbox, so an embedded browser viewer
is not an option.

### 5. Files

- **Open** uses the default handler.
- **Open with…** lists every handler for the type, with **Always use this**, which sets the user default.
- **Files' own image viewer stays** as the quick path for images.

### 6. Workplace apps

- **Media Viewer (new):** views images, audio, video, PDF (bundled pdf.js) and text, with `csp_profile: media`.
  This replaces the shell's new-tab fallback for these types.
- **Sheets imports** `.csv` and `.xlsx`; **Docs imports** `.docx` and `.md`. Each declares `action: import` once it
  can import.

### Order of work

1. **Host:** reading by record id (fact 5) first, as it is a fix in its own right; then the `opens` field in the manifest schema and certification, the handler table, `/run?open=` with the
   ready handshake and the `media` profile.
2. **Media Viewer app.**
3. **Files:** Open and Open with…, plus user defaults.
4. **Sheets and Docs import**, each as its own change.

## Consequences

- **Any app can become a file handler without changes to Files or the host,** only a manifest declaration.
- **Files are passed by reference and read under the user's rights.** No app receives bytes it could not fetch itself.
- **The new-tab fallback stays as a safety net:** a type with no handler still opens in the browser, and an unknown
  type downloads.
- **The `media` profile widens the CSP only for apps that ask for it,** and still allows nothing outside the platform.
- **Bundling pdf.js adds about 1.5 MB to the Media Viewer.** That is the cost of not depending on the browser's
  viewer.

## Open questions

1. **Should an admin be able to forbid a handler for a type** (for example, no import of `.xlsx` into Sheets)?
2. **Should shared files** (ADR-0085) **open with the recipient's defaults or the sender's?**
3. **Should the virtual file system** (ADR-0114) **resolve paths to records so apps can open files by path?**

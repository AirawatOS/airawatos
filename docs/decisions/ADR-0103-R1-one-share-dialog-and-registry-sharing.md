# ADR-0103-R1 — One Share dialog everywhere, and sharing a whole registry

**Status:** Proposed · **Date:** 2026-11-15
**Amends:** ADR-0103 (owner-granted per-object sharing). **Related:** ADR-0085 / ADR-0087 (sharing with other
organisations), DEBT-B182 (capability and grant model), ADR-0133 (file associations — the Opener).

---

## Context

People want to share a registry in the Data app the way they share a Google Sheet: add a person, choose what they may
do, see who has access, remove someone. They also want the same experience in Files and in the Workspace apps (Docs,
Sheets, Slides).

What exists today:

- **Data app:** shares a registry only with *other organisations* (ADR-0087 Data Exchange: offer → request → approve).
  No person-to-person sharing.
- **Files:** sends files to *another organisation* (ADR-0085), admins only. No person-to-person sharing.
- **Docs / Sheets / Slides:** each user sees only their own documents (`personal: true`). No sharing at all.
- **ADR-0103** designs person-to-person sharing of a single object (a file, a doc, one record): an owner-issued
  `access.grant` (view / comment / edit) enforced in the kernel. Its kernel primitive (S1) is built and was proven on
  nashik; the shared "Share…" dialog (S2) and its use in each app (S4) were never built.
- **A whole registry is not a single object.** Registries (`geo.osm_feature`, `works.work_order` …) belong to the
  organisation (`x-ownership: tenant`); who may read them inside the organisation is decided by roles. ADR-0103 has no
  grant for "this whole registry".

## Decision

### 1. One Share dialog, used by every app

A single platform component (served by the host like `/shared/aos.js`), opened the same way from Data, Files, Docs,
Sheets and Slides. Apps do not build their own.

```
┌ Share "Work orders" ─────────────────────────────── ✕ ┐
│ [ Add people or groups …                  ] [Viewer ▾] │
│                                                        │
│ People with access                                     │
│  (A) Anita Rao   anita@…   Owner                       │
│  (R) Ravi K      ravi@…    Editor ▾   (Remove)         │
│  (G) Ward 12 engineers (group) Viewer ▾                │
│                                                        │
│ General access                                         │
│  🔒 Restricted ▾  Only people added above              │
│     (or: Anyone in Bengaluru — Viewer ▾)               │
│                                                        │
│ [ Copy link ]                               [ Done ]   │
└────────────────────────────────────────────────────────┘
```

- **Add people or groups:** search people and roles/groups *in the organisation*. Other organisations are not offered
  here; they stay on the existing "Shared with organisations" flow (ADR-0085/0087), which needs a steward's approval.
- **Levels:** Viewer, Commenter, Editor. Registries offer only Viewer and Editor until comments exist for records.
- **People with access:** change a level or remove someone. Changes take effect at once and are recorded.
- **General access:** Restricted (default) or "Anyone in <organisation>" at a chosen level.
- **Copy link:** the link opens the item through the Opener (ADR-0133). It never grants anything by itself; a person
  without access sees "Request access" (ADR-0103 §4, pull).
- **Who sees the Share button:** only someone allowed to share that item (§3). Others see who it is shared with, read-only.

### 2. Registry-level grants

`access.grant.object_id` may name a whole registry: `ds:<tenant>:<schema>/*`. Levels:

- **Viewer** — read every record of that registry in this organisation.
- **Editor** — also add, change and retire records, through apps allowed to write that schema.

The kernel checks a registry grant at the same gates as an object grant (ADR-0103 §3): for a read, own tenant AND (a
role already allows it OR the caller holds a registry or object grant); for a write, the same with Editor.
Sensitive registries (`sensitivity: sensitive`) cannot be shared this way; they stay role-only.

### 3. Who may share what

| Item | Owner | Who may share |
|---|---|---|
| Doc, Sheet, Slide, a user's File (`x-ownership: user`) | its author | the owner (and Editors, if the owner allows it) |
| A record about a person (`x-ownership: subject`) | that person | that person only |
| A whole registry (`x-ownership: tenant`) | the organisation | the registry's **data owner** — a new per-registry role, held by the steward until assigned |

The rule that only the owner may grant (ADR-0103) holds; for a registry the "owner" is its data owner role. This is
part of the capability and grant model (DEBT-B182) and should be decided there, not invented in the Data app.

### 4. Shared with me

Each app lists what was shared with the user: Data shows "Shared with me" registries in its left pane; Files and the
Workspace apps show a "Shared with me" view. One query backs all of them: grants where the grantee is me.

## Consequences

- **The experience is the same everywhere because it is one component** backed by one record (`access.grant`).
- **Kernel work is needed, and it is authority code:** registry-level grants at the read and write gates, the data
  owner role, and bulk reads (query/resolve) honouring grants. ADR-0103 S1 noted that bulk reads stay tenant-scoped;
  sharing a registry is mostly bulk reads, so this must be done before registry sharing works.
- **Docs/Sheets/Slides must stop being owner-only** (`personal: true` forces `owner == me` on every read in the host);
  reads must honour grants instead.
- **Staging cannot show this** without a kernel that has ADR-0103 S1 and these changes. The Data app does not show a
  Share button until the kernel supports it — a button that cannot work is worse than none.

## Slices

1. **Kernel:** registry grants; data owner role; grant-aware bulk reads (after the B182 capability ADR).
2. **The Share dialog component** + `/bridge/share` (list / add / change / remove / general access), with tests.
3. **Wire in:** Docs (first, as ADR-0103 S2 planned), then Data (registries), Files, Sheets, Slides; "Shared with me" in each.
4. **Request access** from a link (ADR-0103 S3).

## Decisions needed

1. Approve kernel (authority) work for registry grants and grant-aware bulk reads, or wait for the B182 ADR.
2. Who is a registry's data owner by default: the steward, or the role that may write the registry today.
3. Whether "Anyone in <organisation>" is allowed for registries, or only for Docs/Files.

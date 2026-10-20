# EC2 hot-patches to bake — 2026-10-19 (self-serve dev loop + Console)

> ⚠️ **Everything below was deployed to the live EC2 stack (`airos.airawat.org` / `13.205.13.220`) by
> `docker cp`-ing files into running containers — NOT baked into any image.** A reference-image rebuild or
> `docker compose up --force-recreate` *without* these in the image (or durable overlay) **reverts them**.
> The source changes ARE in the working trees of the nested repos (`platform-spec`, `components`) — this
> checklist pins exactly what to fold into the next image build.

## Milestone proven
A Studio developer (`manish`, `studio.product-manager`) uploaded the real **48.5 MB DJB complaints CSV** via
`aos upload` and ran the `water-complaints` driver **in the `airawatdeveloper` sandbox via the Console** with
**no admin, no install, no publish, no certificate** → **96,343 real complaints in `water.complaint`**
(keyword crosswalk; `raw_category` preserved; PII dropped). This is the full self-serve inner loop:
`describe → run <driver> KEY=/inbox/file → logs <driver>`.

---

## 1. app-host — `platform-spec/reference/app_host.py`
Bake into the app-host image (`manishsv/airawatos-reference`). Changes:
- **`/bridge/file-push`** — `aos upload` large-file endpoint. Cookie-OR-verified-bearer auth; streams the body
  to the filestore spooled in 1 MB chunks (256 MB cap); writes the owner-stamped `platform.file`; **auto-creates
  the folder chain** so the file is navigable in Files.
- **Files-app upload error surfacing** support (pairs with the file-explorer bundle, §4).
- **Run-gate predicate** (`_bridge_run`): allow `ADMIN_ROLES` **OR** `is_studio_builder × tenant_env ∈
  {development,sandbox}`. Production stays admin-only.
- **Dev-run routing** (`_do_run`): for a studio builder in a development tenant, send `dev:true` + the caller's
  `auth` token + `source_file_id` (`_stage_draft` tars the current source to the filestore) → the scheduler's
  dev-token draft path (no install/cert).
- **Async `/bridge/run`**: fire the run in a background thread and return `{status:"started"}` immediately
  (large ingests exceed the ~60 s proxy timeout → was a 504 on success). Token captured before the thread
  (`_current_session` is thread-local) and passed via the new `_do_run(..., token=)` param.

## 2. scheduler — `platform-spec/reference/scheduler.py`
Bake into the scheduler image.
- `DEV_RUN_TIMEOUT` default **600 → 1800 s** (a full 96k/50 MB config-driven ingest exceeds 10 min).
- Dev + installed run **log tail 8 / 60 → 400 lines** (so `logs <component>` / the run outcome show a full
  Python traceback, not a truncated tail).

## 3. runtime launcher — `platform-spec/reference/host_runner.py` + `host.py`
Bake into the scheduler image. The **services-only `broker_ips` fix**: the L1 egress guard resolves the broker
**hostname → IP** and allows exactly that endpoint, so a component can reach the kernel-as-broker over the
container network (`http://kernel:8080`), not just loopback. The EC2 scheduler was running an OLD `host_runner.py`
(no `broker_ips`) → every dev-run failed with `broker GET /v1/context … host-confined (L1): egress … denied`.

## 4. App bundles (durable in `/data/app-bundles/apps/<id>` — survives recreate, NOT image rebuild)
- **`console`** — NEW in-platform command-line app (`components/apps/console`, id `ds:airawatdeveloper:app/console`,
  `roles:[]` = everyone, `data_browser:true`). Commands: `help whoami data query files components describe run
  (async + file paths) runs logs clear`. Also on the `airawatdeveloper` shelf (`platform.app_shelf`).
- **`file-explorer`** (`components/apps/file-explorer`) — surfaces the real upload error + a client-side 25 MB
  pre-check (was a generic "Upload failed"); `path`-aware.
- Fold both into the bake (or confirm the `/data/app-bundles` overlay is preserved). Console needs a proper
  Studio Publish/cert for role-gated cross-tenant serving.

## 5. ✅ RESOLVED (2026-10-19) — network tenant record: `airawatdeveloper` `environment: development`
It was mis-registered as `production` (the `POST /v1/tenants` default) despite being the dev sandbox, so the
kernel refused to mint dev-tokens for it. Re-signed via `POST network /v1/tenants` (airawat steward) → now
`development`.

**The earlier "IN-MEMORY → reverts on restart" worry was WRONG.** The network's `TENANTS` namespace is
**postgres-backed** (`network/kv.py` `KV`/`Namespace`, `_backend()` returns `_DURABLE=True` when `KV()`
connects — and the EC2 network has `DB_HOST=postgres`). Verified live: the record is stored in the `kv` table
(`store='tenants', key='airawatdeveloper'`) and has persisted since `issued_at: 2026-10-14` across many
restarts. **A network restart does NOT revert it.**

**Durable-in-provisioning fix (shipped):**
- `network/ensure_dev_tenant.py` — idempotent, identity-preserving seed: flips an existing record to
  `development` (preserving steward_participant / prefix / jurisdiction / host_operator — never mints a new
  steward key), no-ops if already `development`, and (with `DEV_STEWARD=…`) creates it fresh on a bedrock DB.
  Runs inside the network process (`import api` → same durable KV), so no HTTP / identity token / passwordless-
  steward dependency. Run it as the final provisioning step: `docker compose exec network python
  ensure_dev_tenant.py` (or `docker exec airawat-network python3 /app/ensure_dev_tenant.py`).
- Baked into the image: `network/deploy/Dockerfile` COPYs the script + a **gated, non-fatal boot hook**
  (`ENSURE_DEV_TENANT=1` → self-heal on boot; default OFF = byte-identical to `uvicorn api:app`). A
  bake-exactly-running overlay is published: **`manishsv/airawatos-network:0.3.5-dev-tenant-ensure`**
  (= `0.3.5-zoho-keyprefix` + the script; overlay Dockerfile in `deploy/ec2/network-dev-tenant-overlay.Dockerfile`).
- `deploy/local/docker-compose.yml` points the `network` service at that tag and sets
  `ENSURE_DEV_TENANT=1` + `DEV_TENANT=airawatdeveloper` + `DEV_STEWARD=ds:airawatdeveloper:participant/developer`.

**Live EC2 status:** record is already `development` (durable in postgres) and the baked script was smoke-tested
against the live KV (idempotent no-op). The live `airawat-network` still runs `0.3.5-zoho-keyprefix`; an
*optional* cutover to `0.3.5-dev-tenant-ensure` (recreate the network with `ENSURE_DEV_TENANT=1`) activates the
on-boot self-heal there too — not required for durability, since the record already persists.

## 6. Still-ephemeral in `/app/components` (from an earlier session)
SDK `components/_common/aos/ingest.py`, the `water-complaints` driver, and the `water-setup` app are re-seeded
into `/app/components` after each recreate — fold into the bake too.

---

## Source locations (nested repos — changes uncommitted on their feature branches)
| File | Repo | Branch |
|---|---|---|
| `platform-spec/reference/{app_host,scheduler,host_runner,host}.py` | `platform-spec` | `feat/participant-embed-sdk-s1` |
| `components/apps/{console,file-explorer}`, `components/_common/aos/cli.py` | `components` | `feat/pm25-source-apportionment` |

## ✅ Published to Docker Hub (2026-10-19)
Bake-exactly-running overlays (only the deployed files, on top of each service's current base) + every
local-only running image pushed so the whole stack is reproducible from the registry:

| Image (Docker Hub) | What | Contains |
|---|---|---|
| `manishsv/airawatos-reference:0.2.47-selfserve-dev` | **NEW** app-host | `0.2.46-datasets` + patched `app_host.py` |
| `manishsv/airawatos-reference:0.2.9-selfserve-dev` | **NEW** scheduler | `0.2.9-airfix` + patched `scheduler.py`,`host_runner.py`,`host.py` |
| `manishsv/airawatos-kernel:0.2.10-datasets` | kernel (was local-only) | pushed as-is |
| `manishsv/airawatos-reference:0.2.9-airfix-h3` | runtime-manager (was local-only) | pushed as-is |
| `manishsv/airawatos-reference:0.2.46-datasets` | old app-host base (was local-only) | pushed as-is |

Already on Docker Hub: `reference:0.2.83-auth` (identity), `reference:0.2.9-airfix` (scheduler base),
`network:0.3.5-zoho-keyprefix`.

### Cutover (recreate later — NOT done yet)
In `/home/ec2-user/airawatos/docker-compose.yml`, point the two services at the baked tags:
- app-host:  `0.2.46-datasets` → **`0.2.47-selfserve-dev`**
- scheduler: `0.2.9-airfix` → **`0.2.9-selfserve-dev`**

then `docker compose up -d --no-deps --force-recreate <app-host-svc> <scheduler-svc>`.
⚠️ A recreate wipes the ephemeral `/app/components` driver re-seed (water-complaints etc.) — re-seed or bake
those separately. The Console/file-explorer bundles survive (durable `/data/app-bundles` volume). The fragile
`airawatdeveloper environment=development` network record is unaffected by this recreate (only a *network*
restart reverts it).

## 7. ADR-0114 VFS Slice 1 (deployed 2026-10-20; NOT baked)
The unified virtual filesystem, read-only slice (ADR-0114). Deployed by `docker cp` into the running
app-host + a schema register on the network — fold into the next bake.
- **`platform.fsnode` governed** — signed schema `ds:airawat:schema/platform.fsnode@0.1.0` published to the
  network (`platform-spec/reference/govern_fsnode.py`; superset of `platform.file`). Re-run on a fresh
  network: `docker exec -e NETWORK=http://localhost:8090 airawat-network python3 /app/govern_fsnode.py`.
- **VFS resolver** in `platform-spec/reference/app_host.py`: `GET /bridge/vfs?action=stat|list|read|head|tail|wc|grep&path=…`
  (`_bridge_vfs` + `_vfs_nodes`/`_vfs_norm`/`_vfs_split`/`_vfs_iter_lines`). Reads `platform.fsnode` UNION
  `platform.file` (legacy projected as blob/folder), owner-scoped — same visibility as the Files app, so no
  behavior change. **head/grep stop early (bounded read); tail/wc full-scan** — the server returns a small
  JSON result so a 48MB file never crosses the wire to preview/search. Read-only (no write/mkdir/mount/publish
  yet). Route added in `do_GET` next to `/bridge/file`.
- **Console bundle** (`components/apps/console/dist/index.html`): new `ls`/`cd`/`pwd`/`cat` + power commands
  `head`/`tail`/`grep [-i]`/`wc`/`stat`/`find` over `/bridge/vfs` (+ a `cwd`); `ls` no longer aliases `data`,
  `cat` no longer aliases `files` (both are real VFS commands). `cat` previews small files (≤256KB) and points
  big ones at `head`/`grep`. **TAB completion** (2026-10-20): first word → command name; args of the filesystem
  commands → VFS path (one match fills, several complete the common prefix + list) via `/bridge/vfs?action=list`.
  Durable in `/data/app-bundles/apps/console` (survives recreate, not image rebuild).
- **Verified:** schema published ✔ ; app_host compiles in-container + restarted ✔ ; `/bridge/vfs` auth-gate
  returns 403 without a session ✔ ; path-resolution logic unit-tested ✔. NOT yet live-verified for the
  owner-scoped data path (needs a logged-in session — do via the Console `ls/cd/cat` in-browser).
- **`/projects` mount** (ADR-0114 Slice 3, read-only; deployed 2026-10-20): `_vfs_projects` in `app_host.py`
  surfaces the caller's **Studio projects** → their **member components** → each component's **source files**
  (read from `_find_component_dir(cid)` on disk), with a path-traversal guard. `ls /projects`,
  `cd /projects/<proj>/<comp>`, `cat`/`head`/`grep` work on source; `run <comp>` runs it **install-free**
  (self-serve dev, already live). `ls /` now shows a `projects/` entry. Scan logic refactored into the shared
  `_vfs_scan` (used by both filestore blobs and on-disk source). Visibility = project owner/team (or admin).
  Caveat: a component only lists source if its dir is on disk (baked or materialised) — a never-run unbaked
  component may need one `run` (which materialises) before its files appear.
- **Writable workspace + publish** (ADR-0114 Slice 3 write side; deployed 2026-10-20): `POST /bridge/vfs`
  `{path,content}` → `_bridge_vfs_write` → `_vfs_projects(action="write")` edits a component source file the
  SAME way Studio `component-save` does (same `_component_edit_authorized` per-component ownership gate + the
  same `{meta.yaml, run.py, dist/index.html}` allow-list; writes to the on-disk component dir, traversal-guarded).
  Console: `edit <path>` (modal textarea, Ctrl/⌘-S) · `write <path> <text>` · `publish <component>` →
  `/bridge/project-publish` (certify + list; enforces not-a-stub + a green dev run). Round-trips with Studio
  (same files, same records). This completes the Console → build-a-solution inner loop
  (`edit → run → logs → publish`); scaffolding (`new …`), `schema/iface propose`, and `compose` are the
  remaining wiring slices (S3b–d).
- Source lives (uncommitted, like §1–§3) on `platform-spec@feat/participant-embed-sdk-s1` +
  `components@feat/pm25-source-apportionment`.

## Optional follow-ups (not blockers)
- `TAXONOMY_MAP` crosswalk for exact DJB label→canonical mapping (Setup Console ✨ Auto-map via kimi-k3).
- Audit the remaining hardcoded `ADMIN_ROLES &` action gates and apply the sandbox-privilege predicate
  (builder-role × development env), keeping destructive/cross-tenant/production ops admin-only.

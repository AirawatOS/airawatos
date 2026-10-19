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

## 5. ⚠️ MOST FRAGILE — network tenant record: `airawatdeveloper` `environment: development`
It was mis-registered as `production` (the `POST /v1/tenants` default) despite being the dev sandbox, so the
kernel refused to mint dev-tokens for it. Re-signed via `POST network /v1/tenants` (airawat steward) → now
`development`. **The network's `TENANTS` map is IN-MEMORY — a network restart REVERTS it to `production`** and
breaks the whole self-serve dev loop again. **Durable fix:** set `environment=development` wherever
`airawatdeveloper` is provisioned/seeded, and/or make the network tenant registry durable.

## 6. Still-ephemeral in `/app/components` (from an earlier session)
SDK `components/_common/aos/ingest.py`, the `water-complaints` driver, and the `water-setup` app are re-seeded
into `/app/components` after each recreate — fold into the bake too.

---

## Source locations (nested repos — changes uncommitted on their feature branches)
| File | Repo | Branch |
|---|---|---|
| `platform-spec/reference/{app_host,scheduler,host_runner,host}.py` | `platform-spec` | `feat/participant-embed-sdk-s1` |
| `components/apps/{console,file-explorer}`, `components/_common/aos/cli.py` | `components` | `feat/pm25-source-apportionment` |

## Optional follow-ups (not blockers)
- `TAXONOMY_MAP` crosswalk for exact DJB label→canonical mapping (Setup Console ✨ Auto-map via kimi-k3).
- Audit the remaining hardcoded `ADMIN_ROLES &` action gates and apply the sandbox-privilege predicate
  (builder-role × development env), keeping destructive/cross-tenant/production ops admin-only.

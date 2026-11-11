# Install AirawatOS on your laptop (local test)

> **⚠️ LEGACY — do not follow.** This describes the old `deploy/local/` prebuilt-image install. Use
> [`docs/operator/INSTALL-LOCAL.md`](operator/INSTALL-LOCAL.md) instead.


Stand up the whole platform on your machine from the **same pinned images that run in production**, so you can
test the install end-to-end. This brings up the core + active-loop engines; it does **not** reproduce the live
site's data — a fresh stack is a *bare* platform (empty registry/DB) you then log into and populate.

All the files you need are in [`deploy/local/`](../deploy/local).

---

## 1 · Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2). Give it **≥ 8 GB RAM** and **~20 GB disk**.
- **Apple Silicon (arm64):** the `manishsv/airawatos-*` images are **amd64** and the compose already pins
  `platform: linux/amd64` on them, so they run under Docker Desktop's emulation automatically. Enable
  **Settings → General → "Use Rosetta for x86/amd64 emulation"** for speed.
  ⚠️ **Do NOT `export DOCKER_DEFAULT_PLATFORM=linux/amd64`.** That forces the infra images (Vault, Postgres,
  nginx) to emulate too — and **Vault's Go binary crashes under QEMU/Rosetta** (the stack then hangs with an
  empty Vault token). Leaving it unset lets Vault/Postgres/nginx run **native arm64** while the Airawat services
  stay amd64 via their per-service pins.
- A Docker Hub account isn't required — the images are public.

## 2 · Get the files

```bash
cd Airawat/deploy/local
cp .env.example .env          # VAULT_TOKEN is filled in step 4
```
`deploy/local/` contains: `docker-compose.yml` (pinned, portable core+engines), `vault/` (auto-init config),
`nginx.conf` (single front door on :80), `.env.example`.

## 3 · Pull the images (pinned — not `:latest`)

```bash
docker compose pull
```
This fetches the exact versions the compose pins (`network:0.3.5-zoho-keyprefix`, `kernel:0.2.8-devgrant`,
`reference:0.2.115-settings-fixes`, `identity:0.2.83-auth`, …). First pull is a few hundred MB.

## 4 · Bring up Vault first, then capture its token

Vault auto-initialises on first boot and writes a **root token** into its data volume. The other services
read it via `${VAULT_TOKEN}`, so bring Vault up alone, grab the token, and write it into `.env`:

```bash
docker compose up -d vault
# wait ~10s for it to init + unseal, then:
docker compose exec vault sh -lc \
  "tr -d '\n ' < /vault/data/init.json | sed 's/.*\"root_token\":\"\([^\"]*\)\".*/\1/'"
# (init.json is pretty-printed JSON — flatten newlines/spaces FIRST, else the pattern won't match → empty token)
```
Copy the printed token into `.env`:
```
VAULT_TOKEN=hvs.XXXXXXXXXXXXXXXX
```

## 5 · Start the rest

```bash
docker compose up -d
docker compose ps        # watch health; postgres/vault/network should read "healthy"
```
Bring-up order is handled by `depends_on` + healthchecks (postgres & vault → network → kernel → identity →
everything else). Give it 1–2 minutes on first boot (emulated amd64 is slower).

## 6 · Verify

```bash
curl -s localhost/network/v1/health            # → {"status":"ok"} (AirawatNetwork)
curl -s -o /dev/null -w "%{http_code}\n" localhost/kernel/v1/health   # → 200 (kernel)
curl -s -o /dev/null -w "%{http_code}\n" localhost/                   # → 200 (app-host landing)
```
Then open **http://localhost/** in a browser — you should get the landing page, and **http://localhost/login**
the sign-in screen.

## 7 · Log in (passwordless dev IdP)

> **Local development only.** Production enforces passwords (`IDENTITY_PASSWORD_REQUIRED=enforce`, **ADR-0121**);
> the passwordless sign-in below works solely because this is a local/offline dev stack.

A fresh stack ships the reference IdP's seed realms (no passwords set yet), so you can sign straight in:

| Realm | User | Role |
|---|---|---|
| `airawatdeveloper` | `devrick` | developer (build/publish in Studio) |
| `airawat` | `steward` | network admin (Marketplace, Components) |

Pick the realm on the login screen, type the username, leave password blank, sign in. *(Local development
only; production enforces passwords — `IDENTITY_PASSWORD_REQUIRED=enforce`, ADR-0121.)*

## 8 · What "installed" looks like

Services healthy + you can log in = **the install works**. The registry/DB are **empty**, so there are no
cities, apps, or marketplace listings yet — that content was built up incrementally on the live host and isn't
part of a fresh install. To put something in, use the **Studio** app (as `devrick`) to build + publish a tiny
solution — see [`quickstart.md`](quickstart.md) and [`build-quickstart.md`](build-quickstart.md).

## 9 · Teardown

```bash
docker compose down            # stop + remove containers (keeps data volumes)
docker compose down -v         # also wipe the volumes (full reset)
```

---

## What this install leaves out (and why)

Three production services are intentionally omitted because they need host-path mounts or separate setup, and
none is required to test the core install:

- **runtime-manager** — places heavy sandboxed *runtime-profile* containers; holds the Docker socket and mounts
  a host components dir. Needed only for drivers/engines that require a runtime image.
- **mospi-gateway** — an external-data sidecar (national statistics); bind-mounts its own source.
- **keycloak** — optional OIDC IdP. The built-in passwordless reference IdP covers local testing *(local
  development only; production enforces passwords — `IDENTITY_PASSWORD_REQUIRED=enforce`, ADR-0121)*.

Add them later from the production compose on the deploy host if you need those features.

## Troubleshooting

- **`VAULT_TOKEN` empty / services crash-loop on Vault auth** — you skipped step 4, or Vault re-initialised
  after a `down -v`. Re-run step 4 and `docker compose up -d` again.
- **502 from nginx right after a recreate** — nginx re-resolves every 10s; wait, or `docker compose restart nginx`.
- **Slow / high CPU on Apple Silicon** — expected under amd64 emulation. For native-speed you'd build the
  images from source for arm64 (a separate path; not covered here).
- **Health never goes green** — check `docker compose logs <service>`; the usual cause is the Vault token not
  propagated to `network`/`identity`/`secrets`.

See **[architecture/services.md](architecture/services.md)** for what each service does and how they wire together.

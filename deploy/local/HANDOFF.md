# Deploy AirawatOS on your machine

This stands up a **complete AirawatOS instance** (OS kernel + AirawatNetwork + identity + apps) on one
machine using Docker. You do **not** need the source code or any GitHub access — the platform ships as
**public Docker images**, and the single script below writes everything else it needs.

Total time: ~5 min of your attention + a one-time ~2 GB image download.

---

## 1 · Install prerequisites

- **Docker** — [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or
  Docker Engine + Compose v2 (Linux). Give it **≥ 8 GB RAM** and **~20 GB free disk**.
- **Apple Silicon Macs (M1/M2/M3):** in Docker Desktop → **Settings → General**, tick
  **"Use Rosetta for x86/amd64 emulation"** (the images are amd64). The script handles the rest.
- Nothing else — no Docker Hub login, no GitHub account, no source checkout.

Verify Docker is ready:
```bash
docker version && docker compose version
```

## 2 · Get the script

You were sent **one file: `airawatos-bootstrap.sh`**. Put it anywhere (e.g. your home folder). That file is
the entire deployment — it writes the compose file, reverse proxy, and Vault config itself.

## 3 · Run it

```bash
bash airawatos-bootstrap.sh
```

What it does, unattended: checks Docker → pulls the public images → starts Vault and captures its token →
brings up the full stack → waits for health → prints the result. First run takes a few minutes while images
download (and longer on Apple Silicon, which emulates amd64).

Everything is installed under `~/airawatos-local/` (override with `AIRAWATOS_DIR=/path bash airawatos-bootstrap.sh`).

## 4 · Open it

When the script finishes it prints health checks and a URL.

- **On your own laptop:** open <http://localhost/>
- **On a remote server:** open `http://<server-ip-or-hostname>/` — and make sure **port 80 is open**
  in the machine's firewall / cloud security group.

**Log in** (passwordless demo identity provider — a fresh install ships two seed users):

| Realm | Username | Password | Who |
|---|---|---|---|
| `airawatdeveloper` | `devrick` | *(leave blank)* | Developer — build & publish in Studio |
| `airawat` | `steward` | *(leave blank)* | Network admin — Marketplace, Components |

Pick the realm on the login screen, type the username, leave the password empty, sign in.

## 5 · What you get

A **bare, working platform**: all services healthy, you can log in and use Studio — but the registry is
**empty** (no cities, apps, or marketplace content yet; that data isn't part of a fresh install). Build
something via the **Studio** app as `devrick` to populate it.

---

## Managing it

```bash
cd ~/airawatos-local
docker compose ps                 # service status / health
docker compose logs -f app-host   # tail a service's logs
docker compose restart nginx      # if you briefly see a 502 right after boot (proxy re-resolves in ~10s)
docker compose down               # stop everything (keeps your data)
docker compose down -v            # stop AND wipe all data (full reset; next run re-initialises Vault)
docker compose up -d              # start again
```

## If something goes wrong

- **A service won't go healthy / crash-loops on "vault" auth** — re-run `bash airawatos-bootstrap.sh`
  (it re-captures the Vault token). This is the most common first-run hiccup.
- **`502 Bad Gateway` right after startup** — the proxy hasn't re-resolved yet; wait ~15 s or
  `docker compose restart nginx`.
- **Slow / high CPU on Apple Silicon** — expected; it's amd64 emulation. Enabling Rosetta (step 1) helps.
- **Health never goes green** — `cd ~/airawatos-local && docker compose logs network kernel` and send the
  output back to whoever shared this with you.

---

### What this leaves out (and why it's fine)

Three production-only services are intentionally omitted — none is needed to run and explore the platform:
**runtime-manager** (placement of heavy sandboxed driver/engine containers), **mospi-gateway** (an
external-data sidecar), and **Keycloak** (optional OIDC provider — the built-in passwordless identity
service covers local use). They can be added later on a real deployment host.

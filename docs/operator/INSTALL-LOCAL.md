# Install AirawatOS locally (developers)

This replaces the old team instructions (Docker Desktop + clone `airawatos` + `components` +
`deploy/local/airawatos-install.sh` + `http://localhost/login`). Those used prebuilt images and the legacy
`deploy/local/` stack. **Do not use them any more.**

Everything below runs on your machine. The stack is reachable only from it: the edge listens on `127.0.0.1:8080`.

## 0. What you need

- **Docker Desktop** (macOS or Windows) or Docker Engine with the compose plugin (Linux), version 24 or later.
  - Give Docker at least **8 GB of memory** and **40 GB of disk** (Settings → Resources).
  - Nothing else may use host port **8080**.
- **git**, **bash**, **curl** and **python3** (3.9 or later) on the host.
- About 45 minutes for the first build and install.
- **Apple Silicon (arm64)** is the verified platform: the images build natively and `make verify` passes there.
- **Intel/AMD (amd64)** builds natively the same way, but that build is **not yet proven** (DEBT-B114).
  - Report anything that fails.
  - Do **not** build or run the images under emulation (`--platform linux/amd64` on Apple Silicon, or the reverse).
    pyarrow crashes under QEMU.

## 1. Clone the five repositories, side by side

Until the repository restructure lands, AirawatOS is five repositories. Four of them are cloned **inside** the root one,
and the root repository ignores them:

```
mkdir -p ~/src && cd ~/src
git clone https://github.com/AirawatOS/airawatos.git AirawatOS
cd AirawatOS
for r in platform-spec kernel network components; do git clone https://github.com/AirawatOS/$r.git $r; done
```

**Branches.** Use `main` in all five. *Until Layer 1 is merged* (pull requests open), check out the feature branches
instead:

```
git checkout docs/trusted-network-platform-adr-0119-0120
git -C platform-spec checkout feat/network-console-multinetwork
git -C kernel        checkout feat/admin-issuer-scope
git -C network       checkout feat/trust-plane-phase1
git -C components    checkout feat/network-console-multinetwork
```

## 2. Build the images (image policy: built locally from your checkout)

Images are **never pulled**. Build them from the commits you checked out, with the tag that the compose file pins:

```
TAG=$(awk -F: '/image: manishsv\/airawatos-reference/{print $3; exit}' deploy/local-dev/docker-compose.dev.yml | awk '{print $1}')
deploy/build-images.sh "$TAG"
```

This takes 10–20 minutes the first time. The script refuses to build from a repository with uncommitted changes:
commit or stash first. It records what it built in `deploy/local-dev/IMAGES.lock.json`. That file is tracked, so
`git status` shows it as modified after a build; leave it, or `git checkout` it back.

## 3. Install

Choose the first administrator password yourself:

```
OPERATOR_PASSWORD='choose-a-long-password' deploy/installer/install.sh --profile dev
```

The install takes 10–15 minutes. It ends with `✓ install complete — profile=dev (every phase succeeded)`. If any phase
fails, it stops with `✗ install FAILED in phase: …` and the phase name.

If you leave `OPERATOR_PASSWORD` out, the installer generates a strong password and never prints it. It writes it only
to the gitignored file `conformance/.creds.json`. Read it with:

```
python3 -c "import json;print(json.load(open('conformance/.creds.json'))['opadmin']['password'])"
```

## 4. Sign in

Open **http://127.0.0.1:8080/login** (or `http://localhost:8080/login`). Note the port; port 80 was the old stack.

| Field | Value |
|---|---|
| Realm | `localdev-operator` (the operator realm — platform administration) |
| User | `admin` |
| Password | your `OPERATOR_PASSWORD`, or the one in `conformance/.creds.json` |

**First password.** The installer's bootstrap password for `admin` is single use (ADR-0131):
- It is removed from Vault at the end of the install.
- If the sign-in page asks you to set a new password, do so. It is the only admin password from then on, and nobody
  else knows it.
- Keep it in your password manager. If you lose it, reset the install (section 6).

The same `admin` account also signs in to the `localdev-network` realm (network administration). The dev profile also
creates the `localdev`, `localdev-developer` and `localdev-network` realms with test users, for conformance. Those users'
passwords are in `conformance/.creds.json`.

## 5. Everyday use

```
docker compose -p airawatos-localdev --project-directory deploy/local-dev -f deploy/local-dev/docker-compose.dev.yml ps    # status (all healthy)
docker compose -p airawatos-localdev --project-directory deploy/local-dev -f deploy/local-dev/docker-compose.dev.yml stop  # stop (data kept)
docker compose -p airawatos-localdev --project-directory deploy/local-dev -f deploy/local-dev/docker-compose.dev.yml start # start again
```

Backups and restores of your local data: `deploy/local-dev/backup.sh` and `deploy/local-dev/restore.sh`, described in
`docs/operator/RESTORE-AND-ROTATION.md`.

## 6. Reset to a clean install

```
OPERATOR_PASSWORD='choose-a-long-password' verify/fresh_install.sh
```

This tears the stack down **with all its data**: containers, volumes, networks and the local host secrets. It then
proves that nothing is left and installs from scratch. It ends with
`✓ fresh install passed from a proven-empty slate`. Rebuild the images first (section 2) if you pulled new commits.

`verify/fresh_install.sh` refuses to run if anything of the project is left that it cannot account for, for example a
volume set kept by an earlier restore. It lists what it found. Remove an old set with
`python3 deploy/local-dev/_sets.py list`, then `python3 deploy/local-dev/_sets.py prune <set>`.

## 7. Verify (before a pull request)

```
make verify
```

This runs every assurance net, including a fresh install, against a proven-empty slate. It needs no other containers on
the host, and takes about 2.5 hours. See `CONTRIBUTING.md`.

## Troubleshooting

- **`✗ … has uncommitted changes — commit first`** from `build-images.sh`: one of the five checkouts is dirty.
  `git status` in each.
- **Port 8080 in use:** stop whatever holds it (`lsof -iTCP:8080 -sTCP:LISTEN`).
- **A service stays `unhealthy`:** `docker logs airawat-ld-<service>`. A Vault-using service that cannot log in says
  `FATAL: Vault AppRole login failed`. Reset with section 6.
- **Need the Vault root token** (local-dev administration only): `python3 deploy/local-dev/vault_root.py generate`. When
  you are done, run `python3 deploy/local-dev/vault_root.py revoke-all`.

# Install AirawatOS on your local machine

> **⚠️ LEGACY — do not follow.** This describes the old `deploy/local/` prebuilt-image install. Use
> [`docs/operator/INSTALL-LOCAL.md`](../../docs/operator/INSTALL-LOCAL.md) instead.


A single command brings up a fresh, self-contained AirawatOS instance: the four realms (operator / network /
data tenant / developer), an admin login for each, and the **Base-OS app suite** on every admin desktop
(Admin · Settings · Files · Console · Inbox · Personal Assistant · Marketplace, plus Network Admin on the
network realm).

The service code and installer scripts are **baked into the published images** — you do not need to build
anything or clone the service repos. You clone two repos and run one script.

---

## 1 · Prerequisites

- **Docker Desktop** (macOS/Windows) or Docker Engine (Linux) with **Compose v2**
  (`docker compose version` must work).
- **git**.
- Pull access to the `manishsv/airawatos-*` images on Docker Hub. If the pull is denied, run
  `docker login` with an account that has access (ask the maintainer).
- The images are built for `linux/amd64`. On Apple Silicon they run under Docker Desktop's emulation
  automatically — it works, just a little slower on first boot. On Linux/amd64 they run natively.
- Ports **80** (web) and the compose service ports must be free.

## 2 · Get the code (two repos, nested)

Clone the OS repo, then clone `components` **inside it** (the installer reads the base-app source from
`./components/apps`):

```bash
git clone https://github.com/AirawatOS/airawatos.git
cd airawatos
git clone https://github.com/AirawatOS/components.git
```

Your tree should look like `airawatos/` with a `components/` folder inside it.

## 3 · Install

```bash
cd deploy/local
./airawatos-install.sh
```

It will ask for:
- an **instance name** — lowercase, e.g. `labour`, `health`, `pune` (this becomes your realm prefix);
- an **operator admin password** — entered with no echo, confirmed twice. This sets the initial password
  for every realm admin; each admin is forced to change it on first login.

To run it non-interactively:

```bash
INSTANCE=labour OPERATOR_PASSWORD='ChangeMe@123' ./airawatos-install.sh
```

The script brings the stack up de-seeded (no demo accounts), reads the Vault token automatically, provisions
the four realms + admins, governs the base vocabulary, and delivers + shelves the Base-OS suite. Takes a couple
of minutes on first run (image pulls + base-app seeding).

## 4 · Sign in

Open **http://localhost/login** and sign in as `admin` in any realm with the password you set. You'll be asked
to set a new password on first login.

| Realm (login) | Role | What it's for |
|---|---|---|
| `<instance>-operator` | platform.admin | runs the box (the operator) |
| `<instance>-network`  | network.admin  | the dictionary / network authority (has **Network Admin**) |
| `<instance>`          | platform.tenant-admin | the data tenant |
| `<instance>-developer`| platform.tenant-admin | development + component steward |

Every admin desktop has: **Admin** (add/manage users), **Settings**, **Files**, **Console**, **Inbox**,
**Personal Assistant**, and the **Marketplace** (to install more components).

## 5 · Teardown / fresh reinstall

```bash
docker compose down -v        # removes containers + volumes (full reset)
./airawatos-install.sh        # install again
```

---

## Notes

- **No source bind-mounts.** The de-seeded/realm-scoped identity, the first-login reset flow, and the base-OS
  seeding are baked into `manishsv/airawatos-reference:0.2.83-auth-installer` / `:0.2.116-installer` and
  `manishsv/airawatos-network:0.3.7-installer` (pinned in `docker-compose.yml`). `docker-compose.override.yml.dev-example`
  is only for maintainers who want to run edited local source — copy it to `docker-compose.override.yml` to activate.
- **Your data is yours.** The operator password you type is passed to the provisioner via the process
  environment only — never written to a file or printed. The database password is a machine secret generated
  into Vault; the operator is not shown it.
- **Rebuilding the baked images** (maintainers only): the overlay recipes are in `deploy/local/overlays/`.

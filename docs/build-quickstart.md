# Quickstart — build with the `aos` CLI

*From nothing to a running component in a dev sandbox — the code-first way.*

You build AirawatOS components in your own editor with a small CLI called **`aos`**. You write ordinary
Python against **one object (`ctx`)**; the SDK derives the component's contract from your code, runs it,
and deploys a whole solution into your **development sandbox** — a tenant that is yours, where governance
is auto-approved and nothing can reach production until you promote it. Studio (the in-browser build
workspace) is a second front door onto the *same* pipeline; this is the code-first one.

## 1. Install

```bash
pip install --pre airawatos-aos        # the `aos` command lands on your PATH
# from Git instead:  pip install "git+https://github.com/AirawatOS/components.git#subdirectory=_common"
aos --help
```

`aos` is published as an **early alpha**, so `--pre` is required (plain `pip install airawatos-aos` skips
pre-releases). If your system Python refuses the install (`externally-managed-environment`), create a venv
first: `python3 -m venv ~/aos-env && source ~/aos-env/bin/activate`.

`aos` is a thin client — it holds no data and runs no services. It talks to a network + kernel over HTTP,
so you point it at whichever platform you want (step 3). Some drivers that bucket data by H3 cell also want
the geo extra: `pip install --pre "airawatos-aos[geo]"`.

## 2. (Optional) a platform to build against

You don't need one to *start* — `aos check`, `aos test`, and `aos deploy --sandbox` all run fully offline
against an in-memory registry. You only need a live platform for `--live`. Three ways to have one:

- **Hosted** — point `aos` at the shared platform (`https://airos.airawat.org`); your dev tenant lives there.
- **Local** — run the platform's Docker stack on your machine and point `aos` at `localhost`.
- **None** — stay offline; `--sandbox` proves the whole pipeline with no services at all.

## 3. Configure the target once

`aos config` persists your target to `~/.aos/config.json`, so you set it once instead of exporting env vars
every run. (An env var still overrides for a one-off; resolution is env → config → default.)

```bash
aos config set network=https://airos.airawat.org/network \
               kernel=https://airos.airawat.org/kernel \
               issuer=https://airos.airawat.org/auth/realms/airawatos \
               client-id=aos-cli
aos config list          # shows each value and where it came from (env | config | default)
```

## 4. Log in

`aos login` opens your browser, you authenticate, and the token is captured back and cached
(`~/.aos/credentials.json`, auto-refreshed). No pasting tokens.

```bash
aos login                # browser OIDC (Authorization Code + PKCE)
aos login --device       # headless shells: shows a code to enter in a browser elsewhere
```

Against a **local** dev stack there's usually a passwordless dev login and you can skip this.

## 5. Scaffold a component

```bash
aos new driver my-sensors        # or:  aos new engine my-engine   |   aos new app my-app
```

You get a folder with `run.py` (the SDK model — `@driver.main` / `@engine.verb`, using `ctx`) and a minimal
`meta.yaml` carrying only identity. **You do not hand-write what the component reads, writes, or calls** —
the SDK derives that from your code (next step). Write your logic:

```python
from aos import driver, ctx

@driver.main
def run():
    aoi = ctx.get(AOI_ID, "space.aoi")                       # a READ (tracked)
    rows = fetch_readings(aoi)                               # your logic
    ctx.write_many(rows, valid_from_field="observed_at")     # a WRITE (tracked), bitemporal
```

`ctx` is the one I/O surface — `facts / get / write / write_many / file.put|get / fetch` (brokered egress
with server-side secret injection) / `facts_x` (cross-tenant) / `ai / recommend / …` — identical whether your
code runs in-process or headless. See [Working with governed data](/developer/build/governed-data/) and
[Anatomy of a component](/developer/build/anatomy/).

## 6. Check + test — locally, no services

```bash
aos check my-sensors     # derives meta from the code (reads/writes/scopes/files/egress/secrets) + validates
aos test  my-sensors     # runs it against an in-memory registry (seed with a fixtures.json) — no network
```

`aos check` is the single gate: it prints the **derived** `meta.yaml` and fails if the vocabulary is
malformed. What you touched is a function of what your code did — you never hand-maintain it.

## 7. Deploy to your sandbox

A whole vertical is declared once in a **`solution.yaml`** (members, subscriptions, schemas, viz layers).
Deploy it:

```bash
aos deploy --sandbox my-solution                          # offline: proves the whole closure, no services
aos deploy --sandbox --live my-solution --tenant <you>    # live: govern → certify → install → seed into your dev tenant
aos destroy --sandbox --live my-solution --tenant <you>   # reverse it all (idempotent)
```

In a **development** tenant the network **auto-approves** the schemas/roles/verbs your solution declares
(quarantined to your tenant), certifies your components from source, installs the closure, and seeds the
subscriptions + viz layers — everything marked **"Under Development."** Nothing here can be published to the
Marketplace or Service Directory: that gate is deliberate. When it's ready, you **promote** dev → production
through a reviewed path — from the CLI or from **Solution Studio** (which drives the same publish +
promotion pipeline, with the governance gates in the UI). See
[Governance & Decisions](/developer/deep-dives/governance/).

## The loop, end to end

```
pip install --pre airawatos-aos → aos config set → aos login
aos new → write code (ctx) → aos check → aos test        # inner loop, offline
aos deploy --sandbox [--live]                             # whole solution into your dev sandbox
→ promote to production (reviewed)
```

Next: what a [component](/developer/deep-dives/components/) is, [the Clean Room](/developer/build/capabilities/)
it runs in, [Build, test, publish](/developer/build/lifecycle/), and how
[solutions](/developer/deep-dives/solutions-services/) compose components.

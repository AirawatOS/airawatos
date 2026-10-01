# Quickstart — build & deploy with the `aos` CLI

*From nothing to an app running on your dev sandbox — the code-first way.*

You build AirawatOS components in your own editor with a small CLI, **`aos`**. You write ordinary Python
against **one object (`ctx`)**; the SDK derives the component's contract from your code, runs it, and deploys
a whole solution into your **development sandbox** — a tenant that's yours, where governance is auto-approved
and nothing can reach production until you promote it. (Studio, the in-browser workspace, is a second front
door onto the same pipeline.)

## 1 · Install

```bash
python3 -m venv ~/aos-env && source ~/aos-env/bin/activate
pip install --pre airawatos-aos        # early alpha → --pre is required
aos --help
```

`aos` is a thin client — no data, no services. Some geo drivers also want the extra:
`pip install --pre "airawatos-aos[geo]"`. (If your system Python refuses the install with
`externally-managed-environment`, the venv above is the fix.)

## 2 · Scaffold a component

```bash
mkdir ~/aos-demo && cd ~/aos-demo
aos new driver ds:airawatdeveloper:driver/hello-weather --into hello-weather
# or:  aos new app <id>   |   aos new engine <id>
```

You get `run.py` (the SDK model) and a minimal `meta.yaml` carrying only identity — you never hand-write
what the component reads, writes, or calls; `aos check` derives that from the code.

## 3 · Write the logic — against `ctx`

Edit `hello-weather/run.py`:

```python
"""Hello Weather — a tiny driver that writes one governed fact."""
from aos import driver, ctx

@driver.main
def run():
    rows = [{
        "schema": "demo.greeting",
        "id": f"ds:{ctx.tenant}:demo.greeting/hello",
        "observed_at": ctx.now(),
        "prov": {},
        "message": f"Hello from {ctx.tenant}!",
    }]
    n = ctx.write_many(rows)                      # a WRITE (tracked), bitemporal
    print(f"{n} fact(s) written to tenant {ctx.tenant}")
```

`ctx` is the one I/O surface — `get`/`facts` to read, `write`/`write_many` to write, `fetch` to call an
allowed site (secrets injected server-side), `file` for blobs, `ai` to ask the model. See
[Working with governed data](/developer/build/governed-data/) and [Anatomy of a component](/developer/build/anatomy/).

## 4 · Check, derive, test — all offline

```bash
aos check hello-weather        # derives reads/writes/scopes/egress/secrets into meta + validates
aos meta  hello-weather --write
aos test  hello-weather        # runs it against an in-memory registry — no services
#   → 1 fact(s) written …  writes=['demo.greeting']
```

## 5 · Add an app (a clickable tile)

A driver is headless — it writes **data** (visible in the Data app), not a screen. For something to open on
the desktop, add an **app**. Create `hello-greeter/meta.yaml`:

```yaml
component_id: ds:airawatdeveloper:app/hello-greeter
kind: app
version: 0.1.0
provider: ds:airawatdeveloper:developer
display_name: Hello Greeter
icon: 👋
entrypoint: index.html        # SPA entry inside the bundle
bundle: dist                  # the static bundle served under /apps/<id>/
sandboxed: true
required_schemas: [demo.greeting]    # the data it's allowed to read
```

and `hello-greeter/dist/index.html`:

```html
<!doctype html><meta charset="utf-8">
<title>Hello Greeter</title>
<style>
  body{margin:0;min-height:100vh;display:grid;place-items:center;
    background:#0e1310;color:#e7ede9;font-family:system-ui,sans-serif}
  .card{background:#151b18;border:1px solid #26302b;border-radius:16px;padding:40px 44px;text-align:center}
  .who{color:#57d6c4;font-weight:700}
</style>
<div class="card">
  <div style="font-size:3rem">👋</div>
  <h1>Hello from <span class="who" id="t">…</span></h1>
  <p>Your first AirawatOS app — it runs in the browser as you, reading only what it declared.</p>
</div>
<script>
  // the app-host injects config.json (tenant, the signed-in user's context)
  fetch('config.json').then(r=>r.json()).then(c=>{
    document.getElementById('t').textContent = c.tenant || 'your tenant';
  }).catch(()=>{ document.getElementById('t').textContent = 'your tenant'; });
</script>
```

An **app holds no authority** — it runs as the signed-in user and reaches data only through the platform.

## 6 · Compose a `solution.yaml`

A solution bundles members and installs them together:

```yaml
solution: hello-weather-demo
environment: development
members:
  reuse: []
  build:
    - hello-weather        # the driver (writes demo.greeting)
    - hello-greeter        # the app (the 👋 tile)
```

## 7 · Prove the whole closure offline

```bash
aos deploy --sandbox . --tenant airawatdeveloper
#   → build: hello-weather · build: hello-greeter · install · Under Development
```

Offline dry-run — governs, certifies, installs, seeds, with **no services**. Confirms the solution is
complete before you touch a platform.

## 8 · Deploy to your sandbox and see it

Two real sandboxes — pick whichever you have:

**Your own local stack** (desktop at `localhost:8099`):
```bash
aos deploy --sandbox --live . --tenant airawatdeveloper
```

**The hosted sandbox** (`airawatdeveloper` on airos.airawat.org) — one command:
```bash
platform-spec/deploy/ec2/ec2-deploy.sh ~/aos-demo airawatdeveloper
```

Then open the tile:

```
https://<your-host>/apps/hello-greeter/          # e.g. https://airos.airawat.org/apps/hello-greeter/
```

Everything lands **"Under Development,"** quarantined to your tenant. Reverse any time with
`aos destroy --sandbox --live`.

## 9 · Promote (when it's ready)

Dev tenants **cannot** publish directly — promotion to the **Marketplace** is a *reviewed* gate (via Studio
or `aos publish`). That's deliberate: your sandbox is for building and testing; the world sees it only after
review. See [Governance & Decisions](/developer/deep-dives/governance/).

## The loop, end to end

```
pip install --pre airawatos-aos
aos new → write code (ctx) → aos check → aos test        # inner loop, offline
aos deploy --sandbox [--live]                            # your own desktop (local)
ec2-deploy.sh … airawatdeveloper                         # hosted sandbox → see the tile
→ promote to the Marketplace (reviewed)
```

## Good to know

- **`solution.yaml` is format-agnostic** — block *or* inline, whether or not PyYAML is installed.
- **Pointing at a platform:** `aos config set network=… kernel=…` persists a target to `~/.aos/config.json`
  (env overrides per-run). The offline inner loop (steps 1–7) needs no config at all.
- **Hosted deploy today** runs through `ec2-deploy.sh` (it executes the deploy inside the hosted app-host).
  Running `aos deploy --live` straight from your laptop against the hosted sandbox arrives with auth
  hardening (`aos login`); the dev sandbox is passwordless for now and intentionally not publicly exposed.

Next: what a [component](/developer/deep-dives/components/) is, [the Clean Room](/developer/build/capabilities/)
it runs in, and how [solutions](/developer/deep-dives/solutions-services/) compose components.

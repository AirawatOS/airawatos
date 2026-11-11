---
summary: When and how to write each kind of component — driver, engine, pipeline, app, AI agent, skill, adapter — each with a minimal real example, and how they compose into a solution.
audience: developer
keywords: driver, engine, pipeline, app, agent, skill, adapter, meta.yaml, aos, ctx, solution
---

# Writing components

*One block, seven shapes. Pick the shape that matches the job, write ~20 lines against `ctx`, declare nothing you can derive — then certify, publish, install.*

Everything you build is a [component](/developer/deep-dives/components/): the same folder, the same `register → check → certify → list → pull → verify → install` path, the same clean-room runtime. What changes between a **driver** and an **app** is only *the job it does* and *the handful of fields in `meta.yaml` that say so*. This page is the map: which shape for which job, and the minimal real example of each.

Every runnable kind is written against the SDK's single I/O object, **`ctx`** — `ctx.facts`/`ctx.get` to read, `ctx.write` to write, `ctx.fetch` to call an outside site, `ctx.ai` for the model. It can touch *only* what its code uses; `aos check` reads your code and writes the `reads`/`writes`/`egress`/`secrets` lists into `meta.yaml` for you. You never hand-maintain them. (Why that's safe: [the Clean Room](/developer/build/capabilities/).)

## Pick a shape

```svg
<svg viewBox="0 0 720 300" role="img" aria-label="Decision guide for choosing a component kind" font-family="system-ui,sans-serif" font-size="13" fill="currentColor">
  <style>
    .q{fill:none;stroke:currentColor;stroke-width:1.5}
    .k{fill:none;stroke:currentColor;stroke-width:1.5}
    .lbl{font-size:12px} .kind{font-weight:600}
  </style>
  <text x="20" y="28" class="kind" font-size="14">What does it do?</text>
  <!-- rows -->
  <g transform="translate(20,52)">
    <text x="0" y="0" class="lbl">Bring outside data in → governed facts</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">driver</text>
  </g>
  <g transform="translate(20,86)">
    <text x="0" y="0" class="lbl">Compute over governed facts, expose a verb</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">engine</text>
  </g>
  <g transform="translate(20,120)">
    <text x="0" y="0" class="lbl">Run several components in a fixed order</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">pipeline</text>
  </g>
  <g transform="translate(20,154)">
    <text x="0" y="0" class="lbl">A screen a person clicks</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">app</text>
  </g>
  <g transform="translate(20,188)">
    <text x="0" y="0" class="lbl">Reason over facts + rules → a cited recommendation</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">skill</text>
  </g>
  <g transform="translate(20,222)">
    <text x="0" y="0" class="lbl">Bundle skills into one named AI expert</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">agent</text>
  </g>
  <g transform="translate(20,256)">
    <text x="0" y="0" class="lbl">Carry messages to/from an outside channel</text>
    <line x1="330" y1="-4" x2="470" y2="-4" class="q" marker-end="url(#a)"/>
    <rect x="474" y="-18" width="110" height="22" rx="5" class="k"/><text x="484" y="-2" class="kind">adapter</text>
  </g>
  <defs><marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="currentColor"/></marker></defs>
</svg>
```

Every runnable kind reads and writes **only through the broker** — the single door. A driver may also reach one declared outside host; an app holds no authority at all and acts as the signed-in user.

```svg
<svg viewBox="0 0 720 150" role="img" aria-label="Components reach the registry and outside hosts only through the broker" font-family="system-ui,sans-serif" font-size="12" fill="currentColor">
  <style>.b{fill:none;stroke:currentColor;stroke-width:1.5} .e{stroke:currentColor;stroke-width:1.5;fill:none}</style>
  <rect x="20" y="55" width="150" height="40" rx="6" class="b"/><text x="95" y="79" text-anchor="middle" font-weight="600">component (ctx)</text>
  <rect x="285" y="55" width="110" height="40" rx="6" class="b"/><text x="340" y="79" text-anchor="middle" font-weight="600">broker</text>
  <rect x="520" y="12" width="180" height="36" rx="6" class="b"/><text x="610" y="34" text-anchor="middle">registry (facts)</text>
  <rect x="520" y="58" width="180" height="36" rx="6" class="b"/><text x="610" y="80" text-anchor="middle">model gateway</text>
  <rect x="520" y="104" width="180" height="36" rx="6" class="b"/><text x="610" y="126" text-anchor="middle">declared outside host</text>
  <line x1="170" y1="75" x2="285" y2="75" class="e" marker-end="url(#b)"/>
  <text x="200" y="68" font-size="11">read / write / fetch / ai</text>
  <line x1="395" y1="70" x2="520" y2="34" class="e" marker-end="url(#b)"/>
  <line x1="395" y1="75" x2="520" y2="76" class="e" marker-end="url(#b)"/>
  <line x1="395" y1="80" x2="520" y2="120" class="e" marker-end="url(#b)"/>
  <text x="408" y="118" font-size="11">secret injected here —<tspan x="408" dy="14">the component never sees it</tspan></text>
  <defs><marker id="b" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="currentColor"/></marker></defs>
</svg>
```

---

## Driver — bring outside data in

**When:** you need data from a sensor, an API, a file, or another system turned into **governed facts**. A driver is the only kind that routinely reaches an outside host (`ctx.fetch`, declared `egress`), and the only kind whose whole job is `ctx.write`.

```python
# run.py
from aos import driver, ctx

@driver.main
def run():
    tenant = ctx.tenant                                  # resolved from the run token, not configurable
    aoi = ctx.get(AOI_ID, "space.aoi")                   # read one fact by id
    r = ctx.fetch("https://api.example.org/readings")    # brokered egress; auth applied broker-side
    for row in r.json()["results"]:
        ctx.write(schema="air.sensor_reading",
                  id=f"ds:{tenant}:air/sensor_reading/{row['id']}",
                  value=row["pm25"], observed_at=row["ts"])   # tenant stamped, write tracked
    # or in one round-trip: ctx.write_many(facts, valid_from_field="observed_at")

if __name__ == "__main__":
    raise SystemExit(driver.run())
```

```yaml
# meta.yaml  (reads/writes/egress/secrets are AUTO-DERIVED by `aos check` — don't hand-edit)
component_id: ds:<tenant>:driver/<name>
kind: driver
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
confinement_min: L1
egress:
  - { host: api.example.org, rate_per_min: 60, user_agent: "AirawatOS/<name>" }
secrets: [EXAMPLE_API_KEY]        # by NAME only; the broker injects the Vault value
```

**Ship it:** `aos check` (derives the contract) → `aos test` (runs against an in-memory registry) → certify + publish + install. See [Build, test, publish](/developer/build/lifecycle/).

---

## Engine — compute over governed facts

**When:** you have facts and need to *derive* something from them — a rollup, a join, a score, a projection — and expose it as a **verb** other components and the platform can call. An engine never reaches outside; it reads and writes governed facts only.

```python
# run.py — no __main__; the host discovers the HANDLERS global
from aos import engine, ctx

@engine.verb("assess-effectiveness", implements="intelligence.assess_effectiveness@0.1.0")
def assess_effectiveness(body):                          # request dict in, JSON-able dict out
    decided = ctx.facts("governance.decision").where(lambda d: d.get("outcome") == "approved")
    out = []
    for d in list(decided)[:20]:
        ctx.write({"schema": "intelligence.effectiveness",
                   "id": f"ds:{ctx.tenant}:intelligence/effectiveness/{d['id'].split('/')[-1]}",
                   "decision": d["id"], "score": score(d)})
        out.append({"decision": d["id"]})
    return {"assessed": len(out), "results": out}

HANDLERS = engine.handlers()                             # the entrypoint: built from the @engine.verb decorators
```

```yaml
# meta.yaml
component_id: ds:<tenant>:engine/<name>
kind: engine
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
implements: [intelligence.assess_effectiveness@0.1.0]   # the governed verb contract(s) it fulfils
verbs:
  assess-effectiveness: intelligence.assess_effectiveness@0.1.0
```

The verb it implements must be a **governed interface**. If yours doesn't exist yet, propose it first — [Designing a verb](/developer/build/designing-a-verb/).

---

## Pipeline — run components in order

**When:** a job is really *several* components that must run in a fixed sequence (acquire → index → notify). A pipeline holds **no** docker or secret authority of its own; it *requests* placement of each member through the runtime manager, member by member, each under its own run token.

```yaml
# meta.yaml
component_id: ds:<tenant>:pipeline/<name>
kind: pipeline
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
stages:
  - { stage: acquire, members: [driver/rainfall, driver/terrain-dem] }
  - { stage: index,   members: [engine/cell-indexer] }
  - { stage: notify,  writes: platform.inbox_item }
members:
  - ds:<tenant>:driver/rainfall
  - ds:<tenant>:engine/cell-indexer
```

The entrypoint is an ordered list of `(label, member, token, env)` run in sequence — each member placed via the governed `platform.runtime_invoke` (the same door the scheduler uses), so the pipeline itself stays unprivileged.

---

## App — a screen people use

**When:** a person needs to *see* or *do* something. An app is **served, not run** — it holds no component authority, gets no run token, and acts entirely as the **signed-in user** through the host's `/bridge/*` seam. It never touches data directly.

```html
<!doctype html>
<link rel="stylesheet" href="/shared/aos.css">
<script src="/shared/aos.js"></script>
<div id="app"></div>
<script>
  await AOS.config();                        // reads ./config.json → the host-injected app_id
  const cams = await AOS.query('device.camera');          // POST /bridge/query (scoped to the user)
  await AOS.run('camera-configure', { id: cams[0].id });  // POST /bridge/<verb>
</script>
```

```yaml
# meta.yaml
component_id: ds:<tenant>:app/<name>
kind: app
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: index.html      # or dist/index.html
bundle: dist
sandboxed: true
required_schemas: [device.camera]    # what it reads AS THE USER (no run-token reads)
roles: [safety.incident-commander]   # optional: who may open it
```

Apps adopt the shared runtime (`/shared/aos.js`, `/shared/aos.css`) so you write screens, not plumbing — see the [design system](/developer/deep-dives/components/).

---

## Skill — reason over facts and rules

**When:** you want an AI step that turns **facts × approved rules → a cited `governance.recommendation`** — and never decides on its own. A skill is the atomic reasoner; it runs confined like a driver (`@driver.main`, its own token and trigger) and grounds every output in real records.

```python
# run.py
from aos import driver, ctx

@driver.main
def run():
    rules = [r.get("object") or r for r in ctx.facts("governance.rule").list()]
    facts = ctx.facts("air.quality").recent("observed_at")
    text = ctx.ai([{"role": "system", "content": open("SKILL.md").read()},
                   {"role": "user", "content": render(facts, rules)}])   # brokered model
    ctx.write({"schema": "governance.recommendation", "id": rec_id,
               "method": "rule", "produced_by": f"component://{CID}@{VER}",
               "body": text, "cites": [f["id"] for f in facts]})

if __name__ == "__main__":
    raise SystemExit(driver.run())
```

```yaml
# meta.yaml
component_id: ds:<tenant>:skill/<name>-advisory
kind: skill
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
domain: <domain>
applies_to_facts: [air.quality]
rules_domain: air.quality
reasoning: hybrid                 # deterministic | assisted | hybrid
triggers: [manual, schedule, on-fact-change]
instructions: SKILL.md            # the persona + method the model follows
writes: [governance.recommendation]
```

`SKILL.md` holds the persona and method (YAML frontmatter + prose). A recommendation **proposes**; a human or an authority turns it into a signed decision — [From evidence to action](/developer/deep-dives/decision-support/).

---

## AI Agent (Expert) — a named bundle of skills

**When:** you want to offer a *person-facing expert* ("Air Quality Expert") that is really **several skills** wired together under one identity and persona. The agent itself does not reason — its skills do. It touches nothing (`reads: []`, `writes: []`); installing it fans out to install its skills, each on its own token and trigger.

```yaml
# meta.yaml   (entrypoint run.py is a thin bundle marker: SKILLS = [...] )
component_id: ds:<tenant>:agent/<name>
kind: agent
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
summary: Watches the facts, applies approved rules, proposes cited advisories.
domain: <domain>
persona: >-
  A careful public analyst. Grounds every recommendation in measured facts and
  approved rules, cites its sources, and proposes — never decides.
skills:
  - ds:<tenant>:skill/<name>-advisory
reads: []
writes: []
```

---

## Adapter — carry messages to an outside channel

**When:** you want citizens to reach a service through a channel the platform doesn't own — Telegram, WhatsApp, SMS. An adapter is **fully confined** (clean room, L1): its only outside reach is one declared host, and any credential (the bot token) is a **per-tenant Vault secret the broker injects** — the code never sees it. It reads the agency's governed data, grounds a reply, and pushes it out.

```python
# run.py
from aos import driver, ctx, egress
import os

INJECT = {"name": "TELEGRAM_BOT_TOKEN", "as": "template", "placeholder": "{TOKEN}", "safe": ":"}
egress("api.telegram.org", rate_per_min=30, user_agent="AirawatOS/telegram", secret="TELEGRAM_BOT_TOKEN")

@driver.main
def run():
    tenant = ctx.tenant
    if os.environ.get("MODE") == "setwebhook":           # a post-config ACTION (see below)
        hook = f"{os.environ['PUBLIC_BASE']}/t/{tenant}/telegram/webhook"
        ctx.fetch("https://api.telegram.org/bot{TOKEN}/setWebhook",
                  method="POST", body={"url": hook}, inject=INJECT)
        return
    caps = [c for c in ctx.facts("platform.capability").list()]   # the agency's published services
    reply = ctx.ai([{"role": "system", "content": GROUND}, {"role": "user", "content": question}])
    ctx.fetch("https://api.telegram.org/bot{TOKEN}/sendMessage",
              method="POST", body={"chat_id": chat_id, "text": reply}, inject=INJECT)

if __name__ == "__main__":
    raise SystemExit(driver.run())
```

```yaml
# meta.yaml
component_id: ds:<tenant>:adapter/<name>
kind: adapter
version: 0.1.0
provider: ds:<tenant>:developer
entrypoint: run.py
confinement_min: L1
reads: [platform.capability, platform.experience, platform.publication, platform.agency_profile]
egress:
  - { host: api.telegram.org, rate_per_min: 30, user_agent: "AirawatOS/<name>" }
secrets: [TELEGRAM_BOT_TOKEN]
actions:                           # post-config buttons shown in Settings → Components
  - { id: setwebhook, label: "Activate", mode: setwebhook, needs: TELEGRAM_BOT_TOKEN,
      confirm: "Point the channel at this agency's webhook now?" }
```

**Two rules the platform enforces on an adapter (and any runnable kind):**

- The entrypoint must actually run — end with `if __name__ == "__main__": raise SystemExit(driver.run())`. `@driver.main` only *registers* `run`; without the call, `python run.py` defines it and exits doing nothing.
- Every `mode` you advertise under `actions:` must be **handled in the code**, and every `needs:` must name a secret you declare. The certifier checks this and withholds the certificate otherwise — a button can never fire a silent no-op.

Config a tenant admin sets at install (like `TELEGRAM_BOT_TOKEN`) lives in Vault; the admin clicks **Activate** in Settings → Components to run the `setwebhook` action — no shell, no token in anyone's hands but Vault's.

---

## Compose them into a solution

A single kind rarely ships alone. A **[solution](/developer/deep-dives/solutions-services/)** is a pinned member-graph — a set of components installed together as one unit, with its schemas, verbs and roles governed up front. You write each member as above, then declare the graph and install it into a tenant.

The capstone tutorial builds a real one end to end — a citizen-complaints service for a city: an **adapter** lets residents file a complaint (with a photo) over Telegram and check status; a **driver** pulls complaints proactively from news and social feeds into the same spine; an **engine** finds complaint **hotspots** and proposes permanent fixes; a **skill**/**agent** tracks each complaint to closure and helps staff and vendors resolve it against guidelines, contracts, asset inventory and terrain; and an **app** gives the desk its queue. → **[Complaints, end to end](/developer/tutorials/complaints-end-to-end/)**.

> New to the lifecycle? Start with the [Quickstart](/developer/build/quickstart/) and [Anatomy of a component](/developer/build/anatomy/), then come back here to pick your shape.

# Tutorial: Ship your first interoperable solution

> **Goal:** build, certify, publish, and install a complete AirawatOS solution — a **Ward Air‑Quality board** —
> and watch it become reusable across tenants. You'll touch every moving part: a **driver** (pull data), a
> **governed schema** (the interoperability contract), an **engine** (compute), an **app** (UI), a **solution**
> (the installable bundle), the **marketplace** (certify → publish → approve → install), and the **broker**
> (the only door to the outside world).

**What you'll build**

```
  OpenAQ (external API)                       Ward Air‑Quality
        │  ctx.fetch (brokered egress)          board (app)
        ▼                                           ▲
  ward-air  ──writes──▶  air.sensor_reading  ──read─┘
  (driver)                     │
                               ▼  ward-aqi (engine) rolls readings up per H3 cell
                           air.quality  ◀─────────────────────────────────────────
```

Three components, one solution. `air.sensor_reading` and `air.quality` are **network‑governed schemas** — so the
engine never needs to know *how* the driver got the data, and anyone else's app can read your `air.quality` with
zero integration. That's the whole point.

**Time:** ~60–90 min. **Audience:** a developer comfortable with Python + the command line.

---

## 0 · Prerequisites

1. A running AirawatOS stack. The fastest is your laptop — follow **[install-local.md](install-local.md)**, then
   confirm `curl -s localhost/network/v1/health` returns `{"status":"ok"}`.
2. The `aos` SDK + CLI:
   ```bash
   pip install --pre "airawatos-aos[geo]>=0.1.0a3"    # [geo] pulls h3/shapely for cell indexing
   aos --version
   ```
3. Point `aos` at your stack and sign in as the developer participant:
   ```bash
   aos config set network=http://localhost:8090 kernel=http://localhost:8080 \
                  identity=http://localhost:8093 app-host=http://localhost:8099
   aos login                         # local dev IdP is passwordless: realm=airawatdeveloper, user=devrick
   ```

> **The mental model.** You build components locally; the platform **governs, certifies, delivers, and runs**
> them. You never hand‑wire infrastructure, and you never get unrestricted access — a component gets exactly the
> scopes its certificate declares.

Reference implementations to compare against as you go (all shipped in the repo):
`components/drivers/firms-fire` (a real fetching driver), `components/drivers/air-lowcost-sensors`
(writes `air.sensor_reading`), `components/engines/effectiveness-engine-aos` (an engine), and
`components/solutions/water-safety-aos` (a `solution.yaml`).

---

## 1 · Scaffold the driver

```bash
aos new driver ward-air
cd ward-air
ls
# meta.yaml   run.py
```

Open `meta.yaml`. The key idea: **you do not hand‑maintain `reads`/`writes`/`scopes`** — `aos check` derives them
from what your code actually does. You *do* declare the two things the code can't self‑declare safely: the
**external hosts** you call (`egress`) and the **secret names** you need.

```yaml
# meta.yaml
component_id: ds:airawatdeveloper:driver/ward-air
kind: driver
version: 0.1.0
provider: ds:airawatdeveloper:participant/developer
entrypoint: run.py
confinement_min: L1
display_name: Ward Air Quality (ingest)

# The ONLY outside host this driver may reach. The broker enforces this at runtime; the certificate binds it.
egress:
  - { host: api.openaq.org, rate_per_min: 30, user_agent: "AirawatOS/ward-air (+https://airawat.org)" }

# Optional: OpenAQ works keyless for low volumes; if you have a key, name it here and set it per-tenant later.
secrets: [OPENAQ_API_KEY]
```

> **Why declare egress?** A confined component can't open arbitrary sockets — it reaches the world **only** through
> the broker's `ctx.fetch`, and only to hosts on this list. At certification the Network signs this declaration;
> at install the tenant grants it; at runtime the broker enforces it and injects any secret **server‑side** so your
> code never sees it.

---

## 2 · Pick the schema (the contract comes first)

Before writing a line of ingest logic, decide the **shape** the data lands in. This is the interoperability
contract, and it's owned by the **Network Administrator** — not by you. Reuse an existing governed schema whenever
one fits.

```bash
aos check --schemas air          # list governed schemas in the 'air' domain
#   air.sensor_reading   a point-in-space pollutant reading   (measure)
#   air.quality          a per-cell air-quality summary        (measure)
#   air.hotspot          a flagged high-pollution cell
```

`air.sensor_reading` already exists and fits a raw station reading. **Reuse it.** A record looks like:

```json
{
  "id": "ds:<tenant>:air.sensor_reading/<station>-<iso>",
  "space": { "h3": "8860…", "res": 8, "centroid": [77.59, 12.97] },
  "pm25": 142.0,
  "observed_at": "2026-02-01T09:00:00Z",
  "source": "openaq",
  "prov": { "method": "openaq.v3", "component": "ds:airawatdeveloper:driver/ward-air", "station": "Ward-7 AQ" }
}
```

> **Sidebar — proposing a new schema.** If no governed schema fit, you'd *propose* one and the Network
> Administrator would approve it:
> ```bash
> aos schema propose my.domain.thing --kind measure --from schema.json   # → a publish-request to the Network
> ```
> New schemas aren't self‑served: the standards body reviews them, exactly like the OS vendor owning the file
> format. For this tutorial we reuse `air.sensor_reading`, so there's nothing to approve.

---

## 3 · Write the driver

Replace `run.py`. The SDK gives you the broker as `ctx`; your code is just the logic.

```python
"""ward-air — pull PM2.5 station readings from OpenAQ and write them as governed air.sensor_reading facts.

The transport (broker egress + secret injection), tenant resolution, retry, and reads/writes tracking are the
SDK's. The driver only (a) fetches, (b) normalises to the governed schema, (c) writes.
"""
from aos import driver, ctx


@driver.main
def run():
    tenant = ctx.tenant                      # resolved from the broker context
    if not tenant:
        raise SystemExit("FATAL: no tenant in broker context")

    # The area of interest is supplied at install/run time (a bbox). Fall back to a demo bbox for `aos test`.
    aoi = ctx.input("aoi") or {"bbox": [77.55, 12.93, 77.65, 13.00], "h3_res": 8}
    west, south, east, north = aoi["bbox"]
    res = int(aoi.get("h3_res", 8))

    # BROKERED EGRESS: the only way out. The broker checks our declared egress + rate limit, injects
    # OPENAQ_API_KEY into {KEY} server-side (we never see it), sets our User-Agent, and audits the call.
    url = (f"https://api.openaq.org/v3/parameters/2/latest"
           f"?bbox={west},{south},{east},{north}&limit=1000&api_key={{KEY}}")
    res_fetch = ctx.fetch(url, inject="OPENAQ_API_KEY")   # omit inject= if running keyless
    rows = (res_fetch.json() or {}).get("results", [])

    import h3
    facts = []
    for r in rows:
        coord = r.get("coordinates") or {}
        lat, lng, pm25 = coord.get("latitude"), coord.get("longitude"), r.get("value")
        if lat is None or lng is None or pm25 is None:
            continue
        cell = h3.latlng_to_cell(lat, lng, res)
        obs = r.get("datetime", {}).get("utc") or ctx.now()
        facts.append({
            "id": f"ds:{tenant}:air.sensor_reading/{r.get('locationsId','x')}-{obs[:19]}",
            "space": {"h3": cell, "res": res, "centroid": [round(lng, 5), round(lat, 5)]},
            "pm25": float(pm25),
            "observed_at": obs,
            "source": "openaq",
            # provenance travels WITH the data so every downstream consumer can see where it came from
            "prov": {"method": "openaq.v3", "component": ctx.component_id, "station": r.get("location")},
        })

    n = ctx.write_many(facts, valid_from_field="observed_at") if facts else 0   # tenant-stamped, write tracked
    print(f"ward-air: wrote {n} air.sensor_reading facts in tenant {tenant}")
    if n == 0:
        raise SystemExit("no readings written — check the AOI/bbox or the OpenAQ response")   # fail loudly
```

> **Three rules this illustrates** (all from the real platform):
> 1. **The broker is the only door** — `ctx.fetch` to a *declared* host; no raw HTTP.
> 2. **Normalise to the governed schema** — raw OpenAQ shape → `air.sensor_reading`. This is what makes the data
>    interoperable.
> 3. **Carry provenance** — `source` + `prov` ride with every record (the "no synthetic data / fail loudly"
>    discipline: if nothing real came back, raise, don't fabricate).

---

## 4 · Lint and dry‑run (no servers needed)

```bash
aos check
#   ✓ meta well-formed · egress hosts valid · secret names UPPER_SNAKE
#   derived  writes: [air.sensor_reading]   reads: []   (written back into meta.yaml)
#   ✓ air.sensor_reading is a governed schema

aos test
#   offline: governs + certifies + RUNS the driver against an in-memory ctx, NO services.
#   ward-air: wrote 3 air.sensor_reading facts in tenant airawatdeveloper (sample)
```

`aos check` writes the derived `reads`/`writes`/`scopes` back into `meta.yaml` — that's your contract, generated
from the code, not hand-kept. `aos test` proves the logic end‑to‑end with zero infrastructure.

---

## 5 · Deploy to your sandbox and see real data

```bash
aos deploy --sandbox --live . --tenant airawatdeveloper
```

`--live` touches only the kernel (your dev‑token writes) and the app‑host (your bundle); it never calls the
Network. Open **http://localhost/** → the **Data** app → filter `air.sensor_reading`: you should see the rows your
driver just wrote, each with its `space.h3`, `pm25`, and provenance.

Reverse any time with `aos destroy --sandbox --live`.

---

## 6 · Build the engine (compute on the contract)

Now the payoff: a component that reads `air.sensor_reading` and produces `air.quality` **without caring where the
readings came from**.

```bash
cd ..
aos new engine ward-aqi
cd ward-aqi
```

`run.py`:

```python
"""ward-aqi — roll raw air.sensor_reading points up to a per-cell air.quality summary with an AQI band."""
from aos import engine, ctx

def _band(pm25):
    return ("good" if pm25 <= 30 else "moderate" if pm25 <= 60 else
            "poor" if pm25 <= 90 else "very-poor" if pm25 <= 120 else "severe")

# An engine exposes an OPERATION other components can invoke — a governed INTERFACE (a verb).
# `implements` names the interface; reuse a governed one, or request a new one like you would a schema.
@engine.verb("rollup-aqi", implements="intelligence.compute@0.1.0",
             reads=["air.sensor_reading"], writes=["air.quality"])
def rollup_aqi(body):
    tenant = ctx.tenant
    # group the most-recent reading per H3 cell
    latest = {}
    for r in ctx.facts("air.sensor_reading").recent("observed_at"):
        cell = (r.get("space") or {}).get("h3")
        if cell and cell not in latest:
            latest[cell] = r
    out = []
    for cell, r in latest.items():
        pm25 = float(r["pm25"])
        out.append({
            "id": f"ds:{tenant}:air.quality/{cell}",
            "space": r["space"],
            "pm25": pm25, "band": _band(pm25),
            "observed_at": r["observed_at"],
            "prov": {"method": "ward-aqi.rollup", "component": ctx.component_id, "from": r["id"]},
        })
    n = ctx.write_many(out) if out else 0
    return {"cells": n, "note": "per-cell AQI band from the latest reading"}
```

```bash
aos check     # derives reads:[air.sensor_reading] writes:[air.quality], verifies both are governed
aos test
aos deploy --sandbox --live . --tenant airawatdeveloper
```

> **This is interoperability in one line:** `ctx.facts("air.sensor_reading")` reads *any* producer's readings —
> yours, another developer's satellite driver, a city's sensor feed — because they all conform to the same governed
> schema. The engine is decoupled from the source.
>
> **Note on the interface.** An engine that other components *call* implements a governed **interface**
> (`implements=`), which the Network governs just like a schema. If `intelligence.compute` isn't published yet,
> request it (`aos` interface‑request → Network approves), or — for a purely scheduled batch — use `@driver.main`
> instead of `@engine.verb` and run it on a schedule; the body is identical.

---

## 7 · Build the app (the UI)

```bash
cd ..
aos new app air-board
cd air-board
```

Apps are static bundles the **app‑host** serves; they talk to the platform only through the governed
`/bridge/*` seam, never directly to the kernel. Minimal `dist/index.html`:

```html
<!doctype html><meta charset="utf-8"><title>Ward Air‑Quality</title>
<link rel="stylesheet" href="/shared/aos.css">
<body>
  <h1>Ward Air‑Quality</h1>
  <div id="rows">Loading…</div>
  <script type="module">
    import { AOS } from "/shared/aos.js";                 // shared app runtime: session + governed reads
    const COLORS = {good:"#2e7d32", moderate:"#f9a825", poor:"#ef6c00", "very-poor":"#c62828", severe:"#6a1b9a"};
    const cells = await AOS.read("air.quality");           // governed read, scoped to this tenant + session
    document.getElementById("rows").innerHTML = cells.length
      ? cells.map(c => `<div style="padding:8px;border-left:6px solid ${COLORS[c.band]||'#999'}">
            <b>${c.space.h3}</b> — PM2.5 ${c.pm25} · <b>${c.band}</b></div>`).join("")
      : "No air.quality yet — run the driver + engine first.";
  </script>
</body>
```

```bash
aos check && aos deploy --sandbox --live . --tenant airawatdeveloper
```

Open **http://localhost/apps/air-board/** — coloured ward cards, read straight off `air.quality`. The app has no
idea OpenAQ exists; it only knows the contract.

---

## 8 · Compose the solution (the installable bundle)

A **solution** bundles your components so a tenant installs the whole thing in one click. Create
`ward-air-quality/solution.yaml`:

```yaml
# A one-click Ward Air-Quality vertical. `aos deploy --sandbox` stands it up; publishing distributes it.
solution: ward-air-quality
environment: development
display_name: Ward Air-Quality

# schemas the solution RELIES ON but no member produces — declared so install can verify they exist (governed).
external_inputs: [space.aoi]

# members: `build` are your own components (by path); `reuse` are marketplace components PINNED to a version.
members:
  build:
    - drivers/ward-air
    - engines/ward-aqi
    - apps/air-board

viz_layers: [air.quality]           # expose the result as a map layer in City Scan
schedules:
  - { component: ward-air, cron: "0 */6 * * *" }   # refresh readings every 6h (the scheduler runs it)
```

```bash
aos check ./ward-air-quality            # validates the graph: every read has a producer or an external_input
aos deploy --sandbox ./ward-air-quality --tenant airawatdeveloper    # offline: govern + certify + install locally
```

---

## 9 · Certify and request publication

So far everything lived in your sandbox. To distribute it, go through the governed marketplace lane. **Certify**
and **publish** are separate acts — a certified component is *not* automatically public.

```bash
aos publish ./ward-air-quality
#   certify  drivers/ward-air   → cert ds:…/certificate/… (declares egress api.openaq.org, writes air.sensor_reading)
#   certify  engines/ward-aqi   → cert (reads air.sensor_reading, writes air.quality)
#   certify  apps/air-board     → cert
#   filed publish-request: ward-air-quality@0.1.0  (status: pending)
```

The **certificate** is the Network's signed statement of *exactly what each component is approved to do* — its
declared reads/writes/egress/secrets plus the conformance result and a content digest (`evidence_digest`). The
**publish‑request** is your ask to list it; it sits pending until the standards body decides.

> Dev‑tenant components **cannot** publish directly to the marketplace (ADR‑0106) — that's the governance gate.

---

## 10 · The Network Administrator approves

Switch hats to the Network Administrator (the standards body). In the **Network Admin** app (or via the steward
flow) they review the request — they can see the declares + conformance from the signed cert — and approve:

```
publish-request  ward-air-quality@0.1.0
  members: ward-air (driver), ward-aqi (engine), air-board (app)
  declares: egress[api.openaq.org] · writes[air.sensor_reading, air.quality] · secrets[OPENAQ_API_KEY]
  conformance: verified ✓
  [Approve]  →  listed in the Marketplace (source delivered from the filestore, digest-locked)
```

Approval publishes the listing: the component **source** is content‑addressed in the **filestore**, and the
listing records its `source_file_id` so any host can materialise it later, digest‑verified.

---

## 11 · Install into another tenant

Now be a *different* organisation. Sign in to, say, the `kmc` tenant, open the **Marketplace**, find
**Ward Air‑Quality**, and **Install**.

```
Install ward-air-quality@0.1.0 into kmc
  → GRANT: exactly the certified scopes (read/write air.*, egress api.openaq.org)   ← not the dev's trust, the cert's
  → MATERIALISE: fetch source from filestore, verify digest == certificate          ← untrusted bytes never run
  → SCHEDULE: ward-air every 6h
  installed ✓
```

Install is **grant + digest‑verified materialisation** — the tenant trusts the Network's certificate, never the
developer. The same signed listing installs into any number of tenants.

---

## 12 · Configure per‑tenant

If a component needs a credential, the *tenant* supplies it — the software is identical, the secret is tenant‑local.
In **Settings → Components → Ward Air (ingest)**, set `OPENAQ_API_KEY` (if you're using a keyed plan). It lands in
that tenant's Vault at `secret/kmc/ds:airawatdeveloper:driver/ward-air/OPENAQ_API_KEY`; the broker injects it at
run time. `nashik` can install the same component with a *different* key.

Set the area of interest (the `space.aoi`) for the tenant, then trigger a run (or wait for the schedule). Open
**/apps/air-board/** in that tenant — live ward cards from *its* AOI.

---

## 13 · Prove interoperability (the real payoff)

Because `air.quality` is a governed schema, your board isn't the only thing that can use it:

- Install an existing **City Scan** layer or a third party's `air.hotspot` engine — it reads your `air.quality`
  with **zero integration code**.
- A national **provider** or an **aggregator** can request `air.quality` across tenants through the governed
  **data‑request** lane (subject to a signed grant + consent) — not by scraping your app.

You built a producer; the ecosystem composes on it. Nobody had to agree on anything except the schema.

---

## 14 · Operate: version, re‑publish, verify integrity

Improve the AQI bands, bump the version, re‑publish:

```bash
# edit engines/ward-aqi/_band(), then:
#   set version: 0.2.0 in engines/ward-aqi/meta.yaml
aos publish ./ward-air-quality        # certify 0.2.0 → publish-request → Network approves → tenants can upgrade
```

Versions are **immutable + monotone** — you never overwrite `0.1.0`, you ship `0.2.0`. Tenants upgrade on their own
schedule (admin‑gated). To confirm what's running matches what was certified, use the **Supply Chain** tab
(Settings → Components): it digest‑compares each installed component's on‑host source to its certificate and flags
any drift.

---

## What you learned

| Concept | Where you saw it |
|---|---|
| The broker is the only I/O door | `ctx.fetch` + declared `egress` (§3) |
| Schemas are the interoperability contract, governed by the Network | reuse `air.sensor_reading` (§2); engine decoupled from source (§6) |
| Components are the building blocks; a solution bundles them | driver + engine + app → `solution.yaml` (§1–8) |
| Certify ≠ publish; publication is governed | `aos publish` → publish‑request → approve (§9–10) |
| Install = grant + digest‑verified delivery | install into `kmc` (§11) |
| Secrets/config are per‑tenant | `OPENAQ_API_KEY` in Vault (§12) |
| Build once, distribute across the federation | same listing into many tenants (§11, §13) |

**The arc you walked:** `create a driver → choose a schema → import data → build an engine → build an app →
compose a solution → certify → publish → approve → install in another tenant → interoperate`. That's the Airawat
development lifecycle, end to end.

### Where to go next
- **[architecture/services.md](architecture/services.md)** — what each platform service does and how they wire together.
- **[install-local.md](install-local.md)** — run the whole stack on your laptop.
- Deep dives: components, governance, interaction, runtimes (the `/developer` concept chapters).

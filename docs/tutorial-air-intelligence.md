# Tutorial — build a real solution: Air Intelligence

*The [Quickstart](/developer/get-started/quickstart/) shipped a "hello world." This walks through a **real, running** solution — Air Intelligence — so you see how the pieces fit on something that actually does public-interest work: sense air quality, turn readings into a forecast, recommend an advisory, and land it in a named official's inbox for a decision.*

You'll recognise every idea from the [Deep Dives](/developer/deep-dives/) — a **driver** that ingests data, an **engine** that derives a new layer, a **skill** that turns facts and rules into a cited recommendation, and the **universal Inbox** where a person decides. Here they're wired together into one solution.

> This tutorial follows the actual Air Intelligence components in the platform (`ds:airawat:solution/air-intelligence`). The code excerpts are trimmed from the real source — enough to teach the pattern, not the whole file. Where the real system is richer than shown, it says so.

## What we're building

The end-to-end loop:

```
   sense            derive              recommend           decide
 ┌────────┐     ┌──────────────┐     ┌──────────────┐   ┌──────────┐
 │ driver │ ──▶ │   engine     │ ──▶ │    skill     │──▶│  Inbox   │
 │ air-   │     │ station-     │     │ air-quality- │   │ (a named │
 │ sensors│     │ interpolation│     │ advisory     │   │ official │
 └────────┘     └──────────────┘     └──────────────┘   │ decides) │
 air.sensor_     air.quality          governance.        └──────────┘
   reading       (a derived layer)    recommendation      + a receipt
```

- a **driver** (`air-sensors`) pulls PM2.5 readings from public sources into governed facts;
- an **engine** (`station-interpolation`) reads those readings and computes a continuous **air-quality surface**;
- a **skill** (`air-quality-advisory`) applies rules to the surface and produces a **cited recommendation** — *"issue an advisory for this area"*;
- a **router** turns that recommendation into a **task in the universal Inbox**, where a named official reviews the evidence and **decides** — leaving a receipt.

And an app (`air-explorer`) renders the layers and the recommendation on a map.

## The solution manifest

A **solution** is a bundle that installs its members together. Air Intelligence's manifest lists the components above:

```
component_id: ds:airawat:solution/air-intelligence
kind: solution
version: 0.1.0
members:
  - ds:airawat:driver/air-sensors            # sense: readings → governed facts
  - ds:airawat:engine/station-interpolation  # derive: readings → air-quality surface
  - ds:airawat:engine/hotspot-detection      # derive: find the worst cells
  - ds:airawat:skill/air-quality-advisory    # recommend: facts + rules → advisory
  - ds:airawat:engine/decision-router        # route the recommendation to the Inbox
  - ds:airawat:app/air-explorer              # see it on a map
  - ds:airawat:app/inbox                      # where a person decides
```

Install this and all the members come with it, wired together by their declarations. You'll build the interesting ones below.

---

## Step 1 · The driver — readings into governed facts

A **driver** is the only sanctioned way outside data becomes governed state. `air-sensors` fetches PM2.5 from two public sources (India's CPCB network and OpenAQ) and writes one governed fact per reading.

### Its contract (`meta.yaml`)

Everything the driver may touch is declared up front — this *is* its permission set:

```
component_id: ds:airawat:driver/air-sensors
kind: driver
version: 0.2.1
entrypoint: run.py
confinement_min: L1
reads:  [space.aoi]                 # the area of interest to ingest for
writes: [air.sensor_reading]        # the one governed type it may write
egress:                             # the only outside hosts it may call, with a rate cap
  - { host: api.openaq.org,  rate_per_min: 30 }
  - { host: api.data.gov.in, rate_per_min: 40 }
secrets: [OPENAQ_API_KEY, CPCB_API_KEY]   # keys, delivered at use — never in the code
config:  [SOURCE, MAX_LOCATIONS, AS_OF_DATE, RESOURCE_ID, PAGE_LIMIT]
sources:
  - { ref: "ds:airawat:ref/source/openaq", host: api.openaq.org }
  - { ref: "ds:airawat:ref/source/cpcb",   host: api.data.gov.in }
scopes:
  - { verb: read,  scope: space.aoi }
  - { verb: write, scope: air.sensor_reading }
```

A tenant can read this and know *exactly* what the driver does before installing it — and the platform enforces every line of it at runtime. See [What your code can touch](/developer/build/capabilities/).

### The code (`run.py`)

A driver reaches the world **only through the broker** — the single guarded door (see [Zero-Trust](/developer/deep-dives/zero-trust/)). It never opens a socket, reads a key from disk, or writes to the database directly. Every action is a broker call carrying the run-token:

- **read** what it needs — `POST /v1/read` / `/v1/query` (e.g. the tenant's area of interest);
- **call an allowed website** — `POST /v1/fetch` — the broker makes the call, enforces the rate cap, and **injects the secret** (so the key never touches your code);
- **write a governed fact** — `POST /v1/write`.

The write is where governance happens — a **natural key** (so re-running never duplicates), a **space** block, and **provenance**:

```python
def _write(T, sid, lat, lng, res, vals, obs, source, station, method):
    cell = h3.latlng_to_cell(lat, lng, res)
    rid  = f"ds:{T}:air/sensor_reading/{sid}-{obs[:13]}"   # natural key = tenant + sensor + hour → idempotent
    fact = {"schema": "air.sensor_reading", "id": rid, "sensor_id": sid,
            "space": {"h3": cell, "res": res, "centroid": [round(lng, 5), round(lat, 5)]},
            "pm25": vals.get("pm25"), "no2": vals.get("no2"), "o3": vals.get("o3"),
            "observed_at": obs, "source": source,
            "prov": {"method": method, "component": "ds:airawat:driver/air-sensors",
                     "station": station, "observed_at": obs}}
    _call("/v1/write", {"scope": "air.sensor_reading", "id": rid, "object": fact,
                        "valid_time": {"from": obs}})
```

And the fetch side — brokered egress, filter to the area of interest, and (importantly) **write real data or nothing** — never a synthetic fill:

```python
def ingest_cpcb(T, bbox, res):
    w, s, e, n = bbox; offset = 0
    for _ in range(50):
        status, page = _fetch(f"{CPCB_BASE}?format=json&offset={offset}&limit={PAGE_LIMIT}", inject=CPCB_INJECT)
        if status != 200 or not page:
            return 0                                  # no readings → write nothing, fail loudly
        for rec in page.get("records") or []:
            lat, lon = _num(rec.get("latitude")), _num(rec.get("longitude"))
            if lat is None or not (s <= lat <= n and w <= lon <= e):
                continue                              # keep only stations inside the AOI
            # …group rows by station, collect pm25/no2/o3…
    for st in stations.values():
        if "pm25" in st["vals"]:
            _write(T, f"cpcb-{st['slug']}", st["lat"], st["lon"], res, st["vals"], st["obs"], "cpcb", st["name"], "cpcb-caaqms")
```

`main()` resolves the tenant (from the broker's `/v1/context` — never a hardcoded city), loads that tenant's area of interest, and dispatches on the `SOURCE` config. That's the whole driver: **config + AOI → brokered fetch → governed write, with provenance, idempotently.**

### The type it writes

`air.sensor_reading` is a **governed schema** — a shared, agreed shape (see [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/)). It's a *point* observation (a station at a place and time), with `pm25`/`no2`/`o3`, an `observed_at` valid-time, and a `space` block. Because it's governed, every other component — the engine, the app, another agency — reads it the same way. You build against these types; you don't invent private formats.

> **Try it:** a second driver, `openaq-archive`, writes the **same** `air.sensor_reading` type as a historical backfill. Two drivers, one governed noun — that's how independent sources feed one clean layer.

---

## Step 2 · The engine — readings into a derived layer

Stations are sparse points. An **engine** turns them into something usable: a continuous **air-quality surface** over the whole area. `station-interpolation` reads the readings and writes one `air.quality` value per map cell.

### Its contract

```
component_id: ds:airawat:engine/station-interpolation
kind: engine
version: 0.1.0
confinement_min: L1
reads:  [space.aoi, air.sensor_reading]     # the readings the driver wrote
writes: [air.quality]                       # the derived surface it produces
scopes:
  - { verb: read,  scope: air.sensor_reading }
  - { verb: write, scope: air.quality }
```

An engine, like a driver, does all its I/O **through the broker** — it runs under a minted run-token and calls `/v1/read`, `/v1/query`, `/v1/write`. (No open sockets, no ambient credentials — same clean-room contract.)

### The code — read, compute, write a *derived* fact

The engine reads station facts, interpolates onto H3 cells (inverse-distance weighting), and writes each cell with **derived provenance** — the method it used and the inputs it came from, so the value is reproducible and explainable:

```python
rid  = f"ds:{T}:air/quality/{hcell}-{obs[:13]}"
fact = {"schema": "air.quality", "id": rid,
        "space": {"h3": hcell, "res": res, "centroid": [round(lng,5), round(lat,5)]},
        **out, "observed_at": obs,
        "method": "idw", "confidence": confidence,
        "prov": {"method": "idw", "confidence": confidence,
                 "derived_from": ["air.sensor_reading@stations"], "observed_at": obs}}
_call("/v1/write", {"scope": "air.quality", "id": rid, "object": fact,
                    "valid_time": {"from": obs}})
```

That `prov` block is the whole point of a **derived** fact: `air.quality` isn't a mystery number — it says "computed by IDW from the station readings." Trace it back and you reach the driver, the source, and the hour. See [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/) on provenance.

> **Live vs richer:** `station-interpolation` is the simple, live baseline (Model-0). Air Intelligence also ships an ML path — an engine (`pm25-features`) that assembles many governed layers into a training matrix, and `pm25-model` that trains an XGBoost model (with a champion/challenger promotion gate) and writes `air.quality` with model provenance. Both write the *same* `air.quality` type, so everything downstream is unchanged — you can swap a better engine in without touching the app or the advisory. A per-hour **forecast** schema is planned; the shipped layer is the current nowcast.

> **On verbs:** newer engines expose named actions through a `verbs:` map + a `HANDLERS = {verb: fn}` table (the governed verb-dispatch from [Interaction](/developer/deep-dives/interaction/)). The air engines here use the simpler `main()` style; both are valid — pick verbs when other components need to *call* your engine by name.

---

## Step 3 · The recommendation — facts × rules → a cited advisory

Now the intelligence. This is where **AI advises** — and note who does it: **a skill, not the engine.** `air-quality-advisory` reads the air-quality surface and the governed **rules**, and produces a **cited recommendation**.

### Its contract

```
component_id: ds:airawat:skill/air-quality-advisory
kind: skill
applies_to_facts: [air.quality]
rules_domain:     air.quality
reasoning: hybrid                    # a deterministic core + an LLM for the wording
reads:  [space.aoi, governance.rule, air.quality]
writes: [governance.recommendation]
scopes:
  - { verb: read,  scope: governance.rule }
  - { verb: read,  scope: air.quality }
  - { verb: write, scope: governance.recommendation }
```

### How it reasons (and where the line is)

The reasoning is **hybrid, and deliberately so**:

- a **deterministic core** evaluates the measured PM2.5 against the **approved** `governance.rule` records and picks the highest-priority rule that *fires* — this part is auditable, and its `method` is `"rule"`;
- the **model** (`/v1/complete`) only writes the human-readable *wording* of the advisory, grounded in the rule that fired.

Two guardrails make this trustworthy — and they're the "AI advises, a person decides" boundary in code:

- it reads **only approved rules** (`status != "proposed"`) — a freshly-extracted rule waits for human approval before it can drive an advisory;
- it writes a **recommendation, never a decision** — and if no rule fires, it writes *nothing*.

The write pins the evidence and the citation, so the advisory can be reconstructed:

```python
rid = f"ds:{T}:governance/recommendation/air-quality-{obs[:13]}"
rec = {"schema": "governance.recommendation", "id": rid,
       "title": f"{stage} air quality — {binding} action",
       "summary": narrative,                       # the LLM wording, grounded in the fired rule
       "proposed_action": governing["proposed_action"],
       "rationale": f"Deterministic evaluation of {len(rules)} approved rules against {n} air.quality cells; "
                    f"governing rule '{governing['rule_id']}' fired …",
       "evidence": evidence,                        # the cells + rule it used
       "method": "rule", "produced_by": f"component://{CID}@{VER}",
       "citation": {"rule": governing["id"], "authority": governing.get("authority")}}
_call("/v1/write", {"scope": "governance.recommendation", "id": rid, "object": rec, ...})
```

A `governance.recommendation` is an *input* to a decision — never the decision itself. See [Intelligence & AI](/developer/deep-dives/intelligence/) and [Governance & Decisions](/developer/deep-dives/governance/).

---

## Step 4 · Into the Inbox — where a person decides

A recommendation sitting in the registry helps no one. The **`decision-router`** engine turns it into a **task in the right official's Inbox**. It's deliberately **domain-blind** — it routes *any* `governance.recommendation`; who receives it is configured per install.

### Its contract

```
component_id: ds:airawat:engine/decision-router
version: 0.4.0
config: [DECIDER]                                   # e.g. role://<tenant>/urban.pollution-control-officer
reads:  [governance.recommendation, platform.task]
writes: [platform.case, platform.task, platform.inbox_item]
```

For each actionable recommendation it writes three governed facts — the same `case → task → inbox item` structure behind *every* process on the platform (see [Work: Inbox, Cases & Tasks](/developer/deep-dives/work/)):

```python
# 1) a CASE — one running instance of the "decide" process
_call("/v1/write", {"scope": "platform.case", "id": case_id, "object": {
    "schema": "platform.case", "id": case_id, "title": rec["title"],
    "status": "open", "current_step": "decide"}})

# 2) a TASK — the unit of work, assigned to the DECIDER, with the choices
_call("/v1/write", {"scope": "platform.task", "id": task_id, "object": {
    "schema": "platform.task", "id": task_id, "case": case_id, "verb": "decide",
    "title": f"Decide: {rec['title']}", "assignee": DECIDER,
    "options": [rec["id"]], "actions": ["approve", "reject"], "status": "open"}})

# 3) an INBOX ITEM — what surfaces in that person's Inbox (actor = DECIDER scopes it to them)
_call("/v1/write", {"scope": "platform.inbox_item", "id": inbox_id, "object": {
    "schema": "platform.inbox_item", "id": inbox_id, "actor": DECIDER, "kind": "decision",
    "title": rec["title"], "body": rec["summary"], "ref": task_id,
    "handler": "decide", "actions": ["approve", "reject"], "status": "unread"}})
```

Three things worth noticing:

- **`actor = DECIDER`** is what scopes the item to a **role** (here, the pollution-control officer) — that's how it lands in the *right* person's Inbox and nobody else's.
- It's **idempotent**: the case/task/inbox ids derive from the recommendation id, and a re-run skips anything already routed — so scheduling this loop hourly never spams the inbox.
- The router **stops at routing** — it never approves anything. The named official opens the item in the **Inbox app**, reviews the cited evidence, and approves or rejects. That step produces a signed **`governance.decision`** with a receipt — the accountable act. That's the "a named human decides, and there's a receipt" promise, made concrete.

---

## Step 5 · The apps — see it, and act on it

Two apps close the loop, and neither holds any authority of its own — both act as the signed-in user (see [Components](/developer/deep-dives/components/)):

- **`air-explorer`** (`required_schemas: [air.quality, air.hotspot, air.sensor_reading, governance.recommendation]`) — the officer's workbench: it reads the layers through `/bridge/query` (under the user's token) and draws the PM2.5 map with the station markers, plus the latest advisory in a panel.
- **`inbox`** (the universal **Tasks** app) — one generic screen that renders *any* domain's `platform.inbox_item` and turns its `actions` into buttons. The air decision shows up here as an **approve / reject** task, exactly like a leave request or a court hearing would. That's the payoff of the shared case/task structure: you didn't build an inbox — you got one.

---

## Step 6 · Compose and install

You built the members; now bundle them. In Studio, **Compose** the project into the solution manifest (the `members:` list from the top of this tutorial), then **Install** it into a tenant from the Marketplace. Installing fans out — every member is set up, wired by its declarations, and pointed at that tenant's area of interest.

Then it runs on its own:

```
driver ingests readings  →  engine derives the surface  →  skill recommends
        →  router routes to the officer's Inbox  →  the officer decides  →  receipt
```

Open `air-explorer` to watch the map fill in, and `Tasks` to see (and act on) the advisory.

---

## What you just built

- A **driver** that turns an outside feed into governed facts, with provenance and no synthetic filler.
- An **engine** that derives a new, reproducible layer from those facts.
- A **skill** that applies approved rules to produce a **cited recommendation** — AI advising, inside the guardrails.
- A **router** that lands the recommendation in a named official's **Inbox** as a decidable task — where a person decides, on the record.
- Two **apps** that render and act on all of it, holding no authority of their own.

That's a complete public-interest loop — **sense → derive → recommend → decide** — built from small, certified, traceable parts.

## Where to go next

- **[Deep Dives](/developer/deep-dives/)** — the concepts underneath each step: [Components](/developer/deep-dives/components/), [Intelligence & AI](/developer/deep-dives/intelligence/), [Governance & Decisions](/developer/deep-dives/governance/), [Work: Inbox, Cases & Tasks](/developer/deep-dives/work/).
- **[Build, test, publish](/developer/build/lifecycle/)** — take your components through the two gates.
- Then publish to the **Marketplace** (for anyone) or share your solution directly with a specific participant.


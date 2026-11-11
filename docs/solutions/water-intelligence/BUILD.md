# Build "Water Intelligence" yourself — from the Console

This guide shows a developer how to build the **Water Intelligence** solution end‑to‑end using only the in‑platform **Console**, on a sandbox (development) tenant such as `airawatdeveloper`. Everything is governed data + certified components — no hand‑editing of servers.

> **What you'll build:** an ingest driver that turns a utility's complaint export into geocoded `water.complaint` facts, two analysis engines (`water.hotspot`, `water.signal`/`water.overview`), a seed driver that ships the taxonomy + configuration as data, and a dashboard app — all configurable so the same code serves any water utility.

---

## 0. The shape of the solution

**Governed vocabulary & config (data, not code):**
- `water.category` — the water‑issue taxonomy: `{code, label, domain, keywords[], order}`. Drives normalization (keywords→code), the sewer/water/tanker grouping, and dashboard labels.
- `water.record_kind` — contact‑type vocabulary: `{code, label, is_complaint}` (e.g. complaint / query / no_response_call).
- `water.config` — the **Solution Configuration**: agency name, dashboard title/subtitle, live‑vs‑snapshot flag, zone label, source attributions, severity thresholds, analysis windows. One record per tenant (`ds:<tenant>:water/config/default`).

**Facts (the data the solution produces):**
- `water.complaint` — one geocoded complaint (requires `h3` for mapping).
- `water.hotspot` — a hot H3 cell: count, dominant category, severity, `rate_per_10k`.
- `water.signal` — reopen / recurring / emerging operational signals.
- `water.overview` — one compact projection (totals, distributions, daily trend) the dashboard reads.

**Components:**
| Component | Kind | Reads | Writes |
|---|---|---|---|
| `water-setup` | driver | — | water.category, water.record_kind, water.config |
| `water-complaints` | driver | water.category | water.complaint |
| `water-hotspots` | engine | water.complaint, water.record_kind, water.config | water.hotspot |
| `water-signals` | engine | water.complaint, water.category, water.record_kind, water.config | water.signal, water.overview |
| `water-dashboard` | app | water.overview, water.hotspot, water.signal, water.config, water.category | — |

---

## 1. Create the project

```
project new water-intelligence
```
This creates a Studio project and `cd`s into it. (If you return later: `cd /projects/water-intelligence`.) Everything you scaffold while inside a project is added to its member list and shows under `ls`.

## 2. Govern the schemas (nouns)

In the **sandbox you may define and use schemas freely** — no network‑administrator approval is required to run them in your dev tenant. You only need network approval when you later publish the solution to the marketplace (see §9).

For each noun, propose it:
```
schema propose water.category
schema propose water.record_kind
schema propose water.config
schema propose water.complaint
schema propose water.hotspot
schema propose water.signal
schema propose water.overview
```
`schema propose` opens an editor with a JSON‑Schema skeleton; fill in `properties` + `required` and save. Keep them permissive (don't set `additionalProperties:false`) so drivers can add fields. The id must be `<domain>.<subject>` (e.g. `water.complaint`).

## 3. Build the ingest driver — `water-complaints`

```
new driver water-complaints
edit water-complaints/run.py
```
The driver uses the SDK `ingest.table(...)` helper. Make it **board‑agnostic**:
- **Auto‑detect columns** from the CSV header, each overridable by an env var (`ID_FIELD`, `CATEGORY_FIELD`, `STATUS_FIELD`, `REGISTERED_FIELD`, `CLOSED_FIELD`, `REOPENS_FIELD`, …).
- **Normalize the category** with `ingest.crosswalk(...)`, rebuilding its canonical list + keywords from the governed `water.category` rows at run time (so the taxonomy is data, not code). Keep a small built‑in list only as an offline fallback.
- Preserve the board's original label in `raw_category`; never store PII — read `Address` only to extract a PIN for geocoding, then drop it.
- Geocode **complaints only** (not queries/calls) to an H3 res‑9 cell using a layered local geocoder: colony/locality → PIN centroid → ward centroid, loaded from a `GAZETTEER_FILE_ID`.
- Tag `record_kind` from the source's contact‑type column (`RECORD_KIND_FIELD`).

Declare its config + the governed read in `edit water-complaints/meta.yaml`:
```
reads: [water.category]
config:
  - { name: COMPLAINTS_FILE_ID, kind: value }
  - { name: GAZETTEER_FILE_ID, kind: value }
  - { name: RECORD_KIND_FIELD, kind: value, default: Category }
```

## 4. Build the engines

```
new engine water-hotspots
edit water-hotspots/run.py      # group geocoded complaints by H3 over a window; count, dominant
                                # category, relative severity, rate_per_10k (join ward population).
new engine water-signals
edit water-signals/run.py       # reopen rate, recurring (chronic vs spike), emerging (honest WoW),
                                # + one water.overview projection (totals/distributions/daily trend).
```
Both engines read the governed vocab/config instead of hardcoding anything:
- non‑complaint `record_kind`s come from `water.record_kind` where `is_complaint=false`;
- domain grouping comes from `water.category.domain`;
- severity cut‑offs + window lengths come from `water.config`.

Always **read back** your writes and report the live count (a schema‑rejected record is silently dropped otherwise). Emit nothing on empty input, and say so — never fabricate.

## 5. Build the dashboard — `water-dashboard`

```
new app water-dashboard
edit water-dashboard/dist/index.html
```
A sandboxed browser app that reads governed data via `AOS.query(...)` and the shared design system (`/shared/aos.css`, `/shared/aos.js`). Carry **zero** branding/labels in code:
- category + domain labels ← `water.category`;
- title, agency name, subtitle, snapshot‑vs‑live, zone label, source attributions, severity thresholds ← `water.config`.

Add them to the allow‑list in `edit water-dashboard/meta.yaml`:
```
required_schemas: [water.overview, water.signal, water.hotspot, water.complaint, water.config, water.category]
```

## 6. Build the seed driver — `water-setup`

```
new driver water-setup
edit water-setup/run.py
```
This ships the **default taxonomy + configuration as data** and writes the governed records (idempotent; `RESET=1` overwrites). It is both your dev seed and the solution's install‑time seed step. Declare:
```
writes: [water.category, water.record_kind, water.config]
```

## 7. Run the pipeline

```
run water-setup                                        # seed water.category / record_kind / config
run water-complaints COMPLAINTS_FILE_ID=/inbox/complaints.csv GAZETTEER_FILE_ID=<id>
run water-hotspots POP_FILE_ID=<ward-population id>
run water-signals
```
Use `logs <component>` to see each run's output and `runs <component>` for status. Import files with `fetch <url> as /inbox/<name>`, set component keys with `secret set <component> <KEY>`, and your area of interest with `aoi set bbox …`.

## 8. Open the dashboard

Launch **Water Intelligence Dashboard** from the desktop, or `/run?app=water-dashboard`. It renders entirely from the governed facts + config.

## 9. Configure & re‑brand

To adapt the running solution for any other utility, **edit one record** — no redeploy:
```
edit /projects/water-intelligence/… (or Settings → water.config)
```
Set `agency_name`, `dashboard_title`, `attributions`, `severity`, `windows`. Add/adjust `water.category` rows to match the board's issue types. Point the driver's `*_FIELD` config at the board's own column names.

## 10. Publish to the marketplace (when ready)

A component is published with `publish <component>` (certify + list; needs a green run first); the project is bundled with `compose`. **Before publishing, every schema the solution uses must be approved by the network** (not just usable in your sandbox). Resolve any pending `schema propose` requests in Network Admin → Verbs/Schemas first. See the companion **Install** guide for what an operator does on the other side.


---

## Appendix — Reference code (copy & adapt)

These are the actual working sources of the reference solution. In an installed solution you can also open any of them with `edit water-<component>/run.py` (or `dist/index.html`).

### `water-setup/meta.yaml`
```yaml
component_id: ds:airawatdeveloper:driver/water-setup
kind: driver
version: 0.1.0
provider: ds:airawatdeveloper:developer
display_name: Water Intelligence — Setup / Seed
entrypoint: run.py
confinement_min: L1
# Seeds the solution's REFERENCE DATA (taxonomy + config). Re-runnable (idempotent upsert by id).
# All values are DATA here — the engines/driver/app read these governed records, never hardcode them.
writes: [water.category, water.record_kind, water.config]
scopes:
  - { verb: write, scope: water.category }
  - { verb: write, scope: water.record_kind }
  - { verb: write, scope: water.config }
config:
  - { name: RESET, kind: value, label: "Overwrite existing records", default: "0" }
```
### `water-setup/run.py` — seeds the taxonomy + Solution Configuration as DATA
```python
#!/usr/bin/env python3
"""water-setup — seeds the Water Intelligence solution's governed REFERENCE DATA so NO component hardcodes it:
  • water.category    — the water-issue taxonomy (code→label, domain bucket, normalisation keywords)
  • water.record_kind — the contact-type vocabulary (complaint|query|no_response_call; is_complaint flags the denominator)
  • water.config      — the Solution Configuration (agency branding + operational knobs) every member reads

Idempotent: deterministic ids, re-run safe. The shipped values are a sensible DEFAULT taxonomy + a REFERENCE config
(Delhi Jal Board) — an installer edits water.config for their agency and may add/adjust water.category rows as DATA.
Confined — only I/O is the SDK ctx.
"""
import os
from aos import driver, ctx

# ---- default water-issue taxonomy (code, label, domain, keywords, order). Keywords normalise a board's raw
#      labels to `code`; first match by `order` wins. Domains bucket the donut/grouping. Edit as DATA, not code.
CATEGORIES = [
    ("tanker_request",   "Water tanker required",       "tanker", ["tanker"], 1),
    ("sewer_overflow",   "Sewer blockage / overflow",   "sewer",  ["sewer", "overflow", "blockage", "drain", "logging", "garbage", "manhole cover"], 2),
    ("manhole",          "Manhole / cover",             "sewer",  ["manhole"], 3),
    ("contamination",    "Dirty / contaminated water",  "water",  ["dirty", "contamination", "quality", "muddy", "smell"], 4),
    ("low_pressure",     "Low pressure",                "water",  ["low pressure", "pressure"], 5),
    ("pipeline_leakage", "Water pipeline leakage",      "water",  ["pipeline", "leakage", "leak", "pipe"], 6),
    ("no_water",         "No water",                    "water",  ["no water", "short supply", "non supply", "dry", "supply"], 7),
    ("road_restoration", "Road restoration",            "water",  ["road", "restoration", "pit"], 8),
    ("billing",          "Billing",                     "water",  ["bill", "billing", "payment"], 9),
    ("new_connection",   "New connection",              "water",  ["new connection", "connection"], 10),
    ("other",            "Other",                       "water",  [], 99),
]
RECORD_KINDS = [
    ("complaint",        "Complaint",         True),
    ("query",            "Query",             False),
    ("no_response_call", "No response call",  False),
]
# REFERENCE Solution Configuration (edit water.config for YOUR agency — this is the one Delhi-specific record).
CONFIG = {
    "agency_name": "Delhi Jal Board",
    "dashboard_title": "Water Intelligence Dashboard",
    "subtitle": "from complaints to insight for better water management",
    "is_live": False,
    "snapshot_caveat": ("This is a historical snapshot, not a live feed. Period-over-period \"trend\" deltas are "
                        "intentionally omitted — the export does not span enough time to compute them honestly "
                        "(the within-window week-over-week is shown instead). Hotspots show association, not causation."),
    "zone_label": "operational zones",
    "attributions": {"complaints_source": "DJB grievance export",
                     "geocoder": "OSM-PBF + PIN + ward",
                     "population_source": "WorldPop 2020 constrained"},
    "severity": {"rate_warn": 150, "rate_crit": 300, "count_crit_pct": 0.10, "count_warn_pct": 0.30},
    "windows": {"window_days": 30, "week_days": 7, "max_weeks": 4, "min_count": 1, "min_chronic": 20},
}


@driver.main
def run():
    T = ctx.tenant
    if not T:
        print("FAIL: no run tenant."); return 1
    reset = os.environ.get("RESET", "0").strip() in ("1", "true", "yes")

    def _have(schema):
        try:
            return {(r.get("object") or r).get("id") for r in ctx.facts(schema).list()}
        except Exception:
            return set()

    now = ctx.now()
    cat_rows, rk_rows = [], []
    for code, label, domain, kws, order in CATEGORIES:
        cat_rows.append({"schema": "water.category", "id": "ds:%s:water/category/%s" % (T, code),
                         "code": code, "label": label, "domain": domain, "keywords": kws, "order": order})
    for code, label, is_c in RECORD_KINDS:
        rk_rows.append({"schema": "water.record_kind", "id": "ds:%s:water/record_kind/%s" % (T, code),
                        "code": code, "label": label, "is_complaint": is_c})
    cfg_row = dict(CONFIG, schema="water.config", id="ds:%s:water/config/default" % T)

    wrote = 0
    if reset:
        cw = ctx.write_many(cat_rows); rw = ctx.write_many(rk_rows); fw = ctx.write_many([cfg_row])
        wrote = (cw or 0) + (rw or 0) + (fw or 0)
    else:
        have_cat, have_rk, have_cfg = _have("water.category"), _have("water.record_kind"), _have("water.config")
        new_cat = [r for r in cat_rows if r["id"] not in have_cat]
        new_rk = [r for r in rk_rows if r["id"] not in have_rk]
        new_cfg = [cfg_row] if cfg_row["id"] not in have_cfg else []
        if new_cat: wrote += ctx.write_many(new_cat) or 0
        if new_rk: wrote += ctx.write_many(new_rk) or 0
        if new_cfg: wrote += ctx.write_many(new_cfg) or 0

    live_cat = len(_have("water.category")); live_rk = len(_have("water.record_kind")); live_cfg = len(_have("water.config"))
    print("water-setup: wrote %d records (RESET=%s). live now: water.category=%d water.record_kind=%d water.config=%d"
          % (wrote, reset, live_cat, live_rk, live_cfg))
    print("edit water.config (ds:%s:water/config/default) to set YOUR agency name / attributions / thresholds." % T)
    return 0 if (live_cat >= len(CATEGORIES) and live_rk >= len(RECORD_KINDS) and live_cfg >= 1) else 2


if __name__ == "__main__":
    raise SystemExit(driver.run())
```
### `water-complaints` — board-agnostic ingest (key parts)

Auto-detecting column map + governed taxonomy classifier:
```python
CANONICAL = ["no_water", "low_pressure", "contamination", "tanker_request", "pipeline_leakage",
             "sewer_overflow", "manhole", "road_restoration", "billing", "new_connection", "other"]

# generic keyword classifier — the safety net when TAXONOMY_MAP has no entry. Ordered by specificity (first hit wins);
# water-domain generic, NOT board-specific. A board's explicit TAXONOMY_MAP always takes precedence.
KEYWORDS = [
    ("manhole",          ["manhole"]),
    ("tanker_request",   ["tanker"]),
    ("road_restoration", ["pit", "road construction", "road restoration", "road cutting"]),
    ("pipeline_leakage", ["pipe"]),
    ("sewer_overflow",   ["sewer", "overflow", "blockage", "drain", "logging", "garbage", "manhole cover"]),
    ("contamination",    ["contaminat", "dirty", "quality", "smell", "muddy", "colour", "color"]),
    ("low_pressure",     ["low pressure", "pressure"]),
    ("no_water",         ["no water", "short supply", "supply", "dry", "non supply"]),
    ("new_connection",   ["new connection", "new water connection"]),
    ("billing",          ["bill", "payment", "charge", "arrear", "refund"]),
]

# column auto-detection: env override first (e.g. CATEGORY_FIELD), else the first header matching a candidate.
COLUMNS = {
    "id":       [os.environ.get("ID_FIELD"),          "tracking no", "tracking_no", "complaint id", "complaint_id", "id", "grievance id"],
    "channel":  [os.environ.get("CHANNEL_FIELD"),     "call type", "channel", "source"],
    "category": [os.environ.get("CATEGORY_FIELD"),    "complaint type", "complaint_type", "category", "type"],
    "subcat":   [os.environ.get("SUBCATEGORY_FIELD"), "subcategory", "sub category", "sub-category"],
    "priority": [os.environ.get("PRIORITY_FIELD"),    "priority"],
    "status":   [os.environ.get("STATUS_FIELD"),      "status"],
    "reg_date": [os.environ.get("REGISTERED_FIELD"),  "registered date", "registered_date", "registered on", "created date", "complaint date"],
    "reg_time": [os.environ.get("REGISTERED_TIME_FIELD"), "registered time", "registered_time"],
    "closed":   [os.environ.get("CLOSED_FIELD"),      "closed at", "closed_at", "closed date", "resolved at", "closure date"],
    "reopens":  [os.environ.get("REOPENS_FIELD"),     "number of reopens", "reopens", "reopen count"],
}
# ADMIN_COLUMNS (level→column) declares the board's hierarchy; else auto-detect the common civic levels.
AUTO_ADMIN = {"colony": "colony", "ward": "ward", "ac": "a.c. name", "zone": "zone"}

```
Rebuild the classifier from the governed `water.category` at run time (taxonomy = data):
```python
    # GOVERNED taxonomy wins: if water.category is seeded (water-setup), rebuild the classifier from it so the
    # code carries no board-specific taxonomy — the built-in CANONICAL/KEYWORDS is only the offline fallback.
    global classify
    try:
        _cats = sorted([(r.get("object") or r) for r in ctx.facts("water.category").list()],
                       key=lambda c: c.get("order", 999))
        _cats = [c for c in _cats if c.get("code")]
        if _cats:
            classify = ingest.crosswalk(canonical=[c["code"] for c in _cats], env="TAXONOMY_MAP",
                                        keywords=[(c["code"], c.get("keywords") or []) for c in _cats])
            print("[water-complaints] taxonomy: %d governed water.category rows" % len(_cats), flush=True)
    except Exception as _e:
        print("[water-complaints] governed taxonomy unavailable (%s) — using built-in default." % str(_e)[:80], flush=True)
```
The ingest call (SDK does id-stamping, dedup, batched writes):
```python
    res = ingest.table(
        schema="water.complaint", map_row=map_row, columns=COLUMNS,
        file_env="COMPLAINTS_FILE_ID",
        key_field="tracking_no",                           # board tracking no is the natural key when present…
        key_fields=("raw_category", "registered_at", "source_channel", "ward", "zone"),   # …else hash these STABLE fields
        sig_exclude=("id", "tenant", "source"),            # a change in status/closure/reopen/category ⇒ re-write
        tally_field="category",
        batch=500,                                         # bulk-write via the broker batch endpoint (env INGEST_BATCH overrides)
```
### `water-hotspots` — governed vocab + config, group by H3, read-back verify
```python
    # governed vocab/config — no taxonomy hardcoded. NONCOMPLAINT from water.record_kind; severity cuts from water.config.
    def _objs(sc):
        try: return [(r.get("object") or r) for r in ctx.facts(sc).list()]
        except Exception: return []
    NONCOMPLAINT = {o.get("code") for o in _objs("water.record_kind") if o.get("code") and not o.get("is_complaint")}
    _wcfgs = _objs("water.config"); _sev = (_wcfgs[0].get("severity") if _wcfgs else {}) or {}
    CRIT_PCT = float(os.environ.get("CRIT_PCT", str(_sev.get("count_crit_pct", 0.10))))
    WARN_PCT = float(os.environ.get("WARN_PCT", str(_sev.get("count_warn_pct", 0.30))))
```
Severity cuts from config + the write-and-verify pattern:
```python
    crit_cut = counts[max(0, int(n * CRIT_PCT) - 1)]   # top share by volume = critical (water.config severity)
    warn_cut = counts[max(0, int(n * WARN_PCT) - 1)]   # next share = warning
    now = ctx.now(); win = {"from": cur_from.isoformat(), "to": dmax.isoformat(), "days": WINDOW}
    WARD_POP = _load_ward_pop()                         # {norm ward name: population} (optional; via POP_FILE_ID)
    _popkeys = sorted(WARD_POP.keys(), key=len, reverse=True)

    def _pop_for(wn):
        """Resolve a DJB ward (normalized) to a datameet ward population, tolerating sub-ward suffixes +
        prefix overlaps (the two ward vocabularies differ): exact → strip trailing sub-ward char (A/B/C/1) →
        datameet key is a prefix of the DJB name (mohangardena→mohangarden) → DJB name is a prefix of a key."""
        if not wn:
            return None
        if wn in WARD_POP:
            return WARD_POP[wn]
        w2 = wn[:-1] if len(wn) > 1 else wn
        if w2 in WARD_POP:
            return WARD_POP[w2]
        for k in _popkeys:
            if len(k) >= 5 and wn.startswith(k):
                return WARD_POP[k]
        for k in _popkeys:
            if len(wn) >= 5 and k.startswith(wn):
                return WARD_POP[k]
        return None

    ward_total = defaultdict(int)                       # complaints per WARD over the window = rate numerator
    for _items in cur.values():
        for _it in _items:
            _w = _wn(_it.get("ward"))
            if _w:
                ward_total[_w] += 1
    rate_hits = 0
    facts = []
    for cell, items in cur.items():
        c = len(items)
        if c < MIN_COUNT:
            continue
        dom = Counter((it.get("category") or "other") for it in items).most_common(1)[0][0]
        sev = "critical" if (c >= crit_cut and n >= 10) else ("warning" if c >= warn_cut else "info")
        rec = {"schema": "water.hotspot", "id": "ds:%s:water/hotspot/%s-%s" % (T, cell, dmax.isoformat()),
               "h3": cell, "count": c, "dominant": dom, "category": dom, "severity": sev,
               "window": win, "observed_at": now}
        ward = _modal([it.get("ward") for it in items]);  zone = _modal([it.get("zone") for it in items])
        if ward:
            rec["ward"] = ward
        if zone:
            rec["zone"] = zone
        if ward and WARD_POP:                           # ward-level rate: complaints-in-ward / ward-population × 10k
            _wk = _wn(ward); _pop = WARD_POP.get(_wk)
            if _pop and _pop > 0:
                rec["rate_per_10k"] = round(ward_total.get(_wk, c) / _pop * 10000.0, 2)
                rate_hits += 1
        p = prev.get(cell, 0)
        if p:
            rec["wow_change"] = round((c - p) / p, 3)   # period-over-period; omitted when no prior window
        facts.append(rec)

    written = ctx.write_many(facts, valid_from_field="observed_at", asserted_at=now) if facts else 0
    # VERIFY the writes actually persisted (water.hotspot requires h3+observed_at; a bad record would be dropped at
    # the registry, and write_many reports the SENT count — so confirm against a read-back before claiming success).
    live = sum(1 for r in ctx.facts("water.hotspot").list()
               if (r.get("object") or r).get("observed_at") == now)
    sev_tally = dict(Counter(f["severity"] for f in facts))
    print("wrote %d water.hotspot over %d H3 cells, window %s->%s (%dd) — %s" %
          (written, n, cur_from, dmax, WINDOW, sev_tally))
```
### `water-signals` — the governed vocab loader (no taxonomy in code)
```python
def _load_vocab():
    """Read the GOVERNED water vocabulary (seeded by water-setup) — no taxonomy is hardcoded here.
    Returns (noncomplaint record_kinds, {category_code: domain}, water.config dict). Absent vocab ⇒ generic
    behaviour (all records treated as complaints; every category → the 'water' bucket), said once in the log."""
    def _objs(schema):
        try:
            return [(r.get("object") or r) for r in ctx.facts(schema).list()]
        except Exception:
            return []
    rk = _objs("water.record_kind")
    noncomplaint = {o.get("code") for o in rk if o.get("code") and not o.get("is_complaint")}
    cat_domain = {o.get("code"): (o.get("domain") or "water") for o in _objs("water.category") if o.get("code")}
    cfgs = _objs("water.config")
    cfg = cfgs[0] if cfgs else {}
    if not rk:
        print("[water-signals] no water.record_kind vocabulary — treating every record as a complaint (run water-setup to seed).")
```
The `water.overview` projection it also writes (one compact row the dashboard reads):
```python
    overview = {
        "schema": "water.overview", "id": "ds:%s:water/overview/%s" % (T, dmax.isoformat()),
        "observed_at": now, "window": {"from": dmin.isoformat(), "to": dmax.isoformat(), "span_days": span_days},
        "totals": {"contacts": len(rows), "complaints": len(comp),
                   "queries": kind_ct.get("query", 0), "no_response_calls": kind_ct.get("no_response_call", 0),
                   "closed": closed, "pending": len(comp) - closed,
                   "closure_rate": round(closed / len(comp), 4) if comp else 0,
                   "reopened_complaints": reop_n, "reopen_events": sum(o.get("reopens") or 0 for o in comp),
                   "geocoded": geocoded_comp, "geocode_pct": round(geocoded_comp / len(comp), 4) if comp else 0,
                   "hotspots": None},   # filled by the dashboard from water.hotspot count (kept source-of-truth there)
        "by_category": _top(cat_ct), "by_raw_category": _top(raw_ct, 12), "by_zone": _top(zone_ct, 15),
        "by_channel": _top(chan_ct, 12), "by_domain": _top(dom_ct), "by_status": _top(status_ct, 8),
        "trend_daily": [{"date": d, "complaints": day_ct[d]} for d in sorted(day_ct)],
```
### `water-dashboard` — read governed facts + config in the browser

Query the governed data and populate labels/config (no branding in code):
```javascript
async function main(){
  let ov,hs,sig,cats,cfgs;
  try{
    [ov,hs,sig,cats,cfgs] = await Promise.all([
      AOS.query('water.overview',{limit:5}), AOS.query('water.hotspot',{limit:2000}), AOS.query('water.signal',{limit:500}),
      AOS.query('water.category',{limit:100}), AOS.query('water.config',{limit:5}) ]);
  }catch(e){ document.getElementById('app').innerHTML='<div class="loading">Could not load data: '+E(e.message||e)+'</div>'; return; }
  // governed vocab + Solution Configuration — no labels/branding hardcoded in this app
  (cats||[]).forEach(c=>{ if(c.code){ CATLAB[c.code]=c.label||c.code; if(c.domain && !DOMLAB[c.domain]) DOMLAB[c.domain]=c.domain.replace(/\b\w/g,x=>x.toUpperCase()); }});
  WCFG = (cfgs||[])[0] || {};
```
Thread the Solution Configuration through rendering:
```javascript
  const sev=WCFG.severity||{}, attr=WCFG.attributions||{};
  RWARN=+sev.rate_warn||150; RCRIT=+sev.rate_crit||300;             // rate chips (from water.config)
  const TITLE=WCFG.dashboard_title||'Water Intelligence Dashboard';
  const AGENCY=WCFG.agency_name||''; const SUBTITLE=WCFG.subtitle||'from complaints to insight';
```

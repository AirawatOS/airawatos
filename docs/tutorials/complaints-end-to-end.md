---
summary: Compose a driver, adapter, engine, skill, agent and app into one governed solution — a citizen-complaints service a resident files over Telegram and the city tracks to closure, with proactive intake and hotspot analysis.
audience: developer
keywords: complaints, grievance, solution, adapter, driver, engine, skill, agent, telegram, hotspots, New Delhi
---

# Complaints, end to end

*Every component kind in one working service: a resident photographs a pothole, files it over Telegram, and the city tracks it to a verified closure — while the same spine proactively pulls complaints from news and social feeds, and an AI expert helps staff and vendors resolve them and find permanent fixes.*

This is the capstone to [Writing components](/developer/build/writing-components/). There you saw each kind alone; here they **compose** into one [solution](/developer/deep-dives/solutions-services/) — a pinned member-graph a city installs in one step. We use a real target: a complaints service for a large municipal tenant.

## The use case

A resident sees a civic problem — an overflowing bin, a broken streetlight, a flooded lane. They should be able to report it from where they already are (a chat app), with a photo, in their language; get a ticket; check status; and be asked to confirm when it's fixed. The city should see every complaint — not only the ones filed directly, but the ones surfacing in the news and on social media — on one queue, with the context staff need to act: the guidelines that apply, the vendor contract that covers that ward, the asset inventory, the terrain and drainage, and what happened the last ten times a complaint like this came in nearby.

**The challenges this raises** — and the kind that answers each:

| Challenge | Kind |
|---|---|
| Let residents file + track from a channel we don't own | **adapter** (Telegram) |
| Don't miss complaints that never get filed | **driver** (news / social intake) |
| One queue, one record shape for all of them | a governed **schema** + the **Inbox/Case** spine |
| Find where complaints cluster; propose permanent fixes | **engine** (hotspots) |
| Help staff & vendors resolve each one, grounded in real context | **skill** + **agent** |
| A desk to work the queue | **app** |
| Install it all into a city in one step | **solution** |

## The shape

```svg
<svg viewBox="0 0 740 330" role="img" aria-label="The complaints solution: intake sources flow into one case spine, worked by an app and an AI expert, analysed by a hotspot engine" font-family="system-ui,sans-serif" font-size="12" fill="currentColor">
  <style>.n{fill:none;stroke:currentColor;stroke-width:1.5} .e{fill:none;stroke:currentColor;stroke-width:1.4} .t{font-size:11px} .h{font-weight:600}</style>
  <!-- intake -->
  <rect x="16" y="24" width="150" height="40" rx="6" class="n"/><text x="91" y="42" text-anchor="middle" class="h">adapter</text><text x="91" y="57" text-anchor="middle" class="t">Telegram: file + track</text>
  <rect x="16" y="150" width="150" height="40" rx="6" class="n"/><text x="91" y="168" text-anchor="middle" class="h">driver</text><text x="91" y="183" text-anchor="middle" class="t">news / social intake</text>
  <!-- spine -->
  <rect x="285" y="78" width="170" height="78" rx="8" class="n"/><text x="370" y="104" text-anchor="middle" class="h">city.complaint</text><text x="370" y="122" text-anchor="middle" class="t">governed fact +</text><text x="370" y="138" text-anchor="middle" class="t">platform.case / inbox</text>
  <!-- workers -->
  <rect x="560" y="18" width="162" height="40" rx="6" class="n"/><text x="641" y="36" text-anchor="middle" class="h">app</text><text x="641" y="51" text-anchor="middle" class="t">Complaints Desk</text>
  <rect x="560" y="92" width="162" height="50" rx="6" class="n"/><text x="641" y="112" text-anchor="middle" class="h">agent + skills</text><text x="641" y="128" text-anchor="middle" class="t">triage · resolve · close</text>
  <rect x="560" y="176" width="162" height="40" rx="6" class="n"/><text x="641" y="194" text-anchor="middle" class="h">engine</text><text x="641" y="209" text-anchor="middle" class="t">hotspots → fixes</text>
  <!-- edges in -->
  <line x1="166" y1="44" x2="285" y2="104" class="e" marker-end="url(#c)"/>
  <line x1="166" y1="170" x2="285" y2="130" class="e" marker-end="url(#c)"/>
  <!-- edges out -->
  <line x1="455" y1="104" x2="560" y2="44" class="e" marker-end="url(#c)"/>
  <line x1="455" y1="117" x2="560" y2="117" class="e" marker-end="url(#c)"/>
  <line x1="455" y1="132" x2="560" y2="196" class="e" marker-end="url(#c)"/>
  <!-- status back to resident -->
  <line x1="560" y1="40" x2="166" y2="40" class="e" stroke-dasharray="4 3" marker-end="url(#c)"/>
  <text x="300" y="34" class="t">status / "confirm fixed?" →  resident</text>
  <defs><marker id="c" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="currentColor"/></marker></defs>
</svg>
```

Everything hangs off **one governed record** — `city.complaint` — and the universal [Inbox & Case](/developer/deep-dives/work/) spine. Each kind only ever touches that spine through the broker; no component talks to another directly.

## Build it, member by member

**1 · Govern the vocabulary first.** Before any code, propose the nouns and verbs this service needs — `city.complaint` (the record), its status values, and the lifecycle verbs (`file`, `assign`, `resolve`, `confirm-closed`). Governance is shared, so reuse what exists (the generic Inbox/Case + lifecycle verbs) and propose only what's genuinely new. See [Designing a schema](/developer/build/designing-a-schema/) and [Designing a verb](/developer/build/designing-a-verb/).

**2 · The adapter — file + track over Telegram.** The confined Telegram adapter from [Writing components → Adapter](/developer/build/writing-components/#adapter-carry-messages-to-an-outside-channel). A message with a photo opens a `city.complaint` (the photo goes to the filestore, its digest onto the record); a message like *"status NDMC-4821"* reads the case back; and when work closes, the adapter asks the resident to **confirm the fix** — their reply flips the case to `closed-confirmed` or re-opens it. The bot token is a per-tenant Vault secret; the admin clicks **Activate** in Settings → Components.

**3 · The driver — proactive intake.** A driver that polls news and social feeds (declared `egress`, key in Vault), extracts civic complaints, geocodes them to a ward, and writes them as `city.complaint` with `source: news` — so a pothole trending online lands on the *same* queue as one filed by hand, deduped against existing open cases.

**4 · The engine — hotspots → permanent fixes.** An engine exposing `complaint-hotspots`: it reads all open and historical complaints, clusters them by location and category, joins terrain/drainage and asset inventory, and writes a ranked list of **hotspots** with a proposed permanent fix (a `governance.recommendation`) — e.g. "re-grade this lane; 23 flooding complaints in 3 monsoons." It computes; it never decides.

**5 · The skill + agent — track to closure, help resolve.** A **skill** per job (triage-and-route, draft-a-resolution-plan, check-against-guidelines) and an **agent** — the *Complaints Expert* — that bundles them under one persona. Each skill reads the case plus the grounding a resolver needs — guidelines, the ward's vendor contract, asset inventory, terrain, hydrology, and the history of nearby complaints — and proposes a cited next step for staff or the vendor. Every suggestion cites the records it stands on.

**6 · The app — the Complaints Desk.** A sandboxed app showing the queue, each case's full context and the Expert's cited suggestions, with the action buttons (`assign`, `resolve`) that call the governed verbs as the signed-in officer. Residents need no app — they're on Telegram.

## Pin them into a solution

A solution is the member-graph plus the governed vocabulary it depends on. Declared once, it installs as a unit — each member gets its per-tenant run token and grants, exactly the reads/writes/egress/secrets it certified.

```yaml
# solution meta — the pinned graph a city installs in one step
component_id: ds:<tenant>:solution/complaints
kind: solution
version: 0.1.0
provider: ds:<tenant>:developer
display_name: Citizen Complaints
members:
  - ds:<tenant>:adapter/telegram-concierge     # file + track + confirm closure
  - ds:<tenant>:driver/complaints-intake        # news + social → city.complaint
  - ds:<tenant>:engine/complaint-hotspots        # clusters → permanent-fix recommendations
  - ds:<tenant>:agent/complaints-expert          # bundles the resolution skills
  - ds:<tenant>:app/complaints-desk              # the officer's queue
requires_schemas: [city.complaint, governance.recommendation, platform.case, platform.inbox_item]
```

Install it into the city tenant; set the Telegram token in Settings → Components; click **Activate**. The service is live — residents file, the desk works the queue with the Expert's help, the hotspot engine runs on a schedule, and the intake driver keeps pulling.

## Back to the challenges

- *File + track from a channel we don't own* → the **adapter**, confined, token in Vault.
- *Don't miss unfiled complaints* → the **driver**, feeding the same `city.complaint` spine.
- *One queue, one shape* → the governed **schema** + **Inbox/Case**; every source normalises to it.
- *Cluster + permanent fixes* → the **engine**, proposing cited `governance.recommendation`s.
- *Help staff & vendors resolve* → the **agent + skills**, grounded in guidelines, contracts, assets, terrain and history.
- *A desk to work it* → the **app**, acting as the officer.
- *Install in one step* → the **solution**.

Seven kinds, one record, one certified install — and nothing in it can touch anything it didn't declare. That's the whole point of composing on AirawatOS: each piece is small and auditable, and the governance holds across all of them at once.

> Build each member with [Writing components](/developer/build/writing-components/); govern its vocabulary with [Designing a schema](/developer/build/designing-a-schema/) / [a verb](/developer/build/designing-a-verb/); ship each with [Build, test, publish](/developer/build/lifecycle/).

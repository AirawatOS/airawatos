# Service Delivery — Deliver a citizen service

*Build a real service an agency publishes and a resident uses: file a civic complaint, route it to the right
officer, and see it through to resolution — all from the platform's own apps, with no bespoke server code.*

## The use case

A resident notices a problem the city should fix — uncollected garbage, a burst water line, a dead streetlight.
They need to **report it and track it to resolution**. The city needs to **receive it, route it to the right
officer, resolve it, and stand behind an auditable record**. Every city in the network needs the same thing,
each running its own version.

## The challenges

A civic service sounds simple until you list what actually makes it hard:

1. **One front door.** The resident shouldn't have to know *which department* owns garbage vs. water vs. lighting.
2. **The agency owns its process and its data.** No central database some other body controls; each city runs
   its own service and no one else can read its cases.
3. **Every step attributed and auditable.** Who received it, who acted on it, when — provably, not "trust us."
4. **Consent.** The complaint is the resident's data; whether it's shared, and with whom, is their call.
5. **Don't rebuild the plumbing.** Auth, storage, routing, delivery, the officer's inbox — nobody should
   re-implement those for every new service.

Keep this list in mind. At the end we'll return to each one and show exactly how the platform handled it.

## What you'll build

A working **"Report a Civic Complaint"** service: an agency **publishes** it from Service Studio, a resident
**files** one through the Jan Seva app, it lands in the right **officer's Tasks inbox**, and it **moves to
resolution** — and you'll write **no server code** to make that happen.

The arc: **build the service → publish it → install it → the resident uses it.** You'll do each step in an app;
each app just drives *governed data* underneath, so the API call is shown as "under the hood" — you never type it.

> Apps you'll use (install them from the **Marketplace**, or open at `/apps/<name>/`): **Studio** (developer),
> **Service Studio**, **Admin**, **Network Admin**, **Marketplace**, **Jan Seva**, **Tasks**.
> Example agency: `nashik`.

---

## Step 1 — Govern the vocabulary (once)

A service can only reference **governed** nouns and roles — that's what lets a citizen app built by someone else
understand your service, and makes "who may act" a shared, signed decision. You *propose*; a network steward
*approves*.

- **Need a new data shape (a form/record schema)?** In **Studio**, open **`🔗 Contracts → ＋ Request a schema`**.
  The modal has a **`🤖 Advise`** button that checks the house rules and suggests reuse, then **`File request`**.
  Track it under **`🔗 Contracts → 📥 My requests`**.
- **Need a new role?** In the **Admin** app, open the **`Role Requests`** tab → **`Request a new role`** (role,
  domain, why) → **`File request`**.
- **Approve it (the steward):** schemas in **Network Admin → `⚖️ Change Requests` → `Approve`**; roles in
  **Admin → `Role Requests` → `Approve`**. Approving *signs* it into the governed catalog — that's the authority act.

*The roles this complaint service routes to — `civic.grievance-officer`, `urban.sanitation-officer` — are already
governed, so you can skip straight to Step 2.*

> Under the hood: `＋ Request a schema` → `POST /bridge/schema-request` · `Request a new role` →
> `POST /bridge/role-request` · `Approve` → `/bridge/change-request-decide` (schemas) or
> `/bridge/role-request-decide` (roles).

## Step 2 — Author the service (no bespoke code)

Open **Service Studio** and click **`＋ New Service`**. You fill in four cards — no code, no solution to build:

1. **Service** — the `Service id`, `Title shown to citizens`, `Domain`, `Jurisdiction`, and **`Who it's for`** (a
   governed audience role, e.g. `civic.resident`).
2. **Intake form** — click **`+ Field`** for each thing the citizen fills in (a label, a type, optionally a 📍
   location field, and whether it's required). For a complaint: a description + a location.
3. **Workflow** — click **`+ Step`** for each stage; each step picks the **role** that handles it and the task
   text. For a complaint:
   - `triage` → **civic.grievance-officer** — "Triage & assign the complaint"
   - `resolve` → **urban.sanitation-officer** — "Inspect and resolve on site"
   - `verify` → **civic.grievance-officer** — "Verify resolution & close"
4. **Required documents** — tick any credential types the citizen must present (none, for a complaint).

Stuck? The **`🤖 Service AI Expert`** on the right can draft the form and workflow from a description and offer
**`✨ Apply to editor`**. Behind the scenes your service is bound to the platform's generic, already-certified
`declarative-service` solution — the certified **lifecycle-engine** runs your workflow. *(Only if config truly
can't express your logic do you drop to Developer Studio and build a bespoke solution — most services never do.)*

## Step 3 — Publish it (steward-signed)

In **Service Studio**, click **`Publish`**. The network **signs the service with your agency's steward key** and
lists it in the directory; you'll see **`✓ Published — citizens in <jurisdiction> can now use it.`**

The **governance wall** is real: if a workflow step names a role that isn't governed, publish is refused —
`workflow step 'triage' role '…' is not a governed role` (a live `422`). That's the platform holding you to the
shared vocabulary from Step 1.

> Under the hood: `Publish` → `POST /bridge/service-offering-save` → the network `service-offerings` directory,
> steward-signed. *(Publishing a **component/solution** instead uses Studio's own `Publish` / `⬆ Publish as
> Solution`; a network steward clears it in **Network Admin → `📤 Publish Requests`**.)*

## Step 4 — Install it into the agency (one approval, many grants)

A tenant admin opens the **Marketplace**, finds the fulfilling solution, and clicks **`Install`** (the button
flips to `Uninstall` when done). **One approval** materializes everything the service needs: a steward-signed
access grant per component (for exactly its declared reads/writes), the app shelf + roles, any subscriptions, and
contributed records.

*(The generic `declarative-service` is already installed platform-wide, so a no-code service like this needs no
extra install; a bespoke solution installs exactly this way.)*

> Under the hood: `Install` → `POST /bridge/install` → `/v1/solutions/install`.

## Step 5 — The resident files it (Jan Seva)

The resident opens **Jan Seva** (`🏛️ Citizen Services`) — a public front door. They:

1. **Search** "complaint" → the directory returns it, already scoped to what they're eligible for (they never
   pick a department).
2. **Open** it, fill the intake form.
3. Click **`Consent & Submit`** — the app issues their consent, then files it; the provider opens the case and
   routes the first task. They see a **reference number** and can track status.

> Under the hood: `/bridge/service-search` → `/bridge/service-consent` → `/bridge/service-route {action:"init"}`
> → returns `{ case, reference, routed_to: "role://nashik/civic.grievance-officer", status: "received" }`.

## Step 6 — The officer resolves it (Tasks)

The task appears in the assigned officer's **Tasks** inbox (the platform-wide Inbox). The officer opens it and
clicks **`Mark complete`** (or `Approve`/`Reject` on a decision step); the lifecycle-engine **advances the
workflow** to the next role's inbox — triage → the sanitation officer's field visit → back to verify & close.
The UI confirms e.g. **`✓ Approved — advanced to "resolve" · now with urban.sanitation-officer`**.

*(On a service whose final step issues a credential — like a birth certificate — closing it **mints a signed
credential** into the citizen's wallet; the Tasks toast reads `✓ … credential issued to the applicant`. See the
Cross-Agency tutorial.)*

> Under the hood: `/bridge/query` (load tasks) → `/bridge/complete` or `/bridge/decide`.

---

## Challenges revisited

Back to the five challenges — here's exactly how the platform handled each:

1. **One front door.** The resident searched *once* in Jan Seva; the **network directory** returned every
   agency's matching service, scoped to their eligibility. No department-picking.
2. **The agency owns its process and data.** The service runs as the agency's **own** offering in its **own**
   tenant; zero-trust isolation means no other tenant can read its cases. Every city publishes its own version;
   Jan Seva is identical everywhere.
3. **Attributed and auditable.** Every write is **component-on-behalf-of-the-user**, bitemporal, and the offering
   plus each decision is **steward-signed**. You can prove who received it, who acted, and when.
4. **Consent.** `Consent & Submit` wrote a consent record that gated the submission, and the complaint lands in
   the citizen's own ownership scope — sharing it is their revocable decision.
5. **No plumbing to rebuild.** You filled in **four cards**. The platform supplied auth, the case/task/**Inbox**
   spine, delivery, routing, and the workflow interpreter — **zero server code** for a complete, governed,
   auditable service.

## Where this is reference-grade (honest limits)

- **The provider is a reference stand-in.** Today the platform opens the provider's case itself under provider
  authority (on-platform, synchronous). A real agency plugs in its own solution or endpoint; asynchronous
  external fulfilment is a later step.
- **The service directory + transaction ledger are in-memory** in the reference network — reseed after a restart.
- **Consent is a governed record here.** The stronger form is a signed **credential in the citizen's wallet** the
  provider verifies independently — see
  [Verify a person across agencies](/developer/tutorials/verify-across-agencies/).
- **API-only today:** the general "Request a schema" flow lives in Developer Studio; Service Studio can propose
  only *credential-type* schemas from its AI Expert.

> Deep dives: [Solutions & Services](/developer/deep-dives/solutions-services/) ·
> [Interaction](/developer/deep-dives/interaction/) · [Work: Inbox, Cases & Tasks](/developer/deep-dives/work/) ·
> [Data Ownership & Consent](/developer/deep-dives/ownership-consent/).

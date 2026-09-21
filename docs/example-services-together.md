# Worked example: how the services work together

*One realistic loop — a scheduled air-quality reading becoming an officer's task — touching every platform service, all through the kernel.*

The [Services & APIs](/developer/get-started/services-and-apis/) page lists the pieces. This shows them *moving*. Follow one loop end to end: a sensor reading is pulled on a schedule, turned into a map layer, summarised by AI into an advisory, decided by an officer, and routed to their Inbox as a task — with a citizen's photo attached. Nine services cooperate, and **not one component ever touches another's data directly** — everything goes through the kernel.

The components in this loop run in **different runtimes**: a **driver** (fetches outside data), two **engines** (compute over governed data), and a **skill** (an AI expert). None of them holds any authority of its own; each acts only through the broker, under a run-token, inside its declared capabilities.

## The loop, step by step

**1. The clock starts it — Scheduler.**
A `platform.schedule` entry says "pull air sensors for Kanpur every hour." The **Scheduler** fires when the time comes. It doesn't run anything itself — it asks the runtime manager to.

**2. The driver runs — Runtime Manager + Identity.**
The **Runtime Manager** mints a short-lived **run-token** for the `air-sensors` driver and starts it in a confined driver runtime. The token's authority traces back to **Identity**, the IdP every service trusts. The driver is now running, but boxed in: its only way out is the broker.

**3. The driver reaches the outside world — Secrets + the broker.**
To call the CPCB pollution API, the driver needs a key it isn't allowed to see. It asks the broker for a brokered call; the broker fetches the key from **Secrets** (Vault-backed), makes the outbound request on the driver's behalf, and hands back the response. The raw key never enters the driver's memory. This is the only door to the internet, and it's declared and logged.

**4. The reading becomes a governed fact — Broker → Kernel.**
The driver writes each reading as an `air.sensor_reading` through the broker. The broker forwards it to the **Kernel**, which checks the driver is a certified component allowed to write that schema, stamps *who wrote it*, and records it in the bitemporal registry. The data is now a shared, attributed fact — not a row in some driver's private table.

**5. The write ripples — Automation.**
Every registry write emits an event. The **Automation** service receives it and fans it to whoever subscribed — here, the `station-interpolation` engine, which listens for new readings.

**6. The engine computes — Runtime Manager + Broker → Kernel again.**
Automation asks the **Runtime Manager** to run the engine. In its own runtime, the engine **reads** the readings and **writes** an `air.quality` cell surface — both through the broker, both kernel-authorized, both attributed. A map layer now exists, derived from the readings, with its provenance recorded.

**7. AI drafts the advisory — Model Gateway.**
A `air-quality-advisory` **skill** (an AI expert) runs. To use a language model it goes through the **Model Gateway** — the single confined path to a model provider (the provider key stays in Vault, like any secret). The skill reads the air-quality surface and the *approved* health rules, and drafts a `governance.recommendation`: "PM2.5 is severe in these wards; advise an advisory + inspection." It writes the recommendation through the broker — a *proposal*, not an action.

**8. A person decides — Decision.**
A recommendation does nothing on its own. An officer reviews it and admits it. That goes to the **Decision** service — the single writer that turns an admitted recommendation into a signed `governance.decision` and its downstream effects. Nothing became real until a human decided; now it's a tamper-evident record of *who* decided *what*.

**9. Work reaches a person — Workflow.**
The decision opens a case. The **Workflow** service instantiates the case's workflow into concrete **tasks** and routes them to the right role's Inbox — "inspect ward 12," assigned to the pollution-control officer.

**10. A citizen adds evidence — File Store.**
The officer (or a citizen on the linked grievance) attaches a photo. The bytes go to the **File Store** — content-addressed, immutable — and the record just keeps the file's id. The image is stored once, referenced everywhere.

## What just happened

A scheduled clock tick became a real, attributed, human-approved unit of civic work — and along the way it exercised **Scheduler, Runtime Manager, Identity, Secrets, Automation, Model Gateway, Decision, Workflow, and File Store**, with the **Kernel** as the one thing in the middle that every read and write passed through.

Three properties fell out for free, because of *where* the work happened:

- **Isolation.** The driver, the engines, and the skill never saw each other's data or each other's secrets. Each ran in its own runtime and reached everything through the broker.
- **Attribution.** Every fact, every derivation, every decision carries who asserted it — so the whole chain, from raw reading to officer's task, is auditable end to end.
- **A human in the loop.** The AI *proposed*; a person *decided*; only then did anything become real. The [decision spine](/developer/deep-dives/governance/) is what separates a suggestion from an action.

That's the shape of every loop on the platform — sense, compute, reason, decide, act — and the services are just the platform doing that work so your component doesn't have to.

> Related: [Services & APIs](/developer/get-started/services-and-apis/) (the pieces), [Zero-Trust](/developer/deep-dives/zero-trust/) (why the broker sits in the middle), and [Runtimes & Delivery](/developer/deep-dives/runtimes/) (where your code actually runs).

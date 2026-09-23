# Runtimes & Delivery

*How a component's code gets to a deployment safely, and where it actually runs.*

## Two questions, two answers

For any component, there are two separate questions:

1. **How does the code get here?** — delivery.
2. **Where does it run?** — placement.

AirawatOS answers them separately, and neither answer requires trusting the component's code.

## Delivery: never baked in, always verified

A published component does **not** ship hidden inside the platform's own image. Instead, its certified
code lives in a **content-addressed filestore** — a store where a file's address *is* a fingerprint of
its contents. When you install a component, the platform:

1. fetches the certified code from that store,
2. re-computes the fingerprint and checks it matches the certificate,
3. refuses to run on any mismatch,
4. and caches it locally so repeat runs are fast.

Because the address is the fingerprint, you can't quietly swap certified code for different code under
the same name — the fingerprint would change and the check would fail. Trust rests on the content and
the certificate, **not** on how the file travelled. (This is the delivery half of
[Zero-Trust](/developer/deep-dives/zero-trust/).)

The important design choice: **install** is when the code is materialized, not first-run. That removes a
whole class of "it failed the first time someone used it" surprises.

> This very developer portal is delivered exactly this way: it's published to the filestore and
> materialized on boot — not baked into the platform image. Updating these docs re-publishes the bundle;
> it doesn't require rebuilding or redeploying the platform.

## Placement: light things in-process, heavy things out-of-process

Some components are light — a bit of arithmetic on some data. Others are heavy — they need large
libraries for satellite imagery, geospatial maths, or machine learning. Running them the same way would
force every deployment to carry every heavy library. So AirawatOS splits placement:

- **Light components** run **in-process** inside the app-host, right where the request arrives. Fast,
  simple, synchronous.
- **Heavy components** are dispatched **out-of-process** into a dedicated **runtime** — a container
  that carries exactly the heavy libraries that component needs — and talk to the platform only through
  the broker.

## Runtime profiles: the one placement key

How does the platform know which components are "heavy"? Each component **declares a runtime profile** in
its description, and each runtime **declares which profile it satisfies**. Profiles are cumulative
layers of capability, for example:

- **standard** — light maths and data handling; runs in-process.
- **geospatial** — adds mapping and geometry libraries.
- **earth-observation** — adds satellite-imagery processing.
- **modeling** — adds machine-learning libraries.

A component that declares nothing heavier than *standard* runs in-process. Anything heavier is routed
to a runtime that satisfies its profile. And this is **fail-safe**: if a component needs a profile that
no available runtime provides, the run is designed to *fail clearly* rather than quietly run with a
missing library and produce wrong results.

**A worked example.** Two engines, two very different needs. A simple "is this reading above the alert
threshold?" check needs nothing beyond basic arithmetic — it declares the *standard* profile and runs
in-process, answering instantly. An engine that extracts building outlines from satellite imagery needs
heavy geospatial and earth-observation libraries — it declares the *earth-observation* profile, so the
platform dispatches it to a runtime that carries those libraries, out-of-process. Neither engine
carries the other's baggage, and the deployment never has to bundle satellite-imagery libraries just to
run a threshold check.

## The runtime is itself a component

A runtime is not special magic — it is just another certified component (of kind `runtime`) whose
deliverable is a shared, per-profile container image. Drivers and engines are mounted into it read-only;
they never carry their own container. This gives a clean split: the **filestore** holds component *code*;
the **container registry** holds the heavier runtime *images*.

## The coordination / execution split

Two planes cooperate, and — importantly — **neither calls the other directly**; the registry sits
between them as the seam:

- The **coordination plane** (the scheduler/orchestrator) decides *what* should run, checks the
  certificate and contract, and dispatches. It carries none of the components' heavy libraries.
- The **execution plane** (the runtime-manager on a node) actually runs the code in its profile
  container, mounts the code read-only, materialises the component's declared secrets from the vault
  into the run's environment, and locks execution to the exact certified image.

This is why one deployment doesn't collapse into a single ever-growing container holding every library
anyone ever needed.

## Verbs arrive as data, not as platform code

There's a nice consequence of all this for how a request reaches an engine. The app-host is
**domain-blind** — it doesn't have any sector logic baked in. When a request for a given action ("verb")
comes in, the host looks up *which engine implements that verb* from governed records in the registry,
not from a hardcoded list in its own code. Publishing a new engine registers its verbs, and they go
live within seconds — **no platform edit, no image rebuild.** (The request side of this is
[Interaction](/developer/deep-dives/interaction/).)

## Upgrades don't move under your feet

Published versions are immutable and signed. To change something you publish a new, higher version, and
each tenant chooses when to adopt it. Nothing changes under an installed component without an explicit
step.

## Components vs. platform services: the shape of the whole system

A fair question at this point: *is AirawatOS built out of components, or out of services?* The answer is
**both — but they sit at different layers, and only one of them grows.**

Underneath everything is a **small, fixed set of platform services** — the operating system itself.
These are the long-running processes that provide the ground every component stands on: the **kernel**
(trust root + registry, and the confined model-gateway path), **identity** (mints the tokens every
service checks), the **network** (certification + directory), the **app-host** (where app and browser
requests land), the **file store** (content-addressed component code), **secrets** (the vault), the
**broker** (the one confined door for a component's outside I/O), the **event dispatcher** (the
"automation" service that fans registry-write events out to subscriptions), the **scheduler**, and the
**runtime-manager** (runs heavy components out-of-process). This list is deliberately short, and it
**stays** short: you do not add a new platform service every time you add a capability. (The same set,
drawn as two lanes, is in [Zero-Trust](/developer/deep-dives/zero-trust/).)

On top of that substrate is the **component plane** — and this is where all growth happens. Every new
capability — a driver, an engine, an app, a whole solution — arrives as a **component**: certified,
delivered from the filestore, installed as data, and run under the broker's confinement. Adding one is a
*publish*, not a *deployment*. No new process, no new port, no platform rebuild.

```
   the component plane   — grows without bound
   ┌─────────────────────────────────────────────────┐
   │  drivers · engines · apps · solutions · agents   │
   │  certified · installed as data · broker-confined │
   └─────────────────────────────────────────────────┘
                          runs on
   the platform substrate   — a short, fixed list
   ┌─────────────────────────────────────────────────┐
   │  kernel · identity · network · app-host          │
   │  file store · secrets · broker                   │
   │  event dispatcher · scheduler · runtime-manager  │
   └─────────────────────────────────────────────────┘
```

So the direction of travel is **components on a fixed substrate** — the opposite of "a new
micro-service for every feature." Capability is something you *publish onto* the platform, not something
you *bolt beside* it. That's what keeps a deployment from sprawling into an ever-growing pile of
processes, and it's why the same handful of platform services can carry an unbounded catalogue of sector
capability.

(Watch the word "service" here — it has a second, unrelated meaning as a *size of thing you consume*,
covered in [Solutions & Services](/developer/deep-dives/solutions-services/).)

## Where this stands today

**Working now:** filestore delivery with fingerprint verification for all component shapes; the
first out-of-process runtime split (the geospatial tier) live in production, with the orchestrator
dispatching heavy engines to a dedicated runtime; governed verb dispatch (the domain-blind host reading
verb-to-engine bindings from the registry) live; and the first node-side operator tool that pulls,
verifies, and attests the runtime images it holds.

**Available now** also includes several heavy profiles beyond the base — `earth-observation`, `modeling`,
`media`, and `vision` runtimes each ship as certified components with a pinned image digest.

**Being built:** finishing the cutover so that *nothing* is baked into the platform image (some
components are still baked today); tightening placement to strictly fail-safe everywhere; the strongest
confidential runtime tier; and per-tenant version pinning with admin-approved upgrades.

# Components

*The single building block everything in the platform is made of.*

## One block, one lifecycle

In AirawatOS, **everything you build or install is a component** — a driver that fetches data, an engine
that computes, an app you click on, a bundle that installs several of these at once. They are all the
same kind of thing, and they all travel the same path:

**register → check it conforms → sign a certificate → list it → pull it → verify it → install it.**

There's no special "core" that skips this path. Even the platform's own first-party software goes
through the same certification as anyone else's. "First-party" is just a fact about who published it —
not a shortcut. What you trust is the **certificate**, not whether the code was compiled into the
platform. (Why that's safe is [Zero-Trust Architecture](/developer/deep-dives/zero-trust/).)

> Underneath the components sits a small, *fixed* set of **platform services** — the kernel, identity,
> network, app-host, and a few others — that **are** the operating system itself. Those aren't
> components you install; they're the ground components run on. You add capability by publishing
> components onto that substrate, not by deploying new services (see
> [the substrate vs. the component plane](/developer/deep-dives/runtimes/)).

## What a component is made of

A component is a small folder with two things:

- an **entrypoint** — the actual code (`run.py`), or for an app, a web page (`index.html`). You write it
  against the SDK's one I/O object, **`ctx`**: `ctx.get`/`ctx.facts` to **read**, `ctx.write` to **write**,
  `ctx.fetch` to **call** an outside site, `ctx.file` for blobs, and so on. Engines mark their actions with
  `@engine.verb`; drivers mark their entrypoint with `@driver.main` (see the
  [Quickstart](/developer/build/quickstart/) and [Working with governed data](/developer/build/governed-data/));
- a **description file** (`meta.yaml`) that carries the component's **identity** (id, version, kind, title)
  and the handful of things that can't be read off the code: its **runtime**, **config** schema, packaged
  **assets**, and any **subscriptions**/**lifecycle hooks** you want wired up.

The key move: **the code is the source of truth for the contract, not the description file.** Everything the
component may *touch* — the data it **reads**, the data it **writes** (and into which scopes), the files it
handles, the outside websites it may **call**, the **secrets** it needs (by name only) — is **derived from
your code** by `aos check`, which writes it into `meta.yaml` for you. You never hand-maintain those lists;
they can't drift from what the code actually does, because they *are* what the code does. (The **events a
component reacts to** — `subscribes:` — the platform auto-wires into a governed subscription on install; see
[Interaction: verbs & events](/developer/deep-dives/interaction/). **Lifecycle hooks** — `lifecycle:` — are
handlers the platform calls automatically when the component is installed, reconfigured, or removed.)

The resulting `meta.yaml` still *is* the component's contract — an organization reads it before installing and
knows exactly what the software can and cannot do. What changed is *how it comes to exist*: derived from the
code and signed into the certificate, not typed by hand and hopefully kept in sync.

## The kinds of component

Different jobs need different shapes. The main kinds:

| Kind | What it does |
|---|---|
| **driver** | Brings outside data into the registry as facts, with provenance. The only sanctioned way external data becomes governed state. |
| **engine** | Reads authoritative data, computes something, and writes a derived result — or drives a step-by-step process. Exposes named actions ("verbs"). |
| **app** | A screen a person uses (a map, a dashboard, a form). Holds no authority of its own — it acts as the logged-in user. |
| **solution** | A bundle that lists other components; installing it installs all of them together. |
| **agent** ("AI Expert") | A packaged domain assistant carrying a persona and a set of skills. In its first version it reads and recommends — it does not decide. |
| **skill** | The atomic reasoner: takes facts and rules and produces a cited recommendation. |
| **runtime** | The execution environment heavier components run in (covered in [Runtimes & Delivery](/developer/deep-dives/runtimes/)). |
| **pipeline** | Chains several stages (sense → predict → detect → advise) into one runnable unit. |

## How components fit together

Because every component *declares* what it reads and writes, the platform can wire them into a graph on
its own: a driver writes a data type, an engine reads that type and writes a derived type, an app reads
both and draws them. Nobody hand-connects the wires — the declarations do it, and when a solution is
published the platform can check its data graph is complete.

Two roles stay strictly separated in that graph:

- **Engines** carry authority to compute and write derived facts, always stamped with how they were
  derived and from what.
- **Apps** carry *no* authority. An app reads and displays; it acts purely as the person using it, and
  it must show the provenance and confidence of every value it puts on screen. A tampered app simply
  won't load.

## A component is a class; add config to get an instance

The same certified component can run in different places with different settings. The component itself
is like a *class*; the component **plus its resolved configuration** is an **instance**. Install a
solution into two different organizations and you get two instances of each member — same certified
code, different config — recorded so the platform knows exactly what is running where and under what
settings.

**A worked example.** An "air-quality alert" solution might bundle two members: a *driver* that fetches
readings from a sensor network, and an *app* that shows an alerts dashboard. Installing the solution
fans out and installs both, wired together by their declarations — the driver writes sensor readings,
the app reads them. Install the same solution for a city environment department and for a state
pollution board, and each gets its own instance, pointed at its own area and its own sensor network —
but both run the identical certified code. Nobody re-plumbs anything; the declarations do the wiring
and the config does the rest.

## Where this stands today

**Working now:** the whole component model, with real certified components across every major kind —
drivers, engines, apps, solutions, skills, agents, pipelines — in the live library; the shared
certify-and-deliver path; engines exposing governed verbs; and the "app acts as the user, holds no
authority" rule enforced by the host.

**Being built / evolving:** some of the design records behind this (component instances, the Solution
Architect that generates solutions, the move to deliver *everything* from the filestore rather than
baking some into the platform image) are accepted directions still being rolled out — so a few
components today still ship baked in rather than delivered on install. The AI agent's ability to *act*
(rather than only recommend) is a planned later version.

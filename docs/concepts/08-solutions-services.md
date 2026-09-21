# Solutions & Services

*The three sizes you can consume capability in — a part, a bundle, or an operated outcome.*

## One axis, three sizes

[Components](/developer/deep-dives/components/) are the building blocks. But you rarely want a single
bare part — you want a working capability. AirawatOS lets you consume capability at **three sizes**,
along a single "packaging" axis:

- a **component** is one part — for example, "fetch air-quality readings from a sensor network";
- a **solution** bundles parts into a working capability — for example, "air-quality monitoring" —
  and is what most organizations actually install;
- a **service** is the largest: an *outcome operated for you over time*, against a service-level
  agreement, possibly spanning several solutions and several providers.

A useful way to remember it: **parts and bundles you install; a service is operated for you.**

## Solutions: a bundle that installs itself

A **solution** is a component whose body is a *list of other components*. Installing it **fans out** —
the platform installs every member, wires them together by their declarations, and applies the
configuration the solution specifies. One click, a complete capability.

Because the members are ordinary certified components, a solution is not a special monolith — it's a
manifest. That means a solution can safely reuse parts that other solutions also use, each member is
independently certified, and the platform can check at build time that the solution's data graph is
complete (every "read" has a matching "write" somewhere).

**A worked example.** A "flood monitoring" solution might bundle a rainfall driver, a terrain driver, a
flood-risk engine, and a map app. Installing it for a river-basin authority pulls in all four, points
them at that authority's area, and lights up a working flood map — without the authority assembling the
pieces by hand. Swap "flood/river basin" for "outbreak tracking/health department" and the motion is
identical; only the members differ.

## Services: an outcome, operated over time

A **service** is a step up in kind, not just size. Where a solution is *software you run*, a service is
an *outcome delivered to you* — often person-centric ("get me a birth certificate", "keep this area's
air within limits"), often spanning **more than one provider**, and measured against a **service-level
agreement** rather than just "is it installed."

The important idea is that a service can cut across organizational boundaries while keeping each
provider accountable for its own part. A citizen-facing service might touch several departments; each
handles its step, each is answerable for it, and the whole is stitched together as one experience — with
receipts at each hand-off (this reuses the same signed, formal exchanges from
[Participants & the Network](/developer/deep-dives/participants/)).

**A worked example.** A "new business registration" service might require a name approval from one
department, a tax registration from another, and a trade licence from a third. To the applicant it's one
request with one status to track. Underneath, each provider fulfils its own step under its own
authority, and the service coordinates them and records each result.

## Why keep them distinct

Collapsing these three would lose something important each time:

- a **component** is the unit of *certification and trust* — the thing that is signed and sandboxed;
- a **solution** is the unit of *installation* — the thing an organization adopts in one step;
- a **service** is the unit of *accountability over time* — the thing measured against an SLA and
  operated on someone's behalf.

Keeping them separate is what lets the same certified part appear in many bundles, and the same bundle
underpin many operated services.

## Where this stands today

**Working now:** solutions are fully live — real bundles install and fan out into real deployments
across several sectors, with members wired by declaration and configured per install. The service tier
has a working spine too: a service directory you can search, the ability to raise a request that opens a
case with a provider, status tracking, and signed receipts at each step.

**Being built:** the fullest form of the service tier — a rich, SLA-measured outcome operated across
many providers over a long period — is still maturing. Describe an installed solution as "running"; a
long-lived cross-provider operated service as "emerging."

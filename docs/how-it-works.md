# From pilots to platforms

*India does not have a shortage of good urban-AI pilots. It has a translation and scaling problem — and closing that gap needs a new division of labour, not another platform to adopt.*

## The problem is the ugly middle

Researchers repeatedly demonstrate that something works — a model that detects potholes, estimates air
pollution, predicts flooding, reads property characteristics, optimises traffic. Today the impact of that
work is usually measured by whether the *pilot* worked.

But taking a prototype from a lab or a pilot into a production-grade solution that hundreds of cities can
adopt requires productisation, integration, security, procurement, deployment, support, capacity building
and sustained ownership. **No single participant is naturally equipped to do all of that** — and so good
work stalls in the middle, between "it works" and "it's running everywhere."

The proposition here is that **you should not have to do all of it yourself.**

## A new division of labour

Four kinds of participant each hold part of the answer, and each needs something the others have:

| Participant | Brings | Needs |
|---|---|---|
| **Government** | Problems, data, authority, adoption, funding | Proven solutions, choice, capacity |
| **Researchers** | Research, models, algorithms, innovation | Real problems, data, deployment, evidence |
| **SIs / startups** | Productisation, integration, deployment, sales | Proven technology, reusable capabilities, customers |
| **NGOs / philanthropy** | Mission, community reach, catalytic capital | Scalable impact, evidence, sustainability |

None of these groups is weak. **The problem is that the interfaces between them are weak.** A researcher
shouldn't need to know which government will eventually use their algorithm; an SI shouldn't need to know
which university built every model; a government shouldn't need bespoke integration for every capability.

That gap — the translation layer between research and impact — is the role Airawat exists to fill: the
shared **infrastructure, standards, evidence and ecosystem** that let these capabilities connect.

## The pathway

```
Research → Algorithm / Model → Component → Product → Government Deployment → Evidence → better Research
```

The key idea: **the researcher doesn't have to become a systems integrator or a software company.** They
package what they proved as a reusable **Component**; SIs and NGOs carry it to governments and communities;
governments deploy and sustain it; and every deployment generates **evidence that flows back into research**.

It changes the definition of impact — from *"how many pilots did we run?"* to *"how many real-world
deployments are running capabilities that originated in our work?"*

## How the pieces fit together

If hundreds of organisations are going to build together, they need a common language and shared
infrastructure — one agreement on **how components describe themselves, how data is represented, how
permissions work, how code executes, and how provenance is recorded.** That is what **AirawatOS** provides.
Six pieces, in plain terms:

- **Components** — the single building block. Every capability — a data importer, a model, a piece of logic,
  a screen, a whole service — is a component. They are all described, checked, signed and run the same way.
- **The Network** — the standards body and shared vocabulary. It governs the agreed data shapes (schemas),
  the ways components talk (verbs/interfaces) and the roles that act; it **certifies** components and lists
  them in the **Marketplace** (and services in a **Service Directory**) for anyone on the network to find.
- **The Kernel** — the trusted core each participant runs. It checks a component's certificate before
  running it, confines it to exactly what it declared (the "clean room"), and stamps every write with who
  produced it and from what. What a tenant trusts is the *certificate*, not your code.
- **Runtimes & delivery** — heavier components run in certified runtime environments; the code itself is
  delivered from a content-addressed store and digest-verified on the way in. Nothing runs that wasn't
  published and signed.
- **The Registry** — the shared record book. Every record has a governed type, every write is attributed,
  and history is preserved — so any number can be traced back to the exact source it came from.
- **Federation** — each organisation is its own tenant *and* a citizen of the network. They share governed
  data across tenants through governed doors, keeping ownership and consent intact.

Put together, the flow is simple:

```
A researcher PUBLISHES a component
   → the Network CERTIFIES it and lists it in the Marketplace
      → an SI COMPOSES several components into a Solution
         → a government INSTALLS the Solution into its own tenant
            → the Kernel RUNS it in the clean room; the Registry RECORDS attributed, governed data
               → the deployment GENERATES evidence that flows back to research
```

Independently developed capabilities work together because everyone agreed on the interfaces — not because
they all came from the same vendor.

## What this means for you

**Researchers — don't stop at the pilot.** You've developed something valuable. What if the end of the
project weren't the pilot, but the *beginning of distribution*? Package one capability as a Component and
organisations across the ecosystem can discover and use it — while deployments send evidence back to you.

**SIs & startups — don't build everything again.** Today, every urban-AI win repeats the same work: data
connectors, GIS, workflows, dashboards, AI pipelines, integrations, deployment, security. Assemble proven
Components instead and spend your effort where you win — customer relationship, solution design,
configuration, integration, operations. Airawat isn't here to take your business; it should make it easier
to do more of it. (This is the Linux/Red Hat lesson.)

**NGOs & philanthropy — fund scale, not another isolated pilot.** Instead of *₹X crore → 3 districts →
report → grant ends*, fund a reusable capability that keeps spreading after the grant ends: *proven
capability → reusable Component → open distribution → implementation partners → government adoption →
replication.* The philanthropic rupee then carries residual infrastructure value.

**Governments — get innovation without a new generation of lock-in.** Choose your researchers, products,
integrators and cloud, and keep common standards and portability underneath. Interoperable components, open
standards, reusable products, a choice of partners and sovereign deployment options — so you don't bet
everything on one proprietary stack.

## Build once. Improve together. Deploy many times.

> Researchers should not have to become systems integrators. SIs should not have to reinvent technology
> researchers already built. Governments should not have to choose between innovation and vendor lock-in.
> Philanthropies should not have to keep funding the same capability in different places.

What if the output of every Airawat-supported project were not merely a pilot, but a **reusable capability**
available to the next researcher, the next integrator and the next city? That is the point of the shared
infrastructure described here — and the rest of this portal shows you how to build on it.

Next: the [Quickstart](/developer/get-started/quickstart/) if you want to build now, or a deeper look at
[Components](/developer/deep-dives/components/), [Solutions & Services](/developer/deep-dives/solutions-services/)
and [Governance](/developer/deep-dives/governance/).

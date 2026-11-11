# From Evidence to Action

*Why a decision-support system is a chain of transformations — from an imperfect view of reality to an accountable public action — and why AirawatOS preserves that chain end to end.*

## The real problem

Governments decide with incomplete information every day. A flood officer rarely knows the water level at every point. A commissioner deciding where to send sanitation teams has complaints from some wards and near-silence from others. A public-health officer must often act before every case is confirmed.

AI and digital systems can now fill some of those gaps — estimate what wasn't measured, spot patterns, flag emerging risk, suggest interventions. That is a real opportunity. But it sharpens one question:

> **How do we move from incomplete evidence to consequential public action while preserving the ability to understand, challenge, and defend the decision?**

The key idea is that a decision-support system is not a dashboard. It is a **chain of transformations**: at each step, information gains value but also acquires assumptions, uncertainty, and the possibility of error. If that chain is not preserved, the final recommendation becomes impossible to explain, contest, or defend. A trustworthy system preserves the chain.

This is the third of three questions the platform is built to answer. The first: *why should a human trust intelligence produced by a machine?* The second: *how can an institution preserve what it knew, and when it knew it?* This one: *how do we turn uncertain information and machine intelligence into accountable public action?*

## Three intertwined chains

A trustworthy decision-support system has three dimensions that must be woven together, not built as separate systems.

**The decision loop** — the path from observation to action, and back:

```
Ingest → Infer → Detect → Diagnose → Recommend → Verify → Decide → Act → Assess → Learn
```

The important word is *loop*. Verification can invalidate a diagnosis; new information can revise a recommendation; an intervention changes the situation and produces fresh observations. The sequence is a simplification of an iterative process.

**The evidence chain** — what travels *with* every assertion:

```
Source → Provenance → Freshness → Completeness → Method → Assumptions → Uncertainty
```

**The accountability chain** — what makes an action defensible:

```
Authority → Decision → Rationale → Action → Audit → Contest → Review
```

## Data is not reality

Every decision begins with evidence — sensors, registries, satellites, CCTV, field officers, citizens, history. None of these is a perfect representation of reality. A sensor fails; a report is partial; a registry is stale; a satellite image is days old. So the platform never confuses **data** with **reality**: data is an observation, produced by a particular mechanism, at a particular time, with particular limits. In AirawatOS this is enforced structurally — every fact is a governed record carrying its `observed_at`, its `method`, and its provenance.

## Inferred is not observed

Where the information a decision needs does not exist, models estimate it: air quality between monitors, water depth where there are no gauges, demand from partial mobility data. This is powerful — but an inferred fact is not an observed one, and the platform keeps them distinguishable. A measured gauge reading and a modelled ward estimate may both be valuable; they are not equivalent. Every record declares its `method` — `measured`, `model`, `statistical`, `rule`, or `human` — so "observed vs inferred" is never lost.

## Detect, then diagnose

Assembling the picture lets the system flag where attention is needed — an emerging flood zone, an abnormal crowd, a service-delivery failure. Many analytics systems stop there. But knowing *where* is not knowing *why*. A flooded road may be heavy rain, a blocked drain, insufficient capacity, or altered flow from construction. Different causes imply different interventions, so a wrong diagnosis can make an otherwise reasonable recommendation wrong. Diagnosis combines observations with models, domain knowledge, and history — and the recommendation cites the evidence it rested on.

## The evidentiary burden rises at the recommendation

When the system moves from *describing* reality to *proposing that someone change it*, the question is no longer only "is this prediction accurate?" but also "is this intervention appropriate?" and "what if we are wrong?" In AirawatOS a recommendation is a governed `governance.recommendation` that cites, in its `evidence[]`, the exact records it relied on — so the burden is inspectable, not asserted.

## There is no single confidence number

We often speak of "AI confidence" as one percentage following a recommendation through the chain. Reality is more layered. A camera may be highly confident it saw a crowd; the crowd estimate may still be incomplete because two cameras are down; a model may confidently predict congestion while the evidence that closing a road *helps* is much weaker. These are different uncertainties and must stay distinguishable.

So the right frame is the **quality and uncertainty of the evidence**, of which a confidence score is one component. A conclusion like *Crowd risk: HIGH* becomes usable when the decision-maker can also see: camera coverage 84%, last observation 90 seconds old, two cameras unavailable, density estimate high-confidence, exit-throughput estimate medium-confidence, field verification pending. AirawatOS already computes these components — coverage, freshness, gaps, and per-fact confidence are produced per layer as `city.coverage`; the direction of travel is to compose them into one evidence-quality view attached to the recommendation itself.

## Sometimes the right recommendation is: find out more

A decision-support system need not always propose an operational action. When a possible obstruction is detected but coverage there is poor, the appropriate move may be **gather additional evidence** — ask a field officer to verify. The officer reports a temporary vendor barricade; the diagnosis strengthens and the recommendation sharpens. Ground-truthing is not a step after analytics — it is one of the ways the system actively manages uncertainty. AirawatOS supports this today through governed field campaigns and field reports.

## Human-in-the-loop is not enough

Many systems call themselves "human-in-the-loop" because an officer clicks *Approve*. That is a weak form of control. Meaningful oversight means the decision-maker can *interrogate* the recommendation: what evidence supports this? which parts are observed and which inferred? how fresh is it? what is missing? why this cause? what does it assume? what are the alternatives? what happens if we do nothing? Only then does the human meaningfully participate. This is why AirawatOS exposes the recommendation's evidence and provenance to the decider — not just a button.

## From recommendation to coordinated action

A recommendation has little value unless someone acts, and a real response usually spans organisations. Reducing crowd risk might need police to restrict an entry point, transport to hold buses, parking to redirect vehicles, and a field team to clear an obstruction. The platform decomposes one decision into tasks routed to each responsible role, and tracks acknowledgement, progress, and completion — turning decision support into decision *coordination*. In AirawatOS this is the fan-out from a signed `governance.decision` into role-addressed `platform.inbox_item` tasks.

## Closure is not success

Governments track whether an activity was completed. But a cleaned drain is not the same as reduced flooding; a deployed team is not the same as fallen density; a closed grievance is not the same as improved service. A trustworthy system assesses **intervention effectiveness**, not merely task completion — and the outcome becomes new evidence that improves the next decision. This is the part of the loop most systems omit, and where the platform's own build focus now sits.

## A public decision must be contestable — by design

Public decisions affect rights, livelihoods, mobility, and safety, so people must be able to question them: *why was my benefit denied? why was my neighbourhood evacuated? why was this road closed?* The institution must be able to answer — not "the AI decided," but: these were the facts, this is where they came from, this part was inferred, this model and version produced it, these were the assumptions, this was the uncertainty, this officer decided, and this was the rationale.

Contestability is therefore an **architectural requirement**, not an appeals mechanism bolted on afterward. If a decision cannot later be explained, reconstructed, or challenged, the system is already poorly designed. AirawatOS records the accountable decision as a cryptographically **signed** `governance.decision` whose evidence manifest *is* the receipt, and treats every mutation as a decided change-request — the substrate contestability needs.

## Defending the decision: what was knowable at 10:15

Provenance protects citizens; it also protects officials. Suppose a commissioner acts on the information available at 10:15 AM. At 3:00 PM new information shows one estimate was wrong. Six months later the decision is reviewed. The right question is not *what do we know today?* but *what was reasonably knowable at 10:15 when the decision was made?* A trustworthy system preserves the state of knowledge at decision time — the observations, records, models, assumptions, known gaps, and rationale. Later corrections enrich institutional memory **without rewriting history**. AirawatOS does this with a **bitemporal** registry that distinguishes when something was true from when it was recorded, so any past decision can be reconstructed as of its moment.

## Institutional memory becomes decision infrastructure

Over time every decision leaves a record — not only *what did we do?* but *what did we know, what did we expect, what did we decide, what actually happened?* That makes genuine institutional learning possible: which interventions consistently work, under what conditions, which models systematically over- or under-estimate risk, which recommendations experienced officers override. Government can move from experience living in individual heads toward accumulated institutional intelligence.

## The objective

The point is not merely to build systems that tell governments what to do. It is to build systems in which a government can say, of any decision:

> This is what we knew. This is what we did not know. This is how we reached this conclusion. This is why we chose this action. This is who was accountable. This is what happened afterward. And this is what we learned.

As AI becomes more deeply embedded in public decision-making, the decisive question will not be whether it can produce better recommendations. It will be whether we can build institutions that use machine intelligence while preserving human judgment, uncertainty, accountability, and the right to challenge a decision. That is where decision support becomes institutional infrastructure.

## How AirawatOS implements this

The three chains map onto concrete, running platform mechanisms:

- **Ingest / Infer / Detect** — confined certified *drivers* write governed facts; *engines* derive the unobserved; every record carries `method` (observed vs inferred) and `observed_at`.
- **Recommend** — `governance.recommendation` cites its `evidence[]`; AI advises, it does not act.
- **Decide** — a named authority admits it into a signed `governance.decision`; the evidence manifest is the receipt (see *[Governance & Decisions](/developer/deep-dives/governance/)*).
- **Act** — the decision fans out into role-addressed tasks in the universal Inbox (see *[Work](/developer/deep-dives/work/)*).
- **Evidence chain** — source disclosure (`ref.source`), a W3C-PROV provenance envelope, `observed_at` + a **bitemporal** registry for freshness and point-in-time reconstruction, and per-layer completeness (`city.coverage`: coverage %, freshness, gaps, confidence).
- **Accountability chain** — governed roles and authority, signed decisions, immutable audit via provenance and receipts, and bitemporal reconstruction for review.

The parts of the loop under active development are the ones most systems skip: composing evidence-quality into a single interrogable view, assessing intervention *effectiveness* (not just completion), making *gather-more-evidence* a first-class recommendation, and turning contestability into an explicit citizen-facing flow. See also *[Intelligence & AI](/developer/deep-dives/intelligence/)*.

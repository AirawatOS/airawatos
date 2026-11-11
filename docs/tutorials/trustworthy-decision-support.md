# Tutorial — build a trustworthy decision-support system

*The [Air Intelligence tutorial](/developer/tutorials/air-intelligence/) wired sense → recommend → decide. This one goes further: it builds the **whole trustworthy loop** — evidence with provenance, a cited recommendation, a signed decision, a coordinated action, an honest assessment of whether it worked, and the ability to defend or contest it afterward. It is the buildable companion to the deep dive [From Evidence to Action](/developer/deep-dives/decision-support/).*

By the end you can build a decision-support system where a government can say, of any decision: *this is what we knew, this is what we did not know, this is why we chose this action, who was accountable, what happened afterward, and what we learned.*

We use a running example — a **crowd-safety** loop for a mass gathering — but every step is generic. The real components are named so you can read the full source.

> Prerequisite ideas, all from the Deep Dives: a **driver** ingests data; an **engine** derives new facts; a **governed schema** shapes every record; a **recommendation** cites its evidence; a **signed decision** is the accountable act; the **Inbox** is where people act. This tutorial composes them into the loop.

## The shape of what we're building

```
Ingest → Infer → Detect → Diagnose → Recommend → Decide(signed) → Act → Assess → Learn
                                                        ▲                        │
                                                        └──── the analyst reads outcomes ────┘
```

Three things must travel through it and never be lost: the **evidence chain** (source · provenance · freshness · completeness · method · uncertainty), the **decision** (authority · rationale · signature), and the **outcome** (did it work). If you preserve those, the system is trustworthy. If you drop them, the recommendation becomes impossible to explain, challenge, or defend.

## Step 1 — Model the world: govern your schemas

Every record is a governed, typed fact. Before writing any data, propose the schemas to the Network so they can't drift. Two rules matter for trust:

- Every measure carries **`observed_at`** and a **`method`** — so you can always tell *observed* from *inferred*.
- City- or event-specifics live in **data**, never in a component name or code.

```python
# govern a measure (per H3 cell) via the network — steward-gated, idempotent
post(NET + "/v1/schema-requests", {
  "schema_id": "cell.crowd_density", "version": "0.1.0", "x_kind": "measure",
  "definition": {"type": "object", "x-kind": "measure",
    "required": ["schema", "id", "observed_at", "prov"],
    "properties": {"density_sqm": {"type": "number"}, "headcount": {"type": "integer"},
                   "method": {"type": "string"},      # measured | model | statistical | rule | human
                   "observed_at": {"type": "string"}, "prov": {"type": "object"}}}})
post(NET + "/v1/schema-requests/decide", {"schema_id": "cell.crowd_density", "version": "0.1.0", "decision": "approve"})
```

**Trust property established:** the world is described in typed facts a steward approved — not free-form JSON.

## Step 2 — Ingest: a confined driver, and *data is not reality*

A **driver** is a certified component whose only I/O is the broker. It reads its area-of-interest, calls out to a real source, and writes governed facts — each stamped with how and when it was observed.

```python
# driver run.py (confined): write cell.crowd_density with provenance
obj = {"schema": "cell.crowd_density", "id": f"ds:{T}:cell/crowd_density/{cell}-{t}",
       "space": {"h3_id": cell}, "observed_at": t, "density_sqm": d, "headcount": head,
       "method": "measured",                          # or "sim-gaussian" for an exercise feed — labelled honestly
       "prov": {"source": "cctv-fusion", "at": t}}
call("/v1/write", {"scope": "cell.crowd_density", "id": obj["id"], "object": obj})
```

Certify + publish + install it, then run it:

```bash
python3 tools/deploy_component.py            # certify + stage source + single publish
# install into the tenant (one grant per declared write), then run
```

**Trust property:** every fact knows its source, method, and time. A simulated or estimated feed is *labelled as such* — never dressed up as a measurement.

## Step 3 — Infer: fill the gaps, but keep *observed ≠ inferred*

Where you have no observation, an **engine** estimates it — and marks the result `method: "model"`. The real `flood-risk` engine does exactly this: it reads real terrain + hydrology and writes a `risk.flood` score, tagged `model`, carrying its drivers so it is re-derivable.

The platform never treats an inferred fact as an observed one. That single discipline is what lets a decision-maker later ask *"which of this did we actually see?"*

## Step 4 — Detect & Diagnose, then Recommend — citing the evidence

An engine that finds where attention is needed writes a **`governance.recommendation`** — and the recommendation **cites the exact records it relied on** in its `evidence[]`. This is the cross-function move: the real `crowd-flow-coordinator` joins the crowd feed with CCTV detections, computes an inflow-vs-outflow imbalance, and recommends *reduce inflow* — citing both source records.

```python
ctx_write(rid, {"schema": "governance.recommendation", "id": rid, "tenant": T,
  "title": "Reduce inflow at Ramkund", "proposed_action": "reduce-inflow",
  "rationale": "cctv_count=14 · band=critical · net_inflow_per_hr=12882",
  "evidence": [crowd_row_id, cctv_row_id],     # the burden is inspectable, not asserted
  "method": "rule", "confidence": 0.8, "produced_by": "component://…/crowd-flow-coordinator"})
```

**Trust property:** the AI *advises*; the recommendation is a claim you can trace to its sources — not a black box.

### When the right recommendation is "find out more"

Sometimes the honest move is not an operational order. The `evidence-gap-recommender` engine flags detected hotspots that **lack corroboration** (no CCTV on the cell) and recommends `gather-evidence` — dispatch a field officer, task a camera — so uncertainty is *managed*, not ignored.

## Step 5 — Show the *quality* of the evidence, not one number

There is no single confidence figure that follows a recommendation through the chain. So the analyst composes the **quality of the evidence** per layer: coverage % (from `city.coverage`), freshness (`observed_at` age), the observed-vs-inferred split (`method`), and confidence. The City Intelligence engine returns this as `evidence_quality`, and City Scan renders it beside the answer:

```
Flood risk    inferred 3078          conf 0.72
Crowd density inferred 152 · observed 1
CCTV          unattributed 4         ← itself an evidence-quality signal
```

**Trust property:** the decision-maker sees *how good the evidence is*, not just the conclusion — and can interrogate it (what's inferred? how fresh? what's missing?). That is what makes human oversight meaningful, rather than a rubber-stamp Approve button.

## Step 6 — Decide: one accountable, signed act

The AI never decides. A named authority **admits** a recommendation into a **`governance.decision`**, signed with their key (Ed25519 via the tenant's Vault). The `evidence_manifest` *is* the receipt.

```python
core = {"schema": "governance.decision", "id": did, "outcome": "approved",
        "authority": "user://nashik/nashik-admin", "rationale": "…",
        "evidence_manifest": [rec_ids…], "decided_at": now}
core["signature"] = signing.sign(VAULT_ADDR, VAULT_TOKEN, core["authority"], core, network_url=NET)
```

**Trust property:** a single point of accountability, cryptographically non-repudiable, and offline-verifiable against the network key directory.

## Step 7 — Act: one decision, many agencies

A real response spans organisations. The decision fans out into role-addressed **`platform.inbox_item`** tasks — crowd marshals, transport, parking, police — each tied back to the decision id, each tracked to completion. Decision support becomes decision **coordination**.

## Step 8 — Assess: closure is not success

A cleaned drain is not reduced flooding; a deployed team is not fallen density. The `effectiveness-engine` measures the **target measure before vs after** the intervention on the affected cells and writes an **`intelligence.effectiveness`** record — and it is honest about what it can claim:

```python
{"decision": did, "intervention": "reduce-inflow", "target_schema": "cell.crowd_density",
 "baseline": {"mean": 7.003}, "followup": {"mean": 0.79}, "delta_pct": -88.7, "direction": "improved",
 "note": "OBSERVED change on the affected cells — NOT a causal claim; attribution needs a counterfactual."}
```

**Trust property:** the outcome is measured and written back as new evidence — and the system refuses to claim the intervention *caused* the change without a counterfactual.

## Step 9 — Learn, and feed it back

The `learning-engine` aggregates those outcomes by intervention into an **`intelligence.learning`** signal (*"reduce-inflow on crowd density: improved 1/1, mean −88.7%, evidence: provisional"*). Then the analyst **reads it**, so the next recommendation is grounded in what worked:

> *"Reduce inflow at Ramkund again — the identical action worked last time (density −88.7%), and levels have climbed back to critical."*

**Trust property:** institutional knowledge accumulates in the registry, not in officers' heads — and the loop closes: outcome → learning → the next recommendation.

## Step 10 — Contestability & defence, by design

A public decision must be explainable and challengeable. The `decision-assurance` engine provides two governed verbs:

- **`decision-dossier`** reconstructs a decision's full record — authority, rationale, signature, the recommendations and the facts each cited (with method and freshness), and the measured outcome. The *"defend the decision as of when it was made"* view.
- **`contest-decision`** files a challenge to the deciding authority and returns the dossier, so the challenger sees the exact basis.

**Trust property:** contestability is an architectural property, not an appeals process bolted on afterward. Because every fact is bitemporal (`observed_at` vs when it was recorded), a review six months later asks the right question — *what was reasonably knowable at decision time* — and the record can never be silently rewritten.

## Step 11 — Package it: a governed solution + managed verbs

Wire the pieces into a **solution** — a signed bundle installed with one approval — and a **Studio project** so it's editable. Two governance rules make it trustworthy end to end:

- **Every verb is network-approved.** A component that declares a verb whose interface isn't a governed `network.interface` **fails certification** — it can't be published, installed, or dispatched. Govern the interface first (`POST /v1/interfaces`), then the certify-time `governed-interfaces` check enforces it.
- **A solution registers its own layers on install.** Declare a `lifecycle: {on_install: <handler>}` hook; the host fires it in the confined engine context so the solution seeds its `viz.layer` descriptors into the tenant automatically — the map picks them up with no host code.

```yaml
# in the engine's meta.yaml
implements: [intelligence.assess_effectiveness@0.1.0]
verbs: { assess-effectiveness: intelligence.assess_effectiveness@0.1.0 }
lifecycle: { on_install: seed-layers }
```

## The result

You've built a system where intelligence is used but never trusted blindly:

- every fact carries its provenance, method, and time;
- the recommendation cites its evidence and shows its quality;
- the decision is signed and accountable;
- the action is coordinated across agencies;
- the outcome is measured honestly and fed back;
- and any decision can be reconstructed, defended, or contested.

That is the anatomy of a trustworthy decision-support system — and on AirawatOS it is a handful of certified, governed components on the shared decision spine, not a monolith. Read the concepts in [From Evidence to Action](/developer/deep-dives/decision-support/), and the accountable-decision mechanics in [Governance & Decisions](/developer/deep-dives/governance/).

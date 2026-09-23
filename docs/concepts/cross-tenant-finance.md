# Worked example: money across tenants

*How a water-supply grant moves from a national ministry, through a state, to a city — and why the money follows the information.*

A single-organization workflow stays inside one tenant. This one crosses **sovereign tenants** — a ministry, a state department, a city — none of which can see into another's database. It shows the platform's sharpest civic idea: **the flow of information across agencies determines the flow of money.** Make the information flow governed, shared, and tamper-evident, and the money flow follows it — with no PDFs, no portal reconciliation, and one true picture everyone can trust.

This is the pattern behind India's centrally-sponsored schemes (PMAY-U, AMRUT, Jal Jeevan Mission) — the classic **60:40 Centre:State** co-funding, released in instalments gated on reported progress. It composes primitives you've already met — the cross-tenant data-request/grant lane, signed decisions, double-entry finance, and verifiable credentials — arranged along the **jurisdiction ladder** (nation → state → city).

## The players — three tenants

- **MoHUA** — the national ministry, its own tenant, holds the scheme's budget.
- **State HUDD** — the state's urban department, its own tenant, co-funds 40%.
- **KMC** — the city, its own tenant, does the actual work.

Each is sovereign over its own data. Nobody has a login to anyone else's system. Everything below moves through the **governed cross-tenant lane**: a tenant *requests* to see another's record, that tenant's admin *consents*, and a signed **grant** lets the kernel serve exactly that data — and only that data — leaving a receipt.

## The loop — information gates money

**1. The city assesses need (its own data).**
KMC's diagnosis — coverage gaps in piped water, drawn from its governed layers — becomes a `governance.recommendation` and then a **funding proposal**: "extend supply to these wards; ₹X." It's a signed record in *KMC's* tenant. Nothing has left the city yet.

**2. The funders see the proposal — under consent.**
KMC submits the proposal *to the scheme*. MoHUA and HUDD don't get a copy of KMC's database — they file a **data-request** for that proposal; KMC's admin approves; the kernel issues a signed grant and serves *just the proposal*, with a **data-read receipt** KMC keeps as proof of what it shared, with whom, when. The funders now see the same proposal the city sees — one true picture, no re-keying.

**3. The ministry sanctions — a *decided* change-request.**
MoHUA reviews and admits it. That's a **signed decision** (`governance.decision`) — never an automatic transfer; a named official decided, and it's tamper-evident. The sanction is co-funded 60:40, so it references the state's share too. MoHUA issues KMC a **verifiable credential** — an *award* the city holds in its wallet as portable proof it was funded, verifiable by anyone without calling MoHUA.

**4. Money posts — double-entry, in each tenant's books.**
The disbursement of tranche 1 is a `finance.transaction` — double-entry, posted in the funder's ledger and received in the city's. Because it's a *decided* change-request, there's a decision behind every rupee. The state's 40% posts the same way from HUDD. The money moved because a *signed sanction* moved.

**5. The city executes and reports — the same lane, in reverse.**
KMC does the work and records progress against the project's results-contract — per-step **receipts** and a milestone **credential** ("phase 1 complete, verified"). This isn't a report typed into three different portals; it's governed data.

**6. Verified progress releases the next tranche.**
MoHUA and HUDD read that verified progress **through the same governed lane** (request → consent → grant → receipt). Because the completion is a signed, verifiable fact — not a claim in an email — it satisfies the release condition automatically, and tranche 2 is sanctioned. *A verified progress report reached the funder, so the money followed.*

## Why this is different

Every hop shares the property that makes it work:

- **Sovereignty preserved.** No tenant ever reaches into another's database. Each fact stays in its owner's tenant and is *served* across the boundary only under a signed grant — so a ministry sees a city's proposal because the city consented, not because it has access.
- **Information is the currency.** A tranche can't be released until a *verified* progress report reaches the funder. Make that a tamper-evident, shared fact and the coordination cost — the thing that actually stalls these schemes, funds stuck behind a late utilisation certificate — collapses.
- **Every rupee has a decision, every share a receipt.** Disbursements are decided change-requests; cross-tenant reads leave receipts; awards and milestones are verifiable credentials. The full trail — need → proposal → sanction → disbursement → progress → next tranche — is auditable end to end, across organizations that never shared a database.

That's fiscal federalism as a *data* problem, solved once: sovereign tenants, governed sharing under consent, signed decisions, and money that follows verified information down the jurisdiction ladder.

> This composes the cross-tenant lanes and finance/decision primitives the platform already provides; the full multi-tier program orchestration is a separate design for federated program funding. Related: [Participants & the Network](/developer/deep-dives/participants/) (tenants + federation), [Governance & Decisions](/developer/deep-dives/governance/) (signed decisions), and [Data Ownership & Consent](/developer/deep-dives/ownership-consent/) (why a link is not access).

# ADR-0079 — Resource metering, quotas & billing plane

**Status:** Proposed
**Relates to:** ADR-0030 (broker/confinement), ADR-0016/0027 (marketplace pricing/contracts), the finance
domain (finance.transaction/budget/invoice), Inbox/approvals, wallet/VC, runtime-manager placement.

## Context
The platform operator provides the hardware; tenants consume it (compute, GPU, storage, egress, model calls).
Today AirawatOS neither accounts for that consumption per tenant nor bills for it, and there is no operator
surface to add capacity or a tenant surface to see usage/limits and pay. The 1000-camera scale test made the
gap concrete: the perception tier needs GPUs, and their cost must land on the tenant that drove it.

## Decision
AirawatOS owns the **governed accounting plane — metering, quotas, rating, billing — and delegates raw
provisioning to the substrate** (Kubernetes / cloud autoscaling / Nomad). It does **not** become an IaaS or
re-implement a scheduler. The dividing line:

- **Substrate (delegated):** create/destroy nodes & GPU pools, bin-pack containers. AirawatOS *registers*
  that capacity (`infra.node`/`infra.pool`) and *places onto* it (the runtime-manager already places).
- **AirawatOS (owned):** *who consumed what, on whose behalf, under what quota, at what price* — and the
  itemized invoice. Only the governance layer can answer this per tenant, because only it mediates every run.

### Why this is mostly a harvest, not new plumbing
Every confined run already executes under a broker holding `(tenant, component_id, run_id)` and mediating
every read/write/egress/secret (`kernel/services/broker/broker.py`; instantiated live at
`kernel/api/app.py`). **Usage is a byproduct of the confinement seam** — the broker counts, and emits a
`metering.usage` fact at run finish. Node-level cpu/gpu-seconds come from a thin node-agent. The finance
domain, Inbox, and wallet already exist to rate, invoice, and collect.

### New governed nouns
| Layer | Noun | Notes |
|---|---|---|
| Capacity | `infra.node`, `infra.pool` | operator-registered; a node-agent reports live capacity/health/utilisation |
| Metering | `metering.usage` | per (tenant, component, run, `source`) with an open `units` map: reads/writes/egress_calls/secret_uses (broker), cpu_s/gpu_s/mem_gb_h (node-agent), inference_calls/tokens (model-gateway), storage_gb_h/egress_bytes |
| Governance | `infra.quota` | per-tenant limits + burst; enforced at **placement** (runtime-manager refuses over-quota) and at the broker |
| Pricing | `billing.rate_card` | ₹/unit per resource/tier, operator-set |
| Billing | `billing.invoice` | rating engine: Σ usage × rate_card → itemized invoice → `finance.transaction`; monthly, like payroll |

### Enforcement points (already exist)
- **Placement** — runtime-manager checks `infra.quota` before `docker run`; over-quota → refuse (this is also
  the safety valve against "1000 cameras melt the box").
- **Broker** — the per-op capability check gains a quota/rate-limit dimension.

### Surfaces
- **Operator console:** register/label nodes & GPU pools; fleet + per-tenant utilisation; set rate cards &
  quotas; issue invoices.
- **Tenant-admin console:** usage vs quota, cost-to-date, request scale/quota change (→ Inbox approval),
  view & pay invoice.

## Hard boundary — payments
AirawatOS **meters, rates, and presents** invoices; it does **NOT** handle raw card/bank credentials or
process the charge (PCI, and the platform's own no-credential-entry rule). "Pay" hands off to an external
payment rail (UPI/PSP link) and records only the **receipt** (fits the wallet/VC + finance receipt model).

## Non-goals
Not a scheduler, not an IaaS, not a k8s replacement, not a payment processor. No new per-box daemon beyond a
thin read-only node-agent.

## Consequences
- Per-tenant cost visibility becomes intrinsic to the platform, not bolted on.
- Quotas give the operator a real safety + fairness control (and back-pressure for expensive tiers like GPU vision).
- The metering fact is auditable and attributable end-to-end (same provenance spine as everything else).

## Slicing
1. **Metering** (this ADR's first slice) — govern `metering.usage`; the broker tallies I/O and emits it at
   `finish()`, keyed on the run's tenant. Per-tenant visibility from the seam that already exists. *Lowest risk.*
2. **Node/pool registry + node-agent + operator utilisation console.**
3. **Quotas** — enforce at placement + broker.
4. **Rate card + rating engine → invoices** (reuse finance + the payroll monthly-run pattern).
5. **Tenant billing surface + external pay-link + receipt.**

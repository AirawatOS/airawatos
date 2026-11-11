# Airawat

> **Install locally:** follow [`docs/operator/INSTALL-LOCAL.md`](docs/operator/INSTALL-LOCAL.md). How changes reach `main`: [`CONTRIBUTING.md`](CONTRIBUTING.md). (`deploy/local/` is legacy.)

Airawat is the organisation behind **AirawatOS** — a platform for accountable, federated public-data governance — and the **AirawatNetwork** federation authority. This workspace holds one folder **per repository**: each layer is developed, versioned, and certified independently. The structure separates the **reference implementation**, the **federation authority**, and the **domain distributions** built on top.

> **Two-tier brand.** *AirawatOS* is the base platform (kernel + SDK + platform apps) — developer/operator-facing. **Airawat CityOS / HealthOS / JusticeOS …** are **domain distributions** — the customer-facing products, each = AirawatOS + that vertical's domain packs + apps + components + seed.

> **Workspace-first.** For now these live side-by-side so the seams can settle; each folder is designed to become its own git repo under the [`AirawatOS`](https://github.com/AirawatOS) GitHub org. Split a folder into a repo the moment its boundary is stable.

> **Naming.** One name, spelled one way: the organisation and platform are **Airawat / AirawatOS**, and the CLI is **`airawat`**. It was previously `airos`, which collided with Ubiquiti's long-established router-firmware brand — a searchability problem and a possible trademark one. Renamed now, while the only cost is documentation; after people have it installed, the cost is theirs.

## The standard is not in this workspace

**The trust boundary is published separately, under a neutral name, at [`github.com/Digital-Statecraft`](https://github.com/Digital-Statecraft).** That separation is the point: a standard that lives inside the vendor's workspace is not a standard, it is a product's documentation. Airawat *conforms to* it and does not define it.

| Repo | What it is | How this workspace uses it |
|---|---|---|
| **`Digital-Statecraft/mdk`** | the kernel standard — *Minimum Decision Kernel*. Object/evidence model, registry & temporal resolution, provenance & receipts, component execution + the broker/HTTP binding, the decision record, federation — plus the `GOV`/`ARCH`/`SPEC`/`PROFILE`/`MIP` process. | depended on at release **`mdk@0.1`** (`releases/mdk-0.1.yaml`) |
| **`Digital-Statecraft/cdp`** | the Civic Decision Protocol — what a *public administrative* decision means: authority roles, appellate authority, standing, deadlines, remedies. | the civic layer above MDK |
| **`Digital-Statecraft/book`** | *Decision Public Infrastructure* — the narrative companion to the standard. | context, not a dependency |

Earlier copies of `mdk/` and `book/` lived in this workspace and have been removed; they were stale duplicates of the above, and both are recoverable from those repos' git history.

## The layer stack

```
STANDARD      the trust boundary — normative, versioned, conformance-tested
   ↗ mdk              the kernel standard  (Digital-Statecraft/mdk @ mdk@0.1)
   ↗ cdp              the civic decision protocol  (Digital-Statecraft/cdp)
   domain-spec        granular, composable domains (air, water, finance, grievance,
                      health-facility, court-case…) — libraries a distribution composes

KERNEL        reference implementation of the MDK standard — HEADLESS (API + `airawat` CLI)
   kernel             registry · identity · components/contracts · broker · decision spine
                      · federation CLIENT

NETWORK       the federation AUTHORITY (a shared service many kernels connect to)
   network            participant directory · certification · store/marketplace backend · resolution

SEAM          thin clients of the kernel API / broker contract
   sdk                component SDKs (python, ts…) + the `airawat component` dev-tool

ECOSYSTEM     independently built + certified, published to the marketplace
   apps               first-party UI apps (home, admin, data-explorer, network-admin, city-explorer)
   components         first-party drivers / engines / models / connectors

DISTRIBUTIONS the customer-facing products — a MANIFEST that composes the above, never a fork
   cityos             "Airawat CityOS"   = kernel + urban domains + city apps + components + seed
   (healthos, justiceos, … follow the same pattern)
```

## Repos in this workspace

| Folder → repo | Layer | Purpose | Depends on |
|---|---|---|---|
| `domain-spec` | spec | granular, composable domain schemas | `mdk` |
| `kernel` | kernel | reference implementation + `airawat` CLI + API (headless); federation *client* | `mdk` (+ `cdp`, domain specs) |
| `network` | network | AirawatNetwork: federation *authority* + store/marketplace + certification | `mdk` (federation) |
| `sdk` | seam | per-language component SDKs + dev-tool | `mdk` (broker binding) |
| `apps` | ecosystem | first-party UI apps (installed as components) | kernel API, `sdk` |
| `components` | ecosystem | first-party drivers/engines/models/connectors | `sdk`, `domain-spec` |
| `cityos` | distribution | "Airawat CityOS" — urban bundle + local install | everything above |

## Principles

- **The kernel is a microkernel *plus accountability*.** Registry, identity/capability, component lifecycle + contracts, broker/confinement, the **federation client**, **and** the decision/provenance spine — all defined by the MDK standard. Accountability is a kernel guarantee — no distribution may ship an AirawatOS without it.
- **Federation is client (kernel) vs authority (network).** A standalone kernel runs without the network (side-loading components); connect to `network` to gain the shared certified store + cross-instance federation. Both obey MDK `SPEC-0006`.
- **The marketplace is a function, not a repo** — store/certification backend (`network`) + install (`kernel`) + a browse/install UI (`apps`) + local certify checks (`sdk`).
- **The spec is the platform.** A third party can implement a conformant kernel; a component certified against the spec runs on any conformant kernel. This only means anything because the spec is governed outside this org.
- **The kernel is headless.** It ships an API and one CLI (`airawat`). *Every* UI — including the Admin Console — is an app installed on top.
- **A distribution is a curated install manifest**, not a fork. Domains are shared libraries; each `…OS` composes the domains + apps + components it needs (e.g. `population` appears in both CityOS and HealthOS).

## Decision records

Architecture decisions live with the layer they govern. Changes to the **standard** flow through the `ADR → MIP → SPEC` process defined in `Digital-Statecraft/mdk/governance/` (`GOV-0001`) — proposed there, on their merits, not decided here. Each repo in this workspace keeps its own `decisions/` log for choices local to it. An ADR is always informative source material; it becomes normative only when carried into a SPEC through that process.

## Open items

- **✅ `governance-spec` removed** — superseded by `Digital-Statecraft/cdp`; its README (named authorities, standing, deadlines, remedy catalogue, method-selection policy) is preserved in `cdp/prior-art/airawat-governance-spec.md` for carry-into-CDP. *(Was:* Both define the civic layer — named public authorities, standing, deadlines, the remedy catalogue — and CDP is the version that is published, depends on `mdk@0.1`, and is under review. Anything in `governance-spec` not yet carried into CDP (notably the uncertainty-graded method-selection policy and the domain contestation channels) should be moved there; then this folder goes. Note the two currently disagree on one point: `governance-spec` lists a **Court** authority, and CDP deliberately has none — judicial review sits outside the administrative loop.
- **`kernel` holds pre-MDK code.** The repository moved here from `Digital-Statecraft/reference-implementation` with its git history and now lives at [`AirawatOS/kernel`](https://github.com/AirawatOS/kernel), but the code is the earlier GCP-era service and does not yet conform to MDK — no broker, no receipts, no federation. See `kernel/README.md`, which is explicit that the rest of it describes a target rather than what is there.
- **`domain-spec` has no counterpart in the standard.** It is the one spec layer that is genuinely Airawat's to own — worth confirming it should stay here rather than being proposed upstream.

# ADR-0074 — Operator-configurable platform services: the operator is a tenant, and configuring infrastructure is a governed write

- **Status:** Proposed (2026-09-06)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** ADR-0022 (everything-is-a-component — platform services become components too),
  ADR-0036 (component *instance* = component + config **in scope** — the mechanism a per-tenant storage override
  rides on), ADR-0027 (component contracts carry per-holder config + Vault-escrowed secrets — where backend
  credentials live), ADR-0011 (per-tenant realms + the `AIRAWATOS` platform realm + assurance tiers — why the
  operator's power is *roles*, not a code special-case), ADR-0056 (decided change-request — every config mutation
  is one), ADR-0052 (attributed writes — who asserted a config change), the **P0 zero-trust registry
  authorization gate** (the single scope+role gate this ADR reuses for *config* writes, not just data writes),
  Roles-as-governed-actor-vocab (`network.role` packs — where the new operator roles are governed), ADR-0016
  (Marketplace / Store — certify → publish → install spine + signing; the surface this ADR extends *upward* into
  the platform tier), ADR-0051 (sandbox + certificate-verified-at-use enforcement — the bar an *installed*
  platform component's code must clear, higher than a tenant driver because it can sit in the storage path).
  External anchor: the "configuration is code / config-as-data behind an audited API" pattern, and the classic
  separation between a **control plane** (who may change infrastructure) and a **data plane** (what runs on it).

## Context

Today a platform operator configures Airawat's infrastructure — where files are stored, how the scheduler
behaves, what the broker may egress — by editing **env vars and `docker-compose`** on the host over SSH. That
surface has one virtue and several defects.

The virtue: it is **air-gapped from the application plane**. No authenticated session — tenant admin, agent, or
otherwise — can reach infrastructure. The online attack surface for "reconfigure the platform" is effectively
zero; you need host access.

The defects: it is **un-audited** (a compose edit leaves no governed trace of who changed what, when, or why),
**irreversible by the platform** (no decided-change-request to roll back), **invisible** (no UI shows the current
storage backend or lets an operator see it), and **not multi-tenant** (there is exactly one global config; a
tenant cannot say "keep *my* data in *my* bucket / *my* cloud / on-prem"). As the platform federates across
operators — some on AWS S3, some on Azure Blob, some on a network filesystem — and as tenants demand **data
residency**, "one global compose-managed config" stops being tenable.

The concrete trigger: the registry archive-before-purge tiering (task #201) writes cold shards to the filestore,
and the filestore is a **local Docker volume**. Moving it to object storage surfaced the real question — *not*
"configure the S3 bucket," but "**there is no governed interface by which an operator configures a platform
service at all**, and storage is only the first of many such services." And behind that: **should the operator
be a tenant that configures platform services through the same governed machinery every tenant already uses?**

The answer is yes — and this ADR exists to make that yes safe. Its spine is the **security model**, because the
move relocates a trust boundary: it opens an **online path from an authenticated session to infrastructure
reconfiguration** that did not exist before. Done with the invariants below, it is *net safer* than the SSH
status quo (governed, attributed, reversible). Done without them, it is a serious privilege-escalation hole.

## Decision

Model **platform services as platform-tenant-scoped component instances**, configured through the **same
governed config machinery** (Admin UI → decided-change-request → scoped registry write → Vault-escrowed secrets)
that every tenant already uses for its own components. The operator acts as an **elevated role on the platform
tenant** (`AIRAWATOS`), not as a code special-case. Storage backend is the **first** such service and is a
**pluggable abstraction** (`local | s3 | azure-blob | gcs | nfs`), not "S3."

The design is governed by **one security spine** — a service tier + three invariants + a bootstrap rule — and
everything else (the config-resolution chain, the storage seam, the schemas/roles) hangs off it.

---

## Security spine (the reason this ADR exists)

### What is genuinely new — state it plainly

We are trading a **small, un-audited, high-friction** attack surface (SSH + compose) for a **larger, audited,
attributed, reversible** one (an authenticated config API + UI). Two new risks come with it, and must be
defended, not waved away:

1. **A new online path** from an authenticated session to infrastructure reconfiguration.
2. **Blast-radius concentration** in a platform-operator credential: in principle, redirect where every tenant's
   files/archives are stored → mass exfiltration or denial.

The invariants below are what make the trade a net win rather than a regression.

### Service tiering — the single highest-leverage rule

Not every platform service may be governed the same way. Split them:

| Tier | Services | Config source | Rule |
|---|---|---|---|
| **Trust root** | Vault, identity/authz plane, registry, **bootstrap filestore** | **IaC / env only** | **Never self-reconfigurable through the plane it secures.** |
| **Leaf** | per-tenant storage backend, scheduler policy, broker/egress settings | **Governed config**, with a safe bootstrap default | May be operator- or tenant-configured, gated by role + scope. |

The rule that prevents an entire class of attack in one line: **a trust-root service is never reconfigured — or
installed — through the plane it secures.** Two faces of the same circularity:
- *Config-time:* if the filestore's *own* storage backend were governed config read *through* the filestore, an
  attacker who flips it redirects the very store that holds the config and its backups → circular compromise.
- *Install-time:* the certify → publish → install spine **needs the registry** to function; you therefore cannot
  "install the registry through the marketplace" — the thing being installed is the thing the installer depends
  on. Trust-root services are stood up by IaC/compose, full stop.

So Vault, the authz plane, the registry, and the **bootstrap** filestore read only from IaC/env and are never
marketplace-installable. Governed config *overrides leaf behavior*; installation *adds leaf behavior*; neither
ever becomes, or replaces, the root of trust.

### Invariant 1 — Scope isolation: governing config ≠ exposing it to tenants

This is the whole security story, and it reuses the **existing P0 zero-trust gate** — no new trust assumption:

- A write to platform-service config **at platform scope** (`AIRAWATOS`) requires a **platform-operator role**. A
  *regular* tenant admin can never touch it. Denied by default.
- A **tenant-scoped override** may only affect **that tenant's own view** of a service (e.g. its own bucket) —
  **never** the platform default, **never** another tenant's binding, **never** a cross-tenant read.

If scope enforcement is sound for tenant *data* (it is — P0 shipped), it is sound for tenant *config*, because it
is the **same gate**. Corollary: if it is *not* sound, we already have a data-plane hole and this ADR only raises
the stakes — so this ADR's safety is *contingent on* and *co-tested with* the data-plane gate, not independent.

### Invariant 2 — Separation of duties

No single role may both reconfigure infrastructure and sign what runs on it:

- **`platform.operator`** — configures leaf platform services (storage, scheduler, egress). Cannot certify or
  publish components.
- **`platform.content-admin`** — certifies/publishes/installs components. Cannot reconfigure infrastructure.
- **tenant admin** — configures only its own tenant's component instances and tenant-scoped overrides. Cannot
  touch platform scope at all.

The operator's power is thus **decomposed and role-gated**, so a single compromised credential cannot both
redirect storage *and* publish a malicious component to read from it.

### Invariant 3 — Step-up auth + decided-change-request (this is what makes it *better* than SSH)

- Platform-scope config writes require **step-up authentication** (re-auth / MFA), not merely a live session
  token — a stolen session is insufficient.
- Every config change is a **decided change-request** (ADR-0056): **attributed** (ADR-0052 — who asserted it),
  **immutable** in history, and **reversible** by the platform. This is precisely what the SSH/compose path
  cannot offer: today an infra change is silent and unrollbackable; here it is a governed, auditable, revertible
  decision.
- **Credentials are referenced, never contained.** Config points at a Vault secret handle; it never carries the
  secret value. The platform-default storage credentials are readable only by the **service's runtime
  principal** — never by any admin, operator included (the standing "never read secret values" rule).

### The bootstrap rule

Because leaf-service config is *read from* the registry (and secrets from Vault), the resolution chain **must
always terminate in a safe env/compose-level default that needs no governed lookup**. Governed config *overrides*
the bootstrap default; it never *replaces* the ability to boot from env. Consequence: a total compromise or
outage of governed config **degrades to the bootstrap default** (e.g. `local` storage) — the platform still
starts, still stores, still serves — rather than bricking or becoming unreachable.

---

## The rest hangs off the spine

### Config resolution — layered, terminates in bootstrap

For any leaf platform service, in a given scope, resolve config as:

```
tenant override   →   platform default   →   bootstrap default (env/IaC)
   (tenant admin)      (platform.operator)     (never governed; always present)
```

This makes both requirements fall out for free: an operator sets a **platform default** (their S3), and any
tenant needing **residency / their own cloud / on-prem** sets a **tenant override** — Tenant A on S3-Mumbai,
Tenant B on Azure Blob, Tenant C on the operator default — each with its **own** Vault-escrowed credentials
(ADR-0027), each isolated by Invariant 1.

### Storage backend — a pluggable seam, not "S3"

The filestore keeps its content-addressed contract (`sha2-256:<hash>` in, bytes out; key = the hash) and gains a
`backend` seam resolved from config: `local | s3 | azure-blob | gcs | nfs`. Backend + settings
(bucket/container/path, region, endpoint) come from config; credentials from Vault. No provider is hardcoded; the
**bootstrap default is `local`** (the trust-root filestore), so the platform always boots without any object
store configured.

### Leaf platform components are marketplace-installable — the marketplace extends *upward*

The endpoint of ADR-0022 applied to the platform tier: a leaf platform behavior (a storage backend, a scheduler
policy, an egress ruleset) is a **certified, published, installable component**, and the operator **installs and
configures it through the same certify → publish → install spine** a tenant uses for a driver. The marketplace
becomes the catalogue + install surface for the platform tier too — extended *upward*, not a second mechanism.
`s3` / `azure-blob` / `gcs` / `nfs` are thus **installable backend components**, `local` is the built-in
bootstrap. But two boundaries keep "installable" from meaning "open":

- **Install ≠ arbitrary.** Installing a *platform* component is gated by the **`platform.operator`** role
  (Invariant 2), requires **step-up auth** (Invariant 3), and is recorded as a **decided change-request**
  (ADR-0056). No tenant admin, and no ordinary session, can drop a platform service in. "Marketplace-installable"
  means *governed, attributed, role-gated install* — nothing looser.
- **Code in the storage path clears a higher bar.** A backend adapter is not inert config — it is **code that
  runs inside the filestore, on the data-storage path**, which is more sensitive than a tenant driver. So an
  installed platform component's code must be **CA-certified and run under ADR-0051 enforcement**
  (cert-verified-at-use + sandbox), at a **stricter bar** than tenant components, and is **first-party-only**
  until there is a deliberate decision to open it. This is *not* the low-risk case of installing config.

**Design fork (recorded, leaning built-in-first).** Two shapes satisfy the unified surface: *(a) built-in
adapters* compiled into the filestore, *selected and configured* by governed config (small trust surface; adding
a backend = a filestore release); *(b) installable-code backends* loaded at install (true third-party
extensibility; third-party code on the storage path). The **catalogue/install/configure surface is identical
either way**; only the trust bar differs. Lean: ship the first-party backends as **(a) built-in adapters**
selected by governed config, and treat **(b)** as a later, deliberately-gated extension once the enforcement
story above is proven — so we get the marketplace framing now without immediately putting third-party code on
the storage path.

### "Operator as a tenant" — why it is not a code special-case

`AIRAWATOS` is **not "just a tenant."** It is a tenant **plus elevated roles** gated by the authz plane (ADR-0011
platform realm + assurance tiers). Its power comes from **roles**, enforced by the **same gate** as everything
else — never from a bespoke bypass in code (a bypass *is* the hole). This keeps the isolation story honest: the
platform tenant is subject to the gate like any tenant; it simply holds roles no customer tenant holds.

### New governed schemas (propose via governance → steward-approve)

- **`platform.service`** — a platform service registered as a configurable component (name, tier: `trust-root` |
  `leaf`, config JSON-Schema, which roles may configure it, at which scopes).
- **`platform.service_config`** — a scoped config binding for a service (scope, backend/settings, Vault secret
  handle **reference**, decided-change-request id). Never contains secret values.

### New roles (governed via `network.role` packs)

- `platform.operator` (configures leaf services), `platform.content-admin` (certifies/publishes). Both distinct
  from tenant admin; neither subsumes the other (Invariant 2).

### Slicing

1. **This ADR** — the model + security spine.
2. **Schemas + roles** — govern `platform.service` / `platform.service_config`; add the two operator roles.
3. **Config-resolution seam** — the `tenant → platform → bootstrap` resolver, with the bootstrap-default
   guarantee, exercised by a single leaf service.
4. **Pluggable filestore backend** as **built-in adapters** (fork (a): `local` + `s3`), *selected + configured*
   by governed config, `local` bootstrap fallback — the concrete unblock for archival tiering (#201) and
   residency, without hardcoding a provider or a single bucket, and without yet placing third-party code on the
   storage path.
5. **Operator install + config surface** in the Admin app (Storage/Services tab): the catalogue of leaf platform
   components, `platform.operator`-gated install, step-up auth, each change a decided change-request; add Azure
   Blob / NFS adapters as demand appears.
6. *(Deferred, deliberately gated)* **fork (b): installable-code backends** — only once ADR-0051 enforcement for
   platform-tier code is proven and there is a decision to admit third-party backends onto the storage path.

## Consequences

**Positive.** Infra config becomes **governed, attributed, reversible, visible** — a strict improvement over
silent SSH mutations. **Data residency** and **multi-cloud per tenant** fall out of the resolution chain.
Platform services stop being special: they are dogfooded components, installed and configured through the
certify → publish → install spine we already built and harden continuously — the marketplace extended *upward*
into the platform tier. The bootstrap rule guarantees the platform still boots when governed config is
compromised or absent.

**Negative / accepted.** A **new online attack surface** (the config API) exists where none did — accepted
because it is gated by the P0 scope+role gate, step-up auth, and separation of duties, and because it replaces an
*un-audited* surface with an *audited* one. **Blast radius concentrates** in `platform.operator` — mitigated by
role decomposition (Invariant 2), step-up, and the fact that redirecting storage is now a reversible, attributed
decision, not a silent one. The **data-plane gate becomes load-bearing for the control plane** — accepted, and
made explicit: this ADR's safety is co-tested with the P0 gate, not independent of it. **Installed platform code
can sit on the storage path** — the sharpest new risk an *installable* backend introduces; contained by keeping
first-party backends as built-in adapters (fork (a)), deferring third-party installable-code backends
(fork (b)) behind proven ADR-0051 enforcement, and never lowering the platform-code cert bar to a tenant
driver's.

**Rejected alternatives.** *(a) Keep compose/env only* — no residency, no audit, no UI, doesn't scale across
operators; the status quo we are leaving. *(b) A separate bespoke "infra admin" console outside the
component/scope model* — reintroduces a special-case control plane that must be secured and audited on its own,
exactly the special-casing that becomes the hole; rejected in favor of reusing the one hardened gate. *(c) Govern
**all** services uniformly, including the trust root* — invites the circular-compromise class (config for the
store read through the store); rejected via the trust-root exemption.

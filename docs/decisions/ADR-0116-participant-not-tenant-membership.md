# ADR-0116 — Participant ≠ Tenant: network membership as a tenant-free contract

- Status: Accepted (Slice 1 implemented)
- Date: 2026-10-30
- Related: ADR-0115 (installer & three-realm bootstrap), ADR-0067 (service directory + federation),
  ADR-0058 (interaction contracts / interfaces), ADR-0084 (local OS federated participant), ADR-0039
  (federated identity), ADR-0096 (platform operator model), ADR-0103 (per-object sharing + consent)

## Context

When an agency installs AirawatOS it gets four realms (operator / network / data tenant / developer). The
intended ecosystem is: a tenant (say a municipality) can **connect to one or more networks** — Health, Labour,
Water — by *applying to become a participant*; the network (itself a tenant carrying `network.admin`) decides;
once approved the participant can **provide** services to the network's members and/or **consume** the network's
services for its own users.

The existing join flow (`POST /v1/join/decide`) conflates three things into one act: on approve it **provisions
a tenant**, a Vault-backed steward, and a tenant-admin login. That bundling is wrong for the ecosystem model:

- A municipality that already installed AirawatOS **already has a tenant** — joining Health/Labour/Water must
  not mint new ones.
- A vendor or external system that only wants to **provide** a service into a network needs **no tenant at
  all** — it brings its own backend via the SDK + governed gateway.
- A consumer org that only wants to **use** network services for its users needs **no tenant** either.
- A solo municipality can hold a tenant with **no** memberships.

All four are first-class, and none of them is expressible when "join" means "get a tenant."

## Decision

Separate three orthogonal layers. **Membership never implies a tenant.**

1. **Identity** — *who you are.* A principal/issuer the network can authenticate (a reference-IdP account, or
   your own JWKS via the ADR-0084 trust map). Exists independent of any network or tenant. The `PARTICIPANTS`
   directory (`/v1/participants`) already models this: a signed directory entry keyed by `participant_id`, with
   `jurisdiction`/`kind` and published keys — **no tenant**.

2. **Participation (membership)** — *a contract with a network.* A first-class, tenant-free edge between a
   participant and a network: a recognized relationship + trust + a scoped capability grant to **provide**
   and/or **consume**. This is the new primitive, `network.participation`.

3. **Tenant** — *a data workspace on an operator.* **Optional.** Where governed data lives and apps run, if a
   party needs the network (or its own install) to host data for it. A participant may own **zero, one, or
   many** tenants; a tenant belongs to exactly one participant.

Consequences that follow:

- **Membership is the primitive, keyed on (participant, network)** — independent of tenancy. A participant can
  hold many memberships across many networks; a network has many members.
- **Tenant provisioning is a separate, optional capability.** The old `join/decide` provisioning path is NOT
  deleted — it is demoted to "a participant may *also* ask this network's operator to host a tenant for it,"
  invoked explicitly, never as a side effect of membership.
- **A tenant-free participant touches storage never.** It interacts with the network **only** through governed
  service interfaces / the gateway (ADR-0067, ADR-0058) — it never reads or writes the registry directly. The
  kernel's `(sub, tenant)` scoping therefore does not need a tenant for such a participant; the tenant spine
  and the participation spine meet only when a participant *also* owns a tenant on this install.
- **Trust is participant-level, not tenant-level.** Binding an issuer to a tenant (ADR-0084 trust map) becomes
  optional; a participation can establish trust without any tenant.
- **The installer is re-read honestly:** `<instance>-network` is *a participant that happens to run a network
  and host some tenants* — not a bundle.

### The `network.participation` record

```
{ schema: "network.participation",
  id:          "ds:<network>:participation/<participant-slug>",
  network:     "<network participant/tenant id>",     // the network being joined (a tenant w/ network.admin)
  participant: "<participant id>",                     // may be a tenant id, a participant_id, or an issuer DN
  direction:   "provide" | "consume" | "both",
  scopes:      [ ... ],                                // domains / services / interfaces in scope (what flows)
  status:      "pending" | "approved" | "rejected" | "revoked",
  requested_by, requested_at, decided_by, decided_at, reason, note }
```

Scoped, not binary: a membership says *what* each side may provide/consume, and consent (ADR-0103) governs the
data that actually flows.

### Lifecycle (tenant-free)

```
Tenant/participant admin (Settings → "Networks")        Network admin (a tenant w/ network.admin)
  browse network directory                                ▸ request lands in Network Admin / Inbox
  "Apply to Water network"  ──participation.request──────▶ approve / reject (with scopes)
                                                           │
   network.participation { ..., status: approved } ◀───────┘
                                                           │
  once approved, BIDIRECTIONAL (no tenant required):
    • provide → publish a service offering INTO the network (ADR-0067); members consume it
    • consume → use the network's services and surface them to its own users
```

Authorization for the decision is gated to **the network's own admin** (`network.admin`/`network.steward` of
the network-tenant), *not* the hardcoded `airawat` standards body — this is also the first concrete step of
parameterizing network authority away from the literal `airawat` (the gap noted in ADR-0115).

## Slice 1 (this change)

Backend primitive + tenant-free lifecycle, proven on the local stack:

1. Govern `network.participation` in the base catalogue (`network` domain).
2. `POST /v1/participation/request` — any authenticated principal applies on behalf of a participant to a
   network. Writes a `pending` record. **Provisions nothing.**
3. `POST /v1/participation/decide` — the **network's own** admin approves/rejects (gated to the network tenant,
   not `airawat`). Updates status. **Provisions no tenant.**
4. `GET /v1/participation?participant=…|network=…` — list memberships from either side.

Proven invariant: a participant gains an approved membership in a network and **`TENANTS` is unchanged** — no
tenant is created by participating.

## Later slices (not in this change)

- Settings "Networks" tab (apply + status) and Network-Admin decision surface in the Inbox.
- A **network directory** so participants can discover networks to apply to.
- Trust establishment on approval (issuer ↔ network) for cross-install membership.
- Scope/consent enforcement on the provide/consume paths; metering of cross-network service use.
- Fully parameterize `AUTHORITY_TENANT` across the remaining network governance endpoints (ADR-0115 gap).

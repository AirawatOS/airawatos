# ADR-0129 — Every organisation can spawn networks; vendors and partners are participants

**Status:** Proposed · **Date:** 2026-11-06
**Builds on:** ADR-0116 (participant ≠ tenant), ADR-0122 (recorded roles, SoD), ADR-0124 (service
identities), ADR-0127 (one authority model, two-key rule), ADR-0128 (Networks are federated).
**Affects:** PLATFORM (PLT-1, PLT-10, PLT-16–PLT-21), NETWORK (NET-2, NET-3, NET-5, NET-12), PARTICIPANT
(PTC-1, PTC-11), OFFERINGS (OFF-3, OFF-8), COMPONENT (CMP-1), FOUNDATIONS (FND-3, FND-4).

---

## Context

Every organisation works with others: a municipal corporation has road contractors, system integrators,
NGOs, SMS and AI providers; a water board has equipment suppliers and maintenance firms. Today these
relationships are usually handled badly — shared accounts, vendor staff given logins inside the
organisation's own system, data emailed around — with no explicit permissions and no evidence trail.

Airawat already has the right building blocks for this: Networks, participants with their own identity,
explicit grants, the two-key rule for personal data, offerings with terms and settlement, and decision
records. What it lacks is a decision that **an organisation's own vendor and partner relationships are a
Network**, and that every organisation can have one without effort.

Two related questions are also open:
- **Installer step "local Network".** The installer currently mints a Network on every installation,
  contradicting PLT-1 (a fresh install creates no Networks) and ADR-0128 (Networks are created by tenants).
- **Provider catalog.** PLT-16–PLT-21 describe a separate catalog of approved providers (SMS, AI, payments,
  identity proofing) behind capability gateways — a vendor relationship modelled with its own machinery.

## Decision

1. **Every organisation (tenant) can spawn networks.** A tenant may govern any number of Networks — a partner
   network for its vendors, a network with neighbourhood associations, a data-sharing network with research
   partners — each with its own members and rules. The tenant is the **governing tenant** (hub) of the
   networks it spawns, and may be a member of networks others have spawned.

2. **The organisation and its network remain two distinct things** (FND-4). The tenant is the organisation's
   inside: its staff, internal data and apps. A network is the organisation's dealings with others. They have
   different identifiers, different names (a network never reuses the tenant's slug), and different
   governance: the tenant admin does not become a network's admin by virtue of being tenant admin — only by a
   recorded role assignment (FND-3).

3. **A partner network is available to every organisation, created on first use.** The first time an
   organisation invites a vendor or partner, a **partner network** is created for it in **draft**, with the
   inviting person (or the tenant admin) recorded explicitly as its network admin. No network is pre-created
   at install or at tenant approval.

4. **Vendors and partners are participants.** Each has its own participant identity, keys and role(s)
   (e.g. service provider, data processor, contractor), passes the conformance checks for its role before
   activation (PTC-11), and receives only explicit grants. Vendor staff authenticate through their own
   organisation's login system (scoped external issuer, FND-15) — never through accounts created inside the
   hosting organisation. Vendors may join from any mode (hosted, own AirawatOS installation, own system +
   Participant SDK — ADR-0128).

5. **Partner-network defaults reflect an asymmetric relationship.** The governing organisation sets the rules.
   By default, members see only what they are granted, and the member list is visible to the governing
   organisation, not to other vendors, unless the network admin chooses otherwise (NET-12).

6. **Tenants choose their providers; the platform sets only infrastructure policy.** A provider (SMS, AI,
   payments, identity proofing, …) is **any participant** — a tenant on any installation, or an organisation
   using the Participant SDK — that passes the **provider-role conformance checks** (PTC-11). A tenant uses a
   provider by **explicitly admitting it into its own partner network** (a tenant-admin decision). There is
   **no platform-approved provider catalog and no platform approval or veto** of a tenant's choice.
   - **Platform role, narrowed:** where a tenant's provider calls run through a **shared installation's**
     capability gateways (PLT-16), the platform may set **infrastructure policy** for its own servers — for
     example data residency ("personal data may not go to providers outside India") and an outbound security
     baseline — stated once as policy, applied equally, never as per-provider approval. A tenant on its own
     installation sets these for itself.
   - **Network minimums still apply** when a provider serves a network's members (e.g. "AI hosted in India",
     "proofing at assurance level AL2") — PLT-19.
   - **Convenience defaults allowed:** an installation may offer pre-configured default providers for tenants
     that don't want to choose, but never exclusively.
   - The separate "provider catalog" concept (PLT-17 as written) is retired.

7. **Vendor contracts are offerings.** What a vendor provides is an offering with terms (price, service
   levels, data use, licence), commitments, fulfilment evidence and settlement (OFF-3, OFF-8). Personal data
   handled by a vendor follows the two-key rule, and the vendor is recorded as a data processor.

8. **The installer creates no Network by default** (PLT-1). The current "local Network" step becomes
   dev-profile only, or an explicit opt-in.

9. **Trust does not extend to a participant's own network unless the network's policy says so — default
   "no".** A vendor's subcontractors belong to the **vendor's** partner network, not to the hiring
   organisation's. Whether a member may extend access it holds to members of **its own** network is a
   **network policy**, set by the network admin, and **off by default**. Where enabled:
   - **Never more:** an extended permission can only be a subset of what the member itself holds
     (attenuation), never wider, never longer-lived.
   - **Explicit and recorded:** each extension is a recorded grant naming the sponsoring member, the
     sub-participant, scope and expiry; decision records show the whole chain.
   - **Revocable in cascade:** revoking the member's grant, or the member leaving, revokes every extension
     made through it.
   - **Bounded depth:** the policy sets how many hops are allowed (default when enabled: one).
   - **Personal data:** a sub-participant handling personal data is recorded as a **sub-processor**; the
     two-key rule still applies; and the policy may require the governing organisation's explicit approval for
     each sub-processor.

```text
  MUNICIPAL CORP PARTNER NETWORK            ROADCO PARTNER NETWORK (RoadCo's own)
  +-----------------------------+           +-----------------------------+
  | RoadCo (contractor)  -------+-- hub of->| TarMix (subcontractor)      |
  |   holds grant: read         |           | SurveyCo (subcontractor)    |
  |   ward road-works data      |           +-----------------------------+
  +-----------------------------+
   network policy "extend trust to members' networks":
     default NO  -> TarMix sees nothing of Municipal Corp's data
     if YES      -> RoadCo may pass on a SUBSET of its grant, recorded,
                    expiring, revoked if RoadCo's grant is revoked; depth-limited
```

```text
  ONE AIRAWATOS INSTALLATION
  +------------------------------------------------------------------+
  |  TENANT: Municipal Corp  --governs-->  NETWORK: Municipal Corp   |
  |  (inside: staff, data,                 Partners (contractors,    |
  |   apps)                                integrators, NGOs,        |
  |                                        providers - participants) |
  |        \--member of-->  NETWORK: Metro Urban Network (hosted     |
  |                         by the Urban Dept, possibly elsewhere)   |
  |                                                                  |
  |  Municipal Corp Partners also admits its chosen PROVIDERS        |
  |  (SMS, AI, payments, proofing) - any participant passing the     |
  |  provider-role checks, on any installation                       |
  |  PLATFORM sets only infrastructure policy for shared gateways    |
  +------------------------------------------------------------------+
```

### Note — how providers are found and used

A provider **registers once** as a participant (identity, keys, provider role) and passes the provider-role
checks. It then **publishes offerings** (terms: price, service levels, data use, residency) in the networks it
chooses to belong to — visible to their members, or public (NET-12). A tenant then uses it in one of two ways:

```text
  1 PROVIDER REGISTERS        2 PUBLISHES OFFERINGS            3 TENANT USES IT
  participant identity,       in networks it belongs to,       A) inside a SHARED network both
  provider role, checks       e.g. a regional services            belong to - that network's grant
  passed                      marketplace network                 steward issues call + provide
                              (members, or public)             B) admitted into the tenant's OWN
                                                                  partner network - the tenant
                                                                  governs grants and terms
```

- **Path A — within a shared network:** suited to common, standardised services used across a region; the
  shared network's rules and grant steward govern the relationship.
- **Path B — admitted into the tenant's own partner network:** suited to organisation-specific relationships
  (contracts); the tenant governs grants, terms and personal-data decisions.
- Both paths follow the same rules: explicit grants, the two-key rule for personal data, decision records.
- **Discovery across networks** a tenant does not belong to requires the directory of Networks / root of trust
  deferred in FEDERATION (FED8). Until then, discovery is limited to networks the tenant is a member of, plus
  public offerings.

## Consequences

**Positive**
- Matches how organisations actually work; vendor access becomes explicit, revocable and evidenced, replacing
  shared accounts and vendor logins inside the organisation.
- **One model instead of two:** providers stop being a special catalog and become participants; PLT-16–PLT-21
  can be restated in network terms and shortened.
- "Networks of networks" — the connected economy — emerges from one repeated pattern: every organisation is a
  node in others' networks and a hub of its own.
- Data-processor obligations (DPDP) attach naturally to the participant relationship.
- Resolves the installer's default-network question without pre-creating empty networks.

**Negative / risks**
- **Re-introducing tenant = network.** A one-to-one default pairing invites that assumption back.
  Mitigated by distinct IDs and names, explicit recorded admin roles, and conformance cases that fail if any
  authorization compares a tenant with a network.
- **Network proliferation.** Many organisations, each with partner networks. Mitigated by creation on first
  use and the invisible draft state.
- **Asymmetric defaults need care.** Vendors must not see each other or the organisation's internals by
  default; these defaults must be explicit, testable rules.
- **Migration.** Existing provider configuration (operator-wired providers, tenant Vault credentials) must be
  re-expressed as participant admission + grants.

## Alternatives considered

- **Tenant *is* its network** (one object). Rejected: outsiders would join the organisation's inside; an
  organisation could have only one network; tenant admin and network governance would be fused — the
  conflation FND-4 forbids.
- **Keep a separate provider catalog** (PLT-17 as written). Rejected: duplicates the participant/grant/
  conformance model with its own machinery.
- **Create a partner network for every tenant at approval.** Rejected in favour of on-first-use: avoids
  thousands of empty networks; behaviour for the organisation is the same.
- **Installer mints a default Network.** Rejected: contradicts PLT-1 and ADR-0128.

## Open questions

1. **Naming.** Default display name for a partner network ("<Organisation> Partners"?) and how organisations
   rename or split it later.
2. ~~Vendor-of-vendor chains~~ — **resolved (Decision 9):** subcontractors belong to the vendor's own
   network; extending trust to a member's network is a network policy, default "no".
3. **Vendor role catalogue.** The initial set of vendor roles (service provider, data processor, contractor,
   system integrator) and the conformance checks for each.
4. ~~Provider choice for tenants~~ — **resolved (Decision 6):** tenants choose any participant passing the
   provider-role checks and admit it explicitly; no platform approval; the platform sets only infrastructure
   policy for shared gateways.
5. **Billing.** Whether provider usage charged to a tenant settles through the tenant's partner network
   offerings, the platform's, or both.

## Spec changes if accepted

| Spec | Change |
|---|---|
| PLATFORM | PLT-1 (no Network at install — reinforce); PLT-16–PLT-21 restated: providers are any participants passing provider-role conformance; a tenant admits its chosen provider into its own partner network; PLT-17 shrinks to "the platform sets infrastructure policy (residency, outbound security baseline) for its shared gateways" — no catalog, no approval |
| NETWORK | NET-2 partner network created on first use, in draft, explicit admin; NET-3 tenant admin ≠ network admin unless recorded; NET-12 partner-network visibility defaults; new rule: trust extension to members' networks is a network policy, default off — attenuated, recorded, cascade-revoked, depth-bounded, sub-processors recorded |
| PARTICIPANT | PTC-1 vendors as participants; PTC-11 vendor role conformance (service provider, processor, contractor, integrator) |
| OFFERINGS | vendor contracts as offerings; processor recording for personal data |
| FOUNDATIONS | FND-4: add the partner-network case as an explicit example of tenant ≠ network |
| Installer | local-Network mint → dev profile / opt-in only |

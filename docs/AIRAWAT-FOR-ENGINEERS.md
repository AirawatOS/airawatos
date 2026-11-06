# Airawat for engineers

**Draft v0.1 · November 2026.** The technical companion to [Airawat in plain words](PRIMER.md). Read the
primer first; this document maps its plain-language ideas onto the system's actual parts.
Definitions: [Glossary](specs/GLOSSARY.md). Normative rules: [Specifications](specs/README.md).

---

## 1. Plain words → system terms

| Primer says | System term | Where it's specified |
|---|---|---|
| shared register | **Kernel** (registry + broker) | REGISTRY |
| login pass | **token** (identity only: iss, sub, tenant, aud, exp) | FOUNDATIONS F1 |
| data-sharing permission | **CapabilityGrant** | NETWORK N9, ADR-0127 |
| authorised officer | **RoleAssignment** (platform / tenant / network scope) | FOUNDATIONS §3, ADR-0122 |
| your permission | **Consent** | ACCOUNT A7, ADR-0125 |
| the two permissions | **two-key rule** (grant + consent for personal data) | FOUNDATIONS §3 |
| reasons on file | **decision record** | DECISION |
| tamper-proof log | **audit chain** (hash-chained, signed) | REGISTRY R12 |
| your agency's space | **tenant** | PLATFORM |
| shared space for agencies | **Network** (e.g. Urban Network) | NETWORK |
| account address (`meera@metro`) | **account handle** | ACCOUNT A2 |
| document locker | **wallet** | ACCOUNT A6, W1–W4 |
| tools and models | **components**: drivers, connectors, engines, apps | COMPONENT |
| approved AI providers | **capability gateway** + provider catalog | PLATFORM P16–P21 |
| self-declared | **self-asserted fact** (wallet-signed, labelled) | POLICY PL2 |
| challenge a decision | **contest** | DECISION D11 |
| budget for relief | **funding envelope** | OFFERINGS O6 |
| payment system | **payment rail** (records only; money moves on rails) | OFFERINGS O8 |

---

## 2. The layers

Every request passes through these layers. Each verifies for itself; none trusts that "upstream already
checked".

```text
 INTERNET
   |   security group: 80/443 only
 +----------------------------------------------------------------+
 | PERIMETER      TLS edge -> nginx (App Host, public pages only)  |
 +----------------------------------------------------------------+
 | APPS / DOORS   resident apps, agency portals, dashboards        |
 |                (Client SDK); App Host = messenger + sessions     |
 +----------------------------------------------------------------+
 | IDENTITY       login -> token (identity only); audience-bound;  |
 |                external issuers scoped to their own tenant      |
 +----------------------------------------------------------------+
 | DECISION       identity + RECORDED roles / grants / consent     |
 |                -> allow/deny + decision record; fails closed    |
 +----------------------------------------------------------------+
 | GOVERNANCE     Platform (tenants, policy, providers) · Network  |
 |                (members, grants, marketplace) · Offerings ·     |
 |                Policy                                           |
 +----------------------------------------------------------------+
 | SERVICES       capability gateways (notify, model, payment,     |
 |                proofing); scheduler, automation; every internal |
 |                endpoint requires an audience-bound service token|
 +----------------------------------------------------------------+
 | KERNEL         registry (versions, signatures, provenance,      |
 |                bitemporal history) + broker (component access); |
 |                the only door to facts and files; domain-blind   |
 +----------------------------------------------------------------+
 | STORAGE        Postgres (least-privilege role per service),     |
 |                blob storage (Kernel-only), Vault (secrets, keys)|
 +----------------------------------------------------------------+
```

---

## 3. One request, traced

The Disaster Authority's flood-risk engine reads the Neighbouring Municipality's drain levels:

```text
 engine (component)
   | run token = manifest declaration ∩ runner's authority
   v
 Kernel broker
   | verify run token
   | look up CapabilityGrant: Disaster Authority may READ drains.reading
   |   from Neighbouring Municipality in this Network? recorded via the
   |   governance path (provenance), live, in scope?
   v
 allow -> records returned; access recorded (decision record / aggregate per D10)
 deny  -> refused; refusal recorded
   |
   v
 engine output written as a new record, with provenance:
   inputs (pinned versions), model id + version, who ran it
```

An administrative action follows the same pattern through the Network service: App Host forwards the user's
token → Network service verifies it and checks the recorded role → writes via its own service identity,
noting who it acts for → Kernel verifies, stores the signed version, appends to the audit chain.

---

## 4. Components

- **Kinds:** drivers (ingest from sensors/systems), connectors (outside services), engines (analysis),
  apps (presentation), skills.
- **Manifest:** declares reads, writes, files, egress hosts, named secrets, required capabilities,
  resources. A component never exceeds it.
- **Run token:** declaration ∩ the authority of whoever ran or scheduled it.
- **Isolation:** no network unless declared; quotas; no platform credentials; secrets delivered by name.
- **Private lane:** build and run inside your own tenant with the right role; no certification.
- **Sharing:** always via certification; installing admin consents to declared access; marketplace listing
  needs the Network's contribute grant and listing checks.

---

## 5. Keys and secrets

| Key / secret | Purpose | Where |
|---|---|---|
| Identity issuer key | signs tokens | Vault transit |
| Kernel signing key | signs record versions | Vault transit |
| Audit key | signs the audit chain | Vault |
| Participant keys | sign credentials and messages | per participant |
| Service principal passwords | mint short-lived service tokens | Vault (kv) |
| Database role passwords | least-privilege DB access per service | Vault (kv) |
| Run tokens | component credentials | issued once; to be stored as hashes only |

Target for "secret zero": Vault unlocked by the server's cloud identity, never a stored root token.

---

## 6. Where to go next

- Rules: [Specifications index](specs/README.md)
- Gaps between rules and code: `docs/consolidation/DEBT-REGISTER.md`
- Tests: `docs/conformance/PLAN.md`
- Running it: `docs/operator/OPERATOR-GUIDE.md`, `docs/operator/INSTALLER.md`

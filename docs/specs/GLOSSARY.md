# Airawat Glossary

**Status:** Draft v0.1 · **Date:** 2026-11-06
**Purpose:** plain-language definitions of the terms used across the Airawat specifications, primer and
operator documents. Grouped by theme so related ideas sit together. Internal file names, ADR numbers and
task numbers are deliberately left out — those belong in the specs' references.

---

## 1. Who is acting

- **Principal** — anything that acts: a person, a program, or an AI agent. Every principal has its own
  identity.
- **Service principal** — a principal that is a program rather than a person (for example the scheduler). It
  has its own account and its password lives in the vault, so its actions are recorded as its own. Think of
  it as an ID badge for a machine.
- **Identity** — who a principal is (for example `user://localdev-network/admin`). Identity answers *who*,
  never *what they may do*.
- **Token** — a short-lived pass proving identity, issued at login. It says who you are, which organisation
  you belong to, who vouched for you, which service it is for, and when it expires. **It carries no
  permissions.**
- **Issuer** — the service that vouches for an identity by signing tokens.
  - **Home issuer** — the platform's own identity service; the only issuer trusted for platform-level
    actions.
  - **External issuer** — an outside login system (for example a tenant's own single sign-on), trusted only
    to vouch for its own organisation's users.
- **Audience** — the service a token is addressed to. A token addressed to the scheduler is refused by the
  file store, so a stolen pass cannot be reused elsewhere.
- **Realm** — a login namespace: a place where a group of accounts log in. A realm is not an organisation
  and grants nothing.
- **Assurance** — how strongly someone's identity has been proven (for example "verified through eShram").
  A signal policies can use, not a permission.
- **Identity binding** — the link between an account and a proven real-world identity, kept so that the raw
  identifier (such as an Aadhaar number) is never exposed or used as an ID.

## 2. What they may do

- **Authority** — the right to perform an action. It exists only if a recorded permission covers it at the
  moment of the request.
- **Recorded permission (grant)** — a written record, stored in the Kernel, that gives someone authority.
  Three kinds:
  - **Role assignment** — who may govern. Example: "Asha is network admin of the Livelihood Network".
    Scoped to the platform, a tenant, or a Network.
  - **Capability grant** — what a member or program may do. Examples: "the training provider may provide
    the `training.enrol` service"; "the insurer may read work-history records".
  - **Consent** — what a person has allowed. Example: "Ravi allows this insurer to read his work history
    for six months, for insurance".
- **Two-key rule** — access to a specific person's data needs **both** a capability grant (the organisation
  may read this kind of data) **and** that person's consent. Non-personal data needs only the grant.
- **Scope** — what a permission covers: which platform, tenant, Network, service or data, and for how long.
- **Nothing implied** — belonging to a tenant, being a Network member, having a classification, or having
  your login system approved never grants authority by itself.
- **Decision point (decision function)** — the single place every request is judged: identity plus recorded
  permissions plus current context, giving allow or deny.
- **Fail closed** — if anything needed for a decision is missing or unreachable, the answer is no.
- **Delegation (acting on behalf)** — a recorded permission for one principal (a family member, an operator,
  an AI agent) to act for another, with limits and an expiry. Records show both who acted and for whom.
- **Separation of duties** — sensitive permissions need a second person's approval, so no one person can
  quietly give themselves or an accomplice power.
- **Last-holder floor** — the last holder of a key role (platform authority, tenant admin) cannot be
  removed, so the system can never lock itself out.
- **Break-glass recovery** — the emergency path if every platform authority holder is lost: a recovery key
  split among several named custodians, usable only by a quorum of them, and permanently recorded.
- **Access grant** — the Kernel's internal enforcement record, derived from grants and consent. Not a
  separate kind of permission.

## 3. Organisations and ecosystems

- **Platform** — one installation of Airawat, with its own keys.
- **Operator** — whoever runs the servers. Infrastructure power, but no governance authority.
- **Platform tenant** — the single organisation the installer creates as a home for the platform's own
  people and programs. Being in it grants nothing.
- **Platform authority** — the recorded role of the people who govern the installation: which
  organisations may join, which providers are approved, whether tenants may create Networks.
- **Tenant** — an organisation's workspace (a city, a department, a company). It owns data and users. A
  tenant is not a Network.
- **Verification status** — whether a tenant's identity as an organisation has been checked: **verified**
  or **unverified**. Unverified tenants exist only if self-signup is allowed, and they have limits.
- **Tenant steward** — a platform-level role that reviews applications from organisations wanting to join.
- **Network** — a governed ecosystem that organisations join to exchange services and data (for example a
  Livelihood Network). It has its own permanent ID and its own governance, separate from any tenant.
- **Slug** — a readable label for a Network (for example `livelihood`). A nickname, not the ID, and never a
  source of authority.
- **Membership** — belonging to a Network. It gives belonging only; what a member may do comes from grants.
- **Participant** — a member organisation acting in a Network: offering services, issuing credentials,
  exchanging data. *(Open point: older documents treat participants as independent of tenants; the Network
  spec treats members as existing tenants. To be settled — see NETWORK NET-5.)*
- **Network roles:**
  - **Network admin** — runs the Network.
  - **Membership steward** — approves members.
  - **Capability steward** — maintains the list of possible services.
  - **Grant steward** — issues grants.
- **Capability catalog** — a Network's list of the services and data capabilities that may exist in it.
- **Classification** — a descriptive label on a member ("insurer", "training provider"). It describes; it
  never authorises.
- **Draft Network** — a newly created Network, invisible and not accepting members, until its admin has set
  it up and published it.
- **ChangeRequest** — a recorded proposal for a sensitive change. It is approved by an authorised person
  (often a second one), then carried out exactly as approved, once.
- **Governing tenant** — the organisation recorded as responsible for running a Network.

## 4. Records and the Kernel

- **Kernel** — the core record store. Every fact and every file goes through it, and every read and write is
  checked there. It knows nothing about domains like workers or cities — only records.
- **Registry** — the Kernel's store of records.
- **Record** — one fact stored in the registry, with a permanent ID and a schema.
- **Schema** — the shape a record must have. Schemas are themselves records, owned by the platform, a
  tenant, or a Network.
- **Version** — records are never edited. Every change adds a new version; old versions stay readable.
- **Supersede / retract** — a correction supersedes the previous version; a withdrawal retracts it. Both add
  history; neither erases it.
- **Bitemporal** — every record knows two times: when the fact was true in the world, and when the system
  learned it. You can ask both "what was true on 1 March?" and "what did we believe on 1 March?"
- **Provenance** — where a record came from: who wrote it, under which permission, from what sources.
- **Signature** — each version is signed by the Kernel (and by the writing participant where it has keys),
  so tampering is detectable.
- **Domain-blind** — the Kernel stays generic. Domain meaning lives in schemas and components, never in the
  Kernel's code.
- **Fact vs private working state**
  - **Facts** — anything others rely on. They live in the Kernel.
  - **Private working state** — sessions, counters, caches that belong only to one service. They live in
    that service's own store and are never read by another.
- **Files are records** — a file is a record (owner, schema, fingerprint, size, sensitivity) plus bytes in
  storage only the Kernel can reach.
- **Public schema** — a schema formally designated public, so its records can be read without permission
  (for example air-quality readings). Changing that designation needs a ChangeRequest.
- **Archiving** — moving old versions to cheaper storage without changing any answer the system gives.
- **Idempotent** — repeating the same action changes nothing the second time: no new version, no new audit
  entry.

## 5. Privacy and protection

- **Personal data** — data about an identifiable person. Stored separately so it can be truly erased.
- **Erasure** — real deletion of personal data when required by law or on withdrawal of consent, with the
  erasure itself recorded. History remains, but without the personal content.
- **Field encryption** — sensitive fields encrypted as they are written, through the vault, so they are
  never stored readable.
- **Blind index** — a keyed fingerprint of an encrypted value that lets the system find an exact match (for
  example "is this eShram number already linked to an account?") without ever storing the value readably.
- **Redacted** — what an unauthorised reader sees instead of a protected value: a placeholder, never the
  value or its encryption.

## 6. Evidence

- **Decision record** — the evidence of why something was allowed or denied: who asked, which policy
  version, which facts, each rule's result, the outcome, and who decided.
- **Audit chain** — a tamper-evident history of changes to permissions and trust. Each entry includes a
  fingerprint of the one before it, so altering any entry breaks the chain.
- **Audit verifier** — the tool that checks the chain is unbroken. Run regularly.
- **Contest** — a recorded challenge to a decision, reviewed by someone other than the original decider. The
  result is a new decision; the original is never edited.
- **Self-asserted fact** — something a person states about themselves (for example their income). Accepted
  only where a policy allows it, signed with their wallet key, and labelled as self-asserted in every
  decision that uses it.

## 7. Exchange: offerings, policies, components

- **Offering** — what a participant offers in a Network. Three kinds:
  - **Service** — something done on request (enrolment in training).
  - **Benefit** — an entitlement granted to the eligible (a subsidy).
  - **Information** — access to data (a verified work history).
- **Terms** — what an offering promises: price, who pays or funds it, refunds, service levels, data use,
  licence.
- **Funding envelope** — a funder's recorded budget for a benefit: amount, scheme, rules, period. Every
  approval draws it down and cannot exceed it.
- **Commitment / fulfilment / settlement** — the three records of a transaction: what was agreed, evidence
  it was delivered, and the payment matched to the payment rail's reference.
- **Payment rail** — the regulated system that actually moves money (UPI, bank transfers, treasury systems).
  Airawat records; rails move money.
- **Policy** — a governed rule, written as a readable tree of conditions rather than code, deciding things
  like eligibility or spending limits.
- **Component** — a program on the platform (driver, connector, engine, app, skill) plus a manifest
  declaring exactly what it may touch.
- **Manifest** — a component's declaration of the data it reads and writes, the files it uses, the outside
  hosts it may contact, the secrets it needs, and the capabilities it requires. It can never do more than
  this.
- **Run token** — the scoped credential a running component uses. It allows only the overlap of what its
  manifest declared and what the person running it may do.
- **Broker** — the Kernel's door for components. Every record and file a component touches passes through
  it.
- **Private lane** — building and running your own components in your own tenant, with no certification
  needed.
- **Certification** — the checks a component must pass before it can be used outside its tenant.
- **Solution** — a versioned bundle of components, schemas, apps and configuration, installed as one.
- **Marketplace** — a Network's catalog of certified components and solutions that members can install.
- **Capability gateway** — a platform service for one kind of outside capability (notifications, AI models,
  payments, identity proofing). It routes requests to whichever approved provider the tenant chose.
- **Provider** — an outside vendor behind a gateway (an SMS company, an AI model host).

## 8. People and their accounts

- **Account** — a person's own portable account in a Network, owned by them, not by any app or provider.
- **Handle** — a memorable address for an account (for example `ravi@livelihood`). Unique within its
  Network. An address, never a password.
- **Wallet** — where a person keeps their credentials and keys. Separate from the account, and replaceable.
- **Credential** — a signed statement by a participant about a person ("completed electrician training"). It
  can be checked by anyone and can be revoked.
- **Presentation** — showing a credential to a specific recipient for a specific purpose, bound so it cannot
  be replayed elsewhere.
- **Client** — an app through which a person reaches their account (for example a delivery partner app). A
  door, not an owner.
- **Consent Manager** — under India's data protection rules, a registered intermediary letting people give,
  review and withdraw consent across services. Airawat's consent records are designed so a deployment could
  become one, or work with one.

## 9. Running the system

- **Installer** — the single recipe that builds an Airawat installation, with **profiles**: production,
  rehearsal (a restored copy of production for practising releases), and dev (adds demo data).
- **Pre-flight checks** — what the installer verifies before changing anything: disk encryption, open
  ports, the vault's mode, a dedicated machine.
- **Vault** — where secrets and keys live. Keys never leave it; programs ask it to sign or encrypt.
- **Secret zero** — the first key needed to open the vault. The goal is that the server's cloud identity
  unlocks it, so no master key sits in a settings file.
- **Least-privilege database role** — each service connects to the database with its own account, able to
  touch only its own tables. No service is a superuser.
- **Migrator** — the database role used only by the installer to change table structures. Running services
  cannot change structures.
- **Shadow mode** — a new check that runs and records what it *would* decide, without enforcing it yet. Used
  to compare before switching over.
- **Canary** — releasing a change carefully, watching it, and keeping an immediate way back.
- **Conformance suite** — automated tests checking the running system against the specifications. Known
  problems are marked "expected to fail" and flip when fixed.
- **Debt register** — the list of temporary workarounds and known rule violations, each with the condition
  for removing it.

---

## Plain words used in the primer

The [primer](../PRIMER.md) uses everyday words for the governed concepts. The mapping:

| Plain word (primer) | Governed term | Where |
|---|---|---|
| shared register | **Kernel** (the governed registry) | REGISTRY |
| login pass | **token** (identity only: iss/sub/tenant/aud/exp) | FOUNDATIONS FND-1 |
| data-sharing permission | **capability grant** (`governance.capability_grant`) | FOUNDATIONS §3; NETWORK NET-9 |
| authorised officer | **role** (a `governance.role_assignment`) | FOUNDATIONS §3; ADR-0122 |
| your permission | **consent** (`governance.consent`, subject-granted) | FOUNDATIONS FND-13; ADR-0125 |
| reasons on file | **decision record** (`governance.decision`) | DECISION |
| tamper-proof log | **audit chain** (hash-chained audit) | FOUNDATIONS FND-12 |
| your agency's space | **tenant** (an owning organisation) | FOUNDATIONS §1 |
| shared space | **Network** (a federation/standards body) | NETWORK; FEDERATION |
| document locker | **wallet** (holds verifiable credentials) | ACCOUNT |
| account address | **handle** (a resolvable name for an account) | ACCOUNT; CLIENT |

## Operator vs governing tenant (Network host)

- **Operator** — whoever **runs the servers** of an installation (the host machine, Docker, Vault, the OS,
  backups, the perimeter). The operator holds **no governance authority**: running the infrastructure confers
  nothing over any tenant's data or any Network's decisions (FOUNDATIONS FND-2; PLATFORM "who does what"). Analogy:
  the web-hosting company.
- **Governing tenant / Network host** — the **tenant that created a Network** (held `network.creator`) and
  **governs** it: its registry, directory and grant/decision records for that Network live on its installation,
  and its `network.admin` runs the Network (ADR-0128, FEDERATION FED1/FED2). The host *governs the Network*; it
  does not necessarily *run the servers* (that is the operator). Analogy: the organisation that registered the
  domain and sets its rules. **These are distinct roles and may be different parties.**

## Federation terms

- **Participant registration** — the act of joining a Network by recording, in the **hosting** Network's
  registry, a participant ID + role(s) + public keys + conformance status (FEDERATION FED3; NETWORK NET-6). It is
  belonging, not capability, and the Network never creates the tenant/login/system behind it.
- **Participant ID** — the recorded identity of a member within a Network (tenant-free; ADR-0116). Service
  accounts that act for the member live under this ID (PARTICIPANT PTC-1).
- **Member modes** — the three ways a participant is realised (ADR-0128): (1) a tenant on the host's
  installation; (2) a tenant on another AirawatOS installation; (3) an own system via the Participant SDK.
- **Participant node** — a running system that acts as a participant in one or more Networks (a tenant's
  services, or an own system). Every installation runs participant nodes and may host Networks (PLATFORM).
- **Participant SDK** — the library an own system (mode 3) uses to implement the specs and act as a registered
  participant without being a tenant on an AirawatOS installation (ADR-0117; PARTICIPANT).

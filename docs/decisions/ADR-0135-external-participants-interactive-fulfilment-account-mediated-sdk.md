# ADR-0135 — External-system participants, interactive fulfilment, and the account-mediated SDK

**Status:** Proposed
**Date:** 2026-11-19
**Relates to:** [[ADR-0117]] (credential-and-services network), [[ADR-0118]]/[[ADR-0119]] (Trusted Network
Platform, four planes), [[ADR-0116]] (participant ≠ tenant), [[ADR-0128]] (networks are federated; joining =
registering as a participant), [[ADR-0129]] (participants, explicit grants), [[ADR-0127]] (one authority model,
two-key rule), [[ADR-0125]] (consent), [[ADR-0124]] (service identities), [[ADR-0112]] (participant embed SDK),
[[ADR-0049]] (verifiable credentials, wallet), DEBT-B182 (capability and grant model)

## Context

A ministry is setting up a livelihood network for workers. Its first configuration fixes four things:

- A **national worker registry** is a participant. It issues each worker's registry ID and provides identity
  verification (eKYC) through its existing Aadhaar integration. It is an **existing system**, run by another
  organisation, reachable only through its own APIs.
- A **worker account layer**, run by the ministry, holds each worker's account. The account is anchored on the
  registry ID.
- **Platform companies** are the first issuers. They start registry registration for their workers from their own
  apps and later issue work records.
- The **ministry governs** the network.

The registry's APIs are not a back-office interface. They replay the registry's own self-registration journey
step by step, and **the worker must be present**: image captchas, a mobile OTP and an Aadhaar OTP, each entered
in real time. The same shape recurs elsewhere — a document wallet asking for the holder's consent, a bank OTP,
a field form only the applicant can fill.

ADR-0117/0119 define the generic loop (discover → request → present → fulfil → receive) and ADR-0128 how a
participant joins. They do not yet say: (1) how a participant's **existing system** is connected without moving
onto the platform; (2) how a request is fulfilled when the **account holder must answer challenges mid-way**;
(3) how one SDK serves both **an app acting for an account holder** and **a participant's own backend**;
(4) what anchors the **account** and where the **wallet** lives. This ADR decides those four, generically: the
livelihood network is one configuration; an urban-services or health network is another.

## Decision

### 1. External-system participants are connected through certified connectors

A participant whose service runs in its own system is bound to the network by a **connector**: a certified
component that implements the network service contract on one side and the participant's existing API on the
other (ADR-0117 §2 "external" binding, made concrete).

- **Identity and authority.** The connector runs under the **participant's service identity** (ADR-0124), never
  under the requesting app's. Credentials it issues are signed with the **participant's** key. It holds the
  external system's secrets (subscription keys, encryption keys, salts) in the vault; they never reach an app,
  the SDK or a log.
- **Identifier mapping.** The connector keeps the mapping between network participant ids and the external
  system's own ids (e.g. a platform's id in the registry). A requester can act only for its **own** mapped id;
  the mapping is part of the participant's governed configuration, changed by the network governor.
- **Data minimisation.** The connector passes through what the external system needs and keeps only what the
  credential it issues requires. Regulated identifiers (an Aadhaar number) exist only for the duration of the
  call that needs them and are never stored — a salted hash is kept only where the external system itself uses
  one as the key.
- **Conformance.** A connector is activated only after it passes the conformance checks for the role it serves
  (ADR-0128), against a **mock of the external system** with the same steps and shapes. The mock is part of the
  connector's deliverable: it is how a network is demonstrated and tested before the real system grants access.
- **Change and revocation.** Where the external system offers callbacks or status queries, the connector uses
  them to revoke or update credentials it issued (a worker leaves a platform; a registration is deactivated).

### 2. Interactive fulfilment: a request may pause for the account holder

A request is a small state machine. Besides `accepted → in_progress → completed | failed`, fulfilment may enter
**`awaiting_input`** with a **challenge**, and resume when the account holder answers.

- **Challenge kinds are governed vocabulary**, not free-form UI: `consent` (what will happen, to whom, for what
  purpose — recorded as a `governance.consent`, ADR-0125), `otp` (a code sent to a channel the holder controls),
  `captcha` (an image to read), `form` (fields with a governed schema, possibly prefilled), `choice`,
  `external_redirect` (the holder completes a step on the provider's own page and returns). New kinds are added
  by the standards body.
- **Who sees what.** The requesting app renders the challenge and relays the answer; it never sees the
  connector's secrets, and the answer goes to the fulfilling participant, not to the app. The **outcome goes to
  the account holder** (their wallet). The requesting app learns the outcome only as far as the holder consents
  (by default: completed or failed).
- **Bounds.** Each challenge carries an expiry and a retry limit; the request fails cleanly when they run out.
  Every challenge issued and answered is part of the request's audit record.

### 3. One SDK, two modes

The Participant SDK (ADR-0112, ADR-0128 "own system" mode) exposes the same network verbs in two modes.

| Mode | Who calls | Authenticated as | Typical calls |
| --- | --- | --- | --- |
| **A — for an account holder** | an app in which the holder is signed in (a platform's app, a citizen portal, a service centre, a chat channel) | the holder (PKCE sign-in) + the app's registered client | `login`, `discover`, `request` → `respond` (challenges) → `status`, `wallet`, `present` |
| **B — participant to participant** | a participant's backend, no holder present | the participant's service identity, signed requests | `publishOffering`, `issue`, `verify`, `subscribe`, `status` |

- Every Mode-A action on a holder's data needs **both** the app's capability grant **and** the holder's consent
  (ADR-0127 two-key rule). Mode B needs the participant's capability grant only, unless it touches a person's
  data — then the person's consent is still required.
- What appears in an app is **configuration**: the network's offerings and the app client's allowed scope, not
  screens hard-coded per network.

### 4. The account and the wallet

- **Account anchor.** Each network names the identity participant whose identifier anchors an account (the
  worker registry's ID in the livelihood network; a state ID or a property-tax account in others). The account
  holds the link to that identifier, the holder's consents and the wallet.
- **Wallet providers.** The wallet is an interface (ADR-0117 §7): a network-hosted wallet by default, with
  **DigiLocker** (or another provider) configurable per network — credentials can be pushed to it and fetched
  from it with the holder's consent.

### 5. Participant registration

Joining follows ADR-0128 (participant id, roles, keys, conformance). This ADR adds the **registration portal**
the network operates: an organisation applies, submits evidence of who it is (organisation verification), names
the roles it seeks and its external ids (e.g. its platform id in the registry), registers its apps as clients
(origins, redirect URLs), and is activated by the network governor with **explicit capability grants** — which
credentials it may issue or verify, which offerings it may publish (DEBT-B182).

## Worked example (the livelihood network)

| Concern | Configuration |
| --- | --- |
| Identity participant | the worker registry (registry ID, eKYC) — connected by a connector (§1) |
| Account anchor | the registry ID |
| First issuers | platform companies, each mapped to its registry platform id |
| Offering "registry registration" | fulfilled by the connector; challenges: consent → captcha → mobile OTP → Aadhaar OTP → form (§2); outputs: *identity verified* and *registry registration* credentials, signed by the registry participant |
| Front doors | platform apps (Mode A); platform backends publish jobs and issue work records (Mode B) |
| Wallet | network-hosted; DigiLocker configurable |
| Governor | the ministry |

The **urban-services** network on the reference installation is the same pattern with different values:
departments as participants, the property record as one anchor, building permissions and orders as credentials.

## Consequences

- External systems join without migrating; their secrets and identifiers stay with their connector.
- A demo or a pilot can run end to end against a **mock** of the external system before access is granted; the
  same connector then switches to the real endpoint.
- The SDK gains a generic challenge loop (`request` → `respond` …). Apps must render the governed challenge kinds;
  an app that cannot render one (e.g. a captcha in a voice channel) falls back to `external_redirect`.
- Requests become longer-lived and stateful; fulfilment state, expiries and audit live with the request.
- Open, per external system, not per platform: whether partner server-to-server calls are permitted, how partner
  requests are authenticated, which ids each partner holds, and what may be retained. These are confirmed with the
  external system's owner before a connector goes to production; until then only the mock is used.

## Alternatives rejected

- **Copy the external registry's data into the network** — a second authoritative store, a new concentration of
  sensitive data, and a stale copy; rejected (ADR-0119: no second authoritative store).
- **Let each app integrate with the external system directly** — every app would hold the external system's
  secrets and repeat the integration; consent and audit would be per app.
- **A separate API per challenge type or per network** — breaks "one SDK for every network"; challenge kinds are
  governed vocabulary instead.
- **Ask the account holder to register on the external system first, outside any app** — keeps today's friction
  that the network exists to remove; kept only as the `external_redirect` fallback.

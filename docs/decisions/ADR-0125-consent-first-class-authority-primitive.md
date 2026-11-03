# ADR-0125 — Consent is a first-class authority primitive

**Status:** Accepted
**Date:** 2026-11-03
**Relates to:** [[FOUNDATIONS-v0.1]] F13 (and F1/F2/F10); [[ADR-0119]] (authority = a live grant);
[[ADR-0112]] (participant-embed, citizen auth); debt **B12** (embed scope not bound to the registered
client). Credentials/VC context: ADR-0049 (document wallet / VCs), ADR-0117 (credential & services network).

## Context
Cross-party data access — a recipient (an aggregator, an app, a service provider) using a **data subject's**
data for a stated purpose — is today authorized inconsistently. The embed flow records a `governance.consent`
at citizen login but **does not bind the requested scope to the registered client's capability**: the
consent is written `service:"*"` regardless of what the `platform.app_client` registered, so an app
registered for `profile` can obtain a `service:invoke` consent (debt **B12**, `app_host.py:1148,1555`). There
is no single, governed Consent primitive with a defined shape, a subject-grants model, revocation, and
evidence. The authority model (FOUNDATIONS §3) names three primitives; Consent is the third and is
under-specified.

## Decision
**Consent is a first-class authority primitive: a recorded `governance.consent` object, granted by the data
subject, that authorizes a specific recipient to use the subject's data for a specific purpose, scope, and
period — revocable, with evidence.** It participates in the one decision function (FOUNDATIONS §3) exactly
like RoleAssignment and CapabilityGrant: a cross-party data action is allowed **iff** a live Consent covers
it.

**Shape** (`governance.consent`):
- `subject` — the data subject (the citizen/person/org whose data is used); the **grantor**.
- `recipient` — who is authorized (an aggregator / app_client / service principal id).
- `purpose` — the stated reason the data may be used for (a governed purpose code, not free text).
- `scope` — what data / which service(s) / which schemas the consent covers (bounded; `*` is not a default).
- `period` — `valid_from`/`valid_to` (and/or a one-time flag); outside it the consent is inert.
- `status` — `active` | `revoked` (revoked is terminal; re-grant = a new consent id).
- `revocation` — who/when/why when revoked.
- `evidence` — how the subject's grant was captured (the auth event, a signed assertion / VC reference,
  a challenge, a timestamp) — so the consent is attributable and auditable.

**Rules:**
- **Granted by the subject** — only the verified data subject (`subject == claims.sub`) may create a Consent
  for their data; never an admin, never a recipient on the subject's behalf (F1/F2).
- **Scope is bound, not asserted** — the recorded scope/purpose is what is enforced; a recipient's requested
  scope must be ≤ the recipient's registered capability AND ≤ the subject's granted Consent. This closes
  B12: the consent's `scope`/`service` must match the client's registered scopes, and `service:"*"` is only
  valid if the client is actually registered for all services.
- **Decision** — a cross-party data access authorizes iff `authorize(...)` finds a live Consent with
  `subject == data owner`, `recipient == caller`, `purpose ∈ allowed`, `scope covers resource`, `status
  active`, within `period` (FOUNDATIONS §3). No Consent ⇒ deny (F8).
- **Revocation takes effect immediately** at the recorded-state layer (the next decision sees `revoked`),
  independent of any token lifetime.

## Open question (to resolve before implementation)
**Alignment with the DEPA consent artefact.** DEPA (Data Empowerment and Protection Architecture) defines a
standard consent artefact (purpose, data-fiduciary/consent-manager roles, data-items, frequency, data-life,
signature). This ADR's `governance.consent` should align field-for-field with the DEPA artefact where
AirawatOS operates in that ecosystem — purpose taxonomy, data-item scoping, consent-manager role, revocation
semantics, and the signed-artefact evidence format. **Open:** adopt DEPA's artefact as the on-the-wire
representation (with `governance.consent` as the governed record mirroring it), or define the native record
and map to DEPA at the boundary. Resolve with a DEPA-mapping sub-ADR before building the enforcement.

## Consequences
- Consent joins RoleAssignment + CapabilityGrant as the third authority primitive under one decision
  function (F2/F13); cross-party access stops relying on client-asserted scope (B12).
- Enforcement work (separate slices): bind embed `/authorize` scope to the registered client; write the
  Consent with the bound scope; gate `/embed/request` (and any cross-party read) on the live Consent;
  surface revocation. Pending the DEPA-mapping decision for the artefact shape.
- Evidence + revocation make consent auditable (F12) and subject-controlled (F1).

## Alternatives rejected
- *Treat consent as a CapabilityGrant to the recipient* — loses the subject-as-grantor semantics, the
  purpose/period/evidence fields, and subject-driven revocation; conflates delegated component authority with
  personal-data consent.
- *Keep the embed ad-hoc consent record* — leaves B12 open (client-asserted, unbound scope) and has no
  defined shape, revocation, or DEPA path.

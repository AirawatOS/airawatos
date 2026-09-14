# ADR-0086 — Operator certification & certified-hosting attestation

**Status:** Proposed
**Relates to:** ADR-0020 (OS/Network split — Network authority vs OS plane), ADR-0084 (local OS install as a federated
participant — issuer = the *tenant*, operator is replaceable plumbing), ADR-0074 (operator-configurable platform
services — runtimes/services as certified installable components), ADR-0079 (universal component delivery —
content-addressed source, digest-verified at install), ADR-0016 (Store / certification / signing), the north-star
principle *"runtimes-are-certified-components"* named in `docs/decisions/index.md`.

## Context

The federation trust model shipped in ADR-0084 anchors identity in the **tenant**: the Network verifies an incoming
token purely by the tenant's issuer signature (`iss = ds:<tenant>:identity`, alg allowlist, `aud`, `exp`). There is
**no operator in the verification path** — no mTLS, no origin check, no runtime attestation. This was deliberate: it
makes tenants **portable** across operators (the issuer key travels with the tenant; the operator is *"replaceable
plumbing"*), which is the sovereignty guarantee.

But it leaves a real gap, surfaced in practice: **"why register an operator if anyone can operate?"**

- An "operator" today is a **directory string** (`host_operator`) chosen on the Join page — mutable, DNS-like, and
  **not a gate**. `CERTIFICATES` covers components and schemas, **not operators or hosts**.
- The Network cannot verify that a live install is running **certified, unmodified runtimes**. A hand-modified local
  build can register an issuer (admin-gated) and operate indistinguishably from a hardened, certified operator.
- The intent *"runtimes are certified components, and tenants run on certified operators"* is **documented but
  unbuilt**. Runtime integrity is delivered **upstream only** (images built from certified source, digest-verified at
  install — ADR-0079); it is **not a property the Network can verify about a running operator**.

### One marketplace, two shelves (not two marketplaces)

A natural question: *"are there two marketplaces — runtimes for operators, components for tenants?"* No — and deliberately
so. Per ADR-0022 (everything-is-a-component) and ADR-0074 (*"the marketplace extends upward, not a second mechanism"*),
there is **one certify→publish→install spine and one Store**. It carries two **shelves**, keyed by component *kind* and
*install scope*, with two installer **audiences**:

| | **Runtime / platform shelf** | **Application shelf** |
|---|---|---|
| What | kernel, app-host, scheduler, runtime-manager, runtime profiles, storage/scheduler/egress rulesets | apps, engines, drivers, solutions, models |
| Certified? | Yes — same spine + signing | Yes — same spine + signing |
| Installed by | **operator** (platform/operator scope) | **tenant** (tenant scope) |
| Listed in | **the same Store**, differentiated by kind + scope | the same Store |

**Operator certification (this ADR) attests the operator's installed *runtime-kind* components against their certified
digests in that one Store** — the same records ADR-0079 already keeps for tenant components. No second marketplace is
introduced. (Practical state: the *leaf* platform services + runtime profiles are already marketplace-installable
components; the *base* OS-plane runtimes still ship as Docker images built from certified source — attestation is what
brings them under the same certified-digest check without a separate mechanism.)

There are therefore **two distinct guarantees on two axes**, and only one is built:

| Axis | Guarantee | Status |
|---|---|---|
| **Tenant sovereignty** | Trust the tenant's key; the operator is swappable; identity is portable. | **Built** (ADR-0084) |
| **Host / runtime integrity** | The operator proves it runs certified runtimes; hosting is bound to certified operators. | **Missing** (this ADR) |

The naïve "fix" — put the operator in the auth path and pin each tenant to one operator — would **break portability**.
So the two axes must be reconciled, not collapsed.

## Decision

Introduce **operator certification** as a first-class, *separate* axis from tenant identity, layered **on top of**
ADR-0084 without changing its issuer-anchored verification. Three parts:

1. **Operator identity + attestation.** An operator is a participant (`kind: "operator"`) with its **own signing key**
   (`ds:<operator>:operator/key`). To become *certified*, it submits an **attestation**: the set of runtime component
   **`component@version` + image digests** it runs, signed by its operator key. The Network checks each digest against
   the **certified** Store entry (ADR-0079 already records the certified source/image digest per component version).

2. **Operator certificate.** On a passing attestation, the Network issues an **operator certificate** (a `CERTIFICATES`
   entry, subject = the operator id) recording *which certified runtime set* was attested, an expiry, and the
   attestation digest. Certification is **renewable** and **revocable** — an operator that upgrades re-attests; a stale
   or failed attestation lapses. Attestation is **periodic** (heartbeat), not one-shot, so drift is caught.

3. **Certified-hosting binding — checked, but off the identity path.** `host_operator` becomes a **verified** binding,
   not a free string: a tenant may be provisioned/hosted only on an operator whose certificate is **currently valid**.
   The tenant's *token* is still verified by its own issuer key (ADR-0084 unchanged — **portability preserved**); what
   is added is a **policy check at the hosting/provisioning boundary and at sensitive Network operations** that the
   named `host_operator` is certified. Optionally (S3) the operator **co-signs** or attests origin for the tenants it
   hosts, so the Network can bind "this tenant token *arrived via* a certified operator" — closing the origin gap
   without tying the tenant's *identity* to the operator.

### Why this preserves portability

Tenant identity (`iss`, key) is untouched and still travels operator-to-operator. Certification constrains **the host**,
not **the name**. Moving a tenant to another operator just requires the destination operator to be certified and the
`host_operator` binding re-pointed — the citizens' identities and signed data stay valid, exactly as ADR-0084 promises.
The operator is still replaceable; it just has to be a *certified* replacement.

```
ADR-0084 (unchanged):  tenant token ──signature(iss key)──► Network verify  ✔ portable

ADR-0086 (added, separate axis):
  operator ──attest {component@ver + image digest}, signed by operator key──► Network
  Network: each digest ∈ certified Store?  ──► issue operator CERTIFICATE (expiry, renewable, revocable)
  provisioning / sensitive ops:  host_operator certified & valid?  ──► allow   (identity path untouched)
  [S3] operator co-signs hosted-tenant tokens  ──► "arrived via certified operator" (origin bound, name still portable)
```

### Mechanism choices (and why)

- **Digest attestation over remote code inspection.** The operator signs the `component@version` + image digests it
  runs; the Network compares to the certified Store record. Simple, verifiable, and reuses ADR-0079's digests. It is a
  *self-attestation* (trust-on-first-use + revocation), **not** hardware TEE/remote-attestation — that is a possible
  S4 hardening, out of scope here.
- **mTLS is complementary, not the mechanism.** Client certs prove *transport origin*, not *runtime integrity*. We may
  add operator mTLS at the Network edge (S3) to bind origin, but the integrity claim is the **signed digest
  attestation**, not the TLS cert.
- **Off the identity path, on the policy path.** Keeping certification out of `authn.verify` is deliberate: it keeps
  token verification cheap, portable, and origin-independent, while hosting/admission policy gains the operator
  constraint.

## Consequences

- **"Tenants run on certified operators" becomes true, not assumed** — provisioning and sensitive Network operations
  gate on a live operator certificate, backed by attested runtime digests.
- **Portability is preserved** — identity stays tenant-anchored (ADR-0084); certification constrains the host, a
  separate axis.
- **A modified/unofficial build is detectable** — its attested digests won't match the certified Store, so it cannot
  obtain (or keep) an operator certificate; the reference deployment self-certifies as the bootstrap operator.
- **The "operator" record gains teeth** — it stops being a UX string and becomes a governed, certified, revocable
  participant, answering *"why register an operator."*
- **Cost:** a new attestation/heartbeat surface + operator-certificate lifecycle (issue/renew/revoke), an operator
  signing key per install (Vault), and a provisioning-time policy check. Self-attestation is trust-on-first-use — it
  raises the bar (detects drift + unofficial builds) without claiming hardware-rooted proof; TEE remote attestation is
  a later hardening, not this ADR.

## Rollout (slices)

- **S1 — Operator identity + attestation intake.** Operator signing key (Vault); `POST /v1/operators/attest`
  (operator-signed `{components:[{component_id, version, image_digest}], attested_at}`); the Network verifies each
  digest against the certified Store and records the attestation. Reference deployment self-attests as bootstrap
  operator. *No enforcement yet — observe + record.*
- **S2 — Operator certificate lifecycle.** Issue an operator `CERTIFICATES` entry on a passing attestation (expiry +
  attested set + digest); renew on re-attestation; revoke on failure/lapse; `GET /v1/operators/{id}/certificate`.
- **S3 — Certified-hosting enforcement + origin binding.** Provisioning + sensitive Network ops require the tenant's
  `host_operator` to hold a valid certificate. Operator mTLS at the Network edge and/or operator co-signing of hosted
  tenant tokens to bind *origin* (tenant identity still portable). Enforce, with a grace/legacy window.
- **S4 (optional, later) — Hardware-rooted attestation.** TEE / remote attestation for operators that need
  cryptographic runtime proof beyond self-attestation.

## Open questions

- **Bootstrap trust:** the reference deployment self-certifies (it *is* the Store authority). Is self-attestation
  acceptable for third-party operators at S1–S2 (trust-on-first-use + revocation), deferring TEE to S4? (Proposed: yes.)
- **Granularity:** attest the *whole* runtime set, or per-service? (Proposed: the runtime images that constitute the OS
  plane — kernel, reference/app-host, scheduler, runtime-manager — since those enforce confinement + delivery.)
- **Enforcement scope:** which Network operations gate on operator certification (all writes? only provisioning + steward
  signing + marketplace publish?) vs. which stay open for portability/liveness. (Proposed: provisioning, steward
  signing, and publish; keep read/health open.)
- **Revocation propagation:** how fast must a revoked operator's hosted tenants be treated as untrusted, and what is the
  citizen-facing consequence (read-only? migrate?)? Ties to the ADR-0084 portability path.

# ADR-0150 — Components and solutions: publishers list, certifiers attest, marketplaces present

**Status:** Proposed
**Date:** 2026-11-27
**Related:** ADR-0140 (listings: the poster owns, the network caches, search providers present), ADR-0141 (the commons),
ADR-0143 (the Networks app: Marketplace), ADR-0144 (status lists; keys), ADR-0147 (mandates; the authority directory),
ADR-0149 (evidence; verification checklist).

## The problem

The marketplace is a single catalogue held by the network. A developer submits a component, the commons steward
approves it, and the authority signs its certificate. That makes the network the publisher's intermediary, the steward
the judge of every component's quality, and the authority key the source of every certificate — the shapes ADR-0144,
ADR-0146 and ADR-0147 remove elsewhere. It also gives one answer to questions that have different owners: *who made
this?*, *does it do what its specification says?*, *is it safe to run here?*, *may this organisation use it for this
purpose?*

## Decision

1. **The publisher owns the listing.** A component or solution listing is a record of the governed type
   `network.certified_component` (a listing type, ADR-0140), signed by its publisher: identity, version, the digest of
   each package, the specifications it claims to implement, what it needs (runtime, permissions, data, egress), licence
   and terms. Each change is a new signed version. The commons caches it for discovery and puts it in the feed; any copy
   can be checked against the publisher's key.

2. **Certifiers are participants with a role and a mandate.** A certifier signs a **certificate** about one version of
   one listing (bound to its package digest): what was assessed, against which specification and version, by which
   method (automated conformance suite, test lab, audit), with what result and for how long. Its authority to certify
   that subject comes from a mandate (ADR-0147) granted by whoever owns the specification or the regulated domain.

3. **Levels of certification follow who owns what is being certified.**

   | What is certified | Against | Who may certify | Level |
   |---|---|---|---|
   | Platform conformance (the component honours the platform contracts: manifest, permissions, isolation, signing, the SDK interfaces) | AirawatOS specifications (SPEC-*) | certifiers accredited by the commons | commons |
   | Domain conformance (it implements a domain's record types and protocols correctly) | the domain's governed contracts (ADR-0141 domain owners) | certifiers the domain owner accredits | domain |
   | Regulatory compliance (it meets a law or regulator's standard — data protection, health records, financial rules, accessibility) | the regulator's standard | certifiers the regulator mandates | regulator |
   | Security and operations (penetration test, supply-chain provenance, runtime image integrity) | a published security baseline | security auditors accredited for it | commons or regulator |
   | Fitness for one organisation's purpose | that organisation's requirements | the organisation itself, or someone it engages | the organisation (not a public certificate) |

   A certifier may hold mandates at several levels; a certificate states which one it relies on. The commons runs the
   accreditation machinery (directory, mandates, status), not every certification.

4. **What a certifier certifies is conformance, stated precisely.** A certificate never says "good" or "approved". It says
   *version V of component C, package digest D, conforms to specification S version X for these clauses, tested by method
   M, valid until T*, with a link to the evidence (the conformance report). Partial conformance is stated as such.
   Certifying a solution means certifying the bundle as composed (its parts' certificates plus the integration), not only
   that each part is certified.

5. **Certificates have a status list.** A certifier can suspend or revoke a certificate (a flaw found, a specification
   withdrawn, its own mandate lapsed). Every installation checks the status before installing and on a schedule after;
   a revocation reaches every installed tenant.

6. **Installation is where trust is decided, locally.** The operator or tenant installing a component checks: the
   package digest against the publisher's signed listing; the publisher's key in the directory; each certificate's
   signature, the certifier's mandate for that kind of certificate, and its status; and that the certificates meet
   **its own policy** (for example "platform conformance and, for health data, the regulator's certificate"). Operators
   and networks publish such policies; nobody else decides for them.

7. **Packages can live anywhere.** The publisher, an operator's mirror or a content network may hold a package; the
   digest makes every copy verifiable. The commons need not host packages.

8. **Marketplace providers present.** A marketplace provider is a member whose role *uses* `network.certified_component`:
   it receives the feed and offers search, curation, bundles, its own signed reviews and ratings, and — where it chooses —
   billing or procurement. It cannot alter a listing or a certificate, and its reviews are its own records, kept apart
   from them. The Marketplace tab of the Networks app is one marketplace provider, the default.

## What changes on the current build

| Today | After |
|---|---|
| One catalogue held by the network | Publishers' signed listings, cached by the commons, in the feed |
| The steward approves every component | Certifiers certify against specifications, under mandates; the steward accredits certifiers |
| The authority key signs certificates | Each certifier signs with its own key; certificates name the mandate they rely on |
| A certificate means "approved" | A certificate states the specification, version, clauses, method, validity and evidence |
| Revocation pulls a listing | A certificate status list checked at and after installation |
| The Marketplace is the only catalogue | Any number of marketplace providers on the same feed |

**First build on staging:** the commons gets the *certifier* role; the steward's existing submission queue becomes the
first certifier's review queue (the steward as a recognised platform-conformance certifier, with a mandate recorded);
existing certificates are re-expressed as platform-conformance certificates; installation checks the certificate status.

## Acceptance tests

- A component whose package digest differs from its signed listing is refused at installation.
- A certificate revoked by its certifier stops new installations and is flagged in every tenant that has it installed.
- A certificate from a certifier without a mandate for that kind of certificate is not accepted.
- A second marketplace provider shows the same listings, verified, without the commons' help.

## Open questions

1. Accrediting the first certifiers (the bootstrap) and who may accredit regulators' certifiers.
2. Conformance suites as governed artefacts: who maintains them per specification.
3. Paid components: whether licences and payment belong in the listing, the marketplace provider, or both.
4. Liability when a certified component fails — the certifier's, the publisher's, or the installer's.

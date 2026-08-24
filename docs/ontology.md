# The Airawat Stack — Ontology v3

**A governed digital stack for reconstructable decisions and continuous learning.**

Airawat is a federated architecture for governed digital systems.

Its purpose is not merely to digitize workflows or automate service delivery. Its purpose is to make consequential institutional decisions **reconstructable, defensible, and continuously improvable**.

Every consequential decision should be capable of producing a durable decision receipt that allows an institution, and the person exercising authority on its behalf, to reconstruct years later:

- what was decided;
- what was known at the time;
- what evidence was considered;
- which evidence was accepted, rejected, or contested;
- which rules were applicable;
- which exact versions of those rules were used;
- what authority the decision maker possessed;
- what process was followed;
- which recommendations, models, or software executions contributed;
- where discretion was exercised;
- why the outcome followed;
- what obligations or orders resulted;
- and what subsequently happened.

The system must simultaneously learn from execution, outcomes, appeals, corrections, failures, usage, and changing conditions.

These are the two constitutional properties of Airawat.

## Reconstructability

> The past must remain explainable in the terms, facts, rules, authority, software, models, and process that existed at the time.

## Learnability

> Evidence from the past must improve future language, machinery, intelligence, governance, and participation without rewriting history.

The architecture therefore combines:

```text
IMMUTABLE ACCOUNTABILITY
        +
CONTINUOUS ADAPTATION
```

Learning changes the future.

It never changes the historical record of why the past occurred.

---

# 1. The Stack

Airawat is organized into five semantic layers.

A layer describes **semantic ownership and dependency**, not physical storage, deployment topology, database ownership, or microservice boundaries.

| Layer | Fundamental question | Responsibility |
| --- | --- | --- |
| **L1 Network** | What can participants mean and trust? | Shared semantics + federation trust |
| **L2 AirawatOS / Platform** | How is it executed and enforced? | Local execution + enforcement |
| **L3 Intelligence** | What can reasonably be inferred, predicted, detected, or recommended? | Epistemic interpretation |
| **L4 Governance** | What does the institution recognize, authorize, require, prohibit, or owe? | Normative authority |
| **L5 Interaction** | How do parties participate and exchange? | Participation + exchange |

In shorthand:

```text
L5  participation
L4  authority
L3  knowledge
L2  execution
L1  meaning + trust
```

The deeper distinction is:

```text
Network       defines meaning
Platform      executes meaning
Intelligence  interprets reality
Governance    changes institutional reality
Interaction   connects institutions to participants
```

---

# 2. The Two Constitutional Guarantees

## 2.1 Reconstructability

For every consequential Governance decision, Airawat must be able to reconstruct the decision context as it existed at the time of decision.

Not:

```text
What do we know now?
```

but:

```text
What could the decision maker reasonably
have known then?
```

These are different queries.

A record corrected in 2030 must not silently replace the version available to an officer making a decision in 2027.

Airawat preserves both:

```text
current truth / current institutional view
```

and:

```text
historical decision context
```

A decision must therefore be reproducible from version-pinned references to:

```text
evidence
rules
authority
process
recommendations
models
schemas
facts
software executions
```

---

## 2.2 Learnability

Every layer contains a feedback loop.

Airawat learns from:

```text
usage
errors
corrections
outcomes
appeals
audits
prediction accuracy
recommendation quality
failed interactions
unmet demand
runtime failures
trust failures
```

But learning is never self-modification without governance.

Learning produces:

```text
proposal
candidate rule
candidate model
candidate configuration
candidate process
candidate surface
candidate vocabulary
```

which must then pass through the appropriate certification, approval, or governance mechanism.

Therefore:

> Learning proposes. Governance and certification admit.

---

# 3. Layer Dependency

A concept may semantically depend only on its own layer or lower layers.

Formally:

> A schema owned by layer L may reference, specialize, validate against, or require only concepts from L or below.

Thus:

```text
Interaction → Governance → Intelligence → Platform → Network
Governance  → Intelligence → Platform → Network
Intelligence→ Platform → Network
Platform    → Network
Network     → nothing above Network
```

A higher layer may use a lower layer directly without requiring every intermediate layer.

For example:

```text
governance.decision
```

may rely only on rules and facts without requiring an Intelligence recommendation.

A lower-layer record may later participate in a higher-layer construct without knowing that it does.

This is the machine-checkable meaning of strict downward dependency.

---

# 4. Semantic Ownership ≠ Physical Persistence

All governed records may physically be stored by the Platform registry.

For example:

```text
network.schema
geo.building
risk.flood
governance.decision
benefit.application
```

may all be persisted through the same L2 machinery.

Their namespace indicates semantic ownership, not storage location.

---

# 5. Naming Convention

Every governed semantic name uses:

```text
<namespace>.<term>
```

A namespace may represent:

```text
an architectural layer
a vertical domain
a cross-cutting semantic domain
```

Examples of architectural namespaces:

```text
network
platform
intelligence
governance
interaction
```

Examples of vertical domains:

```text
geo
finance
health
justice
benefit
permit
program
procurement
```

Examples of cross-cutting semantic domains:

```text
rule
credential
marketplace
```

For nouns and semantic contracts, the term is normally noun-like:

```text
geo.building
governance.decision
interaction.request
marketplace.listing
```

For interfaces, the term expresses a verb:

```text
record.read
permit.approve
notification.send
runtime.invoke
```

A dot descends into a classification or governed attribute:

```text
network.participant.kind
platform.component.kind
governance.order.kind
```

An underscore joins words within one compound term:

```text
governance.role_grant
governance.decision_receipt
platform.run_token
```

---

# 6. Field Naming

Reference fields are explicit.

```text
subject_ref
process_ref
decision_ref
origin_ref
steward_ref
decision_maker_ref
accountable_authority_ref
```

Arrays of references use:

```text
evidence_refs[]
rule_refs[]
recommendation_refs[]
authority_basis_refs[]
order_refs[]
commitment_refs[]
key_refs[]
run_refs[]
```

Embedded/value fields do not use `_ref`.

Examples:

```text
status
kind
mode
reason
confidence
valid_time
```

The mechanical convention is:

```text
foo_ref      = one governed reference
foo_refs[]   = many governed references
foo          = embedded or scalar/value semantics
```

This convention applies throughout the ontology.

---

# 7. Identifiers and References

Canonical identifiers use:

```text
ds:<tenant>:<namespace>/<term>/<local>
```

The federation exposes one generic resolvable reference mechanism.

Conceptually:

```text
ds://<tenant>/<namespace>/<term>/<local>
```

A reference resolves to a governed record.

Its semantic type is discovered from the resolved record rather than encoded in multiple URI schemes.

Rules therefore do not require a special `rule://` reference type.

A rule is simply another governed fact.

---

# 8. The Four Semantic Primitives

Airawat uses four semantic primitives:

```text
fact · verb · role · rule
```

They are not mutually exclusive storage classes.

They answer four fundamental questions.

| Primitive | Question |
| --- | --- |
| **fact** | What is asserted? |
| **verb** | What can happen? |
| **role** | In what capacity may an actor participate? |
| **rule** | What constrains what may happen? |

A rule is itself represented as a fact.

A verb and a role are defined through Network definitions.

Thus the four primitives are semantic primitives, not disjoint technical types.

---

# 9. The Type Ladder

Airawat distinguishes three levels explicitly:

```text
DEFINITION KIND
        ↓ defines

SEMANTIC CONTRACT / SCHEMA
        ↓ instantiated as

FACT OR INTERACTION INSTANCE
```

For example:

```text
network.schema
        defines
governance.decision
        specialized by
permit.approval
        instantiated as
permit-approval-123
```

For roles:

```text
network.role
        defines
permit.approver
        granted to
actor X
```

For verbs:

```text
network.interface
        defines
permit.approve
        instantiated by
network.interaction Y
```

This distinction prevents confusion between:

- the metamodel;
- a governed semantic contract;
- and a runtime instance.

---

# 10. Generic Contracts, Domain Types, Instances

A central rule of Airawat is:

> Layers define generic semantic contracts. Domains specialize those contracts. Facts instantiate generic or domain contracts.

Example:

```text
intelligence.prediction
        ↓ x-specializes
risk.flood
        ↓ schema
flood-prediction-001
```

Likewise:

```text
interaction.request
        ↓ x-specializes
benefit.application
        ↓
application-123
```

And:

```text
governance.decision
        ↓ x-specializes
permit.approval
        ↓
approval-987
```

This prevents duplication between generic layer records and domain records.

A `benefit.application` need not coexist with a separate generic `interaction.request` fact merely to say it is a request.

Its schema specializes the request contract.

---

# 11. The Type System

## 11.1 Instance relation

A fact's:

```text
schema
```

field defines its instance relationship.

Therefore no separate persisted `x-instance-of` relation is required.

If:

```text
schema = risk.flood
```

the fact is an instance of `risk.flood`.

---

## 11.2 `x-specializes`

`x-specializes` applies **only between governed semantic contracts/schemas**.

It does not apply between a semantic schema and a persistence envelope.

For example:

```text
risk.flood
x-specializes intelligence.prediction
```

or:

```text
permit.approval
x-specializes governance.decision
```

Specialization follows substitutability:

> Every instance conforming to a specializing schema must satisfy the required semantic contract of every schema it specializes.

A specialization may:

```text
add fields
constrain values
narrow values where substitutability is preserved
add semantic rules
add facets
```

but may not violate required inherited semantics.

Multiple specialization is permitted only where all inherited contracts are mutually compatible.

---

## 11.3 `x-has-facet`

A facet is a reusable semantic contract composed into another schema without asserting an `is-a` relationship.

```text
intelligence.signal
x-has-facet intelligence.priority
```

Thus:

```text
x-specializes = is a
x-has-facet   = has this semantic aspect
```

A facet may define reusable fields, constraints, or semantics.

---

## 11.4 `x-realizes`

`x-realizes` relates an implementation artifact to a governed semantic capability.

For example:

```text
platform.component/weather-model
x-realizes intelligence.complete
```

It is an implementation relation, not type inheritance.

---

# 12. Universal Record Forms

Airawat uses two universal envelopes:

```text
network.fact
network.interaction
```

`network.definition` is not a third persistence envelope.

It is a semantic metamodel contract used to describe vocabulary definitions.

Thus:

```text
network.fact
    schema = network.definition
    payload = ...
```

stores a definition.

This creates closure:

```text
definitions are facts
rules are facts
predictions are facts
decisions are facts
receipts are facts
domain records are facts
```

Interactions are the separate universal form for exchanges between parties.

---

# 13. `network.fact`

A `network.fact` is:

> An attributable, versioned assertion encoded using a governed schema.

It does not mean objectively true.

A fact may describe:

```text
entity
event
relationship
state
measurement
allegation
prediction
recommendation
decision
rule
definition
```

`network.fact` is an envelope.

Semantic schemas such as:

```text
governance.decision
risk.flood
interaction.receipt
credential.verifiable
```

are not subtypes of the envelope. Their instances are carried by the envelope.

---

# 14. Fact Envelope

Each fact contains:

```text
id
schema
valid_time
observed_at?
prov
confidence?
signature?
payload
```

and registry-stamped metadata:

```text
tenant
tx_time
agent_ref
schema_version
content_hash
version
record_status
superseded_by_ref?
status_reason?
```

The registry-stamped fields are never trusted from the submitted body.

---

# 15. Provenance

Provenance records how the assertion came into existence.

Minimum structure:

```text
prov {
    method
    asserted_by_ref?
    source_refs[]
    derived_from_refs[]
    run_ref?
}
```

Possible methods include:

```text
reported
observed
imported
computed
derived
generated
administrative
```

For derived assertions:

```text
derived_from_refs[]
```

is mandatory.

For model-derived facts, provenance should resolve to:

```text
exact component/model version
exact platform.run
input facts
configuration required for reproducibility
```

where required for reconstructability.

---

# 16. Confidence, Verification, and Record Status

These are separate dimensions.

## Confidence

Represents probabilistic certainty where meaningful.

Absence does not mean 1.0.

```text
confidence?
```

is optional.

---

## Verification status

Verification is normally carried in a domain or case context.

Typical values:

```text
unverified
verified
contested
rejected
```

Verification is not part of the universal registry lifecycle.

---

## Record status

Registry lifecycle:

```text
active
superseded
retracted
```

A credential revocation, expired licence, completed commitment, repealed rule, or breached obligation is not automatically a retracted fact.

Domain lifecycle and record lifecycle remain separate.

---

# 17. Time

Airawat distinguishes:

```text
observed_at?
```

When an observation/assertion was made.

```text
valid_time
```

When the asserted state applies in the world or institutional reality.

```text
tx_time
```

When the registry recorded it.

Domain payloads may additionally contain event-specific times such as:

```text
decided_at
issued_at
paid_at
granted_at
sealed_at
```

A normative act may therefore have:

```text
decided_at = 1 March
valid_time.from = 1 April
```

without ambiguity.

---

# 18. Bitemporal Reconstruction

The registry must support both:

```text
What is currently believed or recognized?
```

and:

```text
What record version existed at decision time T?
```

This is foundational to reconstructability.

For a decision at time `T`, Airawat must be able to retrieve the exact versions of relevant facts that were available at `T`, even if they were later corrected.

---

# 19. `network.interaction`

A Network interaction is a verb-typed exchange.

The L1 envelope remains free of upper-layer concepts.

```text
id
interface_ref
parties {
    from_ref
    to_ref
}
request
response?
actor_ref
correlation_id
occurred_at
metadata?
```

It does **not** contain L3/L4/L5 references such as:

```text
raises
governance.case
intelligence.signal
interaction.receipt
```

Higher-layer records may reference the interaction.

The interaction does not depend on them.

---

# 20. `network.definition`

`network.definition` is the common semantic contract for vocabulary definitions.

The principal definition contracts are:

```text
network.schema
network.interface
network.role
network.domain
```

Formally:

```text
network.schema
x-specializes network.definition

network.interface
x-specializes network.definition

network.role
x-specializes network.definition

network.domain
x-specializes network.definition
```

Each definition is itself persisted as a `network.fact`.

---

# 21. `network.schema`

`network.schema` is a metamodel definition type.

Instances of `network.schema` define semantic contracts such as:

```text
geo.building
risk.flood
governance.decision
permit.approval
interaction.request
```

This distinction between `network.schema` as definition type and `governance.decision` as defined schema is fundamental.

---

# 22. `network.interface`

A governed verb definition contains sufficient semantics for interoperability.

Typical fields:

```text
name
request_schema_ref?
response_schema_ref?
interaction_pattern
effect
consequentiality
idempotency?
```

Possible interaction patterns:

```text
request_response
asynchronous_request_response
fire_and_forget
stream
```

Possible effects:

```text
read
compute
mutate
transact
notify
```

The definition governs semantic behavior, not transport implementation.

---

# 23. Consequential Interactions

A governed interface may declare:

```text
consequentiality = consequential
```

where the interaction materially affects:

```text
rights
obligations
money
authority
access
legal status
evidence
external side effects
```

Such interactions should normally produce a durable `interaction.receipt`.

---

# 24. `network.role`

`network.role` defines a canonical actor capacity.

Role names live in their semantic namespace.

Examples:

```text
case.worker
permit.approver
registry.steward
audit.auditor
```

`network.role` defines what the role means.

It does not say who currently holds it.

---

# 25. Namespace vs Domain

A namespace is part of the naming grammar.

A `network.domain` is a governed semantic-domain registration.

Thus:

```text
network
platform
governance
```

may be architectural namespaces without being ordinary domain registrations.

Vertical or cross-cutting semantic domains may be registered as:

```text
geo
finance
health
justice
rule
credential
marketplace
```

The concepts are related but not identical.

---

# 26. `network.pack`

A signed versioned collection of compatible definitions.

```text
definition_refs[]
version
publisher_ref
signature
dependency_refs[]
```

It is not a subtype of `network.definition`.

---

# 27. Rules

A rule is a fact conforming to a `rule.*` schema.

Examples:

```text
rule.threshold
rule.eligibility
rule.validation
rule.fee
rule.priority
rule.decision_evidence
rule.decision_authority
```

Typical rule structure:

```text
meaning
scope
authority_ref
effective_period
expression?
expression_language?
```

The normative meaning and executable representation are distinct.

A policy may remain semantically the same while its executable encoding changes.

---

# 28. Rule Versioning

Every decision that relies on a rule must pin the exact rule version used.

Historical reconstruction must never resolve a decision against a later rule version merely because it shares the same logical identifier.

The same version-pinning principle applies to:

```text
schemas
processes
models
artifacts
recommendations
evidence
```

---

# 29. Network Participants

`network.participant` represents a federation-level actor.

```text
id
kind
display_name
status
key_refs[]
```

Typical kinds:

```text
operator
developer
government
agency
organization
```

Ordinary service users do not need to become Network participants.

Actor-valued fields across the ontology use governed references and may point to:

```text
network participants
individual identity subjects
organizations
components
agents
domain entities
```

according to schema constraints.

---

# 30. `network.authority`

A Network authority is a federation participant recognized as a trust issuer within a governed scope.

Therefore:

```text
network.authority
x-specializes network.participant
```

An authority may be trusted for:

```text
a namespace
participant accreditation
artifact certification
specific definition families
specific jurisdictions
```

Airawat does not require one universal authority.

Trust policy determines which authorities are recognized for which scopes.

---

# 31. Directory

The directory is logical federation machinery for participant and trust discovery.

The governed record is:

```text
network.directory_entry
```

Typical structure:

```text
participant_ref
authority_ref
key_refs[]
scope
valid_time
attestation_ref
```

Directory resolution may be:

```text
local
remote
delegated
cached
federated
```

The ontology does not require one global physical directory.

---

# 32. `network.key`

Keys are first-class governed records because they rotate, expire, and may be revoked.

Typical structure:

```text
key_id
owner_ref
purpose
algorithm
public_key
valid_time
status
```

Possible purposes:

```text
signing
encryption
authentication
```

Algorithms are policy-controlled and evolvable.

---

# 33. `network.attestation`

An attestation represents:

> An authority-signed claim about a governed subject.

Typical structure:

```text
issuer_ref
subject_ref
claim
valid_time
signature
```

Participant accreditation and artifact certification may specialize or use this contract.

This avoids making `network.certificate` artifact-specific.

---

# 34. Canonicalization

All hashes and signatures operate over Network-defined canonical representations.

Two conforming implementations must produce the same signed/hash representation for semantically identical governed content.

---

# 35. Network Change Loop

Vocabulary changes never apply silently.

```text
problem / opportunity
        ↓
network.proposal
        ↓
review
        ↓
network.approval
        ↓
new signed version
```

`network.approval` is the minimal bootstrap authority mechanism required for Network to govern itself without depending upward on Governance.

A `network.approval` must itself retain sufficient pinned context to reconstruct:

```text
proposal version
definition versions
authority
review evidence
signature
```

This is Network's primitive equivalent of reconstructability.

---

# 36. Reputation and Trust Learning

Network owns the rules and vocabulary for trust.

Derived assessments of participant behavior are epistemic outputs.

A domain contract such as:

```text
trust.reputation
```

may therefore specialize:

```text
intelligence.analysis
```

and derive from:

```text
failed verification
revocation history
security incidents
conformance failures
upheld complaints
availability
```

Trust assessments should remain multidimensional and provenance-backed.

A scalar reputation score must not silently become a trust root.

Network rules may use these derived trust facts when determining privileges.

---

# 37. Layer 2: AirawatOS / Platform

Platform provides local execution and enforcement.

It turns Network definitions into operational reality without changing their meaning.

---

# 38. `platform.tenant`

A tenant is:

> An isolated administrative and execution boundary stewarded by a participant.

A participant may steward multiple tenants.

```text
tenant_id
steward_ref
environment
status
```

---

# 39. Authentication

Authentication establishes the current actor.

The actor may represent:

```text
participant
individual
component
agent
service identity
```

Platform authentication services implement governed interfaces.

---

# 40. `platform.role_binding`

A Platform role binding enforces:

```text
actor_ref
role_ref
scope
valid_time
```

where `role_ref` resolves to a governed `network.role` definition.

It does not depend on `governance.role_grant`.

A higher-layer Governance role grant may cause a corresponding Platform role binding to be created.

The L2 concept itself remains self-contained.

---

# 41. `platform.grant`

A Platform grant is a capability authorization.

It is not itself consent.

```text
subject_ref
capabilities[] {
    interface_ref
    scope
}
steward_ref
signature
valid_time
```

Governance consent, role grants, or delegations may provide the authority basis for generating Platform grants, but Platform does not need to understand those richer semantics.

---

# 42. `platform.run_token`

A scoped execution capability.

```text
subject_ref
tenant_ref
capabilities
egress
secret_refs[]
valid_time
```

Components receive no ambient authority.

---

# 43. Registry

The registry persists and versions facts.

On write it:

1. resolves the schema;
2. validates the payload;
3. checks capability;
4. binds tenant context;
5. stamps unforgeable metadata;
6. records exact schema version;
7. calculates canonical content hash;
8. preserves previous versions;
9. records supersession rather than mutation of history.

---

# 44. `platform.runtime`

A certified execution-environment definition.

```text
profile
image
image_digest
attestation_ref
```

A runtime is not instantiated per installation.

An installation selects a runtime.

A run executes using it.

Thus:

```text
platform.runtime
        ↓ selected by
platform.installation
        ↓ used by
platform.run
```

---

# 45. `platform.run`

A record of one execution:

```text
component_ref
installation_ref?
tenant_ref
run_token_ref
started_at
ended_at?
status
input_refs[]
output_refs[]
```

The run itself is the execution record.

A separate run receipt is not required unless cryptographic execution attestation is explicitly introduced.

---

# 46. Platform Artifact Model

`platform.artifact` is the generic artifact contract.

It specializes into:

```text
platform.component
platform.app
platform.solution
```

---

# 47. `platform.component`

A confined runnable artifact.

```text
interface_refs[]
read_schema_refs[]
write_schema_refs[]
scopes[]
egress[]
secret_refs[]
runtime_profile
kind
```

`platform.component.kind` may include:

```text
driver
engine
model
skill
```

---

# 48. `platform.app`

A user-facing executable artifact.

```text
entrypoint
distribution
interface_refs[]
read_schema_refs[]
```

An app has no independent institutional authority.

Calls execute under capabilities associated with the current actor/session.

---

# 49. `platform.solution`

A deployable composition of artifacts.

```text
member_refs[]
extends_refs[]
activation
setup
dependency_refs[]
```

It does not reference higher-layer concepts such as:

```text
governance.process
interaction.surface
```

Higher layers may reference a Platform solution as an implementation.

---

# 50. `platform.installation`

An installation binds an artifact deployment to a tenant.

```text
artifact_ref
artifact_version
tenant_ref
configuration
runtime_ref
grant_refs[]
status
installed_at
```

It forms the lifecycle bridge:

```text
artifact
→ marketplace listing
→ installation
→ run
```

---

# 51. `marketplace.listing`

A certified published offer.

```text
artifact_ref
artifact_version
provider_ref
attestation_ref
status
price?
sla?
```

Artifact family is derived from the referenced artifact and need not be duplicated as listing kind unless marketplace semantics require a distinct classification.

---

# 52. Platform Learning Loop

Platform learns from:

```text
schema validation failures
runtime failures
registry corrections
latency
capacity
resource usage
installation failures
certification failures
```

Learning produces candidate:

```text
configuration
placement policy
runtime policy
certification rule
data-quality improvement
```

Candidates then pass through appropriate operator approval or certification.

---

# 53. Layer 3: Intelligence

Intelligence produces epistemic interpretation.

It answers:

```text
What appears to be happening?
Why?
What may happen?
What deserves attention?
What intervention may be useful?
```

It does not itself create institutional authority.

---

# 54. Deterministic Computation ≠ Intelligence

Not every calculation belongs to Intelligence.

For example:

```text
rule.fee × property.area
→ finance.fee_calculation
```

is deterministic computation.

It may be performed by Platform machinery and produce a domain fact.

Intelligence is reserved for functions involving:

```text
inference
prediction
diagnosis
uncertainty
detection
correlation
optimization
recommendation
```

Thus Airawat distinguishes:

```text
deterministic computation
epistemic inference
normative act
```

---

# 55. Intelligence Contracts

Core generic contracts include:

```text
intelligence.analysis
intelligence.prediction
intelligence.signal
intelligence.recommendation
intelligence.priority
intelligence.agent
```

And:

```text
intelligence.diagnosis
x-specializes intelligence.analysis
```

---

# 56. `intelligence.analysis`

A derived epistemic interpretation whose semantics go beyond deterministic transformation of governed facts.

Examples:

```text
causal diagnosis
risk classification using uncertain evidence
anomaly explanation
multi-source interpretation
```

A purely deterministic aggregation need not be classified as Intelligence.

A domain-specific analysis should normally specialize this generic contract.

---

# 57. `intelligence.prediction`

A modeled future or latent state.

Typical contract:

```text
subject_ref
horizon
prediction
confidence?
basis_refs[]
```

Examples:

```text
risk.flood
x-specializes intelligence.prediction

weather.forecast
x-specializes intelligence.prediction
```

---

# 58. `intelligence.signal`

A signal is:

> An epistemic assertion that a condition may deserve attention.

It may arise from:

```text
detection
inference
correlation
prediction
anomaly analysis
```

A deterministic Governance trigger does not need to produce an Intelligence signal.

For example:

```text
statutory deadline reached
```

may directly trigger a Governance process.

---

# 59. `intelligence.priority`

A reusable recommended-attention facet:

```text
importance
urgency
confidence?
score?
```

Importance may derive from:

```text
magnitude
reach
criticality
```

Urgency may derive from:

```text
time_to_impact
deadline
lead_time
```

The facet expresses recommended attention, not final institutional priority.

Provenance remains on the enclosing fact.

---

# 60. `intelligence.recommendation`

Advice about possible action.

```text
subject_ref
recommended_action
basis_refs[]
confidence?
priority?
alternative_refs[]
```

`basis_refs[]` may reference:

```text
facts
rules
predictions
analyses
constraints
```

A recommendation is never binding merely because it exists.

---

# 61. Derivation vs Evidentiary Basis

Airawat distinguishes:

```text
prov.derived_from_refs[]
```

from:

```text
basis_refs[]
```

`derived_from_refs[]` answers:

> What technically produced this output?

`basis_refs[]` answers:

> What substantive information supports this interpretation or recommendation?

The two may overlap, but are not semantically identical.

---

# 62. `intelligence.agent`

An Intelligence agent is a reasoning actor capable of producing epistemic outputs.

Its L3 definition contains no Governance dependency.

It possesses no institutional authority merely by being an agent.

Higher layers may separately authorize actions involving such an agent.

---

# 63. Intelligence Learning Loop

```text
prediction
→ outcome observation
→ accuracy evaluation
→ candidate model

recommendation
→ decision
→ outcome
→ recommendation evaluation
→ candidate model/policy
```

Candidate models must then pass through:

```text
testing
certification
artifact publication
installation
```

before affecting future production decisions.

---

# 64. Layer 4: Governance

Governance creates normative institutional state.

It answers:

```text
What is recognized?
What is permitted?
What is prohibited?
What is required?
What is owed?
Who has authority?
What decision is binding?
```

Governance is where reconstructability becomes an institutional guarantee.

---

# 65. The Two Trigger Families

A governed matter may arise through two abstract trigger families.

## Trigger A: interaction-triggered

A participant asks an institution to:

```text
decide
authorize
provide
change
adjudicate
recognize
```

Example:

```text
benefit.application
→ Governance handling
```

## Trigger B: state/rule-triggered

A state satisfies a rule requiring institutional attention or action.

Examples:

```text
deadline reached
commitment breached
threshold crossed
statutory period opened
signal received
mandatory review due
```

Trigger B may be either:

```text
fact + deterministic rule
→ Governance
```

or:

```text
fact
→ intelligence.signal
→ triage
→ Governance
```

Intelligence is not mandatory middleware.

---

# 66. Case Principle

A `governance.case` is:

> A tracked governed matter requiring accountable handling.

Not every deterministic state transition requires a case.

A case is normally required where there is:

```text
request requiring disposition
discretion
verification
investigation
multi-step handling
contestability
exception handling
escalation
adjudication
```

Pure deterministic normative consequences may occur without creating a case where governing rules explicitly permit them.

---

# 67. `governance.case`

Typical structure:

```text
subject_ref
opened_by_ref
process_ref
process_version
record[]
priority
status
step
```

`record[]` is a logical case-record view.

It need not imply physical embedding inside one mutable JSON object.

Entries may contain:

```text
ref
relevance
verification_status
submitted_by_ref
```

A case may contain contradictory assertions.

Case membership does not imply truth.

---

# 68. `governance.process`

A versioned definition of governed handling.

```text
steps[]
states[]
transitions[]
rule_refs[]
role_refs[]
```

Every case binds to an exact process version.

A running case must never silently change behavior because the process definition was later edited.

---

# 69. `governance.task`

A unit of accountable work within a case.

```text
case_ref
addressee_ref
priority
status
due?
```

Invariant:

> Every `governance.task` belongs to a Governance case.

Non-case operational work should use another domain/work-management concept rather than overloading Governance task.

---

# 70. Findings and Evidence

A case record may contain:

```text
assertions
documents
observations
prior decisions
reports
derived facts
```

A decision must distinguish:

```text
what was available
```

from:

```text
what was relied upon
```

Therefore decisions carry explicit:

```text
evidence_refs[]
```

and may record finding dispositions such as:

```text
accepted
rejected
contested
```

---

# 71. `governance.decision`

A decision is:

> An attributable exercise of institutional authority that converts evidence and rules into normative institutional state.

Typical contract:

```text
case_ref?
subject_ref
evidence_refs[]
rule_refs[]
recommendation_refs[]?
decision_maker_ref
accountable_authority_ref
authority_basis_refs[]
decided_at
valid_time
discretion
mode
outcome
reason
```

---

# 72. Decision Maker vs Accountable Authority

These are separate concepts.

For a human decision:

```text
decision_maker_ref
≈ accountable authority / authorized officer
```

For automated decision execution:

```text
decision_maker_ref = component/agent
accountable_authority_ref = institution/role
```

The decision remains attributable to an institutional authority even where execution is automated.

---

# 73. Decision Modes

```text
human
human_assisted
automated
```

Deployments may prohibit automated modes for specific decision classes.

Automated execution never removes:

```text
authority basis
rule provenance
software provenance
evidence provenance
decision receipt requirement
```

---

# 74. Receipt Semantics

A receipt is:

> An immutable attestation of the context and result of a consequential act.

Two important receipt contracts are:

```text
interaction.receipt
governance.decision_receipt
```

They serve different domains but share the principle that a consequential act should leave durable evidence of what happened.

---

# 75. `governance.decision_receipt`

This is a core Airawat concept.

A decision receipt is:

> A durable, immutable, signed reconstruction manifest for a consequential decision.

The decision itself records the institutional act.

The receipt does not duplicate that act unnecessarily.

Instead, it cryptographically freezes the exact context needed to reconstruct it.

Typical structure:

```text
decision_ref
decision_hash

evidence_manifest[] {
    ref
    version
    content_hash
    verification_status
    admitted_as
}

rule_manifest[] {
    ref
    version
    content_hash
}

recommendation_manifest[] {
    ref
    version
    content_hash
}

process_manifest? {
    ref
    version
    completed_steps[]
    exceptions[]
}

run_refs[]

finding_manifest[] {
    ref
    disposition
    reason?
}

discretion_manifest? {
    exercised
    basis_refs[]
    alternative_refs[]
}

sealed_at
```

The decision receipt itself is stored as a `network.fact`, so universal fields such as:

```text
content_hash
signature
valid_time
provenance
```

are inherited from the fact envelope and are not duplicated unnecessarily in the payload.

---

# 76. Decision Receipt Principle

The receipt must allow Airawat to reconstruct:

```text
What was decided?

About what?

By whom?

Under what authority?

Using what evidence?

Under which rules?

Using which exact versions?

What was accepted or rejected?

What process was followed?

What recommendations were available?

Which software/model runs contributed?

Where was discretion exercised?

What reason was recorded?

What normative consequences followed?
```

It is not merely a logging artifact.

It is an accountability artifact.

---

# 77. Receipt Completeness

Different decision classes require different evidentiary completeness.

A permit decision may require:

```text
ownership evidence
zoning evidence
plan verification
statutory approvals
authorized approver
```

A grievance decision may require a different set.

Receipt completeness is governed by domain rules such as:

```text
rule.decision_evidence
rule.decision_authority
rule.decision_process
rule.decision_reason
```

Before a consequential decision is finalized:

```text
decision prepared
        ↓
receipt completeness validation
        ↓
authority/signature validation
        ↓
decision finalized
        ↓
decision receipt sealed
```

---

# 78. Historical Reconstruction

Suppose a decision was made in 2027 and reviewed in 2030.

Airawat preserves:

```text
2027 evidence version
2027 rule version
2027 process version
2027 authority state
2027 recommendation/model execution
2027 findings
2027 decision
2027 decision receipt
```

If new evidence appears in 2030, it creates new facts.

It does not rewrite the 2027 receipt.

Thus Airawat can answer both:

```text
Why was this decision reasonable then?
```

and:

```text
Why do we believe something different now?
```

---

# 79. `governance.order`

An enforceable instruction.

```text
decision_ref
action
addressee_ref
kind
status
```

Kinds may include:

```text
directive
corrective
```

An order tells an actor to act.

It does not necessarily create a continuing obligation.

---

# 80. `governance.commitment`

A directed institutional bond:

```text
obligor_ref
    ─── deliverable ───▶
obligee_ref
```

Typical structure:

```text
obligor_ref
obligee_ref
deliverable
origin_ref
due
terms
status
strength
```

Allowed origins include governed references to:

```text
governance decisions
mutual agreements/contracts
rules
```

A commitment may represent:

```text
benefit entitlement
tax liability
contract obligation
service obligation
SLA
budget commitment
```

---

# 81. Rule-Origin Commitments

A rule may directly create a commitment only where the governing norm explicitly provides that the obligation arises automatically from established facts without a discretionary decision.

Otherwise a Governance decision creates the commitment.

This distinction must be explicit.

---

# 82. Commitment Fulfilment

Fulfilment is represented by domain events referencing the commitment.

For example:

```text
finance.payment {
    commitment_ref
    ...
}
```

Multiple fulfilment events may satisfy one commitment.

Fulfilment progress may therefore be derived from those events rather than maintained solely as a mutable field.

A minimal commitment lifecycle may be:

```text
pending
active
fulfilled
breached
cancelled
superseded
closed
```

Partial fulfilment is normally derived from linked fulfilment facts.

---

# 83. Order vs Commitment

An order and commitment are related but distinct.

Example:

```text
Refund ₹5,000 to citizen by Friday
```

may produce:

```text
governance.order
```

instructing the department to act,

and:

```text
governance.commitment
```

recording the continuing obligation owed to the citizen.

An evacuation order may create an instruction without creating an obligee-oriented commitment.

---

# 84. Authority Model

## `governance.role_grant`

Answers:

> Who institutionally holds a canonical role?

```text
grantee_ref
role_ref
scope
valid_time
grantor_ref
authority_basis_refs[]
revocable
```

## `governance.delegation`

Answers:

> Who may exercise another actor's authority on their behalf?

```text
principal_ref
delegate_ref
interface_refs[]
scope
valid_time
delegation_chain_refs[]
status
```

## `governance.consent`

Answers:

> What permission has a subject voluntarily granted, to whom, for what purpose, and for how long?

```text
grantor_ref
grantee_ref
purpose
scope
valid_time
status
```

Consent is not identical to delegation or role grant.

A consent may serve as authority basis for particular actions or Platform grants.

Revocation of consent, delegation, or role authority should be represented through governed state transition or superseding facts, not unstructured embedded blobs.

---

# 85. Appeals and Review

## `governance.appeal`

```text
decision_ref
appellant_ref
grounds
status
```

## `governance.review`

A `governance.review` is an actual review activity/record, not a process definition.

```text
appeal_ref
reviewer_ref
process_ref?
evidence_refs[]
```

The process semantics, where needed, are defined through `governance.process`.

A review culminates in a new Governance decision.

Possible outcomes include:

```text
affirm
modify
reverse
remand
```

---

# 86. `governance.correction`

A correction specializes:

```text
governance.decision
```

and adds:

```text
supersedes_ref
remedy
```

It receives its own decision receipt.

Thus:

```text
decision₁
→ receipt₁
→ appeal
→ review
→ correction decision₂
→ receipt₂
```

Decision₂ never rewrites Decision₁.

---

# 87. Auditability

Airawat distinguishes:

```text
auditability
```

from:

```text
governance.audit
```

Auditability is reconstructable from:

```text
fact provenance
registry history
interaction receipts
decision receipts
rule versions
process versions
authority chains
execution records
```

`governance.audit` is an actual audit engagement/findings record:

```text
subject_ref
auditor_ref
process_ref?
scope
evidence_refs[]
findings[]
at
```

Audit process mechanics, where required, are modeled through `governance.process`.

---

# 88. Governance Learning Loop

Governance learns from:

```text
decisions
decision receipts
appeals
corrections
audit findings
outcomes
variance in discretion
repeated evidence failures
```

Learning may identify:

```text
bad shared rule
bad local rule
bad process
missing evidence requirement
inconsistent authority
poor decision guidance
```

The resulting change path depends on what needs improvement.

For example:

```text
shared rule problem
→ network.proposal

local policy problem
→ local policy revision process

process problem
→ new governance.process version
```

---

# 89. Layer 5: Interaction

Interaction is where participants encounter the governed system.

It covers:

```text
requests
reports
responses
presentations
surfaces
receipts
```

Channel is normally represented as metadata or a governed classification rather than as a persistent noun unless it has independent identity or lifecycle.

---

# 90. `interaction.request`

A generic semantic contract representing the speech act:

> Please do, decide, provide, authorize, change, recognize, or adjudicate something.

Domain requests should normally specialize it.

Examples:

```text
benefit.application
x-specializes interaction.request

permit.application
x-specializes interaction.request

grievance.grievance
x-specializes interaction.request
```

This avoids duplicate generic request records.

---

# 91. `interaction.report`

A generic contract representing:

> I assert or observed that a condition exists or an event occurred.

Examples:

```text
civic.pothole_report
x-specializes interaction.report
```

A report may later:

```text
become an observation
trigger Intelligence
open a case
join an existing case
remain informational
```

---

# 92. Request vs Report

The distinction is semantic.

```text
request = asks for institutional action
report  = asserts something about the world
```

Downstream workflow is not what defines the type.

---

# 93. `interaction.receipt`

`interaction.receipt` is a governed schema whose instances use the `network.fact` envelope.

It records that a consequential interaction occurred and what result was accepted.

Typical uses:

```text
application submission
payment submission
formal notification
document delivery
credential presentation
external communication
```

The corresponding `network.interaction` remains the protocol/exchange occurrence.

`interaction.receipt` does not "specialize" the `network.fact` envelope. It is carried by it.

---

# 94. `interaction.surface`

A reusable semantic presentation surface offered to users.

Typical fields:

```text
app_ref
channel_kind
audience
capabilities
```

A per-user UI session is runtime/session machinery and does not automatically become an ontology fact.

A separate persistent `interaction.channel` noun is introduced only where a channel has meaningful independent identity or lifecycle.

---

# 95. Inbox

The inbox is a view.

It combines:

```text
pending interactions
+
governance.tasks
```

addressed to an actor and orders them according to institutional priority.

No generic stored `platform.inbox_item` is required.

---

# 96. Credentials

A Verifiable Credential is represented through a governed schema such as:

```text
credential.verifiable
```

whose instances use the `network.fact` envelope and require portable signature and credential-status semantics.

Typical fields:

```text
issuer_ref
subject_ref
claims
valid_time
credential_status_ref
holder_binding?
```

Signature semantics come from the universal fact/signature model rather than being duplicated unnecessarily.

Credential lifecycle is separate from record lifecycle.

Revoking a credential does not mean retracting the historical fact that it was issued.

A wallet is an Interaction surface/tool, not the credential itself.

---

# 97. Interaction Learning Loop

Interaction learns from:

```text
usage
drop-off
abandonment
requests
reports
complaints
feedback
failed discovery
unmet demand
channel accessibility
```

Learning generates candidate improvements to:

```text
surface
service discovery
process
content
accessibility
channel strategy
marketplace demand
```

These changes must pass through appropriate product, certification, or Governance mechanisms before deployment.

---

# 98. The Decision Circulation

The stack's central circulation is:

```text
                        WORLD / PARTICIPANTS
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
         observation                             request
              │                                     │
              ▼                                     ▼
       domain facts                         interaction request
              │                                     │
      ┌───────┴────────┐                            │
      │                │                            │
deterministic      Intelligence                     │
 rule trigger      interpretation                   │
      │                │                            │
      │             signal                          │
      │                │                            │
      └────────────┬───┴────────────────────────────┘
                   ▼
          GOVERNED ATTENTION
                   │
                   ▼
          case where required
                   │
        evidence + rules + authority
                   │
         recommendation optional
                   │
                   ▼
               DECISION
                   │
                   ▼
          DECISION RECEIPT
                   │
           ┌───────┴─────────┐
           ▼                 ▼
         ORDER           COMMITMENT
           │                 │
           └──────┬──────────┘
                  ▼
             INTERACTION
             act / respond
                  │
                  ▼
                WORLD
                  │
                  ▼
             OBSERVATION
                  │
                  ▼
                 LEARN
                  │
                  └──────────────↻
```

---

# 99. Reconstructability Loop

For every consequential decision:

```text
facts
+ evidence
+ rules
+ process
+ authority
+ recommendations?
+ software/model execution provenance?
        ↓
decision
        ↓
decision receipt
        ↓
durable historical context
```

Years later:

```text
decision receipt
        ↓
resolve pinned versions
        ↓
reconstruct decision context
        ↓
explain / audit / appeal / defend
```

---

# 100. Learning Loop

Every completed circulation generates evidence.

```text
decision
→ action
→ observed outcome
→ evaluation
→ candidate improvement
→ governed admission
→ future version
```

The previous version remains preserved.

---

# 101. Per-Layer Learning

| Layer | Evidence | Candidate improvement |
| --- | --- | --- |
| Network | ambiguity, interoperability failure, trust failure | vocabulary, shared rules, trust policy |
| Platform | runtime failure, correction, latency, capacity | software, certification, configuration |
| Intelligence | prediction error, recommendation outcome | models, features, reasoning |
| Governance | appeal, correction, audit, decision variance | rules, process, decision guidance |
| Interaction | usage, abandonment, complaints, unmet demand | surfaces, channels, discovery |

Learning loops generate candidates.

They do not bypass the governance appropriate to the thing being changed.

---

# 102. Worked Scenario A: Benefit Delivery

## Search

```text
catalog.search
→ benefit.scheme
```

## Eligibility

If deterministic:

```text
citizen facts
+ rule.eligibility
→ benefit.eligibility_calculation
```

This does not require Intelligence.

If uncertain or inferential:

```text
citizen facts
→ intelligence.analysis
→ likely eligibility
```

## Apply

```text
benefit.application
x-specializes interaction.request
```

The application may open:

```text
governance.case
```

where verification/disposition is required.

## Decide

```text
benefit.approval
x-specializes governance.decision
```

The decision pins:

```text
citizen evidence
eligibility rule
benefit rule
authority
process
recommendations if any
```

and produces:

```text
governance.decision_receipt
```

## Entitlement

Approval creates:

```text
governance.commitment
obligor_ref = government
obligee_ref = beneficiary
deliverable = benefit
```

## Fulfil

```text
finance.payment
commitment_ref → governance.commitment
```

The outcome later contributes to learning.

---

# 103. Worked Scenario B: Permit

## Apply

```text
permit.application
x-specializes interaction.request
```

## Calculate fee

If deterministic:

```text
rule.fee × property facts
→ finance.fee_quote
```

No Intelligence required.

## Assess

```text
permit.assessment
x-specializes governance.decision
```

or where approval is the decisive act:

```text
permit.approval
x-specializes governance.decision
```

Decision receipt pins:

```text
submitted plans
ownership records
zoning rule
fee rule
inspection evidence
authority
process version
recommendations if used
```

## Issue

The approval may produce:

```text
credential.verifiable
```

representing the permit.

Years later the permit decision can be reconstructed exactly from its receipt.

---

# 104. Worked Scenario C: Infrastructure

Domain entities remain distinct from institutional acts.

```text
program.program
program.project
program.plan
procurement.tender
procurement.bid
contract.contract
work.milestone
finance.payment
```

A sanction may be:

```text
program.sanction
x-specializes governance.decision
```

rather than a generic decision plus duplicated domain status.

The sanction receives a decision receipt containing pinned references to:

```text
proposal version
budget evidence
appraisal
applicable rules
authority
recommendations
process
discretion
outcome
```

Later program state may be derived from these Governance acts.

---

# 105. Worked Scenario D: Grievance

```text
grievance.grievance
x-specializes interaction.request
```

If it contests a prior decision:

```text
→ governance.appeal
```

Otherwise:

```text
→ governance.case
```

Case record may contain:

```text
citizen allegation
agency response
documents
prior interactions
inspection evidence
prior decisions
```

Intelligence may recommend:

```text
classification
priority
routing
```

Governance decides:

```text
grievance.disposition
x-specializes governance.decision
```

The receipt records:

```text
accepted/rejected evidence
SLA/rules
authority
process
recommendations
reason
remedy
```

If later corrected:

```text
correction decision
→ new receipt
→ supersedes original decision
```

The original receipt remains immutable.

---

# 106. Worked Scenario E: Automated Statutory Obligation

A statutory obligation may arise automatically where law explicitly defines the consequence.

```text
facts
+ rule
→ governance.commitment
```

No case or discretionary decision is required if:

```text
conditions are established
rule is deterministic
no discretion exists
governing norm authorizes automatic creation
```

The system must nevertheless preserve:

```text
rule version
facts relied upon
execution record
authority basis for automation
resulting commitment
```

so the automated normative consequence remains reconstructable.

---

# 107. Decision Receipt as the Accountability Spine

The case is the handling spine where matters require tracked resolution.

The **decision receipt is the accountability spine**.

It creates a stable boundary between:

```text
what was knowable then
```

and:

```text
what was learned later
```

This is the foundation for:

```text
audit
appeal
judicial review
enquiry
legislative scrutiny
administrative accountability
institutional learning
```

---

# 108. Reconstructability Invariant

For every consequential decision, Airawat must be capable of reconstructing:

```text
decision-time evidence
decision-time rule versions
decision-time process
decision-time authority
decision-time recommendations
decision-time software/model provenance
decision-time findings
decision-time reasoning
decision-time outcome
```

without relying on mutable current-state representations.

---

# 109. Learning Invariant

Every learning mechanism must preserve:

```text
source evidence
evaluation
candidate change
approval/certification
new version
```

No layer may silently self-modify production semantics while erasing the previous version.

---

# 110. Normative Invariants

1. Every persisted assertion conforms to `network.fact`.

2. Every fact references exactly one governed schema version.

3. A fact's `schema` defines its instance relationship.

4. `x-specializes` applies only between semantic schemas/contracts, never between a schema and an envelope.

5. Every derived assertion records derivation provenance.

6. Confidence, verification, authority, and record lifecycle are separate dimensions.

7. Every consequential exchange conforms to a governed `network.interface`.

8. Lower-layer schemas may never require upper-layer concepts.

9. Every governed record reference is explicit through `_ref` or `_refs`.

10. Every binding institutional act is attributable to an accountable authority.

11. Intelligence outputs do not themselves create normative authority.

12. Deterministic calculation does not automatically belong to Intelligence.

13. Recommendations are optional inputs to Governance decisions.

14. Every consequential Governance decision produces a reconstructable decision receipt.

15. Every receipt pins exact versions or immutable hashes of its decision context.

16. Historical receipts are immutable.

17. Corrections supersede; they do not erase.

18. Running cases pin process versions.

19. Decisions pin rule versions.

20. Model-derived facts retain model/component execution provenance where reconstructability requires it.

21. Technical capability never implies institutional authority.

22. Learning generates governed candidates, not silent production mutation.

23. Domain schemas should specialize generic layer contracts where appropriate rather than duplicate generic records.

24. Current truth and historical decision context must remain separately queryable.

25. Signatures across trust boundaries bind canonical representations.

26. Domain lifecycle does not equal registry record lifecycle.

27. A case may contain contested assertions.

28. A signal is a candidate for attention, not automatically a case.

29. A Governance task always belongs to a case.

30. Pure deterministic consequences need not create artificial cases where governing rules permit direct execution.

31. Keys, rules, schemas, processes, models, and decision context needed for historical reconstruction must remain version-resolvable.

---

# 111. Naming and Ontology Lint Rules

The future machine-checkable metamodel should enforce at least the following mechanical rules.

## Naming

```text
<namespace>.<term>
```

## Reference fields

```text
foo_ref
foo_refs[]
```

## No ambiguous reference/value mixing

A field named:

```text
foo
```

must not sometimes contain an embedded object and sometimes a governed reference.

## No upper-layer dependency

A schema may reference only schemas from its own layer or below.

## No envelope specialization

This is invalid:

```text
interaction.receipt
x-specializes network.fact
```

because `network.fact` is an envelope.

This is valid:

```text
permit.approval
x-specializes governance.decision
```

because both are semantic contracts.

## No implementation ambiguity in field names

Avoid fields such as:

```text
models_or_runs
thing
data
object
ref_or_value
```

Prefer explicitly typed semantics.

---

# 112. Ontology Conformance Test

Every domain should demonstrate:

```text
1. What are the domain facts?

2. Which generic contracts do those facts specialize?

3. Which schemas define them?

4. What verbs operate on them?

5. What roles participate?

6. What rules constrain them?

7. Which computations are deterministic?

8. Which outputs are genuinely inferential?

9. What can trigger governed attention?

10. When is a case required?

11. What evidence enters the case?

12. How is verification represented?

13. Who may decide?

14. What is the authority chain?

15. What rule/process versions apply?

16. What constitutes a complete decision receipt?

17. What normative state does the decision create?

18. What orders or commitments follow?

19. How is fulfilment recorded?

20. How are outcomes observed?

21. How can the decision be appealed?

22. How are corrections represented without rewriting history?

23. Can the decision context be reconstructed years later?

24. What evidence from execution feeds each learning loop?

25. How does a learned improvement become an approved new version?
```

If a domain cannot answer these questions, its ontology or governance design is incomplete.

---

# 113. Canonical Concept Map

```text
METAMODEL / NETWORK
│
├── network.definition
│   ├── network.schema
│   ├── network.interface
│   ├── network.role
│   └── network.domain
│
├── network.fact
├── network.interaction
├── network.reference
├── network.participant
│   └── network.authority
├── network.directory_entry
├── network.key
├── network.attestation
├── network.pack
├── network.proposal
└── network.approval


L2 PLATFORM
│
├── platform.tenant
├── platform.role_binding
├── platform.grant
├── platform.run_token
├── platform.runtime
├── platform.run
├── platform.artifact
│   ├── platform.component
│   ├── platform.app
│   └── platform.solution
├── platform.component.kind
├── platform.installation
├── platform.telemetry [target]
└── marketplace.listing


L3 INTELLIGENCE
│
├── intelligence.analysis
│   └── intelligence.diagnosis
├── intelligence.prediction
├── intelligence.signal
├── intelligence.recommendation
├── intelligence.priority
└── intelligence.agent


L4 GOVERNANCE
│
├── governance.case
├── governance.process
├── governance.task
├── governance.decision
│   └── governance.correction
├── governance.decision_receipt
├── governance.order
├── governance.commitment
├── governance.appeal
├── governance.review
├── governance.audit
├── governance.role_grant
├── governance.consent
└── governance.delegation


L5 INTERACTION
│
├── interaction.request
├── interaction.report
├── interaction.receipt
└── interaction.surface


CROSS-CUTTING / DOMAIN VOCABULARY
│
├── rule.*
├── credential.*
├── marketplace.*
├── trust.*
├── geo.*
├── finance.*
├── risk.*
├── benefit.*
├── permit.*
├── grievance.*
├── program.*
├── procurement.*
└── other domains
```

---

# 114. Migration Priorities

Highest-leverage changes:

```text
signal.alert
→ intelligence.signal

governance.recommendation
→ intelligence.recommendation
```

Then:

```text
platform.case
→ governance.case

platform.task
→ governance.task

platform.inbox_item
→ remove
```

Then:

```text
marketplace.component
→ marketplace.listing

component
→ platform.component
   platform.app
   platform.solution
```

Then introduce:

```text
governance.decision_receipt
```

as the reconstructability artifact.

Further reconciliations:

```text
process
→ governance.process

role assignment
→ platform.role_binding

interaction.credential
→ credential.verifiable

network.certificate
→ network.attestation

network.directory
→ directory machinery
   + network.directory_entry records

governance.audit-as-trail
→ reconstructable view

generic request wrappers
→ domain schemas specializing interaction.request

generic domain decisions
→ domain schemas specializing governance.decision
```

Vertical vocabulary remains unchanged unless individual domain semantics require revision.

---

# 115. The Architecture in One Sentence

> **Airawat is a governed digital stack in which every consequential decision can be reconstructed and justified from the evidence, rules, authority, process, knowledge, and software context available at the time, while the outcomes of those decisions continuously improve the language, machinery, intelligence, governance, and interactions that shape future decisions.**

---

# 116. The Stack in One Diagram

```text
                     RECONSTRUCTABLE PAST
                            ▲
                            │
                    decision receipt
                            │
                            │
facts → compute/infer → govern → act → observe
  ▲                                      │
  │                                      │
  └─────────────── learn ◀───────────────┘
                            │
                            ▼
                        BETTER FUTURE
```

The five layers implement this circulation:

```text
Network
    meaning + trust

Platform
    execution + enforcement

Intelligence
    inference + advice

Governance
    accountable authority + decision receipt

Interaction
    participation + exchange
```

And the entire system remains grounded in the same four semantic primitives:

```text
fact · verb · role · rule
```

The central invariant is:

> **Preserve enough of the past to explain every important decision. Learn enough from the past to make the next decision better.**

---

# 117. Next Step: Machine-Checkable Metamodel

This prose ontology is the semantic specification.

The next step is to translate it into a machine-checkable metamodel that can enforce the architectural rules automatically.

At minimum, the metamodel should be able to validate:

```text
namespace and term grammar
schema registration
schema versioning
fact envelopes
interaction envelopes
reference-field conventions
layer ownership
strict downward dependencies
x-specializes compatibility
x-has-facet composition
interface request/response contracts
role definitions
rule structures
provenance requirements
decision-receipt completeness
version pinning
cross-trust-boundary signing
canonicalization requirements
artifact relationships
```

The metamodel should make architectural violations detectable before deployment.

For example, it should reject:

```text
an L2 schema referencing governance.decision
a schema specializing network.fact
a derived fact without lineage
a consequential decision without a decision receipt
a decision receipt referencing mutable unversioned evidence
an ambiguous reference field
an incompatible schema specialization
```

The prose defines what Airawat means.

The machine-checkable metamodel will make those meanings enforceable.
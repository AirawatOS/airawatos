# Participants & the Network

*Who is who in the system, and how separate organizations work together without giving up control of their data.*

## Two ideas at once

AirawatOS is built on two independent ideas:

- **Multi-tenant** — each organization gets its own private, walled-off workspace (its **tenant**) for
  its own data. Your data is isolated from everyone else's.
- **Multi-participant** — many different organizations build the pieces (the drivers, engines, apps)
  and plug them in.

Holding these together is the **Network** — the shared trust layer: one register of who's who, one
agreed vocabulary, one signing authority. Each deployment runs its tenants' private data and shares
only governed vocabulary and certified components. The rule that ties it together: **nothing leaves a
tenant without a signed permission.**

## The cast of participants

A **participant** is any *organization* playing a role. Roles are per-interaction — the same
organization can consume data in one exchange and provide derived data in another. The main roles:

- **Participant / Tenant** — an organization in the network and its private workspace. Usually one
  organization, one tenant.
- **Network Authority (AirawatNetwork)** — the neutral standards body. It runs the register of
  participants, the shared vocabulary, the certification (it is the certificate authority), the
  directory, and the marketplace. Think "building codes plus a notary."
- **Operator** — runs a deployment (the actual servers) and sets participants up on it. Deliberately
  replaceable "plumbing."
- **Developer** — builds and *publishes* components to the marketplace.
- **Provider / Agency** — exposes data, engines, or rules and answers requests about them (a pollution
  board, a disaster authority, a statistics office).
- **Consumer** — an app or agent that discovers providers, asks them for data, and assembles the
  answer for a person.
- **Steward** — a participant's authority over *its own* data: the one who signs the permission slips.
- **Resident** — an end-user of a tenant: files reports, holds documents, receives services. A resident
  is *not* a participant.

> One separation matters for trust: the Network Authority governs and certifies, but should **not**
> publish software — a certifier signing its own software would break the "separation of duties." So
> the authority certifies, and a developer participant publishes. (Today the platform is still moving
> the last components over to fully honour this split — it's the intended model, not yet fully in place.)

## Identity: logging in makes you part of the Network

Each tenant runs its own login (its own identity provider). The clever part: when you log into *your*
tenant, the Network already accepts you. It reads which tenant issued your login and checks that
tenant's published keys. There is **no separate Network account** — network identity is *derived* from
your tenant login. It's the same pattern universities use to let you log in anywhere with your home
credentials.

Because the *tenant* (not the operator) is the issuer of identity, a tenant is **portable**: move it to
a different operator and its users, their credentials, and its identity namespace are unchanged. That is
the sovereignty guarantee in practice — the operator is plumbing, the tenant owns its identity.

Everyone can authenticate; what differs is **what you're allowed to do**, in three tiers: read the
public directory and specs (anyone), act on behalf of your participant (attributed to you), or approve
and certify (stewards). Network-facing roles are granted by your own tenant's admin — there is no
parallel hierarchy to climb.

## Working across boundaries: formal, signed, consented

Participants don't "chat" with each other in AirawatOS. Every cross-boundary exchange is a **formal,
typed request** — a data-sharing request, a service request, or an event subscription. Each one is:

- **authenticated and signed**, so the receiver knows exactly who is asking;
- **default-deny** — the owner of the data decides whether to answer;
- **consented and audited** — there's a record of what was shared and why.

Participants sign their messages with their own keys, and the keys stay in each deployment's own vault —
the hub that relays messages holds no private keys and can't forge anyone's signature. So you trust
*the signed object*, not the messenger.

**A worked example.** A national statistics office publishes a consumer-price index as governed data in
its own tenant. Another organization — say a city running a cost-of-living analysis — wants to use it.
It doesn't get a copy of the statistics office's database; it makes a formal, signed **data-sharing
request**. The statistics office (the steward of that data) authorises a *read-only* share. Now the
city can read the price-index facts, and every value it displays still carries its true source: "from
the national statistics office." Nobody's raw database was handed over, the owner decided, and the
attribution survives the journey.

## Finding each other: the directory

Participants discover each other through a **directory** — like a phone book plus service discovery.
Each entry says who a participant is, what jurisdiction it covers, what it has published (and to whom),
and its trust info (its certificate and public key). The directory only *advertises*; the owning tenant
still authorises each actual request at the moment it's made. Private data may be listed but never read
straight from the directory.

## Joining the network

A new deployment joins by registering as a **participant** (the organization), then connecting an
**instance** (the running deployment); a steward approves it, which provisions its credentials.
Admitting a brand-new deployment is a deliberate, admin-gated act — its keys are registered on the
Network on purpose, never self-serve.

## Where this stands today

**Working now:** the split between running a deployment and running the network authority; the
join-and-approve membership flow; tenant-per-organization identity where logging into your tenant makes
you Network-authenticated; the public register of participants; signed, consented, formal exchanges
between tenants (including signed message relay with the keys held per-deployment); and the first
"resolve a rule from the responsible authority" lookups.

**Being built:** the full signed **jurisdiction directory** with automatic resolution up the chain
(the public participant register is live; the richer tree directory is designed, not yet running);
broader cross-provider discovery over that directory; and completing the "authority certifies /
developer publishes" separation across every component.

# Zero-Trust Architecture

*How the platform runs other people's code without trusting it.*

## The problem

AirawatOS is a marketplace. A city installs a piece of software — a "component" — that some
developer, maybe on the other side of the world, wrote and published. That component then runs
inside the city's own workspace, next to the city's own data.

Normally you would have to *trust* that code: trust that it only does what it claims, trust that it
won't quietly copy data somewhere, trust that it won't reach a system it shouldn't. That kind of
trust does not scale, and it is exactly how things go wrong.

AirawatOS takes a different stance: **it never trusts the component's code at all.** Instead it
trusts two things it can actually check — a **certificate** and the **host**.

## The two things we trust instead

**1. The certificate.** Before any component can be sold or run, it is checked and cryptographically
signed. The signature covers a fingerprint (a "digest") of the exact code. When the platform is about
to run a component, it re-computes that fingerprint and compares it to the certificate. If they don't
match — if even one line of the code was swapped after signing — it **refuses to run**. So the
platform isn't trusting the developer's promise; it is checking the code is exactly the certified code.

**2. The host.** The component runs inside a **host** that is built so the component has no way to
do anything it wasn't granted. This is the key idea, and it's stronger than a rule that says "you're
not allowed to." The forbidden things are simply **not there**:

- No open connection to the internet.
- No access to the disk.
- No passwords, keys, or tokens lying around.
- No handle to the database.

As the design puts it: there is *no socket to try*. Anything the component didn't ask for isn't merely
denied — it is **absent**.

## The single door: the broker

If a component has no direct access to anything, how does it do useful work — read data, call an
outside website, use a secret?

Through one guarded channel called the **broker**. The broker is the component's *only* door to the
outside world. And the broker only lets through exactly what the component **declared up front** in
its description file:

- the kinds of data it may **read**,
- the kinds it may **write**,
- the specific outside websites it may **call** (and how often),
- the **secrets** it needs — which are handed over only at the moment of use, never stored in the
  code or the image.

The broker holds the real credentials; the component never sees them. And every time the component
writes something, the broker stamps it with the component's true, un-fakeable identity
(`component://<name>@<version>`). So no action inside the platform is anonymous — every value can be
traced back to the exact component and version that produced it. (This traceability idea runs through
the whole platform — see [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/).)

## Least privilege, by construction

When a component runs, the host mints it a short-lived **run-token** that carries *precisely* the
permissions it declared — no more. And those declared permissions must be a subset of what the
certificate approved. So there are two independent checks agreeing on what the component may do: the
certificate (at publish time) and the run-token (at run time).

This is what lets a city read a component's permissions *before* installing it and know that list is
the complete and enforced truth of what the software can touch.

## Why "absent, not denied" matters

A firewall rule that says "block this" can be misconfigured, bypassed, or forgotten. An ability that
doesn't exist can't be any of those things. AirawatOS leans on this everywhere: the safest permission
is the one that was never wired up. The strength of the sandbox around a component (how strong the
walls are) can be dialed up over time — from a simple isolated process to heavier isolation — without
the component ever knowing or needing to change. The contract it runs under stays the same.

## Two separate ideas people mix up

- **Certifying a component** proves *the code was checked and hasn't changed*. This is live today.
- **Certifying an operator** is a *different* axis — it's about trusting the machine and the people
  running a whole deployment (see [Runtimes & Delivery](/developer/deep-dives/runtimes/)). It is an
  early, evolving capability, and it is a lighter "attest what you're running" check — deliberately
  not the heavyweight hardware attestation you may have read about elsewhere.

## Where this stands today

**Working now:** the broker as a component's single door, with declared-only reads/writes/outside-calls
and un-fakeable attribution on every write, proven end-to-end for real components; the "refuse to run
if the code doesn't match its certificate" check; the run-token carrying only declared permissions.

**Being built:** the strongest isolation tier — a **clean room** where even the operator can't see the
data a component processes — is designed but not yet built. Operator certification is an early
capability, with the full signed lifecycle still to come.

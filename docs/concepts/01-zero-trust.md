# Zero-Trust Architecture

*How the platform runs other people's code without trusting it.*

## The problem

An organization — a city, a health department, a court, a statistics office — installs a piece of
software (a "component") from a marketplace. Some developer, maybe on the other side of the world,
wrote and published that component. Once installed, it runs inside that organization's own workspace,
next to its own data.

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

> **Two tiers of confinement — be precise about which you're reading.** The strongest form — a component
> with *literally no socket*, every secret used only inside the kernel — is real today for **light,
> in-process components** that reach the outside through the broker's fetch path. **Heavier components** (a
> satellite-imagery driver, an ML trainer) run in a **locked, certified container**: their code is mounted
> read-only and signature-checked, they may act only within their **declared** reads / writes / outside-hosts
> / secrets, and every write is attributed — but the container runs its own process, receives its declared
> secrets in its environment, and makes its own outbound calls to its declared hosts. So read the absolutes
> above as the confinement **contract**; the fully socket-less clean room is the target tier, still being built.

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
(`component://<name>`). So no action inside the platform is anonymous — every value can be
traced back to the exact component and version that produced it. (This traceability idea runs through
the whole platform — see [The Shared Vocabulary](/developer/deep-dives/shared-vocabulary/).)

**A worked example.** Take a driver that fetches hourly air-quality readings from an outside sensor
network's website. Its description declares exactly three things: it may **call** that one website
(and no other), it may **write** the "sensor reading" data type (and nothing else), and it needs one
**secret** — the API key for that website. When it runs:

- it can reach that one website — but not the internet at large, not another agency's server, nothing
  else;
- it can write sensor readings — but it cannot read residents' records or write anywhere else;
- the API key is handed to it only for the moment of the call, never left sitting in its code;
- and every reading it writes is stamped as coming from that driver, at that version.

If a later version of the driver quietly tried to also call a data-broker website to sell what it
collected, that call would simply fail — the door was never opened. And because the code's fingerprint
would no longer match its certificate, the tampered version wouldn't run at all.

## Where that one door leads: the kernel fans out

A component has exactly one door — the broker — and the broker is the run-token-authenticated face of
the **kernel**. So a fair question is: if the component can only talk to the broker, how does it ever
use a secret, read a file, or call an AI model? The answer is that it *doesn't* — the **kernel** does,
on its behalf. The component asks the broker for a result; the kernel is the hub that reaches out to
the supporting services and brings the result back. The component never names those services and never
holds a connection to any of them:

- **Secrets.** On the broker-mediated fetch path, when a component makes a declared outside call the
  kernel fetches the key from Secrets and makes the call itself — so the component never sees it. A
  heavier container component instead receives its **declared** secrets in its run environment (from the
  vault, at start) and makes its own outbound calls to its declared hosts.
- **File Store.** Blob reads and writes are mediated by the kernel; the component asks, the kernel
  fetches or stores.
- **Model Gateway.** An AI completion goes component → broker → kernel → Model Gateway, with the
  provider keys staying in the vault the whole time.
- **Network.** To authorize a read or write, the kernel calls the Network to resolve the schema and
  verify the grant — the component just issues the read or write.
- **Event dispatcher.** Every write the kernel records emits an event out to the **event dispatcher**
  (the "automation" service), which fans it to subscribers. The component doesn't publish events;
  writing *is* the event.

So those services are indeed reached "through the kernel" — but it's the kernel calling them, triggered
by a component that only ever spoke to its one door.

## Two services act *on* components, not called *by* them

Two supporting services are the exception that proves the rule — a component never calls them, because
they are the **control plane** that runs the component in the first place:

- **Scheduler** fires on time and asks the Runtime Manager to start a component (one of the ways work
  begins).
- **Runtime Manager** is the trusted invoker: it starts the confined component under its **run-token**
  (a per-component, per-tenant token minted by the kernel when the component is installed) and injects
  only that component's declared capabilities.

A component can't call these — they call it into existence. (Workflow and Decision are similar: they
orchestrate cases from the outside and persist their own state through the kernel registry, like
everyone else.)

## Two lanes, one identity

There is a second door in the platform, and it's important not to confuse it with the broker. **Apps**
— the screens a person clicks — don't run confined with a run-token; they act as the logged-in user.
Their door is the **app host**'s `/bridge/*` channel, a user-session door that mediates to the
kernel, network, and file store on the person's behalf. So the whole platform reduces to two lanes:

- **Component runtime → broker (the kernel's confined face) → kernel fans out** to the supporting
  services.
- **App (browser) → app host `/bridge/*` → the app host fans out** on the logged-in user's behalf.

```
  Lane A — a component acts (confined, run-token)
    component ──► broker ──► kernel ──► { secrets · file store · model gateway
                (the only door)   (fans out)    · network · event dispatcher }

  Lane B — a person acts (session token)
    browser / app ──► app-host  /bridge/*  ──► { kernel · network · file store }

  underneath both:  identity — mints the tokens every service checks
```

*Every path a component or app can take crosses a door the platform controls.*

Underneath **both** lanes sits **Identity** — it issues the verified tokens (run-tokens for
components, session tokens for users) that every service checks before it trusts a caller. That's what
lets two doors stay safe: neither the component nor the app is trusted, only the token it carries and
the service that minted it.

## Least privilege, by construction

When a component is installed, the kernel mints it a **run-token** that carries *precisely* the
permissions it declared — no more — and every run executes under that token. And those declared
permissions must be a subset of what the certificate approved. So there are two independent checks agreeing on what the component may do: the
certificate (at publish time) and the run-token (at run time).

This is what lets an organization read a component's permissions *before* installing it and know that
list is the complete and enforced truth of what the software can touch.

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

**Working now:** the broker as the data door — declared-only **reads and writes** with un-fakeable
attribution on every write, enforced in the kernel for every component; **broker-mediated outside-calls**
with the key injected server-side (the light, in-process path); the "refuse to run if the code doesn't
match its certificate" check; and the run-token carrying only declared permissions.

**Being built:** the strongest isolation tier — a **clean room** where a component has literally no
socket and even the operator can't see the data it processes — is designed but not yet built. Today's
**heavier components run in a locked, certified container** with their declared capabilities, but they
hold their declared secrets in-environment and make their own outbound calls to their declared hosts;
pulling those onto the broker-mediated path (so the declared host-list is network-enforced too) is part
of this work. Operator certification is an early capability, with the full signed lifecycle still to come.

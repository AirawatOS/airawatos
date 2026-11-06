# Airawat in plain words

**A shared, trusted space where public agencies work together — and residents are served as one.**

*Draft v0.3 · November 2026 · For officials, partners, policymakers and anyone new to Airawat.
Engineers: see [Airawat for engineers](AIRAWAT-FOR-ENGINEERS.md).*

---

## Why this matters

A city is run by many agencies: the municipal corporation, the water board, the transport authority, the
pollution control board, the disaster management authority, the health department. Each keeps its own
records, on its own systems, inside its own boundary on the map.

That worked when problems stayed inside one agency. They don't any more.

- **Climate doesn't respect boundaries.** A flood starts with rain upstream, runs through drains owned by
  three agencies, and pools in the next town. Polluted air drifts across districts. A heatwave hits the
  whole region at once.
- **People move.** A family that moves for work has to prove who they are again, re-register everywhere,
  and start from zero with every office.

Today, agencies coordinate by phone calls and spreadsheets, and residents carry the burden of the gaps.

```text
   TODAY

   Water Board     Municipal Corp     Pollution Board     Disaster Authority     Health Dept
   [ own data ]    [ own data ]       [ own data ]        [ own data ]           [ own data ]

        no easy way to share          residents repeat themselves at every counter
        decisions made without the full picture       little record of who decided what
```

Airawat is a shared, trusted space that fixes this — without asking any agency to give up control of its
own data.

---

## The four questions everyone asks

### 1. How can agencies share data without losing control of it?

Each agency **keeps its own data**. Nothing is pooled into someone else's system.

When one agency wants to use another's data, there must be a **data-sharing permission** on file — like a
sanction order. It says exactly who may see what, and it can be withdrawn at any time.

Everything goes through a **shared register**: think of a public records office where every entry is
signed and dated, nothing is ever erased, and every request to look is checked against the permissions on
file.

```text
   Water Board          Municipal Corp          Disaster Authority
       |                      |                         |
       | adds pump readings   | adds drain levels       | asks to see both
       v                      v                         v
   +---------------------------------------------------------------+
   |                      THE SHARED REGISTER                       |
   |   every entry: who added it, when, signed - never erased       |
   |   every look:  checked against the permissions on file         |
   +---------------------------------------------------------------+
                                |
                     permission on file?
                    /                    \
                  yes                     no
                   |                       |
          sees the data               refused
          (the look is noted)         (the refusal is noted)
```

Agencies join a **shared space** for their region — an **Urban Network** — with its own charter and its own
authorised officers, like a joint committee. No single agency owns it.

### 2. How can residents get services from many agencies without repeating themselves?

Each resident has **one account**, with an address like a UPI ID — say `meera@metro`. They prove who they
are **once**. They can use it from the city's app, an agency portal, or even an app they already use, such
as their employer's.

Their certificates and records sit in a **document locker**, like DigiLocker, that they control.

```text
                         meera@metro
                              |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
    Water       School      Clinic      Bus pass    Relief
    connection  admission   registration            scheme

   she proves who she is ONCE · each agency sees only what she allows
   she sees all her requests, from all agencies, in one place
```

The apps are just doors. The account belongs to the resident, not to any agency or app.

### 3. Who can see my data — and can I say no?

Your personal data needs **two permissions** before anyone can see it:

```text
   1. the agency must be ALLOWED to see this kind of data   (permission on file)
   2. YOU must agree, for this purpose, for this long       (your permission)

   both present  -> they can see it
   either missing -> they can't
```

You can see every permission you've given, and **withdraw** any of them. Where the law requires, your
personal data can be **truly erased**.

Data that isn't about anyone personally — drain levels, air quality, bus locations — needs only the
agency's permission, and some of it is simply public.

### 4. When something goes wrong, how do we know who decided what?

Every important decision leaves **reasons on file**, like a file noting: who decided, on what basis, using
which information, at what moment.

These go into a **tamper-proof log** — think of a bound register with numbered pages, where removing or
changing a page would be noticed.

If a resident disagrees with a decision about them, they can **challenge** it. Someone other than the
original decision-maker reviews it, and the outcome is recorded alongside the original. Nothing is
quietly rewritten.

---

## A monsoon in the Metro region

```text
   1 AGENCIES JOIN          2 THEY AGREE WHAT TO SHARE      3 DATA COMES IN
   Water Board, both        Disaster Authority may see      drain sensors, pump status,
   municipalities,          drains + pumps in the whole     rainfall forecasts -
   Transport, Health,       region; Transport may see       each agency's own data
   Disaster Authority       flood alerts; air quality       stays its own
                            is public
                                     |
                                     v
   4 THE PICTURE COMES TOGETHER                 5 PEOPLE DECIDE, AGENCIES ACT
   a flood-risk model combines rain,            the duty officer issues the alert;
   both cities' drains and pump status          Water Board moves pumps,
   -> ward-by-ward risk for the WHOLE region    Transport diverts buses,
   -> it recommends; it does not decide         crews clear drains,
                                                residents get the alert on any app
                                     |
                                     v
   6 AFTERWARDS: the register shows exactly what was known, and who decided what, hour by hour
```

The same arrangement works in a heatwave: the health department combines temperature, air quality and
heat-illness numbers to flag wards at risk; the city opens cooling centres; the water board adds supply.
Different hazard, same shared space, same rules.

---

## Meera moves to a new city

Meera, a construction worker, moves with her family to the Metro region.

1. **She creates her account** on the city's app and proves who she is through an approved government
   source. Her ID number is never shown to the agencies.
2. **She applies for what she needs** — a water connection, school places for her children, a clinic, a bus
   pass — from one app, across four agencies.
3. **Her history can follow her.** With her permission, her children's school records and her clinic
   history come from her old city. Each transfer needs both permissions: the agency's, and hers.
4. **She isn't shut out for lacking paperwork.** Where she has no document — say, for her income — she can
   declare it herself. The declaration is signed and marked as self-declared, so everyone knows what it
   rests on.
5. **The city sees what it needs to plan — not who she is.** Planners see how many new arrivals each ward
   has and what services they need, as totals, without tracking individuals.
6. **In the monsoon,** she gets the flood alert on her phone. If she qualifies for relief, it's approved by
   a named officer against the scheme's budget, and paid through the normal payment system.

---

## The same idea, other uses

The Urban Network is one use. The same arrangement works wherever independent organisations need to trust
each other:

- **Livelihoods:** a delivery rider's training, certificates and work history travel with him from one
  employer to the next; a labour department funds training and can see where every rupee went.
- **Health:** clinics and labs share records, with the patient's permission.
- **Environment:** monitoring agencies across states share air and water data for the same airshed or river.

---

## Data and AI, used responsibly

Agencies bring in their own data — from sensors, existing systems and files — and build tools on top of it:
risk maps, dashboards, forecasts.

AI models can help, under clear rules:

- **Models recommend; people decide** — or an automatic rule that a named officer approved in advance, and
  remains accountable for.
- **Every recommendation records which model produced it,** so it can be explained and checked later.
- **Agencies choose approved AI providers** — for example, ones hosted in India.
- **A good tool can travel.** One city's flood early-warning kit can be checked and offered to other cities,
  so good work spreads.

---

## Ten promises

1. Your login proves who you are — it never, by itself, lets you do anything.
2. Every permission is written down, and says who gave it.
3. Belonging to an agency or a group doesn't, by itself, give you any power.
4. Your personal data needs the agency's permission **and** yours.
5. If anything needed to make a decision is missing, the answer is no.
6. Software programs need permission too — being "inside" proves nothing.
7. Records are never overwritten; the history is kept and signed.
8. Your personal data can be truly erased when the law or you require it.
9. Every important decision has its reasons on file, and can be challenged.
10. The people who run the servers can't decide who is allowed to do what.

---

## Where things stand (November 2026)

This describes where Airawat is heading. Honestly, today:

- **Working:** the shared register, with full history and signatures; bringing data in from sensors and
  systems; risk maps and dashboards; shared spaces for agencies with written permissions (on the development
  system); a test suite that checks the system against its own rules.
- **Partly working:** services across agencies; certificates and document lockers; residents' permissions
  (designed, not yet applied everywhere).
- **Designed, not yet built:** resident accounts with their own addresses; records that follow residents
  between cities; budget tracking for relief and subsidies; erasure of personal data.
- **The live system** runs an older version; the improved version will be released in careful stages.

---

## Want to know more?

| If you want… | Read |
|---|---|
| What a word means | [Glossary](specs/GLOSSARY.md) |
| How it's built | [Airawat for engineers](AIRAWAT-FOR-ENGINEERS.md) |
| The exact rules | [Specifications](specs/README.md) |

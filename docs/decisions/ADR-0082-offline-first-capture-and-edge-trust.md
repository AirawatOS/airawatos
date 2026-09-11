# ADR-0082 — Offline-first capture & edge trust (connectivity tiers)

**Status:** Proposed
**Relates to:** ADR-0024 (participant message signing — Ed25519), ADR-0026 (agent = signed scoped delegate),
ADR-0049 (document wallet & verifiable credentials), ADR-0052 (authenticated, attributed registry writes —
W3C-PROV envelope), ADR-0030/0051 (broker + certified components), ADR-0023 (federation interaction model),
the P1 bitemporal registry (valid_time vs asserted_at), ADR-0077 (design system / app runtime), the Field
Report app + `signal.incident` triage spine.

## Context
AirawatOS assumes **connectivity for writes**. Every governed write is mediated by the kernel: schema
validation, the attributed-write envelope (ADR-0052), tenant scoping, and receipt issuance all happen
server-side. Reads can be cached in the browser, but a field worker or citizen in a **no-coverage area cannot
file anything** — no grievance, no incident, no inspection, no meter reading. Large parts of the jurisdictions
AirawatOS is meant to serve (interior wards, hill villages, disaster zones where towers are down) have
**absent or intermittent** mobile data.

The naive fix — "build an offline mobile app" — is a trap if it means running the governed stack on the
device. The kernel/registry/broker are the **trust anchor**; replicating them onto an untrusted phone would
dissolve the zero-trust guarantees the whole platform rests on. But the opposite extreme — refuse all input
without a live connection — makes the platform useless exactly where civic need is highest.

The resolution is that AirawatOS **already holds the primitives** for trustworthy disconnected capture; they
have simply never been composed for the offline case:
- **Bitemporal registry (P1):** every fact carries `valid_time` (when it happened) distinct from `asserted_at`
  (when the registry learned it). A record captured offline and synced hours later is *not* a special case —
  it is exactly a fact whose valid_time precedes its asserted_at.
- **Ed25519 signing (ADR-0024) + scoped delegation (ADR-0026) + VCs (ADR-0049):** authority can be delegated
  to a narrowly-scoped key held by an actor — including a field device — so a payload can be signed by its
  originator, not only by a live server session.
- **Attributed writes (ADR-0052):** the write envelope already binds *who asserted this* and *on what evidence*.

## Decision

### 1. Connectivity is a spectrum; match a mechanism to each tier — do NOT ship one monolith "offline app"
| Tier | Field reality | Mechanism |
|---|---|---|
| **Online** | offices, towns | normal web apps (unchanged) |
| **Intermittent** | patchy rural data | **offline-first PWA**: service-worker-cached shell + forms + AOI map tiles; capture to a local signed **outbox**; sync on reconnect |
| **No data, has SMS/USSD** | feature phones, weak signal | **narrowband intake gateway** → the same `signal.incident` / grievance spine |
| **Full dead zone** | interior, disaster | **store-and-carry**: a signed outbox relayed by a *sync-mule* (a supervisor's device over BLE/local wifi) or a *village edge node* that batches and uploads when it next has backhaul |

### 2. Edge-trust model — move signing to CAPTURE time, relay later (governance is NOT relaxed)
The core rule: **a record is signed by a scoped device credential at the moment of capture, queued, and later
relayed to the kernel, which verifies the signature + the credential's scope before it becomes a governed
fact.** Concretely:

- **Device/holder credential.** A field worker's device is provisioned with a **scoped credential** — a VC
  (ADR-0049) or a delegated agent key (ADR-0026) — that authorises exactly the capture verbs/schemas it needs
  (e.g. `write signal.incident` within jurisdiction X), time-boxed and revocable. The device never holds a
  tenant or steward key.
- **Sign at capture.** On submit-with-no-signal the app builds the record, stamps `valid_time = now` (device
  clock, plus a monotonic capture counter), and **signs it with the device credential**. The signed record
  lands in a local **outbox** (IndexedDB / native store). It is tamper-evident from that instant.
- **Relay + verify on reconnect.** When connectivity returns, the outbox drains to a broker relay endpoint.
  The kernel **verifies the device signature + the credential's scope + the schema**, then performs the
  attributed write (ADR-0052) with `asserted_at = now`, preserving the device's `valid_time`. A capture that
  fails verification is quarantined, never silently written.
- **Idempotent + replay-safe.** Each capture carries a device-scoped UUID; the relay is idempotent on it, so a
  mule that delivers the same outbox twice produces one fact. Signatures + the capture counter defeat replay.

This keeps the trust anchor server-side while letting the *edge* produce records the anchor can later trust.

### 3. What explicitly stays server-side (non-goals)
- **No kernel/registry/broker on the device.** No offline schema authoring, no offline certification, no
  offline decisions/approvals that require authority the device doesn't hold.
- **Offline reads are best-effort, as-of snapshots**, clearly labelled with their cache time. Authoritative
  reads (balances, approvals, live status) require connectivity.
- **Decisions remain online.** Offline capture feeds the *sense* half of a loop; the decision/approval half
  (ADR-0029/0046) runs when the record reaches the kernel and a human/authority acts.

### 4. Surfaces
- **PWA, not native, first.** An installable offline-first PWA (service worker + IndexedDB outbox + cached AOI
  tiles) reaches the Android reality with no app-store friction and reuses the existing web apps. Go native
  **only** when we need BLE peer-sync (the mule) or robust background sync — a thin native shell can wrap the
  same PWA and add those.
- **Field Report is the first offline surface** (it already captures media + GPS into `signal.incident`).
  A submit with no signal shows "queued", a sync badge shows the outbox depth, and pins/receipts appear once
  synced with `valid_time` = when it was actually reported.
- **Narrowband intake** (SMS/USSD shortcode) is a server-side gateway that maps a structured message to the
  same grievance/incident schema — no device app at all.

## Consequences
- **Reach:** the platform works — for the capture half — across intermittent, narrowband, and dead-zone tiers,
  without weakening the write-path trust model.
- **Honest provenance:** offline records are first-class and visibly time-true (valid_time vs asserted_at), not
  back-dated fabrications; unverifiable captures are quarantined, consistent with the no-synthetic-data rule.
- **New surfaces to build/operate:** a device-credential issuance + revocation flow, an outbox/sync client, a
  broker relay-verify endpoint, and (later) a mule/edge-node transport. Clock skew, revocation-after-capture,
  and outbox size need explicit handling (below).
- **Edge cases to design:** device clock skew (carry a server time-sync on last contact + a capture counter;
  the kernel may clamp implausible valid_times and flag them); a credential revoked *after* a valid capture
  (accept the capture if it was signed while valid — the signed timestamp + credential validity window
  decide); outbox durability + cap (evict only after confirmed relay).

## Rollout (proposed slices — each independently shippable)
1. **S1 — Edge credential + relay-verify.** Provision a scoped device VC/agent key; add a broker relay endpoint
   that verifies a signed capture + scope and performs the attributed write with device `valid_time`. Prove
   with a scripted signed-capture → relay → governed `signal.incident` on a test tenant.
2. **S2 — Offline Field Report PWA.** Service worker caches shell + form + AOI tiles; offline submit → signed
   IndexedDB outbox → sync-on-reconnect against S1. Prove airplane-mode capture → reconnect → pin appears.
3. **S3 — Narrowband intake.** SMS/USSD gateway → grievance/incident spine (feature-phone reach).
4. **S4 — Store-and-carry.** BLE/local-wifi peer sync (sync-mule) and/or a village edge-node batcher for true
   dead zones; idempotent multi-hop delivery.

## Open questions
- Credential issuance UX for low-literacy field workers (QR enrolment via a supervisor? tie to the Document
  Wallet?).
- Edge-node form factor + who operates it (panchayat kiosk? supervisor phone only?).
- Whether offline capture should be a **generic capability** any capture app opts into (an "offline outbox"
  aos.js module) rather than bespoke per app — almost certainly yes after S2.

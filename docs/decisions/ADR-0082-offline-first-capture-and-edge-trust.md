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

## Architecture (as built — S1–S3 + Citizen-Services routing)

Every connectivity tier funnels through **one channel-neutral intake core** into the **one governed spine**. Each
channel is a thin *adapter* differing only in how it proves admission and how it normalises its payload; after that
they all call `_intake_core`, which parses, hashes any phone/wa-id (never storing raw PII), and forks on intent.

```
 CONNECTIVITY TIER        CHANNEL / ADAPTER              AUTH AT THE DOOR            ENTRY POINT
════════════════════════════════════════════════════════════════════════════════════════════════════
 No signal / dead zone    Field Report PWA               device Ed25519 key +        /bridge/offline-relay
 (capture OFFLINE)        · sign on device               credential.device VC        (verify VC sig +
                          · IndexedDB signed outbox        (issuer steward-signed)     capture sig + scope + window)
                          · sync on reconnect
 No data (2G) / feature   SMS / USSD                     shared secret               /bridge/sms-intake
 phone                    (telco webhook)                (X-Gateway-Token)           /bridge/message-intake
 Intermittent data        WhatsApp                       Meta HMAC                   /bridge/whatsapp
                          (text · location pin ·         (X-Hub-Signature-256)
                           media · interactive)
 Online (normal)          web apps                       session cookie              normal /bridge/*
        │                        │                              │                           │
        └────────────────────────┴──────────────────────────────┴───────────────────────────┘
                                             ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │            _intake_core   (channel-neutral)                  │
                    │  1. LLM parse → {intent, category, severity, one_line,       │
                    │       service_query, place}                                  │
                    │  2. phone / wa-id → SALTED HASH   (never store raw PII)       │
                    │  3. native location pin → lat/lng directly (no geocoding)     │
                    └───────────────────────────────┬─────────────────────────────┘
                                                     │  fork on INTENT
                    ┌────────────────────────────────┴───────────────────────────────┐
                    ▼                                                                  ▼
          intent = grievance / info                                    intent = service_request
                    │                                                                  │
                    ▼                                                     service/search(service_query)
        write governed  signal.incident                                              │
        (citizen tier · source=channel ·                                     match offering?
         reporter=hash · valid_time)                                     ┌────────────┴────────────┐
                    │                                                 yes│                       no│
                    ▼                                                    ▼                         ▼
          report-triage engine                                open governed  platform.case   (fallback)
          → classify → civic.issue                            (service ENQUIRY · links the     → incident
          → route if actionable                                offering · current_step:enquiry)   (never lost)
                    │                                                    │
                    ▼                                                    ▼
        agency Inbox / City Scan pin                          service desk / Inbox
                                                              (identity step-up → full
                                                               ADR-0067 delegated application)

 ══ THE GOVERNED SPINE — one trust anchor, server-side, NEVER on the device ══
   kernel: schema-validate · attributed write (who / on-what) · BITEMPORAL
           (valid_time = when it happened · asserted_at = when it synced) · signed receipt
```

**Reading it.** Trust travels with the *message*, not the transport: the offline lane signs on the device at capture
time (tamper-evident in the outbox, re-verified at the kernel); SMS/WhatsApp are the unverified **citizen** tier —
enough to *open* work, held for verification before it drives action. A complaint becomes a `signal.incident`; an "I
need X" becomes a `platform.case` on the ADR-0067 service spine; an unmatched service request still lands as an
incident so nothing is dropped. Devices and gateways only *capture and sign* — only the kernel validates, attributes,
and issues receipts, and bitemporality is what makes a report filed offline yesterday an honest record rather than a
back-dated one.

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

## Rollout (each independently shippable)
1. **S1 — Edge credential + relay-verify. ✅ DONE (proven on nashik).** `credential.device` VC + `/bridge/offline-relay`:
   verifies the VC signature (issuer steward) + the device-key capture signature + scope + jurisdiction + validity
   window + idempotency, then writes the attributed `signal.incident` with the capture's `valid_time`. Tamper /
   expired-VC / out-of-scope / replay all quarantined. (En route, fixed a platform bug: a duplicate `_require_member`
   shadowed the issuer gate, 500ing all VC issuance.)
2. **S2 — Offline Field Report PWA. ✅ DONE (proven in-browser).** WebCrypto Ed25519 device key (non-extractable, in
   IndexedDB) + `/bridge/provision-device` VC + a JS JCS byte-identical to the kernel's, signed IndexedDB outbox,
   sync via S1; service-worker shell cache. Interop (browser Ed25519 + JCS ↔ Python verify) confirmed live.
   *S2b remaining:* offline **launch** through the shell iframe; re-publish the bundle for durability; a generic
   `aos.js` outbox module any capture app opts into.
3. **S3 — Narrowband intake + channel generalization. ✅ DONE (proven).** Channel-neutral `_intake_core`; adapters
   `/bridge/sms-intake` (shared secret), `/bridge/message-intake` (generic/USSD), `/bridge/whatsapp` (Meta HMAC;
   text / native location pin → lat/lng / interactive / media). Phone stored only as a salted hash.
   **Citizen-Services routing:** `service_request` intent → `service/search` → open a governed `platform.case` service
   enquiry (ADR-0067), grievance/info → incident. *Remaining:* WhatsApp media→filestore + GET webhook-verify;
   identity/assurance step-up to turn an enquiry into a full delegated application.
4. **S4 — Store-and-carry.** BLE/local-wifi peer sync (sync-mule) and/or a village edge-node batcher for true
   dead zones; idempotent multi-hop delivery. *(Not started.)*

## Open questions
- Credential issuance UX for low-literacy field workers (QR enrolment via a supervisor? tie to the Document
  Wallet?).
- Edge-node form factor + who operates it (panchayat kiosk? supervisor phone only?).
- Whether offline capture should be a **generic capability** any capture app opts into (an "offline outbox"
  aos.js module) rather than bespoke per app — almost certainly yes after S2.

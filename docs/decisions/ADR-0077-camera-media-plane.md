# ADR-0077 — The media plane: the broker is the only door for *authority*; media bytes travel direct

- **Status:** Proposed (2026-09-08)
- **Deciders:** Airawat (platform steward), product owner
- **Composes / relates to:** MDK `SPEC-0004` (component execution + the broker — the single-door invariant this
  ADR is careful not to break), `PLAT-0001` / `PLAT-HOST-004` (one gate, many launchers — the clause that
  already permits a resident component), `PLAT-HOST-002/009` (point-of-use admission + artifact digest),
  `PLAT-HOST-005` (an app holds no component authority — why the viewer direction is a different mechanism),
  `PLAT-0002` (platform services — the file store), ADR-0062 (invocation, lifecycle & triggering — a run today
  is spawn→exit→receipt, which a stream is not), ADR-0063 (govern the control-plane verbs — `platform.media`
  must be governed like any other), ADR-0074 (operator-configurable platform services — the control-plane /
  data-plane separation this ADR borrows and applies one layer down), ADR-0067 (civic service federation — the
  grievance path a detection eventually lands in), `INT-0001` (`INT-REC-001`: an engine offers, an Authority
  decides), `drivers/kanpur-idss` (the broker-held-credential pattern this generalizes), `docs/plans/
  crowd-safety-mass-gathering-solution.md` (the `crowd-camera` slot this fills, and the privacy stance it
  deliberately departs from).

## Context

We are building a Video Management System **on** AirawatOS rather than beside it. The governed half of a VMS —
which camera, what was detected, who viewed it, what was decided, what may be deleted — is exactly what this
platform is good at. The other half is a continuous, high-bandwidth byte stream, and nothing in the platform
has ever carried one.

Three properties of a camera collide with three assumptions the platform currently makes:

1. **A stream never ends.** ADR-0062 defines a run as trigger → spawn → exit code + attributed writes →
   receipt. A camera feed has no exit code. `host.py` has only `_launch_shim` and `_launch_l2`, both
   run-to-completion, and the scheduler's invoke path caps out around 1700s.
2. **RTSP is not HTTP.** `egress:` in a host manifest is an HTTP host plus a rate cap, enforced by the broker's
   `/v1/fetch`. A camera is `rtsp://10.x.x.x:554/...` on a private VLAN, speaking RTSP control plus RTP data,
   plus ONVIF/SOAP for discovery and PTZ. The broker has no notion of any of it.
3. **Video is large and continuous.** The reference broker is ~113 lines of Python doing request/response.
   N cameras × 2–4 Mbps, continuously, is not a bigger version of that workload; it is a different one.

The question this ADR settles is narrow and load-bearing: **how does a confined component reach a camera
without either breaking the single-door invariant or turning the broker into a media proxy?**

Two obvious answers, both wrong in different directions:

- **Grow the broker a stream capability.** The invariant survives literally and credentials never reach the
  component — but every video byte crosses a component whose auditability depends on being small. It becomes a
  bandwidth bottleneck, a single point of failure, and it must either learn RTSP/RTP/ONVIF in full or blindly
  tunnel. Blind tunnelling forfeits the property that makes the broker worth trusting: that it understands what
  it permits.
- **Declare a camera-network egress class, enforced at L2.** Zero data-path overhead, protocol-agnostic, and
  philosophically consistent with the ladder's own argument that L2 is stronger because the OS kernel enforces
  it. But the grant is coarse — "can reach the camera VLAN," not "can reach camera 47" — so per-camera
  authorization degrades to the driver policing itself, which is precisely the cooperative confinement L2 was
  introduced to stop being. Credentials land in the component. `prov.egress` audit becomes self-reported.
  Tier-4 behavioural conformance goes blind exactly where the stakes are highest.

Neither is acceptable for the component that handles the most sensitive data in the system.

## Decision

**Separate authority from bytes.**

| Plane | Path | Carries |
|---|---|---|
| **Control** | broker → delegated **media service** (`platform.media`) | camera discovery, credential resolution, per-camera grant check, ONVIF/PTZ, stream open/close, the session audit record |
| **Data** | direct, on a narrow declared grant | RTP/RTSP media bytes **only**, after the control plane has authorized that session |

The invariant restates cleanly and survives:

> **The broker is the only door for *authority*. The data path carries no authority of its own.**

Three commitments make that true rather than aspirational.

### 1. The control plane is a *delegated* service, not the broker itself

The broker does **not** learn RTSP. It delegates to a dedicated, internal-token-gated **media service**, exactly
as it already delegates secrets: `platform.secret` is a separate service that only the broker may call, and the
broker resolves `(tenant, component, egress)` from the run record before delegating so a component cannot forge
its own identity. `platform.media` follows that established shape.

This is the difference between the two rejected options and this one. The broker stays ~113 lines and stays
auditable. RTSP, RTP, and ONVIF knowledge lands in a component whose job that is — one that may be written in
Go or Rust for throughput without touching the kernel or the trust root.

`platform.media` is a **governed verb** (ADR-0063) and a tier-appropriate platform service (ADR-0074): it holds
camera credentials and sits in the path of the most sensitive data on the system, so it is held to the
installed-platform-component bar, not the tenant-driver bar.

### 2. The data-plane grant must be *narrow*, and we must say so out loud

The design holds only if the network grant is genuinely per-session — ideally the runtime manager programs the
exact permitted 5-tuple, short-lived, at the moment the media service authorizes the session. If the grant
degrades to "the VLAN is reachable," we have landed back on the rejected Option B with extra ceremony.

**On a laptop dev setup it will degrade that way.** Stated here rather than discovered later.

Narrowness is not only the authorization story — it is what makes the *audit* story true. A broker-witnessed
session record proves what was **authorized**; only the narrow grant makes out-of-band access to camera 47
impossible. The two mechanisms are complementary, not alternatives. Without narrowness the session log records
intentions, not events.

### 3. Behavioural conformance recovers **asymmetrically** — do not claim parity

Tier-4 certification proves a component only egresses declared hosts by running it against an enforcing
test-broker. Under this design the test-broker still witnesses every stream open/close and every per-camera
grant check, so a component can be certified as *"only opened cameras it declared."* It **cannot** be certified
as *"only received bytes from them"* — the data path is invisible to the runner. That is better than a bypass
and weaker than full brokering, and the certificate must not imply otherwise.

## The open question this ADR does not close: TCP interleaving

The control/data split assumes control and data are separable sockets. **With `rtsp_transport=tcp` — RTSP
interleaved mode — RTP is multiplexed over the same TCP connection as control.** One socket, one file
descriptor, nothing to split.

TCP is not an edge case. It is the default in GovVMS (`ingestConfig.rtspTransport`), the default in the Python
recorder (`RTSP_DEFAULT_RTSP_TRANSPORT=tcp`), and what municipal deployments force because it traverses NAT and
firewalls and does not shred under loss.

So the split is realizable in exactly three ways, and **the ADR must choose one before the media service is
built**:

| Option | Mechanism | Cost |
|---|---|---|
| **UDP RTP** | media service does DESCRIBE/SETUP/PLAY, negotiates `client_port` at the *driver's* ports; RTP flows direct | commits to UDP, which real deployments avoid |
| **Socket handoff** | media service authenticates, drives the session to PLAY, passes the fd via `SCM_RIGHTS`; credentials never leave it; works with TCP | same-host only; ffmpeg cannot be handed an RTSP socket, so we write our own RTP depacketization — a large amount of new code in the most correctness-sensitive place |
| **Scoped in-component credential** | per-camera Vault secret, materialized per run, short TTL | honest and cheap, but concedes the one property the split exists to preserve |

**Recommendation pending prototype:** socket handoff is the only option that preserves both TCP and
broker-held credentials, and it is the most expensive. Until it is proven, slice 1 ships the third option with
the concession recorded on the component's certificate, not hidden in it.

## Resident components — the second new capability

`PLAT-HOST-004` already sanctions this and it is worth quoting, because it means the *contract* needs no
amendment:

> Per-kind **launchers** MAY differ in lifecycle — a `batch-launcher` runs a driver to completion; a
> **`service-launcher` keeps an engine or agent resident**; an `app-host` serves a UI — but each MUST route
> through the same gate and the same single door.

So: **not a new `kind`**, but a manifest attribute — `kind: driver` + `lifecycle: resident`. Certification,
conformance, grants, and admission all work unchanged; only the launcher differs. Four things do need designing,
because "run to exit" is baked into the current model:

- **Run-token lifetime** — renewable, revocable on uninstall, rather than dying with a run.
- **Receipts** — a stream has no exit code. Session receipts: `open` / heartbeat / `close`, so a run that never
  exits still produces an attributable record.
- **Supervision** — restart with backoff, stall detection, health state. GovVMS's `rtsp-supervisor.ts` already
  is this logic and should be ported rather than reinvented.
- **Placement** — one resident driver per N cameras, or one per camera. The second is better for isolation,
  failure blast-radius, and multi-node scale; GovVMS's lease-based fencing is the existing answer and the
  runtime manager is the natural owner.

## PTZ is an action on the world, not a control call

Pan/tilt/zoom **actuates a physical device**. It is the one place a component changes reality rather than
observing it, and in a system whose output is evidence, *"was this camera moved during the incident?"* is a
question the record must be able to answer.

PTZ is therefore a **governed action with its own audit**, not merely a low-bandwidth call that happens to ride
the control plane. Who may move a camera is a role question; that a camera was moved is a fact that belongs in
the evidence chain. Whether it rises to a Decision Object (ADR-0029/0046) is left open — but it is at minimum an
attributed, governed write, and it must not be modelled as a side effect of a read.

## The viewer direction: same principle, different mechanism

Serving video **to** the operator app raises the identical authority question and resolves with different
machinery. Do not assume symmetry of implementation:

- Outbound (camera → driver) is machine-to-machine on a controlled network; a network grant is a coherent
  enforcement primitive.
- Inbound (store → viewer) is to a **browser**, under the **end user's** token (`PLAT-HOST-005`: an app holds no
  component authority), through an app-host whose default CSP is `connect-src 'self'`, needing HLS or WebRTC
  rather than RTSP. **You cannot put a browser on a camera VLAN.**

That side resolves to short-lived, scoped media URLs or a token-gated streaming endpoint issued by the media
service after a per-user, per-camera, per-purpose authorization — with every view landing as an audited access.
Principle symmetric; mechanism not.

## Storage: frames yes, recordings no

- **Screengrabs → the file store, unchanged.** Content-addressed sha2-256, write-once, dedup, integrity
  inherent. For a few-hundred-KB JPEG this is ideal, and it makes the detection **citable**: the frame's id *is*
  its hash, so a recommendation citing that frame stays reconstructable. That is the ontology's whole argument.
- **Recordings → not this file store, as it stands.** `filestore.py` reads the entire blob into memory on both
  POST and GET, re-hashes on every read, and has **no HTTP Range support** — so no seeking, no HLS, no
  playback. A 5-minute 1080p segment is 50–150 MB.
- **And it has no delete.** Retention deletion is a legal obligation for a VMS; an immutable content-addressed
  store has no answer for it. This is a governance question before it is an engineering one, and it is
  **out of scope here** — flagged for its own ADR. The governed record cites a digest; where the bytes live
  under retention policy is that ADR's problem.

## New governed vocabulary

The platform has **36 governed schemas and not one device noun** — `air.sensor_reading` is a reading; sensors
themselves are never registered. `device.camera` is therefore the platform's **first device noun** and should be
designed to generalize (sensors, gateways, actuators), not shaped only to this use.

Proposed `surveillance` pack, following the `space.aoi` precedent — *a driver reads a governed registry record
that tells it what to operate on*:

| Schema | Stratum | What it is |
|---|---|---|
| `device.camera` | domain | identity · location `{h3, lat/lng, zone, ward}` · stream config · owner agency · **`purpose_binding`** · **`retention_class`** · enabled |
| `device.stream_health` | domain | observed state per camera, per timestamp |
| `media.frame` | domain | a screengrab — cites its file-store id, never carries bytes |
| `media.segment` | domain | a recording — cites its digest, never carries bytes |
| `prov.media_session` | prov | one record per authorized stream: camera, run, tenant, duration, outcome |

**Credentials never appear in these records.** They follow `drivers/kanpur-idss`: named in the manifest, valued
in Vault per `(tenant, component)`, resolved by the control plane. This is a strict upgrade on GovVMS today,
which decrypts `rtspUrl` in-process from an env-derived key.

## Privacy posture — an explicit departure, recorded as such

`docs/plans/crowd-safety-mass-gathering-solution.md` commits the platform to *count, don't identify*:
aggregate at source, no individual tracking, no face recognition unless separately lawful and governed.

A VMS is deliberately the opposite: it retains identifiable footage in order to produce evidence about specific
incidents. That is lawful and legitimate, and it is **a different privacy regime** — it must be represented
explicitly on `device.camera` (`purpose_binding`, `retention_class`, who may view live vs. recorded) rather than
inheriting a default that assumes the opposite. A camera installed for crowd counting and a camera installed for
evidentiary capture are different governed objects even when they are the same physical device.

Note also the framing: media bytes are **low-authority, not low-sensitivity**. Surveillance footage is the most
sensitive payload in the system. The data plane carries no authority; it carries a great deal of sensitivity.

## The detection loop needs nothing new

Stated for completeness, because it is the part that already works. `kind: engine` reads `media.frame`, writes
`intelligence.analysis` + `governance.recommendation` citing `method` + `uncertainty_ref`, and **never decides**
(`INT-REC-001`). Triggering is the existing event fabric — a `platform.subscription` on `media.frame` written →
run the detector, kernel outbox → event relay → automation matcher. An Authority admits the recommendation into
a `governance.decision` with a signed receipt; `solutions/grievance-handling` routes the case.

This is a governance **upgrade** on GovVMS, which today lodges to KMC-PGR with no decision record.

## Slicing

1. **`device.camera` pack** — the contract everything else reads. Seedable today from
   `rtsp-test-source/cameras.yaml` via `rtsp-sim export --format airawat`.
2. **Resident driver, one camera, credentials in-component** (the conceded option), writing `media.frame` to the
   file store. Concession recorded on the certificate. This is the walking skeleton.
3. **Detection engine** on the existing subscription fabric → recommendation → Authority admits. **At this point
   the governed loop is complete end-to-end on one camera** and everything after is hardening.
4. **`platform.media` control plane** — per-camera grant check, Vault-held credentials, `prov.media_session`.
   Resolve the TCP-interleaving question here, with a prototype, before writing the service.
5. **Narrow per-session data grant** in the runtime manager.
6. **Viewer media seam** — scoped short-lived URLs, audited access.
7. Recording, retention, and the delete question — separate ADR.

**Honest note on slices 2–3:** on the current dev fixture (loopback, TCP transport, no RTSP auth) the split
**cannot be prototyped at all** — the skeleton exercises the fallback, not the design. The authenticated camera
should be added to `rtsp-test-source` early, so the first real test of credential handling does not happen
against live municipal cameras.

## Addendum (2026-09-08) — how a component is actually placed, and where ffmpeg lives

Found while deploying slice 2, and it corrects an assumption this ADR was drafted under.

**Components are not subprocesses of the scheduler.** On a real stack the scheduler has
`RUNTIME_MANAGER_URL` set, so it *delegates* to the runtime-manager, which runs the component as a
**container from a certified runtime image** (`components/runtimes/<profile>`), the code mounted read-only
at `/drivers`, with `LAUNCHER_REQUIRE_CERTIFIED_IMAGE=1` verifying the local image id against the
profile's `image_digest`. The subprocess shape exists only where no runtime-manager is configured — a
local-dev fallback, not how a stack executes anything.

Three consequences:

1. **`rtsp-ingest` is `confinement_min: L2`**, not L1. L1 was an artefact of testing against the local
   fallback.
2. **ffmpeg belongs in a runtime profile**, not in the shared reference image. A new
   `runtime/media` profile carries it. Putting it in the reference image would add ~60MB to the image
   every platform service runs from *and still not reach the driver*; adding it to `geospatial` or
   `earth-observation` would change a pinned `image_digest` and force re-certification of unrelated,
   working drivers.
3. **"L2 means no route to the camera" was too strong.** A placed container joins the stack network, so a
   camera or fixture on that network is reachable at L2. The routing problem is real only for a camera on
   a *separate* network — which is the case the slice-5 data-plane grant exists for. The concession in
   slice 2 is about **credentials in the component**, not about L2 being unable to reach anything.

## Consequences

- **The single-door invariant is refined, not broken** — from "the broker is the only door" to "the broker is
  the only door for authority." That refinement must be carried into `PLAT-0001` explicitly, or it will be read
  as an exception and erode.
- **A new trusted component exists.** `platform.media` holds camera credentials and sits in the sensitive path.
  It is a smaller, more auditable surface than a media-capable broker, but it is new trust and must be
  certified, versioned, and reviewed as such.
- **Certification is honestly weaker for this component class**, and says so on its face: opens are provable,
  bytes are not.
- **Credentials and audit are designed in from slice 1**, even where slice 1 concedes them — these are the two
  things that cannot be retrofitted into a surveillance system that already holds real footage.
- **The `crowd-camera` slot fills.** `mass-gathering-safety-kumbh` composes a *simulator* whose own header says
  it stands in for "a fusion of CCTV people-counting, bus GPS and telco density." A real camera driver replaces
  it, and the crowd-safety solution becomes real without redesign.

## Open questions

1. **TCP interleaving** — UDP, socket handoff, or conceded in-component credentials? Blocks slice 4.
2. **Placement** — one resident driver per camera or per fleet? Reuse GovVMS's lease fencing?
3. **Recording storage and retention deletion** in a content-addressed world — separate ADR, but it constrains
   `media.segment` and should not be deferred long.
4. **Does PTZ rise to a Decision Object**, or is an attributed governed write sufficient?
5. **Is the recorder the same component as the ingest driver**, or a second one? If separate, both need camera
   access and the per-camera grant story doubles.

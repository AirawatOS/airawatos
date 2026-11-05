# ADR-0096 — The platform operator: a key-rooted participant with a node-side CLI

> **⚠️ PARTIALLY SUPERSEDED (2026-11-05).** The *"a tenant = network citizenship"* framing (Relates-to line,
> via ADR-0039) is overturned by **ADR-0116** (participant ≠ tenant; membership is tenant-free) — see
> **PLATFORM-v0.1 P4** (the platform/any tenant confers no authority), **NETWORK-v0.1 N1** (slug/tenant not
> accepted as network authority), **FOUNDATIONS-v0.1 F3**. The operator model itself (key-rooted participant,
> node-side CLI, operator holds no governance role per **PLATFORM-v0.1 P3**) stands; only the
> tenant-as-citizenship premise is corrected. Body unchanged below.

**Status:** Proposed. First slice DONE & proven on EC2 (2026-09-19): the node-side `airawat` CLI with `provision-runtime` (pull → digest-verify → attest), reusing ADR-0095 R3's attestation endpoints. The identity/signing machinery below is the follow-on.

**Relates to:** ADR-0011 (realms/RBAC), ADR-0039 (federated identity — a tenant = network citizenship), ADR-0030 (clean-room runtime + broker), ADR-0051 (point-of-use cert/image enforcement), ADR-0082 (offline/edge device credential), ADR-0085 (filestore delivery), ADR-0086 (operator certification — host integrity), ADR-0093 (retire baking — the OS ships services-only), ADR-0095 (runtime lifecycle; this ADR lands its **R4**).

## Context

Everything in AirawatOS is modelled as a governed participant with an identity: tenants (cities, ministries), the Network standards body (`airawat`), the developer (`airawatdeveloper`). **The one actor never modelled is the platform operator** — the party that runs the metal: holds each node's Docker socket (via the runtime-manager), pulls runtime images, and keeps the OS services alive.

Today an operator has **no entry point**. Installing a runtime means: SSH to the node, `docker pull manishsv/airawatos-runtime-<profile>`, edit compose. Nothing is resolved, verified, recorded, or attributable. ADR-0095 R3 made a node *attest* which certified images it holds, but the pull itself is still an ungoverned human act. This is the gap ADR-0095 R4 named ("governed image provisioning") and ADR-0086 anticipated ("operator = participant with a signing key + host-integrity attestation").

Three questions force the design:
1. **How does an operator install a runtime** through the platform rather than around it?
2. **Should the operator have a *tenant*** (a data/app namespace), and is that a security problem given its infrastructure privilege?
3. **What must be CLI/backend-only** (unavailable via the web), because it is either catastrophic on web-session compromise or must work when the web is down?

## Decision

### 1. The operator is a participant `kind:"operator"` with a signing key — and a lightweight tenant

Model the operator as a first-class participant whose **authority is rooted in an operator signing key** (ADR-0086), *not* in tenant RBAC. Give it a lightweight **tenant** too — a home realm plus an "Operator Console" app surface — so operator-facing UX (node health, provisioning, the attestation dashboard, capacity) is delivered through the *same* governed app-host + marketplace machinery as everything else, with no bespoke tooling.

The security of this rests on one line, drawn hard:

> **An "operator tenant" is an ordinary tenant. Its host powers do NOT come from tenant membership — they come from the operator signing key and the runtime-manager's privilege boundary.**

Consequences of that line:
- **Web-session compromise ≠ host root.** A stolen operator web session can *request* and *observe*; it cannot itself pull an image or touch Docker, because those acts require the key (held on the node/CLI, never in a browser) and the runtime-manager's internal boundary.
- **No cross-tenant data reach.** The operator runs the metal; it does not get to read what runs on it. Cross-tenant visibility stays the governed **aggregator lane** (consumer-bound, offering-scoped grants), never an operator privilege.
- **Distinct from the Network Steward.** `airawat` (the standards body → Network Admin console) governs *specs and certificates*; the operator runs *nodes*. These are separate participants with separate consoles. (Network Admin today quietly does both; this ADR separates them.)

There is **no structural blocker** to an operator tenant provided that line holds; it is in fact the uniform, everything-is-a-tenant answer.

### 2. The CLI is the primary operator surface and the trust root

The operator CLI — named **`airawat`**, run node-side — is not a convenience wrapper over the web; it is the **trust root**:
- it holds the operator **signing key locally** (machine / HSM), which the browser must never see;
- it must work when the app-host / web is **down** — bootstrap, recovery, and break-glass all happen when the UI is unreachable;
- it is dependency-free (stdlib only) so it runs on a bare node with nothing but Python + Docker + a network URL.

The web console is then a **thin declare-and-observe layer** over the CLI's world: it *shows* state (the Runtimes panel, attestations, capacity) and *enqueues* signed intents (a provision request) that the node's key-holding agent executes and attests. **Principle: declare + observe over the web; sign + execute privileged host acts via the key-holding CLI/agent.**

Core verbs (map to R4 + ADR-0086):

| verb | acts |
|---|---|
| `provision-runtime <id>` | resolve cert → fetch + **digest-verify** source from the network filestore → `docker pull` → **lock** `.Id == certified image_digest` → **attest** (signed) |
| `list-runtimes` / `attestations` / `health` | read the operator catalog, the host-integrity roll-up, and local reachability |
| *(follow-on)* `register-node`, `rotate-key`, `drain-node` | node identity + key lifecycle + graceful placement removal |

### 3. What is CLI/backend-only vs web-OK

| Backend / CLI only (never web) | Why |
|---|---|
| operator **key generation / rotation** | key material must never touch a browser |
| **node registration** + node/device credential (ADR-0082 parallel) | establishes the trust root |
| the **`docker pull` / exec** itself on the host | the privileged act — web can *request*, the node *executes* |
| **break-glass**: restart / drain / rollback services | must work *when the web is down* |
| **Vault / secrets root** operations | catastrophic on session compromise |

| Web-OK (read-mostly, low-consequence) |
|---|
| view attestations, capacity, which runtimes are certified/available |
| **trigger** a provision (enqueues a signed action a node carries out) |
| lifecycle / audit views |

The web never holds the operator key and never touches the Docker socket.

## What is already built (this ADR's first slice)

- **`operator/airawat`** — the node-side CLI above, dependency-free, verbs `provision-runtime` / `list-runtimes` / `attestations` / `health`.
- **`provision-runtime`** does the real pull → digest-verify (source dir-digest == certificate) → image-lock (`.Id == image_digest`) → attest, reusing ADR-0095 R3's `POST /v1/runtime/attest`. Proven on EC2: certified runtimes provision + attest with the network **independently re-verifying** the digest; unknown/uncertified ids refuse cleanly.
- **Runtime sources landed in the network filestore** (content-addressed) so any node — not just one with the tenant filestore — can fetch + verify them (closed an ADR-0095 R2 portability gap).

**Stand-in:** attestation is currently gated by an internal token, not the operator signing key. That is the honest scaffold; §1's signing machinery replaces it.

## Migration (phased)

- **P0 — CLI scaffold + R4 pull/verify/attest.** ✅ DONE (2026-09-19). `airawat provision-runtime` end-to-end; runtime sources portable via the network filestore.
- **P1 — Operator identity.** Govern participant `kind:"operator"`; generate the operator signing key (CLI-side); `register-node` writes a node record; the operator obtains an **operator certificate** (ADR-0086) as a `CERTIFICATES` entry.
- **P2 — Signed attestation.** Replace the internal token on `/v1/runtime/attest` with a **signature over `(node, runtime, version, image_digest, ts)`** verified against the operator's registered key. Advisory → then optionally an install/placement gate ("certified AND attested-by-a-trusted-operator on ≥1 node").
- **P3 — Operator tenant + console.** Provision the operator's lightweight tenant + realm; ship an "Operator Console" solution (nodes, runtimes, attestations, capacity) that *declares/observes* and *enqueues* signed actions — the thin web layer over the CLI.
- **P4 — Break-glass + lifecycle.** `rotate-key`, `drain-node`, service restart/rollback as CLI/agent-only recovery paths.

## Consequences

- **Governed provisioning.** Installing a runtime becomes one auditable command with verify + attest built in — no more ungoverned SSH + `docker pull`.
- **Blast-radius contained.** The operator gets a tenant and web UX without becoming root; privilege stays with the key + the runtime-manager boundary. A web compromise cannot pull images, read other tenants, or touch Docker.
- **Uniformity.** The last un-modelled actor becomes a participant like every other — same identity, certificate, and app-delivery machinery.
- **Cost.** Two surfaces to maintain (CLI + thin web) and an operator key to manage; key rotation/recovery must be designed carefully (P4).

## Open questions

1. **Image digest form** — `image_digest` is the local `.Id` (config digest), not the registry manifest digest. Record both; decide which a placement gate keys on (manifest digest is portable across nodes).
2. **Enforcement switch** — when does availability *require* a signed attestation (P2) rather than stay advisory? Suggested: advisory until all live runtimes attest, then gate.
3. **Multi-operator / multi-node trust** — when several operators run nodes for the same network, whose attestation counts, and does a tenant get to require attestation by a *specific* trusted operator?
4. **Key custody** — operator key on disk vs HSM vs a hardware token; and the recovery path when a node/key is lost (ties into ADR-0082 device credentials).

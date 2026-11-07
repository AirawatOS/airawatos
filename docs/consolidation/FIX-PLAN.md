# Consolidation FIX-PLAN — bottom-up, layer by layer

The remediation plan for consolidation phase 5. It is **bottom-up**: a layer is not declared done until the layer
beneath it has passed its exit gate, because every upper layer's security depends on the one below (an App Host
front gate means nothing if the Kernel door it sits above is reachable directly; a signed component means nothing
if the fact store has no credential separation). Work proceeds **Layer 1 → Layer 7**.

This plan does not restate findings — it sequences them. Findings live in
[DEBT-REGISTER.md](DEBT-REGISTER.md); the review method (fresh reviewers, findings-only, local-dev, EC2 out of
scope) is [REVIEW-METHOD.md](../reviews/REVIEW-METHOD.md); the door/flow topology is
[ARCHITECTURE-FLOWS-v0.1.md](../specs/ARCHITECTURE-FLOWS-v0.1.md); per-rule measured status is
[STATUS-MATRIX.md](../specs/STATUS-MATRIX.md). Each slice's review doc is under [docs/reviews/](../reviews/).

**How to read a layer.** Each layer lists: **Owned rules** (by ID — the rules this layer is responsible for),
**Open findings & debt**, **Missing tests**, and an **Exit gate**. A layer's exit gate is met only when: every
owned finding is closed *or* explicitly deferred with a written reason; every owned rule has a test; every owned
rule reads **HELD** in the matrix (or a deferred-with-reason exception is recorded); all assurance nets (§0) are
green for that layer; an **independent fresh-reviewer pass** finds no new High/Med; the layer's services are
**safe as N copies** (FND-18 — no HA-blocking state; see [HA-AUDIT.md](HA-AUDIT.md) + the proposed two-copy test);
and a **fresh install + conformance (both modes)** passes.

---

## §0. Foundational assurance nets (built in Layer 1, enforced for every layer)

These are the mechanisms every layer's exit gate checks against. They are built first (Layer 1) and then run in
CI and on every fresh install.

1. **Network separation** — each layer on its own network with deny-by-default egress; only the edge is
   host-published; the Kernel door and data stores are internal-only (ARC-1/ARC-5/ARC-7).
2. **Credential separation** — per-service DB roles that can touch only their own tables (only the Kernel role
   reaches fact tables, ARC-3); per-service Vault tokens/AppRoles scoped to their own paths, **no shared root
   token** (ARC-7, DEBT-B58).
3. **Audience-bound service tokens** — every internal door admits only a token addressed to it, minted from a
   Vault credential (`svc_authz`/`svc_token`); **no shared static literals**, **no passwordless principals**
   (FND-9; retires A71/A37/A36/A29).
4. **Route inventory test** — every HTTP route declares its class: `public` / `login` / `named-authority` /
   `internal-only`. An **undeclared route fails CI**. An **anonymous call to every non-public route expects a
   refusal** (fresh-install black-box).
5. **One decision function** — each door authorizes through a single function that reads **recorded**
   roles/grants/consent (never token claims, tenant name, or issuer), is **fail-closed**, and **writes a decision
   record** (FND-2/FND-3/FND-8/FND-12). Gates are **armed by default on a fresh install**; a missing gate config
   **stops startup (fail-loud)**, never silently shadows (FND-16).
6. **Banned-pattern checks in CI** — static gates that fail the build on: a token-role read used as authority
   (B1), an undeclared route, a default/hardcoded secret, a fail-open handler (`if not X or …` admitting on
   unset), a superuser DB connection from a service, a direct internal-service URL that skips a door.
7. **Conformance + fresh-install in CI** — `deploy/installer/install.sh --profile dev` from a clean volume, then
   `conformance/run-both.sh` (internal + external) must pass with 0 FAIL / 0 XPASS / 0 SKIP_CREDS on a healthy
   stack, every run.
8. **Secret & dependency scanning** — secret-scanning on the tree + image layers; dependency/CVE scan of the
   runtime images; both gate the build.

The **flow-map test** (enumerate running containers × network memberships × actual socket edges; assert every
edge crosses a declared door — ARC §c) is the capstone net that proves nets 1–5 hold together.

---

## Layer 1 — Installation + infrastructure

**Foundational.** Everything above assumes these hold; they must land first.

- **Start here:** network separation per boundary (ARC-1/5/7); gates **on by default** on a fresh install, **no
  shadow**, **fail-loud** on missing config (FND-16); **per-service credentials** (DB roles + Vault policies).
  Then build the eight assurance nets of §0 and wire nets 4–8 into CI + the installer.
- **Owned rules:** ARC-1..ARC-7; FND-16 (enforce-by-default / fail-loud); FND-8 at the infra layer (nothing
  privileged reachable unauthenticated); the §0 nets themselves.
- **Open findings & debt:** **DEBT-B52** (flat docker network — no per-layer separation), **DEBT-B57** (fact
  store reached by `network_app`/`identity_lockout`, not Kernel-only), **DEBT-B58** (shared `VAULT_TOKEN`, no
  per-service policy), **DEBT-A72** (service ingress gates default-off/shadow), **DEBT-B5** (unauthenticated
  privileged endpoints), **DEBT-A61** (sibling `deploy/local` binds nginx `0.0.0.0`), **DEBT-A71/A37/A36/A29**
  (shared static internal-token literals → audience-bound tokens), the **EC2 host-iptables** and
  **disk-full/log-rotation** operational notes (memory) folded into installer hardening.
- **Missing tests:** the route-inventory test (net 4); the flow-map test; the DB-grant audit; the Vault-policy
  audit; the banned-pattern CI gate; the fresh-install-in-CI job. None exist yet — this layer builds them.
- **Exit gate:** networks separated and proven by the flow-map test; every service on its own DB role + Vault
  policy (B57/B58 closed); every ingress gate armed-by-default with fail-loud on missing config (A72 closed, B5
  closed); route inventory + banned-pattern + fresh-install + conformance + secret/dep scans green in CI;
  independent review; fresh install + conformance both modes pass.

---

## Layer 2 — Kernel

- **Owned rules:** FND-2 (authority from recorded state), FND-6 (domain-blind), FND-7 + **ADR-0123** (self-
  contained for authz inputs — never calls upward, ARC-2), REG-1..REG-18 (registry correctness, signatures,
  Kernel-mediated files), the single P0 registry authorization gate.
- **Open findings & debt:** **DEBT-A1** (anonymous kernel read succeeds; also ARC-5 — the `/kernel/` edge route
  must become internal-only), **DEBT-B9** (Kernel calls the Network for authority key/schemas/grants/tenant-dev —
  ADR-0123), **DEBT-B8** (not domain-blind: `_NAT_KEYS`/dataplane vocab baked in — FND-6), **DEBT-B23** (committed
  versions carry no Kernel/participant signature; no hash chain — REG-8), **DEBT-B20** (run-token serialized at
  rest in cleartext), **DEBT-B53** (run-token has no expiry/audience). Confirmed fixed: B15 (list strips
  run_token), B22 (install admin-gated), P0#1 (high-entropy run-tokens).
- **Missing tests:** anon-read-denied as a PASS (currently XFAIL under A1); a Kernel-calls-upward banned-pattern
  check (ADR-0123); registry-signature + hash-chain conformance (B23); run-token expiry/replay test (B53).
- **Exit gate:** ADR-0123 closed (Kernel self-contained; `/kernel/` internal-only); anon reads denied; registry
  versions signed + chained; run-tokens short-lived/audience-bound and not stored cleartext; owned REG/FND rows
  HELD or deferred-with-reason; nets green; independent review; fresh install + conformance pass.

---

## Layer 3 — Identity

- **Owned rules:** FND-1 (tokens carry identity only), FND-9 (service-to-service = audience-bound Vault-minted
  tokens; no passwordless principals), FND-15 (external issuers scoped), CLI-3 (short-lived, app-addressed,
  consent-referencing tokens), PTC-2 (authentication = identity only).
- **Open findings & debt:** **DEBT-B14** (`IDENTITY_PASSWORD_REQUIRED` shadow default) / **DEBT-A30**
  (passwordless bare-login for steward/service principals — task #282), **DEBT-B31** (human/citizen tokens are
  platform-audienced with no consent-reference claim), **DEBT-A68** (three daemons share one `scheduler`
  principal → split into per-service principals), **DEBT-A9** (failed authentication not logged — FND-12).
  Confirmed fixed: B28/B29 (identity internal-write + directory gates), svc_token fail-closed (no passwordless
  fallback, verified slice-5).
- **Missing tests:** failed-auth-logged assertion; per-service-principal (not shared) assertion; consent-reference
  claim presence (CLI-3); external-issuer tenant-mismatch rejection as a PASS (FND-15).
- **Exit gate:** password enforcement on by default (B14/A30 closed); per-service principals (A68 closed); tokens
  identity-only + consent-referenced (B31); failed auth logged (A9); owned rows HELD or deferred; nets green;
  independent review; fresh install + conformance pass.

---

## Layer 4 — Network + Trust

- **Owned rules:** NET-1..NET-12, PTC-1..PTC-12, FED-1..FED-8, FND-11 (separation of duties + last-holder floor),
  FND-14 (authority traceable to bootstrap), the Trust-plane decision function (ADR-0119).
- **Open findings & debt:** **DEBT-B36/B42** (federation/offerings directory leakage to anon — gated in slice-5
  hotfix B42; confirm the federation subset), **DEBT-B11** (slug / `net:`id / tenant conflated — FND-4),
  **DEBT-B18** (granting `platform.authority` not separation-of-duties / last-holder protected — FND-11),
  **DEBT-A17**, the **publish-request / network-certs IN-MEMORY** gap (restart wipes certs + requests — FND-5),
  **DEBT-B23** delivery-side (component versions unsigned — shared with Layers 2 & 7).
- **Missing tests:** directory anon-leak refusal (federation subset); separation-of-duties on authority grant;
  cert/request durability across restart; grantor-chain-to-bootstrap (FND-14).
- **Exit gate:** directory reads scoped; authority grants SoD + last-holder protected (B18); certs/requests
  durable (FND-5); owned NET/PTC/FED rows HELD or deferred; nets green; independent review; fresh install +
  conformance pass.

---

## Layer 5 — App Host

- **Owned rules:** CLI-1..CLI-6 (registered clients, consent-bounded scope, short-lived app tokens, public
  versioned protocol / never `/bridge`), PLT-14 (content safety), PLT-15 (public front door route-separated +
  rate-limited), FND-5 (durable sessions), FND-8 at the bridge surface.
- **Open findings & debt:** **DEBT-B45** (session cookie no `Secure`; no CSRF/Origin check), **DEBT-B46** (public
  front door unauth + unthrottled + not route-separated), **DEBT-B47** (account-hold check fails open),
  **DEBT-B48** (fail-open anon bridge reads/proxies), **DEBT-B50** (docrender renders active content — latent
  stored XSS), **DEBT-B12** (embed consent scope not bound to registered client), **DEBT-A23 / CLI-6 / PTC-12**
  (`/bridge/*` used as the public protocol — cross-cutting with Layer 7). Confirmed fixed: **B41** (component-
  publish verifies token+role), **B42** (directory/provenance bridges require auth) — slice-5 hotfixes.
- **Missing tests:** CSRF/Origin + `Secure` on cookie-auth POSTs; account-hold fail-closed; each anon bridge
  read → refusal; docrender sanitization unit test (B50); embed scope ≤ registered-client ∩ consent (B12,
  black-box via seeded demo-embed); rate-limit/route-separation on the public front door.
- **Exit gate:** public front door rate-limited + route-separated (B46); cookies `Secure` + CSRF-protected (B45);
  account-hold + anon bridges fail-closed (B47/B48); docrender sanitizes (B50); embed scope bound (B12); a
  versioned public protocol defined so `/bridge` is no longer the contract (CLI-6/PTC-12 — see cross-cutting);
  owned CLI/PLT rows HELD or deferred; nets green; independent review; fresh install + conformance pass.

---

## Layer 6 — Internal services + gateways

- **Owned rules:** FND-8 (every privileged endpoint authenticated, fail-closed, no shadow), FND-9 (audience-bound
  service tokens), FND-10 (least privilege / cross-tenant only by recorded grant), FND-5 (durable at-least-once /
  dedup), FND-12 (audited).
- **Open findings & debt:** **DEBT-B5** (model-gateway `/complete|/embed|/transcribe` + notify `/notify`
  unauthenticated; filestore shadow), **DEBT-A72** (ingress gates default-off — only scheduler/automation armed),
  **DEBT-A71/A37/A36** (shared static literals → audience-bound tokens), **DEBT-A66 / B1 / B3** (secrets/decision
  authority from token roles / authentication-alone), **DEBT-B10** (automation dedup + scheduler receipts
  in-memory → double-fire on restart), **DEBT-B49** (filestore blob path has no owning-tenant scope even once
  gated), **DEBT-A40** (notify unattributed registry write), **DEBT-A65** (dual-audience migration acceptance),
  **DEBT-A11/B16** (connector/secrets `/fetch` SSRF). **Conversation-channel gateway (with DEBT-B46):** **DEBT-B64** — inbound SMS/USSD/message intake authenticated by one shared secret (interim: moved to Vault, slice-1c-iv step 4); **target:** per-provider, per-tenant signed webhooks, tenant bound by provider registration, behind the B46 rate-limited front door. Confirmed fixed: B4/A36 fail-closed-when-unset; B6/B28/B29
  identity directory; automation `/events` promoted to a PASS (slice-5).
- **Missing tests:** anon→refusal on model-gateway/notify once gated (XFAIL until armed); cross-tenant filestore
  read once gated (B49); decide-authorization from a recorded grant (B3); workflow /instantiate authority (B1);
  dedup survives restart (B10); scheduler `/run` scoped to caller tenant (A28/A39).
- **Exit gate:** every privileged endpoint armed-by-default + fail-closed (B5/A72 closed); shared literals retired
  to audience-bound tokens (A71/A37/A36); authority from recorded grants not token roles (B3/A66); dedup/receipts
  durable (B10); filestore tenant-scoped (B49); owned FND rows HELD or deferred; nets green; independent review;
  fresh install + conformance pass.

---

## Layer 7 — Components + SDKs

- **Owned rules:** CMP-1..CMP-18 (manifest, private/sharing lanes, run-token = declaration ∩ authority, isolated
  runs, broker-only I/O, signed content-pinned packages, certified sharing, informed-consent install), CLI-6 /
  PTC-12 (SDK is one optional impl of a public versioned protocol; never `/bridge`).
- **Open findings & debt:** **DEBT-B51** (default/in-process runtime inherits full host env — no confinement),
  **DEBT-B52** (placed container joins flat net, no egress policy — depends on Layer-1 network separation),
  **DEBT-B53** (run-token no expiry/audience — shared with Layer 2), **DEBT-B54** (on-demand filestore delivery
  fail-open + trusts unsigned listing digest), **DEBT-B55** (launch digest-rebind only on baked path),
  **DEBT-B56** (unverified-digest certify accepted; host ignores `conformance.verified`), **DEBT-B23** extended
  (no publisher/steward signature on a component version), **DEBT-A4** (capability = self-asserted listing scope;
  steward-grant gate default-off), **DEBT-A67** (version provenance unsigned/mutable), **DEBT-A11/B16** (connector
  `safe_endpoint` weak SSRF filter), **DEBT-A50/A51/A54** (deploy tooling: direct internal ports, `/bridge`
  client, cleartext creds to a plain-http IP). Confirmed sound: the aos SDK confined runtime (broker-only `/v1/*`,
  fail-closed token gate, no self-asserted roles), `/v1/fetch` declared-egress, install/list admin-gating.
- **Missing tests:** scrubbed-env assertion for in-process runs (B51); container-egress-denied (B52); run-token
  replay/expiry (B53); on-demand-delivery fail-closed (B54); un-baked digest rebind (B55); conformance.verified
  honored (B56); publisher-signature-present on a version (B23); the proposed tests are recorded as SKIP_BUILD in
  `run_components_review_cases()` with their exact shape.
- **Exit gate:** a real isolation runtime (scrubbed env + `--network none` + broker egress proxy) for the default
  path (B51/B52 closed, on Layer-1 network separation); run-tokens short-lived/audience-bound (B53); delivery
  fail-closed on every path with a verified cert + digest (B54/B55/B56); component versions publisher-signed with
  verifiable provenance (B23/A67); capability = declaration ∩ recorded grant with the grant gate on (A4); a
  versioned public protocol so SDKs no longer ship `/bridge` (CLI-6/PTC-12); owned CMP rows HELD or deferred; nets
  green; independent review; fresh install + conformance pass.

---

## Cross-cutting threads

These span layers; each must be closed everywhere, not in one layer. Listed with each layer's contribution.

- **Thread T1 — Authority from token roles (DEBT-B1 / FND-1/FND-2).** The pervasive "role claim in a token is
  authority" anti-pattern. *Kernel* (L2): admin off issuer+role. *Identity* (L3): stops stamping `roles` as
  authority; adds consent-ref (B31). *Network* (L4): Trust-plane already recorded-grant — keep. *App Host* (L5):
  front gates read recorded grants not claims. *Services* (L6): secrets/decision/workflow read grants (A66/B3).
  *SDKs* (L7): client doesn't surface roles as authority (B1/B31). Banned-pattern net (§0.6) is the enforcer.
- **Thread T2 — `/bridge` is not the public protocol (CLI-6 / PTC-12 / DEBT-A23).** Define a public, versioned,
  `/bridge`-free client/wire protocol; demote the SDK to one implementation. *App Host* (L5): publish the versioned
  door; keep `/bridge/*` internal-only. *SDKs* (L7): `aos.js` + the embed/deploy tooling target the versioned
  protocol, not `/bridge`.
- **Thread T3 — No shadow in production; fail-loud (DEBT-A72 / FND-16).** Every gate armed-by-default; missing
  config stops startup. *Infra* (L1): the default; *Services* (L6): flip every `<SVC>_REQUIRE_TOKEN` on and remove
  the shadow path; audited by the route-inventory + fresh-install nets.
- **Thread T4 — Signing & provenance (DEBT-B23 / A67 / REG-8).** Registry versions (L2) and component versions
  (L4 catalog + L7 delivery) both need a participant/publisher signature + verifiable provenance + a verified,
  fail-closed digest at use. One signing spine (`signing.py` per ADR-0052) applied across kernel rows and
  component versions.
- **Thread T5 — No silent in-memory authoritative state (FND-5) → safe as N copies (FND-18).** Each item below
  is **HA-blocking**: it breaks when the service runs as ≥2 copies behind a load balancer (full analysis +
  fixes in [HA-AUDIT.md](HA-AUDIT.md)). Per owning layer:
  - *L2 Kernel* — run-tokens are boot-rehydrated from KV but not looked up live (**B20/B10**): read them from KV
    per use. **HA-blocking.**
  - *L3 Identity* — user/password store is a local file: move to a durable store. **HA-blocking.**
  - *L4 Network* — certificates + publish-requests are in memory (restart wipes): make them durable. **HA-blocking.**
  - *L5 App Host* — `_SESSIONS` in memory (**B10/B45**): durable shared session store (or sticky LB interim). **HA-blocking.**
  - *L6 Services* — automation dedup + scheduler receipts in memory and the scheduler clock / event-relay drain /
    automation dispatch are assumed-singleton loops (**B10**): durable shared dedup + **leader election / lease**
    for the singleton work; **filestore** local-disk blobs → shared object storage. **HA-blocking.**
  Already safe as N: secrets, model-gateway, notify, workflow, decision, nginx. Each layer's exit gate now
  includes "safe as N copies (FND-18)", verified by the proposed two-copy conformance test (HA-AUDIT §e).
- **Thread T6 — Confinement is enforced, not conventional (CMP-5/6 / DEBT-B51/B52).** Depends on Layer-1 network
  separation; realized in Layer 7 as the isolation runtime. Until L1 lands, L7 cannot close.

---

## Before first production (gates beyond the layer exits)

The first production deployment is a **fresh install** of the reviewed source (REVIEW-METHOD). Beyond every
layer's exit gate, two things are required before that install serves real data/users:

1. **External penetration test** — an independent, authorized external pen-test against a fresh install (not the
   current dev EC2 box), covering the internet-facing surface (edge, App Host front door, federation door) and
   the flow-map (attempting every ARC bypass). Findings triaged and closed/deferred-with-reason before go-live.
2. **Runtime decision records + alerting** — the one-decision-function records (FND-12) are emitted durably in
   production, and alerting fires on: repeated auth failures, any fail-closed denial spike, any privileged-endpoint
   call without a token, and any off-map flow the flow-map monitor detects. Production is observable for the
   invariants this plan enforces, not just green at install time.

> **Sequencing reminder:** do not start a layer's fixes before the layer below has passed its exit gate. The nets
> in §0 are Layer-1 deliverables precisely because every higher layer's exit gate depends on them.

# COMPONENTS + SDKs review — Consolidation phase 5, slice 6

Scope: the unit of executable capability and the tooling that ships it —
- the `aos` Python SDK / CLI (`components/_common/aos/*`, `ids.py`),
- the clean-room broker + launcher (`kernel/services/broker/*`, kernel `api/app.py` HTTP binding, `components/_common/launcher.py`),
- signing / provenance / delivery of component versions (`platform-spec/reference/{package,signing,host,hostcore}.py`, `app_host.py` `_materialise`, `network/{authority,store,api}.py`),
- the browser/client SDK surface (`platform-spec/reference/shared/aos.js`, the inline `/embed/sdk.js`).

Audited by four fresh, independent, read-only reviewers; findings only — no code changed in the review step. Evidence is `file:line` in the canonical tree `Airawat/`. Judged against the repository source + a fresh install; **EC2 is out of scope** (dev environment, see `docs/reviews/REVIEW-METHOD.md`). Rules: COMPONENT CMP-1..18, CLIENT CLI-1..6, PARTICIPANT PTC-2/PTC-12, FOUNDATIONS FND-1/2/8/9/10/14, REGISTRY REG-8.

## The four governing questions (answers)

1. **Do components reach the platform only through declared doors?** For the **confined runtime**, yes — the `aos` SDK's `Ctx.from_broker` talks only to the governed broker's versioned `/v1/*` door under a kernel-minted run-token, with egress brokered through `/v1/fetch` (secret injected server-side). **But the confinement that makes that the *only* door is absent in the default path**: the reference/in-process runtime runs a component as a host subprocess inheriting the full kernel environment (B51), and placed containers join the flat internal docker network with no egress policy (B52) — so a component can bypass the broker entirely and hit secrets/filestore/kernel/Postgres/Vault directly. The **author tooling** (`aos deploy`/`aos upload`) also dials internal ports + `/bridge/*` directly (transitional, DEBT-A50/A51).
2. **What the client SDK exposes.** The browser runtime `aos.js` hands every page the internal `/bridge/*` surface *as* its API, plus an arbitrary-verb dispatcher (`AOS.run(verb)→/bridge/<verb>`) and a raw any-path `AOS.get/post`, with a client-injected `app_id` — i.e. the SDK *is* the protocol and the protocol is the internal bridge (CLI-6/PTC-12). The embed SDK lets a page self-assert `clientId`+`scope`, which the server records as an unbounded `service:"*"` consent (DEBT-B12), and persists a role-bearing 1h JWT in page-readable `sessionStorage` (CLI-3/B1/B31).
3. **Signing / provenance of component versions (DEBT-B23).** **OPEN and broader than the register recorded.** No publisher/steward signature exists anywhere in certify→publish→install→run; `signing.py`'s Ed25519 machinery is wired only to decisions/orders. Integrity rests solely on a CA cert over a bare SHA-256 digest, and that gate is **not fail-closed**: skipped on the on-demand filestore path when the cert/network is absent (B54), enforced at launch only on the baked path while un-baked is the ADR-0093 default (B55), and satisfiable by a publisher-chosen digest via the unverified legacy certify branch the host never flags (B56). Provenance lives only in unsigned, mutable store-listing metadata (DEBT-A67).
4. **Does any SDK path rely on bridges or token roles?** **Bridges: yes** — `aos.js` (CLI-6/PTC-12) and the author tooling (`cli.py:362` `/bridge/file-push`, `solution.py:322` `/bridge/component-publish`). **Token roles: no, in the SDK itself** — the `aos` runtime sends the identity bearer for authentication only and never treats role claims as authority; the pervasive roles-as-authority violation (DEBT-B1) lives in the servers it calls, inherited transitively.

## Summary (one page)

**The confined-runtime seam is well-designed; the sandbox that would make it unbypassable is missing, and component-version integrity is not fail-closed.** The broker's synchronous authorization is sound — fail-closed on missing/invalid run-token (401), default-deny capability checks (403), `/v1/fetch` egress bound to declared hosts with `prov.egress` audit, install/list endpoints admin-gated (DEBT-B22/B15 confirmed fixed), dev-token mint reach-confined. The `aos` SDK runtime reaches the platform only through that door and never self-asserts roles or forges tokens. The weaknesses are **structural, not in the check logic**:

Top risks (new this slice unless noted):
1. **B51 (HIGH)** — default/in-process runtime inherits the full host env (incl. `SECRETS_INTERNAL`) + unrestricted sockets/fs; broker-as-only-door is convention, not enforcement. `launcher.py:248-261`.
2. **B52 (HIGH)** — placed containers join the flat internal net with no egress policy; direct reach to filestore/secrets/kernel/Postgres/Vault. `launcher.py:310-320,450-455`.
3. **B54 (HIGH)** — on-demand filestore delivery fail-OPEN (digest check skipped when cert/network absent) and trusts an unsigned listing digest. `app_host.py:3771-3775`.
4. **B23 (HIGH, extended)** — component versions carry no publisher/steward signature; CMP-7 PARTIAL. `signing.py` unused for components.
5. **B55 (MED-HIGH)** — launch-time digest rebind enforced only on the baked path; un-baked (default) skips it. `host.py:206`.
6. **B56 (MED)** — unverified-digest certify accepted; host ignores `conformance.verified`. `network/api.py:1327`, `host.py:87`.
7. **B53 (MED)** — run-token has no expiry/audience → indefinitely replayable. kernel `app.py:1126-1130`.
8. **CLI-6 / PTC-12 (HIGH, existing DEBT-A23)** — no public versioned, `/bridge`-free client protocol; `aos.js` ships the bridge as the contract.
9. **DEBT-B12 (HIGH, existing)** — embed SDK self-asserts scope → server records `service:"*"` consent (black-box reproducible on seeded demo-embed).

Verdict counts (across the four reviewers): **HIGH 6, MED 6, LOW 3** — **6 NEW B-items (B51–B56)** opened + **B23 scope extended**; all other findings map to existing debt (A4, A11/B16, A23, A47/A48, A50/A51/A54, A67, B1/B12/B20/B31, server B41 already fixed). Positives: the broker token gate, `/v1/fetch`, install/list admin-gating, high-entropy run-tokens (P0#1), connector tenant-scoping (A2/A3), and admission `COMPONENT_ENFORCE=1` default are all correct.

## Per-area findings

| Area | Finding | Rule(s) | Debt |
| --- | --- | --- | --- |
| launcher (in-process) | default runtime = host subprocess, inherits full kernel env + sockets/fs | CMP-5/6, FND-10 | **B51 (new)** |
| launcher (container) | flat internal network, no `--network none`/egress proxy/allow-list | CMP-5/11, FND-10 | **B52 (new)** |
| broker run-token | no exp / no aud → replayable (mint high-entropy ✓, at-rest=B20) | CMP-3, FND-9 | **B53 (new)**; B20 |
| broker capability | caps = certified listing's own scopes; steward-grant check default-OFF | CMP-3, FND-2 | A4 |
| connector_gateway | `safe_endpoint` blocks only exact metadata host, permits private ranges, misses encodings (bounded; pinned path default-off) | FND-10 | A11/B16 |
| delivery (S-mat) | fail-open digest check + trusts unsigned listing cert, no `verify_certificate` | CMP-7, FND-8 | **B54 (new)** |
| delivery (launch) | digest rebind only on baked path; un-baked default skips | CMP-7, FND-8 | **B55 (new)** |
| certify (legacy) | signs caller-supplied digest; host ignores `conformance.verified` | CMP-7, FND-8 | **B56 (new)** |
| signing/provenance | no publisher/steward signature on a component version; prov in unsigned listing | CMP-7, REG-8, FND-14 | **B23 (extended)**; A67 |
| trust root | TOFU — host trusts `{network}/v1/authority` key, no pinned anchor | FND-2/14 vs 3/15 | note |
| aos.js (client SDK) | `/bridge/*` as the contract + `AOS.run(verb)`/`AOS.get/post(any)` + client `app_id` | CLI-6, PTC-12 | A23 |
| embed SDK | self-asserted scope → `service:"*"` consent; role-bearing 1h JWT in sessionStorage; demo redirect bypass | CLI-2/3, FND-13, B1 | B12, B1/B31, A47/A48 |
| aos SDK (deploy/upload) | `/bridge/file-push`+`/bridge/component-publish`; cleartext bearer+cookie to plain-http IP; self-asserted-tenant dev-token | CLI-6, FND-9/10 | A50/A51/A54; server B41 (fixed) |
| aos SDK (runtime) | **sound** — broker-only `/v1/*`, fail-closed token, no self-asserted roles, no token forging | FND-1/2, CMP-6 | — (positive) |

## Conformance cases (slice-6 delta)

`run_components_review_cases()` (new, wired into the internal branch) records the six NEW findings (B51–B56) as **SKIP_BUILD** with precise proposed tests. Each is a code-audit fact whose black-box reproduction needs a fixture the seeded healthy stack does not ship (a planted component printing its env; a placed container probing internal services; a captured run-token to replay; a cert'd component with differing on-disk bytes; a `component_asset` with no network listing; a `/v1/certify` with only an arbitrary digest). Their rules (CMP-5/6/7, FND-8/9/10) are **already VIOLATED** in the matrix from other cases, so the matrix reduction is unchanged; the SKIP_BUILD rows are additive coverage markers that name the exact test to build when each is fixed. The CLI-6/PTC-12 and DEBT-B12 findings are already represented in the matrix (VIOLATED/PLANNED) and in server-side conformance; the embed scope→`service:"*"` consent is the single most black-box-reproducible item (demo-embed seeded) and is the recommended first XFAIL when B12 is tackled.

## Debt opened / extended

- **B51** (HIGH, CMP-5/6/FND-10) — in-process runtime inherits host env (no confinement).
- **B52** (HIGH, CMP-5/11/FND-10) — placed container no egress policy (flat net).
- **B53** (MED, CMP-3/FND-9) — run-token no expiry/audience.
- **B54** (HIGH, CMP-7/FND-8) — on-demand filestore delivery fail-open + unsigned-listing-digest trust.
- **B55** (MED-HIGH, CMP-7/FND-8) — launch digest-rebind only on baked path.
- **B56** (MED, CMP-7/FND-8) — unverified-digest certify accepted; host ignores `conformance.verified`.
- **B23** (extended) — the no-publisher-signature REG-8 gap holds on the component-delivery side (CMP-7 PARTIAL), not only kernel registry rows.
- Notes (no id): TOFU trust root; `aos.js`-is-the-bridge (CLI-6/PTC-12/A23); `aos upload` cleartext creds + `solution.py` bridge client (A51/A54/B41); capability self-assertion (A4); connector SSRF filter (A11/B16).

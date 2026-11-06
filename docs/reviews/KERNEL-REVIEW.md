# Kernel review — Consolidation phase 5, slice 1

**Date:** 2026-11-06 · **Scope:** `kernel/` (branch `feat/admin-issuer-scope`) against the rules the Kernel is
responsible for: REGISTRY REG-1..REG-18; FOUNDATIONS FND-1/2/3/6/7/8/10/12/16; DECISION DEC-1..DEC-12 (the ones
the Kernel records); COMPONENT broker CMP-3/CMP-6. **Method:** three fresh, independent reviewer agents (not the
authoring session), read-only, findings-only — no kernel code was changed. Evidence is `file:line` in `kernel/`.

> **How to read this vs STATUS-MATRIX.md.** The matrix is *conformance-measured* (what the black-box/abuse cases
> prove); this review is a *code audit* (what the source actually enforces, fail-closed, with shipped defaults).
> They diverge on purpose: e.g. FND-1/FND-3 show **HELD** in the matrix (the forged-token abuse case is correctly
> rejected) but **VIOLATED** here (authority is still read off the token `roles` claim). Where they differ, the
> matrix states the tested surface and this review states the deeper gap. Covered-rule test additions from this
> slice are in `conformance/run.py` (`run_kernel_review_cases`); new debt is in `../consolidation/DEBT-REGISTER.md`.

---

## Summary (one page)

**Verdict counts (39 rule-blocks audited):** held **6** · partial **15** · violated **16** · not-applicable(not-kernel) **4**.

| spec | held | partial | violated | n/a |
|---|---|---|---|---|
| REGISTRY (18) | 5 (REG-1,3,4,9,10) | 6 (REG-2,6,7,11,12,16) | 7 (REG-5,8,13,14,15,17,18) | 0 |
| FOUNDATIONS (9) | 0 | 4 (FND-2,6,10,12) | 5 (FND-1,3,7,8,16) | 0 |
| DECISION+broker (12) | 1 (DEC-5) | 5 (DEC-2,3,9,CMP-3,CMP-6) | 4 (DEC-1,4,6,10) | 4 (DEC-7,8,11,12) |

**Top risks (cross-cutting, most serious first):**

1. **Enforcement ships inert — the Kernel's own gates default OFF/shadow in production** (FND-8, FND-16, REG-5,
   REG-7 — *critical*). `REQUIRE_AUTH` (`api/kernelcore.py:19`), `PROV_ENFORCE` (`:60`), `DATAPLANE_ENFORCE`
   (`:62`), `REQUIRE_STEWARD_GRANT` (`:63`) all default OFF; audience/issuer binding is empty/shadow
   (`services/authn.py:24-25,29`). Unattributed and uncertified "fact" writes are admitted-and-logged, not
   refused; the no-anonymous posture rests on per-handler reach gates rather than a global requirement.
2. **Unauthenticated `/v1/components/install` is not admin-gated and reaches the run-token mint path** (FND-8 —
   *critical*, **NEW** DEBT-B22). `api/app.py:2074-2094`: no admin gate, `_authenticate(...) or {}`, tenant
   fallback, `_install_one` mints+returns a broker run-token (a bearer secret). Distinct from the fixed DEBT-B15.
3. **Authorization is asserted, not recorded — and leaves no decision trail** (FND-1/FND-2, DEC-1/DEC-4/DEC-6 —
   *critical/high*, **NEW** DEBT-B27). Admin/platform-service authority is read off the token `roles` claim
   (`kernelcore.py:52,86`); the kernel authz gate emits **no decision record on allow or deny**, and fail-closed
   denials (`_read_reach`→DENY→empty set) are silent — the decision library (`services/decision/*`) is a correct
   but disconnected skeleton nothing on the live path calls.
4. **The Kernel is not self-contained for authz inputs** (FND-7 — *high*, DEBT-B9). It calls the Network over HTTP
   for schema defs, cross-tenant grants, the authority key and tenant classification (`app.py:1783,1926,2271,1819`);
   Network-down degrades/denies and the standalone fallback self-signs its own authority with no check.
5. **Registry integrity + privacy primitives are unbuilt or mislocated** (REG-8/REG-14/REG-16/REG-17/REG-18 —
   *high*, **NEW** DEBT-B23/B24/B25/B26). Versions are unsigned (SHA-256 content hash only); there is no erasable
   personal-data store (retract retains content); `/v1/registry/archive` physically deletes with no cold resolver
   and can purge live versions; no field-level encryption (plaintext JSONB); files are a flat digest-is-capability
   blob store with no per-file authority.

**New debt opened by this review:** DEBT-B22 (unauth install run-token), DEBT-B23 (unsigned versions),
DEBT-B24 (archive-then-delete), DEBT-B25 (no erasable store), DEBT-B26 (no field encryption), DEBT-B27 (no
decision record on authz), DEBT-A75 (REG-2 ungoverned-shape + latest-version stamp), DEBT-A76 (REG-1 resurrect
cross-schema rebind). Existing debt confirmed live: DEBT-A1..A9, A17, A28, A40, A72, B1, B2, B3, B5, B7, B8, B9,
B10, B12, B13. (DEBT-B19 "object.id ≠ registry id", already flagged for this review, is confirmed under REG-1.)

---

## REGISTRY (REG-1..REG-18)

| rule | verdict | sev | evidence (kernel/) | debt |
|---|---|---|---|---|
| REG-1 permanent ids | held | info | single-table bitemporal keying `pg_store.py:27-34`; version auto-increment `:209-210`; retract = tombstone version, never deletes `:262-280`; `rv_one_open` partial-unique `:67` | DEBT-A76 (NEW, resurrect cross-schema rebind unchecked, `store.py:115-116`); DEBT-B19 (object.id≠registry id) |
| REG-2 schema-governed writes | partial | medium | `SCHEMA_VALIDATE` default **strict** `kernelcore.py:71`; but ungoverned/no-`properties` defs skip validation `app.py:2297-2299`, and the Kernel stamps LATEST not caller-declared version `:2296/:2243-2244` | DEBT-A12, DEBT-A75 (NEW) |
| REG-3 versions not edits | held | info | append-only; close prior `tx_to` + INSERT new in one txn `pg_store.py:211-214`; no UPDATE of `object` on the write path | — (ADR-0052) |
| REG-4 valid + recorded time | held | info | both axes stored `pg_store.py:30-33`, queried independently `resolve_as_of` `:391,438-441` (timestamptz compare) | — (unit test `tests/test_registry_bitemporal.py`) |
| REG-5 write authority | **violated** | critical | single gate exists `_assert_write_own_tenant app.py:1081-1107` but own-tenant authority from the token `tenant` claim `:1090-1094`; `PROV_ENFORCE`/`DATAPLANE_ENFORCE`/`REQUIRE_STEWARD_GRANT` default OFF `kernelcore.py:60,62,63`. Cross-tenant lane DOES require a signed grant `app.py:1103` | DEBT-B1, B2; A2, A3, A4, A17 |
| REG-6 read authority; exists=read | partial | medium | exists/count/resolve all fail-closed BEFORE answering (`_read_reach`→DENY→empty `app.py:1046-1057,1224-1226`; exists `:1247-1249`; count `:259-260`) independent of REQUIRE_AUTH — a correction to the spec's "to confirm". Residual: `REQUIRE_AUTH` default OFF `kernelcore.py:19` | DEBT-A1, B8 |
| REG-7 provenance | partial | high | writer agent from verified creds only `app.py:875-897`, stored `pg_store.py:212-214`; but `PROV_ENFORCE` OFF → unattributed write accepted + shadow-logged `app.py:117-120` | DEBT-A2, A40 |
| REG-8 Kernel/participant signature | **violated** | high | versions are SHA-256 content-hashed, NOT signed `store.py:35-37`; signer (`receipts/crypto.py`) used for receipts/keys only; `tools/audit_verify.py:20-24` confirms no signature, no hash chain | DEBT-B23 (NEW) |
| REG-9 idempotent writes | held | info | content-hash dedup on write (byte-identical re-put returns existing ref, no new version) `pg_store.py:202-207,242-247`; hash excludes version `store.py:36` | — (upgrade from spec "to confirm") |
| REG-10 deterministic resolution | held | info | `DISTINCT ON (id) … ORDER BY id, tx_from DESC` `pg_store.py:457-459`; fast path via `rv_one_open`; id tiebreaker + keyset paging `query.py:71-97` | — (breaks across archive boundary — see REG-16) |
| REG-11 schemas are records; owner≠adopter | partial | low-med | Kernel does NOT hold schemas as its own records — fetches upward `app.py:2269-2272`; dev-sandbox local catalog is dev-tenant-gated `:779-811`. Largely Network-owned | DEBT-A18, A22, B9 |
| REG-12 audit of trust-bearing records | partial | high | admin-gate audit per call `app.py:29-42`→`adminaudit.py:70-92`; but not durable on DB-fail (in-mem ring, non-blocking `:5-12,89-91`), failed-auth not logged, no before/after, no hash chain `audit_verify.py:23-24` | DEBT-A9, B10 |
| REG-13 domain-blind | **violated** | high | domain vocab baked into enforcement: `_NAT_KEYS app.py:1279`, `_DATAPLANE_PREFIXES :1163-1169`, event-skip prefixes `:81-84`, public allow-list `:1037`, `SHARED_SCHEMAS :229-230` | DEBT-B8, B7 |
| REG-14 erasable personal-data store | **violated** | high | not built — no erasure endpoint/store/reference-split; retract retains `object` (`store.py:140`, `pg_store.py:277-279`); consent (ADR-0125) not enforced | DEBT-B25 (NEW), B12 |
| REG-15 public = schema-level via CR | **violated** | medium | "public" is a hardcoded kernel allow-list `_public_schema app.py:1031-1037`, not a schema field set by CR (per-object `access.grant` exists `:955-985` but is per-record) | DEBT-B8 |
| REG-16 archiving in protocol | partial | high | archive IS implemented (contra spec "PLANNED") `app.py:669-702`/`610-657`→`pg_store.py:516-537` — but DELETEs from hot store with **no cold resolver** (archived versions unresolvable, REG-10 breaks) and `history_only=False` purges live versions | DEBT-B24 (NEW); #201/#202 |
| REG-17 field encryption | **violated** | high | not built — plaintext JSONB `pg_store.py:30,212-214`; no encrypt/decrypt/blind-index/HMAC/Vault-transit; idempotency is plain SHA-256 not keyed HMAC `store.py:35-37` | DEBT-B26 (NEW); ADR-0126 |
| REG-18 files are records | **violated** | high | flat content-addressed blob store; `/v1/file/{put,get}` gate only on run-token presence, proxy to filestore, no per-file authority/receipt/encryption `app.py:1632-1666` ("possessing the digest is the read capability") | DEBT-A72, B5 |

## FOUNDATIONS (FND the Kernel enforces)

| rule | verdict | sev | evidence (kernel/) | debt |
|---|---|---|---|---|
| FND-1 identity carries no authority | **violated** | high | admin/platform-service authority read off token `roles` claim `kernelcore.py:52-53,86-87`; mitigated by HOME-issuer binding + no bare-slug, but a home-issued role claim IS the authority; `_effective_roles` unions token roles `app.py:992-1006` | DEBT-B1 |
| FND-2 authority only from recorded grants | partial | high | recorded-grant lookups exist + fail-closed for per-object/cross-tenant data (`_active_grant app.py:955-985`, `_steward_authorizes :1907-1940`); but admin/platform spine decides on token roles, not a grant lookup | DEBT-B1, B3, A66 |
| FND-3 nothing implied by tenant/classification; self-asserted roles stripped | **violated** | med-high | classification drives authz (`_is_dataplane_schema app.py:1168-1169`, `_public_schema :1031-1037`, `SHARED_SCHEMAS :228-230`); issuer used only to restrict (good) but roles read directly `:994` | DEBT-B7, B13 |
| FND-6 domain-blind / unknown opaque | partial | medium | opaque-unknown held (`_schema_def`→None→skip validate `app.py:2262-2299`); but domain nouns baked in (`_EVENT_SKIP_PREFIXES :81-84`, `_DATAPLANE_PREFIXES :1163`, `_identifier_schemas :1281`) | DEBT-B8 |
| FND-7 authorizes with Network down | **violated** | high | upward HTTP for authz inputs: schemas `app.py:2271`, grants `:1926`, tenant class `:1819`, authority key `:1783`; standalone self-signs `:1771-1792` and `_authority_verifies`→True when no pubkey `:2360-2361` | DEBT-B9 (ADR-0123) |
| FND-8 fail closed | **violated** | critical | enforcement defaults OFF/shadow: `REQUIRE_AUTH kernelcore.py:19`, `PROV_ENFORCE :60`, `DATAPLANE_ENFORCE :62`, `REQUIRE_STEWARD_GRANT :63`; aud/iss empty/shadow `authn.py:24-25,29`. **NEW**: unauth `/v1/components/install` mints a run-token `app.py:2074-2094` | DEBT-A1-A6; B22 (NEW) |
| FND-10 least privilege & scope | partial | medium | reads own-tenant+shared steward `app.py:1053-1054`, cross-tenant read needs signed grant `:1202-1203`, writes own-tenant unless signed grant `:1081-1107`, egress declared-host fail-closed `:1596-1598`; weakened by `REQUIRE_STEWARD_GRANT` off `:1447` + `SHARED_STEWARD=airawat` `:228` | DEBT-A4, A19, B7 |
| FND-12 every decision audited; failed-auth logged | partial | high | admin gate + egress audit allow+deny (`app.py:37-38`; `:1524-1537`); but general read/write denials emit nothing (`:1225-1226,1105`), failed AUTHENTICATION not logged (`kernelcore.py:44-46`), audit non-blocking + ring not durable | DEBT-A9, B5, B10 |
| FND-16 safe defaults | **violated** | critical | prod-pointing defaults (`HOME_ISS ds:airawat:identity kernelcore.py:31`, `SHARED_STEWARD airawat app.py:228`, authority key/participant/tenant fallbacks); enforcement defaults OFF (FND-8); missing config does NOT stop startup (JWKS unset→skip verify `kernelcore.py:42-43`; NETWORK_URL unset→self-sign `app.py:1789-1792`) | DEBT-A7, A8, A1-A6, A30; B8 |

## DECISION (Kernel-recorded) + COMPONENT broker

**Structural finding:** `services/decision/{objects,loop,compliance}.py` build correct, immutable, version-pinned,
replayable MDK records — but **nothing on the kernel's live authorization path calls them**. The authz gates
(`_read_reach`, `_assert_read_object`, `_assert_write_own_tenant`, broker `_require`) return rows or raise 403/401
and emit **no decision record** on allow or deny; the only allow/deny trails are `adminaudit` (admin endpoints) and
`prov.egress` (external calls), neither a decision record.

| rule | verdict | sev | evidence (kernel/) | debt |
|---|---|---|---|---|
| DEC-1 record on allow AND deny | **violated** | high | authz plane emits nothing: `broker_read` returns obj / raises 403 `app.py:1368`; `broker_write` returns a receipt not a decision `:1453`; `_read_reach` returns a mode tuple `:1040-1057` | DEBT-A9, B27 (NEW) |
| DEC-2 contents | partial | medium | where built (`compliance.decide`, `objects.decision objects.py:89-107`) it is good (case_ref, version-pinned admitted_basis, authority, reason) — but never runs on the authz path; the live admin-audit row has no policy version/pinned inputs/reason codes | B27; ADR-0046 |
| DEC-3 replayable | partial | low | `loop.reconstruct loop.py:75-89` resolves refs + reports missing; version-pinning enforced `objects.py:76`; not on the authz path | ADR-0046 |
| DEC-4 deciding authority recorded+named | **violated** | high | `objects.authority objects.py:80-86` records whatever agent is passed with no live-grant check; `compliance.decide` defaults `authority_agent=…officer compliance.py:26`; authz path names no authority | DEBT-B3, B27 |
| DEC-5 never edited | held | info | decision records are governed append-only (REG-3); `previous_decision`/`correction_reference` fields `objects.py:104-106` for supersede-by-reference (flow not exercised in kernel) | REG-3 |
| DEC-6 denials recorded (incl fail-closed) | **violated** | critical | every deny a bare exception, no record (`_require broker.py:72-76`→403 `app.py:60-62`; `_assert_*` 403/401); fail-closed `_read_reach`→DENY→empty set is silent `app.py:1057` | DEBT-A9, B27; FND-8 |
| DEC-7 personal data by reference | n/a | info | inherits REGISTRY REG-14 (registry-layer, unbuilt), not a decision-emission defect | REG-14 |
| DEC-8 reason codes; subject access | n/a | info | subject access = per-object sharing (ADR-0103)+apps; note: reason text is free-text not a governed vocabulary `compliance.py:53-54` | — |
| DEC-9 linked (correlation/op ids) | partial | medium | `adminaudit` per-call `correlation_id app.py:35` threads nothing beyond its own row | FND-14, REG-12 |
| DEC-10 full vs aggregated depth | violated(by absence) | low | no tiered logging because DEC-1 emits nothing; moot until DEC-1 lands | DEBT-A9 / DEC-1 |
| DEC-11 contest flow | n/a | info | Inbox/Case + service layer (ADR-0048), not the kernel | — |
| DEC-12 automated decisions | n/a | info | engine write-grants to governance.decision = components/ADR-0056 (DEBT-B18), not the kernel | DEBT-B18 |
| CMP-3 run token = declaration ∩ authority | partial | medium | declaration∩install-tenant half holds (`_install_caps app.py:2019-2028`, broker default-deny `broker.py:32-38,72-76`); the ∩-runner-authority half absent — run token is a bearer secret `_mint_run_token app.py:1119-1123`; dev-token gets scope `*` `broker.py:36` | DEBT-A28 |
| CMP-6 records & files only via broker | partial | high | records: held — all component record I/O via the Broker, attributed + sealed `broker.py:79-137`. files: **violated** — `/v1/file/{put,get}` bypass the broker, no cap/scope check, no receipt `app.py:1632-1666`. dataplane sideload: `/v1/registry/objects` + `DATAPLANE_ENFORCE` shadow lets a bare token write fact records `app.py:109,1172-1183` | DEBT-A72; REG-18; DATAPLANE shadow |

---

## Conformance cases added (step 3)

`conformance/run.py` → `run_kernel_review_cases()` (internal mode): one live black-box XFAIL reproducing the NEW
unauth-install finding (**FND-8/NEW** — unauth `/v1/components/install` → 404, not 401/403 = ungated), plus recorded
SKIP_BUILD entries (with the reason each is not cleanly black-box reachable + the proposed internal pytest) for the
remaining Kernel-relevant NO-TEST rules: REG-2, REG-4, REG-8, REG-9, REG-11, REG-18, FND-12, DEC-2, DEC-5, DEC-9,
CMP-3, CMP-6. Verified both modes (internal 15 PASS / 4 XFAIL / 0 FAIL; external 14 PASS / 2 XFAIL / 0 FAIL).
`STATUS-MATRIX.md` regenerated: the NO-TEST Kernel rows are now PLANNED(needs-build) (recorded) and FND-8 stays
PARTIAL. The deeper `violated` verdicts above live here in the review (the matrix reports only what the black-box
suite can measure).

---

## Appendix — EC2 production exposure of `/v1/components/install` (read-only, 2026-11-06)

**Question (slice-1 step 2):** does the production kernel expose `/v1/components/install`, and does any app-host
bridge reach it without its own check?

**Findings (read-only; no POST to prod, no SSH mutation):**
- **Not publicly routed.** `deploy/ec2/nginx/nginx.conf` has **no public kernel location** ("OS kernel API: NO
  public route — internal kernel:8080 only"); public locations are `/network/`, `/kc/`, `/` → app-host. Confirmed
  live with read-only GETs: `https://airos.airawat.org/healthz` → 200, but `/kernel/v1/components`,
  `/kernel/healthz`, `/kernel/v1/components/install` all → **404** (they fall through to app-host, which has no
  such route). The kernel port is internal to the compose network (not published to the host).
- **The only public install path is app-host `/bridge/install` → `_do_install`, which has its OWN gate**
  (`platform-spec/reference/routes/marketplace_routes.py:68`): `if not (ADMIN_ROLES & claims.roles)` →
  `PermissionError` (tenant-admin required; a dev/sandbox Studio-builder is the only exception). app-host
  authenticates the session before dispatching the bridge.
- **Net:** the ungated kernel endpoint is **not internet-exposed**. The residual is defense-in-depth only — any
  service co-resident on the EC2 docker network could call `kernel:8080/v1/components/install` unauthenticated and
  obtain a run-token (a lateral-movement path that already presupposes an internal compromise). EC2 runs a kernel
  image **predating** the hotfix, so this intra-network gap persists there until the image is rebuilt + redeployed.

**Containment — NOT warranted as an emergency** (no public exposure), and **not run** (EC2 is out of scope this
slice). The correct remediation is to bake + redeploy the hotfixed kernel image; the exact sequence (for a later,
in-scope EC2 slice) is:

```
# BUILD + PUBLISH the hotfixed image (from the kernel repo @ b04b8d9, branch feat/admin-issuer-scope):
docker build -f kernel/deploy/Dockerfile -t manishsv/airawatos-kernel:dev-hard6 kernel
docker push manishsv/airawatos-kernel:dev-hard6
# On EC2 (pin the new tag in the prod compose, then):
docker compose -f <ec2-compose.yml> pull kernel && docker compose -f <ec2-compose.yml> up -d kernel
# UNDO (roll back to the pre-hotfix tag if the install flow regresses):
#   repin kernel image -> manishsv/airawatos-kernel:dev-hard5 (current prod tag) and `up -d kernel` again.
```

If a belt-and-suspenders *interim* containment were wanted before the redeploy (it is not necessary given no public
route), the only meaningful measure is to confirm the kernel port stays unpublished (it already is — internal
`8080/tcp` only; no host port binding to remove). No nginx `deny` is applicable because no public kernel location
exists to deny.

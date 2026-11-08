# R5 — independent assessment of the four items slice 1g left open

Reviewer: independent (did not build slice 1g, was not on the first exit review). Date 2026-11-08.
Scope: findings and assessment only. Nothing in code, config, Vault, git or the running containers was changed. The probes
were reads: anonymous GET/HEAD/OPTIONS calls, anonymous POSTs with an empty body to auth-gated routes, `psql`
catalog SELECTs, `pip download`, and throwaway images tagged `r5-rereview-amd64:*`. The `:1g` tags were not touched.
Scratch: `/Users/manishsv/.claude/jobs/8ad4875a/tmp/rereview/` (amd64/, scripts/, routes.json, live.json, openapi_live.jsonl).

| # | item | severity | owning layer | verdict |
|---|---|---|---|---|
| 1 | amd64 reference image not proven | Med | L1 (build/release) | **blocks pre-production only** (with one caveat, below) |
| 2 | kernel/network/reference env switches vs the production guard | **High** (for production) | L1 guard; flags L2/L3/L4/L6 | **blocks pre-production**. The guard's L1 part (AIRAWAT_ENV fail-open, SCHEMA_VALIDATE=off) should be fixed before L1 exit. |
| 3 | B92 N1, routes the route extractor misses | **High** (the net is blind on the secrets service and the governance plane) | L1 (net 4) | **blocks L1 exit** |
| 4 | B93, the ARC-3 DB-grant audit is not a case | Med | L1 (nets 2 and 7) | **blocks L1 exit**, because FIX-PLAN lists "the DB-grant audit" as a Layer-1 missing test this layer builds |

---

## Item 1 — amd64 reference image not proven

### Findings
1. **Every pinned dependency has a linux x86_64 cp311 wheel. This is not a lock defect.** `pip download` for
   x86_64 manylinux tags with `--only-binary=:all: --python-version 3.11` fetched all 27 entries in
   `platform-spec/requirements.reference.lock` (exit 0). The same check passes for `kernel/deploy/requirements.lock` (30/30) and
   `network/deploy/requirements.lock` (30/30). A first attempt with only manylinux2014/2_17/2_28 tags failed on
   `nvidia-nccl-cu12==2.32.3`. That was an artifact of my tag list: the wheel exists as `manylinux_2_27_x86_64`, and pip
   on the real amd64 image picks it.
2. **Only pyarrow crashes, and the crash is an emulation artifact.** I built the reference base with all 27 x86_64 wheels,
   tagged `r5-rereview-amd64:scratch` / `:scratch2`, under the Docker Desktop builder (QEMU user-mode). Then I imported
   each module in a fresh container:
   ```
   cryptography ok 50.0.2 · psycopg2 ok 2.9.9 · h3 ok 4.5.0 · numpy ok 2.4.6 · shapely ok 2.2.0
   pyarrow: qemu: uncaught target signal 11 (Segmentation fault) - core dumped
   xgboost ok 3.2.0 · sklearn ok 1.9.1 · scipy ok 1.17.1 · pyproj ok 3.7.2 · yaml ok 6.0.3
   osmium: ok once libexpat1 is installed (the real Dockerfile installs it; my first scratch image did not)
   ```
   The emulated CPU advertises SSE4.2, POPCNT, AVX, AVX2, FMA3, BMI2 and F16C (numpy `__cpu_features__`), but not AVX-512.
   So this is not a missing-baseline-ISA problem of the x86-64-v2/v3 kind. The crash is reported by `qemu:` itself
   ("uncaught target signal 11"). pyarrow is the one module here that loads a very large C++ library with heavy static
   initialisers and its own allocators (jemalloc/mimalloc). Segfaults of that library under QEMU user-mode are a known
   class of emulation failure.
   Variant runs: PYARROW_VARIANTS_PLACEHOLDER
   Conclusion: **an emulation artifact, not a wheel or lock defect.** It is still unproven until something runs on real
   amd64.
3. **The services in this image do not use the crashing dependency.** No module in `platform-spec/reference` or
   `components/_common` imports pyarrow, xgboost, sklearn, numpy, shapely, h3, osmium, pyproj or scipy. They are used only by
   marketplace components (`components/engines/pm25-*`, `drivers/corpus-builder`). ADR-0093 strips those components from
   this image, and production refuses in-process placement (`AIRAWAT_INPROCESS_COMPONENTS`). On the `:1g` image these
   dependencies are about 850 MB of the 1.3 GB site-packages: `nvidia` (NCCL, pulled in by xgboost) 471 MB, xgboost 227 MB,
   pyarrow 153 MB. They add attack surface and CVE load to every service container, and they are the only reason the
   amd64 smoke test fails.
4. **Production is amd64, and the docs say so.** `deploy/PRODUCTION-READINESS.md` §1: "Production is amd64, so production
   images **must be built on a native amd64 builder** … never cross-emulated on the Mac." `deploy/RELEASE-PLAN.md` ships
   "new amd64 image from … HEAD" for network and reference. The target is EC2 (`airos.airawat.org`). That doc's
   attribution ("segfaulted importing numpy/scipy/xgboost/osmium") is stale or wrong: those import fine, and only pyarrow
   crashes.
5. **Kernel and network are also arm64-only.** IMAGES.lock.json records `linux/arm64` for all three `:1g` images. The
   DEBT-B94 note names amd64 only for the reference image, but no amd64 digest exists for any of the three.
6. **"A native amd64 build (CI) must record the digest" has nowhere to run.** `verify/ci/reference-pipeline.yml` is a
   "HANDOVER artefact, not wired into any CI system", and `verify/ci/checkout-siblings.sh` does not exist.

### Risk
Low that the image is broken on amd64: every wheel exists and the one crash is emulator-specific. Med that it ships
unverified, because the first real amd64 execution would happen in production. The lock files pin versions but carry
**no hashes** (see R5-6).

### Verdict and closing condition
**Blocks pre-production only.** Layer 1's exit gate is about the local install and its nets, and that runs on arm64.
Caveat: if L1 exit is meant to include "fresh install + conformance green in CI" on a real runner, and that runner is
amd64, the amd64 build becomes an L1 deliverable.
Smallest closing condition:
- `docker build -f platform-spec/Dockerfile.reference` on a native x86_64 host (or a CI runner) passes the in-Dockerfile
  import smoke test, and the amd64 image id/digest is recorded in IMAGES.lock.json.
- The same for the kernel and network images.
Cheaper alternative that also shrinks risk: move pyarrow, xgboost, sklearn, scipy, numpy, shapely, h3, osmium and
pyproj out of the services image and into the component runtime images. The smoke test then covers only what the
services import, and it passes under emulation.
Also correct PRODUCTION-READINESS §1 (only pyarrow crashes) and the B94 note (kernel and network are arm64-only as well).

---

## Item 2 — env switches outside gateflags.py vs the production guard

### How the guard works (verified by reading and running it)
`deploy/local-dev/prod-guard.sh` calls `gateflags.py guard` **only if** `AIRAWAT_ENV` ∈ {production, prod}. Otherwise it
`exec`s the service directly. `gateflags.production_violations()` refuses only these:
- any `*_SHADOW` key, plus `SCHEMA_SHADOW_SCHEMAS`;
- the 5 named conveniences unless they are unset or off;
- `SCHEMA_VALIDATE == "shadow"`;
- the `--no-verify-cert` arg;
- a static VAULT_TOKEN.

**It is a deny-list of values that are present. It cannot see weakening by absence.** Run directly against the guard:
```
AIRAWAT_ENV=production (nothing else)                 violations=[]   ← kernel would start auth/prov/dataplane = shadow
KERNEL_REQUIRE_AUTH=0                                 violations=[]
PROV_ENFORCE=0, DATAPLANE_ENFORCE=no                  violations=[]
COMPONENT_ENFORCE=0 / DEV_REQUIRE_DEVELOPER=0         violations=[]
SCHEMA_VALIDATE=off                                   violations=[]   ← weaker than "shadow", which IS refused
HOUSE_RULES_ENFORCE=0 / RUNTIME_ATTEST=0              violations=[]
CONNECTOR_PINNED_ENDPOINT_OK=1                        violations=[]
NOTIFY_ALLOWED_CALLERS widened (+app-host)            violations=[]
AIRAWAT_ENV unset or "staging" + FILESTORE_SHADOW=1   prod=False → guard exits 0, service starts in shadow
IDENTITY_AUD_ISS_SHADOW=1 / AIRAWAT_EPHEMERAL_OK=1    refused (covered)
```
The live kernel today (local-dev, the reference posture) logs:
`[enforce] posture · auth=shadow · prov=shadow · dataplane=shadow · component=ENFORCE · steward-grant=ENFORCE · schema=strict · aud=ENFORCE · iss=ENFORCE`.
`docker-compose.dev.yml` does not set KERNEL_REQUIRE_AUTH, PROV_ENFORCE or DATAPLANE_ENFORCE.

### Classification — every env switch that can weaken enforcement (kernel, network, platform-spec/reference)
"Default" means the behaviour when the variable is unset. A "BY ABSENCE" entry means the unsafe state is the default, so
production must set the variable explicitly. The guard cannot detect that.

| switch (file) | parse / default | weakening value(s) | guard? |
|---|---|---|---|
| KERNEL_REQUIRE_AUTH (kernel/api/kernelcore.py:19) | on iff 1/true/yes; **default off** | unset, or any other value ("on" counts as off) | **NOT covered** (by absence) |
| PROV_ENFORCE (kernelcore.py:60) | same, **default off** | unset/other | **NOT covered** (by absence) |
| DATAPLANE_ENFORCE (kernelcore.py:62) | same, **default off** | unset/other | **NOT covered** (by absence) |
| KERNEL_REQUIRE_STEWARD_GRANT (kernelcore.py:63) | same, **default off** | unset/other | **NOT covered** (by absence) |
| COMPONENT_ENFORCE (kernelcore.py:61) | off iff ''/0/false/False; default on | "", 0, false | **NOT covered** |
| DEV_REQUIRE_DEVELOPER (kernelcore.py:67) | on iff 1/true/yes; default on | 0, or **any non-listed value incl. "on"/"enforce"** (fail-open parse) | **NOT covered** |
| SCHEMA_VALIDATE (kernelcore.py:71) | default strict | `shadow` (covered), **`off`** (not covered) | partial |
| SCHEMA_SHADOW_SCHEMAS | — | any | covered |
| IDENTITY_AUD_ISS_SHADOW (kernel/services/authn.py:29, own parser) | on iff 1/true/yes | set at all | covered (name ends `_SHADOW`). The kernel's parser differs from gateflags (it ignores "on"), but the guard refuses any value, so production is consistent. |
| IDENTITY_EXPECTED_AUD / _ISS (authn.py:24-25) | **empty ⇒ aud/iss NOT enforced** | unset | **NOT covered** (by absence) |
| IDENTITY_JWKS (kernelcore.py:20; network/api.py:19) | unset ⇒ the kernel `_authenticate` returns None for ANY bearer, so **`Bearer junk` satisfies KERNEL_REQUIRE_AUTH**; network lookups return anonymous | unset | **NOT covered** (by absence) |
| IDENTITY_CLOCK_SKEW (authn.py:22) | 30 s | large value | NOT covered (low) |
| CONNECTOR_PINNED_ENDPOINT_OK (kernel/api/app.py:419) | on iff `!= "0"`, so **"" / "false" / "no" = ON** (fail-open parse); this is the A2 SSRF guard | anything but "0" | **NOT covered** |
| EVENT_SKIP_SCHEMA_PREFIXES (app.py:85) | list | widening skips event emission | NOT covered (low) |
| PLATFORM_SERVICE_ROLES, SHARED_SCHEMAS, PLATFORM_CONTROL_SCHEMAS, RUN_TOKEN_READERS (kernel) | lists | widening = more cross-tenant reach | NOT covered (widening) |
| REGISTRY_BACKEND (kernel/services/registry/__init__.py:21) | **default memory** (non-durable) | unset | NOT covered (by absence; durability, not authz) |
| PLATFORM_AUTHORITY_MODE (network/trust_wiring.py:68) | **default shadow** (tenant fallback) | unset/anything but enforce | **NOT covered** (by absence) |
| NETWORK_ADMIN_AUTHZ (network/trust_admin_authz.py:68) | **default legacy** (tenant==network) | unset/anything but role | **NOT covered** (by absence) |
| TRUST_ENFORCE_STEWARD_PROVENANCE (network/trust/roles.py:31) | on iff == "1"; **default off** | unset/other | **NOT covered** (by absence) |
| HOUSE_RULES_ENFORCE (network/api.py:2210) | off iff 0/false/False | 0 | NOT covered |
| VERB_NAMING_ENFORCE (network/api.py:2200) | **default off** | unset | NOT covered (by absence; low, naming) |
| **JOIN_EMAIL_DEV_ECHO (network/api.py:851)** | **default ON** | unset | **NOT covered** (by absence). See R5-1. |
| EXPECTED_AUDIENCE (network/api.py:29) | default "airawatos" | mis-set | NOT covered |
| NET_DOOR_CALLERS_JSON (network/api.py:324), AUTHORITY_ADMIN_TENANTS (366), TRUSTED_ISSUERS (25) | override/widen | widening | NOT covered (widening) |
| TRUST_AUDIT_HMAC_KEY (network/trust/contract/gate2a_run.py:80, migration/bootstrap_airawat.py:250) | **default "a"*48** | unset | NOT covered (tools, not the live service; still a literal default) |
| IDENTITY_PASSWORD_REQUIRED (platform-spec/reference/identity.py:589) | **default shadow** (passwordless login minted) | unset/anything but enforce | **NOT covered** (by absence; = B84/G2) |
| IDENTITY_SEED_DEMO, AIRAWAT_EPHEMERAL_OK, AIRAWAT_INPROCESS_COMPONENTS, AIRAWAT_NO_VERIFY_CERT | conveniences | on/invalid | covered |
| AIRAWAT_ALLOW_PASSWORDLESS | covered, **but read by nothing** (B84/G3) | — | covered (dead) |
| VAULT_ADDR/VAULT_TOKEN absent → identity `_KEY_BACKEND = "local-dev"` (identity.py:611/639): an **ephemeral in-process signing key** | absence | unset | **NOT covered** (by absence). The guard catches a static token, not the absence of Vault. |
| IDENTITY_PER_TENANT_ISSUER (identity.py:638) | default 0 | — | n/a (feature) |
| `*_ALLOWED_CALLERS` / `*_ACCEPT_AUD` (filestore, notify, model-gateway, runtime-manager, secrets, scheduler, identity, automation) | `is not None` ⇒ override | widening | **NOT covered** (widening) |
| `*_SHADOW` (FILESTORE, NOTIFY, MODELGW, SCHEDULER, AUTOMATION, …) | gateflags | set | covered |
| SUBSCRIPTION_ENFORCE (automation.py:87) | **default off** | unset | NOT covered (by absence) |
| RUNTIME_ATTEST (runtime_manager.py:129) | default on; off iff == "0" | 0 | NOT covered |
| SEED_DATA_TENANT (network/ensure_install.py:98) | default 0 | 1 | NOT covered (installer-time) |
| LOCAL_STEWARDS (scheduler.py:267), FIRST_PARTY_STEWARDS (app_host.py:78) | lists | widening | NOT covered |
| **AIRAWAT_ENV itself** | guard active only for production/prod | unset / "staging" / typo | **NOT covered**: every check is skipped (fail-open on the guard's own switch) |

### Risk
In production the posture is whatever the operator remembered to set. Twelve or more enforcement switches are unsafe by
default, and the guard cannot see any of them. Mitigation observed live: the kernel's per-handler checks fail closed for
anonymous callers even with auth=shadow. Anonymous `/v1/registry/query|count|resolve|exists` return empty, and
`/v1/components` returns 403. So `KERNEL_REQUIRE_AUTH` is a belt, not the only lock. PROV, DATAPLANE, the
authority/admin-authz modes, password enforcement and aud/iss binding are the real gates, and all of them are open by
default.
Two parse bugs fail OPEN on non-standard values:
- `CONNECTOR_PINNED_ENDPOINT_OK=""` or `"false"` enables pinned endpoints, which reopens the SSRF path.
- `DEV_REQUIRE_DEVELOPER=on` disables the developer gate.

### Verdict and closing condition
This is DEBT-B84, still OPEN. The first review marked it non-blocking for L1, with owners L2/L3/L4/L6 per flag.
I agree the **flags** belong to their layers and **block pre-production**. Two parts are the guard's own logic (L1),
are cheap, and I would close them before L1 exit:
(a) the guard is a no-op unless `AIRAWAT_ENV` is exactly production/prod;
(b) `SCHEMA_VALIDATE=off` passes while `shadow` is refused.
Smallest closing condition:
- (L1) gateflags gains a **required-posture allow-list**: for each enforcement switch, the value production MUST have,
  with **unset treated as a violation** (KERNEL_REQUIRE_AUTH=1, PROV_ENFORCE=1, DATAPLANE_ENFORCE=1,
  KERNEL_REQUIRE_STEWARD_GRANT=1, IDENTITY_PASSWORD_REQUIRED=enforce, PLATFORM_AUTHORITY_MODE=enforce,
  NETWORK_ADMIN_AUTHZ=role, TRUST_ENFORCE_STEWARD_PROVENANCE=1, IDENTITY_EXPECTED_AUD/ISS non-empty,
  IDENTITY_JWKS set, JOIN_EMAIL_DEV_ECHO=0, SCHEMA_VALIDATE=strict, CONNECTOR_PINNED_ENDPOINT_OK unset/0).
- (L1) The guard refuses `SCHEMA_VALIDATE` ≠ strict.
- (L1) The guard decides "production" fail-closed: refuse unless `AIRAWAT_ENV` is an explicit known value, or invert the
  relationship so production is the default.
- (L1) A `gateflags_test` case for each entry.
- (owning layers) The kernel and network parse their switches through gateflags.state(), so the two fail-open parses go
  away. Alternatively, flip the defaults to enforce, which removes the "by absence" class entirely.

---

## Item 3 — B92 N1: routes the extractor misses

### Method
1. Ran `verify/route_extract.py` (→ routes.json).
2. FastAPI: pulled live `/openapi.json` from kernel and network (from inside app-host) and diffed.
3. stdlib: AST search for path comparisons in **every** handler-class method (not only `do_*`) and in module-level
   functions. Diffed against `verify/route-inventory.json`, which flags declarations the extractor never emits.
4. Live: from inside the network container, called GET/HEAD/OPTIONS on every path literal in each service's source plus 16
   common paths (/, /docs, /admin, /metrics, /debug, /files/x, /.env, …), 1,700+ requests. Recorded every non-404 that
   the extractor does not cover.

### Findings — routes the extractor misses
| service | missed routes | how dispatched | privileged? | anonymous result |
|---|---|---|---|---|
| **secrets** | **POST /set, /rotate, /copy, /status, /materialize, /fetch** (all six real routes; the extractor sees only GET /healthz) | `do_POST` → `self._post()` helper | **Yes, the most privileged surface in the stack**: write, rotate and copy tenant secrets, list secret metadata, return a RAW secret (/materialize), brokered egress with secrets (/fetch) | Code: /set,/rotate,/copy,/status call `_admin()` → `tokens.verify` → 401 before any read. /materialize,/fetch call `_secrets_gate_denied` → 403 first. **Not probed live:** my anonymous POST to the secrets service was refused by the session's permission classifier, so this rests on code reading. |
| **network** | **POST /v1/governance/grants, /grants/revoke, /memberships, /roles, /capabilities; GET /v1/governance/networks/mine, /capabilities, /memberships, /grants** (9) | `@app.post` decorators **inside** `register_trust_endpoints()` in `network/trust_wiring.py`, a file the extractor does not scan (FASTAPI lists only network/api.py). Registered only when TRUST_PLANE_ENABLED. | **Yes**: issue/revoke grants, assign roles, set memberships, define capabilities (the authority plane) | live: all 9 → **401** "invalid token: no token"; `Bearer garbage` → 401 |
| filestore | GET/HEAD /files/* | `do_GET`/`do_HEAD` → `self._get()` | yes (blob reads) | live 403 (GET and HEAD) |
| app-host | OPTIONS /embed/* (19 paths → 204) | `do_OPTIONS` (VERBS has no OPTIONS) | no: CORS preflight, empty body, ACAO only for registered origins | 204 |
| kernel, network | GET /docs/oauth2-redirect | FastAPI default | no: static Swagger HTML | 200 |

Not misses:
- app-host GET `/bridge/{doc-ask,query,fetch,…}` → 401. That is the `BRIDGE_LOGIN_REQUIRED` pre-check in `do_GET`, which
  runs for POST-only paths. There is no GET handler behind it.
- app-host `_bridge_vfs` "/projects" is a VFS path, not an HTTP route.
- Kernel: live openapi (41 ops) is fully covered by the extractor.
- Network api.py: 125 ops covered; only the trust_wiring routes are missing.

### Why this matters more than "N1 non-blocking" suggests
- `route_probe.py` probes **only the extractor's output**. The secrets POSTs are *declared* in route-inventory.json, so
  `route_inventory_test.py` only prints "stale declaration (no longer exposed)" and passes. **The anonymous-refusal net
  has never exercised a single privileged secrets route**, and FND-8's "every non-public route refuses anonymous" case
  is green without them.
- The 9 governance routes are neither declared nor probed. The "undeclared route fails CI" net cannot see them.
- B92's N1 text lists filestore, do_OPTIONS and oauth2-redirect. It **understates the gap**: it misses the secrets
  service (all of its POST routes) and the whole Trust governance plane.
- Today every missed privileged route refuses anonymous callers, confirmed live for network and filestore and by code for
  secrets. **No missed route is privileged and reachable without auth.** The exposure is in the assurance claim, not the
  current behaviour: a regression in any of these 17 routes would ship green.

### Verdict and closing condition
**Blocks L1 exit.** Net 4 is a Layer-1 deliverable whose exit gate says "route inventory … green". As built, the
net is blind to the two most privileged route families. Owning layer L1.
Smallest closing condition:
- (a) The stdlib extractor follows `self.<helper>()` calls from `do_*` (or treats any `self.path`/`route`/`u.path`
  comparison in the handler class as a route) and adds `do_OPTIONS`.
- (b) The FastAPI side is taken from the **live** `app.routes` / `/openapi.json` (the docstring already promises "introspected from the live
  `app.routes`", but the code scans two files' decorators). At minimum, add network/trust_wiring.py, plus FastAPI's
  `/docs/oauth2-redirect`.
- (c) A declared-but-not-extracted route **fails** the test instead of printing "stale".
- (d) The 9 governance routes are declared and anonymous-probed, the secrets POSTs are probed, and the six secrets "who"
  entries are corrected. The code gates /set,/rotate,/copy,/status by a tenant-admin user token, not by "svc:secrets
  from kernel/launcher" as the inventory says.

---

## Item 4 — B93: ARC-3 DB-grant audit

### Audit (read-only, `docker exec airawat-ld-postgres psql -U kernel -d kernel`; the superuser is POSTGRES_USER=kernel from compose)
```
 rolname          | super | createrole | createdb | login | repl | bypassrls
 identity_lockout |   f   |     f      |    f     |   t   |  f   |   f
 kernel           |   t   |     t      |    t     |   t   |  t   |   t      ← bootstrap superuser (not used by any service)
 kernel_app       |   f   |     f      |    f     |   t   |  f   |   f
 migrator         |   f   |     f      |    f     |   t   |  f   |   f
 network_app      |   f   |     f      |    f     |   t   |  f   |   f
role memberships: none · default privileges (pg_default_acl): none · functions in public: none · extensions: plpgsql
public schema ACL: pg_database_owner=UC, PUBLIC=U, migrator=UC, kernel_app=U, network_app=U, identity_lockout=U
database ACLs: kernel & postgres = NULL (PG default ⇒ PUBLIC CONNECT+TEMP)
table grants (non-superuser):
 identity_lockout → identity_login_fails  SELECT,INSERT,DELETE        (table owned by superuser kernel, not migrator)
 kernel_app       → kernel_admin_audit, kernel_authz_decision, kernel_kv, registry_schema_meta, registry_version
                    SELECT,INSERT,UPDATE,DELETE  (+ USAGE/SELECT/UPDATE on the 3 sequences)
 network_app      → network_kv  SELECT,INSERT,UPDATE,DELETE
 migrator         → owner of all tables except identity_login_fails
has_table_privilege SELECT: network_app only network_kv; identity_lockout only identity_login_fails
live sessions: kernel_app ×4 (172.18.0.5), network_app ×1 (172.18.0.3); none as superuser/migrator
pg_hba: host all all all scram-sha-256 (local/127.0.0.1 trust inside the container — image default); ssl = off
Vault: no service policy (deploy/local-dev/vault/policies/svc-*.hcl) can read the migrator or superuser password.
```

### Assessment
- **The ARC-3 test as ARCHITECTURE-FLOWS §80 defines it holds live.** ("assert non-Kernel roles cannot SELECT fact
  tables.") No non-kernel role can read registry_version, registry_schema_meta, kernel_kv or the kernel audit tables. No
  service role is superuser, createrole, createdb or bypassrls. No service connects as superuser or migrator. The roles
  with login are kernel_app, network_app and identity_lockout, plus **migrator** and the **superuser**. The last two are
  install-time identities but carry permanent login with SCRAM passwords.
- **Least privilege is not fully met:**
  - `kernel_app` has **UPDATE and DELETE on `kernel_admin_audit` and `kernel_authz_decision`**. The code only INSERTs
    (kernel/api/adminaudit.py:83, kernel/api/app.py:2020). A compromised kernel can rewrite or erase its own decision
    and admin audit trail (FND-12). See R5-3.
  - PUBLIC keeps CONNECT+TEMP on `kernel` and `postgres`. Low.
  - `identity_login_fails` is owned by the superuser rather than migrator. Low; inconsistent with "migrator owns every
    table".
- **Is "ARC-3 HELD" in the matrix honest? No, it overstates the evidence.** The cited cases are:
  - "banned pattern SUPERUSER_DB: no occurrence". This is a static grep that no service connects as superuser.
  - flow-map "fact store reachable only from kernel/network/identity". That is reachability.
  Neither checks a single grant. Change kernel_app to superuser at runtime, or GRANT SELECT ON registry_version TO
  network_app, and the matrix stays HELD. The rule text, "Only the Kernel holds fact-store credentials", is also
  **literally false** today: network and identity hold credentials to the same store. ARCHITECTURE-FLOWS §116 itself
  records that residual as DEBT-B57, now deferred to Layer 2.
  Under the matrix's own derivation rules, a rule with a known recorded violation reads PARTIAL with an XFAIL. That is
  what slice 1g did for NET-3, PTC-1, REG-5 and FND-15. **ARC-3 should be PARTIAL** (an XFAIL for B57), with the grant
  audit as a PASS case.

### Verdict and closing condition
**Blocks L1 exit.** FIX-PLAN Layer 1 "Missing tests" lists "the DB-grant audit … this layer builds them". Net 2
(credential separation) is a Layer-1 net, and its only current proof is reachability. Severity Med: it holds live
today, so the gap is in evidence, not exposure. Owning layer L1.
Smallest closing condition:
- A `verify/db_grants_test.py` (or a conformance mode) runs the catalog queries above and asserts:
  - no non-superuser has super/createrole/createdb/bypassrls/replication;
  - the login set is exactly {kernel_app, network_app, identity_lockout, migrator, <superuser>};
  - per-role table privileges equal a declared map;
  - no role but kernel_app has any privilege on the fact tables;
  - no default ACLs widen future tables.
- It writes ARC-3 cases into the matrix, plus an XFAIL for B57, so ARC-3 reads PARTIAL.
- While there, REVOKE UPDATE,DELETE on the two audit tables from kernel_app and put that in the declared map. Or record
  it as debt against FND-12.

---

## New findings hit along the way

| id | sev | finding & evidence | layer | blocks |
|---|---|---|---|---|
| R5-1 | **Med** | **Join email-verification bypass by default.** `POST /v1/join/request-code` (public) returns the 6-digit code as `dev_code` whenever delivery ≠ "sent" and `JOIN_EMAIL_DEV_ECHO` ≠ "0" (default "1", network/api.py:851). In production, unconfigured SMTP or a transient send failure echoes the code to the requester, who can then prove ownership of any email address. Not refused by the guard and not in the debt register (grep finds no JOIN_EMAIL_DEV_ECHO/dev_code entry). | L4 (network join) + L1 guard | pre-production |
| R5-2 | Med | **The guard is fail-open on its own switch.** `prod-guard.sh` and `gateflags.py guard` exit 0 for any `AIRAWAT_ENV` other than production/prod (unset, "staging", typo). Every shadow flag and convenience then starts. B84 G4 covered "prod" and spaces (now fixed), not this. | L1 | L1 exit (cheap) / pre-prod |
| R5-3 | Med | **Audit tables are mutable by the kernel's runtime role.** kernel_app has UPDATE+DELETE on `kernel_admin_audit` and `kernel_authz_decision`, but the code only INSERTs. FND-12 records can be erased by a compromised kernel. | L1 (grants) / L2 | pre-prod |
| R5-4 | Med | **Fail-open env parses.** `CONNECTOR_PINNED_ENDPOINT_OK` is on for any value ≠ "0" ("" / "false" enable the pinned-endpoint SSRF path, kernel/api/app.py:419). `DEV_REQUIRE_DEVELOPER` is off for any value not in 1/true/yes ("on"/"enforce" disable it). Same class as the B83 bug slice 1g fixed for `*_SHADOW`. | L2 | pre-prod |
| R5-5 | Low | With `IDENTITY_JWKS` unset, kernel `_authenticate` returns None for any bearer, so `Authorization: Bearer x` satisfies `KERNEL_REQUIRE_AUTH`. Per-handler checks still fail closed. | L2 | pre-prod |
| R5-6 | Low | Lock files pin versions but carry **no hashes** (`grep -c hash` = 0 in all three locks), so pip installs without `--require-hashes`. | L1 build | pre-prod |
| R5-7 | Low | The reference services image ships about 850 MB of data-science dependencies (nvidia NCCL 471 MB, xgboost 227 MB, pyarrow 153 MB) that no service imports. That is CVE and attack surface on every service container, and the sole cause of the amd64 smoke failure. | L1 build | pre-prod |
| R5-8 | Low | No CI exists. `verify/ci/reference-pipeline.yml` is an unwired handover artefact and its `checkout-siblings.sh` is missing. Yet the L1 exit gate says "… green in CI", and B94 defers amd64 to "CI". | L1 | L1 exit (as written) |
| R5-9 | Low | Identity falls back to an ephemeral in-process signing key (`key_backend=local-dev`) when VAULT_ADDR/VAULT_TOKEN are absent. That fails open to a working but unmanaged issuer rather than refusing; the guard does not check it. | L3 | pre-prod |
| R5-10 | Info | Kernel `/docs`, `/redoc`, `/openapi.json` and network's equivalents are open to any internal neighbour, including placed components on aos-component, which reach the kernel. They expose the full API map. Kernel `POST /v1/receipts/verify` with `{}` → 500 (unhandled). Postgres ssl=off on the internal net. | L2 | neither |
| R5-11 | Info | PRODUCTION-READINESS §1 blames numpy/scipy/xgboost/osmium for the amd64 segfault. Only pyarrow crashes. IMAGES.lock/B94 imply only the reference image lacks amd64; kernel and network do too. | L1 docs | neither |

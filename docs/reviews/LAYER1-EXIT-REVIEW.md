# Layer 1 — independent exit review

**Date:** 2026-11-08 · **Method:** four fresh reviewers who did not build Layer 1 (REVIEW-METHOD: findings only, no
code changes), each with one scope, run against the live local-dev stack and the source tree, checked against the
FIX-PLAN Layer 1 exit gate (+ §0 nets) and ARCHITECTURE-FLOWS. The single-run `make verify` was run by the
orchestrator after the reviews (it wipes the stack). Debt ids for new findings: DEBT-B83 … B95.

## Verdict: **FAIL** — Layer 1 does not exit yet

The nets run green — **`make verify` passed end to end in one run on a proven-empty slate** (below) — but the
reviewers broke several of the guarantees those nets claim. Ten findings block the exit. Most are narrow, mechanical
fixes; together they are one remediation slice (proposed **1g**, list at the end). Re-review after 1g.

### Single-run `make verify` (2026-11-08T10:20Z, exit 0)
banned patterns 0 failing (self-test 11/11) · GTW + known-violation evidence written · decide() unit 6/6 · **fresh
install: clean slate proven (0 containers/volumes/networks), every volume created by the run, functional proof PASSED**
(onboarding, hold/unhold, in-grant write, FND-19, durable decision records, internal-lookup refusal) · conformance
external 16 PASS / 1 XFAIL, internal 59 PASS / 6 XFAIL, 0 FAIL / XPASS / SKIP_CREDS · flow-map PASS · Vault scope PASS ·
routes: 439 declared, 0 undeclared, 335/335 non-public refused, 8 on review (DEBT-A1, Layer 2) · scans 0 new.
**Caveat:** several of these nets have blind spots (N1–N4, W2) — green is necessary, not sufficient.

## Findings

Severity · evidence (abridged from the reviewers' command transcripts) · rule · owning layer · blocks the exit.

### 1. Walls (networks)
| id | sev | finding & evidence | rule | layer | blocks |
|---|---|---|---|---|---|
| W1 | **High** | **No network denies outbound traffic.** Every aos-* network `Internal=false`; every container — incl. nginx and the `aos-component` network for placed components — connects to `1.1.1.1:443`, `8.8.8.8:53` and `host.docker.internal`. §0 net 1 requires deny-by-default egress. **DEBT-B87** | ARC-1, §0.1 | L1 | **yes** |
| W2 | Med | **The flow-map test assumes share-a-network ⇔ reachable — false.** `notify` (aos-svc only) reaches nginx's aos-edge IP `172.24.0.4:80` (200 /healthz) and the legacy stack's nginx; the test probes neither IPs, the host nor egress, and enumerates a hard-coded map (W7). **DEBT-B87** | ARC-1/5 | L1 | yes (the "proven by flow-map" claim) |
| W3 | Med | **Legacy `deploy/local` stack live on 0.0.0.0:80 with its kernel door open** — `/kernel/v1/health` → 200 from the LAN and from every local-dev container (DEBT-A61). Stray host processes `identity.py :8093` and `secrets.py :8102` are reachable via host.docker.internal (W6). **DEBT-B95** | ARC-5 | L1 | **yes** (until stopped or formally deferred) |
| W4 | Med | **B57 contradiction:** the exit gate says "B57 closed"; ARCHITECTURE-FLOWS §d defers it to Layer 2. Live reach is correct (only kernel/network/identity → 5432; per-role grants verified). | ARC-3 | L1/L2 | yes (record the decision) |
| W5 | Low | The service mesh is full (ARC-4 PLANNED) but the test prints ✓ for that SKIP. | ARC-4 | later | no |
| W8 | Info | Containers run as uid 0 (Vault excepted); Vault plain HTTP; 8201 reachable on aos-data-secrets. | — | prod | no |

**Sound:** container × network membership matches the compose and the map; nginx reaches no service or store by
name or IP (0/41); only `127.0.0.1:8080` is published; edge routes `/` and `/network/` only, `/kernel/` 404 (incl.
`%2F`, `%6b`, `..` variants); Postgres reachable only from kernel/network/identity; Vault not reachable from
notify/filestore/nginx; no docker.sock mounts, no privileged containers.

### 2. Keys (Vault)
| id | sev | finding & evidence | rule | layer | blocks |
|---|---|---|---|---|---|
| K1 | **High** | **Shared `transit/*`:** svc-kernel / svc-network / svc-identity all grant `transit/*` c/r/u. Live `sys/capabilities-self`: the kernel can `transit/sign/airawat-identity` (forge identity tokens) and rotate/config `airawat-authority`; network and identity likewise. §g records them as not widened; the vault-scope test never checks transit. **DEBT-B88** | ARC-7, FND-9/10 | L1 | **yes** |
| K2 | **High** | **model-gateway and the secrets broker read/write every platform credential** — the `secret/data/+/+/*` narrowing covers all 3-segment platform paths (kernel-app DB password, migrator, provisioner, scheduler/launcher/kernel, trust-writer, audit HMAC; secrets also delete). The vault-scope test uses the kernel DB password as model-gateway's "own path shape" and passes. **DEBT-B89** | ARC-7 | L1 | **yes** |
| K3 | Med | app-host reads every operator principal's password (`secret/data/<op>/*`) and so can act as the scheduler (the only run-token reader). **DEBT-B89** | ARC-7/FND-10 | L1 | yes (narrowing is mechanical) |
| K4 | Med | AppRole secret-ids are permanent (ttl 0, unlimited uses, no CIDR), in every container's `Config.Env` and in 0644 host files; installer re-runs accumulate them (V3). **DEBT-B91** | ARC-7 | L1/prod | no (prod gate, RELEASE-PLAN §2c) |
| K5 | Low | `init.json` holds the root token and the only unseal key; auto-unseal reads it. **DEBT-B91** | ADR-0131 | prod | no |
| K6 | Low | The scrubbed admin bootstrap password is still in `conformance/.creds.json` (dev fixture, 0644) and still valid (must_reset pending). **DEBT-B91** | ADR-0131 c4 | L1 (dev) | no |
| K8 | Low | §g drift vs the policy files (identity admin/provisioner grant, kernel own path, decision/workflow policies exist, network metadata list). | — | L1 docs | no |

**Sound:** 12 AppRoles, each mapped to its own policy; no root token in any service (checked by value); no service
can touch `sys/policies` or AppRole secret-id paths; the admin bootstrap password is absent from Vault (no versions)
and the install-state marker is present; the provisioner credential is retained; identity stores pbkdf2 hashes only.

### 3. Gates
| id | sev | finding & evidence | rule | layer | blocks |
|---|---|---|---|---|---|
| G1 | **High** | **Production-guard bypass:** the guard's `_truthy` accepts 1/true/yes/on; `svc_gate._truthy` treats anything but ''/0/false/no/off as true. Live (filestore under the guard, `AIRAWAT_ENV=production`, `FILESTORE_SHADOW=2`/`enabled`/`y`): guard "no dev conveniences — proceeding", gate "SHADOW". Same for every svc_gate door. No automated guard test (G5). **DEBT-B83** | FND-16, FND-8 | L1 | **yes** |
| G2 | Med | The guard knows flag NAMES only: IDENTITY_PASSWORD_REQUIRED (default **shadow**), KERNEL_REQUIRE_AUTH, PROV/DATAPLANE_ENFORCE, KERNEL_REQUIRE_STEWARD_GRANT, PLATFORM_AUTHORITY_MODE, NETWORK_ADMIN_AUTHZ, TRUST_ENFORCE_STEWARD_PROVENANCE, SUBSCRIPTION_ENFORCE and unset IDENTITY_EXPECTED_AUD/ISS all start under production. **DEBT-B84** | FND-16 | L1 guard; flags L2/L3/L4/L6 | no (owners recorded) |
| G3 | Med | The guard refuses `AIRAWAT_ALLOW_PASSWORDLESS`, which nothing reads; app-host still makes passwordless `/login` calls that work only while IDENTITY_PASSWORD_REQUIRED ≠ enforce. **DEBT-B84** | FND-9 | L3 (B14/A30) | no |
| G4 | Med | "Production" means `AIRAWAT_ENV == production` exactly (`prod` or a leading space slips through; `AIRAWAT_PROFILE=dev` is unchecked); the installer's root-token one-offs are refused by the guard under production, so the production install path has never run. **DEBT-B84** | FND-16 | L1 | no (residual) |
| G6 | Info | Doc drift: svc_authz docstring, §h `*_SHADOW` text, launcher docstring. | — | L1 docs | no |

**Sound:** every svc_gate door enforces when its env is unset; identity, secrets, runtime-manager, Network lookups,
attest and run-token always enforce; live `[gate]` lines show ENFORCE; the guard refuses every known `*_SHADOW`
(1/true/yes/on), IDENTITY_AUD_ISS_SHADOW, AIRAWAT_INPROCESS_COMPONENTS, a static VAULT_TOKEN, IDENTITY_SEED_DEMO,
AIRAWAT_EPHEMERAL_OK and SCHEMA_VALIDATE=shadow.

### 4. Badges (service identity)
| id | sev | finding & evidence | rule | layer | blocks |
|---|---|---|---|---|---|
| B1 | **High** | **automation `/events` admits any principal's platform-audience token** (no allow-list; every principal can mint the platform audience). Live: svcprobe/app-host/decision admitted, anonymous 401. Declared callers: {event-relay}. **DEBT-B85** | FND-9, §0.3 | L1 | **yes** |
| B2 | **High** | **The Network lookup allow-list is wider than §h**, and the same set gets the unscoped list mode. Live: decision's svc:network token → 200 on `/v1/join` (applicant contact emails), `/v1/credentials`, `/v1/tenants`; automation (a declared list caller) is missing. **DEBT-B86** | FND-8/10 | L1 | **yes** |
| B3 | Low | Allow-lists match the bare principal name; realm is unchecked at most svc_authz doors and at `/v1/runtime/attest`; the Network realm check is skipped if its env is unset. Mitigated by identity's recorded per-principal audiences. **DEBT-B86** | FND-9 | L1/L3 | no |
| B4 | Info | **No shared-literal internal gate remains in current code** (only comments, tests and the banned-pattern rule; LEGACY stacks annotated; the SMS gateway secret is Vault-held, B64). | — | — | — |
| B5 | Low | Identity re-seeds if its users file is corrupt (a rotated admin password was reset in a throwaway test); mitigated in local-dev because the bootstrap password is scrubbed. | ADR-0131 | L3 | no |
| B6 | Low | Installer re-runs reset trust-reader/trust-writer roles and passwords (no `only_if_unset`). | — | L1 installer | no |
| B7 | Info | The kernel run-token gate reads `roles` from token claims (DEBT-B1). | FND-2 | L2 | no |

**Sound:** 11 doors live-tested — anonymous 401/403, wrong audience 403, undeclared principal (svcprobe) 403 at
runtime-manager, identity, Network lookups and attest, declared callers admitted; recorded audiences at login match
§h exactly and undeclared audiences are refused; ADR-0131 bootstrap: production minimum (admin@operator +
provisioner), create-only (a second seed reports exists, password and roles unchanged), production asserts present.

### 5. Nets
| id | sev | finding & evidence | rule | layer | blocks |
|---|---|---|---|---|---|
| N2 | **High** | **TOKEN_ROLES misses the dominant idiom** `(claims or {}).get("roles")` — about 52 uncounted reads (governance/marketplace/studio routes, kernelcore, workflow, app_host); the "41" baseline is an undercount with false positives. New token-role reads in this form pass silently. **DEBT-B92** | FND-1/2, §0.6 | L1 | **yes** |
| N3 | Med | The hard secret checks are evaded by os.getenv, `or "lit"`, compose list form, shell export, Dockerfile ENV and DSN credentials. **Two real misses:** `tools/republish_portal.py:18` (`or "Airawat@123"`), `demo_identity.sh:5` (`airawat-dev-root`). §0.6's "direct internal URL that skips a door" check is absent. **DEBT-B92** | FND-9/16 | L1 | no (dev/demo hits; fix with N2) |
| N1 | Med | The route extractor misses helper-dispatched routes (filestore `GET/HEAD /files/*` — live 403, undeclared), `do_OPTIONS` and FastAPI `/docs/oauth2-redirect`; its docstring overstates what it follows. **DEBT-B92** | FND-8, §0.4 | L1 | no (the missed routes refuse) |
| N4 | Med | The secret scan fails OPEN: a failed gitleaks run writes no report and is counted as zero findings. **DEBT-B92** | FND-9 | L1 | no (fix before CI) |
| N5 | **High** | **Secrets-broker path traversal:** kernel `/v1/fetch` forwards `inject.name` unvalidated; `secrets.py _path` quotes the component, not the name; Vault normalises `…/comp/../../localdev-operator/admin/password` (307, X-Vault-Token kept by urllib); svc-secrets policy is `secret/data/*`. A component can inject any secret (e.g. the kernel's DB password) into its own declared egress. Not exploited end to end (that would exfiltrate a real secret); the Vault redirect was observed live. **DEBT-B90** | ARC-7, FND-10 | L1 (rule) / L6 (code) | **yes** |
| N6 | Low | The harness proves fresh VOLUMES, not fresh images (mutable local tags); an `AOS_LD_PROJECT` override vs the hard-coded `P` in install.sh could make the volume check vacuous; `.env` carries over. | §0.7 | L1 | no |
| N7–N8 | Info | TOKEN_ROLES baseline entries carry one global note, not per-entry debt ids; gitleaks baseline fine; the trivy baseline is exactly the compose images, nothing untriaged; runtime images (`components/runtimes/*`) are not scanned. | §0.8 | L1 | no |
| N9 | Info | nginx `/network/` proxies the whole Network API, so the 13 internal lookups are edge-reachable (token-gated, 401). | ARC-5 | L4 | no |

### 6. Matrix honesty
| id | sev | finding | layer | blocks |
|---|---|---|---|---|
| M1/M2 | **High** | FND-6, REG-13 (kernel `_NAT_KEYS` domain vocabulary, DEBT-B8) and PLT-4 (authority by the tenant NAME `airawat`) read HELD from narrow PASS cases. **Fixed in this review:** `verify/known_violations.py` (now in `make verify`) adds XFAIL evidence for them and for ARC-7 (K1/K2/N5) and ARC-1 (W1); all five now read **PARTIAL**. **DEBT-B93** | L1 (matrix net) | resolved for these five |
| M3 | Med | Still HELD on narrow cases while their spec status is PARTIAL: **NET-3, PTC-1, REG-5, FND-15**. **DEBT-B93** | L2/L4 (rules) | **yes** (matrix integrity) |
| M4 | Med | ARC-3 is HELD and holds live (the reviewer ran the DB-grant audit: network_app → network_kv only, identity_lockout → identity_login_fails only, fact tables → kernel_app only), but no case proves it; the ARCHITECTURE-FLOWS ARC prose is stale (ARC-7 cites B58; ARC-2 VIOLATED vs NO TEST). | L1 | no |

**Live break attempts on five HELD rules (non-destructive) — all held:** ARC-5 (edge `/kernel` variants all 404;
only 127.0.0.1:8080 published), ARC-7 (notify cannot resolve vault/postgres; the kernel holds an AppRole only),
PTC-1 (anonymous participant registration 401), NET-3 (anonymous governance role writes 401), PLT-5 (anonymous
`platform.authority` grant 401). HELD after this review: FND-15, FND-19, REG-5, NET-3, PLT-5, PTC-1, ARC-3, ARC-5 —
four of them over-claims (M3).

### 7. Layer-1-owned items still open
| item | status | blocks |
|---|---|---|
| W1, K1, K2, G1, B1, B2, N2, N5 (above) | open | **yes** |
| DEBT-A61 / B95 — legacy stack on 0.0.0.0 with `/kernel/` | open, running | **yes**, unless stopped or formally deferred |
| B57 vs the exit-gate wording (W4) | contradiction | yes — record the decision (defer to L2 with reason, or close) |
| M3 over-claims | open | yes — the exit gate reads "owned rows HELD"; a HELD row must be proven |
| ARC-2, ARC-4, ARC-6 NO TEST/PLANNED; FND-16 PLANNED; FND-8 PARTIAL | open | not blocking **if** written deferrals are recorded (ARC-2 → L2, ARC-4 → later, FND-8 remainder → A1 in L2) |
| G2–G4, K3–K6, N1, N3, N4, N6, B3, B5, B6 | open | no |
| Legacy-stack literals (SECRETS_INTERNAL etc.), annotated LEGACY | open | no (retire with the legacy stacks) |

## 8. Assessments requested

### (a) Reproducibility — can every image be rebuilt from the repositories? (B80)
**Yes — proven by rebuild**, contrary to the B80 note. The reference base is `platform-spec/deploy/ec2/
Dockerfile.reference` (its layers match `dev-hard16`'s first 7 RootFS layers, incl. the 1.28 GB pip layer); a
`--no-cache` rebuild through `reference/Dockerfile.local-deliver` and `Dockerfile.reference-patched` produced an
image with the identical source hash, docker CLI, cryptography and psycopg2 (only `pyarrow` differs, 26.0.1 vs
26.0.0 — unpinned). Kernel and network rebuild from their Dockerfiles and match on the app-source hash. **But** no
single file builds a shippable amd64 reference image (the patched file defaults to a local dev tag; the ec2 file
alone lacks psycopg2 and pins cryptography 43.0.3 and an x86_64 docker CLI), dependencies are unpinned and the base
is tag-pinned (R2/R3), and the root `.dockerignore` sends `.env`, the approle env files and `.creds.json` to the build
daemon (R4). **DEBT-B94.**
**Recommendation: make it an exit condition.** The CVE cadence, the scan gate (§0 net 8) and image provenance
(RELEASE-PLAN digest pins + OCI source labels, ADR-0052) all need a rerunnable build. It is nearly met: one
`platform-spec/Dockerfile.reference` from a digest-pinned `python:3.11-slim`, locked dependencies, OCI labels and a
fixed `.dockerignore` (about an hour), plus the CI build-and-scan job.

### (b) DEBT-B82 — authority check hardcoded to tenant `airawat`
**Confirmed, and broader than recorded:** 21 routes in `network/api.py` (trusted-issuers ×3, join/decide, schemas,
interfaces ×4, schema/pack/role-request decide, domains, roles, packs, tenants, tenants/rehost, offering steward,
jurisdictions, store publish-request decide, store revoke) plus `_is_operator`, `JOIN_EMAIL_TENANT` and trust-module
defaults. **Live:** 4 accounts (admin@localdev-network network.admin, opadmin platform.admin, platnone, outsider) × 8
routes → 32/32 `403 not a tenant admin for airawat`; even with the right tenant name the role set
(tenant-admin/steward) excludes network.admin. It is also a token-claims gate (banned by §0.5) and an
escalation-by-NAME risk (a provisioned `admin@airawat` with `platform.tenant-admin` would pass — from a code read,
not exercised). **Owning layer: Layer 4 (confirmed). Not an L1 exit blocker. It MUST precede any non-dev install:**
on any install whose authority tenant is not literally `airawat`, join approval, tenant registration, governance
decisions and store revocation are dead through the API, so the network cannot be operated or respond to an
incident. Fix it through the recorded `platform.authority` / decision function (B1), not an env literal.

### (c) Vault 2.x — restore and rotation
Drilled on a throwaway Vault 2.2.1 (same digest, the repo's entrypoint and vault.hcl, policy/AppRole/KV/transit seeded
as the installer does). **Works:** backup → wipe → restore → `UNSEALED`, with data, the old AppRole login and transit
intact; AppRole secret-id rotation (old 400, new OK); per-role token revocation; root rotation via `generate-root`
(new token `[root]`, old 403, a restart unseals with the new root); transit rotate. **The runbook was wrong and is
now corrected** (`docs/operator/RESTORE-AND-ROTATION.md`, `OPERATOR-GUIDE.md` restore steps):
- **V2 (High):** the DB-role rotation wrote `secret/localdev/kernel-app` — a path the service cannot read, so it would
  keep the OLD password and fail after `ALTER ROLE`. Now `vault kv put -mount=secret localdev/<name>/password`, a
  role↔path map, and `_split_roles.py` with the root token and `POSTGRES_PASSWORD` passed in.
- **V1:** a restore must start Vault as root (`user: "0:0"`) so the entrypoint re-chowns to uid 100 — documented.
- **V3:** destroying a secret-id does not revoke tokens already issued — a revocation loop is added; secret-id
  accumulation is noted (B91).
- **V5:** `deploy/local-dev/.env` is added to the backup set; init.json holds root + unseal key, so a backup is a
  secret; raft snapshot does not apply to file storage.
- **V6:** the OPERATOR-GUIDE restore step 1 had failed since L1-1b (the network container has neither root nor the
  superuser password) and step 2 referred to a `.env` Vault token — both rewritten.
- Residual: the entrypoint decides "uninitialised" by grepping `vault status` text; an unreadable store made it
  attempt `operator init` (failed safely). It should use the exit code (DEBT-B91 follow-up).

## Remediation slice 1g — conditions to PASS on re-review
1. **W1** `internal: true` on every non-edge network (egress only via declared proxies) and **W2/W7** a flow-map net
   that probes egress, the host and cross-network IPs and enumerates the project (B87).
2. **K1** per-service transit key paths; **K2/K3** platform credentials out of the brokers' reach, app-host narrowed;
   the vault-scope net checks transit and platform paths (B88, B89).
3. **N5** reject `/`, `..` and percent-escapes in secret names at kernel `/v1/fetch` and in `secrets.py`; quote (B90).
4. **G1** one truthiness; gates refuse shadow under production themselves; a net that exercises the guard (B83).
5. **B1** automation accepts `svc:automation` from {event-relay} only (B85); **B2** per-route Network caller sets,
   list "service" mode only for declared list callers, realm checked everywhere (B86).
6. **N2** TOKEN_ROLES catches `(x or {}).get("roles")` and attribute/indirect forms, re-baselined with per-entry
   debt ids; adversarial self-tests for every check; fix the two N3 literals (B92).
7. **B95/A61** stop the legacy stack (or bind 127.0.0.1 and drop `/kernel/`); stop the stray host processes.
8. **M3** prove or demote NET-3, PTC-1, REG-5, FND-15 (XFAIL evidence for their recorded debts); add the ARC-3 DB-grant
   audit as a case (B93).
9. **W4** record the B57 decision; record written deferrals for ARC-2/4/6, FND-16 and the FND-8 remainder.
10. **8a** one reproducible `platform-spec/Dockerfile.reference` and the `.dockerignore` fix (B94) — recommended as an
    exit condition.

Not exit conditions, but they must precede any non-dev install: **DEBT-B82** (L4), the production posture (B84), KMS
unseal and single-use secret-ids (B91), the amd64 reference build (B94).

*Review artefacts:* the reviewers' transcripts live with this session; the reviewer for nets left a throwaway citizen
user (`evil@citizens`, role civic.resident) on the shared stack — removed by the review's own fresh install.

# AirawatOS operator guide (cloud-neutral)

How to stand up, upgrade and run a production AirawatOS host safely. Consolidated from `deploy/RELEASE-PLAN.md`,
`deploy/PRODUCTION-READINESS.md`, `docs/OPERATING-RULES.md`, the incident notes
(`docs/incident-2026-11-03-ec2-exposure-hardening.md`; memory: EC2 disk-full, no-host-iptables) and
`docs/specs/PLATFORM-v0.1.md` **P1–P3**. Cloud-neutral; provider specifics live in `AWS-APPENDIX.md`.

The **operator** runs the host and infrastructure and holds **no governance role** (PLATFORM P3). Platform
authority is a recorded role held by people, never by the operator or the host.

---

## 1. Prerequisites (before first install)

All six must hold before a production install. What can be checked automatically vs by hand is in §7.

1. **Encrypted storage with a customer-managed key.** Every data disk, every snapshot, and every off-host
   backup is encrypted at rest with a **customer-managed KMS/HSM key** (not a provider-default key you don't
   control) — so key access can be revoked and crypto-shredding is possible (REGISTRY R14/R17). Covers the
   volumes behind Postgres, the filestore (`/data/filestore`), Vault, and the identity data.
2. **Perimeter: only 80/443 public, SSH from admin addresses only.** The network perimeter (security
   group / cloud firewall — **not** a host firewall, see §5) allows **80 and 443 from the public**, **22
   (SSH) only from named admin CIDRs**, and **nothing else inbound**. All service ports (kernel 8080, network
   8090, identity 8093, Vault 8200, Postgres 5432, …) bind to **127.0.0.1** and are never exposed.
3. **Vault unlocked via instance identity, never a root token.** Vault auto-unseals via a managed key, or the
   host obtains a short-lived token through its **instance identity** (cloud IAM → Vault auth). **No
   long-lived root token** sits in compose, env, or on disk. Services read only their own secret paths
   (`secret/data/<tenant>/<principal>/password`) under a scoped policy. Mint helpers **fail closed** — no
   token means no token minted, never a bypass. The unseal path must survive a host reboot.
4. **Dedicated host — no unrelated projects.** The production host runs **only** this platform's stack. No
   other projects, no personal workloads, no stray containers/images (buildx scratch, `vms-fixture`,
   `demo-connector`, `dev-*` tags). One host, one purpose — so blast radius and the perimeter stay knowable.
5. **Native amd64 build pipeline.** Images are built on a **native amd64 builder** (CI or an amd64 host),
   never cross-emulated (the reference image segfaults under QEMU). Images are pushed **by digest** and pinned
   by digest in the prod compose.
6. **A separate rehearsal environment.** A throwaway, production-shaped **amd64** host exists (or can be
   created on demand) to rehearse upgrades against a restored backup before touching production (§3).

---

## 2. Installation

Minimal, idempotent, operator-first (PLATFORM P1–P3, ADR-0115/0122).

1. **Pre-flight.** Confirm §1 prerequisites (and the `deploy/PRODUCTION-READINESS.md` checklist: iss/aud
   envelope set, prod-guard shipped, trust-reader/writer + audit HMAC provisioned).
2. **Run the installer** (`ensure_install` + base-OS seed). It creates **only** the minimum (PLATFORM P1):
   Vault keys; the durable store (fail-loud if absent); base schemas; **exactly one platform tenant**;
   **service identities with recorded service roles** (scheduler, component-publisher, dev-sandbox,
   embed-service — each a random Vault-backed password, generated not literal, never reset on re-run); and the
   certified platform apps. No other tenants/Networks/memberships/grants. Re-runs are idempotent.
3. **One-time installer credential → first `platform.authority`** (PLATFORM P2). Seed the first
   `platform.authority` holder via the one-time installer credential, then **let that credential expire**. It
   exists only to create the first holder.
4. **Add a second `platform.authority` holder promptly** (PLATFORM P2 / P5, separation of duties). Never
   operate with a single holder: granting authority requires a ChangeRequest approved by a **different**
   holder, and the **last holder cannot be removed** — both need ≥2 holders. Do this immediately after step 3.
5. **Register break-glass custodians** (PLATFORM P5a). Establish a recovery key **split among named
   custodians**, **quorum required** to use, scoped so it can **only restore a `platform.authority` holder**,
   and whose every use is **publicly and permanently recorded**. (Design pending in ADR-0122; record the
   custodian roster and procedure now even where the mechanism is manual.)
6. **Verify.** Site 200 over 443; a known record resolves; a human login succeeds; the filestore serves a
   known blob; daemons authenticate with their Vault-backed tokens.
7. **First admin rotates; the bootstrap password is then gone (ADR-0131).** The installer writes the first
   administrator's initial password to Vault, confirms identity bootstrapped it, and at the end of the install
   (Phase 14) **deletes it from Vault — all versions**. The admin's first login carries `must_reset` and the
   admin sets their own password. Record that password in your secrets custody; nothing else holds it.
8. **Re-installing after the bootstrap (same volumes).** A re-run of the installer over an existing install
   finds the scrub marker (`secret/<op>/install-state`) and **refuses to proceed unless
   `OPERATOR_PASSWORD` is set to the CURRENT admin password** — the password the admin set at first login (or,
   if they have not logged in yet, the bootstrap password from the original install output). It is used in the
   installer shell only and never written back to Vault:
   ```sh
   OPERATOR_PASSWORD='<current admin password>' deploy/installer/install.sh --profile <dev|production>
   ```
   Without it the installer stops with an explicit error rather than minting a new bootstrap password that
   could never log in (identity seeds create-only and never resets an existing admin). On a **fresh** install on
   empty volumes, **production requires `OPERATOR_PASSWORD`** (the initial admin password you choose). The
   installer refuses to generate one in production: a generated password is never printed and is scrubbed at the
   end, so nobody could ever use it. Dev/rehearsal may omit it (generated, and captured in the gitignored
   conformance fixture).
9. **Functional proof (dev profile).** The installer's last phase (Phase 15) onboards a throwaway user through
   the App Host and has an installed fixture component write a record within its grant (refused outside it);
   the install fails if either does not work. Production carries no fixtures — run the §2.6 checks by hand.

---

## 3. Upgrade procedure

One ordered pipeline; do not skip stages. Full detail in `deploy/RELEASE-PLAN.md` (Stages 0/0b/1, §4, §5).

1. **Backup** — logical DB dump (per database) off-host + checksummed, **and** storage snapshots of every data
   volume, taken with the stack quiesced or crash-consistent + the logical dump.
2. **Restore drill** — restore the dump + snapshots into a fresh environment and confirm it comes up (site,
   record resolve, login, blob). **A backup that has not been restored does not count.** Record RTO/RPO.
3. **Rehearsal** — on the separate amd64 copy (§1.6) seeded from the restored backup, build the images and run
   **every upgrade step and every rollback** against production-shaped data; the conformance suite must be
   green at each enforce step. Fix any data surprise (e.g. an account with no password) on prod **before** the
   real run.
4. **Shadow** — deploy the new images with enforcement flags **off/shadow**; confirm no regression and that
   the shadow logs show what enforcement *would* do, with no false denials for real principals.
5. **One enforce flip per change window** — flip exactly one enforcement flag per window, each with a **soak**
   and explicit **go/no-go** (never batch two). Order and criteria are in RELEASE-PLAN §5
   (authority → steward-provenance → automation-token → passwordless **last**). If a go-criterion is not met,
   roll that flip back and re-diagnose.

Build off-box, deploy by digest (§5 standing rules). Rollback at each step = redeploy the previous pinned
digest and revert the flag (RELEASE-PLAN §7); the fastest lock-out unlock is reverting the passwordless flag
to shadow.

---

## 4. Routine operations

- **Scheduled restore drills.** On a fixed cadence (e.g. monthly), restore the latest backup into the
  rehearsal environment and confirm it comes up. Record the date + result. Backups are only as good as the
  last successful restore.
- **Restore runbook (after restoring data volumes).** When you restore the Postgres / Vault / filestore /
  identity volumes from backup, two things drift from the restored state: the **DB-role passwords** in
  Postgres, and the **Vault token** each already-running container holds. Before using the stack:
  1. **Re-sync every DB-role password from Vault** via the single idempotent installer step — it converges
     `migrator` / `kernel_app` / `network_app` **and** `identity_lockout` from Vault (no manual password
     handling; the secret never leaves the container):

     ```
     PGPW=$(sed -n 's/^POSTGRES_PASSWORD=//p' deploy/local-dev/.env | tail -1)
     docker compose exec -T -e VAULT_TOKEN="$VT" network env INSTANCE=localdev DB_HOST=postgres POSTGRES_PASSWORD="$PGPW" \
         python3 - < deploy/installer/_split_roles.py
     ```
     (`$VT` = the install-time root from `/vault/data/init.json`; see RESTORE-AND-ROTATION.md. The network container
     holds neither the root token nor the superuser password since L1-1b / slice-1d, so both are passed in.)
  2. **Recreate — don't just `restart` — every service** so it picks up its AppRole credentials from
     `deploy/local-dev/vault/approle/<svc>.env` and logs in afresh (prod-guard):
     `docker compose up -d`. A bare `docker restart` keeps the container's original environment, so a service
     can come back holding a **stale Vault token** (symptom: `403 Forbidden` reading its Vault path → the
     service fails open to an empty DB password → `password authentication failed`). This is distinct from the
     DB-password drift in (1); a restore needs **both** fixes.
  3. **Verify each service's health before use** — not just that containers are "up": `/healthz` on
     kernel / network / identity (identity must report `lockout_store: "durable(postgres)"`, **not**
     `memory(degraded)`), plus a login, a record resolve, and a blob read. A restore that has not passed these
     checks does not count (same rule as the restore drill).
- **Monitor the identity lockout store (PLANNED monitoring item).** Identity exposes two signals when its
  durable brute-force-lockout store (Postgres `identity_login_fails`, ADR-0121) is unreachable: an **ALERT**
  log line (`[identity][ALERT] lockout-store ... mode=memory(degraded)`) and `lockout_store: "memory(degraded)"`
  on `/healthz`. While degraded, lockout counters are per-replica and in-memory (lost on restart, not shared
  across replicas) — brute-force protection is weakened, silently. Something must **watch both signals and
  alert** (scrape `/healthz` for `memory(degraded)`; match the ALERT line in the log pipeline). Not yet wired
  into a monitoring stack — tracked here as a monitoring item.
- **Key + run-token rotation.** Rotate on a schedule and on personnel change: Vault transit keys (signing
  `airawat-authority`/`airawat-identity`; and the `rec-*`/`idx-*` data keys once R17 ships) via key-version
  bump + rewrap; service-principal passwords in Vault; run-tokens are already short-lived/high-entropy —
  confirm their TTL and that none are long-lived. Rotation is audited.
- **Log rotation + disk monitoring.** Enforce container/host **log rotation** and alert on disk usage with
  headroom. (Incident: the root disk hit 100% → Postgres went unhealthy; Docker volumes + IDE caches were the
  culprits.) Keep a safe-reclaim runbook; grow the data volume before it fills.
- **Periodic perimeter review.** On a fixed cadence, re-verify the perimeter: only 80/443 public, SSH from the
  current admin CIDRs only (prune stale addresses), every service port still bound to 127.0.0.1, and no new
  inbound rule has crept in.
- **Registry audit-chain verification (scheduled integrity check).** On a fixed cadence (e.g. nightly or
  weekly), run the Kernel's read-only audit verifier to confirm no stored registry row was altered in place:

  ```
  docker exec <kernel-container> python3 /app/tools/audit_verify.py            # whole table
  docker exec <kernel-container> python3 /app/tools/audit_verify.py --from <seq> --to <seq>   # a range
  ```

  It recomputes each `registry_version` row's `content_hash` with the kernel's own hash and reports the FIRST
  row whose stored bytes no longer match (the strongest check the current layout supports; rows are
  content-hashed, not per-row signed). **Exit 0** = all rows verified; **exit 2** = a hash break (investigate
  that `seq`/`id` immediately — a row's JSON changed after write); **exit 3** = a present signature failed
  verification. It is **read-only** (a read-only transaction; SELECTs only), so it is safe to run against
  production and against a restored backup. Throughput is ~40k rows/s (~250 ms per 10k) on local-dev; for a
  very large table, schedule it over seq ranges or during a quiet window, and alert on any non-zero exit. See
  `../performance/PERFORMANCE-BUDGETS.md` for the budget (≤ 800 ms / 10k) and the measured number.

  **PLANNED — publish the audit-chain head externally (tamper-evidence an operator cannot rewrite).** Content
  hashes detect a row altered in place, but an operator with DB access could in principle recompute and rewrite
  both the row and its hash. To close that gap, periodically publish the audit *head* — the current max `seq`
  plus a digest over the ordered `content_hash` values up to it (and, once a signing key is provisioned, a
  signature over that digest) — to a location the operator **cannot alter after the fact**: a write-once/
  append-only store (e.g. object storage with object-lock/WORM, or an external notary/transparency log). A
  later verification re-derives the digest from the registry and checks it against the externally pinned head,
  so any retroactive rewrite is detectable even against a fully-privileged local operator. Not yet built;
  tracked here as the next hardening step for the audit chain. (Design note: the head digest is cheap — it
  reuses the same per-row `content_hash` the verifier already computes.)

---

### 4.1 Governing schemas and calling the Network from operator scripts (slice-1d / slice-1f)

**What changed.** The Network no longer signs anything for an anonymous caller, and its internal doors are internal:

| Call | Now requires | Since |
|---|---|---|
| `POST /v1/schemas` (direct, authority-signed schema) | a bearer for an **admin of the network authority** | slice-1d (DEBT-B73) |
| `POST /v1/solutions` | the **publisher** of the solution id (its steward, or `component.publisher` on-behalf-of) | slice-1d |
| `POST /v1/tenants/rehost` | an admin of the network authority | slice-1d |
| the 13 internal lookups (`tenants/resolve`, `directory/resolve`, `grants/resolve`, `schemas/resolve`, `store/resolve`, `certificates/resolve`, `keys/resolve`, …) | an `svc:network` **service** token from a declared platform service — **not callable by operator scripts** | slice-1f |
| lists with personal / institutional data (`join`, `credentials`, `tenants`, `participants`, request queues, …) | any bearer; rows are scoped to the caller's tenant, full lists to authority admins | slice-1f |

An anonymous call now gets **401**; a wrong caller **403**.

**The governed path for a schema (use this, not a direct publish):**
1. Get a bearer: `TOKEN=$(curl -s -XPOST $IDENTITY/realms/<tenant>/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"…"}' | jq -r .access_token)`.
2. **Propose:** `POST /v1/schema-requests` `{schema_id, version, definition, sensitivity}` with the proposer's bearer
   (a developer / publisher of the tenant that will own it).
3. **Decide:** `POST /v1/schema-requests/decide` `{schema_id, version, decision: "approve"}` with an
   **authority-admin** bearer. The Network lints the definition, signs it, and publishes it. The approval is
   recorded (`decided_by`).
4. **Read** it back from the public catalogue `GET /v1/schemas` (not `schemas/resolve`, which is internal now).

**Known limitation:** the authority-admin gate (and therefore steps 3 above and the direct publish) is bound to
the hardcoded authority tenant `airawat` (`network/api.py` `AUTHORITY_TENANT`). On an installation whose authority
tenant has another name (e.g. local-dev's `localdev-network`) no bearer satisfies it, so schemas are governed
**in-process at install** (`seed_base`, Trust-plane schema seeding). That is a production-pointing default
(FND-16), tracked in FIX-PLAN Layer 4.

**Scripts that must change** (they post or read without a token, or read an internal lookup):

| Script | What it does today | Change |
|---|---|---|
| `platform-spec/reference/govern_fsnode.py`, `platform-spec/reference/seeds/govern_verb_binding_schema.py` | anonymous `POST /v1/schemas` | governed path above, or run in-process at install |
| `platform-spec/deploy/ec2/govern_metering.py`, `vision_govern.py`, `vms_govern.py` | `schema-requests` + `decide`, list `GET /v1/schemas` | pass the proposer / authority-admin bearers (steps 2–3) |
| `platform-spec/deploy/ec2/recert.py` | `certificates/resolve` (internal) | read certificates through `GET /v1/store` / the certify response, or run inside the Network container |
| `platform-spec/reference/tools/wire_subscriptions.py` | `GET /v1/interfaces/bindings` (internal) | run as a platform service or inside the Network container |
| `components/tools/govern_*.py`, `seed_archetype_presence.py`, `components/solutions/*/govern_*.py`, `fix_works_payment.py`, `basic-apps/register.py`, `components/demos/worker-career-passport/run.py` | direct `POST /v1/schemas` / `/v1/solutions`, `schemas/resolve` | governed path with bearers; read via `GET /v1/schemas`; register solutions with the publisher's bearer |
| `network/demo_portability.py` | `tenants/rehost`, `tenants/resolve`, `directory/resolve` (demo) | demo only — needs an authority-admin bearer and in-container execution |

## 5. Standing rules (always)

From `docs/OPERATING-RULES.md` and the 2026-11-03 incident:

- **No host firewall changes on Docker hosts.** Never add host `iptables`/`nftables`/`iptables-services`
  rules on a Docker host — they collide with Docker's own `FORWARD`/NAT chains and have taken the box down
  (2026-11-03: loading `iptables-services` inserted a `FORWARD REJECT` → 502 outage). The **perimeter is the
  cloud security group**; local safety is **127.0.0.1 binding**. Any host-level change (host firewall, Docker
  daemon config, kernel/network sysctls) **requires explicit approval and a written rollback plan**.
- **Out-of-scope production changes stop for approval.** Only the agreed change list proceeds; **any
  production change outside it stops** — report intent and wait. Approval for one change never generalizes to
  another, and approval in one session does not carry to the next.
- **Build off-box.** Production images are built on the amd64 pipeline, not hand-built on the production host.
- **Deploy by digest.** The prod compose pins every image by **digest**; never deploy a floating tag, and
  never `docker cp` a patch into a running container (it reverts on recreate — the October hot-patch class;
  RELEASE-PLAN §9).

---

## 6. Incident handling

1. **Contain.** Stop the bleeding without widening blast radius: for an exposure, tighten the **security
   group** (never a host firewall); for a bad rollout, stop the flip; for resource exhaustion, reclaim safely
   (log rotation, prune) and grow the volume. Do not make an out-of-scope change to "fix" it — contain, then
   get approval.
2. **Roll back.** Redeploy the previous pinned digest and revert the offending flag/env (RELEASE-PLAN §7). The
   backups + restore drill (§3) are the floor under every rollback.
3. **Record.** Write an incident note (what happened, blast radius, timeline, root cause, the exact
   contain/rollback steps, and the standing rule it produces) under `docs/`, as with
   `incident-2026-11-03-ec2-exposure-hardening.md`. A manual out-of-band action (e.g. a direct write) is
   recorded in the debt/incident log with date, record id, and reason.

---

## 7. Design note — what can be verified automatically vs manually (design only)

Which §1 prerequisites the **installer** or the **production guard** (startup, `AIRAWAT_ENV=production`) can
check by itself, and which need an operator/auditor. Design only — not all the automatic checks are built yet.

**Automatable at startup (installer / prod-guard):**
- **No default/committed-literal account passwords** — already built: the IdP refuses to boot under
  production if any account's password matches the weak list (hash-based; PRODUCTION-READINESS §8).
- **No dev conveniences under production** — already built: `prod-guard.sh` refuses to start with passwordless
  / demo-seed / iss-aud-shadow / no-verify-cert / schema-shadow active.
- **Durable store present** — built: the network fails loud if the durable backend is absent (PLATFORM P1).
- **Vault reachable + this service can mint its own token** (fail closed) — buildable: a boot self-check that
  the scoped mint works and that **no root token** is configured (reject a configured root token).
- **iss/aud envelope set, not defaulted** — buildable: refuse to boot if `IDENTITY_HOME_ISS`/`EXPECTED_AUDIENCE`
  are unset/at the prod-pointing default (extend the prod-guard).
- **Service ports bound to loopback** — buildable: a startup probe that each internal port answers only on
  127.0.0.1, not on the external interface.
- **Images pinned by digest** — buildable: the guard reads its own image ref and refuses a floating tag.
- **≥2 `platform.authority` holders / never-zero floor** — partially built (the last-holder floor is enforced
  on revoke by ADR-0122); a boot/periodic check that **≥2** holders exist is buildable.

**Manual (operator / auditor / cloud control-plane — not visible to the process):**
- **Disk/snapshot/backup encryption with a customer-managed key** — the running process cannot read the
  cloud volume/snapshot encryption state (needs control-plane permissions it must not hold); verify via the
  console/CLI (AWS-APPENDIX §1) and record.
- **Perimeter: only 80/443 public, SSH from admin CIDRs** — a security-group fact in the cloud control plane,
  not observable from inside the host; review via the console/CLI (AWS-APPENDIX §2).
- **Vault unseal via instance identity across reboot** — the unseal mechanism is infrastructure; confirm by a
  controlled reboot in rehearsal, not by a self-check.
- **Dedicated host, no unrelated projects** — an environment fact; audited by inventory, not the app.
- **Backups actually restorable** — only a performed **restore drill** proves it; cannot be asserted at
  startup.
- **Break-glass custodian roster + quorum** — an organisational control; recorded and rehearsed, not
  machine-checkable.
- **Native amd64 build provenance** — a pipeline property; attest in CI (and the digest pin), not at runtime.

_Docs only. Nothing here changes code or deployed state._

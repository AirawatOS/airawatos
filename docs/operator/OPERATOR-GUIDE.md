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

# Layer 1 — CONDITIONS-ONLY RE-CHECK (slice 1j)

Date: 2026-11-09. Scope, frozen: conditions **4**, **6** and **7** of [LAYER1-EXIT-FINAL](LAYER1-EXIT-FINAL.md) §5 as
implemented in slice 1j (root `1740bec`/`d399f87`; images `manishsv/airawatos-*:1j`), plus the three conditions the owner
attached to approving unauthenticated `generate-root` in local-dev, plus one owner-directed debt registration. Findings only:
no product code was changed by this re-check.

The commit carrying this file contains:
- the two reviewer reports;
- debt rows DEBT-B153 to B162;
- one matrix evidence case (`verify/known_violations.py`) for the High finding;
- the regenerated matrix.

**Exit rule (owner):** PASS if conditions 4, 6 and 7 hold and no High-severity Layer 1 finding exists. Everything else is
registered with an owner and a deadline and does not block, **except an unmet generate-root condition, which must be fixed
before merge**.

## Verdict: **FAIL**

**Condition 4 does not hold, and there is a High-severity Layer 1 finding (DEBT-B154).** If a restore fails while it is
copying the live volumes aside, its automatic rollback **deletes live volumes**. Conditions 6 and 7 hold.

**All three generate-root conditions are not met** (DEBT-B160). They must be fixed before merge.

| # | Condition | Result | Deciding evidence |
|---|---|---|---|
| 4 | Restore validates everything before destroying anything (B124/B126/B139/B140) | **DOES NOT HOLD** | Every earlier failing case is now refused with "nothing was changed": the 6-of-7-volume backup, a backup without AppRole files, absolute and escaping symlinks, `../` members, an empty manifest, a missing `.env`, odd or duplicate manifest keys, a rogue host file. Odd but legal names (newline, `a..b`) restore correctly. Disk full while staging (a 1 MB tmpfs side volume) is refused with the stack untouched. A wrong secret-id rolls back with the post-backup marker intact. **But F-C4-3 (High):** a failed copy-aside makes the rollback `docker volume rm` every live volume not yet copied (pg, vault, identity, netfiles and vault_audit were deleted, and a fresh Vault initialised itself), and it restores filestore from its truncated copy. **F-C4-4 (Med):** SIGTERM during the switch leaves the stack down with no rollback and no message. |
| 6 | Every installer helper fails on a failed write; the guard survives recreation (B127/B135/B141) | **HOLDS** | The earlier reviewer's shelf case (`Phase 1c\|/realms/localdev-network/login`, empty slate) now exits 1 with the INJECTED line and names Phase 1c. Recreating **network** mid-install: the guarded helper fails and names the phase. The guard is in all three 1j images, byte-equal to the repo. A shadowing `sitecustomize.py` in the script dir, the cwd or `/app` does not override it. No python or curl write in `install.sh` bypasses XNET/XAPP. Low: an `env PYTHONPATH=` helper runs unguarded (only Phase 15's exit-checked functional proof), and the legacy `deploy/local/` installer has no guard. |
| 7 | Vault scope covers every mount (B132/B138) | **HOLDS** | All 5 earlier cases (KV-v1, TOTP, list-only, identity/entity/name, sudo `sys/policies/acl/*`) were proven as real 200 reads with decision's own token, and the check FAILS on each. 9 new normaliser and identity cases also FAIL the check: a `+` glob, `allowed_parameters`, `min_wrapping_ttl`, a duplicate stanza, `#` inside a quoted path, a JSON policy, a templated path, a block-comment trick, an entity with direct policies. No normaliser blind spot was found. **New Medium findings:** AppRole login constraints are not compared (`bind_secret_id=false` let decision's role_id ALONE log in and read its password), and stray credentials are not reconciled (a second root token, a stray svc-network token, an extra secret-id). |

### Generate-root approval conditions (owner's rule: fix before merge)

| | Condition | Result | Evidence |
|---|---|---|---|
| a | The regenerated root token is revoked as soon as the post-restore tooling finishes, and the drill fails if any root token remains | **NOT MET** | `deploy/local-dev/vault/entrypoint.sh:46-48` writes the regenerated root back to `init.json`, and nothing revokes it. `restore_drill.py` has no "no root remains" check and keeps using root (lines 67, 113, 116). |
| b | The drill proves every service is back, using its own credentials, BEFORE any root token is generated | **NOT MET** | Root is regenerated when Vault starts (`entrypoint.sh:38`), before any service runs. The drill's only proof that services work (`restore_drill.py:113`) comes after that and authenticates with root. |
| c | RESTORE-AND-ROTATION.md has the production break-glass procedure (recovery keys, quorum, holders, where recorded), and RELEASE-PLAN has a break-glass drill as a rehearsal gate | **NOT MET** | `RESTORE-AND-ROTATION.md` has one sentence on production (no recovery-key threshold, quorum, holders or record location). `RELEASE-PLAN.md` has no break-glass drill gate. |

Security notes on the enablement itself:
- **The pre-backup root token stays valid after a restore** (B161). Its storage entry is in the archived Vault data.
- **Anyone reaching Vault can start or cancel a generate-root attempt** (B162). Vault is reachable from all 12 service containers. This allows denial of service but not theft, because completing an attempt needs the unseal key.
- **Only the local-dev `vault.hcl` sets the flag.** But `install.sh` uses the local-dev compose for every profile, so any install inherits the flag until a production compose exists.

## Owner-directed registration (item 3)

**DEBT-B153 — production installer keeps the Vault root token at rest.** Deadline: before first production.
- `install.sh` reads the root token from `/vault/data/init.json` on the live Vault volume for every profile and never revokes it.
- Target, per ADR-0131: use the root token once during install, then revoke it, so no root token is at rest.
- After install, admin work goes through break-glass `generate-root` with the recovery-key quorum, and that token is revoked afterwards.

## Findings and debt (all registered)

| Debt | Finding | Sev | Owner | Deadline |
|---|---|---|---|---|
| **B154** | F-C4-3: a restore rollback after a failed copy-aside destroys live volumes | **High** | L1 deploy/local-dev | **before Layer 2 starts** (a High blocks the next layer) |
| **B160** | Generate-root approval conditions (a), (b), (c) not met | Med | L1 deploy/local-dev, verify, docs | **before merge** (owner's rule) |
| B153 | Production installer keeps the Vault root token at rest; target per ADR-0131 | Med (operational) | L1 deploy/installer | before first production |
| B155 | F-C4-4: SIGTERM or SIGKILL during the switch leaves the stack down, with no rollback and no message | Med (operational) | L1 deploy/local-dev | before Layer 2 exit |
| B158 | C7GR-1: AppRole login constraints and token shape are not compared (`bind_secret_id=false` lets the role_id alone log in) | Med | L1 assurance net | before Layer 2 exit |
| B159 | C7GR-2: stray Vault credentials (extra root token, stray service token, extra secret-id) are not reconciled | Med | L1 assurance net | before Layer 2 exit |
| B156 | F-C4-5: the next restore deletes the `-prev-` volumes and `.restore-prev` a failed rollback said to keep | Low | L1 | before Layer 2 exit |
| B161 | C7GR-6: the pre-backup root token stays valid after a restore | Low | L1 | before Layer 2 exit |
| B157 | L-C6-2/3: an `env PYTHONPATH=` helper runs unguarded; the legacy installer has no guard | Low | L1 deploy/installer | before first production |
| B162 | C7GR-7/8/9: mount-tune and audit options not compared; the unauthenticated generate-root endpoint is reachable from the services; server config not compared live | Low/Info | L1 | before first production |

**Matrix:** one XFAIL evidence case for B154 on ARC-3, which was already PARTIAL. The case matches on code and reproduces
the demonstrated defect.

## Condition 8 equivalent — `make verify`

**Green in ONE run:** `20261109T160221Z-72ae1911`, 16:02:21 to 16:48:44 UTC, rc 0. Before the run the slate was proven empty: 0 containers, 0 volumes, 0 networks, no stage or prev volumes, and no other container running on the host. All five repos were clean at `e51e342`. The strict matrix requires fresh evidence at the live clean HEAD of all five repos and the case baselines to hold. Among the nets: known-violation evidence (11 cases, B154 XFAIL), the installer test (6 live installs), the fresh install, the Vault scope self-test (0 of 16 mutations missed), the renewal test, the backup/restore self-test and the restore drill. After the run no other container was running, and the only change to the tree was the regenerated matrix.

The nets being green does not change the verdict. The High (B154) is outside what the selftest exercises: it needs a failure DURING the copy-aside step. It is recorded as XFAIL evidence on ARC-3.

## Recommended next step (scope frozen)

A remediation slice limited to two items:
- **B154 (High), together with B155**, since both are switch and rollback integrity: record the full existing-volume set
  before the first copy, never remove a volume that existed, journal the switch, and trap signals.
- **B160 (before merge):** regenerate root on demand, not at Vault start; revoke it when the tooling finishes; the drill
  proves the services on their own credentials first and fails if a root token remains; write the break-glass procedure
  and add the rehearsal gate.

Then a re-check of condition 4 and the generate-root conditions only. Conditions 6 and 7 held and are not reopened.

## Method

Two fresh reviewer agents took part. Neither built any of Layer 1, and neither took part in any earlier review. Their
work was destructive, so they ran one after the other, each alone on the stack.

| Reviewer | Scope | Report |
|---|---|---|
| R-A | Conditions 4 and 6. Ended with `verify/fresh_install.sh` passing from a proven-empty slate. | [recheck/C4-C6](recheck/C4-C6.md) |
| R-B | Condition 7 and the generate-root conditions | [recheck/C7-GR](recheck/C7-GR.md) |

Both restored everything they changed: no side volumes, every policy and role back, AppRole periods at 1h, scratch backups
(which hold the unseal key) deleted, git clean.

One residue was left: the decision role's `secret_id_bound_cidrs` reads `[]` instead of `null`. Both mean "unbounded",
and resetting it would require recreating the role. The final fresh install inside `make verify` recreated every role
anyway.

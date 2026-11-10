# Layer 1 — CONDITIONS-ONLY RE-CHECK 2 (slice 1k)

Date: 2026-11-10. Scope, frozen:
- **Condition 4:** restore never destroys or modifies the live or previous system.
- **DEBT-B160:** the conditions attached to approving unauthenticated generate-root, with B161.

Both are judged as implemented in slice 1k (root `b6705cb`/`494cf9e`). Findings only: this re-check changed no product code.

The commit carrying this file contains:
- the two reviewer reports;
- debt rows DEBT-B163 to B170;
- two matrix evidence cases;
- the regenerated matrix.

**Exit rule (owner):** PASS if condition 4 holds, B160 is met, and no High-severity Layer 1 finding exists. Anything else
is registered with an owner and a deadline and does not block.

## Verdict: **PASS**

Condition 4 holds and B160 is met. No High-severity Layer 1 finding exists. Every new finding is Medium or lower
and registered with an owner and a deadline: two Mediums (B163 and B164, before Layer 2 exit), the rest Low or Info.

| Item | Result | Deciding evidence |
|---|---|---|
| **Condition 4** — restore never destroys the live/previous set | **HOLDS** | See below. |
| **B160 (a)** — no root at Vault start; root only on demand, revoked when the tooling finishes | **MET** | `vault/entrypoint.sh` only reads a root token that is already in `init.json`. It never runs generate-root (first boot, restart or restored volume). `vault_root.py` is the only writer of a generated root. Every generate in the drill is followed by revoke-all. |
| **B160 (b)** — the drill proves every service healthy on its OWN token before any root exists | **MET** | The "no root" check (`restore_drill.py:125`) runs before the per-service probes (`:129-139`), and the first post-restore generate comes after them (`:141`). The probes cover all 12 Vault-using services, including the brokers. A root token could not pass: each probe requires 403 on another service's path. |
| **B160 (c)** — the drill fails if any root remains; break-glass procedure and rehearsal gate present | **MET** | verify-none enumerates every token accessor, so it finds roots not recorded in `init.json`. A failed revoke-all fails the drill. The production break-glass procedure is at `RESTORE-AND-ROTATION.md` §PRODUCTION break-glass (KMS auto-unseal, 3-of-5 recovery keys, holders, custody register, revocation, audit review, rekey), and the break-glass drill is a RELEASE-PLAN rehearsal gate. Run `b803c462`: 2 root tokens revoked, 0 remaining. |
| B161 — every root token revoked after a restore | **Partly met** (Low, B167) | The drill does it. An ordinary operator `restore.sh` run does not, so the pre-backup root token is valid again in the restored Vault. |

### Condition 4 in detail

The reviewer ran every case with the stack stopped and fingerprinted the previous set before and after: every file's name,
mode, owner, size, mtime and sha256 in all 7 volumes, plus `sets/<set>/` and the pointer. In every case the previous set
stayed **byte-identical** and the system was recoverable. The original live set matched its first fingerprint at the end
of the session.

The earlier reviewers' failure modes are gone (F-C4-3 tiny `-prev-` volume, F-C4-4 signals mid-switch, F-C4-5).

New variants that also held:
- a backup whose `.env` sets `AOS_VOLSET` to the live set's name (4 spellings, manifest rehashed);
- SIGTERM during `compose down`, `up -d` and the health wait;
- a second signal while rolling back;
- SIGKILL during the cut-over, then a second restore (refused), then two `--recover` runs at once;
- SIGKILL during the rollback itself;
- disk full while staging;
- an unwritable `sets/`;
- the new Vault container killed during the cut-over;
- two restores started 0.5 s apart;
- prune of a set whose containers are running (refused).

Two neighbouring tools can still destroy data when given bad input. Neither is reached by an ordinary restore:
- `--recover` follows a hand-edited journal (B163);
- `prune` accepts path spellings of the active set (B164).

## New findings (all registered; none High)

| Debt | Finding | Sev | Owner | Deadline |
|---|---|---|---|---|
| B163 | F-C4-6: `restore.sh --recover` trusts the journal. NEW = the active set, NEW = PREV, or a `../` name deleted live data, and it still printed "previous set untouched". | Med | L1 deploy/local-dev | before Layer 2 exit |
| B164 | F-C4-7: `_sets.py prune` compares the raw argument. `./<active>`, `x/../<active>`, `""` and `..` all deleted live data or more. | Med | L1 deploy/local-dev | before Layer 2 exit |
| B165 | F-C4-8: no lock between concurrent restores. An interleaved failure rolled back to an older set, wrote to it, and left the newer live set inactive. | Low | L1 | before Layer 2 exit (production runbook: before first production) |
| B166 | Restore Info items: non-standard `AOS_VOLSET` spellings, abort messages name the wrong stage, anonymous vault volumes accumulate, stale temp dirs. | Info | L1 | before first production |
| B167 | B161 happens only in the drill: after an ordinary restore the old root token is valid again, and its value sits in the previous set's `init.json`. | Low | L1 | before Layer 2 exit |
| B168 | `vault_root.py` can report success it didn't prove: a failed accessor listing reads as empty, failed self-revoke is ignored, and the drill has no try/finally. | Low | L1 | before Layer 2 exit |
| B169 | Admin procedures still assume a root token in `init.json` after a restore (installer re-run, DB-password re-sync, root rotation). | Low | L1 docs + installer | before Layer 2 exit |
| B170 | Vault Info items: the "no root at rest" check covers `init.json` only; stale comments; root token visible in the process list as a docker argument; unauthenticated generate-root inherited by every install profile. | Info | L1 | F5/F6 before Layer 2 exit; F7/F8 before first production |

**Matrix:** two XFAIL evidence cases on ARC-3, for B163 and B164. Each matches on code and reproduces a defect
demonstrated live. ARC-3 was already PARTIAL (B144).

## `make verify`

**Green in ONE run:** `20261110T023720Z-16ff0896`, 02:37:20 to 05:16:00 UTC, rc 0. Before the run the slate was proven empty: 0 containers, 0 volumes, 0 networks, and no other container running on the host. All five repos were clean at `c0bc082`. The strict matrix requires fresh evidence at the live clean HEAD of all five repos, with the case baselines held. Among the nets: known-violation evidence (12 cases, including the two new XFAILs), the installer test, the fresh install, the Vault scope self-test (0 of 16 missed), the renewal test, the backup/restore self-test (0 failures, including the never-in-place cases) and the restore drill (0 failures; no root token remains). Afterwards no other container was running, and the only change to the tree was the regenerated matrix.

## Method

Two fresh reviewer agents took part. Neither built any of Layer 1, and neither took part in any earlier review.

| Reviewer | Scope | Report |
|---|---|---|
| R2-A | Condition 4. Destructive, alone on the stack; byte-identity measured with the stack stopped. | [recheck2/C4](recheck2/C4.md) |
| R2-B | B160 and B161. Read-only on the live stack, in parallel. Code and docs, plus the evidence of run `b803c462`. | [recheck2/B160](recheck2/B160.md) |

R2-A ended with the stack healthy on one set and no stray volumes or containers. It deleted its scratch backups and left
git clean. Its leftover helper scripts in `/tmp/c4tools` (no secrets) were deleted.

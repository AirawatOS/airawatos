# Contributing to AirawatOS

AirawatOS is five Git repositories that are checked out side by side until the repository restructure lands
(`docs/consolidation/REPO-RESTRUCTURE-PROPOSAL.md`):

| Repository | What it holds |
|---|---|
| `airawatos` (root) | deploy (installer, local-dev stack, runtime guard, backup/restore), verify/conformance nets, docs |
| `platform-spec` | the reference services (identity, app-host, scheduler, secrets, decision, workflow, …) |
| `kernel` | the kernel (registry, authz decision function) |
| `network` | the network / trust plane |
| `components` | apps, engines, drivers and their shared library |

This file applies to all five; each nested repository's `CONTRIBUTING.md` points here.

## How a change reaches `main`

`main` is protected on every repository. Nobody pushes to it directly, maintainers included.

1. **Branch** from the current `main`: `feat/<topic>`, `fix/<topic>` or `docs/<topic>`. One topic per branch. A change that
   spans repositories uses the **same branch name** in each affected repository.
2. **Commit, signed.** Every commit must be signed with your SSH or GPG key; unsigned commits are rejected:
   ```
   git config --global gpg.format ssh
   git config --global user.signingkey ~/.ssh/id_ed25519.pub
   git config --global commit.gpgsign true
   ```
   Then add the same public key to GitHub as a *signing* key. Write messages that say what changed and why, and cite the
   debt id (`DEBT-Bnnn`) or ADR when there is one.
3. **Verify** before you open the pull request, on a **proven-empty slate** with no other containers on the host:
   ```
   make verify          # from the root checkout; every net, the fresh install, the strict status matrix
   ```
   It must end with `✓ make verify: all assurance nets green`. Paste the run id (`[build_matrix] … for run <id>`) into the
   pull request. A failing net is fixed in the branch. Never weaken a net to get green: change a test only when the test
   itself is wrong, and say so in the pull request.
4. **Open a pull request** into `main`, one per repository. A cross-repository change lists its sibling pull requests
   and the order they merge in: **kernel, network, platform-spec, components, root last**. The description says:
   - what changed and why;
   - which debt it closes and with what evidence;
   - which debt it opens, with owner and deadline;
   - the `make verify` run id.
5. **Review.** Every pull request needs one approving review from someone other than the author. **Core paths need a
   second reviewer** from `CODEOWNERS`, which GitHub enforces:
   - kernel;
   - identity;
   - network;
   - app-host;
   - authz;
   - `deploy/installer`;
   - Vault configuration (`deploy/local-dev/vault/`, `deploy/runtime/`).
6. **Required checks.** The verification status must be green on the pull request's head commit. New commits invalidate
   earlier approvals.
7. **Merge with a merge commit.** No squash, no rebase-merge: history is preserved, and evidence names the exact commits.
   Merge in the order above.

Layer exits follow the standard in `docs/consolidation/FIX-PLAN.md` § *Layer exit standard*: one deep review, a
scope-frozen re-review of its conditions, and debt registered with an owner and a deadline.

## Image policy

**Images for `main` are rebuilt from `main` with `deploy/build-images.sh`. They are not pulled from or pushed to any
registry.**

- `deploy/build-images.sh <tag>` exports each repository's **committed** `HEAD` with `git archive`. It refuses a dirty tree,
  so nothing untracked (`.env`, credentials, local build output) can enter an image. It builds three images:
  - `manishsv/airawatos-reference:<tag>`;
  - `manishsv/airawatos-kernel:<tag>`;
  - `manishsv/airawatos-network:<tag>`.

  It records every source commit, the image ids and the OS package list in `deploy/local-dev/IMAGES.lock.json`.
- `<tag>` is the one pinned in `deploy/local-dev/docker-compose.dev.yml` (`image:` lines). To build what `main` runs, check
  out `main` in **all five** repositories and run `deploy/build-images.sh <tag from compose>`.
- **Changing what the images contain** (any change to the services, `deploy/runtime/` or a Dockerfile) means:
  1. bump the tag in the compose file;
  2. rebuild with the new tag;
  3. commit the new `IMAGES.lock.json` in the same pull request.

  `make verify` (`verify/images_test.py`) fails if a running image differs from the lock, if `/app` differs from the git
  tree, or if any installed Python or OS package is not in the lock. Never retag an old image to a new tag by hand.
- **Why no registry yet.** The images are built and verified on arm64 only, and an amd64 build is not yet proven
  (DEBT-B114). The `manishsv/` namespace is a personal one. Until a project registry and an amd64 build exist, **every
  developer builds locally from `main`**, and the lock file is the record of what was built. Publishing to a registry is
  a before-first-production item: an organisation-owned registry, images signed, multi-arch built in CI from `main`.

## Local install

`docs/operator/INSTALL-LOCAL.md` covers the clone, build, install, sign-in and reset steps. `deploy/local/` is **legacy**:
do not use it.

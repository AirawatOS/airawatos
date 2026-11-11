# F3: Independent review of the slice-1h reproducible-image fix (B101) and the shipped 1h images

Reviewer: independent; did not build Layer 1 and took part in neither earlier exit review. Date: 2026-11-09.
Scope: B101 (deploy/build-images.sh, IMAGES.lock.json, verify/images_test.py) and the three shipped `:1h` images. Findings only. No tracked file, git state or running container was changed.

## Verdict for this scope

**PASS, with no L1-owned Medium+ finding.** A clean clone from the remotes, checked out at the SHAs in IMAGES.lock.json and built with the clone's own `build-images.sh` on a builder with no usable cache, gives images whose content matches the running `:1h` images file for file:
- every file in /app and /opt/airawat
- `pip freeze --all`
- every dpkg package and version
- the docker CLI binary
- the image Config

The image IDs differ. That is expected, because BuildKit records build-time timestamps (details below). The claim in the debt register that "two builds from the same commits gave the SAME image ids" only holds when the build cache is hit. The test that guards the claim (verify/images_test.py) checks the content of the reference image's /app only. The findings are Low/Info. F3-2 is the one closest to Medium; the reasoning for rating it Low is given there.

## Comparison table: clean-clone rebuild (`:final-review`) vs running `:1h`

The clone was built at root@52d3983, platform-spec@98b0e72, kernel@b3b6373, network@0c9b094 and components@8cef04a, using `BUILDX_BUILDER=desktop-linux ./deploy/build-images.sh final-review` run from the clone root. The only cache hit on the first build was the base image, so this was effectively a `--no-cache` rebuild.

| Image | Recorded / 1h id | Clean-clone id | Layers same (diff_id) | pip freeze | dpkg (pkg+ver) | /app (sha256+mode per file) | /opt/airawat | docker CLI | Config JSON |
|---|---|---|---|---|---|---|---|---|---|
| reference | c47eacdff067 | 9156dd145c74 | 4/13 (base only) | identical | identical | identical (272 files under reference+components) | identical (4 files) | identical sha256 d73c719d… (29.9.3) | identical |
| kernel | 26363761f0ae | 7fdb76cf8784 | 4/16 (base only) | identical | identical | identical | identical (6 files incl. 2 host .pyc) | n/a | identical |
| network | 3f9657baf578 | 58c8019dcaca | 5/15 | identical | identical | identical | identical (6 files incl. 2 host .pyc) | n/a | identical |

Method: `docker run --rm --network none --entrypoint sh <img> -c 'pip freeze --all; dpkg-query -W …; python3 h.py /app /opt/airawat; sha256sum /usr/local/bin/docker'`, then `diff`. The diff was 0 lines for all three images (432, 183 and 195 lines compared).

Why the IDs differ (expected, not a defect):
- **Layer diff_ids differ** because file and directory mtimes are build-time values. For example, in kernel `/app` and `/usr/local/bin/pip` are 2026-11-08 17:05 in 1h and 2026-11-09 01:13 in the rebuild. The git-archive files carry the commit time of the archived commit.
- **The image id** (the config digest) also includes `created` and the history timestamps. Nothing sets `SOURCE_DATE_EPOCH` or `rewrite-timestamp`, so a bit-identical rebuild is impossible by design.
- **Debian drift.** `apt-get upgrade` and the unversioned `apt-get install …` are a documented non-pin. They produced no package difference today, so no drift was observed in this run.

## Findings

| ID | Sev | Finding | Owning layer | In 1h scope | L1-owned Medium+ |
|---|---|---|---|---|---|
| F3-1 | Low | The "same commits → same image ids" proof only shows a build-cache hit. It is not reproducibility. The lock's `root` SHA for reference and kernel is not the commit those bytes were archived from. | L1 build | yes | no |
| F3-2 | Low | images_test.py proves content against git only for the reference image's /app. It does not check /opt/airawat (the baked guard and Vault renewer), the kernel/network /app, installed packages or Debian packages. The lock is self-attesting: an image tampered with outside the script passes once its id is written into the lock. | L1 build/verify | yes | no (see rationale) |
| F3-3 | Low | `build-images.sh` uses whatever buildx builder is selected. On this host that is `airawatx` (docker-container driver), so running the script as documented would start `buildx_buildkit_airawatx0`, the container the host must stay free of. ba2d764 fixed only the probe. | L1 build | yes | no |
| F3-4 | Low | The lock path is relative to the cwd (`open("deploy/local-dev/IMAGES.lock.json","w")`). Run from another cwd, the script either crashes after tagging (tags updated, lock stale) or overwrites another checkout's lock. The script also dirties its own repo (the lock is tracked), so a second run refuses until the lock is committed or `ALLOW_DIRTY=1` is set. | L1 build | yes | no |
| F3-5 | Low | Unpinned network inputs remain beyond the documented `apt-get upgrade`: the `# syntax=docker/dockerfile:1` floating frontend tag (pulled from Docker Hub at build time), unversioned `apt-get install` packages, the docker CLI tgz downloaded without a checksum (held R2-7), and pip without `--require-hashes` (held R2-7). | L1 build | partly (R2-7 held) | no |
| F3-6 | Low | Host-built artefacts are tracked in git and so ship. `deploy/runtime/__pycache__/{svc_health,vault_renew}.cpython-314.pyc`, compiled on the host with Python 3.14, land in kernel and network `/opt/airawat/__pycache__/`. There is no .dockerignore for the `runtime` named context; the reference image is clean via its own dockerignore. Components' tracked `.ingest-logs/` and `.onboard-logs/`, which contain host paths such as `/Users/manishsv/…` and tracebacks but no secrets, ship in reference `/app/components`. | L1 build (root repo / components hygiene) | yes | no |
| F3-7 | Low | The `Dockerfile.reference` header still documents the old working-tree build (`docker buildx build -f platform-spec/Dockerfile.reference … .`). The working tree today still has the gitignored `platform-spec/reference/identity-users.json` (the R2-5 file, 53 users) plus `components/_common/dist` and egg-info. Following that comment would put R2-5's content back into an image. images_test would catch it only through the id/lock mismatch, or through the /app check if the lock were updated. | L1 build | yes | no |
| F3-8 | Info | Not reproducible "from a clean host" without a build step. The `:1h` tags are not resolvable on Docker Hub (`docker manifest inspect` fails for all three). Compose has no `build:` section. No Makefile target or README step runs `build-images.sh`. The lock does not record whether `ALLOW_DIRTY` was used, or whether the HEADs were pushed. They are pushed today: the clone at the recorded SHAs succeeded. | L1 install/docs | yes | no |
| F3-9 | Info | The lock's `base` field is hard-coded in `build-images.sh`, not read from the Dockerfiles. If a Dockerfile's base changed, the lock would still report the old digest. | L1 build | yes | no |

### F3-1 evidence

- The git-archive mtimes inside the shipped images name the commit the bytes came from:
  - `/opt/airawat/svc_health.py` is `2026-11-08 17:03:07 UTC` in reference:1h and kernel:1h. That is 22:33:07 IST, the time of root commit **06017fc**.
  - The same file is `17:24:55 UTC` (22:54:55 IST, i.e. 52d3983) in network:1h and in my rebuild.
- The images were created at reference `17:04:28Z` and kernel `17:05:31Z`, both before 52d3983 existed (`17:24:55Z`). Network was created at `17:25:32Z`.
- So reference and kernel were built at root 06017fc. A later run at 52d3983 hit the cache (BuildKit content hashes ignore mtime) and wrote `root: 52d3983` into the lock.
- `git diff 06017fc 52d3983 -- deploy/runtime deploy/build-images.sh` is empty, so the content is identical and the record is not materially wrong.
- Reproduced the cache behaviour: a second clone build (`ALLOW_DIRTY=1`, because the first run had dirtied the lock) gave **the same ids** 9156dd…/7fdb76…/58c801…, with 33 CACHED steps. A cache-cold build gave different ids from 1h.
- Conclusion: "same ids" proves only the cache. The real reproducibility property is content equality, which holds (see the table).

### F3-2 evidence (tamper demonstration, run in the clone only, own tags)

1. Copied the current `verify/images_test.py` into the clone and pointed the clone's compose at `:final-review`. With the untampered rebuild, `✓ images test: 0 finding(s)`, and reference /app was equal to git (272 files).
2. Built `FROM airawatos-{reference,kernel}:final-review` with:
   - `/opt/airawat/airawat-entrypoint.sh` prefixed with `exit 0  # TAMPERED: production guard bypassed`
   - an extra package installed with `pip install six==1.16.0`
3. Wrote the new ids into the clone's lock and re-ran: `✓ images test: 0 finding(s)`. Inside the tampered kernel image, `head -1 /opt/airawat/airawat-entrypoint.sh` → `exit 0  # TAMPERED…` and `pip freeze` → `six==1.16.0`.

Rationale for Low rather than Medium:
- The lock is a tracked file, so a hand-edited id appears in git.
- `build-images.sh` cannot inject working-tree content, even with `ALLOW_DIRTY=1`, because it always archives HEAD.
- This particular tamper (a neutered guard) would be caught behaviourally by `verify/gateflags_test.py`, which runs every shipped image outside compose and expects rc 97.
- What remains undetected is subtle content drift: kernel/network code, `vault_renew.py`, extra or changed packages.
- Raise it to Medium if Layer 1 claims images_test proves "every shipped image equals git". It does not, and the image id cannot serve as that proof because ids are not reproducible (F3-1).
- Suggested fix: extend the /app-by-content check to kernel/network /app and to /opt/airawat (against root `deploy/runtime` + `platform-spec/reference/gateflags.py`), and record and compare a `pip freeze` digest.

### F3-3 evidence
`docker buildx ls` → `airawatx*  docker-container  \_ airawatx0 stopped` (selected); `desktop-linux docker running`. `build-images.sh` calls `docker buildx build --load --provenance=false` with no `--builder`. I ran it with `BUILDX_BUILDER=desktop-linux`. Afterwards `buildx_buildkit_airawatx0` was still `Exited (1) 6 hours ago`; it was not started.

### Question-by-question

1. **Clean clone.** Done: all five repos cloned from origin on their current branches; remote HEADs equal the local HEADs; root checked out at the lock's 52d3983. The content equals 1h on every axis compared. The only differences are ids and diff_ids (timestamps). No real defect.
2. **Outside-git dependencies.**
   - Host tools: git, tar, python3, docker buildx, and whichever builder is selected (F3-3); cwd-relative lock (F3-4).
   - Network: the pinned base digest; the floating `dockerfile:1` frontend; apt (unpinned); the docker CLI tgz (version-pinned, no checksum); the pip index (version-pinned, no hashes) (F3-5).
   - No working-tree, untracked or local-image input: everything comes from `git archive HEAD`.
   - Dirty-tree refusal: it applies to all five repos (`_export` for each; `--untracked-files=no`; staged and modified both count). I observed the refusal `✗ root has uncommitted changes`. With `ALLOW_DIRTY=1` the content is still HEAD.
   - git archive and attributes: no `.gitattributes` in any repo, no `export-ignore` or `export-subst`, no submodules (no `160000` entries), no LFS. The only tracked symlinks are `kernel/.venv/bin/*`, and those are not copied. Tracked .pyc files do ship (F3-6).
3. **Runnable from a clean clone.** Host state the stack needs, all generated by the installer:
   - `deploy/local-dev/.env` (`POSTGRES_PASSWORD`, `install.sh` around lines 182–191)
   - `deploy/local-dev/vault/approle/*.env` (`_setup_vault_approle`, around line 137)
   - the Vault `init.json`, created by the vault entrypoint inside the vault volume

   `docker compose config` on the clean clone fails (`env file …/vault/approle/event-relay.env not found`), but the installer's first step, `up -d postgres vault`, works without them: a `--dry-run` from the clone succeeded and created nothing. Prerequisite: the images must be built locally first with `build-images.sh`, and that is undocumented (F3-8). I did not run the installer against the live stack (out of bounds).
4. **images_test.py.**
   - It detects a rebuilt image (id ≠ lock) and running containers that do not run the recorded id.
   - It compares by content only the reference image's /app. It does not cover /opt/airawat, packages or kernel/network /app (F3-2).
   - A dirty tree cannot pass through `build-images.sh`, because content is always HEAD.
   - A working-tree build plus a hand-edited lock passes for kernel/network, and for anything outside reference /app (demonstrated in F3-2).
   - File modes are not compared.

## Held (confirmed fixed / holding)
- R2-5: no `identity-users.json`, `dist/` or egg-info in reference:1h. /app equals git by content (272 files, 0 extra, 0 missing).
- Every source SHA in the lock exists on the remotes and checks out cleanly.
- `build-images.sh` refuses a dirty tree in all five repos and exports only committed HEAD.
- Reference context allow-list: no `__pycache__`/.pyc in the reference /opt/airawat.
- All three images are content-reproducible from a clean clone: pip, dpkg, /app, /opt/airawat, docker CLI and Config all identical.
- Pinned items, unchanged in my build: the base digest, the pip tooling, every lock line, and the docker CLI version.
- The running stack runs the recorded ids (`verify/images_test.py` in the original tree: 0 findings, after my cleanup).

## Cleanup confirmation
- Removed my images: `manishsv/airawatos-{reference,kernel,network}:final-review` were deleted with `docker rmi`. The tampered variants were already garbage-collected when the tag was moved. `docker images -a` shows no image created on 2026-11-09.
- Removed `/Users/manishsv/.claude/jobs/8ad4875a/tmp/final/clone/` and `…/tmp/final/tamper/`. Evidence dumps are kept in `…/tmp/final/cmp/`, plus the hash helper `h.py`.
- The `:1h` tags are untouched: reference c47eacdff067…, kernel 26363761f0ae…, network 3f9657baf578… (equal to the lock).
- `deploy/local-dev/IMAGES.lock.json` is untouched: `git status` in the original tree shows only the pre-existing `?? deploy/installer/__pycache__/`. sha256 is 7dec8c1e…
- The running stack is unchanged: still 17 containers, vault/postgres container ids and StartedAt unchanged. `buildx_buildkit_airawatx0` was not started.
- Not removed: the BuildKit cache layers my cold build added to the built-in `desktop-linux` builder (reclaimable with `docker builder prune`). I left them because pruning could affect cache that others use.

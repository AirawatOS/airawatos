# Repository restructure — proposal

**Status:** Proposal only. This document moves nothing, renames nothing, and changes no path. It describes a
target layout and a migration plan for a *later* decision (see §5 timing). Nothing here is executed by committing it.

**Scope note:** the prompt named "five repositories"; the working tree actually contains **eight** git repos
(the extra three — `domain-spec`, `intelligence-spec`, `tests-repo` — only sharpen the argument). All are listed below.

---

## 1. Current state

### 1.1 The repositories

The working directory `/Users/manishsv/Documents/Projects/Airawat` is **eight independent git repositories**
checked out side by side (the root repo ignores the sibling repos via a `/*` allowlist `.gitignore`):

| Repo (remote `github.com/AirawatOS/…`) | Working-dir path | Holds | Rough size |
|---|---|---|---|
| `airawatos` (root / orchestration) | `.` | deploy tooling, conformance suite, `docs/`, `services/`, root compose + README. Tracks **only** an allowlist (`/*` + `!` entries); all code lives in the sibling repos. | — |
| `platform-spec` | `platform-spec/` | **The reference implementation** — `reference/` (identity, app-host + `hostcore`, scheduler, model-gateway, secrets, runtime-manager, filestore, svc_gate/svc_token, broker) **plus** `spec/`, `schemas/`, `interfaces/`, `governance/`, `operator/`, `deploy/`. Name says "spec", contents are mostly implementation. | 13 M / 237 files |
| `kernel` | `kernel/` | kernel `api/`, `services/`, `cli/`, `tools/`, its own `conformance/`, `tests/`, `deploy/`. | 38 M / 108 files |
| `network` | `network/` | network authority `api.py`, `ensure_install.py`, `trust/` (ADR-0119 planes), `decisions/`, `deploy/`. | 71 M / 93 files |
| `components` | `components/` | 16 component tiers — `_common` (SDK), `apps`, `drivers`, `engines`, `connectors`, `pipelines`, `solutions`, `skills`, `experts`, `runtimes`, `providers`, `adapters`, `governance`, `diagnostics`, `demos`, `tools`. | 55 M / 568 files |
| `domain-spec` | `domain-spec/` | `packs/`, `schemas/` — governed domain vocabulary + schema catalogue. | 884 K / 214 files |
| `intelligence-spec` | `intelligence-spec/` | `spec/`, `schemas/` — AI/model governance specs. | 268 K / 58 files |
| `tests` | `tests-repo/` | black-box service test suite (`github.com/AirawatOS/tests`). | 228 K / 11 files |

Each repo is on its **own feature branch** today (`docs/trusted-network-platform-adr-0119-0120`,
`feat/network-console-multinetwork`, `feat/admin-issuer-scope`, `feat/trust-plane-phase1`,
`feat/network-console-multinetwork`), which is itself a symptom — see below.

### 1.2 Friction observed

1. **Cross-repo commits and tags per slice.** A single logical slice routinely edits several repos at once.
   Example (slice-1c-iv-b, this program): one change spanned `platform-spec/reference/identity.py`,
   `network/ensure_install.py`, and root `deploy/` — **three commits, three pushes, and a `pre-identity-cutover`
   tag applied to all three repos** so they revert as a set. There is no atomic commit, no single PR, and no way
   for CI to see the change as one unit. The branches above are out of sync precisely because slices land
   unevenly across repos.
2. **Image version pinning by hand.** Service image tags are edited directly in the compose files, with **no
   single source of truth and divergent tag schemes**. Current pins seen across the three compose files:
   `airawatos-reference:dev-hard17`, `…:0.2.115-settings-fixes`, `…:0.2.95-gwreason`,
   `…:0.2.100-sched-devenv`, `…:0.2.130-ekyc`, `…:0.2.83-auth-installer`; `airawatos-kernel:dev-hard7`,
   `…:0.2.8-devgrant`; `airawatos-network:dev-a77`, `…:0.3.19-ekyc`. Three ad-hoc families (`dev-hardN`,
   `dev-aN`, `0.x-name`) that must be bumped by hand and drift between files.
3. **The `conformance/` ignore issue.** The root `.gitignore` is a deny-all allowlist (`/*` then `!`-entries).
   `conformance/` is force-tracked (`!/conformance/`) and carries its own `.gitignore` to keep `.creds.json`
   (passwords) and `results/` out. Because of the deny-all, new conformance files must be added with
   `git add -f`, which is a standing papercut and an easy way to forget a file.
4. **`platform-spec` holds the implementation.** The repo named for the *spec* is where the running reference
   services live (`reference/`). Specs and code share one repo under a misleading name.
5. **Specs scattered across four places.** Normative material lives in `docs/specs/` (21 files),
   `platform-spec/spec/` (15), `platform-spec/schemas/` (1), `domain-spec/` (214, its own repo),
   `intelligence-spec/` (58, its own repo), and ADRs in `docs/decisions/` (80). No single "constitution".
6. **Two conformance folders.** `conformance/` (root — `run.py`, `run-both.sh`, flow-map, vault-scope, matrix)
   and `kernel/conformance/` (kernel's own), plus a `docs/conformance/`. The black-box suite is a *third* repo
   (`tests-repo/`). Which suite is authoritative is unclear from the tree.
7. **Multiple compose files.** Eight compose files exist; three define the stack
   (`docker-compose.yml` root, `deploy/local-dev/docker-compose.dev.yml`, `deploy/local/docker-compose.yml`) with
   overlapping-but-divergent service definitions and image pins; the rest are per-repo or snippet
   (`kernel/deploy/*`, `network/deploy/*`, `services/*/compose.snippet.yml`).
8. **Runtime data inside the tree.** `.filestore-data/` holds **5,815 files** of runtime blob store at the repo
   root (gitignored — 0 tracked — but physically inside the working copy, inflating scans, backups and `du`).
9. **13 `.env` files — all secret, all untracked (good, but undocumented).** Every one holds a credential:

   | `.env` file | Holds | Secret? | Tracked? |
   |---|---|---|---|
   | `deploy/local-dev/.env` | `VAULT_TOKEN` | **yes** | no (gitignored) |
   | `deploy/local/.env` | `VAULT_TOKEN` | **yes** | no |
   | `deploy/local-dev/vault/approle/app-host.env` | `VAULT_ROLE_ID` + `VAULT_SECRET_ID` | **yes** | no |
   | `…/approle/automation.env` | role-id + secret-id | **yes** | no |
   | `…/approle/decision.env` | role-id + secret-id | **yes** | no |
   | `…/approle/event-relay.env` | role-id + secret-id | **yes** | no |
   | `…/approle/identity.env` | role-id + secret-id | **yes** | no |
   | `…/approle/kernel.env` | role-id + secret-id | **yes** | no |
   | `…/approle/model-gateway.env` | role-id + secret-id | **yes** | no |
   | `…/approle/network.env` | role-id + secret-id | **yes** | no |
   | `…/approle/scheduler.env` | role-id + secret-id | **yes** | no |
   | `…/approle/secrets.env` | role-id + secret-id | **yes** | no |
   | `…/approle/workflow.env` | role-id + secret-id | **yes** | no |

   All 13 are generated at install (the 11 approle envs by `_setup_vault_approle`; the two `VAULT_TOKEN` envs
   from the dev-root discovery) and none are committed. The risk is not leakage today — it is that nothing in
   the repo *documents* that these exist, where they come from, or that they are per-install throwaways.

---

## 2. Target

**One repository**, laid out to mirror the architecture tiers (constitution → core → gateways → components),
with runtime data and build outputs kept **outside** the tree and ignored.

```
airawatos/                      (single repo)
  constitution/                 all specs, ADRs, schemas, glossary — the normative layer
    decisions/                  ADRs (from docs/decisions)
    specs/                      platform specs (docs/specs + platform-spec/spec)
    schemas/                    platform + domain + intelligence schema catalogues
    domains/                    governed domain vocab (from domain-spec/packs)
    intelligence/               AI/model governance (from intelligence-spec)
    glossary.md
  core/                         the OS kernel + always-on platform services
    kernel/                     (from kernel/)
    identity/                   (from platform-spec/reference/identity.py + auth)
    network/                    (from network/)
    app-host/                   (from platform-spec/reference host + hostcore + routes)
    authz/                      svc_gate, svc_token, grants, policy enforcement
  gateways/                     per ADR-0130 — north/south bound gateways
    <gateway>/north/            citizen/tenant-facing ingress
    <gateway>/south/            provider/external egress
  components/                   governed, certified, delivered artifacts
    system/                     engines, connectors, runtimes, providers, governance, experts, skills, diagnostics
    apps/                       (from components/apps)
    pipelines/                  (from components/pipelines)
    drivers/                    (from components/drivers)
    adapters/                   (from components/adapters)
    solutions/                  (from components/solutions)   [addition — see §3 note]
  sdk/                          the component SDK (from components/_common)
  deploy/                       installer, compose, Dockerfiles, vault policies
  conformance/                  single suite (root + kernel + black-box merged)
  tools/                        repo-level tooling
  docs/                         operator/tutorial/runbook prose (non-normative)
```

Kept **outside** the repo and ignored: `.filestore-data/` (runtime blob store), all `dist/`/`build/` outputs,
all `*.env` (per-install secrets), `init.json`, `*.pem`/`*.key`, conformance `results/` and `.creds.json`.

---

## 3. Full mapping table

| Current (repo · path) | → Target | Notes |
|---|---|---|
| root · `docs/decisions/` | `constitution/decisions/` | ADRs are normative → constitution. |
| root · `docs/specs/` | `constitution/specs/` | Merge with `platform-spec/spec`. |
| root · `docs/{architecture,concepts,design,plans,reviews,consolidation,performance}` | `docs/` | Non-normative prose stays in `docs/`. |
| root · `docs/{operator,runbooks,tutorials,examples,solutions}` | `docs/` | Operator/tutorial prose. |
| root · `docs/conformance/` | `conformance/` (docs merged) | Fold the conformance prose next to the suite. |
| root · `conformance/` | `conformance/` | Becomes the single suite; drop the `!/conformance/` force-track hack. |
| root · `deploy/{installer,local-dev,local,ec2}` | `deploy/` | One deploy tree; collapse local vs local-dev (see §5). |
| root · `services/{service-gateway,mospi-gateway}` | `gateways/` | These are the first real gateways → the gateways tier (ADR-0130). |
| root · `docker-compose.yml`, `deploy/**/docker-compose*.yml` | `deploy/compose/` | One canonical compose + profile overrides, not three divergent files. |
| root · `.filestore-data/` | **out of repo** | Runtime data → external volume; ignored. |
| root · `tools/`, `perf/` | `tools/`, `perf/` | Unchanged. |
| platform-spec · `reference/identity.py` + auth | `core/identity/` | **Split:** identity is a core service, not "spec". |
| platform-spec · `reference/` host/app-host/hostcore/routes | `core/app-host/` | Core service. |
| platform-spec · `reference/` scheduler/model-gateway/secrets/runtime-manager/filestore/broker | `core/` (per service) | Core services. |
| platform-spec · `reference/` svc_gate/svc_token | `core/authz/` | Shared enforcement. |
| platform-spec · `spec/` | `constitution/specs/` | **Split:** specs → constitution. |
| platform-spec · `schemas/`, `interfaces/`, `governance/` | `constitution/schemas/`, `constitution/` | Normative → constitution. |
| platform-spec · `operator/`, `deploy/` | `docs/`, `deploy/` | Operator prose + deploy tooling. |
| kernel · `api/`,`services/`,`cli/`,`tools/`,`tests/` | `core/kernel/` | Whole kernel → core. |
| kernel · `conformance/` | `conformance/` | **Merge** into the single suite. |
| kernel · `deploy/`, `docker-compose*.yml` | `deploy/` | Fold into one deploy tree. |
| network · `api.py`,`trust/`,`ensure_install.py` | `core/network/` | Whole network authority → core. |
| network · `decisions/` | `constitution/decisions/` | Network ADRs join the one ADR set. |
| network · `deploy/`, Dockerfile | `deploy/` | Fold in. |
| components · `_common` | `sdk/` | **Split:** the SDK is not a component — promote it. |
| components · `apps`,`pipelines`,`drivers`,`adapters` | `components/{apps,pipelines,drivers,adapters}` | 1:1. |
| components · `engines`,`connectors`,`runtimes`,`providers`,`governance`,`experts`,`skills`,`diagnostics` | `components/system/` | **Split:** these are system/platform components → one `system/` bucket (the target's 5 buckets don't name them individually). |
| components · `solutions` | `components/solutions/` | **Addition:** solutions are first-class; the target list omitted them — recommend adding the tier rather than forcing them into `system/`. |
| components · `demos` | `docs/examples/` or `deploy/demos/` | Demos are not shipped components. |
| components · `tools` | `tools/` | Fold into repo-level tooling. |
| domain-spec · `packs/`,`schemas/` | `constitution/domains/`, `constitution/schemas/` | Governed vocab → constitution. |
| intelligence-spec · `spec/`,`schemas/` | `constitution/intelligence/`, `constitution/schemas/` | AI governance → constitution. |
| tests-repo · (black-box suite) | `conformance/blackbox/` | Fold the third test repo into the one suite. |

**Splits called out explicitly:** `components/_common` → `sdk/`; `components/` 16 tiers → `{system, apps,
pipelines, drivers, adapters, solutions}`; `platform-spec` → `core/` (implementation) **plus**
`constitution/` (specs/schemas); `network/decisions` + `kernel` ADRs → one `constitution/decisions/`.

---

## 4. Options compared

| Option | Atomic cross-layer change | Version / tag | CI | Review strictness | Verdict |
|---|---|---|---|---|---|
| **A — single repository** (target above) | **Yes** — one commit, one PR touches constitution + core + components together | **One** tag/version for the whole platform | **One** run; fresh-install + conformance gate the whole change | per-folder via `CODEOWNERS` (e.g. `constitution/` needs a steward, `core/authz/` needs security) | **Recommended** |
| **B — current multi-repo (8 repos)** | No — N commits, N tags, no atomic PR; branches drift (as seen) | N independent tags, hand-synced | N runs, no cross-repo gate | per-repo only; can't require a security review on one *folder* | Status quo — the friction in §1 |
| **C — core + public-SDK split (2 repos)** | Core changes atomic; SDK consumed as a pinned dependency | 2 tags; SDK semver pinned by core | 2 runs; SDK contract tested independently | CODEOWNERS in each; SDK gets an external-API review gate | Fallback if/when the SDK is published to third parties |

**Recommendation: Option A (single repository).** Reasons:
- **Atomic changes across layers.** The recurring pain (a slice touching identity + ensure_install + installer
  as three commits/tags) collapses to one commit, one PR, one reviewable diff.
- **Single version and tag.** One `pre-identity-cutover`-style tag marks the whole platform state, not three
  repos that must be reverted together by convention.
- **One CI run.** Fresh-install + flow-map + vault-scope + conformance gate the *entire* change set, so a
  cross-repo regression (the class that multi-repo CI cannot see) is caught before merge.
- **Per-folder review strictness via `CODEOWNERS`.** A single repo still enforces fine-grained ownership:
  `constitution/**` → spec stewards; `core/authz/**`, `core/identity/**` → security; `components/**` →
  component owners. Multi-repo can only gate at repo granularity.
- **SDK not yet external.** The only reason to keep a separate repo (Option C) is a third-party-consumed SDK;
  `_common` is internal today, so promote it to `sdk/` inside the monorepo and split later *if* it is published.

---

## 5. Migration plan

**Preserve history** when merging. For each source repo, use `git subtree add --prefix=<target>` (or
`git-filter-repo --to-subdirectory-filter <target>` then a merge with `--allow-unrelated-histories`) so every
file keeps its full `git log`/`git blame`. Never copy files in with a flat "import" commit.

**Order of moves** (each step ends green before the next — see verification):
1. **Scaffold** the target tree in the root repo on a branch; add `CODEOWNERS`, the merged `.gitignore`
   (runtime data + build + env + keys out; drop the `/*` allowlist and the `!/conformance/` hack), and the
   single `deploy/compose/`.
2. **`constitution/`** — subtree-merge `domain-spec`, `intelligence-spec`, and move `docs/decisions`,
   `docs/specs`, `platform-spec/spec`, `platform-spec/schemas` in. Pure docs/schemas → lowest risk first.
3. **`core/`** — subtree-merge `kernel`, `network`; carve `platform-spec/reference` into
   `core/{identity,app-host,scheduler,model-gateway,secrets,runtime-manager,filestore,authz}`.
4. **`sdk/` + `components/`** — subtree-merge `components`; promote `_common` → `sdk/`; regroup the 16 tiers
   into `{system,apps,pipelines,drivers,adapters,solutions}`.
5. **`gateways/`** — move `services/{service-gateway,mospi-gateway}` once ADR-0130 is written (it defines the
   north/south-per-gateway shape this tier assumes; **ADR-0130 does not exist yet** — author it before this step).
6. **`conformance/`** — merge `kernel/conformance` and `tests-repo` into the one suite; retire the force-track hack.

**What must change (and be re-pointed) at each step:**
- **Installer paths** — `deploy/installer/install.sh` references `platform-spec/reference`, `network/…`,
  `components/…`; every `COPY`/`cp`/`XNET`/`XAPP` path and the Dockerfile build contexts move.
- **Compose** — collapse the three stack compose files into one `deploy/compose/` with profile overrides; a
  **single pinned image-tag source** (an `.env` or a `versions.yaml` consumed by compose) replaces hand-edited
  `image:` lines, fixing friction #2.
- **Dockerfiles / image builds** — `platform-spec/reference/Dockerfile.local-deliver` (reference image),
  `network/deploy/Dockerfile`, `kernel/deploy/*` build contexts change to `core/…`; one build matrix, one tag
  scheme (replace `dev-hardN`/`dev-aN`/`0.x-name` with one monotonic `<platform-version>`).
- **Conformance** — `conformance/run.py`, `run-both.sh`, `flow_map_test.py`, `vault_scope_test.py`,
  `build_matrix.py` reference container/project names and repo paths; re-point to the merged layout.
- **Docs links** — ADR cross-links, `MEMORY.md`/index pointers, and any `docs/**` relative links to
  `platform-spec/…`, `domain-spec/…` move to `constitution/…`.

**Verification (gate after *every* step):**
- Fresh install green: `docker compose down -v` + `deploy/installer/install.sh --profile dev` → `✓ install complete`.
- All logins work (admins + a service-principal mint), per the ADR-0131 login checks.
- `conformance/run-both.sh` → 0 FAIL / 0 XPASS, both modes ×3.
- `flow_map_test.py` and `vault_scope_test.py` → PASS.
- No step merges until the previous step is green on all five checks.

**Proposed timing:** **after the Layer 1 (inbound-gate / identity) review closes, before Layer 2 begins.** The
restructure is a path-and-history change, not a behaviour change — doing it between layers avoids reshuffling
files mid-review and gives Layer 2 the single-repo, single-tag, single-CI benefits from its first slice.

---

## 6. Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| **History lost / blame broken** in the merge | Use `git subtree`/`git-filter-repo` (never flat copy); verify `git log --follow` on a sample file after each step | The source repos are untouched until the very end — keep them as the record of truth until the monorepo is proven. |
| **Installer / compose path drift** → broken fresh install | Gate every step on a fresh install + conformance; change paths in the same commit as the move | `git revert` the step's single commit (atomic now — the whole point); source repos still buildable. |
| **Image build breakage** from moved build contexts | Build + boot all images on the branch before merge; keep old tags published so a rollback compose still pulls | Point compose back at the last-known-good pinned tags (the current hand-pins, preserved). |
| **Secrets accidentally committed** during the move | The merged `.gitignore` excludes `*.env`, `init.json`, `*.pem`/`*.key`, `.filestore-data/`, conformance `.creds.json`/`results/` **before** the first move; run `git status` + a secret-scan pre-commit on each step | n/a — prevention, not recovery. |
| **ADR-0130 not yet written** → `gateways/` tier undefined | Author ADR-0130 (north/south-per-gateway) **before** step 5; until then leave `services/` in place | Skip step 5; the rest of the restructure does not depend on it. |
| **In-flight branches on the old repos** collide with the move | Freeze feature work on the source repos during the window; land or shelve the five open branches first | The source repos remain the fallback; resume there if the monorepo is abandoned. |
| **CODEOWNERS too strict** blocks routine work | Start permissive (stewards as reviewers, not hard blocks); tighten `core/authz`, `core/identity`, `constitution` after the team adjusts | Loosen or remove `CODEOWNERS` entries — config-only, instant. |

**Whole-proposal rollback:** nothing is executed by this document. If the restructure is started and then
abandoned, the eight source repos are left intact until the final cut-over, so the fallback is simply to keep
developing in them and delete the monorepo branch.

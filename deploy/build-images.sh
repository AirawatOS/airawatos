#!/usr/bin/env bash
# Build every AirawatOS image FROM GIT ONLY (slice-1h, DEBT-B101 / re-review R2-5).
#
# Each repository's COMMITTED HEAD is exported with `git archive` into a scratch workspace, so nothing untracked
# (gitignored users files, local dist/ or egg-info, .env, credentials) can reach an image. Refuses a dirty tree unless
# ALLOW_DIRTY=1 (the archive would then not match what is on disk). Records, per image, every repository SHA that went
# into it and the resulting image id in deploy/local-dev/IMAGES.lock.json.
#   deploy/build-images.sh [tag]        (default tag: 1h)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-1h}"
WS="$(mktemp -d "${TMPDIR:-/tmp}/aos-build.XXXXXX")"; trap 'rm -rf "$WS"' EXIT
_export() {   # name dir → prints the repo HEAD sha; exports HEAD into $WS/ws/<dir>
  local name="$1" dir="$ROOT/$2"
  if [ -n "$(git -C "$dir" status --porcelain --untracked-files=no)" ] && [ "${ALLOW_DIRTY:-0}" != 1 ]; then
    echo "✗ $name has uncommitted changes — commit first (images are built from git only)" >&2; return 1
  fi
  mkdir -p "$WS/ws/$2"; git -C "$dir" archive HEAD | tar -x -C "$WS/ws/$2"
  git -C "$dir" rev-parse HEAD
}
S_ROOT="$(_export root .)"; S_PS="$(_export platform-spec platform-spec)"; S_K="$(_export kernel kernel)"
S_N="$(_export network network)"; S_C="$(_export components components)"
echo "▶ building from git: root@${S_ROOT:0:10} platform-spec@${S_PS:0:10} kernel@${S_K:0:10} network@${S_N:0:10} components@${S_C:0:10}"
B=(docker buildx build --builder "${AOS_BUILDER:-$(docker context show)}" --load --provenance=false)   # the context builder: no builder container (F3-3)
"${B[@]}" -f "$WS/ws/platform-spec/Dockerfile.reference" --build-arg GIT_SHA="$S_PS" \
  -t "manishsv/airawatos-reference:$TAG" "$WS/ws"
for svc in kernel network; do
  rev="$S_K"; [ "$svc" = network ] && rev="$S_N"
  "${B[@]}" -f "$WS/ws/$svc/deploy/Dockerfile" --build-arg GIT_SHA="$rev" \
    --build-context runtime="$WS/ws/deploy/runtime" --build-context pspec="$WS/ws/platform-spec/reference" \
    -t "manishsv/airawatos-$svc:$TAG" "$WS/ws/$svc"
done
# DEV-ONLY: the stub model provider (model-gateway south-side contract) — its own image, never shipped; only the
# local-dev stack runs it, and it refuses AIRAWAT_ENV=production.
"${B[@]}" -f "$WS/ws/deploy/local-dev/devstub/Dockerfile" --build-arg GIT_SHA="$S_ROOT" \
  -t "manishsv/airawatos-devstub:$TAG" "$WS/ws/deploy/local-dev/devstub"
python3 - "$TAG" "$S_ROOT" "$S_PS" "$S_K" "$S_N" "$S_C" <<'PY'
# Layer 1 merge: the TRACKED lock (IMAGES.lock.json) holds only the PINNED INPUTS a build must reproduce — the Dockerfile,
# the base, the installed OS package set (the Python set is the repo's requirements lock). Machine-specific facts of THIS
# build (image ids, source SHAs, date, platform) go to the UNTRACKED IMAGES.built.json, for information only. So building
# from main never dirties the tree; the lock changes only when an input really changes, and then only with
# AOS_RECORD_LOCK=1 (a deliberate, reviewed change in the same pull request).
import json, os, subprocess, sys, time
tag, root, ps, k, n, c = sys.argv[1:7]
def iid(t): return subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", t], capture_output=True, text=True).stdout.strip()
def plat(t): return subprocess.run(["docker", "image", "inspect", "-f", "{{.Os}}/{{.Architecture}}", t], capture_output=True, text=True).stdout.strip()
base = "python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535"
LOCK, BUILT = "deploy/local-dev/IMAGES.lock.json", "deploy/local-dev/IMAGES.built.json"
old = json.load(open(LOCK)) if os.path.exists(LOCK) else {"images": {}}
inputs, info = {}, {}
for name, df, rev, srcs in (("reference", "platform-spec/Dockerfile.reference", ps, {"root": root, "platform-spec": ps, "components": c}),
                            ("kernel", "kernel/deploy/Dockerfile", k, {"root": root, "platform-spec": ps, "kernel": k}),
                            ("network", "network/deploy/Dockerfile", n, {"root": root, "platform-spec": ps, "network": n}),
                            ("devstub", "deploy/local-dev/devstub/Dockerfile", root, {"root": root})):   # DEV-ONLY
    t = "manishsv/airawatos-%s:%s" % (name, tag)
    osp = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "sh", t, "-c",
                          "dpkg-query -W -f='${Package}=${Version}\\n'"], capture_output=True, text=True).stdout.split()
    inputs[t] = {"dockerfile": df, "base": base, "os_packages": sorted(osp)}
    if name == "devstub":
        inputs[t]["dev_only"] = True          # never shipped: images_test + the banned DEV_STUB_IN_PROD check hold it to local-dev
    info[t] = {"image_id": iid(t), "git_revision": rev, "sources": srcs, "platform": plat(t), "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
json.dump({"_meta": {"note": "UNTRACKED, informational: the last LOCAL build (image ids are machine-specific)."}, "images": info},
          open(BUILT, "w"), indent=1)
_K = ("dockerfile", "base", "os_packages", "dev_only")
same = all({kk: (old["images"].get(t) or {}).get(kk) for kk in _K if kk in v or (old["images"].get(t) or {}).get(kk)} == v for t, v in inputs.items())
if same:
    print("  ✓ pinned inputs unchanged — IMAGES.lock.json not rewritten (this build's ids: %s)" % BUILT)
elif os.environ.get("AOS_RECORD_LOCK") == "1":
    json.dump({"_meta": {"note": "Layer 1 merge: the PINNED INPUTS every build of these tags must reproduce — Dockerfile, base, "
                         "installed OS packages (Python: the repo's requirements lock). verify/images_test.py checks image CONTENT "
                         "against these and against the git HEADs; machine-specific ids live in the untracked IMAGES.built.json.",
                         "amd64": "native amd64 build still required (DEBT-B114, pre-production)."}, "images": inputs},
              open(LOCK, "w"), indent=1)
    print("  ✓ IMAGES.lock.json RECORDED (AOS_RECORD_LOCK=1) — commit it with the change that altered the inputs")
else:
    ch = [t for t, v in inputs.items() if {kk: (old["images"].get(t) or {}).get(kk) for kk in _K if kk in v or (old["images"].get(t) or {}).get(kk)} != v]
    print("  ✗ the pinned inputs of %s differ from IMAGES.lock.json — if intended, rebuild with AOS_RECORD_LOCK=1 and commit the lock" % ch)
for t, r in info.items(): print("  ✓ %-38s %s  (%s)" % (t, r["image_id"][:19], ", ".join("%s@%s" % (a, b[:10]) for a, b in r["sources"].items())))
PY

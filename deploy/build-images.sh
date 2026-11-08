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
B=(docker buildx build --load --provenance=false)
"${B[@]}" -f "$WS/ws/platform-spec/Dockerfile.reference" --build-arg GIT_SHA="$S_PS" \
  -t "manishsv/airawatos-reference:$TAG" "$WS/ws"
for svc in kernel network; do
  rev="$S_K"; [ "$svc" = network ] && rev="$S_N"
  "${B[@]}" -f "$WS/ws/$svc/deploy/Dockerfile" --build-arg GIT_SHA="$rev" \
    --build-context runtime="$WS/ws/deploy/runtime" --build-context pspec="$WS/ws/platform-spec/reference" \
    -t "manishsv/airawatos-$svc:$TAG" "$WS/ws/$svc"
done
python3 - "$TAG" "$S_ROOT" "$S_PS" "$S_K" "$S_N" "$S_C" <<'PY'
import json, subprocess, sys, time
tag, root, ps, k, n, c = sys.argv[1:7]
def iid(t): return subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", t], capture_output=True, text=True).stdout.strip()
def plat(t): return subprocess.run(["docker", "image", "inspect", "-f", "{{.Os}}/{{.Architecture}}", t], capture_output=True, text=True).stdout.strip()
base = "python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535"
imgs = {}
for name, df, ctx, rev, srcs in (("reference", "platform-spec/Dockerfile.reference", "git archive (workspace)", ps,
                                  {"root": root, "platform-spec": ps, "components": c}),
                                 ("kernel", "kernel/deploy/Dockerfile", "git archive (kernel)", k, {"root": root, "platform-spec": ps, "kernel": k}),
                                 ("network", "network/deploy/Dockerfile", "git archive (network)", n, {"root": root, "platform-spec": ps, "network": n})):
    t = "manishsv/airawatos-%s:%s" % (name, tag)
    imgs[t] = {"dockerfile": df, "context": ctx, "git_revision": rev, "sources": srcs, "image_id": iid(t),
               "platform": plat(t), "base": base, "built": time.strftime("%Y-%m-%d")}
json.dump({"_meta": {"note": "slice-1h (DEBT-B101): built FROM GIT ONLY by deploy/build-images.sh (git archive of each repo's "
                     "committed HEAD; nothing untracked can enter). image_id = local image config digest. verify/images_test.py "
                     "checks the tag, the running containers and that /app equals the git tree.",
                     "amd64": "native amd64 build still required (DEBT-B114, pre-production)."},
           "images": imgs}, open("deploy/local-dev/IMAGES.lock.json", "w"), indent=1)
for t, r in imgs.items(): print("  ✓ %-38s %s  (%s)" % (t, r["image_id"][:19], ", ".join("%s@%s" % (a, b[:10]) for a, b in r["sources"].items())))
PY

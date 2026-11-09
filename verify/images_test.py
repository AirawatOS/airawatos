#!/usr/bin/env python3
"""Every image is rebuildable from the repositories and pinned (slice-1g, DEBT-B80/B94 / review R2–R3).

  1. Every Dockerfile that builds an Airawat image (platform-spec/Dockerfile.reference, kernel/deploy/Dockerfile,
     network/deploy/Dockerfile) starts FROM a DIGEST-pinned base and installs Python dependencies only from a lock
     file in which EVERY line is pinned with `==` (no ranges, no bare names), and pins its pip tooling.
  2. Every image in deploy/local-dev/docker-compose.dev.yml is either digest-pinned (third-party) or recorded in
     deploy/local-dev/IMAGES.lock.json (built from the repositories: Dockerfile, git revision, image id).
  3. The local image behind each recorded tag IS the recorded image id, and its OCI revision label is the recorded
     git revision — and every RUNNING container of the stack runs the recorded image.
Exit 1 on any finding.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, "deploy/local-dev/IMAGES.lock.json")
DOCKERFILES = {"platform-spec/Dockerfile.reference": "platform-spec/requirements.reference.lock",
               "kernel/deploy/Dockerfile": "kernel/deploy/requirements.lock",
               "network/deploy/Dockerfile": "network/deploy/requirements.lock"}
bad = []


def check(ok, msg):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        bad.append(msg)


print("▶ images test (B80/B94): pinned, recorded, running what was recorded")
for df, lock in DOCKERFILES.items():
    txt = open(os.path.join(ROOT, df)).read() if os.path.exists(os.path.join(ROOT, df)) else ""
    froms = re.findall(r"^FROM\s+(\S+)", re.sub(r"\$\{BASE\}", "BASE", txt), re.M)
    base = re.search(r"^FROM (python:[^\s]+)$", txt, re.M) or re.search(r"base\.name=\"([^\"]+)\"", txt)
    check(bool(txt) and all("@sha256:" in f or f == "BASE" for f in froms) and "@sha256:" in txt,
          f"{df}: base pinned by digest ({froms})")
    lp = os.path.join(ROOT, lock)
    lines = [l.strip() for l in open(lp)] if os.path.exists(lp) else []
    unpinned = [l for l in lines if l and not l.startswith("#") and not re.match(r"^[A-Za-z0-9_.\[\]-]+==[^\s;]+", l)]
    check(bool(lines) and not unpinned and os.path.basename(lock) in txt,
          f"{df}: installs from {lock}, every dependency pinned (unpinned: {unpinned[:5]})")
    segs = [g.strip() for g in re.split(r"&&|\n|;", txt.replace("\\\n", " ")) if "pip install" in g]
    tools = [(m.group(1), m.group(2) or "") for g in segs for m in
             re.finditer(r"(?<![\w./-])(pip|setuptools|wheel)(==[^\s]+)?(?=\s|$)", g.split("pip install", 1)[1])]
    check(all(v.startswith("==") for _, v in tools), f"{df}: pip tooling pinned ({tools})")
    # slice-1h (R7-3): EVERY pip install installs only pinned `name==ver` or `-r <the lock>` — an extra unpinned install fails
    loose = []
    for g in segs:
        toks = g.split("pip install", 1)[1].split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in ("-r", "--requirement"):
                if not toks[i + 1:i + 2] or not toks[i + 1].endswith(".lock"):
                    loose.append("-r " + "".join(toks[i + 1:i + 2]))
                i += 2; continue
            if not t.startswith("-") and t not in ("&&", "\\") and not re.match(r"^[A-Za-z0-9_.\[\]-]+==\S+$", t):
                loose.append(t)
            i += 1
    check(not loose, f"{df}: every pip install is pinned or from the lock (unpinned: {loose[:5]})")

rec = json.load(open(LOCK)) if os.path.exists(LOCK) else {"images": {}}
compose = open(os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")).read()
for img in sorted(set(re.findall(r"^\s*image:\s*([^\s#]+)", compose, re.M))):
    if "@sha256:" in img:
        check(True, f"{img.split('@')[0]}: third-party, digest-pinned"); continue
    r = rec["images"].get(img)
    check(bool(r), f"{img}: recorded in IMAGES.lock.json (built from {r and r.get('dockerfile')})")
    if not r:
        continue
    iid = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", img], capture_output=True, text=True).stdout.strip()
    lab = subprocess.run(["docker", "image", "inspect", "-f", "{{index .Config.Labels \"org.opencontainers.image.revision\"}}", img],
                         capture_output=True, text=True).stdout.strip()
    check(iid == r["image_id"], f"{img}: local image id {iid[:19]} == recorded {r['image_id'][:19]}")
    check(lab == r["git_revision"], f"{img}: OCI revision label {lab[:10]} == recorded {r['git_revision'][:10]}")
# slice-1h (DEBT-B101, re-review R2-5): the reference image's /app is EXACTLY the git tree at the recorded commits —
# no untracked file (the gitignored identity-users.json, local dist/ and egg-info used to ride in)
STRIP = ("apps", "drivers", "engines", "skills", "experts", "pipelines", "providers", "solutions", "diagnostics", "runtimes")
for img, r in rec["images"].items():
    if "airawatos-reference" not in img:
        continue
    srcs = r.get("sources") or {}
    check(all(k in srcs for k in ("root", "platform-spec", "components")), f"{img}: every source repository SHA recorded ({sorted(srcs)})")
    if not all(k in srcs for k in ("platform-spec", "components")):
        continue
    def tree(repo, sha, sub, dest):   # path -> git blob id (content identity)
        out = subprocess.run(["git", "-C", os.path.join(ROOT, repo), "ls-tree", "-r", sha] + ([sub] if sub else []),
                             capture_output=True, text=True).stdout.splitlines()
        res = {}
        for l in out:
            meta, path = l.split("\t", 1)
            res[dest + path[len(sub):]] = meta.split()[2]
        return res
    want = tree("platform-spec", srcs["platform-spec"], "reference", "reference")
    want.update({f: h for f, h in tree("components", srcs["components"], "", "components/").items() if f.split("/")[1] not in STRIP})
    _H = ("import hashlib,os\nfor d in ('reference','components'):\n for r,_,fs in os.walk('/app/'+d):\n  if '__pycache__' in r: continue\n"
          "  for f in fs:\n   p=os.path.join(r,f); b=open(p,'rb').read()\n   print(hashlib.sha1(b'blob %d\\0'%len(b)+b).hexdigest(), os.path.relpath(p,'/app'))")
    got = dict(reversed(l.split(" ", 1)) for l in subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", img, "-c", _H],
                                                                  capture_output=True, text=True).stdout.splitlines() if " " in l)
    extra, missing = sorted(set(got) - set(want)), sorted(set(want) - set(got))
    changed = sorted(f for f in set(got) & set(want) if got[f] != want[f])
    check(bool(got) and not extra and not missing and not changed,
          f"{img}: /app equals the git tree BY CONTENT ({len(got)} files; untracked: {extra[:4]}; missing: {missing[:4]}; content differs: {changed[:4]})")
# slice-1i (DEBT-B133): check what IS INSTALLED, not how the Dockerfile spells the install — every image's
# pip freeze --all must EQUAL its lock + the pinned tooling, and its OS packages must EQUAL the list recorded at build.
LOCKS = {"reference": "platform-spec/requirements.reference.lock", "kernel": "kernel/deploy/requirements.lock",
         "network": "network/deploy/requirements.lock"}
for img, r in rec["images"].items():
    kind = next((k for k in LOCKS if "airawatos-%s:" % k in img), None)
    test_img = os.environ.get("IMG_OVERRIDE_" + kind.upper(), img) if kind else img
    lock = [l.strip() for l in open(os.path.join(ROOT, LOCKS[kind])) if l.strip() and not l.startswith("#")] if kind else []
    df = open(os.path.join(ROOT, r["dockerfile"])).read()
    tooling = set(re.findall(r"\b((?:pip|setuptools|wheel)==[^\s&]+)", df))
    want_py = set(lock) | tooling
    got_py = set(subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "pip", test_img, "freeze", "--all"],
                                capture_output=True, text=True).stdout.split())
    check(bool(got_py) and got_py == want_py, f"{test_img}: installed Python packages EQUAL the lock + pinned tooling "
          f"({len(got_py)} installed; not in lock: {sorted(got_py - want_py)[:5]}; missing: {sorted(want_py - got_py)[:5]})")
    got_os = set(subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "sh", test_img, "-c",
                                 "dpkg-query -W -f='${Package}=${Version}\\n'"], capture_output=True, text=True).stdout.split())
    want_os = set(r.get("os_packages") or [])
    check(bool(want_os) and got_os == want_os, f"{test_img}: installed OS packages EQUAL the build record "
          f"({len(got_os)} installed; unrecorded: {sorted(got_os - want_os)[:5]}; missing: {sorted(want_os - got_os)[:5]})")
ps = subprocess.run(["docker", "ps", "--filter", "name=airawat-ld-", "--format", "{{.Names}}\t{{.Image}}"], capture_output=True, text=True).stdout
for line in ps.splitlines():
    name, img = line.split("\t")
    r = rec["images"].get(img)
    if not r:
        continue
    run_id = subprocess.run(["docker", "inspect", "-f", "{{.Image}}", name], capture_output=True, text=True).stdout.strip()
    check(run_id == r["image_id"], f"{name} runs the recorded image ({run_id[:19]})")
print(("✗" if bad else "✓") + f" images test: {len(bad)} finding(s)")
sys.exit(1 if bad else 0)

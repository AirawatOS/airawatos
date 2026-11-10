#!/usr/bin/env python3
"""Every image is rebuildable from the repositories and pinned (slice-1g, DEBT-B80/B94 / review R2–R3).

  1. Every Dockerfile that builds an Airawat image (platform-spec/Dockerfile.reference, kernel/deploy/Dockerfile,
     network/deploy/Dockerfile) starts FROM a DIGEST-pinned base and installs Python dependencies only from a lock
     file in which EVERY line is pinned with `==` (no ranges, no bare names), and pins its pip tooling.
  2. Every image in deploy/local-dev/docker-compose.dev.yml is either digest-pinned (third-party) or has its pinned inputs
     recorded in deploy/local-dev/IMAGES.lock.json (Dockerfile, base, installed Python + OS package sets).
  3. Layer 1 merge — CONTENT, not machine ids: each image was built from the CURRENT HEAD (OCI revision label), every
     file of its code (/app, /opt/airawat) equals the git blob at the current HEADs (untracked / changed files fail),
     its installed Python packages EQUAL the lock + pinned tooling and its OS packages EQUAL the recorded set, and every
     RUNNING container runs the image behind its tag. Image ids are machine-specific and only informational
     (deploy/local-dev/IMAGES.built.json, untracked) — so a fresh build from main verifies without a lock commit.
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


print("▶ images test (B80/B94/B133): pinned inputs; image CONTENT vs git HEAD + lock; running what was verified")
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
# Layer 1 merge: the image is verified by its CONTENT against git and the pinned inputs — never by a machine-specific image
# id. The lock holds only what a build must reproduce (base, Dockerfile, the installed Python and OS package sets); the
# ids/dates of the last local build are informational (deploy/local-dev/IMAGES.built.json, untracked).
PRIMARY = {"reference": "platform-spec", "kernel": "kernel", "network": "network"}


def kind_of(img):
    return next((k for k in PRIMARY if "airawatos-%s:" % k in img), None)


def head(repo):
    return subprocess.run(["git", "-C", os.path.join(ROOT, repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def git_tree(repo, sub=""):
    """path (relative to `sub`) -> git blob id at the CURRENT HEAD of `repo`."""
    out = subprocess.run(["git", "-C", os.path.join(ROOT, repo), "ls-tree", "-r", "HEAD"] + ([sub] if sub else []),
                         capture_output=True, text=True).stdout.splitlines()
    res = {}
    for l in out:
        meta, path = l.split("\t", 1)
        res[path[len(sub):].lstrip("/") if sub else path] = meta.split()[2]
    return res


_HASH = ("import hashlib,os,sys\nfor top in sys.argv[1:]:\n for r,_,fs in os.walk(top):\n  if '__pycache__' in r: continue\n"
         "  for f in fs:\n   p=os.path.join(r,f); b=open(p,'rb').read()\n   print(hashlib.sha1(b'blob %d\\0'%len(b)+b).hexdigest(), p)")


def image_files(img, *tops):
    out = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", img, "-c", _HASH, *tops],
                         capture_output=True, text=True).stdout.splitlines()
    return dict(reversed(l.split(" ", 1)) for l in out if " " in l)


for img in sorted(set(re.findall(r"^\s*image:\s*([^\s#]+)", compose, re.M))):
    if "@sha256:" in img:
        check(True, f"{img.split('@')[0]}: third-party, digest-pinned"); continue
    r = rec["images"].get(img)
    check(bool(r), f"{img}: its pinned inputs are recorded in IMAGES.lock.json (Dockerfile {r and r.get('dockerfile')})")
    k = kind_of(img)
    if not r or not k:
        continue
    test_img = os.environ.get("IMG_OVERRIDE_" + k.upper(), img)
    lab = subprocess.run(["docker", "image", "inspect", "-f", "{{index .Config.Labels \"org.opencontainers.image.revision\"}}", test_img],
                         capture_output=True, text=True).stdout.strip()
    check(lab == head(PRIMARY[k]), f"{test_img}: built from the CURRENT {PRIMARY[k]} HEAD (revision label {lab[:10]} == HEAD {head(PRIMARY[k])[:10]})")
    # every file of the image's code equals the git blob at the current HEAD — untracked or changed files fail
    if k == "reference":
        STRIP = ("apps", "drivers", "engines", "skills", "experts", "pipelines", "providers", "solutions", "diagnostics", "runtimes")
        want = {"/app/reference/" + p: h for p, h in git_tree("platform-spec", "reference").items()}
        want.update({"/app/components/" + p: h for p, h in git_tree("components").items() if p.split("/")[0] not in STRIP})
        got = image_files(test_img, "/app/reference", "/app/components")
        exact = True
    else:
        repo = git_tree(PRIMARY[k])
        got = image_files(test_img, "/app")
        want = {}
        for path in got:
            rel = path[len("/app/"):]
            if rel == "requirements.lock":
                want[path] = repo.get("deploy/requirements.lock")
            elif rel == "gateflags.py":
                want[path] = git_tree("platform-spec", "reference").get("gateflags.py")
            else:
                want[path] = repo.get(rel)
        exact = False
    rt = git_tree(".", "deploy/runtime")
    want.update({"/opt/airawat/" + p: h for p, h in rt.items()})
    want["/opt/airawat/gateflags.py"] = git_tree("platform-spec", "reference").get("gateflags.py")
    got.update(image_files(test_img, "/opt/airawat"))
    untracked = sorted(p for p in got if want.get(p) is None)
    changed = sorted(p for p in got if want.get(p) is not None and got[p] != want[p])
    missing = sorted(p for p in want if p not in got and (exact or p.startswith("/opt/airawat/")))
    check(bool(got) and not untracked and not changed and not missing,
          f"{test_img}: code equals the git trees at the CURRENT HEADs BY CONTENT ({len(got)} files; untracked: {untracked[:3]}; "
          f"content differs: {changed[:3]}; missing: {missing[:3]})")
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
    if img not in rec["images"]:
        continue
    run_id = subprocess.run(["docker", "inspect", "-f", "{{.Image}}", name], capture_output=True, text=True).stdout.strip()
    tag_id = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", img], capture_output=True, text=True).stdout.strip()
    check(run_id == tag_id, f"{name} runs the image currently behind {img} (the one verified above)")
print(("✗" if bad else "✓") + f" images test: {len(bad)} finding(s)")
sys.exit(1 if bad else 0)

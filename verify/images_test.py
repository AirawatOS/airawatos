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

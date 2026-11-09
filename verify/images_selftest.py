#!/usr/bin/env python3
"""Mutation self-test of the image content check (slice-1i, DEBT-B133).

Builds throwaway images FROM the recorded kernel image, each adding software by a different route, and requires
verify/images_test.py (pointed at the throwaway via IMG_OVERRIDE_KERNEL) to FAIL on every one — whatever the spelling:
  1. the final review's case: `pip3 install requests`
  2. `python3 -m pip install idna==<other version>` (a pinned package silently changed)
  3. a wheel installed by path (`pip install /tmp/x.whl`) — no package name on the command line at all
  4. an OS package (`apt-get install`)
Then the unmutated image must PASS. Builds with the current context's built-in builder (no builder container).
Throwaway images are removed. Exit 1 on failure.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = json.load(open(os.path.join(ROOT, "deploy/local-dev/IMAGES.lock.json")))
BASE = next(t for t in LOCK["images"] if "airawatos-kernel:" in t)
BUILDER = os.environ.get("AOS_BUILDER") or subprocess.run(["docker", "context", "show"], capture_output=True, text=True).stdout.strip()
MUT = [
    ("pip3 install requests (final-review case)", "RUN pip3 install --no-cache-dir requests"),
    ("python3 -m pip changes a pinned version", "RUN python3 -m pip install --no-cache-dir --no-deps idna==3.10"),
    ("wheel installed by path", "RUN pip download --no-deps -d /tmp/w six==1.16.0 && pip install --no-cache-dir /tmp/w/*.whl"),
    ("OS package via apt", "RUN apt-get update && apt-get install -y --no-install-recommends less && rm -rf /var/lib/apt/lists/*"),
]


def images_test(tag=None):
    env = dict(os.environ)
    if tag:
        env["IMG_OVERRIDE_KERNEL"] = tag
    r = subprocess.run([sys.executable, os.path.join(ROOT, "verify/images_test.py")], capture_output=True, text=True, env=env)
    return r.returncode, [l for l in r.stdout.splitlines() if "✗" in l]


fails = []
print("▶ image content self-test (B133) — base %s" % BASE)
rc, _ = images_test()
print(("  ✓" if rc == 0 else "  ✗") + " baseline: the recorded images pass (exit %d)" % rc)
fails += [] if rc == 0 else ["baseline"]
for i, (name, run) in enumerate(MUT):
    tag = "aos-selftest/kernel:mut%d" % i
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "Dockerfile"), "w").write("FROM %s\nUSER 0\n%s\n" % (BASE, run))
        b = subprocess.run(["docker", "buildx", "build", "--builder", BUILDER, "--load", "-q", "-t", tag, td], capture_output=True, text=True)
    if b.returncode:
        print("  ✗ %s: throwaway build failed: %s" % (name, b.stderr.strip()[-160:])); fails.append(name); continue
    rc, lines = images_test(tag)
    subprocess.run(["docker", "image", "rm", "-f", tag], capture_output=True)
    caught = rc != 0 and any(tag in l for l in lines)
    print(("  ✓" if caught else "  ✗") + " %s → images test %s" % (name, ("FAILS: " + lines[0].strip()[:110]) if caught else "STAYED GREEN"))
    if not caught:
        fails.append(name)
print(("✗" if fails else "✓") + " image content self-test: %d of %d mutation(s) not caught" % (len(fails), len(MUT)))
sys.exit(1 if fails else 0)

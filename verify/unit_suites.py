#!/usr/bin/env python3
"""Every repository's OWN unit test suite, inside `make verify` (Layer 1 merge — a failing suite fails verification).

Until now `make verify` ran only the decision-function unit tests; the kernel's own pytest suite failed for a week
without anyone seeing it. This net runs, for EVERY repository, EVERY test file it tracks (discovered from git, so a
new test file is included automatically):
  kernel         pytest over tests/ (pytest.ini) + services/authz/test_decide.py
  network        every tracked test_*.py, as a script (each exits non-zero on failure)
  platform-spec  every tracked test_*.py, as a script
  components     every tracked test_*.py and _common/aos/selftest_*.py, as a script (PYTHONPATH=_common)
Each file runs inside that repository's OWN service image (the exact production dependencies), source mounted read-only,
no network, AIRAWAT_ENV=development. pytest for the kernel suite is pinned (PYTEST_PINS) and installed once into a cache
directory outside the image; the image itself is never modified.
A built-in self-test runs a deliberately failing test file through the same runner first and requires it to be reported
as FAILED, so the net cannot pass by never failing.
Exit 1 on any failure.
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")
PYTEST_PINS = ["pytest==9.2.0", "httpx==0.28.1"]
TOOLS = os.environ.get("AOS_UNIT_TOOLS", os.path.expanduser("~/.cache/airawat-verify/unit-tools-pytest-9.2.0"))


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def image(kind):
    for l in open(CF):
        m = re.match(r"\s*image:\s*(manishsv/airawatos-%s:\S+)" % kind, l)
        if m:
            return m.group(1)
    raise SystemExit("✗ no %s image in %s" % (kind, CF))


def tracked(repo, pattern):
    out = sh("git", "-C", os.path.join(ROOT, repo), "ls-files").stdout.split()
    return sorted(f for f in out if re.search(pattern, f) and "/.venv/" not in "/" + f and not f.startswith(".venv/"))


def run_in(img, repo_dir, workdir, cmd, extra_env=(), tools=False):
    a = ["docker", "run", "--rm", "--network", "none", "--user", "0:0", "-e", "AIRAWAT_ENV=development",
         "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", "%s:/src:ro" % repo_dir, "-w", workdir, "--entrypoint", "sh"]
    for e in extra_env:
        a += ["-e", e]
    if tools:
        a += ["-v", "%s:/unit-tools:ro" % TOOLS]
    r = subprocess.run(a + [img, "-c", cmd], capture_output=True, text=True, timeout=900)
    return r.returncode, (r.stdout + r.stderr)


def ensure_tools(img):
    if os.path.isdir(os.path.join(TOOLS, "pytest")):
        return True
    os.makedirs(TOOLS, exist_ok=True)
    r = sh("docker", "run", "--rm", "--user", "0:0", "-v", "%s:/t" % TOOLS, "--entrypoint", "pip", img,
           "install", "-q", "--no-cache-dir", "--target", "/t", *PYTEST_PINS)
    return r.returncode == 0 and os.path.isdir(os.path.join(TOOLS, "pytest"))


results = []


def record(name, rc, out):
    ok = rc == 0
    tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
    print(("  ✓ " if ok else "  ✗ ") + "%s — %s" % (name, tail[0][:140]), flush=True)
    results.append(ok)
    return ok


print("▶ unit suites of every repository (kernel, network, platform-spec, components)", flush=True)
REF, KER, NET = image("reference"), image("kernel"), image("network")

# self-test: a deliberately failing test file must be reported as FAILED by the same runner
with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, "test_must_fail.py"), "w").write("import sys\nprint('deliberate failure')\nsys.exit(1)\n")
    rc, _ = run_in(REF, td, "/src", "python test_must_fail.py")
    st = rc != 0
    print(("  ✓ " if st else "  ✗ ") + "self-test: a failing test file is reported as FAILED (exit %s)" % rc, flush=True)
    results.append(st)

# kernel: pytest suite + the decision-function unit tests
if not ensure_tools(KER):
    print("  ✗ could not install the pinned pytest tools into %s" % TOOLS); results.append(False)
else:
    kdir = os.path.join(ROOT, "kernel")
    prc, out = run_in(KER, kdir, "/src", "PYTHONPATH=/unit-tools python -m pytest -p no:cacheprovider -o addopts= 2>&1", tools=True)
    summary = ([l for l in out.splitlines() if re.search(r"\d+ (passed|failed)", l)] or ["(no summary)"])[-1]
    record("kernel pytest (tests/): %s" % summary.strip("= "), prc, out)
    record("kernel services/authz/test_decide.py", *run_in(KER, kdir, "/src", "python services/authz/test_decide.py"))

SUITES = [
    ("network", NET, r"(^|/)test_[^/]*\.py$", []),
    ("platform-spec", REF, r"(^|/)test_[^/]*\.py$", []),
    ("components", REF, r"(^|/)(test|selftest)_[^/]*\.py$", ["PYTHONPATH=/src/_common"]),
]
for repo, img, pat, env in SUITES:
    files = tracked(repo, pat)
    if not files:
        print("  ✗ %s: no test files discovered — refusing to pass an empty suite" % repo); results.append(False); continue
    for f in files:
        d, b = os.path.dirname(f), os.path.basename(f)
        record("%s/%s" % (repo, f), *run_in(img, os.path.join(ROOT, repo), "/src/" + d if d else "/src", "python " + b, env))

bad = results.count(False)
print(("✗" if bad else "✓") + " unit suites: %d of %d failed" % (bad, len(results)))
sys.exit(1 if bad else 0)

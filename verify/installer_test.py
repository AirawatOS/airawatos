#!/usr/bin/env python3
"""The installer never fails silently and never claims success after a failed phase (slice-1h, DEBT-B100 / R7-1, R3-8).

  1. PRE-FLIGHT on a clean host (fast, no stack): the installer's own host pre-flight lines (extracted from
     install.sh, run under its `set -Eeuo pipefail`) with a `docker` stub that reports NO published port at all — the
     clean-host case. They must complete. (The re-review's `make verify` died here: an empty `grep` killed the shell.)
  2. EVERY PHASE IS NAMED and every Python phase records failed writes: static checks that each phase banner sets
     _PHASE, the EXIT trap reports it, and no write helper swallows a non-2xx.
  3. FAULT INJECTION (live, --live): run the real installer with AOS_INSTALL_FAULT=<phase> (dev profile) and require a
     non-zero exit, a "✗ install FAILED in phase: <that phase>" line, and NO "install complete".
INSTALL=<path> tests another copy of install.sh (e.g. the pre-1h one). Exit 1 on any failure.
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.environ.get("INSTALL", os.path.join(ROOT, "deploy/installer/install.sh"))
src = open(INSTALL).read()
fails = []


def check(name, ok, detail=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (" — " + detail if detail else ""))
    if not ok:
        fails.append(name)


print("▶ installer test (B100): %s" % os.path.relpath(INSTALL, ROOT))
# 1. pre-flight lines on a clean host (no 0.0.0.0 publisher, Vault status without storage_type)
pf = [l for l in src.split("\n") if re.match(r"^\s*_(bad_ports|vstorage)=", l)]
with tempfile.TemporaryDirectory() as td:
    stub = os.path.join(td, "docker")
    open(stub, "w").write("#!/bin/sh\nexit 0\n")          # `docker ps` lists nothing: the clean host
    os.chmod(stub, 0o755)
    script = "set -Eeuo pipefail\n_vstatus=''\n" + "\n".join(pf) + "\necho PREFLIGHT-SURVIVED\n"
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env={**os.environ, "PATH": td + ":" + os.environ["PATH"]})
check("host pre-flight completes on a host with no 0.0.0.0 publisher", len(pf) == 2 and "PREFLIGHT-SURVIVED" in r.stdout,
      "lines found %d, exit %s" % (len(pf), r.returncode))
# 2. static: phase naming, loud EXIT trap, success only at the end, no swallowed write errors
banners = re.findall(r'^\s*(?:_PHASE="[^\n]*?; )?echo "── Phases? ', src, flags=re.M)
named = re.findall(r'^\s*_PHASE="[^\n]*echo "── Phases? ', src, flags=re.M)
check("every phase banner sets _PHASE", banners and len(named) == len(banners), "%d/%d" % (len(named), len(banners)))
check("an EXIT trap reports the failing phase", re.search(r"trap '[^']*install FAILED in phase: \$\{_PHASE\}", src) is not None)
check('"install complete" is printed only after _INSTALL_DONE=1 at the very end',
      len(re.findall(r"^[^#\n]*install complete", src, flags=re.M)) == 1 and re.search(r"_INSTALL_DONE=1\necho \"✓ install complete", src) is not None)
swallow = re.findall(r"except urllib\.error\.HTTPError as e: return e\b", src)
check("no write helper swallows a non-2xx (each records it in _FAILS)", not swallow and "_FAILS.append" in src, "%d swallowing helpers" % len(swallow))
check("a missing Phase-8 network record fails the phase", "localdev network not found — skip" not in src)

# 3. live fault injection
if "--live" in sys.argv:
    for phase in ("Phase 1a", "Phase 8"):
        r = subprocess.run(["bash", INSTALL, "--profile", "dev"], capture_output=True, text=True,
                           env={**os.environ, "AOS_INSTALL_FAULT": phase}, cwd=os.path.dirname(INSTALL), timeout=1800)
        out = r.stdout + r.stderr
        m = re.search(r"✗ install FAILED in phase: (.*?) \(exit", out)
        check("a fault in %s → non-zero exit, phase named, no 'install complete'" % phase,
              r.returncode != 0 and bool(m) and m.group(1).startswith(phase) and "install complete" not in out,
              "exit %s, reported phase %r" % (r.returncode, m and m.group(1)))
print(("✗" if fails else "✓") + " installer test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

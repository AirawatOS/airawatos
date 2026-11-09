#!/usr/bin/env python3
"""The installer never fails silently and never claims success after a failed phase (slice-1h, DEBT-B100 / R7-1, R3-8).

  1. PRE-FLIGHT on a clean host (fast, no stack): the installer's own host pre-flight lines (extracted from
     install.sh, run under its `set -Eeuo pipefail`) with a `docker` stub that reports NO published port at all — the
     clean-host case. They must complete. (The re-review's `make verify` died here: an empty `grep` killed the shell.)
  2. EVERY PHASE IS NAMED and every Python phase records failed writes: static checks that each phase banner sets
     _PHASE, the EXIT trap reports it, and no write helper swallows a non-2xx.
  3. FAULT INJECTION (live, --live): run the real installer with AOS_INSTALL_FAULT_WRITE=<phase>|<url> (dev profile) and
     require a non-zero exit, a "✗ install FAILED in phase: <that phase>" line, and NO "install complete".
  slice-1j (DEBT-B141): the write guard must SURVIVE CONTAINER RECREATION and FAIL CLOSED when it is absent —
     static: XNET/XAPP exec through install-guard/run, which is baked into the images; nothing is copied into a container;
     live: (a) the conditions review's case — app-host RECREATED right before the shelf step and the shelf login of
     localdev-network failed → the install fails naming Phase 1c; (b) the same for the localdev-operator shelf login;
     (c) the guard made unloadable (AOS_INSTALL_TEST_GUARD_DIR=a directory without it) → the very first guarded helper
     refuses and the install fails naming its phase.
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
def _fn(f):
    m = re.search(r"^%s\(\)\s*\{(.*?)\}\s*$" % f, src, re.M | re.S)
    return m.group(1) if m else ""
check("exec helpers (XNET, XAPP) run through install-guard/run, which refuses unless the guard is active (B141)",
      all("_GUARD_RUN" in _fn(f) for f in ("XNET", "XAPP")) and "/opt/airawat/install-guard/run" in src,
      "through run: %s" % [f for f in ("XNET", "XAPP") if "_GUARD_RUN" in _fn(f)])
check("one-off helpers (XRUNNET, XRUNKERN) get the guard MOUNTED from outside on each run",
      all("sitecustomize.py:ro" in _fn(f) and "_GUARD_ENV" in _fn(f) for f in ("XRUNNET", "XRUNKERN")))
check("nothing copies the guard INTO a running container (a recreate would remove it)",
      not re.search(r"^[^#\n]*(COMPOSE|docker) cp [^\n]*(guard|sitecustomize)", src, re.M))
_RUN = os.path.join(ROOT, "deploy/runtime/install-guard/run")
check("install-guard/run is in deploy/runtime (baked into every image at /opt/airawat) and checks the guard's marker",
      os.path.exists(_RUN) and "AOS_INSTALL_WRITE_GUARD" in open(_RUN).read() and "exit 97" in open(_RUN).read())
check("a missing Phase-8 network record fails the phase", "localdev network not found — skip" not in src)

# 3. live fault injection
if "--live" in sys.argv:
    # slice-1h (R7-6): fault runs start from an EMPTY slate — an installed stack has scrubbed its admin bootstrap password,
    # so a re-install would stop before the phase under test. The fresh-install net that follows rebuilds the stack.
    _C = ["docker", "compose", "-p", "airawatos-localdev", "--project-directory", os.path.join(ROOT, "deploy/local-dev"),
          "-f", os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")]
    # slice-1i (DEBT-B135): faults INSIDE real writes (the write guard fails the first matching write of that phase) — not at
    # phase banners. The final review's case: the Phase-1 shelf step's failed login was swallowed and the install completed.
    # the shelf step (seed_base_os MODE=shelf — the final review's case) runs inside Phase 1c's span
    # slice-1j (DEBT-B141): (name, phase, env, must-see) — the shelf step runs in app-host AFTER its recreate
    LIVE = [
        ("a failed WRITE (/login) inside Phase 1c", "Phase 1c", {"AOS_INSTALL_FAULT_WRITE": "Phase 1c|/login"}, "INJECTED"),
        ("a failed WRITE (/set-password) inside Phase 7", "Phase 7 ", {"AOS_INSTALL_FAULT_WRITE": "Phase 7 |/set-password"}, "INJECTED"),
        ("a failed WRITE (/v1/registry/objects) inside Phase 8", "Phase 8", {"AOS_INSTALL_FAULT_WRITE": "Phase 8|/v1/registry/objects"}, "INJECTED"),
        ("app-host RECREATED before the shelf step + the localdev-network shelf login fails (conditions-review case)", "Phase 1c",
         {"AOS_INSTALL_TEST_RECREATE": "MODE=shelf", "AOS_INSTALL_FAULT_WRITE": "Phase 1c|/realms/localdev-network/login"}, "INJECTED"),
        ("app-host RECREATED before the shelf step + the localdev-operator shelf login fails", "Phase 1c",
         {"AOS_INSTALL_TEST_RECREATE": "MODE=shelf", "AOS_INSTALL_FAULT_WRITE": "Phase 1c|/realms/localdev-operator/login"}, "INJECTED"),
        ("the write guard cannot load (a directory without it) → the first guarded helper REFUSES", "",
         {"AOS_INSTALL_TEST_GUARD_DIR": "/nonexistent-guard-dir"}, "write guard NOT ACTIVE"),
    ]
    only = os.environ.get("LIVE_ONLY", "")
    for name, phase, env, must in LIVE:
        if only and only not in name:
            continue
        subprocess.run(_C + ["down", "-v", "--remove-orphans"], capture_output=True)
        r = subprocess.run(["bash", INSTALL, "--profile", "dev"], capture_output=True, text=True,
                           env={**os.environ, **env}, cwd=os.path.dirname(INSTALL), timeout=1800)
        out = r.stdout + r.stderr
        m = re.search(r"✗ install FAILED in phase: (.*?) \(exit", out)
        check("%s → non-zero exit, %s named, no 'install complete'" % (name, phase.strip() or "the phase"),
              r.returncode != 0 and bool(m) and m.group(1).startswith(phase) and "install complete" not in out and must in out,
              "exit %s, reported phase %r, %r seen: %s" % (r.returncode, m and m.group(1)[:50], must, must in out))
print(("✗" if fails else "✓") + " installer test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

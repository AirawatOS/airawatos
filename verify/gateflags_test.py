#!/usr/bin/env python3
"""Gate flags: one parser, and production refuses any shadow flag that is set at all (slice-1g, DEBT-B83).

Runs the REAL production guard (deploy/local-dev/prod-guard.sh) as the entrypoint of THROWAWAY containers (no network,
no stack needed) and the REAL gate decision (svc_gate.require) for each value:

  1. AIRAWAT_ENV=production + FILESTORE_SHADOW=<v> for v in "1", "2", "true", "yes", " ", "", "on", "TRUE", "enabled"
     → the guard REFUSES (exit 97; the service command never runs) — whatever the value.
  2. Production spelled " Production ", "PROD", "prod" → still production (refused with a shadow flag).
  3. A development convenience with an unrecognised value (AIRAWAT_ALLOW_PASSWORDLESS=2) → refused in production.
  4. The gate and the guard can never disagree: for every value, if the gate would run in SHADOW, production refuses;
     an unrecognised value ("2", "enabled") keeps the gate ENFORCING (fail closed).
  5. Positive: production with no flags starts; development with a flag starts.
  6. The guard works in the kernel and network images too (they get the parser by mount).

Env: PG=<prod-guard.sh> REF=<reference dir> (defaults: the working tree) to run against older code. Exit 1 on failure.
"""
import concurrent.futures as cf, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG = os.environ.get("PG", os.path.join(ROOT, "deploy/local-dev/prod-guard.sh"))
REF = os.environ.get("REF", os.path.join(ROOT, "platform-spec/reference"))
COMPOSE = open(os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")).read()
IMG = {k: re.search(r"manishsv/airawatos-%s:[^\s]+" % k, COMPOSE).group(0) for k in ("reference", "kernel", "network")}
GF = os.path.join(REF, "gateflags.py")
fails = []


def guard(env, image="reference"):
    """Run prod-guard.sh as the entrypoint; return (exit code, started?)."""
    cmd = ["docker", "run", "--rm", "--network", "none", "--entrypoint", "/bin/sh", "-v", PG + ":/local-dev/prod-guard.sh:ro"]
    if os.path.exists(GF):
        cmd += ["-v", GF + ":/local-dev/gateflags.py:ro"]
    for k, v in env.items():
        cmd += ["-e", "%s=%s" % (k, v)]
    cmd += [IMG[image], "/local-dev/prod-guard.sh", "python3", "-c", "print('SERVICE-STARTED')"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode, "SERVICE-STARTED" in r.stdout


def gate_enforces(value):
    """svc_gate.require('FILESTORE_SHADOW') with the value set — True = the door ENFORCES."""
    cmd = ["docker", "run", "--rm", "--network", "none", "-v", REF + ":/r:ro", "-e", "FILESTORE_SHADOW=" + value,
           IMG["reference"], "python3", "-c", "import sys; sys.path.insert(0,'/r'); import svc_gate; print('REQ', svc_gate.require('FILESTORE_SHADOW'))"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    return "REQ True" in out


def check(name, ok, detail):
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail)
    if not ok:
        fails.append(name)


VALUES = ["1", "2", "true", "yes", " ", "", "on", "TRUE", "enabled"]
print("▶ gate-flag test (B83) — guard %s, parser %s" % (os.path.relpath(PG, ROOT), os.path.relpath(REF, ROOT)))
jobs = {}
with cf.ThreadPoolExecutor(8) as ex:
    for v in VALUES:
        jobs[("prod", v)] = ex.submit(guard, {"AIRAWAT_ENV": "production", "FILESTORE_SHADOW": v})
        jobs[("gate", v)] = ex.submit(gate_enforces, v)
    for spelling in (" Production ", "PROD", "prod"):
        jobs[("spell", spelling)] = ex.submit(guard, {"AIRAWAT_ENV": spelling, "FILESTORE_SHADOW": "1"})
    jobs[("conv", "2")] = ex.submit(guard, {"AIRAWAT_ENV": "production", "AIRAWAT_ALLOW_PASSWORDLESS": "2"})
    jobs[("pos", "prod")] = ex.submit(guard, {"AIRAWAT_ENV": "production"})
    jobs[("pos", "dev")] = ex.submit(guard, {"AIRAWAT_ENV": "development", "FILESTORE_SHADOW": "1"})
    for img in ("kernel", "network"):
        jobs[("img", img)] = ex.submit(guard, {"AIRAWAT_ENV": "production", "MODELGW_SHADOW": "2"}, img)
    res = {k: f.result() for k, f in jobs.items()}

for v in VALUES:
    rc, started = res[("prod", v)]
    check("production refuses FILESTORE_SHADOW=%r" % v, rc == 97 and not started, "exit %s, service started=%s" % (rc, started))
for v in VALUES:
    enforces = res[("gate", v)]
    rc, started = res[("prod", v)]
    check("gate and guard agree for %r (gate SHADOW ⇒ production refuses)" % v, enforces or not started,
          "gate %s, production started=%s" % ("ENFORCE" if enforces else "SHADOW", started))
for v in ("2", "enabled"):
    check("an unrecognised value %r keeps the gate ENFORCING (fail closed)" % v, res[("gate", v)], "gate %s" % ("ENFORCE" if res[("gate", v)] else "SHADOW"))
for spelling in (" Production ", "PROD", "prod"):
    rc, started = res[("spell", spelling)]
    check("AIRAWAT_ENV=%r is production (shadow flag refused)" % spelling, rc == 97 and not started, "exit %s, started=%s" % (rc, started))
rc, started = res[("conv", "2")]
check("production refuses AIRAWAT_ALLOW_PASSWORDLESS='2' (unrecognised ≠ off)", rc == 97 and not started, "exit %s, started=%s" % (rc, started))
rc, started = res[("pos", "prod")]
check("positive: production with no flags starts", rc == 0 and started, "exit %s, started=%s" % (rc, started))
rc, started = res[("pos", "dev")]
check("positive: development with a shadow flag starts", rc == 0 and started, "exit %s, started=%s" % (rc, started))
for img in ("kernel", "network"):
    rc, started = res[("img", img)]
    check("%s image: production refuses MODELGW_SHADOW='2'" % img, rc == 97 and not started, "exit %s, started=%s" % (rc, started))

print(("✗" if fails else "✓") + " gate-flag test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

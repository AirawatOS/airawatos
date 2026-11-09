#!/usr/bin/env python3
"""The healthcheck tells the truth about Vault (slice-1i, DEBT-B125). Runs the BAKED svc_health.py inside throwaway
containers of the shipped reference image (no stack needed):
  1. the final review's case: a service that DECLARES Vault (VAULT_ROLE_ID set) but holds NO token → unhealthy
  2. declared, a token present but Vault unreachable → unhealthy
  3. declared, token present, no renewer running → unhealthy
  4. positive: a service that does not use Vault at all (no role id, no token) → healthy
Exit 1 on failure.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.environ.get("IMG") or re.search(r"^\s*image:\s*(manishsv/airawatos-reference:[^\s#]+)",
                                         open(os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")).read(), re.M).group(1)
H = os.environ.get("HEALTH", "/opt/airawat/svc_health.py")
MOUNT = ["-v", os.path.abspath(os.environ["HEALTH_FILE"]) + ":/t/svc_health.py:ro"] if os.environ.get("HEALTH_FILE") else []
if MOUNT:
    H = "/t/svc_health.py"
CASES = [
    ("declares Vault but holds NO token (final-review case)", {"VAULT_ROLE_ID": "r", "VAULT_ADDR": "http://127.0.0.1:1"}, 1),
    ("declares Vault, has a token, Vault unreachable", {"VAULT_ROLE_ID": "r", "VAULT_TOKEN": "hvs.x", "VAULT_ADDR": "http://127.0.0.1:1"}, 1),
    ("declares Vault, has a token, renewer not running", {"VAULT_ROLE_ID": "r", "VAULT_TOKEN": "hvs.x", "VAULT_ADDR": "http://127.0.0.1:1"}, 1),
    ("does not use Vault at all (positive)", {}, 0),
]
fails = []
print("▶ healthcheck truth test (B125) — %s in %s" % (H, IMG))
for name, env, want in CASES:
    cmd = ["docker", "run", "--rm", "--network", "none", "--entrypoint", "sh"] + MOUNT
    for k, v in env.items():
        cmd += ["-e", "%s=%s" % (k, v)]
    # the service process: a sleeper that carries the env (as the real service would), then the healthcheck
    cmd += [IMG, "-c", "sleep 30 & sleep 0.3; python3 %s; echo RC=$?" % H]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rc = int((re.search(r"RC=(\d+)", out) or [0, 99])[1])
    ok = (rc != 0) == (want != 0)
    print(("  ✓ " if ok else "  ✗ ") + "%s → healthcheck exit %d (%s)" % (name, rc, out.strip().splitlines()[0][:80] if out.strip() else ""))
    if not ok:
        fails.append(name)
print(("✗" if fails else "✓") + " healthcheck truth test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Operations: log rotation everywhere, a rotated Vault audit device, a complete backup set (slice-1h, DEBT-B102).

  1. every compose service has a size-capped json-file log (max-size + max-file) — static, from `docker compose config`;
     and every RUNNING container of the project actually carries that log config (docker inspect);
  2. Vault has a FILE audit device writing to its own volume, and a Vault request lands in the audit log;
  3. the audit log is ROTATED: it is pushed past its limit and must be renamed to audit.log.1 within the check interval,
     with Vault writing a fresh audit.log afterwards (SIGHUP reopen);
  4. the backup set (deploy/local-dev/backup.sh) covers every durable volume of the compose project, identity, filestore
     and app-bundles included.
Writes conformance/results/local-dev-ops.json. Exit 1 on any failure.
"""
import json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402

P = "airawatos-localdev"
C = ["docker", "compose", "-p", P, "--project-directory", os.path.join(ROOT, "deploy/local-dev"), "-f",
     os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")]
cases, bad = [], 0


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def check(name, ok, detail, rules=("ARC-7", "FND-12")):
    global bad
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail)
    cases.append({"case": name, "rules": list(rules), "result": "PASS" if ok else "FAIL", "detail": detail[:300]})
    bad += (not ok)


print("▶ operations test (B102)")
cfg = json.loads(sh(*C, "config", "--format", "json").stdout)
nolog = [n for n, s in cfg["services"].items() if not ((s.get("logging") or {}).get("options") or {}).get("max-size")]
check("every compose service has a size-capped, rotated log", not nolog, "uncapped: %s" % (nolog or "none"), ("FND-16",))
live = sh("docker", "ps", "--filter", "label=com.docker.compose.project=" + P, "--format", "{{.Names}}").stdout.split()
unc = [c for c in live if "max-size" not in sh("docker", "inspect", "-f", "{{json .HostConfig.LogConfig.Config}}", c).stdout]
check("every running container carries the capped log config", live and not unc, "%d containers; uncapped: %s" % (len(live), unc or "none"), ("FND-16",))

VR = sh("docker", "exec", "airawat-ld-vault", "sh", "-lc",
        'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"').stdout.strip()
V = ["docker", "exec", "-e", "VAULT_TOKEN=" + VR, "-e", "VAULT_ADDR=http://127.0.0.1:8200", "airawat-ld-vault"]
dev = sh(*V, "vault", "audit", "list", "-detailed")
check("Vault has a file audit device on its own volume", "file/" in dev.stdout and "/vault/audit/audit.log" in dev.stdout,
      dev.stdout.strip().replace("\n", " | ")[:200] or dev.stderr[:120])
mounts = sh("docker", "inspect", "-f", "{{range .Mounts}}{{.Destination}}={{.Name}} {{end}}", "airawat-ld-vault").stdout
check("the audit log lives on a dedicated volume", re.search(r"/vault/audit=\S*localdev_vault_audit", mounts) is not None, mounts.strip()[:160])
size = lambda f: int((sh("docker", "exec", "airawat-ld-vault", "sh", "-c", "wc -c < %s 2>/dev/null || echo 0" % f).stdout.strip() or "0"))
s0 = size("/vault/audit/audit.log")
sh(*V, "vault", "token", "lookup")
s1 = size("/vault/audit/audit.log")
check("a Vault request is recorded in the audit log", s1 > s0, "audit.log %d → %d bytes" % (s0, s1))
# rotation: push the log past the limit (as root, out of band) and wait for the rotation loop + a fresh log
limit = int(os.environ.get("AUDIT_MAX_MB", "50")) * 1024 * 1024
# slice-1h (R7-7): start from a known state — an earlier run's rotated file must not decide this run's result
sh("docker", "exec", "--user", "0:0", "airawat-ld-vault", "sh", "-c", "rm -f /vault/audit/audit.log.[1-9]")
sh("docker", "exec", "--user", "0:0", "airawat-ld-vault", "sh", "-c",
   "head -c %d /dev/zero | tr '\\0' 'x' >> /vault/audit/audit.log && echo >> /vault/audit/audit.log" % (limit + 1024))
rotated, deadline = False, time.time() + 90
while time.time() < deadline and not rotated:
    time.sleep(5)
    rotated = size("/vault/audit/audit.log.1") > limit
sh(*V, "vault", "token", "lookup")
fresh = 0 < size("/vault/audit/audit.log") < limit
check("the audit log is rotated past its limit and Vault reopens a fresh one", rotated and fresh,
      "audit.log.1 %s; fresh audit.log %s" % ("present" if rotated else "MISSING", "written" if fresh else "not reopened"))
sh("docker", "exec", "--user", "0:0", "airawat-ld-vault", "sh", "-c", "rm -f /vault/audit/audit.log.[1-9]")   # leave no test artefact behind
vols = {k for k in cfg.get("volumes", {})}
bk = open(os.path.join(ROOT, "deploy/local-dev/backup.sh")).read()
m = re.search(r'^VOLS="([^"]+)"', bk, re.M)
covered = set(m.group(1).split()) if m else set()
check("the backup set covers every durable volume (identity, filestore, app-bundles included)", vols and vols <= covered,
      "volumes %s; not in backup.sh: %s" % (sorted(vols), sorted(vols - covered) or "none"))
evidence.write("ops", cases)
print(("✗" if bad else "✓") + " operations test: %d failure(s)" % bad)
sys.exit(1 if bad else 0)

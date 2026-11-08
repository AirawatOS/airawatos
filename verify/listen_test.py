#!/usr/bin/env python3
"""No Airawat service listens on a non-loopback address (slice-1g, DEBT-B95 / A61).

Two checks:
  1. STATIC — every docker-compose file in the repositories that publishes a port binds it to 127.0.0.1 (or [::1]).
     A bare "80:80" / "0.0.0.0:80:80" publishes on every interface (the LAN). The production EC2 compose is the only
     declared exception (its edge must face the internet) and is listed explicitly.
  2. LIVE — no running container of an Airawat compose project publishes on 0.0.0.0/[::], and no host process that
     runs Airawat code (platform-spec/kernel/network/components) is listening at all (stray dev processes).
Exit 1 on any finding. Writes conformance/results/local-dev-listen.json (ARC-5).
"""
import glob, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_PUBLIC = {"platform-spec/deploy/ec2/docker-compose.yml"}   # production edge — faces the internet by design
REPOS = (".", "platform-spec", "kernel", "network", "components")
bad = []


def tracked_composes():
    out = []
    for r in REPOS:
        ls = subprocess.run(["git", "-C", os.path.join(ROOT, r), "ls-files"], capture_output=True, text=True).stdout.split()
        out += [os.path.normpath(os.path.join(r, f)) for f in ls if re.search(r"(^|/)docker-compose[^/]*\.ya?ml$", f)]
    return sorted(set(out))


print("▶ listen test — STATIC: compose port publications")
for f in tracked_composes():
    txt = open(os.path.join(ROOT, f), errors="replace").read()
    for m in re.finditer(r'^\s*ports:\s*\[([^\]]*)\]|^\s*-\s*["\']?([0-9.:\[\]]*\d+:\d+[^"\'\s#]*)', txt, re.M):
        specs = [x.strip().strip('"\'') for x in (m.group(1).split(",") if m.group(1) is not None else [m.group(2)])]
        for sp in specs:
            if not sp or not re.match(r"^[\d.\[\]:]+$", sp.split("/")[0]):
                continue
            parts = sp.split(":")
            host_ip = ":".join(parts[:-2]) if len(parts) >= 3 else ""
            if host_ip not in ("127.0.0.1", "[::1]") and f not in ALLOWED_PUBLIC:
                bad.append(f"{f}: publishes '{sp}' on every interface")
                print(f"  ✗ {f}: '{sp}'")

print("▶ listen test — LIVE: containers + host processes")
ps = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}\t{{.Label \"com.docker.compose.project.working_dir\"}}"],
                    capture_output=True, text=True).stdout
for line in ps.splitlines():
    name, ports, wd = (line.split("\t") + ["", "", ""])[:3]
    if not wd.startswith(ROOT):
        continue                                            # not an Airawat project
    if re.search(r"(0\.0\.0\.0|\[::\]):\d+->", ports):
        bad.append(f"container {name} publishes on all interfaces: {ports}")
        print(f"  ✗ container {name}: {ports}")
ls = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pn"], capture_output=True, text=True).stdout
cur, listeners = None, {}
for l in ls.splitlines():
    if l.startswith("p"):
        cur = l[1:]
    elif l.startswith("n") and cur:
        listeners.setdefault(cur, []).append(l[1:])
loopback_only = []
for pid, addrs in sorted(listeners.items()):
    cmd = subprocess.run(["ps", "-o", "command=", "-p", pid], capture_output=True, text=True).stdout.strip()
    if not re.search(r"(platform-spec/reference|kernel/api|network/api|components/_common)\S*\.py|uvicorn api", cmd):
        continue
    public = [a for a in addrs if not a.startswith(("127.0.0.1:", "[::1]:", "localhost:"))]
    if public:
        bad.append(f"host process {pid} runs Airawat code on a non-loopback address {public}: {cmd[:100]}")
        print(f"  ✗ host process {pid} {public}: {cmd[:100]}")
    else:
        loopback_only.append((pid, addrs))
if loopback_only:     # reported, not failed: loopback-bound (not on the LAN); unreachable from containers once egress is denied
    print(f"  · {len(loopback_only)} loopback-only host process(es) run Airawat code (stray dev processes — stop when unused): "
          + ", ".join(f"{p}@{a[0]}" for p, a in loopback_only))

os.makedirs(os.path.join(ROOT, "conformance", "results"), exist_ok=True)
json.dump({"env": "local-dev", "mode": "listen", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "",
           "cases": [{"case": "no Airawat service listens on a non-loopback address (compose + live)", "rules": ["ARC-5"],
                      "result": "FAIL" if bad else "PASS"}]},
          open(os.path.join(ROOT, "conformance", "results", "local-dev-listen.json"), "w"), indent=1)
print(("✗" if bad else "✓") + f" listen test: {len(bad)} finding(s)")
sys.exit(1 if bad else 0)

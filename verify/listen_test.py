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
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

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


print("▶ listen test — STATIC: compose port publications (parsed as YAML — short AND long syntax)")
# slice-1h (DEBT-B99, re-review R6-4): the regex missed the long form `ports: [{target: 80, published: 8080}]` (binds every
# interface). Every tracked compose file is now PARSED as YAML (PyYAML, inside the reference image) and every port entry —
# "h:c", "ip:h:c", a bare number, or {target, published, host_ip} — is checked.
_PARSE = r"""
import json, sys, yaml
out = []
for f in json.loads(sys.argv[1]):
    try:
        d = yaml.safe_load(open("/w/" + f)) or {}
    except Exception as e:
        out.append([f, "?", "UNPARSEABLE: %s" % str(e)[:80], ""]); continue
    for svc, sd in (d.get("services") or {}).items():
        for p in (sd or {}).get("ports") or []:
            if isinstance(p, dict):
                if p.get("published") is not None:
                    out.append([f, svc, "%s->%s" % (p.get("published"), p.get("target")), str(p.get("host_ip") or "")])
            else:
                parts = str(p).split("/")[0].split(":")
                ip = ":".join(parts[:-2]) if len(parts) >= 3 else ""
                out.append([f, svc, str(p), ip if len(parts) >= 2 else ""])
print(json.dumps(out))
"""
_files = tracked_composes()
_img = re.search(r"^\s*image:\s*(manishsv/airawatos-reference:[^\s#]+)", open(os.path.join(ROOT, "deploy/local-dev/docker-compose.dev.yml")).read(), re.M).group(1)
_r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", "-v", ROOT + ":/w:ro", _img, "-c", _PARSE,
                     json.dumps(_files)], capture_output=True, text=True)
try:
    _ports = json.loads(_r.stdout)
except Exception:
    _ports = None
    bad.append("compose files could not be parsed: %s" % (_r.stderr or _r.stdout)[-200:])
    print("  ✗ compose parse failed: " + (_r.stderr or _r.stdout)[-200:])
for f, svc, spec, ip in (_ports or []):
    if spec.startswith("UNPARSEABLE"):
        bad.append(f"{f}: {spec}"); print(f"  ✗ {f}: {spec}"); continue
    if ip.strip("[]") not in ("127.0.0.1", "::1") and f not in ALLOWED_PUBLIC:
        bad.append(f"{f}: service {svc} publishes '{spec}' on every interface")
        print(f"  ✗ {f}: {svc} '{spec}' (host_ip {ip or 'unset = all interfaces'})")
print(f"  {len(_files)} compose file(s), {len(_ports or [])} port publication(s) checked")
if not _files:
    bad.append("no compose file found — the static check would pass vacuously")

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
_ev.seal(os.path.join(ROOT, "conformance", "results", "local-dev-listen.json"))
print(("✗" if bad else "✓") + f" listen test: {len(bad)} finding(s)")
sys.exit(1 if bad else 0)

#!/usr/bin/env python3
"""Network internal doors admit EXACTLY their declared callers (slice-1g, DEBT-B86 / review B2).

Parses the declared table in docs/specs/ARCHITECTURE-FLOWS-v0.1.md (between <!-- net-doors:begin/end -->) and, LIVE,
for every door × every operator-realm service that can hold an svc:network token (kernel, app-host, scheduler,
launcher, decision, workflow, identity, svcprobe), calls the door with that service's REAL token (identity /login with
aud=svc:network; identity's own self-issued token from inside the identity container) and records whether the gate
admitted it. Fails on ANY difference between declared and accepted, in either direction:
  * a declared caller refused  → the door is narrower than declared (breaks the caller)
  * an undeclared caller admitted → the door is wider than declared (the review B2 hole)
Also fails if a door in the Network code is missing from the table (or vice versa).

Resolve doors: admitted = the gate passed (any status but 401/403). Lists: "service mode" — for /v1/join and
/v1/interfaces/bindings non-service callers get 403; for /v1/tenants a non-service caller sees only its own realm's
rows, so service mode = it sees the full set (strictly more than a user-scoped read).
Runs on the HOST (docker). Writes conformance/results/local-dev-netdoors.json (FND-8/FND-10). Exit 1 on difference.
"""
import json, os, re, subprocess, sys, time
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET = "airawat-ld-network"
SERVICES = ["kernel", "app-host", "scheduler", "launcher", "decision", "workflow", "identity", "svcprobe"]

doc = open(os.path.join(ROOT, "docs/specs/ARCHITECTURE-FLOWS-v0.1.md")).read()
table = doc.split("<!-- net-doors:begin -->", 1)[1].split("<!-- net-doors:end -->", 1)[0]
DECLARED = {}
for m in re.finditer(r"^\| (list )?`([^`]+)` \| ([^|]+) \|$", table, re.M):
    DECLARED[("list" if m.group(1) else "door", m.group(2))] = {c.strip() for c in m.group(3).split(",") if c.strip() not in ("—", "-", "")}
code = open(os.path.join(ROOT, "network/api.py")).read()
CODE_DOORS = set(re.findall(r'_require_internal_lookup\(authorization, "([^"]+)"\)', code))

VR = subprocess.run(["docker", "exec", "airawat-ld-vault", "sh", "-lc",
                     'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"'],
                    capture_output=True, text=True).stdout.strip()
idtok = subprocess.run(["docker", "exec", "airawat-ld-identity", "python3", "-c",
                        "import os, sys\n"   # identity's PID1 Vault token (AppRole), so the token is signed with identity's REAL transit key
                        "for l in open('/proc/1/environ','rb').read().split(b'\\0'):\n"
                        "    k, _, v = l.partition(b'=')\n"
                        "    if k in (b'VAULT_TOKEN', b'VAULT_ADDR'): os.environ[k.decode()] = v.decode()\n"
                        "sys.argv=['identity.py']; sys.path.insert(0,'/app/reference'); import identity; print('TOK', identity._self_network_token())"],
                       capture_output=True, text=True).stdout
idtok = (re.search(r"^TOK (\S+)$", idtok, re.M) or [None, ""])[1]

PROBE = r'''
import json, os, urllib.request, urllib.error
def req(m, url, body=None, tok=None, h=None):
    hd = dict(h or {}); hd["Content-Type"] = "application/json"
    if tok: hd["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(url, data=(json.dumps(body).encode() if body is not None else None), headers=hd, method=m)
    try:
        x = urllib.request.urlopen(r, timeout=15); return x.status, x.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
    except Exception as e: return 0, str(e).encode()
V, VT = "http://vault:8200", os.environ["VR"]
toks = {"identity": os.environ.get("IDTOK", "")}
for s in json.loads(os.environ["SVCS"]):
    if s == "identity": continue
    st, b = req("GET", V + "/v1/secret/data/localdev-operator/%s/password" % s, h={"X-Vault-Token": VT})
    pw = ((json.loads(b).get("data") or {}).get("data") or {}).get("password") if st == 200 else None
    if not pw: toks[s] = ""; continue
    st, b = req("POST", "http://identity:8093/login", {"username": s, "tenant": "localdev-operator", "password": pw, "aud": "svc:network"})
    toks[s] = json.loads(b).get("access_token", "") if st == 200 else ""
out = {"tokens": {k: bool(v) for k, v in toks.items()}, "doors": {}, "lists": {}}
for d in json.loads(os.environ["DOORS"]):
    out["doors"][d] = {s: (req("POST", "http://localhost:8090" + d, {}, toks[s])[0] if toks[s] else None) for s in toks}
for l in json.loads(os.environ["LISTS"]):
    res = {}
    for s in toks:
        if not toks[s]: res[s] = None; continue
        st, b = req("GET", "http://localhost:8090" + l, None, toks[s])
        try: n = len(next(v for v in json.loads(b).values() if isinstance(v, (list, dict))))
        except Exception: n = -1
        res[s] = [st, n]
    out["lists"][l] = res
print("OUT " + json.dumps(out))
'''
doors = sorted(k[1] for k in DECLARED if k[0] == "door")
lists = sorted(k[1] for k in DECLARED if k[0] == "list")
r = subprocess.run(["docker", "exec", "-e", "VR=" + VR, "-e", "IDTOK=" + idtok, "-e", "SVCS=" + json.dumps(SERVICES),
                    "-e", "DOORS=" + json.dumps(doors), "-e", "LISTS=" + json.dumps(lists), NET, "python3", "-c", PROBE],
                   capture_output=True, text=True, timeout=300)
m = re.search(r"^OUT (.*)$", r.stdout, re.M)
if not m:
    print("✗ probe failed:", r.stdout[-400:], r.stderr[-400:]); sys.exit(1)
O = json.loads(m.group(1))
cases, bad = [], 0


def rec(name, ok, detail, rule="FND-10"):
    global bad
    cases.append({"case": name, "rules": ["FND-8", rule], "result": "PASS" if ok else "FAIL", "detail": detail})
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail)
    bad += (not ok)


print("▶ Network internal doors: declared (ARCHITECTURE-FLOWS) vs accepted (live)")
rec("every service can hold an svc:network token for the probe", all(O["tokens"].values()), "tokens: %s" % O["tokens"])
rec("the declared table covers every internal door in the Network code (and no other)", CODE_DOORS == set(doors),
    "code-only %s, doc-only %s" % (sorted(CODE_DOORS - set(doors)), sorted(set(doors) - CODE_DOORS)))
for d in doors:
    acc = {s for s, st in O["doors"][d].items() if st not in (None, 0, 401, 403)}
    dec = DECLARED[("door", d)]
    rec("%s admits exactly %s" % (d, sorted(dec) or "nobody"), acc == dec,
        "accepted %s; undeclared admitted %s; declared refused %s; statuses %s"
        % (sorted(acc), sorted(acc - dec), sorted(dec - acc), O["doors"][d]))
for l in lists:
    res, dec = O["lists"][l], DECLARED[("list", l)]
    if l == "/v1/tenants":
        counts = [v[1] for v in res.values() if v and v[0] == 200]
        full = max(counts) if counts else -1
        svc = {s for s, v in res.items() if v and v[0] == 200 and v[1] == full}
        ok = svc == dec and full > 0    # a non-service reader is refused or sees only its own realm's rows (< full)
    else:
        svc = {s for s, v in res.items() if v and v[0] == 200}
        ok = svc == dec
    rec("list %s: service mode for exactly %s" % (l, sorted(dec)), ok,
        "service-mode callers %s; undeclared %s; declared missing %s; %s" % (sorted(svc), sorted(svc - dec), sorted(dec - svc), res))

os.makedirs(os.path.join(ROOT, "conformance", "results"), exist_ok=True)
json.dump({"env": "local-dev", "mode": "netdoors", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "",
           "cases": cases}, open(os.path.join(ROOT, "conformance", "results", "local-dev-netdoors.json"), "w"), indent=1)
_ev.seal(os.path.join(ROOT, "conformance", "results", "local-dev-netdoors.json"))
print(("✗" if bad else "✓") + " Network doors: %d difference(s)" % bad)
sys.exit(1 if bad else 0)

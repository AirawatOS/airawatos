#!/usr/bin/env python3
"""DEBT-B174 — the shared service client's declared edges ARE the ARCHITECTURE-FLOWS table.

Parses the `svc-edges` block of docs/specs/ARCHITECTURE-FLOWS-v0.1.md (one row per door operation: door, audience,
base env=default, operation, request, timeout, retries, callers) and compiles it to deploy/runtime/lib/aos_svc/edges.json
— what `aos_svc.client_for(caller)` builds its methods from. Default mode CHECKS that edges.json is exactly the compiled
table (any hand edit or doc change without a regenerate fails); `--write` regenerates it. Also proves, against the real
package, that a caller gets exactly its declared operations and NotDeclared for every other one.
No stack needed. Exit 1 on any difference.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs/specs/ARCHITECTURE-FLOWS-v0.1.md")
LIB = os.path.join(ROOT, "deploy/runtime/lib")
OUT = os.path.join(LIB, "aos_svc/edges.json")


def compile_table():
    doc = open(DOC).read()
    t = doc.split("<!-- svc-edges:begin -->", 1)[1].split("<!-- svc-edges:end -->", 1)[0]
    doors, callers = {}, set()
    for l in t.splitlines():
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) != 8 or cells[0] in ("door", "") or set(cells[0]) <= {"-"}:
            continue
        door, aud, base, op, reqs, to, rt, cs = cells
        env, _, default = base.partition("=")
        m = re.match(r"^(GET|POST|PUT|DELETE|HEAD) (\S+)( \(public\))?$", reqs)
        if not m:
            sys.exit("✗ svc-edges: bad request cell %r" % reqs)
        d = doors.setdefault(door, {"audience": aud, "base_env": env, "base_default": default, "operations": {}})
        if (d["audience"], d["base_env"], d["base_default"]) != (aud, env, default):
            sys.exit("✗ svc-edges: door %s has inconsistent audience/base across rows" % door)
        who = sorted(c.strip() for c in cs.split(",") if c.strip() not in ("", "—", "-"))
        callers |= set(who)
        d["operations"][op] = {"method": m.group(1), "path": m.group(2), "public": bool(m.group(3)),
                               "timeout": int(to), "retries": int(rt), "callers": who}
    return {"generated_from": "docs/specs/ARCHITECTURE-FLOWS-v0.1.md#svc-edges — do not edit; run verify/svc_edges.py --write",
            "callers": sorted(callers), "doors": doors}


want = compile_table()
if "--write" in sys.argv:
    with open(OUT, "w") as f:
        json.dump(want, f, indent=1, sort_keys=True); f.write("\n")
    print("✓ wrote %s (%d doors, %d callers)" % (os.path.relpath(OUT, ROOT), len(want["doors"]), len(want["callers"])))
    sys.exit(0)
have = json.load(open(OUT)) if os.path.exists(OUT) else None
fails = []
if have != want:
    fails.append("aos_svc/edges.json differs from the ARCHITECTURE-FLOWS svc-edges table — run verify/svc_edges.py --write")
sys.path.insert(0, LIB)
import aos_svc  # noqa: E402
for caller in want["callers"]:
    c = aos_svc.client_for(caller)
    for door, spec in want["doors"].items():
        for op, o in spec["operations"].items():
            declared = caller in o["callers"]
            try:
                c.door(door)._op(op); got = True
            except aos_svc.NotDeclared:
                got = False
            if got != declared:
                fails.append("%s → %s.%s: client %s, table %s" % (caller, door, op, "allows" if got else "refuses", "declares" if declared else "does not"))
try:
    aos_svc.client_for("not-a-service"); fails.append("an undeclared caller got a client")
except aos_svc.NotDeclared:
    pass
# CI pins: a consumer repository's CI checks out aos_svc from root at the commit in .github/aos-runtime.ref — that commit
# must carry the SAME package tree as root HEAD, or that repository's CI tests a different client than the images ship.
import subprocess  # noqa: E402
def _tree(repo_dir, rev):
    r = subprocess.run(["git", "-C", repo_dir, "rev-parse", "%s:deploy/runtime/lib" % rev], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None
head = _tree(ROOT, "HEAD")
dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "deploy/runtime/lib"], capture_output=True, text=True).stdout.strip()
for repo in ("kernel", "platform-spec"):
    pin_f = os.path.join(ROOT, repo, ".github/aos-runtime.ref")
    pin = open(pin_f).read().split()[0] if os.path.exists(pin_f) else None
    if not pin:
        fails.append("%s: no .github/aos-runtime.ref (its CI cannot find aos_svc)" % repo); continue
    if dirty:
        print("    (deploy/runtime/lib has uncommitted changes — pins compared against root HEAD)")
    if _tree(ROOT, pin) != head:
        fails.append("%s CI pins root %s, whose aos_svc differs from root HEAD — update %s/.github/aos-runtime.ref" % (repo, pin[:10], repo))
n = sum(len(s["operations"]) for s in want["doors"].values())
print(("✓" if not fails else "✗") + " svc-edges: %d doors, %d operations, callers %s — client == table" % (len(want["doors"]), n, ", ".join(want["callers"])))
for f in fails:
    print("    " + f)
sys.exit(1 if fails else 0)

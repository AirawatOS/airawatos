#!/usr/bin/env python3
"""Route inventory — the two tests of FIX-PLAN §0 net 4 (slice-1d). Runs on the HOST against the local-dev stack.

  TEST 1 (declared): enumerate the routes every service ACTUALLY exposes (route_extract.py) and FAIL on any route
          not declared in verify/route-inventory.json. A declared route the code no longer exposes is reported (stale).
  TEST 2 (anonymous refusal): inside the `network` container, call every NON-public route with no credential and
          FAIL unless it is refused (401/403) — route_probe.py.

Also prints the REVIEW list (routes declared `public` that should not be) and writes conformance/results/
local-dev-routes.json for the status matrix (FND-8: every privileged endpoint authenticated, fail-closed).
Usage: python3 verify/route_inventory_test.py
"""
import json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
NET = os.environ.get("AOS_NET_CONTAINER", "airawat-ld-network")
RESULTS = os.path.join(ROOT, "conformance", "results", "local-dev-routes.json")


def main():
    routes = json.loads(subprocess.run([sys.executable, os.path.join(HERE, "route_extract.py")],
                                       capture_output=True, text=True, check=True).stdout)
    inv = json.load(open(os.path.join(HERE, "route-inventory.json")))
    cases = []; fail = 0
    print("▶ route inventory — TEST 1: every exposed route is declared")
    n = 0
    for svc, rs in sorted(routes.items()):
        exposed = {f"{r['method']} {r['path']}" for r in rs}; n += len(exposed)
        declared = set((inv.get(svc) or {}).keys())
        for k in sorted(exposed - declared):
            print(f"  ✗ UNDECLARED  {svc:15} {k}"); fail += 1
            cases.append({"case": f"route declared: {svc} {k}", "rules": ["FND-8"], "result": "FAIL"})
        for k in sorted(declared - exposed):
            print(f"  · stale declaration (no longer exposed): {svc} {k}")
    if not fail:
        cases.append({"case": f"every exposed route is declared ({n} routes, {len(routes)} services)", "rules": ["FND-8"], "result": "PASS"})
    print(f"  {n} routes exposed across {len(routes)} services; {fail} undeclared")

    print("▶ route inventory — TEST 2: every non-public route refuses an anonymous call")
    with tempfile.TemporaryDirectory() as td:
        rp = os.path.join(td, "routes.json"); json.dump(routes, open(rp, "w"))
        subprocess.run(["docker", "exec", NET, "mkdir", "-p", "/tmp/v"], check=True)
        for src, dst in ((os.path.join(HERE, "route_probe.py"), "route_probe.py"), (rp, "routes.json"),
                         (os.path.join(HERE, "route-inventory.json"), "decl.json")):
            subprocess.run(["docker", "cp", src, f"{NET}:/tmp/v/{dst}"], check=True, capture_output=True)
        p = subprocess.run(["docker", "exec", NET, "python3", "/tmp/v/route_probe.py", "/tmp/v/routes.json",
                            "/tmp/v/decl.json", "--matrix", "/tmp/v/probe.json"], capture_output=True, text=True)
        print(p.stdout.rstrip())
        out = os.path.join(td, "probe.json")
        subprocess.run(["docker", "cp", f"{NET}:/tmp/v/probe.json", out], check=True, capture_output=True)
        probe_cases = json.load(open(out))["cases"]
    bad = [c for c in probe_cases if c["result"] != "PASS"]
    fail += len(bad)
    cases.append({"case": f"every non-public route refuses an anonymous call ({len(probe_cases)} probed, {len(bad)} not refused)",
                  "rules": ["FND-8"], "result": "PASS" if not bad else "FAIL"})

    review = [(s, k, v["review"]) for s, d in inv.items() if s != "_meta" for k, v in d.items() if v.get("review")]
    print(f"▶ REVIEW — {len(review)} route(s) declared public that should not be:")
    for s, k, r in review:
        print(f"  ! {s:14} {k:44} {r}")
    if review:   # a known violation of FND-8 tracked as debt: shown as XFAIL so the rule reads PARTIAL, never HELD
        cases.append({"case": f"no route is public that should not be ({len(review)} on the review list — DEBT-A1/B36/B48)",
                      "rules": ["FND-8"], "result": "XFAIL"})
    sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    json.dump({"env": "local-dev", "mode": "routes", "git_sha": sha, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cases": cases}, open(RESULTS, "w"), indent=1)
    print(("✓" if not fail else "✗") + f" route inventory: {fail} failure(s)")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()

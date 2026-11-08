#!/usr/bin/env python3
"""Anonymous probe of every route (slice-1d, FIX-PLAN §0 net 4, second test).

Runs INSIDE the local-dev `network` container (it reaches every service on the internal networks). Reads the route
list (route_extract.py output) and the declarations (route-inventory.json) from argv, calls every route with NO
credentials, directly on the owning service (never via the edge, so an internal-only route is exercised as a
compromised neighbour would), and reports the status. A route declared anything other than `public` must be
REFUSED (401/403). Prefix routes are probed at the declaration's `sample` path (or the prefix with `x`).

Usage (in container): python3 route_probe.py routes.json route-inventory.json [--matrix out.json]
"""
import json, sys, time, urllib.error, urllib.request

BASE = {"identity": "http://identity:8093", "app-host": "http://app-host:8099", "secrets": "http://secrets:8102",
        "filestore": "http://filestore:8095", "model-gateway": "http://model-gateway:8104",
        "notify": "http://notify:8094", "workflow": "http://workflow:8097", "decision": "http://decision:8096",
        "automation": "http://automation:8098", "event-relay": "http://event-relay:8101",
        "scheduler": "http://scheduler:8103", "runtime-manager": "http://runtime-manager:8105",
        "kernel": "http://kernel:8080", "network": "http://127.0.0.1:8090"}
REFUSED = (401, 403)


# A generic body carrying the keys handlers commonly index, so a handler that parses its body BEFORE authenticating
# reaches its auth check instead of crashing (400/422/500 would hide whether the route is protected). Dummy values;
# nothing here is a credential. A declaration may override it with its own `body`.
GENERIC_BODY = {k: "conformance-probe" for k in (
    "tenant", "tenant_id", "component_id", "component", "subject_id", "subject_kind", "participant_id", "id", "schema",
    "scope", "network", "decision", "name", "key", "username", "password", "email", "code", "case", "task", "url",
    "workflow", "query", "q", "text", "message", "token", "service_id", "offering_id", "grantee", "role", "kind",
    "cid", "path", "object_id", "file_id", "share_id", "request_id", "solution_id", "interface", "domain", "pack",
    "jurisdiction", "issuer", "holder", "credential", "presentation", "markdown", "aoi", "bbox", "verb", "reason")}
GENERIC_BODY.update({"object": {}, "items": [], "members": [], "texts": [], "messages": [], "filter": {}})


def call(method, url, body=None):
    data = json.dumps(body if body is not None else GENERIC_BODY).encode() if method in ("POST", "PUT", "PATCH") else None
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(r, timeout=15).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return "ERR:" + type(e).__name__


def main():
    routes = json.load(open(sys.argv[1])); decl = json.load(open(sys.argv[2]))
    out_matrix = sys.argv[sys.argv.index("--matrix") + 1] if "--matrix" in sys.argv else None
    rows = []; bad = 0
    for svc, rs in sorted(routes.items()):
        d = decl.get(svc, {})
        for r in rs:
            key = f"{r['method']} {r['path']}"
            ent = d.get(key)
            if ent is None:
                rows.append((svc, key, "UNDECLARED", None)); continue
            cls = ent["class"]
            if cls == "public":
                rows.append((svc, key, "public", None)); continue
            path = ent.get("sample") or r["path"].replace("*", "x")
            st = call(r["method"], BASE[svc] + path, ent.get("body"))
            ok = st in REFUSED
            bad += not ok
            rows.append((svc, key, cls, st))
    for svc, key, cls, st in rows:
        if st is not None and st not in REFUSED:
            print(f"  ✗ NOT REFUSED  {svc:15} {key:55} class={cls} anon→{st}")
    n = sum(1 for r in rows if r[3] is not None)
    print(f"route anon-probe: {n} non-public routes called anonymously; {n - bad} refused; {bad} NOT refused; "
          f"{sum(1 for r in rows if r[2] == 'public')} public (not probed); "
          f"{sum(1 for r in rows if r[2] == 'UNDECLARED')} undeclared")
    if out_matrix:
        cases = [{"case": f"anon {svc} {key} → refused", "rules": ["FND-8"],
                  "result": "PASS" if st in REFUSED else "FAIL"} for svc, key, cls, st in rows if st is not None]
        json.dump({"env": "local-dev", "mode": "routeprobe", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "git_sha": "", "cases": cases}, open(out_matrix, "w"), indent=1)
    sys.exit(1 if bad or any(r[2] == "UNDECLARED" for r in rows) else 0)


if __name__ == "__main__":
    main()

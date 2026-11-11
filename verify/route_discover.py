#!/usr/bin/env python3
"""Runtime route discovery for the stdlib services (slice-1h, DEBT-B104 / re-review R5 item 3, B92 N1).

The stdlib `http.server` services have no router object: they dispatch inside do_* methods, through helper methods and
through dispatch TABLES (dicts of path → handler). Source parsing of the comparisons missed every helper/table-dispatched
route. So routes are now DISCOVERED AT RUNTIME, in two halves:

  HOST half (candidates):  python3 route_discover.py candidates  → {service: [paths]}
      Each service module is COMPILED and every string constant of every code object (recursively — function bodies,
      class bodies, dict/tuple literals, dispatch tables) that looks like a URL path becomes a candidate. No regex over
      source text: the compiler's own constants.
  CONTAINER half (probe):  python3 route_discover.py probe candidates.json  (inside the network container)
      Every candidate is called on the LIVE service with GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS and no credential, both
      as-is and with a child segment (`<path>/x`, for prefix routes). A response that differs from the service's answer
      to a random never-routed path (status, and body size for a catch-all) means the route EXISTS.
      Output: {service: [{"method", "path", "status"}]} — `path/*` for a route that only answers with a child segment.
"""
import json, os, re, sys, types

PATHLIKE = re.compile(r"^/[A-Za-z0-9_\-./]*$")
METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")


def candidates(root):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from route_extract import STDLIB, REF
    out = {}
    for svc, fn in STDLIB.items():
        code = compile(open(os.path.join(REF, fn)).read(), fn, "exec")
        seen, stack = set(), [code]
        while stack:
            c = stack.pop()
            for k in c.co_consts:
                if isinstance(k, types.CodeType):
                    stack.append(k)
                elif isinstance(k, str) and PATHLIKE.match(k) and 1 < len(k) < 120 and "//" not in k and not k.endswith((".py", ".json", ".html", ".js", ".css", ".png", ".svg")):
                    seen.add(k.rstrip("/") or "/")
                elif isinstance(k, (tuple, frozenset)):
                    seen.update(x.rstrip("/") for x in k if isinstance(x, str) and PATHLIKE.match(x) and 1 < len(x) < 120)
        out[svc] = sorted(seen)
    return out


def probe(cands):
    import urllib.error, urllib.request, uuid
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from route_probe import BASE

    def call(url, method):
        data = b"{}" if method in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=6)
            return r.status, len(r.read() or b"")
        except urllib.error.HTTPError as e:
            return e.code, len(e.read() or b"")
        except Exception:
            return 0, 0

    found = {}
    for svc, paths in cands.items():
        base = BASE.get(svc)
        if not base:
            continue
        nonsense = "/__no_such_route_%s" % uuid.uuid4().hex[:8]
        baseline = {m: call(base + nonsense, m) for m in METHODS}
        rows = []
        for p in paths:
            for m in METHODS:
                st, n = call(base + p, m)
                bst, bn = baseline[m]
                exists = st not in (0, 404, 501) and (st != bst or (bst not in (404, 501) and n != bn))
                if exists:
                    rows.append({"method": m, "path": p, "status": st})
                    continue
                st2, n2 = call(base + p.rstrip("/") + "/x", m)
                if st2 not in (0, 404, 501) and (st2 != bst or (bst not in (404, 501) and n2 != bn)):
                    rows.append({"method": m, "path": p.rstrip("/") + "/*", "status": st2})
        found[svc] = rows
    return found


if __name__ == "__main__":
    if sys.argv[1:2] == ["candidates"]:
        print(json.dumps(candidates(None)))
    elif sys.argv[1:2] == ["probe"]:
        print(json.dumps(probe(json.load(open(sys.argv[2])))))
    else:
        print(__doc__); sys.exit(2)

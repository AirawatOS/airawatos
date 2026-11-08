#!/usr/bin/env python3
"""Enumerate the HTTP routes each service ACTUALLY exposes (slice-1d, FIX-PLAN §0 net 4).

Two kinds of service:
  * stdlib `http.server` services (platform-spec/reference/*.py) route by comparing the request path inside
    `do_GET` / `do_POST` / ... (and the helper methods those call). We parse the source with `ast` and collect every
    path literal the dispatch compares against: `p == "/x"`, `"/x" == p`, `p in ("/a", "/b")`, `p.startswith("/x/")`,
    `re.match(r"^/x/...", p)`. Exact literals become routes; startswith/regex become PREFIX routes (`/x/*`).
    The verb is the do_* method the comparison is reachable from (call graph within the handler class).
  * FastAPI services (kernel, network) are introspected from the live `app.routes` (run inside the container).

Output: JSON {service: [{"method": "GET|POST|...", "path": "/x" | "/x/*"}]} on stdout.
Usage: python3 verify/route_extract.py [--fastapi kernel=<json> network=<json>]
"""
import ast, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "platform-spec", "reference")
STDLIB = {  # service -> source file (only files that run as a compose service)
    "identity": "identity.py", "app-host": "app_host.py", "secrets": "secrets.py", "filestore": "filestore.py",
    "model-gateway": "model_gateway.py", "notify": "notify.py", "workflow": "workflow.py", "decision": "decision.py",
    "automation": "automation.py", "event-relay": "event_relay.py", "scheduler": "scheduler.py",
    "runtime-manager": "runtime_manager.py",
}
VERBS = {"do_GET": "GET", "do_POST": "POST", "do_PUT": "PUT", "do_DELETE": "DELETE", "do_PATCH": "PATCH", "do_HEAD": "HEAD"}
PATHLIT = re.compile(r"^/[A-Za-z0-9_\-./{}<>:]*$")


def _lits(node):
    """String literals in a node that look like URL paths."""
    out = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and PATHLIT.match(node.value):
        out.append(node.value)
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for e in node.elts:
            out += _lits(e)
    return out


def _routes_in(fn):
    """(kind, path) pairs compared in this function body (not nested defs' own routing — those are followed via calls)."""
    found = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            op = n.ops[0]; left, right = n.left, n.comparators[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for p in _lits(left) + _lits(right):
                    found.append(("exact", p))
            elif isinstance(op, (ast.In, ast.NotIn)):
                for p in _lits(right):
                    found.append(("exact", p))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "startswith":
            for a in n.args:
                for p in _lits(a):
                    found.append(("prefix", p))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("match", "fullmatch") \
                and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            m = re.match(r"^\^?(/[A-Za-z0-9_\-./]*)", n.args[0].value)
            if m and len(m.group(1)) > 1:
                found.append(("prefix", m.group(1)))
    return found


def _calls(fn):
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                and n.func.value.id == "self":
            names.add(n.func.attr)
    return names


def extract_stdlib(path):
    tree = ast.parse(open(path).read())
    routes = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        methods = {f.name: f for f in cls.body if isinstance(f, ast.FunctionDef)}
        for vname, verb in VERBS.items():
            if vname not in methods:
                continue
            # Only the do_* body itself routes. Helper methods are NOT followed: they compare paths for other reasons
            # (e.g. is the upstream URL an identity path), which are not routes this service exposes.
            for kind, p in _routes_in(methods[vname]):
                if p in ("/",) and kind == "prefix":
                    continue
                routes.add((verb, p + ("*" if kind == "prefix" and not p.endswith("*") else "")))
    return sorted(routes)


FASTAPI = {"kernel": [os.path.join(ROOT, "kernel", "api", "app.py"), os.path.join(ROOT, "kernel", "api", "routers", "kernel_meta.py")],
           "network": [os.path.join(ROOT, "network", "api.py")]}


def extract_fastapi(files):
    """Routes from `@app.<verb>("/x")` / `@router.<verb>("/x")` decorators, plus FastAPI's default doc routes
    (`/docs`, `/redoc`, `/openapi.json`) unless the app is constructed with them disabled."""
    routes = set()
    for f in files:
        src = open(f).read(); tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.args \
                            and d.func.attr in ("get", "post", "put", "delete", "patch") \
                            and isinstance(d.args[0], ast.Constant):
                        p = re.sub(r"\{[^}]+\}", "*", d.args[0].value)   # {oid:path} -> *
                        routes.add((d.func.attr.upper(), p))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "FastAPI":
                kw = {k.arg: k.value for k in n.keywords}
                for name, path in (("docs_url", "/docs"), ("redoc_url", "/redoc"), ("openapi_url", "/openapi.json")):
                    v = kw.get(name)
                    if not (isinstance(v, ast.Constant) and v.value is None):
                        routes.add(("GET", path))
    return sorted(routes)


def main():
    out = {}
    for svc, f in STDLIB.items():
        out[svc] = [{"method": m, "path": p} for m, p in extract_stdlib(os.path.join(REF, f))]
    for svc, files in FASTAPI.items():
        out[svc] = [{"method": m, "path": p} for m, p in extract_fastapi(files)]
    json.dump(out, sys.stdout, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()

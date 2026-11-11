#!/usr/bin/env python3
"""ARC flow-map test — reachability PROVEN BY CONNECTION ATTEMPTS, not inferred from membership (slice-1g, DEBT-B87).

The earlier version assumed "X reaches Y iff they share a network". The Layer 1 exit review showed that is false:
containers reached the internet, the host and other networks' IPs (W1/W2). This version attempts the connections:

  0. ENUMERATE — every container of the compose project (by label) must be declared; no outside container may be
     attached to an aos-* network; each container's networks must equal the DECLARED map.
  1. DEFAULT-DENY — every network except the declared egress networks (aos-public, aos-egress) must be
     `internal: true` (Docker gives an internal network no route out).
  2. CROSS-CONTAINER — from EVERY container, a TCP connect to EVERY other container's service port on EVERY one of
     its IP addresses. Allowed only to an IP on a network both share; an IP on any other network must be
     unreachable (catches routed / published-port paths).
  3. EGRESS — from every container: the internet (1.1.1.1:443, 8.8.8.8:53) and the host (host.docker.internal on
     the edge port and an Airawat dev port). Allowed only for the declared egress gateways.
Runs on the HOST (docker exec into each container; python3 where present, busybox `nc -z` otherwise).
Writes conformance/results/<env>-flowmap.json. Exit 1 on any off-map path.  Usage: python3 conformance/flow_map_test.py
"""
import json, os, subprocess, sys, time
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99
from concurrent.futures import ThreadPoolExecutor

ENV = os.environ.get("AOS_ENV", "local-dev")
P = "airawatos-localdev"          # the installer hard-codes the project; an override here could make the test vacuous

# DECLARED per-boundary membership (must match docker-compose.dev.yml) — container -> networks.
DECLARED = {
    "airawat-ld-nginx":           {"aos-public", "aos-edge"},
    "airawat-ld-app-host":        {"aos-edge", "aos-svc", "aos-data-secrets", "aos-egress"},
    "airawat-ld-network":         {"aos-edge", "aos-svc", "aos-data-facts", "aos-data-secrets", "aos-egress"},
    "airawat-ld-identity":        {"aos-svc", "aos-data-facts", "aos-data-secrets"},
    "airawat-ld-kernel":          {"aos-svc", "aos-data-facts", "aos-data-secrets", "aos-component", "aos-egress"},
    "airawat-ld-secrets":         {"aos-svc", "aos-data-secrets"},
    "airawat-ld-filestore":       {"aos-svc"},
    "airawat-ld-model-gateway":   {"aos-svc", "aos-data-secrets", "aos-egress"},
    "airawat-ld-notify":          {"aos-svc", "aos-data-secrets"},   # notify decision: its own service identity (Vault, own password only)
    "airawat-ld-stub-provider":   {"aos-svc"},                        # DEV-ONLY stub model provider (fixtures decision): no egress, no Vault
    "airawat-ld-workflow":        {"aos-svc", "aos-data-secrets"},
    "airawat-ld-decision":        {"aos-svc", "aos-data-secrets"},
    "airawat-ld-automation":      {"aos-svc", "aos-data-secrets"},
    "airawat-ld-event-relay":     {"aos-svc", "aos-data-secrets"},
    "airawat-ld-scheduler":       {"aos-svc", "aos-data-secrets"},
    "airawat-ld-runtime-manager": {"aos-svc", "aos-data-secrets"},
    "airawat-ld-postgres":        {"aos-data-facts"},
    "airawat-ld-vault":           {"aos-data-secrets"},
}
EGRESS_NETS = {"aos-public", "aos-egress"}          # the ONLY networks with a route out
PORT = {"airawat-ld-nginx": 80, "airawat-ld-app-host": 8099, "airawat-ld-network": 8090, "airawat-ld-identity": 8093,
        "airawat-ld-kernel": 8080, "airawat-ld-secrets": 8102, "airawat-ld-filestore": 8095,
        "airawat-ld-model-gateway": 8104, "airawat-ld-notify": 8094, "airawat-ld-workflow": 8097,
        "airawat-ld-decision": 8096, "airawat-ld-automation": 8098, "airawat-ld-event-relay": 8101,
        "airawat-ld-scheduler": 8103, "airawat-ld-runtime-manager": 8105, "airawat-ld-postgres": 5432,
        "airawat-ld-vault": 8200, "airawat-ld-stub-provider": 8110}
OUTSIDE = [("1.1.1.1", 443, "internet"), ("8.8.8.8", 53, "internet"),
           ("host.docker.internal", 8080, "host"), ("host.docker.internal", 8093, "host")]
# edges the platform cannot work without — must be reachable (the rest of the shared-network pairs are allowed, not required)
REQUIRED = [("airawat-ld-nginx", "airawat-ld-app-host"), ("airawat-ld-nginx", "airawat-ld-network"),
            ("airawat-ld-app-host", "airawat-ld-kernel"), ("airawat-ld-kernel", "airawat-ld-postgres"),
            ("airawat-ld-kernel", "airawat-ld-vault"), ("airawat-ld-identity", "airawat-ld-postgres")]

RESULTS = []


def rec(rule, name, ok, detail, kind="testable"):
    RESULTS.append({"spec": "ARCHITECTURE", "rule": rule, "name": name,
                    "status": ("PASS" if ok else "FAIL") if kind == "testable" else kind, "detail": detail})
    mark = ("  ✓ " if ok else "  ✗ ") if kind == "testable" else "  · "
    print(mark + "[%s] %s — %s" % (rule, name, detail))
    return ok


def sh(*a, timeout=60):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=timeout)


def project_containers():
    out = sh("docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={P}", "--format", "{{.Names}}").stdout
    return set(out.split())


def nets_and_ips(c):
    out = sh("docker", "inspect", "-f", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}", c)
    return dict(x.split("=", 1) for x in out.stdout.split()) if out.returncode == 0 else None


PY_PROBE = r'''
import socket, sys, json
from concurrent.futures import ThreadPoolExecutor
T = json.loads(sys.argv[1])
def go(t):
    h, p = t
    try:
        s = socket.create_connection((h, p), timeout=1.5); s.close(); return 1
    except Exception:
        return 0
with ThreadPoolExecutor(32) as ex:
    print(json.dumps(list(ex.map(go, [tuple(x) for x in T]))))
'''


def probe(src, targets):
    """[(host, port)] -> [0/1] connect results, executed INSIDE src."""
    has_py = sh("docker", "exec", src, "sh", "-c", "command -v python3").returncode == 0
    if has_py:
        r = sh("docker", "exec", src, "python3", "-c", PY_PROBE, json.dumps(targets), timeout=120)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return None
    script = " ; ".join(f"(nc -z -w 2 {h} {p} >/dev/null 2>&1 && echo 1 || echo 0)" for h, p in targets)
    r = sh("docker", "exec", src, "sh", "-c", script, timeout=180)
    vals = [int(x) for x in r.stdout.split() if x in ("0", "1")]
    return vals if len(vals) == len(targets) else None


def main():
    print("▶ ARC flow-map test (connection attempts) — project=%s env=%s" % (P, ENV))
    ok = True
    # 0 · enumerate
    running = project_containers()
    extra = sorted(running - set(DECLARED))
    ok &= rec("ARC-1", "every container of the project is declared", not extra, "undeclared: %s" % extra if extra else "%d declared" % len(DECLARED))
    actual = {c: nets_and_ips(c) for c in DECLARED}
    missing = [c for c, v in actual.items() if v is None]
    ok &= rec("ARC-1", "every declared container is running", not missing, str(missing) if missing else "all running")
    mism = [f"{c}: {sorted(v)} != {sorted(DECLARED[c])}" for c, v in actual.items() if v is not None and set(v) != DECLARED[c]]
    ok &= rec("ARC-1", "network membership equals the declared map", not mism, "; ".join(mism)[:400] if mism else "match")
    foreign = []
    for n in sorted(set().union(*DECLARED.values())):
        members = sh("docker", "network", "inspect", n, "-f", "{{range $k,$v := .Containers}}{{$v.Name}} {{end}}").stdout.split()
        foreign += [f"{m}@{n}" for m in members if m not in DECLARED]
    ok &= rec("ARC-1", "no outside container attached to an aos-* network", not foreign, str(foreign) if foreign else "none")
    # 1 · default-deny networks
    leaky = []
    for n in sorted(set().union(*DECLARED.values()) - EGRESS_NETS):
        internal = sh("docker", "network", "inspect", n, "-f", "{{.Internal}}").stdout.strip()
        if internal != "true":
            leaky.append(f"{n} (Internal={internal or '?'})")
    ok &= rec("ARC-1", "every non-egress network is internal (default-deny egress)", not leaky, ", ".join(leaky) if leaky else "all internal")
    # 2 + 3 · connection attempts from every container
    plans = {}
    for src, snet in actual.items():
        if snet is None:
            continue
        targets, meta = [], []
        for dst, dnet in actual.items():
            if dst == src or dnet is None:
                continue
            for net, ip in dnet.items():
                if ip:
                    # allowed: a shared network; OR a declared egress gateway reaching an address on an EGRESS network
                    # (that address is routable from outside anyway — e.g. the public edge). Never an internal network.
                    allowed = net in snet or (bool(set(snet) & EGRESS_NETS) and net in EGRESS_NETS)
                    targets.append((ip, PORT[dst])); meta.append(("peer", dst, net, allowed))
        egress_ok = bool(set(snet) & EGRESS_NETS)
        for h, p, kind in OUTSIDE:
            targets.append((h, p)); meta.append((kind, f"{h}:{p}", "", egress_ok))
        plans[src] = (targets, meta)
    with ThreadPoolExecutor(8) as ex:
        results = dict(zip(plans, ex.map(lambda s: probe(s, plans[s][0]), plans)))
    off_map, egress_leaks, reached, unprobed = [], [], set(), []
    for src, (targets, meta) in plans.items():
        res = results.get(src)
        if res is None:
            unprobed.append(src); continue
        for (h, p), (kind, what, net, allowed), got in zip(targets, meta, res):
            if got and kind == "peer":
                reached.add((src, what))
            if got and not allowed:
                (off_map if kind == "peer" else egress_leaks).append(f"{src} → {what}{'@' + net if net else ''} ({h}:{p})")
    ok &= rec("ARC-1", "every container was probed", not unprobed, str(unprobed) if unprobed else f"{len(plans)} sources")
    ok &= rec("ARC-1", "no container reaches another over a network they do not share (incl. routed / published-port paths)",
              not off_map, "; ".join(off_map[:12]) if off_map else "0 off-map connections")
    ok &= rec("ARC-1", "only the declared egress gateways reach the internet or the host",
              not egress_leaks, "; ".join(egress_leaks[:12]) if egress_leaks else
              "egress: " + ", ".join(sorted(c.replace('airawat-ld-', '') for c, v in actual.items() if v and set(v) & EGRESS_NETS)))
    miss = [f"{a}→{b}" for a, b in REQUIRED if (a, b) not in reached]
    ok &= rec("ARC-1", "the platform's required edges are reachable", not miss, str(miss) if miss else "all reachable")
    # rule-specific views of the same evidence
    pg_from = sorted(s.replace("airawat-ld-", "") for s, d in reached if d == "airawat-ld-postgres")
    ok &= rec("ARC-3", "the fact store is reachable only from kernel / network / identity", set(pg_from) <= {"kernel", "network", "identity"}, f"postgres reached from {pg_from}")
    vault_ok = {c.replace("airawat-ld-", "") for c, n in DECLARED.items() if "aos-data-secrets" in n} - {"vault"}
    v_from = sorted(s.replace("airawat-ld-", "") for s, d in reached if d == "airawat-ld-vault")
    ok &= rec("ARC-7", "Vault is reachable only from its declared clients", set(v_from) <= vault_ok, f"vault reached from {v_from}")
    pub = [c for c, n in actual.items() if n and "aos-public" in n]
    ok &= rec("ARC-5", "only the edge (nginx) sits on the public network", pub == ["airawat-ld-nginx"], f"aos-public: {pub}")
    comp = [c for c, n in actual.items() if n and "aos-component" in n]
    ok &= rec("ARC-1", "the component network holds only the broker (kernel)", comp == ["airawat-ld-kernel"], f"aos-component: {comp}")
    rec("ARC-4", "per-service micro-segmentation within the service mesh", False,
        "PLANNED — aos-svc is one shared network (not tested, never ✓)", kind="SKIP_BUILD")
    sha = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    os.makedirs("conformance/results", exist_ok=True)
    json.dump({"env": ENV, "mode": "flowmap", "git_sha": sha, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cases": [{"case": r["name"], "rules": [r["rule"]], "result": r["status"]} for r in RESULTS]},
              open(f"conformance/results/{ENV}-flowmap.json", "w"), indent=1)
    _ev.seal(f"conformance/results/{ENV}-flowmap.json")
    print(("✓ ARC flow-map PASS" if ok else "✗ ARC flow-map FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()

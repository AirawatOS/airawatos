#!/usr/bin/env python3
"""ARC flow-map test (FIX-PLAN L1 slice-1a, step 5) — enumerate ACTUAL container networks and attempt the
forbidden reachabilities; FAIL on any off-map path.

Runs on the HOST (needs `docker inspect` + cross-container probes), unlike conformance/run.py which runs inside
a container. Two layers of proof:
  1. MEMBERSHIP — `docker inspect` each container's networks and assert they equal the DECLARED map. Docker
     network isolation is deterministic from membership: X can reach Y iff they share a network. So the
     membership map IS the flow map.
  2. REACHABILITY — from the membership, assert every FORBIDDEN (src,dst) pair shares NO network, and a few
     ALLOWED pairs do; then confirm with LIVE TCP probes (docker exec) on representative pairs.

Emits conformance/results/<env>-flowmap.json (same schema as run.py --matrix) so build_matrix.py renders the
ARC rows. Exits non-zero on any off-map path. Usage: python3 conformance/flow_map_test.py
"""
import json, os, subprocess, sys, time

ENV = os.environ.get("AOS_ENV", "local-dev")
P = os.environ.get("AOS_LD_PROJECT", "airawatos-localdev")

# DECLARED per-boundary membership (must match docker-compose.dev.yml). container -> set(networks).
DECLARED = {
    "airawat-ld-nginx":         {"aos-edge"},
    "airawat-ld-app-host":      {"aos-edge", "aos-svc", "aos-data-secrets"},
    "airawat-ld-network":       {"aos-edge", "aos-svc", "aos-data-facts", "aos-data-secrets"},
    "airawat-ld-identity":      {"aos-svc", "aos-data-facts", "aos-data-secrets"},
    "airawat-ld-kernel":        {"aos-svc", "aos-data-facts", "aos-data-secrets", "aos-component"},
    "airawat-ld-secrets":       {"aos-svc", "aos-data-secrets"},
    "airawat-ld-filestore":     {"aos-svc"},
    "airawat-ld-model-gateway": {"aos-svc", "aos-data-secrets"},
    "airawat-ld-notify":        {"aos-svc"},
    "airawat-ld-workflow":      {"aos-svc"},
    "airawat-ld-decision":      {"aos-svc"},
    "airawat-ld-automation":    {"aos-svc", "aos-data-secrets"},
    "airawat-ld-event-relay":   {"aos-svc", "aos-data-secrets"},
    "airawat-ld-scheduler":     {"aos-svc", "aos-data-secrets"},
    "airawat-ld-postgres":      {"aos-data-facts"},
    "airawat-ld-vault":         {"aos-data-secrets"},
}
PORT = {"airawat-ld-kernel": 8080, "airawat-ld-postgres": 5432, "airawat-ld-vault": 8200,
        "airawat-ld-secrets": 8102, "airawat-ld-app-host": 8099, "airawat-ld-network": 8090}
DNS = {  # container -> its service DNS alias
    "airawat-ld-kernel": "kernel", "airawat-ld-postgres": "postgres", "airawat-ld-vault": "vault",
    "airawat-ld-secrets": "secrets", "airawat-ld-app-host": "app-host", "airawat-ld-network": "network",
}

RESULTS = []
def rec(rule, name, ok, detail, kind="testable"):
    RESULTS.append({"spec": "ARCHITECTURE", "rule": rule, "name": name,
                    "status": ("PASS" if ok else "FAIL") if kind == "testable" else kind,
                    "detail": detail})
    print(("  ✓ " if ok else "  ✗ ") + "[%s] %s — %s" % (rule, name, detail))
    return ok

def inspect_nets(c):
    try:
        out = subprocess.run(["docker", "inspect", "-f",
                              "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}", c],
                             capture_output=True, text=True, timeout=10)
        return set(out.stdout.split()) if out.returncode == 0 else None
    except Exception:
        return None

def shares_net(a, b, actual):
    return bool(actual.get(a, set()) & actual.get(b, set()))

def main():
    print("▶ ARC flow-map test — project=%s env=%s" % (P, ENV))
    ok_all = True
    actual = {c: inspect_nets(c) for c in DECLARED}

    # (1) MEMBERSHIP — each container's actual networks == declared.
    mism = []
    for c, want in DECLARED.items():
        got = actual.get(c)
        if got is None:
            mism.append("%s: not running" % c)
        elif got != want:
            mism.append("%s: actual %s != declared %s" % (c, sorted(got), sorted(want)))
    ok_all &= rec("ARC-1", "container network membership matches the declared map",
                  not mism, "all 16 on-map" if not mism else "OFF-MAP: " + "; ".join(mism))

    # (2) REACHABILITY (derived from membership). FORBIDDEN pairs must share NO network.
    edge_forbidden = ["airawat-ld-kernel", "airawat-ld-postgres", "airawat-ld-vault", "airawat-ld-secrets",
                      "airawat-ld-scheduler", "airawat-ld-model-gateway", "airawat-ld-workflow",
                      "airawat-ld-decision", "airawat-ld-notify", "airawat-ld-automation",
                      "airawat-ld-event-relay", "airawat-ld-filestore"]
    bad = [d for d in edge_forbidden if shares_net("airawat-ld-nginx", d, actual)]
    ok_all &= rec("ARC-5", "the edge (nginx) reaches no internal service or data store",
                  not bad, "edge isolated from %d internal targets" % len(edge_forbidden)
                  if not bad else "edge SHARES a net with: " + ", ".join(bad))

    facts_allowed = {"airawat-ld-postgres", "airawat-ld-kernel", "airawat-ld-network", "airawat-ld-identity"}
    leak = [c for c in DECLARED if c not in facts_allowed and shares_net(c, "airawat-ld-postgres", actual)]
    ok_all &= rec("ARC-3", "the fact store (postgres) is reachable only by kernel/network/identity",
                  not leak, "facts restricted to the 3 DB-role holders"
                  if not leak else "postgres ALSO reachable by: " + ", ".join(leak))

    pure_compute = ["airawat-ld-notify", "airawat-ld-workflow", "airawat-ld-decision",
                    "airawat-ld-filestore", "airawat-ld-nginx"]
    vleak = [c for c in pure_compute if shares_net(c, "airawat-ld-vault", actual)]
    ok_all &= rec("ARC-7", "Vault is not reachable by pure-compute services or the edge",
                  not vleak, "vault closed to pure-compute + edge"
                  if not vleak else "vault reachable by: " + ", ".join(vleak))

    comp_members = [c for c, nets in actual.items() if nets and "aos-component" in nets]
    ok_all &= rec("ARC-1", "the component net is broker-only (kernel is its only service member)",
                  comp_members == ["airawat-ld-kernel"],
                  "aos-component members = %s" % comp_members)

    # ARC-4 (per-service micro-segmentation inside the svc mesh) is a later refinement — recorded, not asserted.
    rec("ARC-4", "per-service micro-segmentation within the svc mesh (declared calls: only)",
        True, "svc mesh is one shared network today; per-service ACLs are a later slice", kind="SKIP_BUILD")

    # (3) LIVE probes — confirm membership⇒reachability on representative pairs (python containers).
    def probe(src, dst):
        host, port = DNS[dst], PORT[dst]
        code = ("import socket,sys\ntry: socket.create_connection(('%s',%d),2); print('R')\n"
                "except Exception: print('B')") % (host, port)
        try:
            r = subprocess.run(["docker", "exec", src, "python3", "-c", code],
                               capture_output=True, text=True, timeout=12)
            return "R" in r.stdout
        except Exception:
            return None
    live = []
    for src, dst, want in [("airawat-ld-notify", "airawat-ld-postgres", False),
                           ("airawat-ld-notify", "airawat-ld-vault", False),
                           ("airawat-ld-model-gateway", "airawat-ld-postgres", False),
                           ("airawat-ld-app-host", "airawat-ld-kernel", True),
                           ("airawat-ld-kernel", "airawat-ld-postgres", True)]:
        got = probe(src, dst)
        if got is None:
            live.append("%s->%s: unprobeable" % (src, dst)); continue
        if got != want:
            live.append("%s->%s: %s (want %s)" % (src, dst, "reachable" if got else "blocked",
                                                  "reachable" if want else "blocked"))
    ok_all &= rec("ARC-1", "live reachability probes match the membership map",
                  not live, "5/5 probes as expected" if not live else "MISMATCH: " + "; ".join(live))

    # emit matrix results
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(d, exist_ok=True)
    out = {"env": ENV, "mode": "flowmap", "base": "docker-host",
           "git_sha": os.environ.get("GIT_SHA", ""),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "cases": [{"case": r["name"], "spec": r["spec"], "rule": r["rule"],
                      "rules": [r["rule"]], "mode": "flowmap", "result": r["status"]} for r in RESULTS]}
    with open(os.path.join(d, "%s-flowmap.json" % ENV), "w") as f:
        json.dump(out, f, indent=2)
    print(("✓ ARC flow-map PASS" if ok_all else "✗ ARC flow-map FAILED — off-map path above"))
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()

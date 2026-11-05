#!/usr/bin/env python3
"""AirawatOS performance harness (Consolidation phase 4) — measurement only, no service changes.

Times each budgeted operation over N iterations against the LOCAL-DEV stack, computes p50/p95, and compares
to the budgets in docs/performance/PERFORMANCE-BUDGETS.md. Operations the bedrock stack cannot exercise are
reported BLOCKED with the reason, never faked.

Run INSIDE the app-host container (it has reference/ on the path for svc_token/hostcore, the Vault env, and
network reach to every service):

    docker cp perf/run.py airawat-ld-app-host:/tmp/perf_run.py
    docker exec airawat-ld-app-host python3 /tmp/perf_run.py            # or: N=100 python3 /tmp/perf_run.py

Results are INDICATIVE (single arm64 laptop, co-located services, near-empty registry) — not production SLOs.
"""
import json, os, sys, time, statistics, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/app/reference")
try:
    import svc_token, hostcore
except Exception as e:  # pragma: no cover
    svc_token = hostcore = None
    print("WARN: could not import svc_token/hostcore (%s) — token-dependent ops will be BLOCKED" % e)

KERN = os.environ.get("AIRAWAT_API", "http://kernel:8080")
IDN = os.environ.get("IDENTITY_URL", "http://identity:8093")
SCHED = os.environ.get("SCHEDULER_URL", "http://scheduler:8103")
FS = os.environ.get("FILESTORE_URL", "http://filestore:8095")
AUTO = os.environ.get("AUTOMATION_URL", "http://automation:8098")
VADDR = (os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/")
VTOK = os.environ.get("VAULT_TOKEN") or ""
AUD = os.environ.get("IDENTITY_AUDIENCE", "airawatos-localdev")
N = int(os.environ.get("N", "50"))

# Budgets (p95 ms) from docs/performance/PERFORMANCE-BUDGETS.md — the pass/fail gate is p95.
BUDGET_P95 = {
    "login": 400, "svctoken_mint": 150,
    "authz_uncached": 60, "authz_cached": 8,
    "write": 80, "read_by_id": 25, "query": 150, "point_in_time": 80,
    "audit_verify_10k": 800, "consent_personal_read": 90,
    "scheduler_dispatch": 100, "automation_event": 80,
    "file_upload_1mb": 150, "file_download_1mb": 80,
}


def _req(method, url, body=None, headers=None, data=None, timeout=30):
    b = data if data is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url, data=b, headers=dict(headers or {}), method=method)
    t = time.perf_counter()
    try:
        resp = urllib.request.urlopen(r, timeout=timeout).read()
        return (time.perf_counter() - t) * 1000.0, 200, resp
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - t) * 1000.0, e.code, e.read()[:120]
    except Exception as e:
        return (time.perf_counter() - t) * 1000.0, "ERR", str(e)[:120].encode()


def _pctl(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


def _vault_pw(path):
    if not VTOK:
        return None
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{VADDR}/v1/{path}", headers={"X-Vault-Token": VTOK}), timeout=8).read() or b"{}")
        return (((d.get("data") or {}).get("data") or {}).get("password"))
    except Exception:
        return None


RESULTS = []  # (op, p50, p95, status, note)


def bench(op, fn, iters=None, warmup=1):
    iters = iters or N
    for _ in range(warmup):
        try: fn()
        except Exception: pass
    samples, bad = [], None
    for _ in range(iters):
        try:
            ms, code, _ = fn()
            if code == 200:
                samples.append(ms)
            else:
                bad = code
        except Exception as e:
            bad = str(e)[:60]
    if not samples:
        RESULTS.append((op, None, None, "BLOCKED", "no 200s (last=%s)" % bad)); return
    p50, p95 = _pctl(samples, 50), _pctl(samples, 95)
    budget = BUDGET_P95.get(op)
    status = "PASS" if (budget and p95 <= budget) else ("FAIL" if budget else "—")
    note = "n=%d%s" % (len(samples), "" if bad is None else "; some non-200 (%s)" % bad)
    RESULTS.append((op, round(p50, 1), round(p95, 1), status, note))


CONC_RESULTS = []  # (op, clients, p50, p95, throughput_per_s, ok, bad)
CONC_LEVELS = [int(x) for x in os.environ.get("CONC_LEVELS", "10,50,100").split(",")]
CONC_REQS = int(os.environ.get("CONC_REQS", "300"))   # total requests fired per (op, level)


def bench_concurrent(op, fn):
    """Fire CONC_REQS requests across `clients` worker threads for each level in CONC_LEVELS; report p50/p95 of
    per-request latency and achieved throughput (completed 200s / wall-clock). A blocking urllib call per thread
    is a fair single-node client model here (no async multiplexing hiding server cost)."""
    for clients in CONC_LEVELS:
        lat, ok, bad = [], 0, 0
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=clients) as ex:
            for ms, code in ex.map(lambda _: fn()[:2], range(CONC_REQS)):
                if code == 200:
                    lat.append(ms); ok += 1
                else:
                    bad += 1
        wall = time.perf_counter() - t0
        thr = ok / wall if wall else 0
        CONC_RESULTS.append((op, clients, round(_pctl(lat, 50) or 0, 1), round(_pctl(lat, 95) or 0, 1),
                             round(thr, 0), ok, bad))


def main():
    cp = svc_token.token("component-publisher", "localdev-network", AUD) if svc_token else None
    cp_h = {"Authorization": "Bearer " + cp} if cp else {}

    # 1) login (platauth@localdev-network) — password hash + token sign
    pw = _vault_pw("secret/data/localdev-network/platauth/password")
    if pw:
        body = {"username": "platauth", "tenant": "localdev-network", "password": pw}
        bench("login", lambda: _req("POST", IDN + "/login", body, {"Content-Type": "application/json"}))
    else:
        RESULTS.append(("login", None, None, "BLOCKED", "no platauth password in Vault"))

    # 2) service-token mint — full Vault read + /login, cache cleared each iter
    if svc_token:
        def mint():
            svc_token._CACHE.pop(("component-publisher", "localdev-network", AUD), None)
            t = time.perf_counter(); tok = svc_token.token("component-publisher", "localdev-network", AUD)
            return (time.perf_counter() - t) * 1000.0, (200 if tok else "ERR"), b""
        bench("svctoken_mint", mint, iters=min(N, 30))
    else:
        RESULTS.append(("svctoken_mint", None, None, "BLOCKED", "svc_token not importable"))

    # 3) authorization decision — authenticated read (adds the authz decision) vs anon (no authz)
    #    cached = steady-state repeated authenticated read; uncached ≈ authenticated minus anon delta (noted).
    rid_body = {"filter": {"schema": "network.network"}, "limit": 1}
    bench("authz_cached", lambda: _req("POST", KERN + "/v1/registry/resolve", rid_body, dict(cp_h, **{"Content-Type": "application/json"})))
    # uncancached proxy: fresh token each iteration forces re-auth of the principal
    if svc_token:
        def authz_uncached():
            svc_token._CACHE.pop(("component-publisher", "localdev-network", AUD), None)
            tok = svc_token.token("component-publisher", "localdev-network", AUD)
            return _req("POST", KERN + "/v1/registry/resolve", rid_body, {"Authorization": "Bearer " + (tok or ""), "Content-Type": "application/json"})
        bench("authz_uncached", authz_uncached, iters=min(N, 30))
    else:
        RESULTS.append(("authz_uncached", None, None, "BLOCKED", "svc_token not importable"))

    # 4) Kernel record WRITE (own-tenant platform schema)
    import time as _t
    def write_op():
        oid = "ds:localdev-network:platform/perf_probe/%d" % int(_t.time() * 1e6)
        obj = {"schema": "platform.perf_probe", "id": oid, "tenant": "localdev-network", "note": "perf"}
        return _req("POST", KERN + "/v1/registry/objects", {"id": oid, "object": obj}, dict(cp_h, **{"Content-Type": "application/json"}))
    bench("write", write_op, iters=min(N, 30))

    # 5) read by id — resolve a seeded perf.pit id (localdev-network-stewarded → visible to cp) against the
    #    ~1M-row table, so the rv_live index lookup is exercised at volume (see perf/seed.py).
    PIT_ID = "ds:localdev-network:perf.pit/pit-0"
    rbody = {"filter": {"id": PIT_ID}, "limit": 1}
    bench("read_by_id", lambda: _req("POST", KERN + "/v1/registry/resolve", rbody, dict(cp_h, **{"Content-Type": "application/json"})))

    # 6) query — schema-filtered on a seeded schema (rv_live_schema_id pushdown against the ~1M-row table)
    bench("query", lambda: _req("POST", KERN + "/v1/registry/query", {"filter": {"schema": "perf.pit"}, "limit": 100}, dict(cp_h, **{"Content-Type": "application/json"})))

    # 7) point-in-time / history of a seeded perf.pit id (6 versions; owner-gated, cp owns the steward tenant)
    PIT_HIST = KERN + "/v1/registry/objects/" + urllib.parse.quote(PIT_ID, safe="") + "/history"
    bench("point_in_time", lambda: _req("GET", PIT_HIST, headers=cp_h))

    # 8) audit-chain verify / 10k — measured out-of-band by the kernel tool (tools/audit_verify.py), not an HTTP
    #    op; the harness records the tool's number in the budgets doc. Still no black-box HTTP endpoint.
    RESULTS.append(("audit_verify_10k", None, None, "N/A-TOOL", "measured by kernel/tools/audit_verify.py (see budgets doc); not an HTTP op"))

    # 9) consent check personal read — enforcement not built
    RESULTS.append(("consent_personal_read", None, None, "BLOCKED", "consent enforcement + D10 personal-read path not built (ADR-0125/0127 PLANNED)"))

    # 10) scheduler dispatch — /reload (gate + handler), svc:scheduler
    if hostcore:
        def sdispatch():
            tok = hostcore.scheduler_token()
            return _req("POST", SCHED + "/reload", {}, {"Authorization": "Bearer " + (tok or ""), "Content-Type": "application/json"})
        bench("scheduler_dispatch", sdispatch)
    else:
        RESULTS.append(("scheduler_dispatch", None, None, "BLOCKED", "hostcore not importable"))

    # 11) automation event — POST /events, svc:automation (scheduler principal holds that audience)
    if svc_token:
        def aevent():
            tok = svc_token.token("scheduler", "localdev-operator", "svc:automation")
            return _req("POST", AUTO + "/events", {"type": "perf.probe", "id": "p"}, {"Authorization": "Bearer " + (tok or ""), "Content-Type": "application/json"})
        bench("automation_event", aevent)
    else:
        RESULTS.append(("automation_event", None, None, "BLOCKED", "svc_token not importable"))

    # 12) file upload / download — 1 MB, svc:filestore (shadow gate)
    if hostcore:
        blob = os.urandom(1024 * 1024)
        up_fid = {}
        def upload():
            tok = hostcore.filestore_token()
            ms, code, body = _req("POST", FS + "/files", data=blob,
                                  headers={"Authorization": "Bearer " + (tok or ""), "Content-Type": "application/octet-stream"})
            if code == 200 or code == 201:
                try: up_fid["id"] = json.loads(body).get("id")
                except Exception: pass
                return ms, 200, body
            return ms, code, body
        bench("file_upload_1mb", upload, iters=min(N, 30))
        fid = up_fid.get("id")
        if fid:
            def download():
                tok = hostcore.filestore_token()
                return _req("GET", FS + "/files/" + urllib.parse.quote(fid, safe=":"), headers={"Authorization": "Bearer " + (tok or "")})
            bench("file_download_1mb", download, iters=min(N, 30))
        else:
            RESULTS.append(("file_download_1mb", None, None, "BLOCKED", "upload produced no file id"))
    else:
        RESULTS.append(("file_upload_1mb", None, None, "BLOCKED", "hostcore not importable"))
        RESULTS.append(("file_download_1mb", None, None, "BLOCKED", "hostcore not importable"))

    # report
    print("\nAirawatOS perf harness — local-dev (INDICATIVE, arm64 laptop, N=%d)\n" % N)
    print("%-24s %8s %8s %10s  %-6s  %s" % ("operation", "p50(ms)", "p95(ms)", "budget95", "result", "note"))
    print("-" * 100)
    for op, p50, p95, status, note in RESULTS:
        b = BUDGET_P95.get(op, "")
        print("%-24s %8s %8s %10s  %-6s  %s" % (op, p50 if p50 is not None else "-", p95 if p95 is not None else "-", b, status, note))
    fails = [r[0] for r in RESULTS if r[3] == "FAIL"]
    blocked = [r[0] for r in RESULTS if r[3] == "BLOCKED"]
    print("\nPASS: %d   FAIL: %d %s   BLOCKED: %d %s" % (
        sum(1 for r in RESULTS if r[3] == "PASS"), len(fails), fails or "", len(blocked), blocked or ""))

    # --- concurrency pass: core read-path ops under 10/50/100 parallel clients -------------------------------
    print("\nConcurrency pass — %d requests per (op, level), levels %s\n" % (CONC_REQS, CONC_LEVELS))
    conc_ops = [
        ("authz_cached", lambda: _req("POST", KERN + "/v1/registry/resolve", rid_body, dict(cp_h, **{"Content-Type": "application/json"}))),
        ("read_by_id", lambda: _req("POST", KERN + "/v1/registry/resolve", rbody, dict(cp_h, **{"Content-Type": "application/json"}))),
        ("query", lambda: _req("POST", KERN + "/v1/registry/query", {"filter": {"schema": "perf.pit"}, "limit": 100}, dict(cp_h, **{"Content-Type": "application/json"}))),
        ("point_in_time", lambda: _req("GET", PIT_HIST, headers=cp_h)),
    ]
    for op, fn in conc_ops:
        bench_concurrent(op, fn)
    print("%-16s %8s %8s %8s %12s %8s %6s" % ("operation", "clients", "p50(ms)", "p95(ms)", "thrpt(/s)", "ok", "bad"))
    print("-" * 74)
    for op, clients, p50, p95, thr, ok, bad in CONC_RESULTS:
        print("%-16s %8d %8s %8s %12s %8d %6d" % (op, clients, p50, p95, int(thr), ok, bad))
    print("\n(Concurrency numbers are INDICATIVE: single arm64 laptop, all services + Postgres co-located, no "
          "network latency. Tail growth with clients is the signal, not the absolute p95.)")


if __name__ == "__main__":
    import urllib.parse  # noqa (used above)
    main()

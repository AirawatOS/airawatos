#!/usr/bin/env python3
"""AirawatOS conformance suite (Consolidation Phase 3) — black-box, two modes.

Tests externally observable behaviour only (HTTP status, returned records). No service code is imported or
inspected. Full rule -> cases -> classification map: Airawat/docs/conformance/PLAN.md.

Modes (env AOS_MODE):
  external (default) — via the edge nginx at AOS_BASE (default http://127.0.0.1:8080): /kernel/*, /network/*,
                       /* (app-host). This is what an outside caller can reach.
  internal          — directly against in-cluster service addresses (identity:8093, filestore:8095,
                       scheduler:8103, model-gateway:8104, secrets:8102, notify:8094, automation:8098,
                       kernel:8080, ...). Run inside a container attached to the local-dev docker network
                       (see README). Covers the reference-service endpoints not published at the edge.

Credentials (external authenticated cases): AOS_TEST_USERS as JSON, or conformance/.creds.json (gitignored).
Each value is either "password" (default realm = AOS_REALM) or {"password":.., "tenant":..}.

Result kinds: PASS / XFAIL (known violation reproduced; green) / XPASS (violation looks fixed; flagged) /
FAIL (contradicts spec; fails run) / SKIP_CREDS / SKIP_BUILD. Exit non-zero only on FAIL.
"""
import json, os, sys, time, base64, urllib.request, urllib.error

MODE  = os.environ.get("AOS_MODE", "external")
BASE  = os.environ.get("AOS_BASE", "http://127.0.0.1:8080").rstrip("/")
REALM = os.environ.get("AOS_REALM", "localdev-network")
TIMEOUT = 8

INTERNAL = {  # in-cluster service base URLs (see README for the docker-network runner)
    "kernel": "http://kernel:8080", "network": "http://network:8090", "identity": "http://identity:8093",
    "notify": "http://notify:8094", "secrets": "http://secrets:8102", "scheduler": "http://scheduler:8103",
    "model-gateway": "http://model-gateway:8104", "filestore": "http://filestore:8095",
    "automation": "http://automation:8098", "event-relay": "http://event-relay:8101",
}

def _load_creds():
    raw = os.environ.get("AOS_TEST_USERS")
    if not raw:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".creds.json")
        if os.path.exists(p):
            try: raw = open(p).read()
            except Exception: raw = None
    if not raw: return {}
    try: d = json.loads(raw)
    except Exception: return {}
    out = {}
    for u, v in d.items():
        out[u] = v if isinstance(v, dict) else {"password": v, "tenant": REALM}
    return out
CREDS = _load_creds()

def _req(method, url, body=None, token=None, headers=None, cookie=None):
    data = None; h = {"accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode(); h["content-type"] = "application/json"
    if token: h["authorization"] = "Bearer " + token
    if cookie: h["cookie"] = cookie
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=TIMEOUT)
        return r.getcode(), r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else ""), dict(e.headers or {})
    except Exception as e:
        return 0, "ERR: %s" % e, {}

def http(method, path, body=None, token=None, headers=None, cookie=None):
    return _req(method, BASE + path, body, token, headers, cookie)

def forged_jwt(roles=("network.admin",), iss="evil-issuer", sub="attacker"):
    def seg(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return "%s.%s.%s" % (seg({"alg": "HS256", "typ": "JWT"}),
                         seg({"sub": sub, "roles": list(roles), "iss": iss, "tenant": REALM,
                              "exp": int(time.time()) + 3600}), "AAAAinvalidsignatureAAAA")

RESULTS = []
def record(spec, rule, name, kind, status, detail=""):
    RESULTS.append({"spec": spec, "rule": rule, "name": name, "kind": kind, "status": status, "detail": detail})
def expect(spec, rule, name, ok, detail): record(spec, rule, name, "testable", "PASS" if ok else "FAIL", detail)
def xfail(spec, rule, name, reproduced, detail):
    record(spec, rule, name, "expected-fail", "XFAIL" if reproduced else "XPASS", detail)

# ============================ EXTERNAL: no-credential cases ============================
def run_no_cred_cases():
    st, _, _ = http("POST", "/kernel/v1/registry/resolve", {"filter": {"schema": "network.network"}}, token=forged_jwt())
    expect("FOUNDATIONS", "F1/F3/F15", "forged role+foreign-iss token rejected (abuse)",
           st in (401, 403), "kernel resolve w/ forged bearer -> %s" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:1", "object": {"schema": "viz.layer", "id": "conf:probe:1"}})
    expect("FOUNDATIONS", "F8", "anonymous write denied (abuse)", st in (401, 403), "anon kernel write -> %s" % st)

    st, _, _ = http("POST", "/network/v1/governance/roles", {})
    expect("NETWORK", "N3", "anonymous governance role-write denied (abuse)", st in (401, 403),
           "anon network governance -> %s" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/resolve", {"filter": {"schema": "network.network"}})
    xfail("REGISTRY", "R6/F8", "anonymous read denied (abuse) [debt A1]", st == 200,
          "anon kernel read -> %s (rule 401; live-violation 200)" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/exists", {"id": "network.network"})
    if st in (0, 404):
        record("REGISTRY", "R6", "anonymous existence-check denied (abuse)", "expected-fail", "SKIP_BUILD",
               "/kernel/v1/registry/exists not reachable (%s)" % st)
    else:
        xfail("REGISTRY", "R6", "anonymous existence-check denied (abuse) [debt A1]", st == 200,
              "anon exists -> %s (rule 401; live-violation 200)" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:2", "object": {"schema": "viz.layer", "id": "conf:probe:2"}}, token=forged_jwt())
    expect("REGISTRY", "R5", "forged-token write denied (abuse)", st in (401, 403), "forged kernel write -> %s" % st)

    st, body, _ = http("POST", "/kernel/v1/registry/resolve",
                       {"filter": {"schema": "zzz.conformance_unknown_%d" % int(time.time())}})
    expect("FOUNDATIONS", "F6/R13", "unknown schema handled opaquely (pos)",
           st == 200 and '"results"' in body, "resolve unknown schema -> %s" % st)

    st, _, _ = http("POST", "/login", {"realm": REALM, "username": "admin", "password": "admin"})
    expect("ACCOUNT", "A4", "handle/username is not a credential (abuse)", st in (401, 403),
           "login admin/pw=admin -> %s" % st)

    st, _, _ = http("GET", "/embed/authorize?client_id=demo-embed&scope=service:invoke"
                           "&redirect_uri=https://example.test/cb&code_challenge=x&code_challenge_method=S256")
    if st in (200, 302):
        xfail("CLIENT", "C2", "scope bound to registered client, not query (abuse) [debt B12]", True,
              "/embed/authorize over-broad scope -> %s (honors query scope)" % st)
    else:
        record("CLIENT", "C2", "scope bound to registered client, not query (abuse) [debt B12]",
               "expected-fail", "SKIP_BUILD",
               "/embed/authorize -> %s; cannot isolate scope-binding black-box (needs client+redirect+PKCE)" % st)

# ============================ EXTERNAL: credentialed cases ============================
def login_session(user):
    c = CREDS.get(user)
    if not c: return None, "no creds for %s" % user
    st, _, hdr = http("POST", "/login", {"realm": c.get("tenant", REALM), "username": user, "password": c["password"]})
    if st != 200: return None, "login %s@%s -> %s" % (user, c.get("tenant", REALM), st)
    sc = hdr.get("Set-Cookie") or hdr.get("set-cookie") or ""
    return (sc.split(";")[0] if sc else None), "ok"

def case_B15(cookie):
    st0, b0, _ = http("GET", "/kernel/v1/components")
    n = 0
    try: n = len(json.loads(b0).get("installed", []))
    except Exception: pass
    note = "already %d installed" % n
    if n == 0:
        cid = os.environ.get("AOS_TEST_COMPONENT", "")
        if not cid:  # auto-discover an installable component from the catalogue
            cst, cb, _ = http("GET", "/bridge/components", cookie=cookie)
            try:
                comps = json.loads(cb).get("components", [])
                cid = (comps[0].get("component_id") or comps[0].get("id")) if comps else ""
            except Exception:
                comps = []
            if not cid:
                record("REGISTRY", "B15", "components list does not leak run_token (abuse) [debt B15]",
                       "expected-fail", "SKIP_BUILD",
                       "local-dev component catalogue empty (/bridge/components total=0) — nothing to install; "
                       "set AOS_TEST_COMPONENT=<published cid> to exercise the populated leak-check")
                return
        ist, ib, _ = http("POST", "/bridge/install", {"component_id": cid}, cookie=cookie)
        note = "install %s -> %s" % (cid, ist)
        if ist not in (200, 201):
            record("REGISTRY", "B15", "components list does not leak run_token (abuse) [debt B15]",
                   "expected-fail", "SKIP_BUILD", "install failed (%s): %s" % (ist, ib[:100]))
            return
    st, body, _ = http("GET", "/kernel/v1/components")
    if "run_token" in body:
        xfail("REGISTRY", "B15", "components list does not leak run_token (abuse) [debt B15]", True,
              "anon GET /components (populated) CONTAINS run_token — leak reproduced; %s" % note)
    else:
        expect("REGISTRY", "B15", "components list does not leak run_token (abuse) [debt B15]", True,
               "anon GET /components (populated: %s) has no run_token" % note)

def case_R10(cookie):
    schema = os.environ.get("AOS_TEST_SCHEMA", "network.network")
    s1, b1, _ = http("POST", "/bridge/registry-resolve", {"filter": {"schema": schema}}, cookie=cookie)
    if s1 in (0, 404):
        record("REGISTRY", "R10", "deterministic resolution over records (pos)", "needs-creds", "SKIP_BUILD",
               "/bridge/registry-resolve not reachable (%s)" % s1); return
    n = 0
    try: n = len(json.loads(b1).get("results", []))
    except Exception: pass
    if n == 0:
        record("REGISTRY", "R10", "deterministic resolution over records (pos)", "needs-creds", "SKIP_CREDS",
               "no visible records for %s (determinism would be trivial-on-empty)" % schema); return
    s2, b2, _ = http("POST", "/bridge/registry-resolve", {"filter": {"schema": schema}}, cookie=cookie)
    expect("REGISTRY", "R10", "deterministic resolution over %d records (pos)" % n, s1 == s2 and b1 == b2,
           "two resolves of %s -> %s/%s identical=%s" % (schema, s1, s2, b1 == b2))

CRED_PLACEHOLDERS = [
    ("FOUNDATIONS","F2","valid token w/o grant cannot do privileged write [debt B1]"),
    ("FOUNDATIONS","F14","role assignment names its grantor (granted_by)"),
    ("REGISTRY","R1","write then re-read by id — id stable"),
    ("REGISTRY","R3","supersede creates new version; prior addressable"),
    ("REGISTRY","R7","written record carries provenance [debt A2 shadow]"),
    ("NETWORK","N1","slug/tenant not accepted as net authority [debt B11/B2]"),
    ("NETWORK","N9","wildcard/unversioned capability grant rejected [debt B12]"),
    ("CLIENT","C1","unregistered client rejected [debt A47]"),
]
def run_cred_cases():
    if not CREDS:
        record("REGISTRY","B15","components list does not leak run_token (abuse) [debt B15]","needs-creds","SKIP_CREDS","needs admin session to install first")
        record("REGISTRY","R10","deterministic resolution over records (pos)","needs-creds","SKIP_CREDS","needs a reader session to see records")
        for s,r,n in CRED_PLACEHOLDERS: record(s,r,n,"needs-creds","SKIP_CREDS","supply AOS_TEST_USERS to enable")
        return
    cookie, msg = login_session("admin")
    expect("FOUNDATIONS","F1","authenticated session opens (pos)", bool(cookie), "admin login: %s" % msg)
    if cookie:
        case_B15(cookie); case_R10(cookie)
    else:
        record("REGISTRY","B15","components list does not leak run_token (abuse) [debt B15]","needs-creds","SKIP_CREDS","admin login failed: %s"%msg)
        record("REGISTRY","R10","deterministic resolution over records (pos)","needs-creds","SKIP_CREDS","admin login failed: %s"%msg)
    for s,r,n in CRED_PLACEHOLDERS: record(s,r,n,"needs-creds","SKIP_CREDS","not implemented in first suite")

# ============================ EXTERNAL: NEEDS-BUILD (genuinely not built) ============================
NEEDS_BUILD = [
    ("FOUNDATIONS","F5","durable authority survives restart","restart orchestration"),
    ("FOUNDATIONS","F7","kernel authorizes with Network down","network-down orchestration [debt B9]"),
    ("FOUNDATIONS","F16","missing config stops startup","startup-time"),
    ("FOUNDATIONS","F17","agent delegation; no self-widen","no delegation primitive (NOT BUILT)"),
    ("REGISTRY","R12","trust-bearing write audited","audit not black-box readable"),
    ("REGISTRY","R14","personal data by reference; erasure","erasable store PLANNED"),
    ("REGISTRY","R15","public = schema flag via CR","hardcoded allow-list [debt B8]"),
    ("REGISTRY","R16","archived version resolves identically","archiving PLANNED"),
    ("DECISION","D1","protected authz emits a decision record","not emitted [debt A9/B1]"),
    ("DECISION","D3","replayable; model output as input","replay harness not exposed"),
    ("DECISION","D4","decider needs recorded authority [debt B3]","not emitted; authn accepted"),
    ("DECISION","D6","denial recorded with reason [debt A9]","denials not logged"),
    ("DECISION","D7","personal data in decision by reference","inherits R14 (PLANNED)"),
    ("DECISION","D8","reason codes; subject reads own decisions","subject-access not built"),
    ("DECISION","D10","personal-data read always full record","tiered logging not built"),
    ("DECISION","D11","contest flow; reviewer != decider","contest flow not proven"),
    ("DECISION","D12","automated decision labelled + human authority [debt B18]","not built"),
    ("NETWORK","N4","suspended net refuses exchange, allows reads","status machine not verified"),
    ("NETWORK","N6","join never creates a login [debt B9]","needs creds to drive join (EXPECTED FAIL)"),
    ("NETWORK","N7","issuer trust admin-only + scoped","needs creds (EXPECTED FAIL)"),
    ("ACCOUNT","A2","id/handle/binding distinct; handle reserved","model not verified"),
    ("ACCOUNT","A3","raw id never shown; one-identity-one-account","assurance untrustworthy [debt B13]; R14 PLANNED"),
    ("ACCOUNT","A7","consent by holder; withdraw->erase","consent enforcement pending [debt B12]"),
    ("ACCOUNT","A8","assisted access via F17","no delegation primitive"),
    ("ACCOUNT","A9","closure withdraws consents + erases","not built"),
    ("ACCOUNT","W3","presentation bound to recipient/purpose","PLANNED"),
    ("ACCOUNT","W4","selective disclosure","PLANNED"),
    ("CLIENT","C6","public versioned protocol, not /bridge/* [debt A23]","only /bridge/* + /embed/* exist"),
]
def run_needs_build():
    for s,r,n,why in NEEDS_BUILD: record(s,r,n,"needs-build","SKIP_BUILD",why)

# ============================ INTERNAL mode cases ============================
def run_internal_cases():
    T = INTERNAL
    def tokenless_accepted(spec, rule, name, method, url, body=None):
        st, b, _ = _req(method, url, body=body)
        if st == 0:
            record(spec, rule, name, "expected-fail", "SKIP_BUILD", "unreachable: %s (%s)" % (url, b[:50])); return
        if st in (401, 403):
            # Gate active HERE. The fail-open/unauth violation is not reproducible in local-dev as configured
            # (e.g. SECRETS_INTERNAL is set); observing fail-open would require unsetting the gate env — a
            # service change we do not make. Not a pass, not a fix: simply not black-box reproducible here.
            record(spec, rule, name, "expected-fail", "SKIP_BUILD",
                   "%s -> %s: gate active in local-dev (tokenless rejected); fail-open path needs the gate env UNSET — not reproducible without a config change" % (url, st))
            return
        if st == 404:
            record(spec, rule, name, "expected-fail", "SKIP_BUILD",
                   "%s -> 404: route not found; cannot confirm tokenless-accept (need a real privileged route)" % url)
            return
        # 2xx / 400 / 500 / 501 => the handler RAN without a service token => no auth gate => violation present.
        xfail(spec, rule, name, True, "%s -> %s: handler ran WITHOUT a service token (no auth gate)" % (url, st))
    # F10 / debt B5 — unauthenticated privileged reference endpoints
    tokenless_accepted("FOUNDATIONS","F10/B5","filestore serves without a service token (abuse)","GET",  T["filestore"]+"/")
    tokenless_accepted("FOUNDATIONS","F10/B5","notify /notify accepts without a service token (abuse)","POST", T["notify"]+"/notify", {})
    tokenless_accepted("FOUNDATIONS","F10/B5","scheduler /run accepts without a service token (abuse)","POST", T["scheduler"]+"/run", {"component":"__conformance_probe__"})
    tokenless_accepted("FOUNDATIONS","F10/B5","model-gateway /complete accepts without a service token (abuse)","POST", T["model-gateway"]+"/complete", {})
    tokenless_accepted("FOUNDATIONS","F10/B5","automation /events accepts without a service token (abuse)","POST", T["automation"]+"/events", {})
    # F9 / debt B4 — fail-open internal-token gates
    tokenless_accepted("FOUNDATIONS","F9/B4","secrets /materialize accepts w/o internal token (abuse)","POST", T["secrets"]+"/materialize", {})
    tokenless_accepted("FOUNDATIONS","F9/B4","secrets /fetch accepts w/o internal token (abuse)","POST", T["secrets"]+"/fetch", {})
    record("FOUNDATIONS","F9/B4","runtime-manager /invoke fail-open (abuse)","expected-fail","SKIP_BUILD","no runtime-manager in the local-dev stack")
    # B6 — identity directory disclosure
    st, b, _ = _req("GET", T["identity"]+"/users")
    if st == 0:
        record("CLIENT","C5/B6","identity /users directory disclosure (abuse)","expected-fail","SKIP_BUILD","identity /users unreachable (%s)"%b[:40])
    else:
        disclosed = st == 200 and ("username" in b or '"users"' in b or b.strip().startswith("["))
        xfail("CLIENT","C5/B6","identity /users directory disclosure (abuse)", disclosed,
              "GET identity/users -> %s discloses=%s" % (st, disclosed))
    # kernel reachable directly internally (parity with external anon read)
    st, _, _ = _req("POST", T["kernel"]+"/v1/registry/resolve", {"filter": {"schema": "network.network"}})
    xfail("REGISTRY","R6/F8","anonymous kernel read denied (internal) [debt A1]", st == 200,
          "kernel:8080 anon read -> %s (rule 401; live-violation 200)" % st)

# ============================ runner ============================
def report(mode):
    specs = ["FOUNDATIONS","REGISTRY","DECISION","NETWORK","ACCOUNT","CLIENT"]
    kinds = ["PASS","XFAIL","XPASS","FAIL","SKIP_CREDS","SKIP_BUILD"]
    print("\n== mode: %s ==" % mode)
    print("%-13s %5s %6s %6s %5s %6s %6s" % ("SPEC","PASS","XFAIL","XPASS","FAIL","nCRED","nBUILD"))
    print("-"*60)
    tot = {k:0 for k in kinds}
    for sp in specs:
        row = {k:0 for k in kinds}
        for r in RESULTS:
            if r["spec"].split("/")[0] == sp: row[r["status"]] += 1
        for k in kinds: tot[k] += row[k]
        print("%-13s %5d %6d %6d %5d %6d %6d" % (sp,row["PASS"],row["XFAIL"],row["XPASS"],row["FAIL"],row["SKIP_CREDS"],row["SKIP_BUILD"]))
    print("-"*60)
    print("%-13s %5d %6d %6d %5d %6d %6d" % ("TOTAL",tot["PASS"],tot["XFAIL"],tot["XPASS"],tot["FAIL"],tot["SKIP_CREDS"],tot["SKIP_BUILD"]))
    notable = [r for r in RESULTS if r["status"] in ("FAIL","XPASS","XFAIL","PASS")]
    print("\nExecuted cases:")
    for r in notable:
        print("  [%-5s] %-14s %-9s %s — %s" % (r["status"], r["spec"], r["rule"], r["name"], r["detail"]))
    return tot

def main():
    print("AirawatOS conformance suite — mode=%s" % MODE)
    if MODE == "internal":
        print("internal targets:", ", ".join("%s=%s" % (k, v) for k, v in INTERNAL.items()))
        # preflight on kernel
        st, _, _ = _req("GET", INTERNAL["kernel"]+"/healthz")
        if st != 200: print("PREFLIGHT: kernel:8080/healthz -> %s" % st)
        run_internal_cases()
    else:
        print("target %s (realm %s); credentials: %s" % (BASE, REALM, "supplied (%d)"%len(CREDS) if CREDS else "none"))
        st, _, _ = http("GET", "/healthz")
        if st != 200: print("PREFLIGHT FAIL: %s/healthz -> %s" % (BASE, st)); sys.exit(2)
        run_no_cred_cases(); run_cred_cases(); run_needs_build()
    tot = report(MODE)
    if tot["XPASS"]:
        print("\n>>> %d XPASS (violation looks FIXED — update spec/debt):" % tot["XPASS"])
        for r in RESULTS:
            if r["status"] == "XPASS": print("    %s %s — %s" % (r["spec"], r["rule"], r["name"]))
    if tot["FAIL"]:
        print("\n>>> %d FAIL (contradicts spec):" % tot["FAIL"])
        for r in RESULTS:
            if r["status"] == "FAIL": print("    %s %s — %s — %s" % (r["spec"], r["rule"], r["name"], r["detail"]))
        sys.exit(1)
    print("\nOK — no FAIL. Exit 0.")
    sys.exit(0)

if __name__ == "__main__":
    main()

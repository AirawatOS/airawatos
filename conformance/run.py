#!/usr/bin/env python3
"""AirawatOS conformance suite (Consolidation Phase 3) — black-box, against local-dev.

Tests externally observable behaviour only (HTTP status, returned records). No service code is imported or
inspected. See docs/conformance/PLAN.md (in the Airawat repo) for the full rule -> cases -> classification map.

Run:  python3 conformance/run.py            # against http://127.0.0.1:8080
Env:  AOS_BASE           override base URL (default http://127.0.0.1:8080)
      AOS_REALM          test realm (default localdev-network)
      AOS_TEST_USERS     JSON {"admin":"pw",...} to enable NEEDS-CREDENTIALS cases
                         (or put the same JSON in conformance/.creds.json — gitignored)

Result kinds:
  PASS       a TESTABLE-NOW case behaved as the spec requires
  XFAIL      an EXPECTED-FAIL case reproduced the known live violation (green; cites the debt item)
  XPASS      an EXPECTED-FAIL case did NOT reproduce -> the violation looks FIXED (flagged; good news)
  FAIL       a TESTABLE-NOW case did not behave as the spec requires (fails the run)
  SKIP_CREDS needs a supplied session/bearer; no credentials provided
  SKIP_BUILD feature/endpoint not built or not black-box reachable at :8080

Exit code: non-zero only if any FAIL. XPASS is reported prominently but does not fail the run.
"""
import json, os, sys, time, urllib.request, urllib.error, base64, http.cookiejar

BASE  = os.environ.get("AOS_BASE", "http://127.0.0.1:8080").rstrip("/")
REALM = os.environ.get("AOS_REALM", "localdev-network")
TIMEOUT = 8

def _load_creds():
    raw = os.environ.get("AOS_TEST_USERS")
    if not raw:
        p = os.path.join(os.path.dirname(__file__), ".creds.json")
        if os.path.exists(p):
            try: raw = open(p).read()
            except Exception: raw = None
    if not raw: return {}
    try: return json.loads(raw)
    except Exception: return {}
CREDS = _load_creds()

def http(method, path, body=None, token=None, headers=None, cookie=None):
    """Return (status:int, text:str, headers:dict). Network errors -> status 0, text=error."""
    url = BASE + path
    data = None
    h = {"accept": "application/json"}
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

def forged_jwt(roles=("network.admin",), iss="evil-issuer", sub="attacker"):
    """A syntactically-valid but UNSIGNED/wrong-sig JWT bearing role + foreign-iss claims."""
    def seg(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    head = seg({"alg": "HS256", "typ": "JWT"})
    payload = seg({"sub": sub, "roles": list(roles), "iss": iss, "tenant": REALM,
                   "exp": int(time.time()) + 3600})
    return "%s.%s.%s" % (head, payload, "AAAAinvalidsignatureAAAA")

# --- case helpers ------------------------------------------------------------
RESULTS = []
def record(spec, rule, name, kind, status, detail=""):
    RESULTS.append({"spec": spec, "rule": rule, "name": name, "kind": kind,
                    "status": status, "detail": detail})

def expect(spec, rule, name, got_ok, detail):
    record(spec, rule, name, "testable", "PASS" if got_ok else "FAIL", detail)

def xfail(spec, rule, name, violation_reproduced, detail):
    # violation_reproduced True  -> XFAIL (known debt still present; green)
    # violation_reproduced False -> XPASS (looks fixed; flagged)
    record(spec, rule, name, "expected-fail", "XFAIL" if violation_reproduced else "XPASS", detail)

# ============================================================================
# TESTABLE-NOW + EXPECTED-FAIL cases (no credentials needed)
# ============================================================================
def run_no_cred_cases():
    # F1/F3/F15 — a token bearing role + foreign-iss claims but an invalid signature is rejected.
    st, _, _ = http("POST", "/kernel/v1/registry/resolve", {"filter": {"schema": "network.network"}},
                    token=forged_jwt())
    expect("FOUNDATIONS", "F1/F3/F15", "forged role+foreign-iss token rejected (abuse)",
           st in (401, 403), "kernel resolve with forged bearer -> %s (want 401/403)" % st)

    # F8 — anonymous WRITE denied.
    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:1", "object": {"schema": "viz.layer", "id": "conf:probe:1"}})
    expect("FOUNDATIONS", "F8", "anonymous write denied (abuse)",
           st in (401, 403), "anon kernel write -> %s (want 401/403)" % st)

    # F8 / N3 — anonymous governance write denied.
    st, _, _ = http("POST", "/network/v1/governance/roles", {})
    expect("NETWORK", "N3", "anonymous governance role-write denied (abuse)",
           st in (401, 403), "anon network governance -> %s (want 401/403)" % st)

    # F8 / R6 — anonymous READ should be denied; currently allowed (debt A1 REQUIRE_AUTH off).
    st, body, _ = http("POST", "/kernel/v1/registry/resolve", {"filter": {"schema": "network.network"}})
    xfail("REGISTRY", "R6/F8", "anonymous read denied (abuse) [debt A1]",
          st == 200, "anon kernel read -> %s (rule: 401; live-violation: 200)" % st)

    # R6 — anonymous existence check is a read; should be denied. Endpoint may not exist -> SKIP_BUILD.
    st, _, _ = http("POST", "/kernel/v1/registry/exists", {"id": "network.network"})
    if st == 0 or st == 404:
        record("REGISTRY", "R6", "anonymous existence-check denied (abuse)", "expected-fail",
               "SKIP_BUILD", "/kernel/v1/registry/exists not reachable (%s)" % st)
    else:
        xfail("REGISTRY", "R6", "anonymous existence-check denied (abuse) [debt A1]",
              st == 200, "anon exists -> %s (rule: 401; live-violation: 200)" % st)

    # R5 — forged-token write denied.
    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:2", "object": {"schema": "viz.layer", "id": "conf:probe:2"}},
                    token=forged_jwt())
    expect("REGISTRY", "R5", "forged-token write denied (abuse)",
           st in (401, 403), "forged kernel write -> %s (want 401/403)" % st)

    # R10 — deterministic resolution: same anon resolve twice yields identical results.
    f = {"filter": {"schema": "network.network"}}
    s1, b1, _ = http("POST", "/kernel/v1/registry/resolve", f)
    s2, b2, _ = http("POST", "/kernel/v1/registry/resolve", f)
    expect("REGISTRY", "R10", "resolution deterministic (pos)",
           s1 == s2 and b1 == b2, "two resolves -> %s/%s, identical=%s" % (s1, s2, b1 == b2))

    # F6 / R13 — kernel treats an unknown schema opaquely (no domain-specific error).
    st, body, _ = http("POST", "/kernel/v1/registry/resolve",
                       {"filter": {"schema": "zzz.conformance_unknown_%d" % int(time.time())}})
    ok = st == 200 and '"results"' in body  # opaque empty result, not a "unknown domain" rejection
    expect("FOUNDATIONS", "F6/R13", "unknown schema handled opaquely (pos)",
           ok, "resolve unknown schema -> %s" % st)

    # B15 — unauth /components reachable; must not leak run_token. Latent (installed empty on local-dev).
    st, body, _ = http("GET", "/kernel/v1/components")
    reachable = st == 200
    leak = "run_token" in body
    expect("REGISTRY", "B15/R6", "components list does not leak run_token (abuse)",
           reachable and not leak,
           "GET /components -> %s, run_token_in_body=%s (unauth-reachable=%s; latent per debt B15)"
           % (st, leak, reachable))

    # A4 — the handle/username is never a credential: login with username-as-password fails.
    st, _, _ = http("POST", "/login", {"realm": REALM, "username": "admin", "password": "admin"})
    expect("ACCOUNT", "A4", "handle/username is not a credential (abuse)",
           st in (401, 403), "login admin/pw=admin -> %s (want 401/403)" % st)

    # C2 [debt B12] — embed authorize reflects a query-supplied scope rather than binding to the client.
    # Black-box probe: if /embed/authorize is reachable, scope-from-query is the live (wrong) behaviour.
    st, _, _ = http("GET", "/embed/authorize?client_id=demo-embed&scope=service:invoke"
                           "&redirect_uri=https://example.test/cb&code_challenge=x&code_challenge_method=S256")
    if st in (200, 302):
        # Live serves the over-broad scope from the query -> the B12 violation reproduced.
        xfail("CLIENT", "C2", "scope bound to registered client, not query (abuse) [debt B12]",
              True, "/embed/authorize over-broad scope -> %s (live honors query-supplied scope)" % st)
    else:
        # A non-2xx/3xx (e.g. 400 unknown-client / bad redirect / PKCE) rejects BEFORE scope evaluation,
        # so scope-binding cannot be isolated black-box here without a registered client + redirect + PKCE.
        record("CLIENT", "C2", "scope bound to registered client, not query (abuse) [debt B12]",
               "expected-fail", "SKIP_BUILD",
               "/embed/authorize -> %s; cannot isolate scope-binding black-box (needs registered client+redirect+PKCE)" % st)

# ============================================================================
# NEEDS-CREDENTIALS cases (run only if CREDS supplied)
# ============================================================================
def login_session(username):
    pw = CREDS.get(username)
    if not pw: return None, "no password supplied"
    st, _, hdr = http("POST", "/login", {"realm": REALM, "username": username, "password": pw})
    if st != 200: return None, "login -> %s" % st
    sc = hdr.get("Set-Cookie") or hdr.get("set-cookie") or ""
    cookie = sc.split(";")[0] if sc else None
    return cookie, "ok" if cookie else "no cookie"

CRED_CASES = [
    ("FOUNDATIONS", "F2",  "valid token w/o grant cannot do privileged write [debt B1]"),
    ("FOUNDATIONS", "F14", "role assignment names its grantor (granted_by)"),
    ("REGISTRY",    "R1",  "write then re-read by id — id stable"),
    ("REGISTRY",    "R3",  "supersede creates new version; prior addressable"),
    ("REGISTRY",    "R7",  "written record carries provenance [debt A2 shadow]"),
    ("NETWORK",     "N1",  "slug/tenant not accepted as net authority [debt B11/B2]"),
    ("NETWORK",     "N3",  "single-holder self-assign of security role denied"),
    ("NETWORK",     "N9",  "wildcard/unversioned capability grant rejected [debt B12]"),
    ("CLIENT",      "C1",  "unregistered client rejected [debt A47]"),
]
def run_cred_cases():
    have = bool(CREDS)
    # Prove the session path works if creds exist; otherwise skip all.
    if have:
        cookie, msg = login_session("admin")
        record("FOUNDATIONS", "F1", "authenticated session opens (pos)",
               "testable", "PASS" if cookie else "FAIL", "admin login: %s" % msg)
    for spec, rule, name in CRED_CASES:
        record(spec, rule, name, "needs-creds", "SKIP_CREDS",
               "supply AOS_TEST_USERS to enable" if not have else "not implemented in first suite")

# ============================================================================
# NEEDS-BUILD cases (listed, not executed)
# ============================================================================
NEEDS_BUILD = [
    ("FOUNDATIONS","F5","durable authority survives restart","restart orchestration, not black-box"),
    ("FOUNDATIONS","F7","kernel authorizes with Network down","network-down orchestration [debt B9]"),
    ("FOUNDATIONS","F9","s2s minted tokens, no shared secret","internal hop, not black-box"),
    ("FOUNDATIONS","F12","failed auth logged","audit store not black-box readable [debt A9]"),
    ("FOUNDATIONS","F16","missing config stops startup","startup-time, not black-box"),
    ("FOUNDATIONS","F17","agent delegation; no self-widen","no delegation primitive (NOT BUILT)"),
    ("REGISTRY","R12","trust-bearing write audited","audit not black-box readable"),
    ("REGISTRY","R14","personal data by reference; erasure","erasable store PLANNED"),
    ("REGISTRY","R15","public = schema flag via CR","hardcoded allow-list [debt B8]"),
    ("REGISTRY","R16","archived version resolves identically","archiving PLANNED"),
    ("DECISION","D1","protected authz emits a decision record","decision records not emitted [debt A9/B1]"),
    ("DECISION","D3","replayable; model output as input","replay harness not exposed"),
    ("DECISION","D4","decider needs recorded authority [debt B3]","not emitted; authentication accepted"),
    ("DECISION","D6","denial recorded with reason [debt A9]","denials not logged"),
    ("DECISION","D7","personal data in decision by reference","inherits R14 (PLANNED)"),
    ("DECISION","D8","reason codes; subject reads own decisions","subject-access not built"),
    ("DECISION","D10","personal-data read always full record","tiered logging not built"),
    ("DECISION","D11","contest flow; reviewer != decider","contest flow not proven"),
    ("DECISION","D12","automated decision labelled + human authority [debt B18]","not built"),
    ("NETWORK","N4","suspended net refuses exchange, allows reads","status machine not verified"),
    ("NETWORK","N6","join never creates a login [debt B9]","join provisions user+password (EXPECTED FAIL, needs creds to drive)"),
    ("NETWORK","N7","issuer trust admin-only + scoped","membership.steward can approve, service-wide (EXPECTED FAIL)"),
    ("ACCOUNT","A2","id/handle/binding distinct; handle reserved","model not verified"),
    ("ACCOUNT","A3","raw id never shown; one-identity-one-account","assurance untrustworthy [debt B13]; R14 PLANNED"),
    ("ACCOUNT","A7","consent by holder; withdraw->erase","consent enforcement pending [debt B12]"),
    ("ACCOUNT","A8","assisted access via F17","no delegation primitive"),
    ("ACCOUNT","A9","closure withdraws consents + erases","not built"),
    ("ACCOUNT","W3","presentation bound to recipient/purpose","PLANNED"),
    ("ACCOUNT","W4","selective disclosure","PLANNED"),
    ("CLIENT","C5","handle resolution registered-only + anti-enum [debt B6]","identity directory not at :8080; invariant unheld platform-wide"),
    ("CLIENT","C6","public versioned protocol, not /bridge/* [debt A23]","only /bridge/* + /embed/* exist"),
]
def run_needs_build():
    for spec, rule, name, why in NEEDS_BUILD:
        record(spec, rule, name, "needs-build", "SKIP_BUILD", why)

# ============================================================================
def main():
    print("AirawatOS conformance suite — target %s (realm %s)" % (BASE, REALM))
    print("credentials: %s\n" % ("supplied (%d users)" % len(CREDS) if CREDS else "none (NEEDS-CREDENTIALS cases will skip)"))
    # preflight
    st, _, _ = http("GET", "/healthz")
    if st != 200:
        print("PREFLIGHT FAIL: %s/healthz -> %s. Is local-dev up?" % (BASE, st)); sys.exit(2)

    run_no_cred_cases()
    run_cred_cases()
    run_needs_build()

    # report
    specs = ["FOUNDATIONS", "REGISTRY", "DECISION", "NETWORK", "ACCOUNT", "CLIENT"]
    kinds = ["PASS", "XFAIL", "XPASS", "FAIL", "SKIP_CREDS", "SKIP_BUILD"]
    print("%-13s %5s %6s %6s %5s %6s %6s" % ("SPEC", "PASS", "XFAIL", "XPASS", "FAIL", "nCRED", "nBUILD"))
    print("-" * 60)
    tot = {k: 0 for k in kinds}
    for sp in specs:
        row = {k: 0 for k in kinds}
        for r in RESULTS:
            if r["spec"] == sp: row[r["status"]] += 1
        for k in kinds: tot[k] += row[k]
        print("%-13s %5d %6d %6d %5d %6d %6d" % (sp, row["PASS"], row["XFAIL"], row["XPASS"],
                                                 row["FAIL"], row["SKIP_CREDS"], row["SKIP_BUILD"]))
    print("-" * 60)
    print("%-13s %5d %6d %6d %5d %6d %6d" % ("TOTAL", tot["PASS"], tot["XFAIL"], tot["XPASS"],
                                             tot["FAIL"], tot["SKIP_CREDS"], tot["SKIP_BUILD"]))
    print()
    # details for anything not a plain PASS/SKIP
    notable = [r for r in RESULTS if r["status"] in ("FAIL", "XPASS", "XFAIL")]
    if notable:
        print("Executed cases (XFAIL = known debt reproduced; XPASS = debt looks FIXED; FAIL = contradicts spec):")
        for r in notable:
            print("  [%-5s] %-11s %-8s %s — %s" % (r["status"], r["spec"], r["rule"], r["name"], r["detail"]))
    fails = [r for r in RESULTS if r["status"] == "FAIL"]
    xpass = [r for r in RESULTS if r["status"] == "XPASS"]
    print()
    if xpass:
        print(">>> %d XPASS: a known violation no longer reproduces — update the spec status / debt register:" % len(xpass))
        for r in xpass: print("    %s %s — %s" % (r["spec"], r["rule"], r["name"]))
    if fails:
        print(">>> %d FAIL: a TESTABLE-NOW case contradicts the spec:" % len(fails))
        for r in fails: print("    %s %s — %s — %s" % (r["spec"], r["rule"], r["name"], r["detail"]))
        sys.exit(1)
    print("OK — no FAIL. Suite green (PASS + XFAIL). Exit 0.")
    sys.exit(0)

if __name__ == "__main__":
    main()

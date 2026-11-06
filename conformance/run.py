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
    expect("FOUNDATIONS", "FND-1/FND-3/FND-15", "forged role+foreign-iss token rejected (abuse)",
           st in (401, 403), "kernel resolve w/ forged bearer -> %s" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:1", "object": {"schema": "viz.layer", "id": "conf:probe:1"}})
    expect("FOUNDATIONS", "FND-8", "anonymous write denied (abuse)", st in (401, 403), "anon kernel write -> %s" % st)

    st, _, _ = http("POST", "/network/v1/governance/roles", {})
    expect("NETWORK", "NET-3", "anonymous governance role-write denied (abuse)", st in (401, 403),
           "anon network governance -> %s" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/resolve", {"filter": {"schema": "network.network"}})
    xfail("REGISTRY", "REG-6/FND-8", "anonymous read denied (abuse) [debt DEBT-A1]", st == 200,
          "anon kernel read -> %s (rule 401; live-violation 200)" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/exists", {"id": "network.network"})
    if st in (0, 404):
        record("REGISTRY", "REG-6", "anonymous existence-check denied (abuse)", "expected-fail", "SKIP_BUILD",
               "/kernel/v1/registry/exists not reachable (%s)" % st)
    else:
        xfail("REGISTRY", "REG-6", "anonymous existence-check denied (abuse) [debt DEBT-A1]", st == 200,
              "anon exists -> %s (rule 401; live-violation 200)" % st)

    st, _, _ = http("POST", "/kernel/v1/registry/objects",
                    {"id": "conf:probe:2", "object": {"schema": "viz.layer", "id": "conf:probe:2"}}, token=forged_jwt())
    expect("REGISTRY", "REG-5", "forged-token write denied (abuse)", st in (401, 403), "forged kernel write -> %s" % st)

    st, body, _ = http("POST", "/kernel/v1/registry/resolve",
                       {"filter": {"schema": "zzz.conformance_unknown_%d" % int(time.time())}})
    expect("FOUNDATIONS", "FND-6/REG-13", "unknown schema handled opaquely (pos)",
           st == 200 and '"results"' in body, "resolve unknown schema -> %s" % st)

    st, _, _ = http("POST", "/login", {"realm": REALM, "username": "admin", "password": "admin"})
    expect("ACCOUNT", "DEBT-A4", "handle/username is not a credential (abuse)", st in (401, 403),
           "login admin/pw=admin -> %s" % st)

    # CLI-1 — an unregistered client is rejected at /embed/authorize (no cred needed).
    st, _, _ = http("GET", "/embed/authorize?client_id=__conformance_unregistered__&scope=profile"
                           "&redirect_uri=https://x.test/cb&code_challenge=x&code_challenge_method=S256")
    if st in (0, 404):
        record("CLIENT", "CLI-1", "unregistered client rejected (abuse) [debt DEBT-A47]", "testable", "SKIP_BUILD",
               "/embed/authorize not reachable (%s)" % st)
    else:
        expect("CLIENT", "CLI-1", "unregistered client rejected (abuse) [debt DEBT-A47]", st not in (200, 302),
               "unregistered client_id -> %s (want reject, not 200/302)" % st)

    st, _, _ = http("GET", "/embed/authorize?client_id=demo-embed&scope=service:invoke"
                           "&redirect_uri=https://example.test/cb&code_challenge=x&code_challenge_method=S256")
    if st in (200, 302):
        xfail("CLIENT", "CLI-2", "scope bound to registered client, not query (abuse) [debt DEBT-B12]", True,
              "/embed/authorize over-broad scope -> %s (honors query scope)" % st)
    else:
        record("CLIENT", "CLI-2", "scope bound to registered client, not query (abuse) [debt DEBT-B12]",
               "expected-fail", "SKIP_BUILD",
               "/embed/authorize -> %s; cannot isolate scope-binding black-box (needs client+redirect+PKCE)" % st)

# ============================ EXTERNAL: credentialed cases ============================
def login_session(user):
    c = CREDS.get(user)
    if not c: return None, "no creds for %s" % user
    uname = c.get("username", user)   # cred key may be a logical name (e.g. opadmin) distinct from the login username
    st, _, hdr = http("POST", "/login", {"realm": c.get("tenant", REALM), "username": uname, "password": c["password"]})
    if st != 200: return None, "login %s@%s -> %s" % (uname, c.get("tenant", REALM), st)
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
                record("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]",
                       "expected-fail", "SKIP_BUILD",
                       "local-dev component catalogue empty (/bridge/components total=0) — nothing to install; "
                       "set AOS_TEST_COMPONENT=<published cid> to exercise the populated leak-check")
                return
        ist, ib, _ = http("POST", "/bridge/install", {"component_id": cid}, cookie=cookie)
        note = "install %s -> %s" % (cid, ist)
        if ist not in (200, 201):
            record("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]",
                   "expected-fail", "SKIP_BUILD", "install failed (%s): %s" % (ist, ib[:100]))
            return
    st, body, _ = http("GET", "/kernel/v1/components")
    if "run_token" in body:
        xfail("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]", True,
              "anon GET /components (populated) CONTAINS run_token — leak reproduced; %s" % note)
    else:
        expect("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]", True,
               "anon GET /components (populated: %s) has no run_token" % note)

def case_R10(cookie):
    schema = os.environ.get("AOS_TEST_SCHEMA", "network.network")
    s1, b1, _ = http("POST", "/bridge/registry-resolve", {"filter": {"schema": schema}}, cookie=cookie)
    if s1 in (0, 404):
        record("REGISTRY", "REG-10", "deterministic resolution over records (pos)", "needs-creds", "SKIP_BUILD",
               "/bridge/registry-resolve not reachable (%s)" % s1); return
    n = 0
    try: n = len(json.loads(b1).get("results", []))
    except Exception: pass
    if n == 0:
        record("REGISTRY", "REG-10", "deterministic resolution over records (pos)", "needs-creds", "SKIP_CREDS",
               "no visible records for %s (determinism would be trivial-on-empty)" % schema); return
    s2, b2, _ = http("POST", "/bridge/registry-resolve", {"filter": {"schema": schema}}, cookie=cookie)
    expect("REGISTRY", "REG-10", "deterministic resolution over %d records (pos)" % n, s1 == s2 and b1 == b2,
           "two resolves of %s -> %s/%s identical=%s" % (schema, s1, s2, b1 == b2))

# Remaining needs-cred rules with no black-box write/read bridge mapped in the first suite.
# /bridge/resolve returns 500 for these schemas and there is no registry-write bridge, and /bridge/roles
# refuses even the tenant admin ("requires a tenant admin") — so these are honestly SKIP_BUILD, not SKIP_CREDS.
CRED_NO_BRIDGE = [
    ("FOUNDATIONS","FND-14","role assignment names its grantor (granted_by)","no grantor-returning read bridge (/bridge/roles refuses tenant admin)"),
    ("REGISTRY","REG-1","write then re-read by id — id stable","no black-box registry-write bridge"),
    ("REGISTRY","REG-3","supersede creates new version; prior addressable","no black-box registry-write bridge"),
    ("REGISTRY","REG-7","written record carries provenance [debt DEBT-A2 shadow]","no black-box registry-write bridge"),
    ("NETWORK","NET-1","slug/tenant not accepted as net authority [debt DEBT-B11/DEBT-B2]","needs a governance call asserting slug==tenant; no bridge mapped"),
    ("NETWORK","NET-9","wildcard/unversioned capability grant rejected [debt DEBT-B12]","capability-grant bridge refuses the tenant admin; shape not drivable black-box"),
    # REG-17 — field-level data protection (ADR-0126). All PLANNED/NEEDS-BUILD: no encrypt/decrypt path exists yet
    # (Vault transit signs only; records are plaintext JSONB). Registered so the suite tracks the obligation.
    ("REGISTRY","REG-17","personal field (x-sensitivity:personal) is NOT stored in the versioned record; value lives in the REG-14 erasable store","needs encrypt-on-write + erasable-store split; not built (ADR-0126)"),
    ("REGISTRY","REG-17","sensitive field stored inline as per-tenant (rec-<tenant>) transit ciphertext, never plaintext","needs inline transit encrypt-on-write; not built (ADR-0126)"),
    ("REGISTRY","REG-17","erasure of a personal field deletes the value (REG-14) + records an audited erasure; derived per-person key is NOT erasure","needs erasable store + erasure event; not built (ADR-0126/REG-14)"),
    ("REGISTRY","REG-17","REG-9 idempotency over a protected field compares a keyed HMAC of plaintext — never a plain hash, never ciphertext","needs HMAC idempotency on the write path; not built (ADR-0126)"),
    ("REGISTRY","REG-17","unauthorised read of a protected field returns a redacted placeholder — never ciphertext, never plaintext","needs decrypt-authz + redaction on the read path; not built (ADR-0126)"),
    ("REGISTRY","REG-17","Kernel→Vault uses its own service identity scoped to transit encrypt/decrypt/hmac on rec-*/idx-* (never root); fails closed if Vault down","needs Kernel Vault policy + fail-closed path; not built (ADR-0124/0126)"),
    ("REGISTRY","REG-17","every key use is audited in the Kernel chain AND Vault audit device, without plaintext/ciphertext","needs transit audit wiring; not built (ADR-0126/REG-12)"),
    ("ACCOUNT","ACC-3","identity-binding uniqueness via a keyed blind index (HMAC), not a plaintext column","needs blind-index on write + uniqueness check; not built (ADR-0126)"),
    ("DECISION","DEC-10","every decryption of personal data produces a full decision record (actor/subject/purpose/basis)","needs personal-read decision-record emission; not built (ADR-0126/0125)"),
]
def case_F2_no_grant(outsider_cookie):
    """A valid NON-admin session must be denied a governance write — authority from a grant, not auth."""
    st, _, _ = http("POST", "/bridge/role-grant", {"principal": "x", "role": "network.admin"}, cookie=outsider_cookie)
    expect("FOUNDATIONS", "FND-2", "valid non-admin session denied governance write (abuse)",
           st in (401, 403), "outsider POST /bridge/role-grant -> %s (want 401/403)" % st)

def run_cred_cases():
    if not CREDS:
        record("REGISTRY","DEBT-B15","components list does not leak run_token (abuse) [debt DEBT-B15]","needs-creds","SKIP_CREDS","needs admin session to install first")
        record("REGISTRY","REG-10","deterministic resolution over records (pos)","needs-creds","SKIP_CREDS","needs a reader session to see records")
        record("FOUNDATIONS","FND-2","valid non-admin session denied governance write (abuse)","needs-creds","SKIP_CREDS","needs a non-admin session")
        for s,r,n,why in CRED_NO_BRIDGE: record(s,r,n,"needs-build","SKIP_BUILD",why)
        return
    cookie, msg = login_session("admin")
    expect("FOUNDATIONS","FND-1","authenticated session opens (pos)", bool(cookie), "admin login: %s" % msg)
    if cookie:
        case_B15(cookie); case_R10(cookie)
    else:
        record("REGISTRY","DEBT-B15","components list does not leak run_token (abuse) [debt DEBT-B15]","needs-creds","SKIP_CREDS","admin login failed: %s"%msg)
        record("REGISTRY","REG-10","deterministic resolution over records (pos)","needs-creds","SKIP_CREDS","admin login failed: %s"%msg)
    ocookie, omsg = login_session("outsider")
    if ocookie:
        case_F2_no_grant(ocookie)
    else:
        record("FOUNDATIONS","FND-2","valid non-admin session denied governance write (abuse)","needs-creds","SKIP_CREDS","outsider login failed: %s"%omsg)
    # ADR-0122 PLT-4 black-box — platform.authority is a recorded role (enforce). admin holds it; faker (same
    # tenant) does not. Requires the ld-network running dev-b375cfe + bootstrap phase 4b seed.
    pacookie, _ = login_session("opadmin")   # E1: platform.authority holder is admin@<inst>-operator
    pncookie, _ = login_session("platnone")
    case_platform_authority(pacookie, pncookie)
    case_admin_network_admin(cookie)
    for s,r,n,why in CRED_NO_BRIDGE: record(s,r,n,"needs-build","SKIP_BUILD",why)

def _networks_mine(cookie):
    st, body, _ = http("GET", "/bridge/networks-mine", cookie=cookie)
    try:
        rows = json.loads(body).get("result", [])
    except Exception:
        rows = []
    return st, rows

def case_platform_authority(pa_cookie, pn_cookie):
    # Uses the dedicated ADR-0122 test users: platauth (holds platform.authority after 2b) and platnone
    # (same platform tenant, no recorded role). Supply their passwords in .creds.json to run these.
    # PA1 — the platform.authority holder performs a platform-authority action (sees all networks, flag true).
    if not pa_cookie:
        record("PLATFORM","PLT-4","opadmin (platform.authority) performs a platform-authority action (pos)","needs-creds","SKIP_CREDS","opadmin not in .creds.json")
    else:
        st, rows = _networks_mine(pa_cookie)
        ok = st == 200 and len(rows) >= 1 and all(r.get("platform_authority") is True for r in rows)
        expect("PLATFORM","PLT-4","opadmin (operator tenant) sees all networks w/ platform_authority=true (pos)",
               ok, "opadmin /bridge/networks-mine -> %s rows=%d pa=%s" % (st, len(rows),
                    sorted({bool(r.get("platform_authority")) for r in rows}) if rows else []))
    # PA2 — a same-tenant user WITHOUT the role is not platform authority.
    if not pn_cookie:
        record("PLATFORM","PLT-4","platnone (same tenant, no role) is not platform authority (abuse)","needs-creds","SKIP_CREDS","platnone not in .creds.json")
    else:
        st, rows = _networks_mine(pn_cookie)
        ok = st == 200 and all(r.get("platform_authority") is not True for r in rows)
        expect("PLATFORM","PLT-4","platnone (same tenant, no role) is NOT platform authority (abuse)",
               ok, "platnone /bridge/networks-mine -> %s rows=%d pa=%s" % (st, len(rows),
                    sorted({bool(r.get("platform_authority")) for r in rows}) if rows else []))
    # PA3 — granting platform.authority without a different-holder CR is refused (a holder already exists).
    if not pa_cookie:
        record("PLATFORM","PLT-5","grant platform.authority without a CR refused (abuse)","needs-creds","SKIP_CREDS","opadmin not in .creds.json")
    else:
        st, _, _ = http("POST", "/bridge/gov-assign-role",
                        {"principal": "user://localdev-network/conf-probe", "role": "platform.authority",
                         "status": "active"}, cookie=pa_cookie)
        if st in (0, 404):
            record("PLATFORM","PLT-5","grant platform.authority without a CR refused (abuse)","needs-build","SKIP_BUILD",
                   "/bridge/gov-assign-role not reachable (%s)" % st)
        else:
            expect("PLATFORM","PLT-5","grant platform.authority without a different-holder CR is refused (abuse)",
                   st in (400, 401, 403, 409), "opadmin assign platform.authority (no CR) -> %s (want refuse)" % st)
        # PA4 — revoking the LAST platform.authority holder (admin@operator) is refused.
        st, _, _ = http("POST", "/bridge/gov-assign-role",
                        {"principal": "user://localdev-operator/admin", "role": "platform.authority",
                         "status": "revoked"}, cookie=pa_cookie)
        if st in (0, 404):
            record("PLATFORM","PLT-5","revoke last platform.authority holder refused (abuse)","needs-build","SKIP_BUILD",
                   "/bridge/gov-assign-role not reachable (%s)" % st)
        else:
            expect("PLATFORM","PLT-5","revoking the last platform.authority holder (admin@operator) is refused (abuse)",
                   st in (400, 401, 403, 409), "opadmin revoke platform.authority (last holder) -> %s (want refuse)" % st)

def case_admin_network_admin(admin_cookie):
    # After 2b, admin is a PLAIN network.admin (platform.authority revoked). It must still work as
    # network.admin (sees its network, role network.admin) and must NOT be platform authority.
    if not admin_cookie:
        record("NETWORK","NET-3","admin works as plain network.admin after losing platform.authority (pos)","needs-creds","SKIP_CREDS","admin login failed")
        return
    st, rows = _networks_mine(admin_cookie)
    has_na = any("network.admin" in (r.get("roles") or []) for r in rows)
    no_pa = all(r.get("platform_authority") is not True for r in rows)
    expect("NETWORK","NET-3","admin is a plain network.admin (network.admin role, not platform authority) (pos)",
           st == 200 and has_na and no_pa,
           "admin /bridge/networks-mine -> %s rows=%d network.admin=%s platform_authority=%s"
           % (st, len(rows), has_na, sorted({bool(r.get("platform_authority")) for r in rows}) if rows else []))

# ============================ EXTERNAL: NEEDS-BUILD (genuinely not built) ============================
NEEDS_BUILD = [
    ("FOUNDATIONS","FND-5","durable authority survives restart","restart orchestration"),
    ("FOUNDATIONS","FND-7","kernel authorizes with Network down","network-down orchestration [debt DEBT-B9]"),
    ("FOUNDATIONS","FND-16","missing config stops startup","startup-time"),
    ("FOUNDATIONS","FND-17","agent delegation; no self-widen","no delegation primitive (NOT BUILT)"),
    ("REGISTRY","REG-12","trust-bearing write audited","audit not black-box readable"),
    ("REGISTRY","REG-14","personal data by reference; erasure","erasable store PLANNED"),
    ("REGISTRY","REG-15","public = schema flag via CR","hardcoded allow-list [debt DEBT-B8]"),
    ("REGISTRY","REG-16","archived version resolves identically","archiving PLANNED"),
    ("DECISION","DEC-1","protected authz emits a decision record","not emitted [debt DEBT-A9/DEBT-B1]"),
    ("DECISION","DEC-3","replayable; model output as input","replay harness not exposed"),
    ("DECISION","DEC-4","decider needs recorded authority [debt DEBT-B3]","not emitted; authn accepted"),
    ("DECISION","DEC-6","denial recorded with reason [debt DEBT-A9]","denials not logged"),
    ("DECISION","DEC-7","personal data in decision by reference","inherits REG-14 (PLANNED)"),
    ("DECISION","DEC-8","reason codes; subject reads own decisions","subject-access not built"),
    ("DECISION","DEC-10","personal-data read always full record","tiered logging not built"),
    ("DECISION","DEC-11","contest flow; reviewer != decider","contest flow not proven"),
    ("DECISION","DEC-12","automated decision labelled + human authority [debt DEBT-B18]","not built"),
    ("NETWORK","NET-4","suspended net refuses exchange, allows reads","status machine not verified"),
    ("NETWORK","NET-6","join never creates a login [debt DEBT-B9]","needs creds to drive join (EXPECTED FAIL)"),
    ("NETWORK","NET-7","issuer trust admin-only + scoped","needs creds (EXPECTED FAIL)"),
    ("ACCOUNT","ACC-2","id/handle/binding distinct; handle reserved","model not verified"),
    ("ACCOUNT","ACC-3","raw id never shown; one-identity-one-account","assurance untrustworthy [debt DEBT-B13]; REG-14 PLANNED"),
    ("ACCOUNT","ACC-7","consent by holder; withdraw->erase","consent enforcement pending [debt DEBT-B12]"),
    ("ACCOUNT","ACC-8","assisted access via FND-17","no delegation primitive"),
    ("ACCOUNT","ACC-9","closure withdraws consents + erases","not built"),
    ("ACCOUNT","ACC-W3","presentation bound to recipient/purpose","PLANNED"),
    ("ACCOUNT","ACC-W4","selective disclosure","PLANNED"),
    ("CLIENT","CLI-6","public versioned protocol, not /bridge/* [debt DEBT-A23]","only /bridge/* + /embed/* exist"),
]
def run_needs_build():
    for s,r,n,why in NEEDS_BUILD: record(s,r,n,"needs-build","SKIP_BUILD",why)

# ============================ INTERNAL mode cases ============================
def _mint_service_bearer(principal, tenant):
    """Mint a service principal's bearer by reading its Vault credential + logging in at identity — so refusal/
    confinement cases exercise the REAL role. None if Vault/identity is unreachable (→ SKIP_CREDS)."""
    vaddr = (os.environ.get("VAULT_ADDR") or "").rstrip("/"); vtok = os.environ.get("VAULT_TOKEN") or ""
    if not (vaddr and vtok):
        return None, "no VAULT_ADDR/VAULT_TOKEN (cannot read %s credential)" % principal
    try:
        r = _req("GET", f"{vaddr}/v1/secret/data/{tenant}/{principal}/password", headers={"X-Vault-Token": vtok})
        pw = (((json.loads(r[1]) or {}).get("data") or {}).get("data") or {}).get("password") if r[0] == 200 else None
    except Exception as e:
        return None, "vault read failed: %s" % str(e)[:60]
    if not pw:
        return None, "%s credential absent in Vault (run bootstrap)" % principal
    st, b, _ = _req("POST", INTERNAL["identity"] + "/login", {"username": principal, "tenant": tenant, "password": pw})
    tok = (json.loads(b) or {}).get("access_token") if st == 200 else None
    return (tok, None) if tok else (None, "%s login -> %s" % (principal, st))


def _mint_component_publisher_token():
    return _mint_service_bearer("component-publisher", os.environ.get("COMPONENT_PUBLISHER_TENANT", "localdev-network"))


def case_dev_sandbox_confined():
    """ADR-0124 item (c) — dev-sandbox holds platform.developer, which the KERNEL confines to dev-token mint +
    writes in its own development tenant. Prove the service token is CONFINED: refused at kernel admin, and
    refused a CROSS-TENANT write. (The platform.developer app-host gates are human-session only — never reached
    by this service token — so the role needs no narrowing.)"""
    dev_tenant = os.environ.get("DEV_SANDBOX_TENANT", "localdev-developer")
    tok, why = _mint_service_bearer("dev-sandbox", dev_tenant)
    probes = [
        ("REGISTRY", "FND-11", "dev-sandbox refused at kernel admin (registry.usage)", INTERNAL["kernel"] + "/v1/registry/usage", {}),
        ("REGISTRY", "FND-2",  "dev-sandbox refused a cross-tenant write", INTERNAL["kernel"] + "/v1/registry/objects",
         {"id": "ds:localdev:probe/devsandbox", "object": {"schema": "viz.layer", "id": "ds:localdev:probe/devsandbox"}}),
    ]
    if not tok:
        for spec, rule, name, *_ in probes:
            record(spec, rule, name, "needs-creds", "SKIP_CREDS", why)
        return
    for spec, rule, name, url, body in probes:
        st, b, _ = _req("POST", url, body=body, token=tok)
        if st == 0 or st == 404:
            record(spec, rule, name, "testable", "SKIP_BUILD", "%s -> %s (route unreachable)" % (url, st)); continue
        expect(spec, rule, name, st in (401, 403), "%s -> %s (confined: refused expected)" % (url, st))


def case_component_publisher_refused():
    """ADR-0124 — component.publisher is a NARROW service role (NOT admin). Prove it is REFUSED at the
    kernel admin, network-administration (assign role / issue grant) and secrets gates it would have passed
    as platform.steward. A 2xx here is a real FAIL (the role leaked admin reach)."""
    tok, why = _mint_component_publisher_token()
    probes = [
        ("REGISTRY", "FND-11/DEBT-B1", "component.publisher refused at kernel admin (registry.usage)", "POST", INTERNAL["kernel"] + "/v1/registry/usage", {}),
        ("NETWORK",  "NET-3/DEBT-B1",  "component.publisher refused at network admin (assign role)",     "POST", INTERNAL["network"] + "/v1/roles", {"role": "network.admin", "principal": "x"}),
        ("NETWORK",  "NET-3/DEBT-B1",  "component.publisher refused at network admin (issue grant)",      "POST", INTERNAL["network"] + "/v1/grants/issue", {"tenant": "localdev", "component_id": "ds:localdev:driver/probe"}),
        ("ACCOUNT",  "A?/DEBT-B1",  "component.publisher refused at secrets admin (/set)",             "POST", INTERNAL["secrets"] + "/set", {"tenant": "localdev", "component": "x", "name": "y", "value": "z"}),
    ]
    if not tok:
        for spec, rule, name, *_ in probes:
            record(spec, rule, name, "needs-creds", "SKIP_CREDS", why)
        return
    for spec, rule, name, method, url, body in probes:
        st, b, _ = _req(method, url, body=body, token=tok)
        if st == 0 or st == 404:
            record(spec, rule, name, "testable", "SKIP_BUILD", "%s -> %s (route unreachable)" % (url, st)); continue
        expect(spec, rule, name, st in (401, 403), "%s -> %s (refused expected; 2xx = admin leak)" % (url, st))


def _login_with_aud(principal, tenant, vault_path, aud):
    """(status, token-aud) logging in through the REAL identity /login requesting `aud`. Reads the principal's
    Vault password so it works under enforce. status None → creds unavailable (SKIP)."""
    vaddr = (os.environ.get("VAULT_ADDR") or "").rstrip("/"); vtok = os.environ.get("VAULT_TOKEN") or ""
    if not (vaddr and vtok):
        return None, "no VAULT_ADDR/VAULT_TOKEN"
    try:
        r = _req("GET", f"{vaddr}/v1/{vault_path}", headers={"X-Vault-Token": vtok})
        pw = (((json.loads(r[1]) or {}).get("data") or {}).get("data") or {}).get("password") if r[0] == 200 else None
    except Exception as e:
        return None, "vault read failed: %s" % str(e)[:50]
    if not pw:
        return None, "credential absent in Vault"
    body = {"username": principal, "tenant": tenant, "password": pw}
    if aud is not None:
        body["aud"] = aud
    st, b, _ = _req("POST", INTERNAL["identity"] + "/login", body)
    if st != 200:
        return st, None
    pp = json.loads(b)["access_token"].split(".")[1]; pp += "=" * (-len(pp) % 4)
    return 200, json.loads(base64.urlsafe_b64decode(pp)).get("aud")


def _login_token(principal, tenant, vault_path, aud=None):
    """The raw access_token from a REAL identity /login (reads the principal's Vault password, works under
    enforce). None when creds/login unavailable. Used to mint a WRONG-audience token for ingress abuse tests."""
    vaddr = (os.environ.get("VAULT_ADDR") or "").rstrip("/"); vtok = os.environ.get("VAULT_TOKEN") or ""
    if not (vaddr and vtok):
        return None
    try:
        r = _req("GET", f"{vaddr}/v1/{vault_path}", headers={"X-Vault-Token": vtok})
        pw = (((json.loads(r[1]) or {}).get("data") or {}).get("data") or {}).get("password") if r[0] == 200 else None
    except Exception:
        return None
    if not pw:
        return None
    body = {"username": principal, "tenant": tenant, "password": pw}
    if aud is not None:
        body["aud"] = aud
    st, b, _ = _req("POST", INTERNAL["identity"] + "/login", body)
    return (json.loads(b).get("access_token") if st == 200 else None)


def case_login_audience_allowlist():
    """ADR-0124 — identity /login enforces a RECORDED per-principal audience allow-list (never silent default).
    The daemons share the `scheduler` principal (recorded audience: svc:automation)."""
    sp_t, sp_v = "localdev-operator", "secret/data/localdev-operator/scheduler/password"
    granted = _login_with_aud("scheduler", sp_t, sp_v, "svc:automation")
    if granted[0] is None:
        for n in ("granted", "svc:kernel refused", "svc:app-host refused", "human refused"):
            record("FOUNDATIONS", "FND-15/ADR-0124", "login audience allow-list: " + n, "needs-creds", "SKIP_CREDS", str(granted[1]))
        return
    expect("FOUNDATIONS", "FND-15/ADR-0124", "scheduler may request its recorded audience (svc:automation)",
           granted == (200, "svc:automation"), "scheduler svc:automation -> %s" % str(granted))
    expect("FOUNDATIONS", "FND-15/ADR-0124", "scheduler refused svc:kernel (not recorded)",
           _login_with_aud("scheduler", sp_t, sp_v, "svc:kernel")[0] == 403, "expect 403")
    expect("FOUNDATIONS", "FND-15/ADR-0124", "scheduler refused svc:app-host (not recorded)",
           _login_with_aud("scheduler", sp_t, sp_v, "svc:app-host")[0] == 403, "expect 403")
    h = _login_with_aud("platauth", "localdev-network", "secret/data/localdev-network/platauth/password", "svc:automation")
    if h[0] is None:
        record("FOUNDATIONS", "FND-15/ADR-0124", "login audience allow-list: human refused", "needs-creds", "SKIP_CREDS", str(h[1]))
    else:
        expect("FOUNDATIONS", "FND-15/ADR-0124", "human (platauth) refused a service audience", h[0] == 403, "platauth svc:automation -> %s" % str(h))


def case_platform_authority_bootstrap_rule():
    """ADR-0122 — with a platform.authority holder already present, a NON-CR grant is REFUSED (403): re-running
    bootstrap's first-holder seed (phase 7b) grants nothing. Proven via the governance endpoint as trust-writer."""
    vaddr = (os.environ.get("VAULT_ADDR") or "").rstrip("/"); vtok = os.environ.get("VAULT_TOKEN") or ""
    name = "bootstrap grants no platform.authority when a holder exists (ADR-0122)"
    if not (vaddr and vtok):
        record("NETWORK", "PLT-5/ADR-0122", name, "needs-creds", "SKIP_CREDS", "no VAULT_ADDR/VAULT_TOKEN"); return
    try:
        r = _req("GET", f"{vaddr}/v1/secret/data/localdev-network/trust-writer/password", headers={"X-Vault-Token": vtok})
        # trust-writer secret is stored with field `value` (the field the Trust service itself reads — installer
        # Phase 7), not `password`; read `value` with a `password` fallback for older installs.
        _d = (((json.loads(r[1]) or {}).get("data") or {}).get("data") or {}) if r[0] == 200 else {}
        pw = _d.get("value") or _d.get("password")
    except Exception as e:
        record("NETWORK", "PLT-5/ADR-0122", name, "needs-creds", "SKIP_CREDS", "vault: %s" % str(e)[:50]); return
    if not pw:
        record("NETWORK", "PLT-5/ADR-0122", name, "needs-creds", "SKIP_CREDS", "trust-writer cred absent"); return
    st, b, _ = _req("POST", INTERNAL["identity"] + "/login", {"username": "trust-writer", "tenant": "localdev-network", "password": pw})
    tok = (json.loads(b) or {}).get("access_token") if st == 200 else None
    if not tok:
        record("NETWORK", "PLT-5/ADR-0122", name, "needs-creds", "SKIP_CREDS", "trust-writer login -> %s" % st); return
    body = {"role": "platform.authority", "principal": "user://localdev-network/__bootstrap_probe__",
            "scope": {"type": "platform", "ref": None}, "status": "active"}
    st2, b2, _ = _req("POST", INTERNAL["network"] + "/v1/governance/roles", body, token=tok)
    if st2 in (0, 404):
        record("NETWORK", "PLT-5/ADR-0122", name, "testable", "SKIP_BUILD", "/v1/governance/roles -> %s" % st2); return
    expect("NETWORK", "PLT-5/ADR-0122", name, st2 in (401, 403),
           "/v1/governance/roles grant -> %s (refused expected: a holder exists, no CR)" % st2)


def run_internal_cases():
    T = INTERNAL
    case_component_publisher_refused()
    case_dev_sandbox_confined()
    case_login_audience_allowlist()
    case_platform_authority_bootstrap_rule()
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
    # ADR-0124 item 1 (service 2/5) — filestore ingress. The gate is live; a WRONG-AUDIENCE token is refused
    # even in shadow (assertable now). The ANONYMOUS-refused case only holds once FILESTORE_REQUIRE_TOKEN flips
    # on (shadow until every reader — app-host/kernel/launcher — is wired; debt DEBT-A72), so it is recorded as an
    # expected-fail until the flip, mirroring how scheduler DEBT-B5 was handled pre-flip.
    _fs_wrong = _login_token("scheduler","localdev-operator","secret/data/localdev-operator/scheduler/password","svc:automation")
    if _fs_wrong:
        _stfw, _bfw, _ = _req("POST", T["filestore"]+"/files", body=None, token=_fs_wrong)
        expect("FOUNDATIONS","FND-10/DEBT-B5","filestore refuses a wrong-audience token (abuse)", _stfw == 403,
               "svc:automation token -> %s (expect 403 wrong audience)" % _stfw)
    else:
        record("FOUNDATIONS","FND-10/DEBT-B5","filestore refuses a wrong-audience token (abuse)","needs-creds","SKIP_CREDS","no svc:automation token")
    _stfa, _bfa, _ = _req("POST", T["filestore"]+"/files", body=None)
    if _stfa == 0:
        record("FOUNDATIONS","FND-10/DEBT-B5","filestore refuses an anonymous call (abuse)","expected-fail","SKIP_BUILD","filestore unreachable")
    else:
        xfail("FOUNDATIONS","FND-10/DEBT-B5","filestore refuses an anonymous call (abuse)", _stfa not in (401,403),
              "anon /files -> %s (FILESTORE_REQUIRE_TOKEN shadow until all readers wired — debt DEBT-A72)" % _stfa)
    tokenless_accepted("FOUNDATIONS","FND-10/DEBT-B5","notify /notify accepts without a service token (abuse)","POST", T["notify"]+"/notify", {})
    # ADR-0124 item 1 — scheduler /run,/reload now REQUIRE a svc:scheduler token from an allow-listed caller.
    # Promoted from the tokenless-abuse probe to a real assertion: anonymous AND wrong-audience are refused.
    _s_anon, _s_b, _ = _req("POST", T["scheduler"]+"/run", body={"component":"__conformance_probe__","tenant":"kmc"})
    if _s_anon == 0:
        record("FOUNDATIONS","FND-10/DEBT-B5","scheduler /run requires a service token (abuse)","expected-fail","SKIP_BUILD","scheduler unreachable (%s)"%_s_b[:40])
    else:
        expect("FOUNDATIONS","FND-10/DEBT-B5","scheduler /run refuses an anonymous call (abuse)", _s_anon in (401,403),
               "anon /run -> %s (expect 403)" % _s_anon)
        _wrong = _login_token("scheduler","localdev-operator","secret/data/localdev-operator/scheduler/password","svc:automation")
        if not _wrong:
            record("FOUNDATIONS","FND-10/DEBT-B5","scheduler /run refuses a wrong-audience token (abuse)","needs-creds","SKIP_CREDS","could not mint a svc:automation token")
        else:
            _stw, _bw, _ = _req("POST", T["scheduler"]+"/run", body={"component":"__conformance_probe__","tenant":"kmc"}, token=_wrong)
            expect("FOUNDATIONS","FND-10/DEBT-B5","scheduler /run refuses a wrong-audience token (abuse)", _stw == 403,
                   "svc:automation token -> %s (expect 403 wrong audience)" % _stw)
    tokenless_accepted("FOUNDATIONS","FND-10/DEBT-B5","model-gateway /complete accepts without a service token (abuse)","POST", T["model-gateway"]+"/complete", {})
    tokenless_accepted("FOUNDATIONS","FND-10/DEBT-B5","automation /events accepts without a service token (abuse)","POST", T["automation"]+"/events", {})
    # FND-9 / debt DEBT-B4 — fail-open internal-token gates
    tokenless_accepted("FOUNDATIONS","FND-9/DEBT-B4","secrets /materialize accepts w/o internal token (abuse)","POST", T["secrets"]+"/materialize", {})
    tokenless_accepted("FOUNDATIONS","FND-9/DEBT-B4","secrets /fetch accepts w/o internal token (abuse)","POST", T["secrets"]+"/fetch", {})
    record("FOUNDATIONS","FND-9/DEBT-B4","runtime-manager /invoke fail-open (abuse)","expected-fail","SKIP_BUILD","no runtime-manager in the local-dev stack")
    # DEBT-B6 — identity directory disclosure
    st, b, _ = _req("GET", T["identity"]+"/users")
    if st == 0:
        record("CLIENT","CLI-5/DEBT-B6","identity /users directory disclosure (abuse)","expected-fail","SKIP_BUILD","identity /users unreachable (%s)"%b[:40])
    else:
        disclosed = st == 200 and ("username" in b or '"users"' in b or b.strip().startswith("["))
        # ADR-0124 DEBT-B6 — the directory now requires the internal provisioner token; an anonymous GET must be
        # refused (not disclosed). Promoted from expected-fail to a real assertion.
        expect("CLIENT","CLI-5/DEBT-B6","identity /users directory requires an authorised caller (abuse)", not disclosed,
               "anon GET identity/users -> %s discloses=%s (want refused)" % (st, disclosed))
    # kernel reachable directly internally (parity with external anon read)
    st, _, _ = _req("POST", T["kernel"]+"/v1/registry/resolve", {"filter": {"schema": "network.network"}})
    xfail("REGISTRY","REG-6/FND-8","anonymous kernel read denied (internal) [debt DEBT-A1]", st == 200,
          "kernel:8080 anon read -> %s (rule 401; live-violation 200)" % st)

def run_kernel_review_cases():
    """Consolidation phase-5 Kernel review (slice 1): cases for Kernel-relevant rules that were NO TEST in
    STATUS-MATRIX. Black-box/internal where feasible (expected-fail where the review found a violation);
    otherwise a recorded SKIP_BUILD stating WHY it is not black-box reachable + the proposed internal test.
    See docs/reviews/KERNEL-REVIEW.md."""
    K = INTERNAL["kernel"]
    # FND-8 (NEW, critical) — /v1/components/install has no admin gate: an UNAUTHENTICATED POST is PROCESSED
    # (reaches component lookup, returns 404/4xx) instead of being refused 401/403 up front. Any status other
    # than 401/403 means no admin gate fired before the (ungated) run-token-mint path. Reproduce black-box.
    st, _, _ = _req("POST", K + "/v1/components/install", {"component_id": "ds:localdev:driver/__review_probe__"})
    expect("FOUNDATIONS", "FND-8", "unauthenticated /v1/components/install is admin-gated (abuse)",
           st in (401, 403),
           "unauth install -> %s (want 401/403; admin-gated before any processing — DEBT-B22 hotfix)" % st)
    # FND-1 / FND-3 (review VIOLATED, matrix HELD) — test honesty: identity carries NO authority. A HOME-issued
    # token whose ROLE claim is admin (platform.steward) but which holds NO recorded governance grant must be
    # REFUSED at a kernel admin endpoint (authority only from recorded grants, FND-2). Today the kernel admin
    # gate honours the token role (DEBT-B1), so the admin call is ALLOWED = violation reproduced → XFAIL.
    # Principal: rolesteward (installer Phase 9, dev-only — platform.tenant-admin CLAIM, no recorded grant).
    rs = _login_token("rolesteward", "localdev-network", "secret/data/localdev-network/rolesteward/password")
    if not rs:
        record("FOUNDATIONS", "FND-1/FND-3", "home-issued admin role-claim without a recorded grant refused at kernel admin (abuse)",
               "needs-creds", "SKIP_CREDS", "could not mint a rolesteward token (installer Phase 9 dev-only)")
    else:
        st2, _, _ = _req("GET", K + "/v1/components", token=rs)
        xfail("FOUNDATIONS", "FND-1/FND-3",
              "home-issued admin role-claim (no recorded grant) refused at kernel admin (abuse) [debt DEBT-B1]",
              st2 not in (401, 403),
              "rolesteward (platform.tenant-admin CLAIM, no recorded grant) GET /v1/components -> %s (rule: deny 401/403; DEBT-B1: token role honoured as authority)" % st2)
    # The remaining Kernel-relevant NO-TEST rules are not cleanly black-box reachable; record WHY + the proposed
    # internal (pytest) test. kind 'needs-build' → SKIP_BUILD (matrix: PLANNED(needs-build)). See KERNEL-REVIEW.md.
    def nb(spec, rule, name, why): record(spec, rule, name, "needs-build", "SKIP_BUILD", why)
    nb("REGISTRY","REG-2","schema-governed writes; no ungoverned/ad-hoc shapes",
       "no black-box registry-write bridge; review VIOLATED-leaning (ungoverned shapes pass unvalidated; kernel stamps latest not caller-declared version — app.py:2297/2296). Internal test: POST kernel /v1/registry/objects an unknown schema -> assert refused.")
    nb("REGISTRY","REG-4","valid + recorded time",
       "held per review; not black-box (no write bridge). Internal test EXISTS: kernel/tests/test_registry_bitemporal.py.")
    nb("REGISTRY","REG-8","Kernel/participant signature on each committed version",
       "VIOLATED per review: versions are SHA-256 content-hashed, not signed (store.py:35-37; audit_verify.py:20-24). Not black-box (needs an authed read of a known record). Internal test: resolve a committed version -> assert a kernel Ed25519 signature present (currently none).")
    nb("REGISTRY","REG-9","idempotent writes (content-hash dedup)",
       "held per review (pg_store.py:202-207); not black-box (no write bridge). Internal test: write a byte-identical object twice -> assert one version, same ref.")
    nb("REGISTRY","REG-11","schemas are records; owner != adopter",
       "largely Network-owned: the kernel fetches defs upward (app.py:2269). Belongs to the Network review. Kernel-side internal test: /v1/registry/schemas/local is dev-tenant-gated and may not shadow a governed schema (app.py:797).")
    nb("REGISTRY","REG-18","files are records (Kernel-mediated bytes)",
       "VIOLATED per review: /v1/file/{put,get} gate only on run-token presence, no per-file authority/receipt (app.py:1632-1666). Internal test (needs a stored-blob fixture): fetch a blob by digest with a run token lacking a file grant -> assert refused.")
    nb("FOUNDATIONS","FND-12","every authz decision audited (allow+deny); failed-auth logged",
       "PARTIAL per review: only the admin gate + egress audit; general read/write denials and failed authentication emit no record (app.py:1105,1225; kernelcore.py:44). Audit store not black-box readable. Internal test: assert an audit row on an allow AND a deny at a non-admin gate, and on a failed authentication.")
    nb("DECISION","DEC-2","decision record contents",
       "no decision-record read surface and the kernel authz path emits none (decision lib disconnected; DEC-1 violated). Internal test: drive the authz gate -> assert a record with case_ref + version-pinned admitted_basis + named authority + reason.")
    nb("DECISION","DEC-5","decision records never edited",
       "held-by-construction (governed append-only, REG-3) but not exercised on the kernel path. Internal test: supersede a decision -> assert new version + original marked contested, no in-place edit.")
    nb("DECISION","DEC-9","decisions linked (correlation/op ids) to CRs + audit",
       "PARTIAL per review: the adminaudit correlation_id threads nothing beyond its own row (app.py:35). Internal test: assert one correlation id links the decision record, the ChangeRequest, and the audit event.")
    nb("COMPONENT","CMP-3","run token = declaration ∩ authority",
       "declaration∩tenant half held; the ∩-runner-authority half absent (run token is a bearer secret; app.py:1119). Broker caps covered by kernel/tests/test_broker_caps.py. Internal test: a run token presented by a principal lacking the run's authority is refused.")
    nb("COMPONENT","CMP-6","records & files only via the broker under run token + declared scopes",
       "records side held (broker attribution+receipt, broker.py:79-137); files side VIOLATED = REG-18; dataplane sideload gate DATAPLANE_ENFORCE shadow by default (kernelcore.py:62). Internal test: write a fact-schema record with a bare tenant token (not via broker) -> assert refused when DATAPLANE_ENFORCE on.")

# ============================ runner ============================
import re as _re
_SPEC_RULE_RE = _re.compile(r"\b(?:FND|REG|DEC|NET|CLI|PLT|CMP|OFF|POL|PTC)-\d+[a-z]?\b|\bACC-W?\d+\b|\bFED\d+\b")
def _rules_of(rule_field):
    """Spec-rule IDs a case cites (from its slash-tagged rule label); excludes DEBT-*/FIND-*/ADR-* refs."""
    return sorted(set(_SPEC_RULE_RE.findall(rule_field or "")))

def emit_matrix(mode):
    """`--matrix`: write conformance/results/<env>-<mode>.json — one record per case with its spec rules,
    for build_matrix.py to reduce into docs/specs/STATUS-MATRIX.md. No human report."""
    import subprocess
    env = os.environ.get("AOS_ENV", "local-dev")
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        sha = os.environ.get("GIT_SHA", "")
    out = {
        "env": env, "mode": mode, "base": (INTERNAL["kernel"] if mode == "internal" else BASE),
        "git_sha": sha, "ts": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "cases": [{"case": r["name"], "spec": r["spec"], "rule": r["rule"],
                   "rules": _rules_of(r["rule"]), "mode": mode, "result": r["status"]} for r in RESULTS],
    }
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s-%s.json" % (env, mode))
    with open(p, "w") as f: json.dump(out, f, indent=2)
    print("[matrix] wrote %s (%d cases, env=%s mode=%s sha=%s)" % (p, len(out["cases"]), env, mode, sha))

def report(mode):
    specs = ["FOUNDATIONS","REGISTRY","DECISION","NETWORK","ACCOUNT","CLIENT","PLATFORM"]
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
    skipped = [r for r in RESULTS if r["status"] in ("SKIP_CREDS","SKIP_BUILD")]
    if skipped:
        print("\nSkipped cases (per-case — a credentialed run should show 0 SKIP_CREDS):")
        for r in skipped:
            print("  [%-10s] %-14s %-9s %s — %s" % (r["status"], r["spec"], r["rule"], r["name"], r["detail"]))
    return tot

def main():
    print("AirawatOS conformance suite — mode=%s" % MODE)
    if MODE == "internal":
        print("internal targets:", ", ".join("%s=%s" % (k, v) for k, v in INTERNAL.items()))
        # preflight on kernel
        st, _, _ = _req("GET", INTERNAL["kernel"]+"/healthz")
        if st != 200: print("PREFLIGHT: kernel:8080/healthz -> %s" % st)
        run_internal_cases(); run_kernel_review_cases()
    else:
        print("target %s (realm %s); credentials: %s" % (BASE, REALM, "supplied (%d)"%len(CREDS) if CREDS else "none"))
        st, _, _ = http("GET", "/healthz")
        if st != 200: print("PREFLIGHT FAIL: %s/healthz -> %s" % (BASE, st)); sys.exit(2)
        run_no_cred_cases(); run_cred_cases(); run_needs_build()
    if "--matrix" in sys.argv or os.environ.get("AOS_MATRIX"):
        emit_matrix(MODE)
        sys.exit(1 if any(r["status"] == "FAIL" for r in RESULTS) else 0)
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

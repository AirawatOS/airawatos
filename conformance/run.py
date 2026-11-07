#!/usr/bin/env python3
"""AirawatOS conformance suite (Consolidation Phase 3) — black-box, two modes.

Tests externally observable behaviour only (HTTP status, returned records). No service code is imported or
inspected. Full rule -> cases -> classification map: Airawat/docs/conformance/PLAN.md.

Modes (env AOS_MODE):
  external (default) — via the edge nginx at AOS_BASE (default http://127.0.0.1:8080): /network/* (federation),
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
    "runtime-manager": "http://runtime-manager:8105",
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
    # ARC-5 (FIX-PLAN L1 slice-1a) — the edge exposes ONLY the App Host front door + the federation door. The
    # Kernel door is internal-only: every /kernel/* is refused at the edge (was proxied to kernel:8080; removed).
    # So an external client cannot reach the Kernel at all. The Kernel's OWN authz (forged-token/anon-write/
    # anon-read/unknown-schema) is now exercised in INTERNAL mode against kernel:8080 (run_internal_cases),
    # where the Kernel is actually reachable — not via a door that must not exist.
    for p in ("/kernel/v1/registry/resolve", "/kernel/v1/registry/objects", "/kernel/v1/registry/exists"):
        st, _, _ = http("POST", p, {"filter": {"schema": "network.network"}})
        expect("FOUNDATIONS", "ARC-5/FND-8", "edge does not expose the Kernel door: %s (abuse)" % p,
               st in (403, 404) or st == 0, "edge %s -> %s (want 404/403/unreachable, never 2xx)" % (p, st))

    st, _, _ = http("POST", "/network/v1/governance/roles", {})
    expect("NETWORK", "NET-3", "anonymous governance role-write denied (abuse)", st in (401, 403),
           "anon network governance -> %s" % st)

    # slice-1c-iv step 4 (DEBT-B64) — the inbound channel gateway secret moved to Vault: an anonymous intake and one
    # presenting the RETIRED demo literal that older images baked as ENV are both refused at the edge.
    for _gp in ("/bridge/sms-intake", "/bridge/message-intake"):
        _gb = {"tenant": "localdev", "from": "+0000", "text": "conformance probe"}
        st_a, _, _ = http("POST", _gp, _gb)
        st_l, _, _ = http("POST", _gp, _gb, headers={"X-Gateway-Token": "sms-gw-" + "demo-2026"})
        expect("PLATFORM", "PLT-15/DEBT-B64", "channel gateway %s refuses anon + the retired baked literal (abuse)" % _gp,
               st_a == 403 and st_l == 403, "anon -> %s, retired literal -> %s (want 403/403)" % (st_a, st_l))

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
    # ARC-5: the Kernel door is internal-only, so an external caller lists components through the App Host door
    # (/bridge/components), not /kernel/v1/components. The leak-check (no run_token in the listing) still applies.
    st0, b0, _ = http("GET", "/bridge/components", cookie=cookie)
    n = 0
    try:
        j0 = json.loads(b0); n = len(j0.get("components", j0.get("installed", [])))
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
    st, body, _ = http("GET", "/bridge/components", cookie=cookie)
    if "run_token" in body:
        xfail("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]", True,
              "GET /bridge/components (populated) CONTAINS run_token — leak reproduced; %s" % note)
    else:
        expect("REGISTRY", "DEBT-B15", "components list does not leak run_token (abuse) [debt DEBT-B15]", True,
               "GET /bridge/components (populated: %s) has no run_token" % note)

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
        expect("FOUNDATIONS","FND-10/DEBT-B5","filestore refuses an anonymous call (abuse)", _stfa in (401,403),
               "anon /files -> %s (ENFORCE — slice-1c-ii: app-host/kernel/launcher all mint svc:filestore; closes A72)" % _stfa)
    # ADR-0124 slice-1c-ii — notify ENFORCES a svc:notify gate (decision + workflow mint it). Anonymous refused;
    # a WRONG-AUDIENCE token (addressed to another door) refused.
    _n_anon, _n_b, _ = _req("POST", T["notify"]+"/notify", body={"actor":"x","title":"probe"})
    if _n_anon == 0:
        record("FOUNDATIONS","FND-10/DEBT-B5","notify /notify refuses an anonymous call (abuse)","expected-fail","SKIP_BUILD","notify unreachable")
    else:
        expect("FOUNDATIONS","FND-10/DEBT-B5","notify /notify refuses an anonymous call (abuse)", _n_anon in (401,403),
               "anon /notify -> %s (ENFORCE — slice-1c-ii)" % _n_anon)
    if _fs_wrong:
        _stnw, _bnw, _ = _req("POST", T["notify"]+"/notify", body={"actor":"x","title":"probe"}, token=_fs_wrong)
        expect("FOUNDATIONS","FND-10/DEBT-B5","notify refuses a wrong-audience token (another door)", _stnw == 403,
               "svc:automation token -> %s (expect 403; notify accepts svc:notify only)" % _stnw)
    else:
        record("FOUNDATIONS","FND-10/DEBT-B5","notify refuses a wrong-audience token (another door)","needs-creds","SKIP_CREDS","no svc:automation token")
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
    # ADR-0124 slice-1c-ii — model-gateway ENFORCES a svc:model-gateway gate on /complete,/embed,/transcribe
    # (kernel mints for /complete, app-host for the rest). Anonymous refused; WRONG-AUDIENCE refused.
    _m_anon, _m_b, _ = _req("POST", T["model-gateway"]+"/complete", body={"messages":[{"role":"user","content":"x"}]})
    if _m_anon == 0:
        record("FOUNDATIONS","FND-10/DEBT-B5","model-gateway /complete refuses an anonymous call (abuse)","expected-fail","SKIP_BUILD","model-gateway unreachable")
    else:
        expect("FOUNDATIONS","FND-10/DEBT-B5","model-gateway /complete refuses an anonymous call (abuse)", _m_anon in (401,403),
               "anon /complete -> %s (ENFORCE — slice-1c-ii)" % _m_anon)
    if _fs_wrong:
        _stmw, _bmw, _ = _req("POST", T["model-gateway"]+"/complete", body={"messages":[{"role":"user","content":"x"}]}, token=_fs_wrong)
        expect("FOUNDATIONS","FND-10/DEBT-B5","model-gateway refuses a wrong-audience token (another door)", _stmw == 403,
               "svc:automation token -> %s (expect 403; model-gateway accepts svc:model-gateway only)" % _stmw)
    else:
        record("FOUNDATIONS","FND-10/DEBT-B5","model-gateway refuses a wrong-audience token (another door)","needs-creds","SKIP_CREDS","no svc:automation token")
    # ADR-0124 item 1 (service armed) — automation /events now REQUIRES a svc:automation|platform token.
    # Promoted from the tokenless-abuse probe to a real assertion (anon + wrong-audience refused), mirroring
    # scheduler (slice-5 review F5: the gate is ARMED in local-dev via AUTOMATION_EVENTS_REQUIRE_TOKEN but was
    # still only probed shadow-style, so its armed state was never proven by a PASS).
    _a_anon, _a_b, _ = _req("POST", T["automation"]+"/events", body={})
    if _a_anon == 0:
        record("FOUNDATIONS","FND-10/DEBT-B5","automation /events requires a service token (abuse)","expected-fail","SKIP_BUILD","automation unreachable (%s)"%_a_b[:40])
    else:
        expect("FOUNDATIONS","FND-10/DEBT-B5","automation /events refuses an anonymous call (abuse)", _a_anon in (401,403),
               "anon /events -> %s (expect 401/403)" % _a_anon)
        # Wrong-audience rejection is already unit-proven by test_automation_ingress.py (svc:app-host refused);
        # not repeated here because the scheduler principal cannot mint a wrong-but-mintable audience for
        # automation under the identity audience allow-list (would only add a SKIP_CREDS).
    # FND-9 / debt DEBT-B4 — fail-open internal-token gates
    # ADR-0124 slice-1c-iii — secrets /materialize + /fetch now ENFORCE svc:secrets (from {kernel,launcher});
    # A71 literal retired. Anonymous refused; a wrong-audience token (addressed to another door) refused.
    for _ep in ("/materialize", "/fetch"):
        _ss, _sb, _ = _req("POST", T["secrets"] + _ep, body={})
        if _ss == 0:
            record("FOUNDATIONS","FND-9/A71","secrets %s refuses an anonymous call (abuse)" % _ep,"expected-fail","SKIP_BUILD","secrets unreachable")
        else:
            expect("FOUNDATIONS","FND-9/A71","secrets %s refuses an anonymous call (abuse)" % _ep, _ss in (401,403),
                   "anon %s -> %s (ENFORCE svc:secrets — slice-1c-iii)" % (_ep, _ss))
    if _fs_wrong:
        _sw, _swb, _ = _req("POST", T["secrets"]+"/fetch", body={"url":"http://x"}, token=_fs_wrong)
        expect("FOUNDATIONS","FND-9/A71","secrets /fetch refuses a wrong-audience token (another door)", _sw == 403,
               "svc:automation token -> %s (expect 403; secrets accepts svc:secrets only)" % _sw)
    else:
        record("FOUNDATIONS","FND-9/A71","secrets /fetch refuses a wrong-audience token (another door)","needs-creds","SKIP_CREDS","no svc:automation token")
    # slice-1c-iv step 2 — the runtime manager now RUNS in local-dev (placement authority; the scheduler delegates).
    # Gate: svc:runtime-manager from {kernel, launcher, scheduler}, always enforce.
    _RM = T["runtime-manager"] + "/v1/invoke"; _rb = {"component": "__conformance__/absent", "run_token": "x"}
    _ra, _, _ = _req("POST", _RM, _rb)
    if _ra == 0:
        record("FOUNDATIONS","FND-9/A71","runtime-manager /v1/invoke refuses an anonymous call (401)","expected-fail","SKIP_BUILD","runtime-manager unreachable")
    else:
        expect("FOUNDATIONS","FND-9/A71","runtime-manager /v1/invoke refuses an anonymous call (401)", _ra == 401,
               "anon -> %s (want 401)" % _ra)
        if _fs_wrong:
            _rw, _, _ = _req("POST", _RM, _rb, token=_fs_wrong)
            expect("FOUNDATIONS","FND-9/A71","runtime-manager refuses a wrong-audience token (403)", _rw == 403,
                   "svc:automation token -> %s (want 403)" % _rw)
        else:
            record("FOUNDATIONS","FND-9/A71","runtime-manager refuses a wrong-audience token (403)","needs-creds","SKIP_CREDS","no svc:automation token")
        _up = _login_token("svcprobe","localdev-operator","secret/data/localdev-operator/svcprobe/password","svc:runtime-manager")
        if _up:
            _ru, _, _ = _req("POST", _RM, _rb, token=_up)
            expect("FOUNDATIONS","FND-9/A71","runtime-manager refuses an UNDECLARED caller holding svc:runtime-manager (403)", _ru == 403,
                   "svcprobe svc:runtime-manager -> %s (want 403: not on the allow-list)" % _ru)
        else:
            record("FOUNDATIONS","FND-9/A71","runtime-manager refuses an UNDECLARED caller holding svc:runtime-manager (403)","needs-creds","SKIP_CREDS","no svcprobe token (dev fixture)")
        for _who in ("scheduler", "kernel"):
            _dt = _login_token(_who,"localdev-operator","secret/data/localdev-operator/%s/password" % _who,"svc:runtime-manager")
            if not _dt:
                record("FOUNDATIONS","FND-9/A71","runtime-manager admits the DECLARED caller %s (pos)" % _who,"needs-creds","SKIP_CREDS","no %s svc:runtime-manager token" % _who); continue
            _rd, _rdb, _ = _req("POST", _RM, _rb, token=_dt)
            # admitted ⇒ the handler ran: an absent component is a 404 "unknown component", never 401/403
            expect("FOUNDATIONS","FND-9/A71","runtime-manager admits the DECLARED caller %s (pos)" % _who,
                   _rd == 404 and "unknown component" in _rdb, "%s svc:runtime-manager -> %s %s" % (_who, _rd, _rdb[:60]))
    # slice-1c-iv step 3 — kernel /v1/components/run-token: the ONE run-token disclosure door, scheduler-only.
    _KRT = T["kernel"] + "/v1/components/run-token"; _kb = {"component_id": "ds:none:engine/absent", "tenant": "localdev"}
    _ka, _, _ = _req("POST", _KRT, _kb)
    expect("FOUNDATIONS","FND-8/B15","kernel run-token door refuses an anonymous call", _ka in (401, 403), "anon -> %s" % _ka)
    _cp, _ = _mint_component_publisher_token()
    if _cp:
        _kc, _, _ = _req("POST", _KRT, _kb, token=_cp)
        expect("FOUNDATIONS","FND-8/B15","kernel run-token door refuses a non-scheduler platform service (component-publisher)",
               _kc == 403, "component-publisher -> %s (want 403)" % _kc)
    _st = _login_token("scheduler","localdev-operator","secret/data/localdev-operator/scheduler/password")
    if _st:
        _ks, _ksb, _ = _req("POST", _KRT, _kb, token=_st)
        expect("FOUNDATIONS","FND-8/B15","kernel run-token door admits the scheduler (pos; absent install → 404)",
               _ks == 404, "scheduler -> %s %s" % (_ks, _ksb[:60]))
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
    # Kernel authz properties, migrated here from the external suite when ARC-5 (slice-1a) removed the /kernel/
    # edge route — the Kernel is reachable only internally now, so these probe kernel:8080 directly.
    st, _, _ = _req("POST", T["kernel"]+"/v1/registry/resolve", {"filter": {"schema": "network.network"}}, token=forged_jwt())
    expect("FOUNDATIONS","FND-1/FND-3/FND-15","forged role+foreign-iss token rejected (internal, abuse)",
           st in (401, 403), "kernel:8080 resolve w/ forged bearer -> %s" % st)
    st, _, _ = _req("POST", T["kernel"]+"/v1/registry/objects",
                    {"id": "conf:probe:1", "object": {"schema": "viz.layer", "id": "conf:probe:1"}})
    expect("FOUNDATIONS","FND-8","anonymous kernel write denied (internal, abuse)", st in (401, 403),
           "kernel:8080 anon write -> %s (want 401/403)" % st)
    st, _, _ = _req("POST", T["kernel"]+"/v1/registry/objects",
                    {"id": "conf:probe:2", "object": {"schema": "viz.layer", "id": "conf:probe:2"}}, token=forged_jwt())
    expect("REGISTRY","REG-5","forged-token write denied (internal, abuse)", st in (401, 403),
           "kernel:8080 forged write -> %s" % st)
    st, bq, _ = _req("POST", T["kernel"]+"/v1/registry/exists", {"id": "network.network"})
    if st in (0, 404):
        record("REGISTRY","REG-6","anonymous existence-check denied (internal, abuse)","expected-fail","SKIP_BUILD",
               "kernel:8080 /v1/registry/exists not reachable (%s)" % st)
    else:
        xfail("REGISTRY","REG-6","anonymous existence-check denied (internal, abuse) [debt DEBT-A1]", st == 200,
              "kernel:8080 anon exists -> %s (rule 401; live-violation 200)" % st)
    st, bq, _ = _req("POST", T["kernel"]+"/v1/registry/resolve",
                     {"filter": {"schema": "zzz.conformance_unknown_%d" % int(time.time())}})
    expect("FOUNDATIONS","FND-6/REG-13","unknown schema handled opaquely (internal, pos)",
           st == 200 and '"results"' in bq, "kernel:8080 resolve unknown schema -> %s" % st)

def run_internal_services_review_cases():
    """Consolidation phase-5 INTERNAL SERVICES + GATEWAYS review (slice 5). The slice's substantive risks all
    map to EXISTING debt already encoded in run_internal_cases() (unauth/shadow ingress DEBT-B5/A72, shared
    literals DEBT-B4/A71/A37, authority-from-claim DEBT-B1/B3). These two cases cover the slice's only NEW
    findings; both are code-audit facts not black-box-reachable on a seeded healthy local-dev stack, so they
    are recorded SKIP_BUILD with the proposed unit test (per the review method)."""
    # DEBT-B49 (FND-10) — filestore has NO tenant segment in its content-addressed path, so even once
    # FILESTORE_REQUIRE_TOKEN flips on, any allow-listed caller can GET any tenant's blob by digest. Not
    # black-box-reproducible today (gate is shadow; once gated it needs a known cross-tenant digest).
    record("FOUNDATIONS","FND-10/DEBT-B49","filestore blob path carries no owning-tenant scope (cross-tenant read once gated)",
           "expected-fail","SKIP_BUILD",
           "filestore.py:42-44 _path=DATA/<hex[:2]>/<hex>, no tenant; gate (filestore.py:63-70) checks aud+caller, never owner tenant. "
           "Proposed unit test: seed two tenants' blobs, assert tenant-A token cannot GET tenant-B digest once the gate is armed.")
    # DEBT-B50 (content safety) — docrender.md_to_html strips <script> but passes SVG event handlers
    # (onload=) and javascript: link schemes through; safe on /bridge/component-docs only because that route
    # sets script-src 'none', but /bridge/doc-render returns the raw fragment as JSON and build_portal renders
    # full pages from the same lib. Verified by direct md_to_html probe (see INTERNAL-SERVICES-REVIEW.md).
    record("CLIENT","PLT-14/DEBT-B50","docrender shared renderer does not neutralise active content (latent stored XSS)",
           "expected-fail","SKIP_BUILD",
           "docrender.py:22 (link href, no scheme allow-list) + :53-57 (svg fence strips <script> only, leaves onload=/<foreignObject>). "
           "Proposed unit test: md_to_html('[x](javascript:...)') and an svg-onload fence, assert the js scheme + event handler are stripped.")

def run_components_review_cases():
    """Consolidation phase-5 COMPONENTS + SDKs review (slice 6). The slice's findings split into (a) items
    already encoded against existing debt — the CLI-6/PTC-12 `/bridge`-as-protocol family (DEBT-A23; the
    client-SDK aos.js embodiment), embed scope→service:* consent (DEBT-B12), capability self-assertion with the
    steward-grant gate default-off (DEBT-A4), connector SSRF filter (DEBT-A11/B16) — and (b) six NEW findings
    (B51-B56). The confined-runtime broker door and the aos SDK runtime are SOUND (broker-only /v1/*, fail-closed
    token gate, no self-asserted roles). The NEW findings are code-audit facts whose black-box reproduction needs
    fixtures the seeded healthy local-dev stack does not ship (a planted component, a cert'd component with
    differing on-disk bytes, a run-token to replay, a component_asset with no network listing), so they are
    recorded SKIP_BUILD with the proposed test — their rules (CMP-5/6/7, FND-8/9/10) are already VIOLATED in the
    matrix from other cases, so the matrix reduction is unchanged. See COMPONENTS-SDK-REVIEW.md."""
    record("COMPONENT","CMP-5/CMP-6/DEBT-B51","default/in-process component runtime inherits full host env (no confinement)",
           "expected-fail","SKIP_BUILD",
           "launcher.py:248-261 runs a no-profile component as a host subprocess with dict(os.environ,...). "
           "Proposed test: install a component that prints os.environ; assert SECRETS_INTERNAL/SECRETS_URL are NOT present (scrubbed env).")
    record("COMPONENT","CMP-5/CMP-11/DEBT-B52","placed component container has no egress confinement (flat internal net)",
           "expected-fail","SKIP_BUILD",
           "launcher.py:310-320,450-455 docker run with no --network none / egress proxy / host allow-list. "
           "Proposed test: from a placed container, assert a direct POST to filestore:8095/kernel:8080 is refused by network policy (not merely by the service gate).")
    record("COMPONENT","CMP-3/FND-9/DEBT-B53","run-token has no expiry and no audience (replayable)",
           "expected-fail","SKIP_BUILD",
           "kernel app.py:1126-1130 _run_spec is a bare dict lookup (no exp/aud/iss). "
           "Proposed test: capture a run-token, replay /v1/write after a delay / with a wrong audience expectation; assert refusal.")
    record("COMPONENT","CMP-7/FND-8/DEBT-B54","on-demand filestore delivery is fail-open + trusts an unsigned listing digest",
           "expected-fail","SKIP_BUILD",
           "app_host.py:3771-3775 refuses only `if want and got!=want`; want is a try/except network-store value, never verify_certificate'd (store.py:82 stores no signature). "
           "Proposed test: seed a platform.component_asset with NO matching network listing, trigger on-demand invoke; assert it REFUSES (currently materialises).")
    record("COMPONENT","CMP-7/FND-8/DEBT-B55","launch-time digest rebind enforced only on the baked path",
           "expected-fail","SKIP_BUILD",
           "host.py:206 gates the artifact_digest recompute behind `if baked and cert`; un-baked (default) bind-mounts without rebinding. "
           "Proposed test: launch a cert'd component with host.launch(baked=False) and on-disk bytes != certified digest; assert refusal (currently runs).")
    record("COMPONENT","CMP-7/FND-8/DEBT-B56","unverified-digest certify accepted; host ignores conformance.verified",
           "expected-fail","SKIP_BUILD",
           "network/api.py:1327-1328 signs a caller-supplied evidence_digest with conformance.verified=false; host.py:87 checks only status=='valid'. "
           "Proposed test: POST /v1/certify with only evidence_digest=<arbitrary>, publish, deliver; assert host refuses the conformance.verified=false cert.")

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

def _jwt_claims(tok):
    """Decode (NO verify) a JWT payload for claim inspection in review cases."""
    import base64 as _b64
    try:
        p = tok.split(".")[1]; p += "=" * (-len(p) % 4)
        return json.loads(_b64.urlsafe_b64decode(p))
    except Exception:
        return {}

def run_identity_review_cases():
    """Consolidation phase-5 Identity review (slice 2): tests for identity-relevant rules the review found
    VIOLATED / NO TEST. Internal mode (identity reachable). Expected-fail where the review found a violation;
    recorded SKIP_BUILD with the reason + proposed internal test otherwise. See docs/reviews/IDENTITY-REVIEW.md."""
    admin = _login_token("admin", "localdev-network", "secret/data/localdev-operator/admin/password")
    if not admin and CREDS.get("admin"):   # ADR-0131: the bootstrap pw is scrubbed post-install → use the fixture
        _c = CREDS["admin"]
        _st, _b, _ = _req("POST", INTERNAL["identity"] + "/login", {"username": "admin", "tenant": _c.get("tenant", "localdev-network"), "password": _c["password"]})
        admin = json.loads(_b).get("access_token") if _st == 200 else None
    if not admin:
        record("ACCOUNT","ACC-3","assurance reflects the real auth method","needs-creds","SKIP_CREDS","could not mint an admin token")
        record("ACCOUNT","ACC-2","account id permanent + distinct from the handle","needs-creds","SKIP_CREDS","could not mint an admin token")
        record("CLIENT","CLI-3","token app-addressed + carries a consent reference","needs-creds","SKIP_CREDS","could not mint an admin token")
    else:
        cl = _jwt_claims(admin)
        # ACC-3 — assurance must be COMPUTED from the real auth method (a password login >= AL1), in the spec
        # AL0–AL3 vocabulary. Today identity stamps a uniform "A0" (DEV_AUTH) even after a real password check —
        # off-vocabulary AND uncomputed (DEBT-B13/DEBT-A34). Violation reproduced → XFAIL.
        asr = str(cl.get("assurance") or "")
        xfail("ACCOUNT","ACC-3","assurance reflects the real auth method (AL-vocabulary, >=AL1 after password) [debt DEBT-B13]",
              (not asr.startswith("AL")) or asr == "AL0",
              "admin password-login token assurance=%r amr=%r (rule: computed AL>=1; DEBT-B13: uniform/off-vocabulary)" % (cl.get("assurance"), cl.get("amr")))
        # ACC-2 — the account should carry a PERMANENT id distinct from the login handle; today `sub` IS the
        # handle (user://<tenant>/<username>), so id == handle, no rename reservation (DEBT-B30). XFAIL.
        sub = str(cl.get("sub") or "")
        xfail("ACCOUNT","ACC-2","account id is permanent + distinct from the login handle [debt DEBT-B30]",
              sub.endswith("/admin"),
              "admin token sub=%r (rule: opaque permanent id != handle; today sub embeds the username)" % sub)
        # CLI-3 — token should be APP-ADDRESSED (aud = the client/app) and carry a CONSENT reference; today a
        # human login is platform-addressed (aud=\"airawatos\") with no consent claim (DEBT-B31; roles=DEBT-B1). XFAIL.
        aud = cl.get("aud"); has_consent = any(k in cl for k in ("consent","consent_ref","cnf","scope"))
        xfail("CLIENT","CLI-3","token app-addressed + carries a consent reference [debt DEBT-B31]",
              (aud in ("airawatos", None)) or (not has_consent),
              "admin token aud=%r consent_ref=%s (rule: app-addressed + consent ref; today platform-aud, no consent)" % (aud, has_consent))

    # ── DEBT-B28 (FND-1) — authority is NEVER granted by omission (HOTFIX; expected PASS) ───────────
    # Provision a BRAND-NEW account on the LIVE IdP with NO roles, set a password, log in, and inspect the
    # token: its roles claim must be EMPTY. Before the hotfix a roleless create defaulted to
    # platform.tenant-admin (full authority). See identity._apply_create_roles + test_identity_hotfix_b28_b29.py.
    # ADR-0131 / 1c-iv-c — provisioning is svc:identity-only: act as the provisioner (Vault-backed) like the installer.
    itok = _login_token("provisioner", "localdev-operator", "secret/data/localdev-operator/provisioner/password", "svc:identity")
    if not itok:
        record("FOUNDATIONS","FND-1/DEBT-B28","roleless-created account carries no authority","needs-creds","SKIP_CREDS","could not mint a provisioner svc:identity token")
    else:
        ih = {"Authorization": "Bearer " + itok}; pu, pt, ppw = "b28probe", "localdev-network", "B28-Probe-Pw-9x!q2"
        st_c, _, _ = _req("POST", INTERNAL["identity"]+"/users", {"username": pu, "tenant": pt}, headers=ih)   # NO roles field
        _req("POST", INTERNAL["identity"]+"/set-password", {"username": pu, "tenant": pt, "password": ppw}, headers=ih)
        st_l, b_l, _ = _req("POST", INTERNAL["identity"]+"/login", {"username": pu, "tenant": pt, "password": ppw})
        tok = ""
        try: tok = json.loads(b_l).get("access_token", "") if st_l == 200 else ""
        except Exception: tok = ""
        if st_c != 200 or not tok:
            record("FOUNDATIONS","FND-1/DEBT-B28","roleless-created account carries no authority","needs-creds","SKIP_CREDS","provision=%s login=%s"%(st_c, st_l))
        else:
            rr = _jwt_claims(tok).get("roles")
            expect("FOUNDATIONS","FND-1/DEBT-B28","a roleless-created account has NO roles — no authority by omission [DEBT-B28 fixed]",
                   rr == [], "b28probe token roles=%r (rule: omitted roles ⇒ [], never platform.tenant-admin)" % (rr,))

    # ── DEBT-B29 / DEBT-A71 (FND-9) — identity door is svc:identity-only (ADR-0131 / slice-1c-iv-c) ─────
    # accept svc:identity · allow {provisioner, app-host}@operator realm · verified against identity's own JWKS ·
    # always enforce. The unseeded-provisioner fail-closed branch + production boot refusal are unit-proven
    # (test_identity_hotfix_b28_b29.py) — not reachable black-box on a correctly-installed server.
    _IU = INTERNAL["identity"] + "/users"; _probe = {"username": "b29probe", "tenant": "localdev-network"}
    st_anon, _, _ = _req("POST", _IU, _probe)
    expect("FOUNDATIONS","FND-9/DEBT-B29","identity /users refuses an anonymous write (fail closed) [A71 closed]",
           st_anon in (401, 403), "anon POST /users -> %s (want 401/403)" % st_anon)
    st_lit, _, _ = _req("POST", _IU, _probe, headers={"X-Internal-Token": "airawat-ld-" + "identity-internal"})
    expect("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses the RETIRED shared literal (no literal gate)",
           st_lit in (401, 403), "retired X-Internal-Token literal -> %s (want 401/403)" % st_lit)
    _wa = _login_token("scheduler","localdev-operator","secret/data/localdev-operator/scheduler/password","svc:automation")
    if _wa:
        st_wa, _, _ = _req("POST", _IU, _probe, token=_wa)
        expect("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses a wrong-audience token (another door)",
               st_wa == 403, "svc:automation token -> %s (want 403)" % st_wa)
    else:
        record("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses a wrong-audience token (another door)","needs-creds","SKIP_CREDS","no svc:automation token")
    # undeclared caller: a principal NOT on the allow-list presenting the platform audience (the only audience a
    # non-allow-listed principal can mint) — refused; and identity /login refuses it an svc:identity token at all.
    _ud = _login_token("kernel","localdev-operator","secret/data/localdev-operator/kernel/password")
    if _ud:
        st_ud, _, _ = _req("POST", _IU, _probe, token=_ud)
        expect("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses an UNDECLARED caller (kernel, not allow-listed)",
               st_ud == 403, "kernel platform-aud token -> %s (want 403)" % st_ud)
        _kd = _login_token("kernel","localdev-operator","secret/data/localdev-operator/kernel/password","svc:identity")
        expect("FOUNDATIONS","FND-9/DEBT-A71","identity /login refuses svc:identity to an undeclared principal (kernel)",
               _kd is None, "kernel svc:identity mint -> %s (want refused)" % ("TOKEN" if _kd else "refused"))
    else:
        record("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses an UNDECLARED caller (kernel, not allow-listed)","needs-creds","SKIP_CREDS","no kernel token")
    _ip = _login_token("svcprobe","localdev-operator","secret/data/localdev-operator/svcprobe/password","svc:identity")
    if _ip:
        st_ip, _, _ = _req("POST", _IU, _probe, token=_ip)
        expect("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses an UNDECLARED caller holding svc:identity (403)",
               st_ip == 403, "svcprobe svc:identity -> %s (want 403: not on the allow-list)" % st_ip)
    else:
        record("FOUNDATIONS","FND-9/DEBT-A71","identity /users refuses an UNDECLARED caller holding svc:identity (403)","needs-creds","SKIP_CREDS","no svcprobe token (dev fixture)")
    for _who, _pth in (("provisioner","secret/data/localdev-operator/provisioner/password"),
                       ("app-host","secret/data/localdev-operator/app-host/password")):
        _dt = _login_token(_who, "localdev-operator", _pth, "svc:identity")
        if not _dt:
            record("FOUNDATIONS","FND-9/DEBT-A71","identity directory admits the DECLARED caller %s (pos)" % _who,"needs-creds","SKIP_CREDS","no %s svc:identity token" % _who); continue
        st_ok, b_ok, _ = _req("GET", INTERNAL["identity"] + "/users?tenant=localdev-operator&page_size=5", token=_dt)
        expect("FOUNDATIONS","FND-9/DEBT-A71","identity directory admits the DECLARED caller %s (pos)" % _who,
               st_ok == 200 and '"users"' in b_ok, "%s svc:identity GET /users -> %s" % (_who, st_ok))

    def nb(spec, rule, name, why): record(spec, rule, name, "needs-build", "SKIP_BUILD", why)
    nb("FOUNDATIONS","FND-9","no passwordless full-authority mint (residual; write-gate half fixed by DEBT-B29)",
       "write-gate half FIXED (DEBT-B29, ADR-0131 form): POST /users,/set-password,/prefs + directory reads admit ONLY svc:identity from {provisioner,app-host}@operator (anon/literal/wrong-aud/undeclared refused — live PASS cases above); unseeded provisioner fails CLOSED and production refuses to boot (assert_provisioner_seeded) — all covered by platform-spec/reference/test_identity_hotfix_b28_b29.py. RESIDUAL (DEBT-B14/A26): passwordless principals (steward/scheduler) still mint under _PW_MODE=shadow; not reproducible on this local-dev config (IDENTITY_PASSWORD_REQUIRED=enforce → passwordless login refused). Internal test: a no-password principal login under shadow must refuse.")
    nb("FOUNDATIONS","FND-16","safe defaults (no prod-pointing default; enforce-by-default; fail-loud)",
       "PARTIAL per review: roleless-create default FIXED (DEBT-B28 — no longer platform.tenant-admin) and the identity door has no literal at all — svc:identity only + a prod boot guard on the provisioner (DEBT-B29/A71, ADR-0131). RESIDUAL: ISS/AUD/HOME_ISS default ds:airawat:identity/airawatos (identity.py:31,33; authn.py:74); _PW_MODE default shadow (:499); no fail-loud on missing issuer/audience. A config-default audit, not a runtime black-box case. Internal test: assert startup refuses when issuer/audience are unset.")
    nb("ACCOUNT","ACC-4","login + recovery; per-account-type recovery",
       "PARTIAL per review: login mechanics strong (Argon2id/PBKDF2, lockout, must-reset) but NO self-service recovery flow and no per-account-type recovery policy (DEBT-A77). Internal test: a rate-limited + audited recovery-initiate endpoint exists (not built).")
    nb("ACCOUNT","ACC-5","provider connections (consent + confirmation; revocable)",
       "not-identity: provider connection is the service-federation/app-host layer (ADR-0067); identity has no provider-connection surface. Test belongs to the app-host/service review.")
    nb("CLIENT","CLI-1","registered clients with recorded scopes",
       "not-identity: client registry (platform.app_client, recorded scopes) is app-host/embed (ADR-0112); identity registers users, not client apps. Test belongs to the app-host review.")
    nb("PLATFORM","PLT-3","operator holds no governance role (+ login-namespace != tenant, DEBT-B21)",
       "label note: PLT-3 is 'operator holds no governance role', not realm modelling. The login-namespace-as-tenant concern is DEBT-B21 (realms are tenant records; realm==tenant id — identity.py:620-628). Both are modelling/architecture, not a black-box runtime case. Internal test (B21): a person authenticates once and belongs to >1 org without a tenant-per-realm (blocked today).")


def run_network_review_cases():
    """Consolidation phase-5 NETWORK+TRUST review (slice 3): tests for the NETWORK / PARTICIPANT / FEDERATION
    rules and the TRUST-plane FOUNDATIONS rules the network service enforces. Internal mode (network reachable).
    After the slice-4 hotfixes the four reproducible violations (DEBT-B33/B34/B36) are asserted PASS (the
    anonymous gate refuses); the remaining rules are SKIP_BUILD with a reason + proposed internal/architectural
    test (DEBT-B35 is now fixed + unit-tested — installer-only bootstrap). See docs/reviews/NETWORK-REVIEW.md."""
    N = INTERNAL["network"]
    def _st(method, path, body=None):
        try:
            s, _, _ = _req(method, N + path, body); return s
        except Exception as e:
            return None
    def _req2(method, path, body=None):
        try:
            return _req(method, N + path, body)
        except Exception as e:
            return None, "", {}

    # ── FIXED violations (slice-4 hotfixes): the anonymous gate must now REFUSE. These assert the fix lands
    #    (PASS); if a gate regresses to open, the case FAILs. See docs/reviews/NETWORK-REVIEW.md. ──
    # NET-9 / DEBT-B34 (CRITICAL) — the capability-grant store must refuse an unauthenticated write.
    g = {"id": "ds:localdev:governance.access_grant/conf-unauth-probe", "steward": "ds:localdev:steward",
         "signature": "ZmFrZQ==", "reads": ["ds:localdev:probe.schema"], "writes": [],
         "object": {"kind": "governance.access_grant"}}
    s = _st("POST", "/v1/grants", g)
    expect("NETWORK", "NET-9/DEBT-B34", "capability-grant store POST /v1/grants refuses anonymous (grant.steward, fail closed)",
           s in (401, 403), "unauth POST /v1/grants -> %s (rule: 401/403 + grant.steward; DEBT-B34 fixed)" % s)
    # PTC-1 / FED7 / DEBT-B33 (CRITICAL) — the federation trust directory must refuse an unauthenticated bind.
    s = _st("POST", "/v1/participants", {"participant_id": "ds:confprobe:steward", "public_key": "AAAABBBBCCCC"})
    expect("PARTICIPANT", "PTC-1/FED7/DEBT-B33", "trust-directory admission POST /v1/participants refuses anonymous (authority-gated)",
           s in (401, 403), "unauth POST /v1/participants -> %s (rule: authority-gated; DEBT-B33 fixed)" % s)
    # NET-12 / DEBT-B36 — member list must refuse anonymous; service search must not leak members-only offerings.
    s = _st("GET", "/v1/participation?network=ds:localdev:network/self")
    expect("NETWORK", "NET-12/DEBT-B36", "member list GET /v1/participation refuses anonymous (members-only)",
           s in (401, 403), "anon GET /v1/participation -> %s (rule: members-only; DEBT-B36 fixed)" % s)
    st_ss, b_ss, _ = _req2("POST", "/v1/service/search", {})
    cat = []
    try: cat = ((json.loads(b_ss) or {}).get("message", {}) or {}).get("catalog", []) if st_ss == 200 else []
    except Exception: cat = []
    leaked = [o for o in cat if (o.get("visibility") or "members") != "public"]
    expect("NETWORK", "NET-12/DEBT-B36", "anonymous service search returns only public-designated offerings (members-only default)",
           (st_ss in (401, 403)) or (not leaked),
           "anon POST /v1/service/search -> %s, %d non-public offering(s) returned (rule: members-only default per REG-15; DEBT-B36 fixed)" % (st_ss, len(leaked)))

    # ── NO-TEST / not black-box reachable on a seeded healthy stack → SKIP_BUILD with reason + proposed test ──
    def nb(spec, rule, name, why): record(spec, rule, name, "needs-build", "SKIP_BUILD", why)
    # TRUST-plane FOUNDATIONS
    nb("FOUNDATIONS","FND-2/DEBT-B39","Trust audit chain is verified/reconciled at runtime",
       "VIOLATED (structural-only): platform.audit_event chain built with prev_hash/entry_hash/keyed-HMAC (trust/audit.py:76-111) but NO code reads a chain back to verify linkage and no op_id reconciler exists. Not black-box reachable. Internal test: tamper/supersede one audit row -> a verifier flags the broken prev_hash (verifier not built).")
    nb("FOUNDATIONS","FND-3","authority only from a recorded grant, never tenant name (TRUST plane)",
       "HELD in role mode (trust/roles.py:62-66 ignores token roles; authorize.py:82-117 candidate-grant lookup); VIOLATED in the shipped default where is_platform_authority = claims.tenant==authority_tenant (trust_wiring.py:67,79-83, PLATFORM_AUTHORITY_MODE=shadow default). local-dev runs enforce; EC2 default stays shadow. Covered by DEBT-B2. Internal test (shadow): a tenant-only token with no recorded grant manages all networks.")
    nb("FOUNDATIONS","FND-4","tenant != network (authority keyed on net:id, not tenant/slug)",
       "VIOLATED in the legacy default: NETWORK_ADMIN_AUTHZ=legacy makes admin authority = (tenant==network string) (trust_admin_authz.py:66-68) and cross_network_write conflates slug/net:id/tenant (trust_wiring.py:204). HELD in role mode (resolve slug->net:id, authorize on net:id, :224-235). local-dev=role, EC2=legacy. Covered by DEBT-B11/B2. Internal test (legacy): tenant.admin for tenant X writes the network whose slug==X with no role on it.")
    nb("FOUNDATIONS","FND-11/DEBT-B35","platform.authority first-holder bootstrap is installer-only",
       "FIXED (DEBT-B35): the zero-holder first-holder seed now requires ctx.is_installer (set only by the in-process installer, never by the HTTP governance path which builds the context from verified claims with is_installer=False) — trust/governance.py assign_role. Proven by the unit test network/trust/test_bootstrap_installer_only_b35.py (governance-path self-escalation REFUSED; installer seed allowed). Not black-box reachable on a seeded stack (a governed holder already exists), so it stays an internal/unit test, not a live conformance case.")
    nb("FOUNDATIONS","FND-11/DEBT-B38","SoD for floor roles enforces approver != proposer",
       "VIOLATED: SoD checks approver != grantee but not approver != proposer(ctx.actor) (trust/platform_authority.py:119; governance.py:122-128) — a live holder can propose a grant and self-approve as proposer. Internal test: two-holder setup; holder A proposes a grant to C and approves it as the sole approver -> must refuse.")
    nb("FOUNDATIONS","FND-14","role assignments carry grantor + governance provenance",
       "PARTIAL: governance path records granted_by+op_id+role.assign audit (trust/governed_store.py:283-300); but TRUST_ENFORCE_STEWARD_PROVENANCE=0 by default (EC2) still honours un-provenanced steward seeds (trust/roles.py:31,46-52). local-dev enforces. Covered by DEBT-A70. Internal test (provenance off): a role_assignment with no granted_by/op_id is honoured live.")
    # NETWORK plane
    nb("NETWORK","NET-2/DEBT-A78","a Network is a governed lifecycle object (creator role, DRAFT, governing tenant, empty-catalog gate)",
       "ABSENT (honest PLANNED): network_register stores only a directory profile with no status/creator/governing-tenant (api.py:961-997); members are accepted immediately (api.py:837). Not drivable (no DRAFT concept). Proposed test lands with the lifecycle object.")
    nb("NETWORK","NET-5/DEBT-A78","membership supports invite->accept and suspend",
       "PARTIAL: request->approve/reject/revoke + federated handshake present (api.py:813-893); invite->accept and a suspend state absent (status enum seed_base.py:195). Black-box round-trip needs admin creds. Proposed: drive /v1/participation/{request,decide} then assert an invite/suspend transition exists.")
    nb("NETWORK","NET-7/DEBT-B37","issuer trust is network.admin-only and scoped to (member-tenant, net:id)",
       "VIOLATED: participation_decide writes service-wide TRUSTED_ISS/register_issuer under op=membership (admits membership.steward, not network.admin-only) and with no net:id scope (api.py:880-891; trust_admin_authz.py:59). Needs creds to drive a federated approve. Internal test: approve a federated participation as membership.steward -> trust_established (should refuse); issuer then honoured across a different Network.")
    nb("NETWORK","NET-8","classifications are descriptive only (never gate exchange)",
       "TO-CONFIRM: no Network-level classification gates exchange directly, but classification-driven branches exist (eKYC auto-admit when participant_type.identity==citizen api.py:936-947; kind==developer dev surface authority.py:102-103). Architectural. Internal test: a classification flip alone changes an authorization outcome.")
    nb("NETWORK","NET-10/DEBT-A79","publishing a Service requires a recorded service.provide grant",
       "PARTIAL: service publish gated on a tenant-admin token role, not a recorded provide grant (api.py:2672); provide-grant only shadow-logged (api.py:1055). Needs creds. Internal test: a tenant-admin with no service.provide grant publishes an offering -> should refuse.")
    nb("NETWORK","NET-11/DEBT-A80","exchange runs through the one decision function and leaves a decision record",
       "PARTIAL: service_route records a transaction ledger but checks no call/provide grant, no consent, emits no governance.decision (api.py:3045-3055). Architectural. Internal test: a routed exchange produces a replayable governance.decision referencing the grant+consent.")
    # PARTICIPANT
    nb("PARTICIPANT","PTC-2","Network-boundary auth is identity-only (FND-15)",
       "HELD at the Network boundary: federated issuers pinned to one tenant + all roles stripped (authn.py:162-167). Covered live by the FND-15 abuse case (forged role+foreign-iss rejected). Residual DEBT-B1 is a kernel gate, not network.")
    nb("PARTICIPANT","PTC-3/DEBT-A79","Service registration carries iface/endpoint/version/data-use + a provide grant",
       "PARTIAL: iface/endpoint/version captured (api.py:1060-1063); gate is membership, service.provide only shadow-compared; data-use absent. Needs creds. Internal test: an approved member with no provide grant registers a Service -> should refuse.")
    nb("PARTICIPANT","PTC-5/DEBT-A80","inbound request carries a verified decision/consent reference; never widen",
       "PARTIAL: never-widen enforced as offering-scoping + fail-closed (api.py:2500-2545) but NO decision-ref/consent-ref is required or checked on any fulfil path. Internal test: a fulfil call with no decision_ref -> should refuse.")
    nb("PARTICIPANT","PTC-6","signed responses + fulfilment evidence joined to a decision",
       "PARTIAL: signed hub responses + grant-checked signed data-read receipt (hub.py:32-51; api.py:3549-3578); evidence not durably joined to a decision (in-memory). Black-box: granted read -> signed receipt; ungranted -> 403 (drivable with creds).")
    nb("PARTICIPANT","PTC-7","credential issuance requires a typed issue grant; signed; revocation published",
       "PARTIAL: signed with steward key, governed-type enforced, revocation published+checked (api.py:2820-2884,2932-2934); gate is member-of-issuing-tenant (any role), no per-type issue grant (_require_issuer api.py:2797-2808). Internal test: a member with no credential.issue:<type> grant issues that type -> should refuse.")
    nb("PARTICIPANT","PTC-8/DEBT-A81","presentation verification binds holder-proof/recipient/purpose/nonce (ACC-W3)",
       "PARTIAL/VIOLATED: verify checks issuer-sig + revocation + expiry only (api.py:2918-2940); no holder-proof/recipient/purpose/nonce binding -> a VC is replayable by a non-holder. Black-box: /v1/credentials/verify of a VC presented by a non-holder returns signature_valid with no audience check.")
    nb("PARTICIPANT","PTC-9","events: granted types only; interest != authority; idempotency",
       "ABSENT (honest PLANNED): no event publish/subscribe in the service (only a hub broadcast log). Proposed test lands with the event spine (ADR-0120).")
    nb("PARTICIPANT","PTC-10","settlement references",
       "ABSENT (honest PLANNED): no settlement model found. Proposed test lands with the settlement slice.")
    nb("PARTICIPANT","PTC-11","per-role conformance before activation",
       "ABSENT (honest PLANNED): conformance.run is component-only; participation/decide approves with no conformance/health gate (api.py:862-916; conformance.py:128-190). Internal test: approve a participant -> a per-role suite runs first.")
    nb("PARTICIPANT","PTC-12","one public versioned participant protocol; never /bridge",
       "ARCHITECTURAL: no /bridge/* in the network service (grep clean); the never-/bridge violation is first-party->app-host, outside this service; no single versioned participant protocol published yet. Covered elsewhere.")
    # FEDERATION
    nb("FEDERATION","FED1","one governing tenant hosts a Network",
       "PARTIAL: networks bootstrapped + directory profile (ensure_install.py:177; api.py:961-996); host-tenant-vs-operator framing not modelled. Architectural/PLANNED.")
    nb("FEDERATION","FED2","creation needs network.creator; never creates tenants",
       "PARTIAL/PLANNED: creation via bootstrap + /v1/networks (network-admin gated); no network.creator capability implemented. Internal test: a principal without network.creator creates a Network -> should refuse.")
    nb("FEDERATION","FED3","join = registration in host registry (id, roles, keys, conformance)",
       "PARTIAL: mode-1 request carries jwks + decide does a trust handshake (api.py:850-893); cross-install registration PLANNED; conformance field not gated. Black-box: /v1/participation/{request,decide} round-trip (with creds).")
    nb("FEDERATION","FED4","per-role conformance before activation",
       "ABSENT (honest PLANNED): no per-role suite/gate (see PTC-11).")
    nb("FEDERATION","FED5","cross-install requests signed by registered keys",
       "PARTIAL: the signed-relay primitive verifies envelopes against the directory (hub.py:18-30; mail relay api.py:3616-3661); the generalised cross-install Network request is PLANNED. Black-box: a tampered relay envelope -> verify_message false.")
    nb("FEDERATION","FED6/DEBT-B37","home issuer trusted only for its own participants, per-Network",
       "PARTIAL: FND-15 tenant-pin + role-strip real (authn.py:162-167), but trust is install-wide per-tenant, not per-Network — an issuer approved in Network X is honoured for that tenant across every Network on the install. Internal test: an issuer registered by joining Network X verifies tokens for a call scoped to Network Y.")
    nb("FEDERATION","FED7/DEBT-B40","host directory authoritative; resolve uses an exact steward match (no substring collisions)",
       "VIOLATED (two parts): admission is unauthenticated (covered by the PTC-1/FED7 XFAIL above) and /v1/resolve matches ds: refs by substring `steward in p` (api.py:3106) so steward='iit' matches 'ds:iitb:steward'. Needs two prefix-colliding participants to show the mis-resolve black-box. Internal test: register ds:iitb:steward then resolve ds:iit:x -> returns the iitb entry (wrong).")
    nb("FEDERATION","FED8","directory-of-Networks / root of trust",
       "DEFERRED in the spec (FED8). No test.")


def run_apphost_review_cases():
    """Consolidation phase-5 APP HOST + BRIDGES review (slice 4): the App Host is served at the PUBLIC ROOT on
    production (nginx location / -> app-host:8099), so any ungated route is internet-reachable. Internal mode
    (app-host reachable at app-host:8099). LIVE XFAIL for the black-box-reproducible, prod-verified violations;
    SKIP_BUILD (reason + proposed test) for the rest. See docs/reviews/APP-HOST-REVIEW.md."""
    AH = "http://app-host:8099"
    def _st(method, path, body=None, headers=None):
        try:
            s, _, _ = _req(method, AH + path, body, headers=headers); return s
        except Exception:
            return None

    # ── FIXED violations (slice-5 hotfixes): the anonymous gate must now REFUSE (expect PASS). ──
    # FND-8 / DEBT-B41 (CRITICAL) — /bridge/component-publish now VERIFIES the bearer (presence-only was the bug):
    # an invalid 'Bearer x' fails verification -> 401 before any body read/extract/publish.
    s = _st("POST", "/bridge/component-publish?component=ds:confprobe:app/x&version=0.0.1", None, {"Authorization": "Bearer x"})
    expect("FOUNDATIONS", "FND-8/DEBT-B41", "/bridge/component-publish refuses an unverified bearer (not presence-only)",
           s in (401, 403), "POST /bridge/component-publish 'Bearer x' + empty body -> %s (rule: verify token/publisher role -> 401/403; DEBT-B41 fixed)" % s)
    # NET-12 / DEBT-B42 — governed directory / governance-provenance bridges now require a session for anon.
    s = _st("POST", "/bridge/service-offerings", {})
    expect("NETWORK", "NET-12/DEBT-B42", "/bridge/service-offerings refuses anonymous (governed manage view)",
           s in (401, 403), "anon POST /bridge/service-offerings -> %s (rule: members-only; DEBT-B42 fixed)" % s)
    s = _st("POST", "/bridge/schemas", {})
    expect("NETWORK", "NET-12/DEBT-B42", "/bridge/schemas refuses anonymous (catalog + pending change-requests)",
           s in (401, 403), "anon POST /bridge/schemas -> %s (rule: authenticated; DEBT-B42 fixed)" % s)
    s = _st("POST", "/bridge/schema-history", {"schema_id": "governance.role_assignment"})
    expect("NETWORK", "NET-12/DEBT-B42", "/bridge/schema-history refuses anonymous (change-request provenance)",
           s in (401, 403), "anon POST /bridge/schema-history -> %s (rule: authenticated; DEBT-B42 fixed)" % s)

    # ── SKIP_BUILD: reproducible-but-not-safe-to-automate / architectural / needs a seeded fixture ──
    def nb(spec, rule, name, why): record(spec, rule, name, "needs-build", "SKIP_BUILD", why)
    nb("NETWORK","NET-12/DEBT-B42","/bridge/service-search shows anon only public-designated offerings (no audience bypass)",
       "FIXED (DEBT-B42): routes/service_routes.py now shows an anon caller only `audience=='civic.resident'` offerings (was `or not my_roles`, which disabled the filter). A clean black-box assert that an officer-only offering is excluded needs a seeded audience!=civic.resident offering (none on the seed). Internal test: seed such an offering; anon search must exclude it.")
    nb("FOUNDATIONS","FND-8/DEBT-B48","anon bridge reads/proxies fail closed (schedules/runs/fetch/doc-ask/retrieve)",
       "PARTIAL/VIOLATED: GET /bridge/schedules|/bridge/runs (app_host.py:10117) disclose component schedules + run errors anon; POST /bridge/fetch (:8685) is an anon host-allowlisted egress proxy (SSRF-bounded, DEBT-B16); POST /bridge/doc-ask (:9150) drives the model gateway anon (cost); POST /bridge/retrieve (knowledge_routes.py:41) passes empty claims to an unscoped kernel read (sibling expert-chat fails closed :25). Reachable anon. Proposed: session-gate the non-public ones; keep the kernel P0 fail-closed as backstop.")
    nb("CLIENT","CLI-2/DEBT-B12","/embed consent is intersected with the client's registered scopes",
       "VIOLATED: /embed/authorize + /embed/login take `scope` from the request and never intersect with client['scopes']; consent is written service='*'/scope='service:invoke' (app_host.py:1150,1212,1547,1557). Reachable at the public root but exploiting it needs a completed citizen login (writes a consent) — not safe to automate on a shared/prod stack. Internal test: drive authorize with scope beyond the client's registration -> consent must be clamped.")
    nb("CLIENT","CLI-3/DEBT-B31","/embed/token returns an app-addressed token carrying a consent reference",
       "VIOLATED: /embed/token returns the citizen's raw IdP realm JWT (app_host.py:1297) — not aud-bound to the client, no consent ref, roles inside; verify accepts any citizen JWT regardless of client (:1569). Needs a full code/verifier login flow to produce a token -> not safe to automate. Internal test: decode the /embed/token result -> aud == client_id and a consent ref present.")
    nb("CLIENT","CLI-5/DEBT-B43","/embed/signup does not leak account existence (anti-enumeration)",
       "VIOLATED: public POST /embed/signup returns a distinguishable 'username is taken' (409) vs a generic message (app_host.py:1268-1269), unauthenticated + unthrottled -> username-enumeration oracle. A black-box probe would create an account for a free name (a write) -> not run. Internal test: a taken vs free username return an identical response + rate-limit.")
    nb("CLIENT","CLI-4/DEBT-B44","client requests are signed by a key the CLIENT controls (not host-forged)",
       "VIOLATED: _embed_app_keypair generates + holds the client's Ed25519 key inside app-host and signs on its behalf (app_host.py:974-1003); with PKCE-only public clients (no client secret) there is effectively no client authentication, so the ADR-0024 'which app' signature proves nothing. Architectural. Internal test: the request signer key is one the client published, not a host-generated key.")
    nb("FOUNDATIONS","FND-5/DEBT-B45","session cookie is Secure + CSRF/Origin-checked on state-changing bridge POSTs",
       "VIOLATED: the airawat_sid cookie is HttpOnly+SameSite=Lax but omits Secure (app_host.py:2761,2783,2818) and there is NO CSRF token / Origin / Referer check on any cookie-authenticated state-changing /bridge/* POST (SameSite=Lax is the only barrier); sessions are in-memory (hostcore.py:94). Architectural/inspection. Internal test: Set-Cookie carries Secure; a cross-origin cookie-driven bridge POST is rejected.")
    nb("PLATFORM","PLT-15/DEBT-B46","public front door is apply/verify/status only, rate-limited + bot-protected + route-separated",
       "VIOLATED: unauth public POSTs /embed/signup, /t/<tenant>/converse, /t/<tenant>/telegram/webhook (app_host.py:2842-2867,5023,5044) have NO rate-limiting / CAPTCHA and share the handler/port with admin bridges; converse/telegram drive the model gateway -> unauth LLM cost-amplification. Load-generating to prove black-box -> not run. Internal test: >N rapid anon converse calls -> 429; front door on a separate route/limiter from admin.")
    nb("FOUNDATIONS","FND-8/DEBT-B47","account-hold (admin-disable) check fails CLOSED on registry error",
       "VIOLATED: _login_session admits a disabled login when the hold lookup errors (app_host.py:767-772, fail-open by design) — outside the FOUNDATIONS §3 protective-counter carve-out. Needs a registry fault to reproduce. Internal test: force the hold lookup to error -> login refused, not admitted.")
    nb("FOUNDATIONS","FND-1/DEBT-A82","App Host authority comes from a recorded grant, not the token's roles claim",
       "VIOLATED (dominant, DEBT-B1/A23 family): ~20 gates read claims['roles'] as authority (hostcore.py:126 ADMIN_ROLES; app_host.py:2190-2199 _effective_roles via:'identity'; and :3928/:4187/… ); several admin bridges set forward_token=False so the app-host role-claim check is the SOLE gate (participants :3930, participant-resolve :3945, service-offerings manage). Internal test (already live as kernel FND-1/DEBT-B1 XFAIL): a home-issued role claim with no recorded grant is honoured.")
    # FND-10/DEBT-A71 (app-host -> identity/gateway minted token) — RESOLVED: gateway = svc:model-gateway (slice-1c-ii),
    # identity = svc:identity as app-host's own principal (slice-1c-iv-c). Now live-asserted by the FND-9/DEBT-A71
    # identity-door cases (declared caller app-host admitted; anon / retired literal / wrong-aud / undeclared refused).
    nb("CLIENT","CLI-6/PTC-12/DEBT-A23","the public client/participant protocol is a versioned API, not /bridge/*",
       "VIOLATED/PLANNED: there is no /v1-versioned public protocol; the live surface is unversioned /embed/* + the internal /bridge/* RPC family served at the public root (app_host.py:2833 dispatch). Architectural (ADR-0023). The specific invariant 'never expose /bridge/* unauthenticated' is covered by the FND-8/NET-12 XFAILs above.")

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
        run_internal_cases(); run_kernel_review_cases(); run_identity_review_cases(); run_network_review_cases(); run_apphost_review_cases(); run_internal_services_review_cases(); run_components_review_cases()
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

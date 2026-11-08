"""Installer Phase 15 (dev profile) — the fresh install proves FUNCTION, not just startup (slice-1e).

Runs INSIDE the network container (it reaches the edge, identity, kernel, scheduler and Vault), fed on stdin by
install.sh with the install-time root VAULT_TOKEN. Two end-to-end checks, both must pass (exit 1 otherwise):

  A · a user is ONBOARDED THROUGH THE APP HOST: the tenant admin signs in at the edge, creates a login in their own
      tenant (/bridge/user-create → identity via app-host's svc:identity), the new user signs in at the edge with the
      admin-set password (must_reset), rotates it (/auth/change-password), and holds a live session in that tenant.
  B · an INSTALLED COMPONENT WRITES A RECORD WITHIN ITS GRANT: the tenant admin installs the delivered
      `engine/pipeline-probe-step` fixture (install-as-grant — the tenant steward signs a grant for its declared
      writes), the steward resolves in the Network directory (DEBT-B62), the scheduler runs it through the runtime
      manager under its own install token, its declared write (platform.inbox_item) is ACCEPTED and readable by the
      tenant, and an UNDECLARED write (platform.schedule) is REFUSED.

Env: INSTANCE, OPERATOR_PASSWORD (the install's admin password, held by the installer shell), VAULT_ADDR, VAULT_TOKEN.
"""
import base64, http.cookiejar, json, os, secrets, sys, time, urllib.error, urllib.request

INSTANCE = os.environ["INSTANCE"]; APW = os.environ["OPERATOR_PASSWORD"]
VA = (os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT = os.environ["VAULT_TOKEN"]
IDN, EDGE, KRN, SCH, NET = "http://identity:8093", "http://nginx", "http://kernel:8080", "http://scheduler:8103", "http://127.0.0.1:8090"
TENANT = INSTANCE                                   # the dev data tenant (SEED_DATA_TENANT=1)
OPERATOR = f"{INSTANCE}-operator"
CID = f"ds:{INSTANCE}-developer:engine/pipeline-probe-step"
RUN = "fn" + secrets.token_hex(3)
ok = True


def res(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("  ✓ " if cond else "  ✗ FAIL ") + name + (("  — " + str(detail)) if detail and not cond else ""))


def req(method, url, body=None, headers=None, opener=None, timeout=20):
    h = {"Content-Type": "application/json"}; h.update(headers or {})
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    try:
        resp = (opener.open if opener else urllib.request.urlopen)(r, timeout=timeout)
        b = resp.read(); return resp.status, (json.loads(b) if b[:1] in (b"{", b"[") else b.decode()[:300])
    except urllib.error.HTTPError as e:
        b = e.read()
        try: return e.code, json.loads(b)
        except Exception: return e.code, b.decode()[:300]


def browser():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def vpw(path):
    s, d = req("GET", f"{VA}/v1/{path}", headers={"X-Vault-Token": VT})
    return (((d or {}).get("data") or {}).get("data") or {}).get("password") if s == 200 else None


# ── A · onboard a user through the App Host ─────────────────────────────────────────────────────────────────
print(f"▶ A · onboard a user through the App Host (tenant {TENANT})")
adm = browser()
s, d = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": "admin", "password": APW}, opener=adm)
res(f"tenant admin admin@{TENANT} signs in at the App Host", s == 200 and d.get("ok"), f"{s} {d}")
un = "fnuser" + secrets.token_hex(3); tmp = secrets.token_urlsafe(12); new = secrets.token_urlsafe(12)
s, d = req("POST", f"{EDGE}/bridge/user-create", {"username": un, "password": tmp, "roles": []}, opener=adm)
res(f"admin creates {un} in its own tenant (/bridge/user-create → identity, app-host svc:identity)",
    s == 200 and d.get("created") == un and d.get("tenant") == TENANT, f"{s} {d}")
usr = browser()
s, d = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": un, "password": tmp}, opener=usr)
res(f"{un} signs in at the App Host with the admin-set password, must_reset:true",
    s == 200 and d.get("sub") == f"user://{TENANT}/{un}" and d.get("must_reset") is True, f"{s} {d}")
s, d = req("POST", f"{EDGE}/auth/change-password", {"new_password": new}, opener=usr)
res(f"{un} rotates the password through the App Host (/auth/change-password)", s == 200, f"{s} {d}")
s, d = req("GET", f"{EDGE}/session", opener=usr)
res(f"{un} holds a live App Host session in {TENANT}", s == 200 and f"user://{TENANT}/{un}" in json.dumps(d), f"{s} {d}")
fresh = browser()
s, d = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": un, "password": new}, opener=fresh)
res(f"{un} signs in again with the new password, must_reset cleared", s == 200 and not d.get("must_reset"), f"{s} {d}")
s, _ = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": un, "password": tmp})
res("the admin-set password no longer works", s == 401, s)

# ── B · an installed component writes a record within its grant ────────────────────────────────────────────
print(f"▶ B · installed component writes within its grant ({CID} in {TENANT})")
s, d = req("POST", f"{IDN}/realms/{TENANT}/login", {"username": "admin", "password": APW})
atok = (d or {}).get("access_token") if s == 200 else None
res(f"tenant admin token for {TENANT}", bool(atok), s)
H = {"Authorization": "Bearer " + (atok or "")}
s, d = req("POST", f"{NET}/v1/tenants/resolve", {"tenant_id": TENANT})
spid = (d or {}).get("steward_participant")
res(f"tenant record names the registered steward ds:{TENANT}:steward (DEBT-B62)", spid == f"ds:{TENANT}:steward", f"{s} {spid}")
s, d = req("POST", f"{NET}/v1/directory/resolve", {"participant_id": spid or ""})
res("the steward resolves in the Network directory with a key", s == 200 and isinstance(d, dict) and bool(d.get("keys")), f"{s} {str(d)[:160]}")
s, d = req("POST", f"{KRN}/v1/components/install", {"component_id": CID}, headers=H, timeout=60)
res("tenant admin installs the component (install-as-grant: steward-signed grant)", s == 200, f"{s} {str(d)[:200]}")
s, d = req("POST", f"{IDN}/login", {"username": "app-host", "tenant": OPERATOR, "aud": "svc:scheduler",
                                   "password": vpw(f"secret/data/{OPERATOR}/app-host/password")})
stok = (d or {}).get("access_token") if s == 200 else ""
s, out = req("POST", f"{SCH}/run", {"component": CID, "tenant": TENANT, "reason": "install-functional-check",
                                     "env": {"STEP": "fn", "PROBE_RUN": RUN, "PROBE_OUT_OF_GRANT": "1"}},
             headers={"Authorization": "Bearer " + stok}, timeout=600)
out = out if isinstance(out, dict) else {"raw": out}
log = out.get("log") or ""
res("scheduler runs the installed component (runtime manager, its own install token)",
    s == 200 and out.get("status") == "ok", f"{s} {str(out)[:300]}")
wl = [l for l in log.splitlines() if l.startswith("WRITE_RESULT")]
res("declared write (platform.inbox_item) ACCEPTED by the kernel broker", bool(wl) and wl[0].startswith("WRITE_RESULT ok"),
    wl[:1] or log[-300:])
ol = [l for l in log.splitlines() if l.startswith("OUTSIDE_GRANT_RESULT")]
res("undeclared write (platform.schedule) REFUSED", bool(ol) and ol[0].startswith("OUTSIDE_GRANT_RESULT refused 403"),
    ol[:1] or log[-300:])
oid = f"ds:{TENANT}:platform/inbox_item/pipeline-probe-{RUN}-step-fn"
s, d = req("GET", f"{KRN}/v1/registry/objects/{oid}/history", headers=H)
hist = (d.get("history") or []) if isinstance(d, dict) else []
res("the record is readable by the tenant (history has the committed version)", s == 200 and len(hist) >= 1, f"{s} {str(d)[:200]}")

print("✓ functional proof PASSED" if ok else "✗ functional proof FAILED")
sys.exit(0 if ok else 1)

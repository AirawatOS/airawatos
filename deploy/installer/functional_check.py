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
      tenant, and an UNDECLARED write (platform.schedule) is REFUSED. Both verdicts come from the ONE decision
      function (slice-1d), whose decision ids are printed for the host to check the durable decision records.
  C · CORE-RESERVED KINDS (FOUNDATIONS FND-19): the `engine/reserved-kind-probe` fixture DECLARES a
      governance.role_assignment write and is installed, so the steward's grant COVERS it — the kernel must still REFUSE
      the write (no grant or declaration lets a component write a core-reserved kind), and nothing is stored.

Prints `MATRIX_RESULTS <json>` (cases tagged with the rules they prove) and `DECISION_IDS <allow> <deny>`.

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
CASES = []; _RULES = []


def res(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    CASES.append({"case": name, "rules": list(_RULES), "result": "PASS" if cond else "FAIL"})
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
_RULES[:] = ["ACC-4"]          # login + first-login rotation through the App Host (not PLT-11: tenant.admin floor is not exercised)
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
# slice-1f (DEBT-B47): an admin hold refuses the login; lifting it restores access (App Host's own identity, fail-closed)
s, d = req("POST", f"{EDGE}/bridge/user-disable", {"username": un, "disabled": True, "reason": "functional check"}, opener=adm)
res(f"admin puts {un} on hold (/bridge/user-disable)", s == 200 and d.get("disabled") is True, f"{s} {d}")
s, d = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": un, "password": new})
res(f"{un} is REFUSED at the App Host while on hold", s in (401, 403) and "disabled" in json.dumps(d), f"{s} {d}")
s, d = req("POST", f"{EDGE}/bridge/user-disable", {"username": un, "disabled": False}, opener=adm)
s2, _ = req("POST", f"{EDGE}/login", {"realm": TENANT, "username": un, "password": new})
res(f"lifting the hold restores {un}'s login", s == 200 and s2 == 200, f"{s}/{s2}")

# ── B · an installed component writes a record within its grant ────────────────────────────────────────────
print(f"▶ B · installed component writes within its grant ({CID} in {TENANT})")
_RULES[:] = ["CMP-3", "CMP-6", "FND-3"]
s, d = req("POST", f"{IDN}/realms/{TENANT}/login", {"username": "admin", "password": APW})
atok = (d or {}).get("access_token") if s == 200 else None
res(f"tenant admin token for {TENANT}", bool(atok), s)
H = {"Authorization": "Bearer " + (atok or "")}
# slice-1f: the Network's lookups are internal-only. slice-1g (DEBT-B86): each door admits only its DECLARED callers
# (ARCHITECTURE-FLOWS §c table) — tenants/directory/grants resolve are the KERNEL's lookups, so the proof calls them as
# the kernel principal (svc:network), exactly as the kernel broker does.
s, d = req("POST", f"{IDN}/login", {"username": "kernel", "tenant": OPERATOR, "aud": "svc:network",
                                   "password": vpw(f"secret/data/{OPERATOR}/kernel/password")})
NH = {"Authorization": "Bearer " + ((d or {}).get("access_token") or "")} if s == 200 else {}
res("a declared caller (kernel) mints svc:network for the internal lookups", bool(NH), s)
s, _ = req("POST", f"{NET}/v1/tenants/resolve", {"tenant_id": TENANT})
res("the Network's internal lookup refuses an anonymous caller (slice-1f)", s == 401, s)
s, d = req("POST", f"{NET}/v1/tenants/resolve", {"tenant_id": TENANT}, headers=NH)
spid = (d or {}).get("steward_participant")
res(f"tenant record names the registered steward ds:{TENANT}:steward (DEBT-B62)", spid == f"ds:{TENANT}:steward", f"{s} {spid}")
s, d = req("POST", f"{NET}/v1/directory/resolve", {"participant_id": spid or ""}, headers=NH)
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

import re as _re
_m = _re.search(r"decision (dec-[0-9a-f]+)", ol[0] if ol else "")
DENY_ID = _m.group(1) if _m else None

# ── C · core-reserved record kinds (FND-19) ─────────────────────────────────────────────────────────────────
CID2 = f"ds:{INSTANCE}-developer:engine/reserved-kind-probe"
print(f"▶ C · a component GRANTED a core-reserved write is still refused ({CID2})")
_RULES[:] = ["FND-19"]
s, d = req("POST", f"{KRN}/v1/components/install", {"component_id": CID2}, headers=H, timeout=60)
res("tenant admin installs the reserved-kind probe (declares governance.role_assignment)", s == 200, f"{s} {str(d)[:200]}")
s, d = req("POST", f"{NET}/v1/grants/resolve", {"tenant": TENANT, "component_id": CID2}, headers=NH)
gr = [g for g in ((d or {}).get("grants") or []) if "governance.role_assignment" in (g.get("writes") or [])] if isinstance(d, dict) else []
res("the tenant steward's grant COVERS the declared governance.role_assignment write", bool(gr), f"{s} {str(d)[:240]}")
s, out2 = req("POST", f"{SCH}/run", {"component": CID2, "tenant": TENANT, "reason": "install-functional-check",
                                      "env": {"PROBE_RUN": RUN}}, headers={"Authorization": "Bearer " + stok}, timeout=600)
log2 = (out2.get("log") or "") if isinstance(out2, dict) else ""
rl = [l for l in log2.splitlines() if l.startswith("RESERVED_RESULT")]
res("the kernel REFUSES the granted governance.role_assignment write (core-reserved, FND-19)",
    bool(rl) and rl[0].startswith("RESERVED_RESULT refused 403") and "core-reserved" in rl[0], rl[:1] or log2[-300:])
s, d = req("GET", f"{KRN}/v1/registry/objects/ds:{TENANT}:governance/role_assignment/reserved-probe-{RUN}/history", headers=H)
hist2 = (d.get("history") or []) if isinstance(d, dict) else []
res("nothing was stored under the reserved kind", not hist2, f"{s} {str(d)[:160]}")

print("MATRIX_RESULTS " + json.dumps({"env": "local-dev", "mode": "functional",
      "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "", "cases": CASES}))
print(f"DECISION_IDS {RUN} {DENY_ID or '-'}")
print("✓ functional proof PASSED" if ok else "✗ functional proof FAILED")
sys.exit(0 if ok else 1)

#!/usr/bin/env bash
# AirawatOS local-dev bootstrap (from-source stack). Run AFTER `docker compose -f docker-compose.dev.yml up -d`.
# Explicit, ordered, idempotent. Mirrors what PRODUCTION does (mostly implicitly on boot) — annotated per step.
#
#   cd deploy/local-dev && ./bootstrap-dev.sh
#
# Phases:
#   1  base-OS install (operator-first): 4 realms + admins + base vocab + base apps        [prod: airawatos-install.sh]
#   2  Trust-plane schemas governed (seed_trust_schemas.py; dry-run → apply → dry-run)      [prod: implicit; same tool]
#   3  local canonical Network — GENERATED ULID id + slug 'localdev' (never slug-derived)   [§4]
#   4  record the steward as network.admin on the local Network (governance.role_assignment)  [§3]
#      This records EXACTLY network.admin on the Network — it is NOT platform authority and not a proxy for it.
#      platform.authority is not yet representable (governance.role_assignment@0.1.0 has no platform scope/role);
#      see PLAN.md "platform.authority is not yet representable" (next slice, design required).
set -euo pipefail
cd "$(dirname "$0")"
P=airawatos-localdev
F=docker-compose.dev.yml
INSTANCE="${INSTANCE:-localdev}"
OPERATOR_PASSWORD="${OPERATOR_PASSWORD:-}"                      # #282: NO committed literal. Empty ⇒ ensure_install
                                                               # GENERATES the admin password into Vault (reused
                                                               # idempotently); bootstrap reads it back after Phase 1.
SELF_MEMBERSHIP="${SELF_MEMBERSHIP:-0}"                         # §4: platform-tenant self-membership is OPT-IN
COMPOSE() { docker compose -p "$P" --project-directory . -f "$F" "$@"; }
XNET()  { COMPOSE exec -T network "$@"; }
XAPP()  { COMPOSE exec -T app-host "$@"; }

echo "▶ preflight: network + kernel health"
curl -fsS http://127.0.0.1:8080/network/v1/health >/dev/null || { echo "✗ network not up"; exit 1; }
curl -fsS http://127.0.0.1:8080/kernel/v1/health  >/dev/null || { echo "✗ kernel not up";  exit 1; }

echo "── Phase 1 · base-OS install (instance=$INSTANCE) ─────────────────────────────────────────────"
XNET env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" python3 /app/ensure_install.py
# #282 — ensure_install generated the admin password into Vault (no committed literal). Read it back so the
# remaining phases (seed_base_os, the network-admin login, the kernel steward bootstrap) can authenticate.
if [ -z "$OPERATOR_PASSWORD" ]; then
  OPERATOR_PASSWORD="$(XNET env INSTANCE="$INSTANCE" python3 - <<'PY'
import os, json, urllib.request
inst=os.environ["INSTANCE"]; VA=(os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/")
VT=os.environ.get("VAULT_TOKEN","")
r=urllib.request.Request(f"{VA}/v1/secret/data/{inst}-operator/admin/password", headers={"X-Vault-Token":VT})
print(((json.load(urllib.request.urlopen(r,timeout=8)).get("data") or {}).get("data") or {}).get("password",""), end="")
PY
)"
  [ -n "$OPERATOR_PASSWORD" ] && echo "  · admin password read from Vault (generated at install; not printed)" \
                             || { echo "✗ could not read generated admin password from Vault"; exit 1; }
fi
echo "  · govern base domains/roles/schemas"
XNET python3 /app/seed_base.py
echo "  · stage base-app source into app-host + deliver + list + shelf"
BASE_APPS="admin settings file-explorer console inbox personal-assistant storefront network-admin data"
XAPP sh -lc 'mkdir -p /app/_seed'
for a in $BASE_APPS; do COMPOSE cp ../../components/apps/$a app-host:/app/_seed/$a >/dev/null 2>&1 || echo "    (skip $a — not in components)"; done
XAPP env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" MODE=deliver python3 /app/reference/seed_base_os.py
XNET env INSTANCE="$INSTANCE" python3 /app/mint_base_listings.py
COMPOSE restart app-host >/dev/null
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:8080/ >/dev/null 2>&1 && break; sleep 2; done
XAPP env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" MODE=shelf python3 /app/reference/seed_base_os.py

echo "── Phase 2 · Trust-plane schemas (dry-run → apply → dry-run; prod's own tool + behaviour) ──────"
XNET env NET_FILES_DIR=/data/netfiles python3 -m trust.migration.seed_trust_schemas --dry-run
XNET env NET_FILES_DIR=/data/netfiles python3 -m trust.migration.seed_trust_schemas
echo "  · idempotency re-run (expect 0 to govern):"
XNET env NET_FILES_DIR=/data/netfiles python3 -m trust.migration.seed_trust_schemas --dry-run

echo "── Phases 3+4 · local Network (ULID, slug localdev) + authority role_assignment ──────────────"
XNET env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" SELF_MEMBERSHIP="$SELF_MEMBERSHIP" python3 - <<'PY'
import os, time, secrets, json, urllib.request, urllib.error
inst = os.environ["INSTANCE"]; pw = os.environ["OPERATOR_PASSWORD"]
IDN = "http://identity:8093"; KRN = "http://kernel:8080"
def _post(url, body, tok=None):
    h = {"Content-Type": "application/json"}
    if tok: h["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        return json.loads(urllib.request.urlopen(r, timeout=20).read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"__err__": e.code, "body": (e.read() or b"").decode()[:200]}
# login as the network-realm admin → HOME-issued token (iss=ds:localdev:identity)
lg = _post(f"{IDN}/realms/{inst}-network/login", {"username": "admin", "password": pw})
tok = lg.get("token") or lg.get("access_token")
if not tok:
    print("[bootstrap] LOGIN FAILED:", lg); raise SystemExit(1)
print(f"[bootstrap] network-admin token acquired (must_reset={lg.get('must_reset')})")
# ULID network id (Crockford base32, 48-bit time + 80-bit random) — NOT slug-derived
_C = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
def b32(n, L):
    s = ""
    for _ in range(L):
        n, r = divmod(n, 32); s = _C[r] + s
    return s
ulid = b32(int(time.time() * 1000), 10) + b32(secrets.randbits(80), 16)
nid = "net:" + ulid
net_oid = f"ds:{inst}-network:network/network/{ulid}"              # registry storage id (ds: steward path)
# IDEMPOTENCY: reuse an existing localdev network (ULID generated once, never a slug-derived id, never a dup)
q = _post(f"{KRN}/v1/registry/resolve", {"filter": {"schema": "network.network"},
                                         "id_prefix": [f"ds:{inst}-network:"]}, tok)
existing = next((o for r in (q.get("results") or []) for o in [r.get("object") or r]
                 if isinstance(o, dict) and o.get("slug") == "localdev"), None)
if existing:
    nid = existing.get("id")
    print(f"[phase3] localdev network already exists: {nid} (idempotent — reusing, no mint)")
else:
    net = {"schema": "network.network", "id": nid,                # object.id = the net:ULID (schema pattern ^net:)
           "slug": "localdev", "name": "Local Dev Network", "status": "active"}
    print(f"[phase3] minted {nid} (generated ULID, slug=localdev) stored at {net_oid}")
    print("   ->", _post(f"{KRN}/v1/registry/objects", {"id": net_oid, "object": net}, tok))
ra = {"schema": "governance.role_assignment",
      "id": f"ds:{inst}-network:governance/role_assignment/network-admin--admin",
      "principal": f"user://{inst}-network/admin", "network": nid, "role": "network.admin", "status": "active"}
# IDEMPOTENCY: make NO write when an identical live assignment already exists (no version bump, no audit entry)
cur = _post(f"{KRN}/v1/registry/resolve", {"id": ra["id"]}, tok)
live = next((r.get("object") or r for r in (cur.get("results") or [])), None)
same = isinstance(live, dict) and all(live.get(k) == ra[k] for k in ("principal", "network", "role", "status"))
if same:
    print(f"[phase4] network.admin role_assignment already current ({ra['id']}) — idempotent, no write")
else:
    print(f"[phase4] record network.admin on {nid} for {ra['principal']} (governance.role_assignment)")
    print("   ->", _post(f"{KRN}/v1/registry/objects", {"id": ra["id"], "object": ra}, tok))
# ADR-0122 P4 — seed platform.authority (platform scope) for the local steward, idempotently. With
# PLATFORM_AUTHORITY_MODE=enforce the network derives is_platform_authority from THIS recorded role (no
# tenant fallback); without the seed, no local principal would hold platform authority.
# ADR-0122 P4 — platform.authority is seeded in phase 7b through the GOVERNANCE path (GovernanceService.
# assign_role, first-holder-only rule), NEVER a direct registry write here. The previous phase4b direct-write
# granted admin UNCONDITIONALLY, so when platauth already held platform.authority it created a SECOND holder —
# bypassing ADR-0122's zero-holder-only bootstrap rule + the different-holder ChangeRequest. Deferred so the
# write goes through the same path+rule as assign_role, and only when there are zero live holders.
print("[phase4b] platform.authority seed deferred to phase 7b (governance path, first-holder-only)")

if os.environ.get("SELF_MEMBERSHIP") == "1":
    mem = {"schema": "network.membership", "id": f"ds:{inst}-network:network/membership/{ulid}--{inst}",
           "network": nid, "participant": f"user://{inst}/admin", "status": "approved"}
    print("[phase4] (flagged) self-membership ->", _post(f"{KRN}/v1/registry/objects", {"id": mem["id"], "object": mem}, tok))
else:
    print("[phase4] self-membership NOT created (set SELF_MEMBERSHIP=1 to opt in)")
PY

echo "── Phase 5 · trust-reader service principal (role-mode mint-on-demand reader) ──────────────────"
# Role mode (NETWORK_ADMIN_AUTHZ=role) mints its kernel-read token on demand for a DEDICATED read-only
# principal, password in Vault (never compose). Provision both here so role mode works with NO manual token.
# Idempotent: if the Vault password + identity user already exist, reuse them (no rotation, no write).
XNET env II="airawat-ld-identity-internal" TENANT="${INSTANCE}-network" USER="trust-reader" \
        VPATH="secret/data/${INSTANCE}-network/trust-reader/password" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
II=os.environ["II"]; TENANT=os.environ["TENANT"]; USER=os.environ["USER"]; VPATH=os.environ["VPATH"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
def vault_get():
    b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
    if isinstance(b, urllib.error.HTTPError): return None
    return (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("value")
existing = vault_get()
if existing:
    print(f"[phase5] trust-reader password already in Vault at {VPATH} — reusing (idempotent, no write)")
    pw = existing
else:
    pw = secrets.token_urlsafe(18)
    # KV v2 write
    w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"value":pw}},
           headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
    print(f"[phase5] stored trust-reader password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
          else f"[phase5] VAULT WRITE FAILED: {w.code} {(w.read() or b'').decode()[:120]}")
# ensure the identity user exists (role [] — NOT platform.service) + set its password (idempotent)
u=_req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[]},
       headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
print("[phase5] identity user ensured:", "OK" if not isinstance(u, urllib.error.HTTPError) else f"{u.code} (exists ok)")
s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False},
       headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
print("[phase5] trust-reader login password set:", "OK" if not isinstance(s, urllib.error.HTTPError) else f"{s.code}")
PY

echo "── Phase 6 · Trust-plane audit HMAC → Vault (ADR-0119 console/governance endpoints) ────────────"
# The Trust plane (networks/mine + governance reads the console bridge uses) needs an audit HMAC base
# secret. Held in VAULT (never compose); the network reads it at boot via TRUST_AUDIT_HMAC_VAULT_PATH.
# The Trust store's kernel-read token is mint-on-demand (reuses the Phase-5 trust-reader credential) —
# no TRUST_REGISTRY_TOKEN in compose. Idempotent: reuse an existing key, don't rotate.
XNET env VPATH="secret/data/${INSTANCE}-network/trust-plane/audit_hmac" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]; VPATH=os.environ["VPATH"]
def _req(url, data=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
b=_req(f"{VADDR}/v1/{VPATH}")
cur = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("value")
if cur:
    print(f"[phase6] trust-plane audit HMAC already in Vault at {VPATH} — reusing (idempotent)")
else:
    w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"value":secrets.token_hex(32)}}, method="POST")
    print(f"[phase6] stored trust-plane audit HMAC at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
          else f"[phase6] VAULT WRITE FAILED: {w.code}")
PY

echo "── Phase 7 · trust-writer service principal (Trust-plane governance WRITES) ─────────────────────"
# Governance writes (role assign, capability define, grant issue/revoke) persist via a DEDICATED write
# principal — own-tenant write to the Trust steward (ds:<inst>-network:), role [], NEVER platform.service;
# password in Vault, minted on demand. Separate from the read-only trust-reader. Idempotent (reuse).
XNET env II="airawat-ld-identity-internal" TENANT="${INSTANCE}-network" USER="trust-writer" \
        VPATH="secret/data/${INSTANCE}-network/trust-writer/password" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
II=os.environ["II"]; TENANT=os.environ["TENANT"]; USER=os.environ["USER"]; VPATH=os.environ["VPATH"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None), headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
def vault_get():
    b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
    return None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("value")
pw=vault_get()
if pw:
    print(f"[phase7] trust-writer password already in Vault at {VPATH} — reusing (idempotent)")
else:
    pw=secrets.token_urlsafe(18)
    w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"value":pw}}, headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
    print(f"[phase7] stored trust-writer password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError) else f"[phase7] VAULT WRITE FAILED: {w.code}")
u=_req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[]}, headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
print("[phase7] identity user ensured:", "OK" if not isinstance(u, urllib.error.HTTPError) else f"{u.code} (exists ok)")
s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False}, headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
print("[phase7] trust-writer login password set:", "OK" if not isinstance(s, urllib.error.HTTPError) else f"{s.code}")
PY

echo "── Phase 7b · platform.authority FIRST-HOLDER seed via the governance path (ADR-0122) ───────────"
# Seed platform.authority ONLY when there are ZERO live holders, through GovernanceService.assign_role (the
# first-holder-only rule) — NEVER a direct registry write, and NEVER a second grant when a holder already
# exists (that needs a different-holder ChangeRequest). Runs after the trust-writer + audit key (phases 6-7)
# so the governed store is available. Idempotent + safe to re-run.
XNET env INSTANCE="$INSTANCE" python3 - <<'PY'
import os, time
from trust_wiring import build_store_from_env
from trust import GovernanceService
from trust.governance import actor_context_from_claims
from trust.platform_authority import live_holders, PLATFORM_SCOPE
inst = os.environ.get("INSTANCE", "localdev")
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
store = build_store_from_env(); gov = GovernanceService(store)
holders = live_holders(store, "platform.authority", PLATFORM_SCOPE, now)
if holders:
    print(f"[phase7b] platform.authority already held by {sorted(holders)} — SKIP seed "
          f"(ADR-0122 first-holder-only bootstrap; a further grant requires a different-holder ChangeRequest)")
else:
    ctx = actor_context_from_claims({"sub": f"service://{inst}-network/trust-bootstrap",
                                     "roles": ["platform.steward"]})
    rec = gov.assign_role(ctx, {"role": "platform.authority",
                                "principal": f"user://{inst}-network/admin",
                                "scope": {"type": "platform", "ref": None}, "status": "active"}, now)
    print(f"[phase7b] seeded FIRST platform.authority holder (admin) via governance — id={rec.get('id')}")
PY

echo "── Phase 8 · network capability_catalog (Trust-plane governance needs it for grants) ────────────"
# define_capability/issue_grant require the network.network to carry a capability_catalog ref. The minimal
# Phase-3 network record has none; create an empty catalog + link it (own-tenant writes by the network admin).
XNET env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" python3 - <<'PY'
import os, json, urllib.request, urllib.error
inst=os.environ["INSTANCE"]; pw=os.environ["OPERATOR_PASSWORD"]; IDN="http://identity:8093"; KRN="http://kernel:8080"
lg=json.loads(urllib.request.urlopen(urllib.request.Request(f"{IDN}/realms/{inst}-network/login",
    data=json.dumps({"username":"admin","password":pw}).encode(),headers={"Content-Type":"application/json"},method="POST"),timeout=20).read())
tok=lg.get("token") or lg.get("access_token")
def post(path,body):
    rr=urllib.request.Request(KRN+path,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+tok},method="POST")
    try: return urllib.request.urlopen(rr,timeout=20).getcode()
    except urllib.error.HTTPError as e: return e.code
q=post  # alias
cur=json.loads(urllib.request.urlopen(urllib.request.Request(KRN+"/v1/registry/resolve",
    data=json.dumps({"filter":{"schema":"network.network"},"id_prefix":[f"ds:{inst}-network:"]}).encode(),
    headers={"Content-Type":"application/json","Authorization":"Bearer "+tok},method="POST"),timeout=20).read())
net=next((o for r in (cur.get("results") or []) for o in [r.get("object") or r] if isinstance(o,dict) and o.get("slug")=="localdev"), None)
if not net: print("[phase8] localdev network not found — skip"); raise SystemExit(0)
ulid=net["id"].split(":",1)[1]; net_oid=f"ds:{inst}-network:network/network/{ulid}"; cat_oid=f"ds:{inst}-network:network/capability_catalog/localdev"
if net.get("capability_catalog")==cat_oid:
    print("[phase8] capability_catalog already linked — idempotent"); raise SystemExit(0)
print("[phase8] create capability_catalog:", post("/v1/registry/objects",{"id":cat_oid,"object":{"schema":"network.capability_catalog","id":cat_oid,"network":net["id"],"capabilities":[]}}))
net["capability_catalog"]=cat_oid
print("[phase8] link into network.network:", post("/v1/registry/objects",{"id":net_oid,"object":net}))
PY

echo "── Phase 9 · ADR-0122 platform test users (platauth, platnone) ─────────────────────────────────"
# Two users in the platform/governance tenant (<inst>-network) for ADR-0122 conformance: `platauth` (will
# RECEIVE platform.authority — via a ChangeRequest approved by a different holder, NOT granted here) and
# `platnone` (same tenant, no recorded role). Passwords generated + stored in Vault; usernames printed,
# passwords NOT. Idempotent: reuse an existing Vault password, don't rotate.
XNET env II="airawat-ld-identity-internal" TENANT="${INSTANCE}-network" INST="${INSTANCE}" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
II=os.environ["II"]; TENANT=os.environ["TENANT"]; INST=os.environ["INST"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
for USER in ("platauth", "platnone"):
    # #282 — ONE Vault convention for every provisioned credential: path secret/data/<tenant>/<principal>/password,
    # field `password` (same shape ensure_install uses for the service principals). No bespoke test-users/value path.
    VPATH=f"secret/data/{INST}-network/{USER}/password"
    b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
    pw = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
    if pw:
        print(f"[phase9] {USER}: password already in Vault at {VPATH} — reusing (idempotent, no write)")
    else:
        pw = secrets.token_urlsafe(18)
        w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"password":pw}},
               headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
        print(f"[phase9] {USER}: stored password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
              else f"[phase9] {USER}: VAULT WRITE FAILED {w.code}")
    # ensure the identity user (role [] — NO recorded role; platform.authority comes later via CR) + set pw
    # only_if_unset (#282): never reset an existing login password on re-run.
    _req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[]},
         headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
    s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
           headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
    print(f"[phase9] created test user (username only): {USER}   tenant={TENANT}   recorded_role=(none)",
          "OK" if not isinstance(s, urllib.error.HTTPError) else f"set-pw {s.code}")
print("[phase9] ADR-0122 test users ready: platauth, platnone — passwords in Vault at "
      f"secret/data/{INST}-network/<name>/password (field `password`); platform.authority is granted to "
      "platauth SEPARATELY via a ChangeRequest approved by a different holder (ADR-0122 step 2b), never here.")
PY

echo "── Phase 10 · app-host scheduler-caller principal (ADR-0124 item 1) ─────────────────────────────"
# app-host calls the scheduler's /run,/reload as a DEDICATED least-privilege principal: role [] (NO platform
# reach of its own — the run's authority rides the run-token/dev-token in the body), recorded audience
# svc:scheduler so it may mint a token the scheduler's ingress accepts. Password in Vault, minted on demand;
# NO passwordless login. Idempotent: reuse an existing Vault password, don't rotate.
XNET env II="airawat-ld-identity-internal" TENANT="${INSTANCE}-operator" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
II=os.environ["II"]; TENANT=os.environ["TENANT"]; USER="app-host"; AUDS=["svc:scheduler","svc:filestore"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
VPATH=f"secret/data/{TENANT}/{USER}/password"
b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
pw = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
if pw:
    print(f"[phase10] app-host: password already in Vault at {VPATH} — reusing (idempotent, no write)")
else:
    pw = secrets.token_urlsafe(18)
    w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"password":pw}},
           headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
    print(f"[phase10] app-host: stored password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
          else f"[phase10] app-host: VAULT WRITE FAILED {w.code}")
# role [] + the svc:scheduler audience allow-list (so /login honours an aud request for it, ADR-0124)
u=_req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[],"audiences":AUDS},
       headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
       headers={"X-Internal-Token":II,"Content-Type":"application/json"}, method="POST")
print(f"[phase10] app-host scheduler-caller ready: tenant={TENANT} roles=[] audiences={AUDS}",
      "OK" if not isinstance(s, urllib.error.HTTPError) else f"set-pw {s.code}")
PY

echo "✓ bootstrap-dev complete."

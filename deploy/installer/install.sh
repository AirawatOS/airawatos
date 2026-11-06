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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"                     # absolute, captured before any cd
cd "$SCRIPT_DIR"

# AirawatOS installer (docs/operator/INSTALLER.md). All CORE steps run in every profile; DEV-ONLY extras
# (platform test users, synthetic perf data) run only in dev (test users also in rehearsal, for the
# credentialed conformance cases). Idempotent — safe to re-run. The surrounding stack/env (AIRAWAT_ENV,
# production guard, password-enforcement) is set by the compose per profile; this installer gates which STEPS
# run and refuses dev extras under production.
PROFILE="dev"
_args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    *) _args+=("$1"); shift ;;
  esac
done
case "$PROFILE" in
  production|rehearsal|dev) ;;
  *) echo "✗ unknown --profile '$PROFILE' (expected: production | rehearsal | dev)"; exit 2 ;;
esac
# which optional step-classes run in this profile (see INSTALLER.md)
case "$PROFILE" in
  dev)        RUN_TEST_USERS=1; RUN_PERF_SEED="${INSTALL_PERF_SEED:-0}" ;;   # perf seed opt-in (slow); dev only
  rehearsal)  RUN_TEST_USERS=1; RUN_PERF_SEED=0 ;;                           # conformance creds, no demo data
  production) RUN_TEST_USERS=0; RUN_PERF_SEED=0 ;;                           # CORE only; no demo data
esac
echo "▶ AirawatOS installer — profile=$PROFILE (test_users=$RUN_TEST_USERS perf_seed=$RUN_PERF_SEED)"

P=airawatos-localdev
# The compose project lives in deploy/local-dev/; this installer lives in deploy/installer/. Resolve the
# local-dev dir relative to this script so `docker compose` finds the project regardless of CWD.
LOCALDEV="$(cd "$SCRIPT_DIR/../local-dev" && pwd)"
F="$LOCALDEV/docker-compose.dev.yml"
INSTANCE="${INSTANCE:-localdev}"
OPERATOR_PASSWORD="${OPERATOR_PASSWORD:-}"                      # #282: NO committed literal. Empty ⇒ ensure_install
                                                               # GENERATES the admin password into Vault (reused
                                                               # idempotently); bootstrap reads it back after Phase 1.
SELF_MEMBERSHIP="${SELF_MEMBERSHIP:-0}"                         # §4: platform-tenant self-membership is OPT-IN
COMPOSE() { docker compose -p "$P" --project-directory "$LOCALDEV" -f "$F" "$@"; }
XNET()  { COMPOSE exec -T network "$@"; }
XAPP()  { COMPOSE exec -T app-host "$@"; }

# ── Host pre-flight (BEFORE any change) ──────────────────────────────────────────────────────────────
# Each check prints PASS/WARN/FAIL + a plain-language FIX. In production a FAIL stops the install; in dev it
# only WARNs (local dev boxes legitimately fail several). "where detectable" is honest: a check that cannot be
# determined on this host prints a NOTE to verify manually rather than a false pass. Read-only.
_PF_FAIL=0
_pf() {  # _pf <severity pass|warn|fail> <label> <fix>
  local sev="$1" label="$2" fix="${3:-}"
  case "$sev" in
    pass) echo "  ✓ $label" ;;
    note) echo "  • $label (verify manually: $fix)" ;;
    *)    if [ "$PROFILE" = production ]; then echo "  ✗ FAIL: $label"; echo "       FIX: $fix"; _PF_FAIL=1
          else echo "  ⚠ WARN: $label"; echo "       FIX: $fix"; fi ;;
  esac
}
echo "▶ pre-flight: host posture (profile=$PROFILE — production stops on FAIL, dev warns)"
# 1) resources
_cores=$( (command -v nproc >/dev/null && nproc) || sysctl -n hw.ncpu 2>/dev/null || echo 0 )
[ "${_cores:-0}" -ge 2 ] && _pf pass "CPU cores: $_cores (>=2)" || _pf fail "only ${_cores} CPU core(s)" "provision a host with >=2 vCPUs"
_diskavail=$(df -Pk . 2>/dev/null | awk 'NR==2{printf "%d", $4/1048576}')
[ "${_diskavail:-0}" -ge 10 ] && _pf pass "free disk: ${_diskavail} GB (>=10)" || _pf fail "only ${_diskavail:-?} GB free" "free or add disk (>=10 GB headroom)"
# 2) disk encryption (where detectable)
if command -v fdesetup >/dev/null 2>&1; then
  fdesetup status 2>/dev/null | grep -qi "On" && _pf pass "disk encryption: FileVault On" || _pf fail "FileVault appears Off" "enable FileVault (System Settings → Privacy & Security → FileVault)"
elif command -v lsblk >/dev/null 2>&1 && lsblk -o TYPE 2>/dev/null | grep -qi crypt; then
  _pf pass "disk encryption: LUKS volume present"
else
  _pf note "disk encryption not detectable on this host" "confirm the data volume is encrypted at rest (LUKS / cloud-provider volume encryption)"
fi
# 3) only 80/443 exposed publicly — flag any 0.0.0.0 published container port that is not 80/443
_bad_ports=$(docker ps --format '{{.Ports}}' 2>/dev/null | tr ',' '\n' | grep -oE '0\.0\.0\.0:[0-9]+' | sed 's/.*://' | sort -un | grep -vE '^(80|443)$' | tr '\n' ' ')
if [ -n "${_bad_ports// /}" ]; then _pf fail "public (0.0.0.0) ports other than 80/443: $_bad_ports" "bind these to 127.0.0.1 (local) or remove the port publish; expose only 80/443 at the host"
else _pf pass "no public ports other than 80/443 (local-dev binds 127.0.0.1)"; fi
# 4) Vault not in dev/root mode
_vstatus=$(COMPOSE exec -T vault sh -lc 'VAULT_ADDR=http://127.0.0.1:8200 vault status -format=json 2>/dev/null' 2>/dev/null || true)
_vstorage=$(printf '%s' "$_vstatus" | grep -oE '"storage_type":[^,}]*' | head -1)
if printf '%s' "$_vstorage" | grep -qi inmem; then _pf fail "Vault is in dev/in-memory mode (storage=inmem)" "run Vault with durable storage, unsealed, and NO root token in VAULT_TOKEN (use a scoped policy token)"
elif [ -n "$_vstatus" ]; then _pf pass "Vault storage is durable (not in-memory)"
else _pf note "Vault mode not detectable" "confirm Vault runs in production mode (durable storage, unsealed, non-root scoped token)"; fi
# 5) dedicated host (advisory — not reliably detectable)
_pf note "dedicated host" "confirm this host runs ONLY AirawatOS (no co-tenant workloads sharing the kernel/Docker engine)"
if [ "$_PF_FAIL" = 1 ]; then echo "✗ pre-flight FAILED (production) — fix the items above and re-run."; exit 1; fi

echo "▶ preflight: network + kernel health"
curl -fsS http://127.0.0.1:8080/network/v1/health >/dev/null || { echo "✗ network not up"; exit 1; }
curl -fsS http://127.0.0.1:8080/kernel/v1/health  >/dev/null || { echo "✗ kernel not up";  exit 1; }

echo "── Phase 0 · signing + audit keys in Vault (generate-or-verify BEFORE anything else) ───────────"
# The platform's trust roots live in Vault and must exist + be valid before any governed write: the identity
# issuer key (EdDSA, signs login tokens), the Network authority key (EdDSA, signs certificates/directory/tenant
# records), and the trust-plane audit HMAC (signs the governance audit log). Services create the transit keys
# lazily on first use; this step makes them EXPLICIT and FAILS CLEARLY if Vault is unreachable or a key is
# missing/invalid — so an install never silently proceeds on absent trust roots. Idempotent.
XNET env INSTANCE="$INSTANCE" python3 - <<'PY' || { echo "✗ STEP 0 failed — fix Vault/keys above, then re-run"; exit 1; }
import os, sys, json, secrets, urllib.request, urllib.error
VA=(os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT=os.environ.get("VAULT_TOKEN",""); INST=os.environ["INSTANCE"]
def v(method, path, body=None, ok_fail=False):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(f"{VA}/v1/{path}", data=data, method=method,
                             headers={"X-Vault-Token":VT, **({"Content-Type":"application/json"} if data else {})})
    try: return json.loads(urllib.request.urlopen(r, timeout=8).read() or b"{}")
    except urllib.error.HTTPError as e:
        if ok_fail: return None
        raise
def fail(msg, fix):
    print(f"  ✗ {msg}\n     FIX: {fix}", file=sys.stderr); sys.exit(1)
if not VT:
    fail("VAULT_TOKEN is not set — the installer cannot reach Vault.",
         "Set VAULT_TOKEN in the environment (compose .env in local-dev); never commit it.")
try:
    v("GET", "sys/health", ok_fail=False)
except Exception as e:
    fail(f"Vault not reachable at {VA} ({str(e)[:80]}).",
         "Start Vault and confirm VAULT_ADDR/VAULT_TOKEN; in production Vault must be unsealed and NOT in dev-root mode.")
v("POST", "sys/mounts/transit", {"type":"transit"}, ok_fail=True)   # idempotent enable
for key, label in (("airawat-identity","identity issuer"), ("airawat-authority","Network authority")):
    v("POST", f"transit/keys/{key}", {"type":"ed25519"}, ok_fail=True)   # create if missing (idempotent)
    r=v("GET", f"transit/keys/{key}", ok_fail=True)
    keys=((r or {}).get("data") or {}).get("keys") or {}
    pub=next((kv.get("public_key") for kv in keys.values() if isinstance(kv,dict) and kv.get("public_key")), None)
    if not pub:
        fail(f"{label} key transit/keys/{key} missing or has no public key.",
             f"Ensure the Vault transit engine is enabled and the installer can create keys (token policy), or pre-provision transit/keys/{key} (ed25519).")
    print(f"  ✓ {label} key: transit/keys/{key} (ed25519, public key present)")
AUD=f"secret/data/{INST}-network/trust-plane/audit_hmac"   # field `value`, same as installer Phase 6 + the network reader
r=v("GET", AUD, ok_fail=True)
hm=(((r or {}).get("data") or {}).get("data") or {}).get("value") if r else None
if not hm:
    v("POST", AUD, {"data":{"value":secrets.token_hex(32)}})
    print(f"  ✓ trust-plane audit HMAC: generated at {AUD}")
else:
    print(f"  ✓ trust-plane audit HMAC: present at {AUD}")
print("  Phase 0 OK — trust roots present + valid.")
PY

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

if [ "$RUN_TEST_USERS" = 1 ]; then
echo "── Phase 9 · ADR-0122 platform test users (platauth, platnone) · DEV-ONLY ──────────────────────"
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
else
  echo "── Phase 9 · platform test users SKIPPED (profile=$PROFILE — production carries no test fixtures) ──"
fi

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

echo "── Phase 11 · identity_lockout least-privilege DB role (ADR-0121 hardening) ─────────────────────"
# Dedicated Postgres login role for identity's brute-force lockout counters: access ONLY to
# identity_login_fails, NEVER the registry/audit tables (docs/security/IDENTITY-DB-LEAST-PRIVILEGE.md).
# Password in Vault (no compose literal), generated once + reused. Idempotent.
ILPW="$(XNET env INSTANCE="$INSTANCE" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
inst=os.environ["INSTANCE"]; VA=(os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT=os.environ.get("VAULT_TOKEN","")
P=f"secret/data/{inst}/identity-lockout/password"
def rd():
    try:
        d=json.load(urllib.request.urlopen(urllib.request.Request(VA+"/v1/"+P, headers={"X-Vault-Token":VT}), timeout=8))
        return ((d.get("data") or {}).get("data") or {}).get("password")
    except urllib.error.HTTPError:
        return None
pw=rd()
if not pw:
    pw="il_"+secrets.token_hex(24)
    urllib.request.urlopen(urllib.request.Request(VA+"/v1/"+P, data=json.dumps({"data":{"password":pw}}).encode(),
        headers={"X-Vault-Token":VT,"Content-Type":"application/json"}, method="POST"), timeout=8).read()
print(pw, end="")
PY
)"
[ -n "$ILPW" ] || { echo "✗ could not obtain identity_lockout password from Vault"; exit 1; }
COMPOSE exec -T postgres psql -U kernel -d kernel -v ON_ERROR_STOP=1 -v ilpw="$ILPW" <<'SQL'
SELECT 'CREATE ROLE identity_lockout LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='identity_lockout') \gexec
ALTER ROLE identity_lockout WITH LOGIN PASSWORD :'ilpw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE TABLE IF NOT EXISTS identity_login_fails (k TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL);
CREATE INDEX IF NOT EXISTS identity_login_fails_k_ts ON identity_login_fails (k, ts);
GRANT USAGE ON SCHEMA public TO identity_lockout;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM identity_lockout;
GRANT SELECT, INSERT, DELETE ON identity_login_fails TO identity_lockout;
SQL
echo "  · identity_lockout ready — grants: SELECT/INSERT/DELETE on identity_login_fails only (no registry/audit)"

echo "── Phase 11b · split-role least-privilege DB (4b: migrator + kernel_app + network_app) ───────────"
# 4b hardening — no service is a Postgres superuser:
#   migrator    owns every kernel-side table + runs ALL DDL (the ONLY role with CREATE on schema public)
#   kernel_app  DML only on registry_version / registry_schema_meta / kernel_admin_audit / kernel_kv (+ seqs)
#   network_app DML only on network_kv
# Each password is generated once into Vault (reused idempotently) and never written to compose; the kernel
# boots with REGISTRY_SKIP_DDL=1 + KV_SKIP_DDL=1 and the network with KV_SKIP_DDL=1 (see compose), so the
# migrator (via kernel/tools/db_migrate) is the sole DDL author. This phase is idempotent and reversible: it
# converges an existing install onto the split roles. On a legacy install it also copies the shared `kv`
# rows into kernel_kv / network_kv by owner (the step-1 split), leaving `kv` in place.
#
# NOTE (fresh install, DEFERRED to the volume-wipe test): on an empty DB the app-role services cannot boot
# until the tables exist, so the bring-up must run `docker compose up -d postgres vault`, then the migrator
# (`docker compose run --rm -e DB_USER=migrator -e DB_PASSWORD_VAULT_PATH=… kernel python -m tools.db_migrate`
# after this phase has created the roles), then `docker compose up -d`. This installer currently runs AGAINST
# an already-up stack (preflight health-checks kernel+network), so the converge path below is what it exercises.
XNET env INSTANCE="$INSTANCE" DB_HOST=postgres python3 - <<'PY' || { echo "✗ Phase 11b failed"; exit 1; }
import os, json, secrets, urllib.request, urllib.error
import psycopg2
inst = os.environ["INSTANCE"]
VA = (os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT = os.environ.get("VAULT_TOKEN", "")

def vault_pw(path, prefix):
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(VA + "/v1/" + path, headers={"X-Vault-Token": VT}), timeout=8))
        pw = ((d.get("data") or {}).get("data") or {}).get("password")
        if pw: return pw
    except urllib.error.HTTPError:
        pass
    pw = f"{prefix}_" + secrets.token_hex(24)
    urllib.request.urlopen(urllib.request.Request(VA + "/v1/" + path, data=json.dumps({"data": {"password": pw}}).encode(),
        headers={"X-Vault-Token": VT, "Content-Type": "application/json"}, method="POST"), timeout=8).read()
    return pw

roles = {"migrator": (f"secret/data/{inst}/migrator/password", "mg"),
         "kernel_app": (f"secret/data/{inst}/kernel-app/password", "ka"),
         "network_app": (f"secret/data/{inst}/network-app/password", "na")}
pw = {r: vault_pw(p, pre) for r, (p, pre) in roles.items()}

c = psycopg2.connect(host=os.environ.get("DB_HOST", "postgres"), port=5432, dbname="kernel", user="kernel", password="kernel")
c.autocommit = True; cur = c.cursor()
for r in roles:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (r,))
    if not cur.fetchone():
        cur.execute(f"CREATE ROLE {r} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
    cur.execute(f"ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s", (pw[r],))

# Tables must exist before ownership/grants. CREATE IF NOT EXISTS as superuser here is the install-time
# equivalent of the migrator entrypoint (kernel/tools/db_migrate); on an up stack the kernel already made the
# registry tables, so this only fills gaps (kernel_kv / network_kv on a legacy DB).
cur.execute("CREATE TABLE IF NOT EXISTS kernel_kv  (store TEXT, key TEXT, value JSONB, PRIMARY KEY(store,key))")
cur.execute("CREATE TABLE IF NOT EXISTS network_kv (store TEXT, key TEXT, value JSONB, PRIMARY KEY(store,key))")

# Legacy split copy (idempotent): if the shared `kv` still exists, copy each namespace to its owner's table.
cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='kv'")
if cur.fetchone():
    KERNEL_NS = ("tenant_datasets", "cases", "installed", "installed_schemas")
    cur.execute("INSERT INTO kernel_kv  SELECT * FROM kv WHERE store = ANY(%s) ON CONFLICT (store,key) DO NOTHING", (list(KERNEL_NS),))
    cur.execute("INSERT INTO network_kv SELECT * FROM kv WHERE NOT (store = ANY(%s)) ON CONFLICT (store,key) DO NOTHING", (list(KERNEL_NS),))

KERNEL_TABLES = ["registry_version", "registry_schema_meta", "kernel_admin_audit", "kernel_kv"]
SEQS = ["registry_version_seq_seq", "kernel_admin_audit_seq_seq"]
for t in KERNEL_TABLES + ["network_kv"]:
    cur.execute(f"ALTER TABLE {t} OWNER TO migrator")
for s in SEQS:
    cur.execute("SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name=%s", (s,))
    if cur.fetchone():
        cur.execute(f"ALTER SEQUENCE {s} OWNER TO migrator")
for r in roles:
    cur.execute(f"GRANT USAGE ON SCHEMA public TO {r}")
cur.execute("GRANT CREATE ON SCHEMA public TO migrator")   # migrator is the sole DDL author (PG15+ needs this)
for r in ("kernel_app", "network_app"):
    for t in KERNEL_TABLES + ["network_kv"]:
        cur.execute(f"REVOKE ALL ON {t} FROM {r}")
    for s in SEQS:
        cur.execute("SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name=%s", (s,))
        if cur.fetchone():
            cur.execute(f"REVOKE ALL ON SEQUENCE {s} FROM {r}")
for t in KERNEL_TABLES:
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO kernel_app")
for s in SEQS:
    cur.execute("SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name=%s", (s,))
    if cur.fetchone():
        cur.execute(f"GRANT USAGE, SELECT, UPDATE ON SEQUENCE {s} TO kernel_app")
cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON network_kv TO network_app")
cur.close(); c.close()
print("  · roles migrator/kernel_app/network_app ready — owner→migrator; kernel_app=own 4 tables; network_app=network_kv")
PY

if [ "$RUN_PERF_SEED" = 1 ]; then
  echo "── Phase 12 · synthetic perf dataset (~1M rows) · DEV-ONLY ─────────────────────────────────────"
  ( cd ../.. && python3 perf/seed.py --confirm-dev ) || echo "  · (perf seed skipped/failed — non-fatal)"
fi

echo "✓ install complete — profile=$PROFILE"

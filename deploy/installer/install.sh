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
  dev)        RUN_TEST_USERS=1; RUN_PERF_SEED="${INSTALL_PERF_SEED:-0}"; SEED_DATA_TENANT=1 ;;   # perf seed opt-in (slow); dev only
  rehearsal)  RUN_TEST_USERS=1; RUN_PERF_SEED=0; SEED_DATA_TENANT=0 ;;                           # conformance creds, no demo data
  production) RUN_TEST_USERS=0; RUN_PERF_SEED=0; SEED_DATA_TENANT=0 ;;                           # CORE only; no demo data
esac
# ADR-0131 production-minimum for relocated service principals: dev-sandbox (the app-host dev-token principal)
# exists ONLY under the dev profile; embed-service (citizen-embed OIDC) ONLY when embedding is enabled. scheduler
# + component-publisher are always created (both are production-needed). Default embedding ON in dev, OFF otherwise.
case "$PROFILE" in dev) EMBED_ENABLED="${EMBED_ENABLED:-1}" ;; *) EMBED_ENABLED="${EMBED_ENABLED:-0}" ;; esac
# PLATFORM P1 — the `<instance>` data tenant is NOT platform infrastructure: nothing at install time requires
# it (every later phase targets -operator / -network / -developer; its only install-time consumer is the
# base-app shelf default, cosmetic). It is a *first data tenant*, so it is created ONLY under the dev profile
# (SEED_DATA_TENANT=1). production/rehearsal stand up the platform without it; a working tenant is created via
# onboarding, not the installer.
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
# E2: the installer NEVER reads conformance/.creds.json or any test file. Every dev account password is
# generated into Vault (ensure_install for admin; Phase 9 for platauth/platnone; Phase 9b for outsider), the
# same convention as the service principals. conformance/.creds.json is GENERATED FROM Vault after install
# (Phase 13, dev-only), so the fixture is derived from the live secrets, never a committed input.
COMPOSE() { docker compose -p "$P" --project-directory "$LOCALDEV" -f "$F" "$@"; }
# L1-1b: installer-driven commands run with the ROOT token (install-time only); the long-running SERVICE
# process authenticates with its own AppRole scoped token (prod-guard). `-e VAULT_TOKEN` on exec/run overrides
# the container's approle env so the install step acts as root, and (for a one-off) prod-guard then skips its
# AppRole login. VAULT_TOKEN is the installer-shell root discovered from the vault volume (below).
XNET()  { COMPOSE exec -T -e VAULT_TOKEN="${VAULT_TOKEN:-}" network "$@"; }
XAPP()  { COMPOSE exec -T -e VAULT_TOKEN="${VAULT_TOKEN:-}" app-host "$@"; }
# One-off containers on a service image, WITHOUT pulling up its depends_on graph (used before the long-running
# services exist, so they cannot wait on a not-yet-healthy network/kernel).
XRUNNET()  { COMPOSE run --rm --no-deps -T -e VAULT_TOKEN="${VAULT_TOKEN:-}" network "$@"; }
XRUNKERN() { COMPOSE run --rm --no-deps -T -e VAULT_TOKEN="${VAULT_TOKEN:-}" kernel "$@"; }
# ADR-0131 / slice-1c-iv-c — identity's provisioning door accepts ONLY an svc:identity token from an allow-listed
# operator-realm caller. The installer acts as the `provisioner` principal (self-seeded by identity from the Vault
# install config): read its password from Vault (root, install-time) and mint a FRESH short-lived svc:identity
# token for each identity-writing phase. No shared literal; empty output => that phase's writes are refused (403).
_idt() {
  XNET env INST="$INSTANCE" python3 - <<'PYIDT'
import os, json, urllib.request
VA=(os.environ.get("VAULT_ADDR") or "http://vault:8200").rstrip("/"); VT=os.environ.get("VAULT_TOKEN","")
op=f"{os.environ['INST']}-operator"
try:
    r=urllib.request.Request(f"{VA}/v1/secret/data/{op}/provisioner/password", headers={"X-Vault-Token":VT})
    pw=((json.load(urllib.request.urlopen(r,timeout=8)).get("data") or {}).get("data") or {}).get("password","")
    lg=urllib.request.Request("http://identity:8093/login", data=json.dumps({"username":"provisioner","tenant":op,
        "password":pw,"aud":"svc:identity"}).encode(), headers={"Content-Type":"application/json"})
    print(json.load(urllib.request.urlopen(lg,timeout=10)).get("access_token",""), end="")
except Exception:
    print("", end="")
PYIDT
}

# L1-1b — provision per-service Vault AppRoles (closes DEBT-B58). Uses ROOT (install-time) via the vault
# container CLI. Enables approle, writes the least-privilege policies (stdin, no bind-mount), creates one role
# per service, and writes each service's role-id+secret-id to its own bind-mounted env_file (per-service, so no
# service can read another's secret-id). Idempotent. Must run BEFORE the keys/roles one-offs (their env_files
# must exist) and before the all-services bring-up.
VROOT() { COMPOSE exec -T -e VAULT_TOKEN="$VAULT_TOKEN" vault sh -lc "$1"; }
_setup_vault_approle() {
  echo "▶ bring-up: per-service Vault AppRoles + least-privilege policies (L1-1b)"
  VROOT 'vault auth list -format=json 2>/dev/null | grep -q "approle/" || vault auth enable approle' >/dev/null 2>&1 || true
  mkdir -p "$LOCALDEV/vault/approle"
  # policy name : service(s) that use it : role name(s)
  # (automation/event-relay/scheduler share the svc-scheduler policy but each gets its OWN role → own creds)
  for pol in svc-kernel svc-network svc-identity svc-secrets svc-model-gateway svc-scheduler svc-app-host svc-decision svc-workflow svc-runtime-manager; do
    VROOT "VAULT_TOKEN=$VAULT_TOKEN vault policy write $pol -" < "$LOCALDEV/vault/policies/$pol.hcl" >/dev/null \
      || { echo "✗ vault policy write $pol failed"; exit 1; }
  done
  # role name : policy
  for pair in kernel:svc-kernel network:svc-network identity:svc-identity secrets:svc-secrets \
              model-gateway:svc-model-gateway app-host:svc-app-host \
              automation:svc-scheduler event-relay:svc-scheduler scheduler:svc-scheduler \
              decision:svc-decision workflow:svc-workflow runtime-manager:svc-runtime-manager; do
    role="${pair%%:*}"; pol="${pair##*:}"
    VROOT "vault write auth/approle/role/$role token_policies=$pol token_ttl=24h token_max_ttl=168h token_num_uses=0 secret_id_num_uses=0 secret_id_ttl=0" >/dev/null \
      || { echo "✗ vault approle role $role failed"; exit 1; }
    rid="$(VROOT "vault read -field=role_id auth/approle/role/$role/role-id" | tr -d '\r\n')"
    sid="$(VROOT "vault write -f -field=secret_id auth/approle/role/$role/secret-id" | tr -d '\r\n')"
    [ -n "$rid" ] && [ -n "$sid" ] || { echo "✗ vault approle creds for $role empty"; exit 1; }
    printf 'VAULT_ROLE_ID=%s\nVAULT_SECRET_ID=%s\n' "$rid" "$sid" > "$LOCALDEV/vault/approle/$role.env"
  done
  echo "  ✓ 12 AppRoles provisioned; per-service env_files written (secret-ids not printed)"
}

# ARC-5 (slice-1a): the Kernel door is internal-only — the edge no longer proxies /kernel/. Readiness is checked
# INSIDE the kernel container, not via the edge. (Network health stays at the edge /network/ — federation door.)
KHEALTH() { COMPOSE exec -T kernel python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/v1/health',timeout=3).status==200 else 1)" >/dev/null 2>&1; }

# FIX-PLAN L1 slice-1a step 4 — verify the per-boundary ARC networks exist and the critical walls hold. Compose
# CREATES the networks on `up`; this VERIFIES them and FAILS the install on any off-map membership (an open wall
# would silently reintroduce the flat-net exposure). Deterministic: docker membership ⇒ reachability.
_net_members() { docker network inspect "$1" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null; }
_verify_arc_networks() {
  echo "▶ verify: ARC per-boundary networks (edge/svc/data-facts/data-secrets/component)"
  local ok=1 n
  for n in aos-edge aos-svc aos-data-facts aos-data-secrets aos-component; do
    docker network inspect "$n" >/dev/null 2>&1 && echo "  ✓ network $n exists" || { echo "  ✗ network $n MISSING"; ok=0; }
  done
  # Wall 1 (ARC-5): the edge carries only nginx + app-host + network — never a data store or internal service.
  for bad in airawat-ld-postgres airawat-ld-vault airawat-ld-kernel airawat-ld-secrets; do
    _net_members aos-edge | grep -qw "$bad" && { echo "  ✗ WALL: $bad is on aos-edge (edge must be isolated)"; ok=0; }
  done
  # Wall 2 (ARC-3): the fact store net carries ONLY postgres + the 3 DB-role holders (kernel/network/identity).
  for m in $(_net_members aos-data-facts); do
    case "$m" in airawat-ld-postgres|airawat-ld-kernel|airawat-ld-network|airawat-ld-identity) ;;
      *) echo "  ✗ WALL: unexpected member $m on aos-data-facts (facts = kernel/network/identity only)"; ok=0;; esac
  done
  # Wall 3 (ARC-7): the fact store is NOT on the secrets net, and nginx reaches neither data store.
  _net_members aos-data-secrets | grep -qw airawat-ld-postgres && { echo "  ✗ WALL: postgres on aos-data-secrets"; ok=0; }
  # Wall 4 (ARC-1/B52): the component net carries ONLY the broker (kernel) + transient placed components.
  for m in $(_net_members aos-component); do
    case "$m" in airawat-ld-kernel) ;; *) echo "  ✗ WALL: unexpected member $m on aos-component (broker-only)"; ok=0;; esac
  done
  if [ "$ok" = 1 ]; then echo "  ✓ ARC network walls verified"; else echo "✗ ARC network verification FAILED — walls above are open"; exit 1; fi
}

# ── Fresh-install bring-up (idempotent): infra → keys → roles → migrator → services ──────────────────
# 4b: the app-role services (kernel_app/network_app boot with REGISTRY_SKIP_DDL/KV_SKIP_DDL and are NON-owners)
# cannot start until their tables + roles exist, so a from-empty install MUST order the bring-up. On an
# already-up stack every step is a no-op/converge, so this prelude is safe to re-run.
echo "▶ bring-up: postgres + vault"
COMPOSE up -d postgres vault >/dev/null 2>&1 || COMPOSE up -d postgres vault
for i in $(seq 1 45); do
  COMPOSE exec -T postgres pg_isready -U kernel >/dev/null 2>&1 \
    && COMPOSE exec -T vault sh -lc 'VAULT_ADDR=http://127.0.0.1:8200 vault status >/dev/null 2>&1' && break
  sleep 2
done
# L1-1b: the root token is read from the vault volume (/vault/data/init.json) into the INSTALLER SHELL ONLY and
# used for install-time provisioning (keys, roles, approle). It is NO LONGER written to .env or injected into any
# long-running service — services authenticate with their own AppRole scoped token (DEBT-B58 closed). Any stale
# VAULT_TOKEN line left in .env from an earlier build is REMOVED so the shared root cannot ride a service.
VT_DISC="$(COMPOSE exec -T vault sh -lc "tr -d '\n ' < /vault/data/init.json 2>/dev/null | sed 's/.*\"root_token\":\"\\([^\"]*\\)\".*/\\1/'" 2>/dev/null | tr -d '\r')"
if [ -n "$VT_DISC" ]; then
  export VAULT_TOKEN="$VT_DISC"
  if [ -f "$LOCALDEV/.env" ] && grep -q '^VAULT_TOKEN=' "$LOCALDEV/.env"; then
    grep -v '^VAULT_TOKEN=' "$LOCALDEV/.env" > "$LOCALDEV/.env.tmp" && mv "$LOCALDEV/.env.tmp" "$LOCALDEV/.env"
    echo "  · removed the shared VAULT_TOKEN from .env (root is install-time only now)"
  fi
  echo "  · root token read from the vault volume for install-time provisioning (not printed)"
else
  echo "✗ could not read the vault root token from /vault/data/init.json — cannot provision AppRoles"; exit 1
fi
_setup_vault_approle
# ── 1c-iv-a (ADR-0131) · operator install config in Vault, BEFORE identity boots ──────────────────────
# The root of trust at install: write the operator admin's initial password + the provisioner principal's
# password to Vault NOW (postgres+vault are up; all other services are still down), so when identity starts it
# can self-seed the admin + provisioner from this config (slice-1c-iv-b). CREATE-ONLY: never overwrite an
# existing password (idempotent re-install; matches ensure_install's reuse of the admin password). The admin
# path is the SAME one ensure_install reads back, so the human-admin password is unchanged.
echo "▶ bring-up: operator install config (admin + provisioner passwords) → Vault (ADR-0131)"
# admin: an operator MAY pass OPERATOR_PASSWORD (interactive install); else a strong password is generated.
# CREATE-ONLY either way — a re-install never overwrites an existing credential.
# ADR-0131 constraint 4 — after a CONFIRMED bootstrap the installer scrubs the admin bootstrap password and leaves a
# marker (secret/<op>/install-state). A re-install over that state must NOT mint a fresh (unusable) bootstrap
# password: the admin already exists in identity (the create-only seed ignores config changes). The operator passes
# the CURRENT admin password as OPERATOR_PASSWORD; it is used in-shell only and never written back to Vault.
ADMIN_SCRUBBED=0
if ! VROOT "vault kv get -mount=secret ${INSTANCE}-operator/admin/password >/dev/null 2>&1" \
   && VROOT "vault kv get -mount=secret ${INSTANCE}-operator/install-state >/dev/null 2>&1"; then
  ADMIN_SCRUBBED=1
  if [ -z "$OPERATOR_PASSWORD" ]; then
    echo "✗ the admin bootstrap password was scrubbed after the first install (ADR-0131); re-run with"
    echo "  OPERATOR_PASSWORD=<the current admin@${INSTANCE}-operator / realm-admin password>"; exit 1
  fi
  echo "  · admin: bootstrap password already scrubbed (re-install) — using operator-supplied password in-shell only"
elif [ -n "$OPERATOR_PASSWORD" ]; then
  VROOT "vault kv get -mount=secret ${INSTANCE}-operator/admin/password >/dev/null 2>&1 \
    || vault kv put -mount=secret ${INSTANCE}-operator/admin/password password='$OPERATOR_PASSWORD' >/dev/null" \
    && echo "  · admin: operator-supplied password stored (create-only)" \
    || { echo "✗ could not write admin install-config password to Vault"; exit 1; }
else
  VROOT "vault kv get -mount=secret ${INSTANCE}-operator/admin/password >/dev/null 2>&1 \
    || vault kv put -mount=secret ${INSTANCE}-operator/admin/password password=\"\$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)\" >/dev/null" \
    && echo "  · admin: password present at secret/${INSTANCE}-operator/admin/password (create-only, generated)" \
    || { echo "✗ could not write admin install-config password to Vault"; exit 1; }
fi
VROOT "vault kv get -mount=secret ${INSTANCE}-operator/provisioner/password >/dev/null 2>&1 \
  || vault kv put -mount=secret ${INSTANCE}-operator/provisioner/password password=\"\$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)\" >/dev/null" \
  && echo "  · provisioner: password present at secret/${INSTANCE}-operator/provisioner/password (create-only)" \
  || { echo "✗ could not write provisioner install-config password to Vault"; exit 1; }
echo "▶ bring-up: signing + audit keys (Vault)"
XRUNNET env INSTANCE="$INSTANCE" python3 - < "$SCRIPT_DIR/_keys.py" || { echo "✗ bring-up keys failed"; exit 1; }
echo "▶ bring-up: split roles (create migrator/kernel_app/network_app; grant CREATE to migrator)"
XRUNNET env INSTANCE="$INSTANCE" DB_HOST=postgres python3 - < "$SCRIPT_DIR/_split_roles.py" || { echo "✗ bring-up roles failed"; exit 1; }
echo "▶ bring-up: migrator DDL (create all tables owned by migrator)"
XRUNKERN env DB_USER=migrator DB_PASSWORD_VAULT_PATH="secret/data/$INSTANCE/migrator/password" \
  python -m tools.db_migrate || { echo "✗ bring-up migrator failed"; exit 1; }
echo "▶ bring-up: table ownership + least-privilege DML grants"
XRUNNET env INSTANCE="$INSTANCE" DB_HOST=postgres python3 - < "$SCRIPT_DIR/_split_roles.py" || { echo "✗ bring-up grants failed"; exit 1; }
echo "▶ bring-up: all services"
COMPOSE up -d >/dev/null 2>&1 || COMPOSE up -d
for i in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8080/network/v1/health >/dev/null 2>&1 && KHEALTH && break
  sleep 2
done
_verify_arc_networks   # FIX-PLAN L1 slice-1a step4 — all services up ⇒ all 5 ARC networks exist; verify the walls
# step5 — comprehensive ARC flow-map test (membership + forbidden-reachability probes); fails on any off-map path.
_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ -f "$_REPO_ROOT/conformance/flow_map_test.py" ]; then
  AOS_LD_PROJECT="$P" python3 "$_REPO_ROOT/conformance/flow_map_test.py" || { echo "✗ ARC flow-map test FAILED — off-map path"; exit 1; }
fi
# L1-1b step5 — per-service Vault least-privilege (own paths readable, foreign refused, root absent).
if [ -f "$_REPO_ROOT/conformance/vault_scope_test.py" ]; then
  AOS_LD_PROJECT="$P" python3 "$_REPO_ROOT/conformance/vault_scope_test.py" || { echo "✗ Vault least-privilege test FAILED"; exit 1; }
fi

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
KHEALTH || { echo "✗ kernel not up";  exit 1; }

echo "── Phase 0 · signing + audit keys in Vault (generate-or-verify BEFORE anything else) ───────────"
# The platform's trust roots live in Vault and must exist + be valid before any governed write: the identity
# issuer key (EdDSA, signs login tokens), the Network authority key (EdDSA, signs certificates/directory/tenant
# records), and the trust-plane audit HMAC (signs the governance audit log). Services create the transit keys
# lazily on first use; this step makes them EXPLICIT and FAILS CLEARLY if Vault is unreachable or a key is
# missing/invalid — so an install never silently proceeds on absent trust roots. Idempotent.
XNET env INSTANCE="$INSTANCE" python3 - < "$SCRIPT_DIR/_keys.py" || { echo "✗ STEP 0 failed — fix Vault/keys above, then re-run"; exit 1; }

echo "── Phase 1 · base-OS install (instance=$INSTANCE) ─────────────────────────────────────────────"
XNET env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" SEED_DATA_TENANT="$SEED_DATA_TENANT" python3 /app/ensure_install.py
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
echo "── Phase 1a · confirm identity self-bootstrap (ADR-0131) — provisioner mint + admin login ───────"
# The door is svc:identity-only from day one, so nothing below works unless identity seeded the provisioner (and
# the admin) from the install config. Confirm BOTH before any identity write; the admin confirmation also gates
# the end-of-install scrub of the bootstrap password (constraint 4).
for i in $(seq 1 30); do XNET python3 -c "import urllib.request;urllib.request.urlopen('http://identity:8093/healthz',timeout=3)" >/dev/null 2>&1 && break; sleep 2; done
IDT="$(_idt)"
[ -n "$IDT" ] && echo "  ✓ provisioner@${INSTANCE}-operator minted an svc:identity token (self-bootstrap confirmed)" \
  || { echo "✗ provisioner could not mint svc:identity — identity did not self-bootstrap from Vault (see identity logs)"; exit 1; }
ADMIN_BOOTSTRAP_CONFIRMED=0
_adm="$(XNET env INST="$INSTANCE" PW="$OPERATOR_PASSWORD" python3 - <<'PYADM'
import os, json, urllib.request, urllib.error
op=f"{os.environ['INST']}-operator"
r=urllib.request.Request(f"http://identity:8093/realms/{op}/login", data=json.dumps({"username":"admin","password":os.environ["PW"]}).encode(),
                         headers={"Content-Type":"application/json"})
try:
    d=json.load(urllib.request.urlopen(r,timeout=10)); print("OK", "must_reset" if d.get("must_reset") else "rotated", end="")
except urllib.error.HTTPError as e:
    print("FAIL", e.code, end="")
PYADM
)"
case "$_adm" in
  OK*) ADMIN_BOOTSTRAP_CONFIRMED=1; echo "  ✓ admin@${INSTANCE}-operator logs in (${_adm#OK })" ;;
  *)   echo "✗ admin@${INSTANCE}-operator login failed ($_adm) — bootstrap not confirmed"; exit 1 ;;
esac

echo "  · govern base domains/roles/schemas"
XNET python3 /app/seed_base.py

echo "── Phase 1b-svc · role-bearing service principals (scheduler/component-publisher/dev-sandbox/embed-service) — ADR-0131 ──"
# ADR-0131 — these moved OUT of ensure_install (which now only signs tenant records). Each is a dedicated SERVICE
# principal with a random Vault-backed password (never compose/human) at the SAME path its consumer reads via
# svc_token.py. Production minimum: scheduler + component-publisher always; dev-sandbox dev-only; embed-service
# only when embedding is enabled. Written through the svc:identity door as the provisioner (1c-iv-c).
# MUST run before base-app delivery so app-host's publish/dev-token creds exist.
XNET env IDT="$(_idt)" INST="${INSTANCE}" PROFILE="$PROFILE" EMBED_ENABLED="$EMBED_ENABLED" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; INST=os.environ["INST"]; PROFILE=os.environ["PROFILE"]; EMBED=os.environ.get("EMBED_ENABLED")=="1"
operator, network, developer = f"{INST}-operator", f"{INST}-network", f"{INST}-developer"
# (user, tenant, roles, audiences, include?)
PRINCIPALS = [
    ("scheduler",           operator,  ["platform.scheduler"], ["svc:automation", "svc:runtime-manager"], True),  # daemons → automation; scheduler → runtime-manager /v1/invoke (step 2)
    ("component-publisher", network,   ["component.publisher"], None,              True),             # app-host publish/sign
    ("dev-sandbox",         developer, ["platform.developer"],  None,              PROFILE == "dev"), # dev-token mint (DEV ONLY)
    ("embed-service",       operator,  ["embed.client-admin"],  None,              EMBED),            # citizen-embed OIDC (if enabled)
]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
for USER, TENANT, ROLES, AUDS, INCLUDE in PRINCIPALS:
    if not INCLUDE:
        print(f"[1b-svc] {USER}@{TENANT}: SKIPPED (not in this profile's minimum)"); continue
    VPATH=f"secret/data/{TENANT}/{USER}/password"
    b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
    pw = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
    if pw:
        print(f"[1b-svc] {USER}: password already in Vault at {VPATH} — reusing (idempotent)")
    else:
        pw = secrets.token_urlsafe(18)
        w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"password":pw}},
               headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
        print(f"[1b-svc] {USER}: stored password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
              else f"[1b-svc] {USER}: VAULT WRITE FAILED {w.code}")
    _u={"username":USER,"tenant":TENANT,"roles":ROLES}
    if AUDS is not None: _u["audiences"]=AUDS
    _req(f"{IDN}/users", data=_u, headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
           headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    print(f"[1b-svc] {USER} ready: tenant={TENANT} roles={ROLES} audiences={AUDS}",
          "OK" if not isinstance(s, urllib.error.HTTPError) else f"set-pw {s.code}")
PY

echo "── Phase 1c · service principals (app-host/kernel/decision/workflow/launcher) — ADR-0124 slice-1c-ii ──"
# MUST run BEFORE base-app delivery: the filestore / model-gateway / notify gates ENFORCE, so every edge caller
# needs its Vault-backed audience-bound credential in place when delivery first writes/reads the filestore.
# Each is role [] (no platform reach — authority rides the run/dev token), pw in Vault (never compose), with a
# recorded audience allow-list so identity /login honours the aud request (ADR-0124). Idempotent (reuse pw).
XNET env IDT="$(_idt)" TENANT="${INSTANCE}-operator" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; TENANT=os.environ["TENANT"]
PRINCIPALS = {
    "app-host": ["svc:scheduler", "svc:filestore", "svc:model-gateway", "svc:identity"],   # +1c-iv-c: identity door (own principal)
    "kernel":   ["svc:model-gateway", "svc:filestore", "svc:secrets", "svc:runtime-manager"],  # +1c-iii: broker /fetch + runtime-mgr
    "decision": ["svc:notify"],
    "workflow": ["svc:notify"],
    "launcher": ["svc:filestore", "svc:secrets", "svc:network"],           # (runtime manager) source fetch + /materialize + runtime attest (step 5)
}
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
for USER, AUDS in PRINCIPALS.items():
    VPATH=f"secret/data/{TENANT}/{USER}/password"
    b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
    pw = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
    if pw:
        print(f"[phase1c] {USER}: password already in Vault at {VPATH} — reusing (idempotent)")
    else:
        pw = secrets.token_urlsafe(18)
        w=_req(f"{VADDR}/v1/{VPATH}", data={"data":{"password":pw}},
               headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
        print(f"[phase1c] {USER}: stored password in Vault at {VPATH}" if not isinstance(w, urllib.error.HTTPError)
              else f"[phase1c] {USER}: VAULT WRITE FAILED {w.code}")
    _req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[],"audiences":AUDS},
         headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
           headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    print(f"[phase1c] {USER} ready: tenant={TENANT} roles=[] audiences={AUDS}",
          "OK" if not isinstance(s, urllib.error.HTTPError) else f"set-pw {s.code}")
PY
# app-host must be RECREATED so its running process picks up the credential before it delivers to the filestore.
COMPOSE up -d --force-recreate app-host >/dev/null 2>&1 || COMPOSE up -d app-host
KHEALTH 2>/dev/null || true
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1 && break; sleep 1; done

echo "  · stage base-app source into app-host + deliver + list + shelf"
BASE_APPS="admin settings file-explorer console inbox personal-assistant storefront network-admin data"
XAPP sh -lc 'mkdir -p /app/_seed'
for a in $BASE_APPS; do COMPOSE cp ../../components/apps/$a app-host:/app/_seed/$a >/dev/null 2>&1 || echo "    (skip $a — not in components)"; done
XAPP env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" MODE=deliver python3 /app/reference/seed_base_os.py
XNET env INSTANCE="$INSTANCE" python3 /app/mint_base_listings.py
COMPOSE restart app-host >/dev/null
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:8080/ >/dev/null 2>&1 && break; sleep 2; done
# Shelf onto the platform realms; include the `<instance>` data tenant ONLY when it was seeded (dev profile) —
# otherwise it does not exist and shelving onto it would fail.
if [ "$SEED_DATA_TENANT" = 1 ]; then SHELF_TENANTS="$INSTANCE,$INSTANCE-developer,$INSTANCE-operator,$INSTANCE-network"
else SHELF_TENANTS="$INSTANCE-developer,$INSTANCE-operator,$INSTANCE-network"; fi
XAPP env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" MODE=shelf SHELF_TENANTS="$SHELF_TENANTS" python3 /app/reference/seed_base_os.py

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
XNET env IDT="$(_idt)" TENANT="${INSTANCE}-network" USER="trust-reader" \
        VPATH="secret/data/${INSTANCE}-network/trust-reader/password" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; TENANT=os.environ["TENANT"]; USER=os.environ["USER"]; VPATH=os.environ["VPATH"]
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
       headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
print("[phase5] identity user ensured:", "OK" if not isinstance(u, urllib.error.HTTPError) else f"{u.code} (exists ok)")
s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False},
       headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
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
XNET env IDT="$(_idt)" TENANT="${INSTANCE}-network" USER="trust-writer" \
        VPATH="secret/data/${INSTANCE}-network/trust-writer/password" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; TENANT=os.environ["TENANT"]; USER=os.environ["USER"]; VPATH=os.environ["VPATH"]
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
u=_req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":[]}, headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
print("[phase7] identity user ensured:", "OK" if not isinstance(u, urllib.error.HTTPError) else f"{u.code} (exists ok)")
s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False}, headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
print("[phase7] trust-writer login password set:", "OK" if not isinstance(s, urllib.error.HTTPError) else f"{s.code}")
PY

# The kernel caches the "current version" per schema (~300s) on first use. During Phase 1 it may have cached
# governance.role_assignment@0.1.0 (before Phase 2 publishes the 0.2.0 scoped shape that platform.authority
# needs), so the first governed kernel write below would validate against the stale 0.1.0 def (missing
# platform.authority + requiring `network`). Drop the kernel's schema cache so it re-reads the freshly-seeded
# catalog (latest version) before Phase 7b's write. A restart is the simplest cache-clear (kernel is stateless).
echo "▶ refresh kernel schema cache (pick up Phase-2 schema versions before the first governed write)"
COMPOSE restart kernel >/dev/null 2>&1 || true
for i in $(seq 1 30); do KHEALTH && break; sleep 2; done

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
    # DEBT-B35: the first-holder seed is the ONLY place is_installer=True is set — it runs in-process here
    # (never the HTTP governance API), so the zero-holder platform.authority bootstrap is installer-only.
    ctx = actor_context_from_claims({"sub": f"service://{inst}-network/trust-bootstrap",
                                     "roles": ["platform.steward"]}, is_installer=True)
    # E1: the first platform.authority holder is a principal in the PLATFORM (operator) tenant — the OS/system
    # tenant that owns platform administration — NOT admin@<inst>-network. admin@<inst>-network stays a plain
    # network.admin; platform authority and network admin are never on the same account (so NETWORK N3 holds).
    rec = gov.assign_role(ctx, {"role": "platform.authority",
                                "principal": f"user://{inst}-operator/admin",
                                "scope": {"type": "platform", "ref": None}, "status": "active"}, now)
    print(f"[phase7b] seeded FIRST platform.authority holder (admin@{inst}-operator) via governance — id={rec.get('id')}")
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
XNET env IDT="$(_idt)" TENANT="${INSTANCE}-network" INST="${INSTANCE}" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; TENANT=os.environ["TENANT"]; INST=os.environ["INST"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
for USER, _roles in (("platauth", []), ("platnone", []), ("rolesteward", ["platform.tenant-admin"])):   # (svcprobe below)
    # rolesteward (phase-5 FND-1/FND-3 test honesty): a HOME-issued account whose TOKEN carries an admin
    # role CLAIM (platform.tenant-admin) but which holds NO recorded governance grant — the negative case proving
    # "identity carries no authority" / "authority only from recorded grants". Conformance expects a kernel
    # admin endpoint to DENY it; today the kernel honours the claim (DEBT-B1) so that case is XFAIL.
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
    # ensure the identity user in ONE create carrying its EXPLICIT roles ([] for platauth/platnone; the admin
    # claim for rolesteward) + set pw only_if_unset (#282 — never reset an existing login password on re-run).
    # DEBT-B28/A73: a single CREATE persists the explicit roles list (and an empty/omitted list is NOT defaulted
    # to platform.tenant-admin), so the old double-POST workaround for rolesteward is gone.
    _req(f"{IDN}/users", data={"username":USER,"tenant":TENANT,"roles":_roles},
         headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    s=_req(f"{IDN}/set-password", data={"username":USER,"tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
           headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
    print(f"[phase9] created test user (username only): {USER}   tenant={TENANT}   roles={_roles or '(none)'}",
          "OK" if not isinstance(s, urllib.error.HTTPError) else f"set-pw {s.code}")
# svcprobe@<op> (DEV-ONLY conformance fixture): roles [], recorded audiences svc:runtime-manager + svc:identity, but
# on NO door's allow-list — it mints a correctly-addressed token so conformance can prove "undeclared caller → 403"
# (the allow-list, not just the audience, is enforced). Never created outside dev/rehearsal.
_PV=f"secret/data/{INST}-operator/svcprobe/password"
_b=_req(f"{VADDR}/v1/{_PV}", headers={"X-Vault-Token":VTOK})
_ppw = None if isinstance(_b, urllib.error.HTTPError) else (((json.loads(_b) or {}).get("data") or {}).get("data") or {}).get("password")
if not _ppw:
    _ppw = secrets.token_urlsafe(18)
    _req(f"{VADDR}/v1/{_PV}", data={"data":{"password":_ppw}}, headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
_req(f"{IDN}/users", data={"username":"svcprobe","tenant":f"{INST}-operator","roles":[],"audiences":["svc:runtime-manager","svc:identity","svc:network"]},
     headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
_s=_req(f"{IDN}/set-password", data={"username":"svcprobe","tenant":f"{INST}-operator","password":_ppw,"must_reset":False,"only_if_unset":True},
        headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
print("[phase9] svcprobe (undeclared-caller fixture) ready:", "OK" if not isinstance(_s, urllib.error.HTTPError) else f"set-pw {_s.code}")
print("[phase9] ADR-0122 test users ready: platauth, platnone — passwords in Vault at "
      f"secret/data/{INST}-network/<name>/password (field `password`); platform.authority is granted to "
      "platauth SEPARATELY via a ChangeRequest approved by a different holder (ADR-0122 step 2b), never here.")
PY
else
  echo "── Phase 9 · platform test users SKIPPED (profile=$PROFILE — production carries no test fixtures) ──"
fi

if [ "$SEED_DATA_TENANT" = 1 ]; then
echo "── Phase 9b · conformance non-admin test user (outsider) · DEV-ONLY ─────────────────────────────"
# `outsider`: a NON-admin login in the data tenant, for the conformance F2 case (a valid non-admin session is
# denied a governance write). Password generated into Vault (same convention), not read from any file.
XNET env IDT="$(_idt)" TENANT="${INSTANCE}" INST="${INSTANCE}" python3 - <<'PY'
import os, json, secrets, urllib.request, urllib.error
IDN="http://identity:8093"; VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]
IDT=os.environ["IDT"]; TENANT=os.environ["TENANT"]; INST=os.environ["INST"]
def _req(url, data=None, headers=None, method="GET"):
    r=urllib.request.Request(url, data=(json.dumps(data).encode() if data is not None else None),
                             headers=headers or {}, method=method)
    try: return urllib.request.urlopen(r, timeout=10).read()
    except urllib.error.HTTPError as e: return e
VPATH=f"secret/data/{INST}/outsider/password"
b=_req(f"{VADDR}/v1/{VPATH}", headers={"X-Vault-Token":VTOK})
pw = None if isinstance(b, urllib.error.HTTPError) else (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
if not pw:
    pw=secrets.token_urlsafe(18)
    _req(f"{VADDR}/v1/{VPATH}", data={"data":{"password":pw}}, headers={"X-Vault-Token":VTOK,"Content-Type":"application/json"}, method="POST")
    print(f"[phase9b] outsider: stored password in Vault at {VPATH}")
else:
    print(f"[phase9b] outsider: password already in Vault at {VPATH} — reusing")
_req(f"{IDN}/users", data={"username":"outsider","tenant":TENANT,"roles":[]},
     headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
_req(f"{IDN}/set-password", data={"username":"outsider","tenant":TENANT,"password":pw,"must_reset":False,"only_if_unset":True},
     headers={"Authorization":"Bearer "+IDT,"Content-Type":"application/json"}, method="POST")
print(f"[phase9b] outsider ready (non-admin, tenant={TENANT})")
PY
fi

echo "── Phase 11 · identity_lockout least-privilege DB role (ADR-0121 hardening) ─────────────────────"
# Provisioned by the split-role step (_split_roles.py, Phase 11b / bring-up): single source of truth so
# ONE step re-syncs EVERY DB-role password from Vault (migrator / kernel_app / network_app / identity_lockout).
# identity_lockout gets access ONLY to identity_login_fails, never the registry/audit tables
# (docs/security/IDENTITY-DB-LEAST-PRIVILEGE.md). Password in Vault, generated once + reused. Idempotent.
echo "  · identity_lockout provisioned by the split-role step (see Phase 11b)"

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
XNET env INSTANCE="$INSTANCE" DB_HOST=postgres python3 - < "$SCRIPT_DIR/_split_roles.py" || { echo "✗ Phase 11b failed"; exit 1; }

if [ "$RUN_PERF_SEED" = 1 ]; then
  echo "── Phase 12 · synthetic perf dataset (~1M rows) · DEV-ONLY ─────────────────────────────────────"
  ( cd ../.. && python3 perf/seed.py --confirm-dev ) || echo "  · (perf seed skipped/failed — non-fatal)"
fi

if [ "$SEED_DATA_TENANT" = 1 ]; then
echo "── Phase 13 · generate conformance/.creds.json FROM Vault · DEV-ONLY ────────────────────────────"
# E3: the conformance fixture is DERIVED from the live Vault secrets after install, never a committed input.
# One entry per conformance login user; each password is read from its Vault path (field `password`). admin +
# opadmin share the operator-admin credential (same account, two realms). Written to the gitignored file; the
# password values go straight to the file (never echoed).
CREDS_OUT="$SCRIPT_DIR/../../conformance/.creds.json"
XNET env INST="$INSTANCE" ADMIN_PW="$OPERATOR_PASSWORD" python3 - > "$CREDS_OUT" <<'PY'
import os, json, urllib.request, urllib.error
VADDR=os.environ.get("VAULT_ADDR","http://vault:8200"); VTOK=os.environ["VAULT_TOKEN"]; INST=os.environ["INST"]
def vget(path):
    try:
        b=urllib.request.urlopen(urllib.request.Request(f"{VADDR}/v1/{path}", headers={"X-Vault-Token":VTOK}), timeout=8).read()
        return (((json.loads(b) or {}).get("data") or {}).get("data") or {}).get("password")
    except urllib.error.HTTPError:
        return None
admin_pw = vget(f"secret/data/{INST}-operator/admin/password") or os.environ.get("ADMIN_PW") or None   # re-install after scrub
creds={}
if admin_pw:
    creds["admin"]   = {"password": admin_pw, "tenant": f"{INST}-network"}    # network-realm admin login
    creds["opadmin"] = {"password": admin_pw, "tenant": f"{INST}-operator", "username": "admin"}  # platform.authority holder (E1): admin@<inst>-operator
op = vget(f"secret/data/{INST}/outsider/password")
if op: creds["outsider"] = {"password": op, "tenant": INST}
pn = vget(f"secret/data/{INST}-network/platnone/password")
if pn: creds["platnone"] = {"password": pn, "tenant": f"{INST}-network"}
print(json.dumps(creds, indent=2))
PY
if [ -s "$CREDS_OUT" ]; then echo "  · wrote $(python3 -c "import json;print(len(json.load(open('$CREDS_OUT'))))" 2>/dev/null) conformance creds from Vault (passwords not printed)"
else echo "  ⚠ conformance creds generation produced no output"; fi
fi

echo "── Phase 14 · scrub the admin BOOTSTRAP password from Vault (ADR-0131 constraint 4) ─────────────"
# Only after identity CONFIRMED the bootstrap (Phase 1a admin login) and every phase that logs in as admin has run
# (and, in dev, Phase 13 has derived the gitignored conformance fixture). `kv metadata delete` destroys ALL versions
# (a plain `kv delete` is a recoverable soft-delete). A marker records the scrub so a re-install asks for the
# current password instead of minting a new, unusable bootstrap one. The provisioner credential STAYS (service).
if [ "$ADMIN_BOOTSTRAP_CONFIRMED" = 1 ] && [ "$ADMIN_SCRUBBED" = 0 ]; then
  VROOT "vault kv put -mount=secret ${INSTANCE}-operator/install-state admin_bootstrap_scrubbed=$(date -u +%Y-%m-%dT%H:%M:%SZ) >/dev/null \
         && vault kv metadata delete -mount=secret ${INSTANCE}-operator/admin/password >/dev/null" \
    || { echo "✗ could not scrub the admin bootstrap password from Vault"; exit 1; }
  if VROOT "vault kv get -mount=secret ${INSTANCE}-operator/admin/password >/dev/null 2>&1"; then
    echo "✗ admin bootstrap password STILL present after scrub"; exit 1
  fi
  echo "  ✓ admin bootstrap password removed from Vault (all versions); admin must rotate at first login (must_reset)"
elif [ "$ADMIN_SCRUBBED" = 1 ]; then
  echo "  · already scrubbed on a previous install — nothing to remove"
else
  echo "✗ bootstrap NOT confirmed — refusing to scrub (and refusing to report success)"; exit 1
fi

# slice-1e — the fresh install proves FUNCTION, not just startup. DEV profile (it delivers a conformance fixture
# component and creates a throwaway login in the dev data tenant); production carries no fixtures. Both checks must
# pass or the install FAILS: (A) a user is onboarded through the App Host; (B) an installed component writes a record
# within its grant (and is refused outside it). See deploy/installer/functional_check.py.
if [ "$PROFILE" = dev ] && [ "$SEED_DATA_TENANT" = 1 ]; then
  echo "── Phase 15 · functional proof (onboard a user via the App Host; installed component writes within its grant) · DEV-ONLY ──"
  XAPP sh -lc 'rm -rf /app/_seed3 && mkdir -p /app/_seed3/engines'
  COMPOSE cp ../../components/engines/pipeline-probe-step app-host:/app/_seed3/engines/pipeline-probe-step >/dev/null \
    || { echo "✗ Phase 15: fixture engines/pipeline-probe-step not found in components/"; exit 1; }
  XAPP env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" COMPS=engines/pipeline-probe-step python3 - < "$SCRIPT_DIR/_deliver_fixture.py" \
    || { echo "✗ Phase 15: could not deliver the fixture component"; exit 1; }
  XNET env INSTANCE="$INSTANCE" python3 /app/mint_base_listings.py >/dev/null || { echo "✗ Phase 15: listing mint failed"; exit 1; }
  XNET env INSTANCE="$INSTANCE" OPERATOR_PASSWORD="$OPERATOR_PASSWORD" python3 - < "$SCRIPT_DIR/functional_check.py" \
    || { echo "✗ Phase 15: functional proof FAILED — the install starts but does not work end to end"; exit 1; }
else
  echo "── Phase 15 · functional proof SKIPPED (profile=$PROFILE — needs the dev data tenant + fixture) ──"
fi

echo "✓ install complete — profile=$PROFILE"

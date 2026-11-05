# Containment runbook — passwordless-login + public-kernel exposure (2026-11-02)

Prod host `13.205.13.220`. Reverse proxy = `airawat-nginx`, config is a **host-mounted editable file**:
`~/airawatos/nginx.conf` → `/etc/nginx/conf.d/default.conf` (ro in the container). Edit the host file, then
`docker exec airawat-nginx nginx -t && docker exec airawat-nginx nginx -s reload`. Both moves below are
reversible by reverting the file + reload. **Back up first:** `cp ~/airawatos/nginx.conf ~/airawatos/nginx.conf.bak`.

Current nginx `server { listen 80; server_name airos.airawat.org; ... }` has exactly these locations:
`/network/`→network:8090, `/kernel/`→kernel:8080, `/kc/`→keycloak:8080, `/`→app-host:8099.

---

## 2a. Close the passwordless privileged login

**Exposed route:** `POST /login` on the App Host (public via nginx `location /`) → `_do_login` →
`_login_session(realm, username)` → reference IdP `/realms/{realm}/login`, which mints a token with **no
password** for any user that has none. **`realm`+`username` are in the POST body**, so nginx cannot tell one
principal from another at the path — principal-specific filtering must be at the App Host or the IdP.

**Principals exposed (all passwordless in the deployed `identity-users.json`):** `bmc-admin`,
`mysuru-commissioner`, `nashik-admin`, `pune-admin` (`platform.tenant-admin`); `nashik-transport`,
`nashik-medical`, `nashik-marshal`, `nashik-sanitation`, `nashik-grievance-officer`; and ~30 `civic.resident`
citizens. **NOT exposed via this IdP:** `steward`/`platform.steward`, `airawat-scheduler` (absent — demo seed
off), and the Keycloak `verify` service account (separate IdP). So "steward + service principals" are already
not reachable here; the real exposure is **tenant-admins + functional officers (+ citizens)**.

### Option A — edge block of the staff login (instant, fully reversible) ← recommended stopgap
`POST /login` is the **shell/staff** login; citizens self-serve through `/embed/login` + `/citizen-register`.
Blocking `POST /login` closes the tenant-admin exposure. Add to `~/airawatos/nginx.conf` **inside the
`server {}` block, above `location /`**:
```nginx
    location = /login {
        if ($request_method = POST) { return 403; }   # CONTAINMENT: no passwordless staff login from public
        set $up_app_login app-host:8099;               # keep GET (the login PAGE) working
        proxy_pass http://$up_app_login;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```
Reload: `docker exec airawat-nginx nginx -t && docker exec airawat-nginx nginx -s reload`
**Verify (from OUTSIDE the host):**
`curl -s -o /dev/null -w "%{http_code}\n" -X POST https://airos.airawat.org/login -H 'content-type: application/json' -d '{"realm":"bmc","username":"bmc-admin"}'` → **403**.
**Undo:** delete the `location = /login` block, reload.

### Option B — surgical, App Host (needs a redeploy; keeps citizens online)
In `_do_login`/`_login_session`, require a non-empty password for any realm other than the citizens realm
(`CITIZEN_TENANT`), i.e. reject passwordless login for staff/admin realms. Reversible by redeploy. Pair with:

### Option C — the real fix, IdP (principal-specific, no code)
Set a password on (or disable) each privileged account in `identity-users.json` / via the password-gate
rollout (ADR-0068) so those users are no longer passwordless; citizens stay passwordless. This is the durable
close; Option A/B are the bridge to it.

---

## 2b. Remove the Kernel's public routing

The Kernel is publicly routed at `/kernel/`. Internal callers (App Host, Network, service-gateway) reach it
**directly at `kernel:8080` on the docker network**, NOT through nginx — confirmed: in the retained nginx
window every `/kernel/` request came from an external IP, zero internal. So removing the public route does
not break internal traffic.

Edit `~/airawatos/nginx.conf` and **delete (or comment out) the entire `location /kernel/ { … }` block**, then
`docker exec airawat-nginx nginx -t && docker exec airawat-nginx nginx -s reload`.
**Verify:**
- external: `curl -s -o /dev/null -w "%{http_code}\n" https://airos.airawat.org/kernel/v1/health` → **404** (gone).
- internal still works: `docker exec airawat-app-host sh -lc 'curl -s -o /dev/null -w "%{http_code}\n" http://kernel:8080/v1/health'` → **200**.
- app still works: load the site, open an app that reads data → OK (the browser uses `/network/`, never `/kernel/`).
**Undo:** restore the `location /kernel/` block, reload.

---

## 2c. What legitimate flow breaks, and how to tell
- **2a Option A:** remote **staff/admin** login via the shell stops (that's the point). Citizens using
  `/embed/login` are unaffected — confirm by loading the citizen flow. If any staff must log in during the
  window, add an `allow <their IP>;` + `deny all;` instead of the blanket POST 403, or use Option C.
- **2a Options B/C:** nothing legitimate breaks — citizens stay passwordless; staff/admins log in with a
  password they should already have (or get one provisioned).
- **2b:** the browser UI and all internal services are unaffected (they don't use public `/kernel/`). What
  stops: the single external consumer of `/kernel/` seen in logs (`13.61.56.103` — **identify this first**,
  see forensics) and the one-time bootstrap health-check line that curls `localhost/kernel/v1/health`
  (cosmetic; runtime health is checked internally). Tell: watch `docker logs airawat-nginx` for new 404s on
  `/kernel/` from any INTERNAL (172.x) client after reload — expect none.

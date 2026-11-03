# Incident note — EC2 production exposure hardening (2026-11-03)

**Status:** findings confirmed locally / from source; **production changes NOT executed by this session** —
this agent has no SSH/AWS access to the EC2 box and does not connect to the frozen production host. Each
change below is the owner-approved runbook (read-only check → change → verify → undo) for the owner to run.
Companion: `docs/consolidation/DEBT-REGISTER.md`, `docs/specs/FOUNDATIONS-v0.1.md`, `deploy/PRODUCTION-READINESS.md`.
Known prod host: **13.205.13.220** (`airos.airawat.org`).

## What was found (evidence)
- **F-1 run_token leak (B15).** `GET /v1/components` is unauthenticated and returns `list(INSTALLED.values())`
  (`kernel/api/app.py:2370`), and each INSTALLED value carries `"run_token"` — a high-entropy **bearer
  secret** (`app.py:2058`, minted at `_mint_run_token` `app.py:1116`). Confirmed live on local-dev: the
  endpoint answers **HTTP 200** with no token (empty there only because `installed count: 0`). The committed
  front door routes `/kernel/` → kernel:8080 (`deploy/local-dev/nginx.conf:20`), so on any deploy with that
  routing the path is reachable at `/kernel/v1/components` — directly, no bridge. **EC2 public reachability:
  unverified** (live EC2 nginx not in source).
- **F-2 internal-service exposure (B5/#3).** In committed compose only nginx publishes a host port; all
  internal services have no `ports:`. EC2's live compose + security group are **not in source** → whether
  8080/8090/8093/8095/8102/8103/8104/Postgres/Vault are reachable on the public IP is **unverified**.
- **F-3 passwordless mint (B14/A30).** Identity `IDENTITY_PASSWORD_REQUIRED` defaults to **shadow** (mints
  passwordless, logs only; `identity.py:283`); EC2 does not set it. Internet-reachable minting paths via
  app-host: `POST /login`, `/embed/login`, `/embed/signup`, `/register`, `/link`.
- **F-4 `13.61.56.103`.** Not referenced in any committed file; **unknown** — not confirmed to be ours.
  Distinct from the known box 13.205.13.220.
- **F-5 sessions.** App-host `_SESSIONS` are in-memory (`hostcore.py:52`) → an app-host restart invalidates
  all cookie sessions; underlying identity JWTs remain valid until their ≤1h `exp` regardless (no revocation
  list).
- **F-6 nginx not in source** for EC2 (only `deploy/local/` + `deploy/local-dev/` committed).

## What `/register`, `/link`, `/embed/*` currently allow (source review — step 4)
A **new/unauthenticated user** can only obtain a **citizen** identity, never admin/steward:
- `POST /register` (identity.py) — public self-signup; **can ONLY mint `civic.resident` in the fixed
  `CITIZEN_REALM` (`citizens`)**; cannot pick a tenant or an elevated role (identity.py `/register` handler).
- `POST /embed/signup` (app_host.py:1242) — calls the public `/register` (→ `civic.resident` in `citizens`)
  then continues the embed OIDC+PKCE flow.
- `POST /embed/login` (app_host.py:1205) — authenticates an existing citizen against the `citizens` realm.
- `/link` (app_host.py, `_CHAT_CITIZEN`) — captures a citizen token at account-link for the chat channel.
→ None of these can produce a `platform.*`/`network.admin`/steward role. Blocking them only affects citizen
self-signup/login. **Left unblocked pending the owner's decision** (as instructed).

## Changes (approved; executed by the owner via the runbook)
All command blocks are in the owner's runbook (this session's reply of 2026-11-03). Summary + undo:
1. **Edge-block the run_token endpoint** — add `location = /kernel/v1/components { return 404; }` above the
   `/kernel/` block in the live nginx; `nginx -t`; reload. **Undo:** remove the block + reload.
2. **Revoke public inbound to internal ports** (8080/8090/8093/8095/8102/8103/8104/5432/8200) from
   `0.0.0.0/0`; **do NOT touch 22/80/443**. **Undo:** `authorize-security-group-ingress` the same rule.
3. **Identify 13.61.56.103** (describe-instances all regions) + grep retained nginx/app-host/kernel/identity
   logs for requests from it to `/kernel/v1/components` or any login. No change; report.
4. **Passwordless off** — after confirming the live identity image == running image, set
   `IDENTITY_PASSWORD_REQUIRED=enforce` on the identity service and `--force-recreate` it. **Undo:** remove
   the env (reverts to shadow) + recreate. Expected lockout: every tenant admin with **no** password.
5. **Restart App Host** (`--no-deps`, same image check) to drop in-memory sessions — **gated**: STOP if step
   3 shows 13.61.56.103 logged in as a privileged account (key rotation approved separately).
6. **Run-token re-issue plan only** (step 6) — not executed.
7. **Capture the live EC2 nginx** off the box and commit under `deploy/ec2/nginx/` (destination created; the
   live file is pending capture by the owner).

## Run-token model + re-issue plan (step 6 — NOT executed)
- **Issue:** at per-tenant install (`/v1/components/install`), the kernel mints a high-entropy run-token
  (`_mint_run_token`, `app.py:1116`), stores it in `RUN_TOKENS[token]` (the live capability map) and in
  `INSTALLED[ikey].run_token` (`app.py:2056-2058`). A re-install is **idempotent** — it *reuses* the existing
  token (`_mint_run_token(existing=…)`) so already-launched component containers stay valid. Dev-tokens
  (`dev-…`) are separate and memory-only.
- **Re-issue (rotate) for every installed component** — for each `cid@tenant`: (a) mint a **fresh** token
  (install with `existing=None`, or a dedicated rotate op), writing the new token into `INSTALLED` and
  `RUN_TOKENS`; (b) **remove the old `RUN_TOKENS[old]` entry** (otherwise the old bearer still works); (c)
  **restart the component's runtime container** so it picks up the new `RUN_TOKEN` env.
- **What breaks during re-issue:** between (a) and (c), a running component still presents the **old** token
  — if (b) removes it first, that component's broker calls fail until (c) restarts it (brief per-component
  outage); if (b) is deferred, the old token remains valid (no rotation benefit) until removed. Order per
  component: mint new → restart container → remove old token (minimizes the gap). Dev-tokens and any
  INSTALLED-rehydrated-at-boot tokens are lost on a kernel restart regardless (B10).
- **Enumerate installed components on EC2 (read-only):** once step 1's edge-block is in place, enumerate from
  the registry rather than the (now-blocked) `/v1/components` — e.g. an admin-token query for
  `component.install`/INSTALLED records, or `docker exec <kernel> python3 -c "import api.app as a;
  print(list(a.INSTALLED.keys()))"` on the box.

## Open items
- Verify EC2 public reachability of `/kernel/v1/components` and of internal ports (steps 1–2 read-only).
- Identify 13.61.56.103 and whether it accessed the leak/login (step 3).
- Durable fix for the run_token leak: gate `components_list` in the kernel (code; FOUNDATIONS F8) — not just
  the edge block.
- `IDENTITY_PASSWORD_REQUIRED=enforce` locks out password-less tenant admins — provision their passwords
  first (list from step 4).
- Decide on `/register`, `/link`, `/embed/*` (citizen self-signup) — left on pending owner's call.
- Identity signing-key rotation (invalidate in-flight JWTs) — approved separately, gated on step 3.
- Capture + commit the live EC2 nginx config (step 7).
- Broader: ADR-0124 (retire shared-secret internal gates, no fail-open) addresses B4/B5/B14 durably.

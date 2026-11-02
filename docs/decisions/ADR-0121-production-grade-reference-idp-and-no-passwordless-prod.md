# ADR-0121 — Production-grade reference IdP + "every account must have a password"

Status: Accepted (implementation staged — shadow first, enforce via rollout)
Date: 2026-11-02 (rev-2: password requirement is a deployment policy, not a per-tenant-environment exemption)
Relates to: ADR-0068 (pluggable IdP / password gate), ADR-0051 (tenant `environment`), ADR-0115 (realm-scoped
users + first-login reset), ADR-0084 (per-tenant issuers). Supersedes the "passwordless dev auth" posture of
the reference identity service for any deployed instance. Closes task #282 (harden reference IdP); informs
#262 (reproducible identity image).

## Context

The reference identity service (`platform-spec/reference/identity.py`) was built as **passwordless dev auth**
— "the point is the TOKEN contract, not credential checking." A per-user password gate exists (ADR-0068,
pbkdf2-sha256) but is **opt-in**, and in the live sandbox deployment **no account had a password set**.
Combined with the public App Host login (`POST /login`) and a publicly-routed kernel, anyone on the internet
who knew a tenant name could open a session as that tenant's `platform.tenant-admin` — no password. This held
even though the deployment is an internet-facing **demo/sandbox** (no real citizen PII), because an
internet-reachable box with passwordless admin is still an open target / pivot.

The tiered identity model stands: **reference IdP is the default** (low-ops, good for small agencies and
pilots); **Keycloak / any OIDC is pluggable** for agencies that bring their own identity. The security floor
is **identical** for both and does not depend on which IdP an agency chose.

## Decision

**(a) Bring the reference IdP to production grade.** Keep the existing primitives (pbkdf2-sha256 passwords,
first-login forced reset, per-tenant issuer keys). Add:
- **Brute-force lockout** on `/login`, keyed per `(account, source-ip)` so one source cannot lock a user out
  from another (no lockout-DoS); env-tunable (`IDENTITY_LOGIN_MAX_FAILS`, `IDENTITY_LOGIN_LOCK_SECONDS`), plus
  an edge `limit_req` as defense-in-depth.
- **Reproducible, auth-safe image** built from source with a durably Vault-backed signing key (task #262).
- *(phase 2)* optional **TOTP/MFA** for privileged roles; IdP-side account disable; password rotation/expiry.

**(b) Platform invariant — every account on a deployed instance must have a password.** Password requirement
is a **DEPLOYMENT policy**, INDEPENDENT of a tenant's `environment` (ADR-0051). A `sandbox` tenant is relaxed
for *other* things — dev tokens, data rules — but its **logins still require a password**: an
internet-reachable deployment must not carry passwordless accounts. Passwordless is permitted **only** when an
operator explicitly sets the mode to `off`, for a **local/offline** dev instance (e.g. the local compose).
Controlled by `IDENTITY_PASSWORD_REQUIRED`:
- `off` — passwordless allowed (local/offline dev only);
- `shadow` — log a "would-refuse" line but still mint (**default**, so a deploy never locks anyone out before
  accounts have passwords);
- `enforce` — refuse any passwordless login (every account must present a password).

This is deliberately stricter than tying the rule to `environment`: tagging a tenant `sandbox` must not become
a way to run passwordless logins on an exposed host. *(phase 2 defense-in-depth: the kernel/network reject a
token whose `amr`/assurance is A0 on a deployed instance.)*

## Enforcement points (reference)
- `identity.py`: `_login_locked`/`_record_login_fail`/`_clear_login_fails` (lockout) and `_PW_MODE`
  (`IDENTITY_PASSWORD_REQUIRED`), both wired into the `POST /login` + `POST /realms/<tenant>/login` handler. The
  gate no longer consults the tenant environment — it is a single deployment-level mode.
- Tests: `platform-spec/reference/test_identity_passwordless.py` — enforce refuses passwordless for **every**
  tenant incl. one tagged `sandbox`; correct/wrong password; lockout after N; shadow/off behaviours.

## Consequences & rollout (mandatory ordering)
Flipping to `enforce` while an account still has no password locks that account out. Therefore:
1. Deploy with `shadow` (default); collect the "would-refuse" log for one pass → enumerates every passwordless
   account.
2. Set passwords (or provisioner initial-password + `must_reset`) on those accounts.
3. Flip `IDENTITY_PASSWORD_REQUIRED=enforce`.
4. **Then** lift any edge `POST /login` containment block — now safe: logins require a password.
5. **Break-glass:** account recovery is always via the host (`_set_password` on the box), never dependent on
   the web login.

Open items:
- **Citizen self-service** (`civic.resident`, the `/embed` flow) has no admin to hand out a temp password.
  Requiring a password for citizens means the **registration flow must set one** (and/or move to OTP/email
  verification). Until that lands, either require a password at citizen-register, or treat existing demo
  citizen accounts as throwaways (common demo password / delete). Tracked separately; do not block the staff
  rollout on it.
- Internal server-side helpers that call `POST /login` without credentials must move to a password or a
  service token before `enforce`; the shadow pass surfaces them.
- `environment: sandbox` is still set on sandbox tenants for the non-auth relaxations (ADR-0051) — it just no
  longer waives the password requirement.

## Alternatives considered
- **Make Keycloak the default for all agencies.** Rejected: it does not raise the security floor by itself
  (the escalation in this incident ran *through* a misconfigured Keycloak dev realm) and imposes real ops
  burden on the small agencies the reference IdP serves. Fix the floor, don't standardize on one product.
- **Exempt dev/sandbox tenants from the password requirement (rev-1 of this ADR).** Rejected: a `sandbox` tag
  on an internet-reachable deployment must not permit passwordless admin. Passwordless is a *local/offline*
  convenience (`off` mode), not a property of a deployed tenant's environment.
- **Keep passwordless + rely only on the edge block.** Rejected: a blanket edge block takes down legitimate
  login and is not a resting state; the invariant lets real users back in *with* a password.

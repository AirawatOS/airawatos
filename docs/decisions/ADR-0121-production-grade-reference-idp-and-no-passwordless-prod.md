# ADR-0121 — Production-grade reference IdP + "no passwordless login for a production tenant"

Status: Accepted (implementation staged — shadow first, enforce via canary)
Date: 2026-11-02
Relates to: ADR-0068 (pluggable IdP / password gate), ADR-0051 (tenant `environment`), ADR-0115 (realm-scoped
users + first-login reset), ADR-0084 (per-tenant issuers). Supersedes the "passwordless dev auth" posture of
the reference identity service for production tenants. Closes tasks #282 (harden reference IdP) and informs
#262 (reproducible identity image).

## Context

The reference identity service (`platform-spec/reference/identity.py`) was built as **passwordless dev auth**
— "the point is the TOKEN contract, not credential checking." A per-user password gate exists (ADR-0068,
pbkdf2-sha256) but is **opt-in**, and in the live deployment **no account had a password set**. Combined with
the public App Host login (`POST /login`) and a publicly-routed kernel, this meant anyone on the internet who
knew a tenant name could open a session as that city's `platform.tenant-admin` — no password, no stolen key.
A containment block on `POST /login` was applied at the edge, but that blocks *all* staff logins and is a
stopgap, not a resting state.

The tiered identity model stands: **reference IdP is the default** (low-ops, good for small agencies and
pilots); **Keycloak / any OIDC is pluggable** for agencies that bring their own identity. The security floor,
however, must be **identical** for both and must not depend on which IdP an agency chose — a small
municipality holds citizen PII and can be taken over just as a large one can.

## Decision

**(a) Bring the reference IdP to production grade.** Keep the existing primitives (pbkdf2-sha256 passwords,
first-login forced reset, per-tenant issuer keys). Add:
- **Brute-force lockout** on `/login`, keyed per `(account, source-ip)` so one source cannot lock a user out
  from another (no lockout-DoS); env-tunable (`IDENTITY_LOGIN_MAX_FAILS`, `IDENTITY_LOGIN_LOCK_SECONDS`), plus
  an edge `limit_req` as defense-in-depth.
- **Reproducible, auth-safe image** built from source with a durably Vault-backed signing key (task #262).
- *(phase 2)* optional **TOTP/MFA** for privileged roles (`platform.*`, `*.admin`, steward); IdP-side account
  disable; password rotation/expiry.

**(b) Platform invariant — no passwordless login for a production tenant.** Passwordless (A0) login is
permitted **only** for a tenant whose `environment` (ADR-0051) is explicitly dev/sandbox
(`{dev, development, sandbox, test, local}`). A production tenant — **or any tenant whose environment is
unset/unknown (FAIL-SECURE)** — requires a password. Enforced at the one choke point that mints tokens (the
IdP login handler), staged via `IDENTITY_PROD_PASSWORD_REQUIRED`:
- `off` — legacy (passwordless everywhere);
- `shadow` — log a "would-refuse" line but still mint (**default**, so a deploy never locks anyone out before
  prod accounts have passwords);
- `enforce` — refuse a passwordless login for a production tenant.
Dev/sandbox tenants (incl. the AirawatDeveloper sandbox) stay passwordless, so developer ergonomics and
pilots are unaffected. *(phase 2: defense-in-depth — the kernel/network reject a token whose `tenant_env` is
production but whose `amr`/assurance is A0, since the token already carries assurance.)*

## Enforcement points (reference)
- `identity.py`: `_login_locked`/`_record_login_fail`/`_clear_login_fails` (lockout); `_passwordless_allowed(env)`
  + `_PROD_PW_MODE` (invariant); both wired into the `POST /login` + `POST /realms/<tenant>/login` handler, using
  the tenant `environment` already resolved from the registry (`_tenant(...)`) and already stamped into tokens
  as `tenant_env`.
- Tests: `platform-spec/reference/test_identity_passwordless.py` (enforce refuses prod-passwordless; dev stays
  passwordless; correct/wrong password; lockout after N; shadow/off behaviours).

## Consequences & migration (mandatory ordering)
Flipping (b) to `enforce` while a production account still has no password locks that account out. Therefore:
1. Deploy with `shadow` (default) and collect the "would-refuse" log for one pass — this enumerates every
   production account still passwordless.
2. Set passwords (or provisioner initial-password + `must_reset`) on those accounts.
3. Flip `IDENTITY_PROD_PASSWORD_REQUIRED=enforce`.
4. **Then** lift the edge `POST /login` containment block — now safe: production logins require a password and
   an attacker with only a username is refused by the IdP.
5. **Break-glass:** account recovery is always via the host (`_set_password` on the box), never dependent on
   the web login, so a bad flip cannot lock out the fix.

Known migration item: internal server-side helpers that call `POST /login` **without** a `tenant` resolve to
an unknown environment and, under `enforce`, would be treated as production (refused if passwordless). The
shadow pass surfaces these; fix by passing the tenant (or moving them to a service token) before enforcing.

## Alternatives considered
- **Make Keycloak the default for all agencies.** Rejected: it does not raise the security floor by itself
  (the actual escalation in this incident ran *through* a misconfigured Keycloak dev realm), and it imposes a
  real operational burden (own DB, upgrades, realm admin, HA) on exactly the small agencies the reference IdP
  serves. The right fix is an IdP-agnostic baseline, not standardizing on one product.
- **Keep passwordless + rely only on the edge block.** Rejected: a blanket edge block takes down legitimate
  staff login and is not a resting state; the invariant lets real users back in *with* a password.

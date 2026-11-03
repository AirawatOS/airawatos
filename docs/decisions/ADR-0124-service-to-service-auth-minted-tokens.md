# ADR-0124 — Service-to-service auth: short-lived home-issuer tokens minted on demand from Vault; retire all shared-secret internal gates

**Status:** Accepted
**Date:** 2026-11-03
**Relates to:** [[FOUNDATIONS-v0.1]] F8, F9; debt **B4, B5, B6, B14**; A26, A29, A33, A36–A38; extends the
trust-reader/trust-writer mint-on-demand pattern ([[ADR-0122]], `network/trust_admin_authz.py`).

## Context
Internal service-to-service calls today authenticate three insecure ways (debt **B4/B14**):
1. **Shared-secret internal tokens** gating privileged endpoints, several **fail-open when the env is unset**
   — `SECRETS_INTERNAL` (`secrets.py:147,155`), `RUNTIME_MANAGER_INTERNAL` (`runtime_manager.py:49`, set in
   **no** deploy file), `GW_INTERNAL_TOKEN` default `gw-internal` (`model_gateway.py:21`), `IDENTITY_INTERNAL`
   default literal (`identity.py:37`).
2. **Unauthenticated endpoints** doing privileged work (filestore, notify, scheduler `/run`, model-gateway,
   automation, event_relay — B5).
3. **Passwordless service principals** — `airawat-scheduler`/`platform.steward` mint full-authority tokens
   from the reference IdP with **no credential** (`scheduler.py:50`, `automation.py:29`, `event_relay.py:25`,
   identity `_DEMO_USERS`). Anyone who can reach the IdP mints them (B14).

The trust-reader/writer pattern (ADR-0122) already proves the correct shape: a dedicated read-only / write
service principal whose password is in **Vault**, from which the service **mints a short-lived token on
demand** from the local identity service, caches it until shortly before expiry, and **fails closed**.

## Decision
**All service-to-service authentication uses short-lived, audience-bound JWTs from the home issuer, minted
on demand with Vault-held credentials. Every shared-secret internal gate is retired. No gate fails open.**

- **Minted tokens, not shared secrets.** Each service principal is a real identity (`service://<tenant>/<name>`)
  with a credential **in Vault** (never in compose/env). A service mints its token on demand (Vault password
  → `POST /realms/<tenant>/login`), caches it, and re-mints before expiry — the generalized
  `trust_admin_authz._mint_token(prefix)` pattern, applied to every service principal (scheduler, automation,
  event_relay, model-gateway admin, runtime-manager, secrets materialize caller, etc.).
- **Short-lived + audience-bound + home-issuer.** Tokens are ≤1h, carry the deployment's `aud`, and `iss` is
  the home issuer; the callee verifies signature + `exp` + `aud` + `iss` against JWKS (no new static trust).
- **Retire shared-secret gates.** `SECRETS_INTERNAL`, `RUNTIME_MANAGER_INTERNAL`, `GW_INTERNAL_TOKEN`, and
  the `IDENTITY_INTERNAL` provisioner secret are removed as *authorization* mechanisms; the endpoints they
  guarded verify a minted service token and authorize it via a recorded grant (F2) instead.
- **No fail-open, no unauthenticated privileged endpoint (F8).** Every internal endpoint that reads a secret,
  writes a record, runs a component, or spends money requires a verified token and denies on its absence —
  the `if INTERNAL and header != INTERNAL` fail-open idiom is deleted; filestore/notify/scheduler/
  model-gateway/automation/event_relay gain a verify-token gate.
- **No passwordless service principals.** The IdP's passwordless path is not used for service identities;
  service credentials live in Vault and are rotated there (ADR-0121 `enforce` applies to them too).
- **Durability of the mint credential** is the one requirement the IdP must meet: a renewable/rotatable
  Vault-held credential (the current reference IdP issues only 1h *tokens* and has no durable *service
  credential* — A33; this ADR makes the Vault-held password that durable credential, re-minting tokens).

## Consequences
- **Decided; debt B4 (fail-open internal gates), B14 (passwordless principals), and the internal-auth half
  of B5/B6 remain OPEN until implemented.** Implementing work: *service-principal mint-on-demand rollout* —
  (1) give each service principal a Vault credential + mint-on-demand (generalized `_mint_token`); (2) add a
  verify-token gate to each callee (secrets, filestore, notify, scheduler, model-gateway, automation,
  event_relay, runtime-manager); (3) delete the shared-secret envs + fail-open branches; (4) flip IdP
  `IDENTITY_PASSWORD_REQUIRED=enforce`. Target principles: F2/F8/F9/F16.
- One mint helper + one callee-side verify helper replace the ~triplicated service-auth blocks and the
  per-service shared-secret literals (A29, A36–A38; C-dup items) — **debt open until that refactor lands**.
- Rollout (separate slices): (1) give each service principal a Vault credential + mint-on-demand; (2) add the
  verify-token gate to each callee and switch the caller to a Bearer; (3) delete the shared-secret env +
  fail-open branches; (4) flip IdP password mode to `enforce`. Each callee migrates caller-then-gate to avoid
  lockout.

## Alternatives rejected
- *Keep shared secrets but make them mandatory (no empty default)* — removes fail-open but still a bearer-of-
  secret model with no per-call identity/audit, no rotation, no least-privilege; fails F2/F9.
- *mTLS between services* — viable transport auth but does not carry a verifiable principal identity/audience
  for the recorded-grant decision; can complement, not replace, the minted token.

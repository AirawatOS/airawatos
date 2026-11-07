# ADR-0131 — Root of trust at install

**Status:** Accepted (FIX-PLAN L1 slice-1c-iv)
**Supersedes the bootstrap half of:** DEBT-A71 (IDENTITY_INTERNAL), DEBT-B29 (unconfigured provisioner gate)

## Context

The identity service's account-provisioning door (`/users`, `/set-password`, directory reads) was gated by a
**shared committed literal** `IDENTITY_INTERNAL`. Closing it to an audience-bound `svc:identity` token (the
A71 pattern already applied to secrets, runtime-manager, model-gateway) hit a **bootstrap deadlock**: the first
identity writes happen at install (via `network/ensure_install.py`), and minting any `svc:identity` token needs
a principal that only exists *after* those writes. A shared-secret bootstrap channel would re-introduce exactly
the literal we are removing.

## Decision

**The operator install config in Vault is the root of trust. Identity owns realm/principal creation. There is
no bootstrap channel on the internal door.**

1. **Install config in Vault (the root).** Before identity starts, the installer writes an operator install
   config to Vault: the operator realm, its first administrator's initial password, and the `provisioner`
   principal's password (dev profile additionally lists the local-dev realms + test principals). Vault — already
   the platform's secret/transit root — is therefore the single root of trust for who may first exist.
2. **Identity self-bootstraps at boot, create-only.** At startup identity reads that config and **creates only
   principals that do not already exist** — it NEVER resets an existing admin, password, or role. Changing the
   config afterwards does not alter existing principals (constraint 1). The seed is a direct in-process store
   write, not an HTTP call through the gate, so there is no deadlock and no bootstrap secret on the door.
3. **Minimum in production.** Production bootstraps only the **operator realm, its first administrator, and the
   provisioner**. All other tenants/principals are created later through the normal governed path. The four
   local-dev realms and test users are bootstrapped **only under the dev profile** (`IDENTITY_SEED_DEMO`/
   `AIRAWAT_PROFILE=dev`), consistent with PLT-1 (production ships empty).
4. **First admin rotates immediately.** The first administrator's seeded password is marked `must_reset`; the
   installer **removes the bootstrap admin password from Vault** once identity confirms the bootstrap, so the
   initial secret does not linger.
5. **The door is `svc:identity`-only from day one.** `/users`, `/set-password` and the directory reads require
   an audience-bound `svc:identity` token from an allow-listed caller (`provisioner` + the declared service
   callers in ARCHITECTURE-FLOWS), verified against identity's own JWKS, **always enforce**. **B29 preserved:**
   if the provisioner cannot be seeded (Vault unreachable / config absent) identity fails every write closed and
   refuses to boot under `AIRAWAT_ENV=production`.
6. **Tenant records stay the network authority's.** `ensure_install` still signs the tenant records via the
   network authority (`api.AUTH.sign_tenant` → network's own in-process registry); identity resolves tenants
   from the network registry (`/v1/tenants/resolve`). "Identity owns realm/principal **creation**" means the IdP
   **user/principal** records, not the authority-signed tenant records. `ensure_install` stops writing to
   identity entirely.

## Consequences

- `IDENTITY_INTERNAL` is removed from all code, compose, env, and committed defaults. A71 is fully closed for
  gates (secrets + runtime-manager + model-gateway already done in 1c-ii/1c-iii).
- Callers mint `svc:identity`: the installer scripts, app-host (×8 sites), and network `api.py` join→provision
  (×3 sites, which gains a Vault-backed inline minter + an `svc-network` policy grant to read the provisioner
  password). The allow-list the door declares: **identity writes ← `{provisioner}`** (+ any service principal a
  declared edge adds).
- The reference image (identity + app-host) and the network image are rebuilt; the installer seeds the config
  before bring-up and scrubs the admin password after confirmation.
- Trade-off: the install config (passwords) lives in Vault during install — acceptable because Vault is already
  the platform root, the admin password is single-use (`must_reset` + scrubbed), and nothing is a committed
  literal.

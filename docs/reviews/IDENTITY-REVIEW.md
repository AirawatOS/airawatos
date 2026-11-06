# Identity review — Consolidation phase 5, slice 2

**Date:** 2026-11-06 · **Scope:** the reference Identity service / home IdP — `platform-spec/reference/identity.py`
(845 ln), `tokens.py`, `svc_token.py`, `platform-spec/deploy/ec2/keycloak-bootstrap.py`, `network/ensure_install.py`,
and the `kernel/services/authn.py` trust boundary — against the rules Identity is responsible for: FOUNDATIONS
FND-1/FND-9/FND-12/FND-15/FND-16; ACCOUNT ACC-2/ACC-3/ACC-4/ACC-5; CLIENT CLI-1/CLI-3; PLATFORM PLT-3 (+ realms).
**Method:** three fresh, independent reviewer agents (not the authoring session), read-only, findings-only — no
code changed. Evidence is `file:line`.

> **Matrix vs review** (same as the kernel slice): STATUS-MATRIX.md is conformance-*measured*; this review is a
> code *audit*. The new conformance cases (`conformance/run.py` → `run_identity_review_cases`) encode the testable
> violations as XFAIL (ACC-2, ACC-3, CLI-3) so the matrix now shows them VIOLATED; the untestable ones are recorded
> SKIP_BUILD with a reason. **PLT-3 label note:** in the shipped spec PLT-3 is "the operator holds no governance
> role" (not realm modelling) — not an Identity surface; the login-namespace-as-tenant concern is **DEBT-B21**.

---

## Summary (one page)

**Verdict counts (12 named rules):** held **0** · partial **4** (FND-12, FND-15, ACC-4, CLI-3) · violated **6**
(FND-1, FND-9, FND-16, ACC-2, ACC-3, + realms-as-tenants/DEBT-B21) · not-applicable(not-identity) **3** (ACC-5,
CLI-1, PLT-3-operator-role).

**Top risks (most serious first):**
1. **Passwordless full-authority mint + fail-open write gates** (FND-9 — *critical*). `steward`→`platform.steward`
   and `airawat-scheduler`→`platform.scheduler` are seeded with NO credential (identity.py:72,76) and mint a signed
   token whenever `_PW_MODE != enforce` — and the default is **shadow** (`:499`, `:816-823`). Separately, POST
   `/users` / `/set-password` / `/prefs` use `if INTERNAL and hdr!=INTERNAL` (`:691,724,744`) which **fails open**
   when `IDENTITY_INTERNAL` is empty (the GET directory gate was fixed fail-closed `:657`; the writes weren't),
   masked only by a committed literal default (`:38`). (DEBT-B14/A26/A30 + **NEW DEBT-B29**)
2. **Assurance is a static, off-vocabulary lie** (ACC-3 — *high*). A uniform `"A0"` (`DEV_AUTH`, `:36`) is stamped
   on **every** login incl. verified-password logins (`:585`); Keycloak stamps a static `"A2"` on every login and
   emits no `amr` mapper (keycloak-bootstrap.py:84-107); the values `A0`/`A2` don't match the spec vocabulary
   `AL0–AL3`; and the prod boot guard can't see passwordless accounts. Any downstream gating on assurance is
   defeated. (DEBT-B13/A34/A35 + **NEW DEBT-B32**)
3. **Tokens carry authority, not identity** (FND-1/CLI-3 — *high*). `issue()` stamps `roles` into the JWT (`:584`,
   DEBT-B1) and a roleless provisioning create defaults to `platform.tenant-admin` (`:710-711`, **NEW DEBT-B28**).
   Tokens are platform-addressed (`aud="airawatos"`, `:33/:582`) with no consent reference — broad, authority-
   bearing, revocation-proof for the 1h TTL. (**NEW DEBT-B31**)
4. **Prod-pointing defaults + no fail-loud** (FND-16 — *high*). `ISS`/`AUD`/`HOME_ISS` default to
   `ds:airawat:identity`/`airawatos` (`:31,33`; authn.py:74); a local-dev signing key is silently generated when
   Vault is absent; nothing stops startup on missing required config. (DEBT-A7/A30/A29)
5. **No permanent account id / one-identity-one-account** (ACC-2/ACC-3 — *medium-high*). `sub` is the login handle
   (`:582`); public `/register` (`:765-785`) lets one person mint unlimited accounts with no proofing. (**NEW
   DEBT-B30**) And login namespaces are modelled as tenants (realm == tenant id, `:620-628`; DEBT-B21).

**New debt opened:** DEBT-B28 (roleless→tenant-admin), DEBT-B29 (write-gate fail-open on empty IDENTITY_INTERNAL),
DEBT-B30 (no permanent id / unlimited self-register), DEBT-B31 (platform-addressed tokens, no consent ref),
DEBT-B32 (assurance off-vocabulary + no amr + boot-guard blind), DEBT-A77 (no account recovery). Existing debt
confirmed live: DEBT-B1, B13, B14, B21; A7, A26, A29, A30, A31, A33, A34, A35, A71. **Corrected:** the earlier
"/users CREATE drops roles" note is the *pre-fix* behaviour (DEBT-A73, now FIXED) — current code merges and
persists sent roles; the live risk is the roleless-default (DEBT-B28).

Hardening worth crediting (correctly implemented): directory endpoints now fail-closed behind the internal token
(DEBT-B6 resolved, `:656-658`); Argon2id/PBKDF2-at-OWASP-floor with rehash-on-login (`:176-234`); durable+shared
brute-force lockout keyed by `(account|ip)` with an alerted, `/healthz`-surfaced fail-open (`:318-486`, FND-12 §3
carve-out); recorded per-principal audience allow-list, deny-by-default (`:592-600`, ADR-0124); prod default-
password boot guard (`:252-278`).

---

## Per-rule findings

| rule | verdict | sev | evidence (identity.py unless noted) | debt |
|---|---|---|---|---|
| FND-1 identity carries no authority | **violated** | high | `:584` stamps `roles` into the JWT (downstream enforces off it, DEBT-B1); `:710-711` roleless create → platform.tenant-admin | DEBT-B1; B28 (NEW) |
| FND-9 fail-closed internal gates; no passwordless mint | **violated** | critical | passwordless mint of platform.steward/scheduler under `_PW_MODE=shadow` (`:72,76,499,816-823`); write gates `if INTERNAL and hdr!=INTERNAL` fail open on empty secret (`:691,724,744`; GET fixed `:657`) | DEBT-B14,A26,A30,A29; B29 (NEW) |
| FND-12 failed-auth logged; lockout | partial | medium | lockout store durable + alerted fail-open + /healthz (`:318-486`, §3 carve-out HELD); but a failed authentication emits no durable `(issuer,reason,source)` audit (only a counter increment `:807`) | DEBT-A9 |
| FND-15 external-issuer scoping (home issuer) | partial | medium | well-formed home token (sub/iss/aud), recorded per-principal audience allow-list (`:592-600`), cross-tenant mint guarded (`:147`); kernel JWKS only for mapped/HOME iss (authn.py:77-86). Gaps: kernel still trusts iss+role (DEBT-B1); prod-default issuer | DEBT-B1, A7 |
| FND-16 safe defaults | **violated** | high | prod-pointing `ISS`/`AUD`/`HOME_ISS` (`:31,33`; authn.py:74); `_PW_MODE` default shadow (`:499`); roleless→tenant-admin (`:710-711`); local-dev signing key when Vault absent (`:520-523`); no fail-loud on missing config | DEBT-A7,A30,A29,A5,A6; B28 |
| ACC-2 id ≠ handle ≠ binding; handle reserved | **violated** | medium | `sub=user://<tenant>/<username>` — username IS the id (`:582`); no handle/binding model; no rename reservation (uniqueness only at `/register` `:773-774`). Handle-not-a-credential HELD (`:805-808`) | DEBT-B30 (NEW) |
| ACC-3 binding + assurance; one-account | **violated** | high | uniform `assurance="A0"` on every login incl. password (`:36,585`); public `/register` mints unlimited accounts, no proofing (`:765-785`) | DEBT-B13,A34; B30,B32 (NEW) |
| ACC-4 login + recovery | partial | medium | strong login (Argon2id/PBKDF2, lockout, must-reset `:176-234,437-458,834-835`); NO self-service recovery; passwordless-by-default (`:499`) | DEBT-B14; A77 (NEW) |
| ACC-5 provider connections | n/a | info | not-identity: provider connection = service-federation/app-host (ADR-0067); no surface in identity | — |
| CLI-1 registered clients + scopes | n/a | info | not-identity: client registry = app-host/embed (ADR-0112, `platform.app_client`); identity registers users, not client apps | — |
| CLI-3 short-lived app-addressed token + consent ref | partial | high | short-lived HELD (1h, `:586`); app-addressed FAILED (`aud="airawatos"` platform-wide, `:33,582`); consent ref ABSENT; carries roles (DEBT-B1) | DEBT-A33,B1; B31 (NEW) |
| PLT-3 operator holds no governance role (+ realms) | n/a / **violated** | medium | PLT-3-operator-role is not an Identity surface (label note). Realms-as-tenants: realm == tenant id (`:620-628`; ensure_install.py:169-173) conflates login-namespace with organisation | DEBT-B21 |

### Cross-cutting (PLATFORM reviewer)
- **Assurance** (above, ACC-3) — identity `A0`, Keycloak static `A2`, neither computed from acr/amr, off the `AL0–AL3` vocabulary, Keycloak emits no `amr`. DEBT-B13/A34/A35 + B32.
- **Password mode** `_PW_MODE=shadow` default; EC2 doesn't set `enforce` → passwordless still mints in prod; boot guard blind to it. DEBT-A30/A31.
- **Passwordless service principals** — mitigated in the prod install path (`ensure_install.py:184-206` provisions Vault-backed random passwords) but the invariant lives in the installer, not the IdP; residual under demo-seed + shadow. DEBT-A26/B14.

## Conformance cases added
`run_identity_review_cases()` (internal): **ACC-3**, **ACC-2**, **CLI-3** as live XFAIL (reproduce the violations
from a real admin password-login token — assurance=`A0`/off-vocab; sub=handle; aud=platform-wide, no consent).
Recorded SKIP_BUILD (reason + proposed internal test) for FND-9, FND-16, ACC-4, ACC-5, CLI-1, PLT-3. Verified both
modes: internal 16 PASS / 7 XFAIL / 0 FAIL / 0 SKIP_CREDS; external 14 PASS / 2 XFAIL / 0 FAIL. Matrix regenerated
(ACC-2/ACC-3/CLI-3 now VIOLATED; the rest PLANNED(needs-build)).

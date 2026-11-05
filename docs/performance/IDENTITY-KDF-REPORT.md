# Identity password hashing — read-only review (Consolidation phase 4)

**Date:** 2026-11-05 · **Scope:** the reference IdP's password KDF, the stored hash format, whether login
caches/bypasses the KDF, and where failed-login counters live. **Report only — no code changed.** This follows
up the phase-4 perf finding that login's p95 (~24 ms) is far under its 400 ms budget, which pointed at a KDF
weaker than the budget assumed.

All line references are `platform-spec/reference/identity.py` at HEAD.

## What the code does

### Algorithm and parameters
```
_hash_password(pw, iters=200_000):            # L172
    salt = os.urandom(16)                      # 128-bit random salt, per password
    dk   = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iters)
    return f"pbkdf2_sha256${iters}${salt.hex()}${dk.hex()}"
```
- **KDF:** PBKDF2-HMAC-**SHA256** (Python stdlib `hashlib`).
- **Iterations:** **200,000**, baked as the default argument; no env override.
- **Salt:** 16 bytes from `os.urandom`, unique per password.
- **Derived key:** the PBKDF2 default output length for SHA256 (32 bytes).
- **Stored format:** `pbkdf2_sha256$<iters>$<salt_hex>$<hash_hex>` — the iteration count travels **with each
  hash**, so the work factor is per-record and can be raised without invalidating existing hashes (verify
  honours the stored `iters`, re-hash-on-login can upgrade them).

### Stored hashes
- `_PASSWORDS` (L158) maps `username → "pbkdf2_sha256$…"`; persisted to `IDENTITY_PASSWORDS_FILE`
  (`identity-passwords.json`) on the identity data volume via atomic temp-file replace (L194–202).
- Hashes are **durable** (survive restart). They are stored **separately** from the user directory
  (`USERS_FILE`), so a directory read never exposes a hash.
- There is a **production weak-password floor** (L208–223, #282/ADR-0124): at boot under
  `AIRAWAT_ENV=production` the IdP hash-tests every account against a known-weak list and refuses to start if
  any matches — a stale `localdev-admin-pw` / `admin` / `password` cannot ride a dev DB into production. This
  is a real, good guard; it is **orthogonal** to the KDF-strength question below.

### Does login cache or bypass the KDF?
**No.** `_check_password` (L178) re-derives with `pbkdf2_hmac` on **every** call and compares with
`hmac.compare_digest` (constant-time, L185). There is no verifier cache, no "skip hash if recently seen", no
fast path. Each `/login` with a password pays the full 200k-iteration PBKDF2 once. (Passwordless accounts —
users with no entry in `_PASSWORDS` — skip it entirely, by design: the password gate is opt-in per tenant.)

So the ~24 ms login p95 is **a real PBKDF2-200k verification**, fast because it is SHA256 (not memory-hard) on
a fast arm64 core — not a missing or cached hash. The perf finding was pointing at **work factor**, confirmed
here.

### Where do failed-login counters live?
**In memory, not durable.** `_FAILS` (L284) is a plain dict keyed by `(account-key, source-ip)` holding recent
failure timestamps; `_login_locked` (L293) counts failures inside `_LOGIN_LOCK_SECONDS` against
`_LOGIN_MAX_FAILS` (default 5). Consequences:
- **Lost on restart / crash** — a restart resets every lockout counter to zero.
- **Per-process** — with more than one IdP replica, an attacker's attempts spread across replicas are counted
  independently, multiplying the effective threshold (and a load balancer without sticky routing dilutes it
  further).
- Keyed partly by source IP, so a rotating-IP attacker is not throttled per-account across IPs.

## Comparison with current guidance

| Dimension | In code today | Guidance (OWASP 2024 / NIST 800-63B) | Gap |
|---|---|---|---|
| KDF family | PBKDF2-HMAC-SHA256 | Argon2id preferred; PBKDF2-SHA256 acceptable | acceptable family, not the strongest |
| Work factor | **200,000** iters | **PBKDF2-SHA256 ≥ 600,000** iters (OWASP) | **~3× low** |
| Memory hardness | none (PBKDF2) | Argon2id is memory-hard (GPU/ASIC-resistant) | PBKDF2 is GPU-parallelisable |
| Salt | 16 B random, per-record | ≥ 16 B unique | OK |
| Constant-time compare | `hmac.compare_digest` | required | OK |
| Per-record cost upgrade | yes (iters in hash) | recommended | OK — good |
| Failed-login throttle | in-memory, per-process | durable + shared across replicas | **not durable** |

**Net:** the format, salting, constant-time compare, and per-record upgradability are sound. Two gaps:
1. **Work factor** — 200k PBKDF2-SHA256 is below the ~600k floor and PBKDF2 is not memory-hard.
2. **Lockout durability** — in-memory counters don't survive restart and don't aggregate across replicas, so
   the brute-force throttle is weaker than it looks (and weakens further as the read tier scales, ADR-0105).

## Recommendations (NOT applied — report only)

1. **Raise the work factor.** Cheapest change: bump the PBKDF2 iterations to **≥ 600,000** (env-overridable so
   it can track hardware). Because `iters` is stored per hash, existing hashes keep verifying and upgrade on
   next successful login (re-hash-on-verify). Measure the new login p95 against the 400 ms budget — 600k is
   ~3× the current ~24 ms, so ≈ 70–90 ms p95 here: comfortably inside budget, far better brute-force cost.
2. **Prefer Argon2id** for new hashes if a vetted dependency is acceptable (the stored-format prefix already
   namespaces the algorithm: `pbkdf2_sha256$…` vs an `argon2id$…` record, so both can coexist and migrate
   lazily). Memory-hardness is the real GPU/ASIC defence PBKDF2 cannot give.
3. **Make failed-login counters durable and shared** — back `_FAILS` with the registry (or a shared store) so
   lockouts survive restart and aggregate across replicas; keep the in-memory dict as a fast cache in front.
   Pairs with a per-account (not only per-IP) dimension so IP rotation does not reset the throttle.
4. Keep the production weak-password floor (#282) — it is correct and complements, not replaces, the above.

These are **proposed**; per the slice, no identity code is changed here. A follow-up slice can apply (1) (a
one-line default + env knob + re-hash-on-verify) under the standing rule (rebuild + live check + conformance).

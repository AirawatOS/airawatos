# AirawatOS conformance suite (Phase 3, first suite)

Black-box tests of the v0.1 specs (FOUNDATIONS / REGISTRY / DECISION / NETWORK / ACCOUNT / CLIENT) against a
running local-dev stack. HTTP only — no service code is imported or inspected. Full plan + classification:
`Airawat/docs/conformance/PLAN.md`.

## Run
```
python3 conformance/run.py
```
Defaults to `http://127.0.0.1:8080` (the local-dev edge nginx). Override with `AOS_BASE`.
Requires the local-dev stack up (`deploy/local-dev/`).

## Result kinds
- **PASS** — a TESTABLE-NOW case behaved as the spec requires.
- **XFAIL** — an EXPECTED-FAIL case reproduced a *known live violation* (cites the debt item). Green today.
- **XPASS** — an EXPECTED-FAIL case did **not** reproduce → the violation looks **fixed**. Printed
  prominently; update the spec status + debt register when you see one.
- **FAIL** — a TESTABLE-NOW case contradicts the spec. **Fails the run** (exit 1).
- **SKIP_CREDS** — needs a real test-user session/bearer; skipped unless credentials are supplied.
- **SKIP_BUILD** — feature/endpoint not built or not black-box reachable at `:8080`.

The suite is green (exit 0) when there is no FAIL. A fixed violation surfaces as an XPASS.

## Supplying credentials (enables the NEEDS-CREDENTIALS cases)
The authenticated cases need the test users' passwords. Provide them **without committing secrets** via
`conformance/.creds.json` (gitignored) or the `AOS_TEST_USERS` env var. Each value is either `"password"`
(default realm = `AOS_REALM`) or `{"password":.., "tenant":..}` — some test users live in a different tenant:

```json
{
  "admin":      {"password": "<admin-pw>",      "tenant": "localdev-network"},
  "memsteward": {"password": "<memsteward-pw>", "tenant": "localdev-network"},
  "faker":      {"password": "<faker-pw>",      "tenant": "localdev-network"},
  "xadmin":     {"password": "<xadmin-pw>",     "tenant": "localdev"},
  "outsider":   {"password": "<outsider-pw>",   "tenant": "localdev"}
}
```
Passwords live in local Vault at `secret/data/localdev-network/test-users/<name>`. Without credentials the
no-credential cases still run (anonymous, forged-token, unknown-schema, handle-not-a-credential) and pass.

Optional env for the B15 populated leak-check: `AOS_TEST_COMPONENT=<published component id>` — otherwise B15
SKIP_BUILDs when the local-dev component catalogue is empty (it auto-discovers a cid from `/bridge/components`
if one exists).

## Internal runner (step 3) — in-cluster endpoints
The reference services (identity, filestore, scheduler, model-gateway, secrets, notify, automation) are not
published at the edge, so the external mode cannot reach them. Run the **same suite inside a container on the
local-dev docker network** to cover them:
```
docker run --rm --network airawatos-localdev_default -e AOS_MODE=internal \
  -v "$PWD/conformance:/suite:ro" python:3.11-slim python -I /suite/run.py
```
Internal targets: `kernel:8080 network:8090 identity:8093 notify:8094 filestore:8095 automation:8098
event-relay:8101 secrets:8102 scheduler:8103 model-gateway:8104`. Internal cases: F10/B5 (reference
endpoints accept tokenless privileged calls), F9/B4 (fail-open internal-token gates — only observable when
the gate env is UNSET; SKIP_BUILD where the gate is active in local-dev), B6 (identity `/users` directory
disclosure), and the internal parity of the A1 anonymous-read violation.

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
The authenticated-positive cases need the test users' passwords (`admin`, `memsteward`, `xadmin`,
`outsider`, `faker` in `localdev-network`). Provide them **without committing secrets**:
```
export AOS_TEST_USERS='{"admin":"...","outsider":"...","xadmin":"...","memsteward":"...","faker":"..."}'
python3 conformance/run.py
```
or create `conformance/.creds.json` (gitignored) with the same JSON. The passwords live in local Vault at
`secret/data/localdev-network/test-users/<name>`.

Without credentials the suite still runs the no-credential cases (anonymous, forged-token, unauth-endpoint,
run_token-leak, handle-not-a-credential, deterministic-resolution) and passes on those.

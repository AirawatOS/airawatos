# Operational validation — Trust-plane dual-run on a current-source deployment (before human gate #2)

**Status:** reviewed & green-lit as an **operational validation slice only**. **Do NOT flip authorization.**
This runbook is executed on EC2 *after* two preconditions clear; it is written and reviewed now so the
live run is turnkey. The code-review gate is effectively passed; **operational gate #2 is still open**.

The question this slice answers is no longer "does the code work?" (proven: all four divergence classes,
config-defect-vs-intentional distinction, run-A/run-B separation, READY/NOT-READY recommendation) but:

> **Does the new authorization model behave as intended on a real current-source deployment under realistic traffic?**

---

## Preconditions (both must be green before starting)

1. **EC2 platform Postgres healthy.** As of 2026-11-01 `airawat-postgres` is stuck in crash recovery
   ("Consistent recovery state has not been yet reached"), load avg ~14.5, rejecting all connections.
   This is an unrelated infra incident (NOT our code / not a deploy). It must be recovered and
   `pg_isready` green before anything below. *(This is the "wait and monitor" item.)*
2. **Network service upgraded from the stale build → current source** (task #277). The live build is
   pre-ADR-0116 (`/v1/networks` 404s); the three shadow sites + governance endpoints only exist in
   current source. Deploy current `network/` + `app_host`/`api.py` (with the trust wiring already
   committed on `feat/trust-plane-phase1`).

No participant data is migrated and no enforcement is flipped in this slice.

---

## Flow

```
Upgrade stale EC2 network → run current-source Network → connect real Kernel + Postgres
      ↓
TRUST_PLANE_ENABLED=true ; TRUST_DUALRUN_SINK=<durable sink> ; TRUST_DUALRUN_RUN_ID=run-A-...
      ↓
configure test/dev capability catalog  (explicit, governed)
author explicit test/dev grants
      ↓
exercise /services/apply  /services/offer  /services/decide   (realistic test/dev traffic)
      ↓
collect JSONL evidence → run dualrun_report.py → STOP → HUMAN GATE #2
```

## Env (network service container)

```
TRUST_PLANE_ENABLED=true
TRUST_KERNEL_URL=http://airawat-kernel:<port>          # the real kernel registry
TRUST_REGISTRY_TOKEN=<kernel platform-service JWT>     # stays in the adapter; never logged
TRUST_AUDIT_HMAC_KEY=<hex secret, Vault>               # per-network keyed audit
TRUST_AUTHORITY_TENANT=airawat
TRUST_DUALRUN_RUN_ID=run-A-before-corrections          # bump to run-B after any grant fix
TRUST_DUALRUN_SINK=/data/trust/dualrun-evidence.jsonl  # durable, on a mounted volume
```

The service **boots unchanged** if `TRUST_PLANE_ENABLED` is unset — so enabling is reversible by
removing the env and restarting.

## Steps (all against the deployment; a TEST/DEV network only)

1. **Seed the catalog (governed, explicit).** Mint `service.provide:<iface>` / `service.call:<iface>`
   v1 for the handful of test/dev interfaces actually exercised — via `POST /v1/governance/capabilities`
   (or `seed_capabilities()` with a capability.steward token). Do **not** auto-seed every interface.
2. **Author explicit grants** for the test/dev participants via `POST /v1/governance/grants`:
   - a member with `service.call:<iface>` (→ MATCH_ALLOW at /apply),
   - the service provider with `service.provide:<iface>` (→ MATCH_ALLOW at /offer, /decide),
   - a non-provider member with `service.provide:<iface>` (→ LEGACY_DENY_GRANT_ALLOW at /decide),
   - deliberately leave one member ungranted (→ LEGACY_ALLOW_GRANT_DENY at /apply = a config defect).
3. **Exercise realistic traffic** against the three shadow sites with the test/dev participants'
   tokens: `/v1/network/services/apply`, `/v1/network/services` (offer), `/v1/network/services/decide`.
   Each call is normal; the shadow comparator records a row to the sink (log-only, never gates).
4. **Collect evidence & report** (read-only):
   ```
   # copy the sink off the box, then:
   python3 network/trust/migration/dualrun_report.py \
       --sink dualrun-evidence.jsonl --run run-A-before-corrections \
       --site /v1/network/services/apply --site /v1/network/services/offer --site /v1/network/services/decide \
       --unobserved "cross-tenant data-requests" --unobserved "credential issue/verify" \
       --unobserved "event delivery (Event Plane — not built)"
   ```
5. **If run-A shows configuration defects:** correct the grants, bump `TRUST_DUALRUN_RUN_ID` to
   `run-B-after-corrections`, re-exercise, re-report. Never mix run-A and run-B evidence.
6. **STOP.** Hand the run-B report to the human gate. Do not flip `AUTHZ_MODE`.

## Gate #2 criteria (the human decision)

| Criterion | Required |
|---|---|
| Representative real observations | yes |
| Observed sites | apply + offer + decide |
| Unexplained divergences | **0** |
| Configuration defects (latest run) | **0** |
| Intentional policy differences | **documented** (disposition = accept_new_behaviour + note) |
| Evidence from the latest run-id | clean |
| Material operational failures in the shadow path | none |

The decision: **are the remaining differences deliberate improvements over legacy behaviour?** Only if
yes do we approve the next phase — and even then only the staged rollout:

```
type  →  dual  →  grant
```

## Guardrails (unchanged)

- Shadow path is **log-only**; the legacy membership/provider gates stay authoritative throughout.
- **No production participants** — a test/dev network only.
- **No enforcement flip** in this slice.
- The kernel platform-service token lives only in the adapter; never returned or logged.
- Known structural gap recorded in `unobserved_flows`: at `/apply`, `LEGACY_DENY_GRANT_ALLOW` is
  unreachable (membership gates both) — `/decide` is the site that exercises that class.

## Artifacts referenced

- Wiring + comparator: `network/trust_wiring.py`, `network/trust/dual_run.py`, `observation_sink.py`.
- Catalog seeding: `network/trust/catalog_seed.py`. Report: `network/trust/divergence_report.py`.
- CLI: `network/trust/migration/dualrun_report.py`. Local proof: `devrun_dualrun.py` +
  `SAMPLE-divergence-run-A.md` (NOT READY) / `-run-B.md` (READY).

# Sample-component pipeline proof — findings (ADR-0124 item 1 verification, local-dev)

Goal: take two harmless samples — `hello-dev` (driver, writes+reads `demo.ping`) and `hello-engine` (engine,
reads `demo.ping`) — through the **real** publish → certify → install → run pipeline on the bedrock local-dev
stack, and prove Run-now, a scheduled run, a dev-run, a real upload+download, and B15 with a real installed
component. Each step was driven live; results below. Dev profile only; EC2 untouched; `FILESTORE_REQUIRE_TOKEN`
left in shadow.

## What PASSED

| Proof | Result |
|---|---|
| **Real upload** (filestore `POST /files`, `svc:filestore` token, shadow gate) | ✅ 200 — `sha2-256:013a…5b0f`, 1372 bytes stored |
| **Real download** (filestore `GET /files/<id>`, `svc:filestore`) | ✅ 200 — bytes round-trip, `match=True` |
| **dev-run reaches the scheduler through the ADR-0124 lock** | ✅ the app-host→scheduler `/run` carried the `svc:scheduler` bearer and was **accepted** (reached the dev-token mint stage — the gate passed) |
| **B15** (kernel `GET /v1/components`, admin) | ✅ 200, admin-gated, `installed_count=0`, **no `run_token` leaked** |

## What was BLOCKED — gaps (each a real prerequisite the bedrock stack lacks)

Driven in order; the first failure in each path is the finding.

1. **Deliver** (`/bridge/component-publish`, dev bearer) → HTTP 200 but `file_id=None`. The filestore blob write
   succeeded; `_store_bundle` then got **403 writing the `platform.component_asset` record to the kernel
   registry** — `component-publisher` holds no registry-write grant for `platform.component_asset` under the
   `airawatdeveloper` steward on a bedrock stack. The id is swallowed, so delivery silently reports nothing
   stored. *(Gap D1: publisher lacks the component_asset registry grant; also `_store_bundle` should surface
   the 403 rather than return None.)*

2. **Certify** (`/v1/certify`, `component-publisher` on_behalf devtester) → **422 conformance withheld**, two
   failed checks:
   - `steward-is-publisher` — "airawatdeveloper vs localdev-network". The conformance suite requires the
     component's steward prefix to equal the **publisher's tenant**, but no principal whose tenant is
     `airawatdeveloper` exists (component-publisher = localdev-network; devtester = localdev-developer).
     `_require_publisher` *allows* `component.publisher` to publish cross-tenant on_behalf, but the conformance
     check independently *rejects* it. *(Gap D2: the on-behalf cross-tenant publish path and the
     steward==publisher conformance check contradict each other; a bedrock stack has no `airawatdeveloper`-tenant
     publisher.)*
   - `governed-vocabulary` — `demo.ping` is not in the shared governed catalog. A production publisher sees only
     the shared catalog, so a new schema must be governed through the standards body first. *(Gap D3:
     ungoverned vocabulary → not certifiable.)*
   - Also: certify **500'd** on a `files` payload shaped as a list; it expects a `{path: sha256}` dict. *(Gap D4:
     certify input not validated → 500 instead of 422.)*

3. **Store-publish** (`/v1/store/publish`) → 400 "must be certified first" (blocked by #2); independently,
   **a development-tenant publisher is refused 403** (ADR-0106 S3 dev↔prod boundary). *(Gap D5: dev-tenant
   components can never be listed in the store → can never be installed via the store-resolve path.)*

4. **Install** (kernel `/v1/components/install`) → 404 "not found in the store" (blocked by #3). Install
   resolves ONLY from the store and verifies the cert — there is no dev/sandbox direct-install path.

5. **dev-run** (`hello-dev`, `dev:true`, source materialised from the filestore blob) → the scheduler accepted
   the gated call, materialised the source, then the **dev-token mint failed 403**: "'localdev-developer' is
   not owned by a registered Developer participant". *(Gap D6: a dev tenant must be owned by a registered
   `participant/developer` for the kernel to mint a dev-token; bedrock has none.)*

6. **Run-now / scheduled run** — both require an **installed** component (blocked by #1–#4). Not reachable until
   the above are resolved. B15 confirms `installed_count=0`.

## Net

Upload/download and the scheduler lock itself are proven. Running a **brand-new** component end-to-end is gated
on a content/governance bootstrap the bedrock stack does not have, in this order:
(a) register a `participant/developer` owning the dev tenant (D6); (b) govern the component's vocabulary
`demo.ping` in the shared catalog (D3); (c) a publisher principal whose tenant == the component steward, or
relax the steward==publisher conformance rule for the on-behalf lane (D2); (d) grant the publisher the
`platform.component_asset` registry write (D1); (e) for Run-now/scheduled, the component must be store-published
from a **non-dev** tenant (D5) and installed. None of these are code bugs in the gate work — they are the
governance/promotion prerequisites the real pipeline enforces, surfaced by trying it on bedrock.

Sample sources committed: `components/drivers/hello-dev` (pre-existing), `components/engines/hello-engine` (new,
this slice).

# Filestore caller inventory (ADR-0124 item 1, service 2/5)

Complete `file:line` inventory of every caller of the per-tenant content-addressed **filestore** (`filestore:8095`),
for the audience-ingress gate (`FILESTORE_REQUIRE_TOKEN`, accept-set `svc:filestore`). Endpoints:
`POST /files` (write), `GET`/`HEAD /files/<id>` (read), `GET /healthz` (open — not gated).

> Reads are gated too (3e): the store is **not public**. For a public page's assets the **App Host** fetches them
> here with its **own** `svc:filestore` token and proxies the bytes — anonymous visitors never reach the store.

This is the per-tenant filestore. The **network** filestore (`network/api.py` `/v1/files`, ADR-0085) is a
separate service with its own grant gate (S1 public read / S2 accept) and is out of scope for this gate;
app-host's `NETWORK_FILESTORE_URL` writes target that one.

## Callers — writes (`POST /files`)

| # | file:line | context | wired this slice? |
|---|-----------|---------|-------------------|
| W1 | `platform-spec/reference/hostcore.py:247` | asset-url-fetch → store blob | ✅ `fs_headers` |
| W2 | `platform-spec/reference/hostcore.py:541` | `_store_bundle` app/source bundle | ✅ `fs_headers` |
| W3 | `platform-spec/reference/app_host.py:3628` | stage DRAFT source (dev-run) | ⬜ flip-turn |
| W4 | `platform-spec/reference/app_host.py:7289` | upload bridge (file-push) | ⬜ flip-turn |
| W5 | `platform-spec/reference/app_host.py:7312` | upload bridge (chunk) | ⬜ flip-turn |
| W6 | `platform-spec/reference/app_host.py:7373` | upload (streamed fh) | ⬜ flip-turn |
| W7 | `platform-spec/reference/app_host.py:7472` | upload (streamed fh) | ⬜ flip-turn |
| W8 | `platform-spec/reference/app_host.py:8376` | component_asset write | ⬜ flip-turn |
| W9 | `kernel/api/app.py:602` | embed/receipt store | ⬜ flip-turn (kernel) |
| W10 | `kernel/api/app.py:1643` | archive-tiering store | ⬜ flip-turn (kernel) |

## Callers — reads (`GET /files/<id>`)

| # | file:line | context | wired this slice? |
|---|-----------|---------|-------------------|
| R1 | `platform-spec/reference/scheduler.py:408` | dev-source materialise | ✅ `svc:filestore` header (shadow-tolerant) |
| R2 | `platform-spec/reference/app_host.py:310` | app-bundle rehydrate | ⬜ flip-turn |
| R3 | `platform-spec/reference/app_host.py:3605` | draft source read | ⬜ flip-turn |
| R4 | `platform-spec/reference/app_host.py:3760` | S-materialise component source | ⬜ flip-turn |
| R5 | `platform-spec/reference/app_host.py:7195` | download bridge | ⬜ flip-turn |
| R6 | `platform-spec/reference/app_host.py:7526` | file read | ⬜ flip-turn |
| R7 | `platform-spec/reference/app_host.py:7672` | VFS node bytes | ⬜ flip-turn |
| R8 | `platform-spec/reference/app_host.py:7686` | VFS node stream | ⬜ flip-turn |
| R9 | `platform-spec/reference/app_host.py:8375` | asset read | ⬜ flip-turn |
| R10 | `platform-spec/reference/app_host.py:8775` | cross-tenant asset read | ⬜ flip-turn |
| R11 | `platform-spec/reference/app_host.py:10221` | camera/media frame (public SSR path — 3e) | ⬜ flip-turn |
| R12 | `kernel/api/app.py:1660` | embed/archive read | ⬜ flip-turn (kernel) |
| R13 | `components/_common/launcher.py:139` | component source fetch-and-verify (runs in the component-host subprocess / runtime-manager, NOT a Vault-backed service) | ⬜ flip-turn — hardest: needs a token in the runtime context |

## Gate + wiring landed this slice (shadow, flag OFF)

- `filestore.py`: `svc_authz.ingress_gate` on write + read behind `FILESTORE_REQUIRE_TOKEN` (default OFF). Verified
  live: `svc:filestore`→201/200 round-trip; tokenless→201 (shadow); **wrong-audience→403 even in shadow**.
- `hostcore.filestore_token()` / `fs_headers()`; app-host principal granted the `svc:filestore` audience
  (bootstrap phase 10). WRITE callers W1,W2 + READ caller R1 wired.

## Remaining before flip (its own slice — debt DEBT-A72)

Route **all app_host read/write sites (W3–W8, R2–R11) + kernel (W9,W10,R12) + the launcher (R13)** through a
token-bearing helper. The app-host reads feed the **live OS browser UI** (SSR, bundles, media), so a single
missed site breaks the browser on flip — hence a dedicated, fully-wired pass + a real upload/download
verification with sample components, then `FILESTORE_REQUIRE_TOKEN=1` + conformance anon→403. The launcher read
(R13) is the architectural crux: it runs in the component-runtime context, which has no Vault-backed service
identity today — the source fetch must carry a token minted at placement time (or move behind the broker).

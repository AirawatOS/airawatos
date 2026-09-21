# Services & APIs

*The platform is a handful of small services, each with one job. Here's what each one is, and where its API lives.*

AirawatOS isn't one big program — it's a set of independent services that each do one thing and trust each other only through verified tokens and signatures. Two of them are the **governed APIs** you build against; the rest are supporting machinery. This page is the map, generated from the running services.

## The two governed APIs

Almost everything a developer cares about is one of these two.

- **Kernel** — `kernel:8080`. The **data plane**: the bitemporal registry (read / write / history / retract) and the confined **broker** your components' code goes through. This is where governed nouns live and where every read and write is authorized. Your component never calls it directly — it goes through the broker, which enforces the component's declared capabilities. *(FastAPI — live spec at `/openapi.json`, ~52 operations.)*
- **Network** — `network:8090`. The **governance authority**: the catalogs of governed **nouns (schemas), verbs (interfaces), roles**, plus certificates, grants, the store, solutions, and the federation directory. This is where you *propose* a schema/verb/role and a steward *approves* it. *(FastAPI — live spec at `/openapi.json`, ~96 operations.)*

Because both are FastAPI, each serves its own **live OpenAPI** at `/openapi.json` — the spec is generated from the code, so it never drifts. The committed copies live in `platform-spec/spec/openapi/`.

## The supporting services

Small, single-purpose, mostly called by the kernel or the host — not by your component directly. (These are lightweight HTTP services, so their specs in `platform-spec/spec/openapi/` are derived from source rather than a live `/openapi.json`.)

| Service | Address | What it does |
|---|---|---|
| **Identity** | `identity:8093` | The IdP. Per-tenant realms; issues the verified tokens every other service trusts (`/jwks` is the root of that trust). |
| **File Store** | `filestore:8095` | Content-addressed blobs — write-once, immutable, dedup by hash. Backs file uploads and component delivery. |
| **Secrets** | `secrets:8102` | Per-tenant, per-component credentials (Vault-backed). Injected at use; components never see raw values. |
| **Scheduler** | `scheduler:8103` | The clock-driven trigger — fires `platform.schedule` entries on time (one of three ways work starts). |
| **Workflow** | `workflow:8097` | Turns a case's workflow declaration into tasks routed to the Inbox (the lifecycle spine). |
| **Decision** | `decision:8096` | The single writer that turns a signed decision into governed outcomes (execution-engine seam). |
| **Automation** | `automation:8098` | The event dispatcher — the kernel emits events here; it fans them to subscribers. |
| **Runtime Manager** | `runtime-manager:8105` | The trusted runtime invoker — mints run-tokens and runs a confined component. |
| **Model Gateway** | `model-gateway:8104` | The confined path to an AI model provider; the kernel routes completions through it (keys stay in Vault). |

## Everything else

- **App Host** (`:8099`) — the browser-facing host that serves apps and mediates every app call through `/bridge/*` (see [Zero-Trust](/developer/deep-dives/zero-trust/)). It's the door apps use; it isn't a governed data API, so it has no OpenAPI — its surface is the `/bridge/*` bridges.
- **Infrastructure** — Postgres (the registry's store), Vault (secret storage), Redis, and an nginx/edge proxy. Platform plumbing, not application APIs.

## How this maps to the layers

If [The Airawat Stack](/developer/get-started/the-stack/) is the *what* (the layers and domains), this is the *how it runs* — the processes those layers are made of. The **kernel + network** are the trusted core; the supporting services are the platform services around it; the **app host** is where distribution and apps meet the browser.

## Browse it — the API Explorer

**→ [Open the API Explorer](/developer/api/)** — the actual API, browsable in the docs. Pick a service, expand any endpoint to see its parameters, request/response schemas, and examples. For the **Kernel** and **Network** it loads the *live* spec (always current) and lets you **Try it out** against the real gateway; the internal services show their source-derived spec.

## Using the specs

- **Live, always-current:** the Kernel and Network are publicly routed and serve their spec at `https://airos.airawat.org/kernel/openapi.json` and `.../network/openapi.json` — generated from the code, so they never drift.
- **Committed copies:** `platform-spec/spec/openapi/*.json` — one per service (the two FastAPI specs captured verbatim; the supporting services source-derived). Point Postman, code generators, or CI at these.

> The rule of thumb: build against the **kernel** (through the broker) and the **network** (governance). The rest of the services are the platform doing its job so you don't have to.

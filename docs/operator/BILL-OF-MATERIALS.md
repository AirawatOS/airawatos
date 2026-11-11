# AirawatOS — Bill of Materials

What a production deployment is made of, from the repository as it stands. The canonical compose is
`deploy/local-dev/docker-compose.dev.yml` (the from-source stack); the **first production deployment is a fresh
install of this source** (see `deploy/RELEASE-PLAN.md` and `docs/reviews/REVIEW-METHOD.md` — the EC2 box is a
development environment). Network topology, doors and the per-service Vault policies are specified in
[ARCHITECTURE-FLOWS-v0.1](../specs/ARCHITECTURE-FLOWS-v0.1.md); the remediation sequence is
[FIX-PLAN](../consolidation/FIX-PLAN.md). Figures below are measured on the running local-dev stack.

Images are pinned by tag in the compose; the sha256 **digests** below are what those tags resolve to today —
production should deploy by digest. The reference/kernel/network images are first-party (built from
`platform-spec/`, `kernel/`, `network/`); postgres/vault/nginx are upstream.

## 1. Containers (production compose path)

Build/runtime identity:

| Image (tag) | Digest (sha256, abbreviated) | Base OS | Runtime |
|---|---|---|---|
| `manishsv/airawatos-reference:dev-hard11` | `bb5d48ba2bdf…` | Debian GNU/Linux 13 (trixie) | Python 3.11.18 |
| `manishsv/airawatos-kernel:dev-hard5` | `3f4d68f0db1f…` | Debian GNU/Linux 13 (trixie) | Python 3.11.18 |
| `manishsv/airawatos-network:dev-a75` | `f77d4ba372bd…` | Debian GNU/Linux 13 (trixie) | Python 3.11.18 |
| `postgres:16-alpine` | `0cefaabd882e…` | Alpine Linux 3.24 | PostgreSQL 16 |
| `hashicorp/vault:1.15` | `0450896c43b1…` | Alpine Linux 3.18 | Vault 1.15 (Go) |
| `nginx:alpine` | `785835ea65db…` | Alpine Linux 3.24 | nginx |

Per-container deployment facts (image shown by its service; **ARC nets** per ARCHITECTURE-FLOWS §d/§g; ports are
**internal-only** unless marked *published*; idle RSS from `docker stats`):

| Container | Image | ARC network(s) | Port | Volume | Vault secrets (by path) | Idle RSS |
|---|---|---|---|---|---|---|
| nginx (edge) | nginx:alpine | aos-edge | **published 127.0.0.1:8080→80** | — (binds `nginx.conf`) | none | ~47 MiB |
| app-host | reference | aos-edge, aos-svc, aos-data-secrets | 8099 | `localdev_appbundles` | `localdev-operator/*`, `localdev-network/component-publisher/*`, `localdev-developer/*` (svc-app-host) | ~49 MiB |
| network | network | aos-edge, aos-svc, aos-data-facts, aos-data-secrets | 8090 | `localdev_netfiles` | `network-app` pw; `localdev-network/trust-{reader,writer,plane}/*`; transit (svc-network) | ~46 MiB |
| kernel | kernel | aos-svc, aos-data-facts, aos-data-secrets, aos-component | 8080 | — (DB-backed) | `localdev/kernel-app/*` pw; transit (svc-kernel) | ~44 MiB |
| identity | reference | aos-svc, aos-data-facts, aos-data-secrets | 8093 | `localdev_identity` | `localdev/identity-lockout/*` pw; transit (svc-identity) | ~18 MiB |
| secrets | reference | aos-svc, aos-data-secrets | 8102 | — | `secret/data/*` (KV broker — svc-secrets, widened) | ~16 MiB |
| model-gateway | reference | aos-svc, aos-data-secrets | 8104 | — | `secret/data/*` (provider keys — svc-model-gateway, widened) | ~14 MiB |
| filestore | reference | aos-svc | 8095 | `localdev_filestore` | none | ~15 MiB |
| notify | reference | aos-svc | 8094 | — | none | ~13 MiB |
| workflow | reference | aos-svc | 8097 | — | none | ~15 MiB |
| decision | reference | aos-svc | 8096 | — | none | ~14 MiB |
| automation | reference | aos-svc, aos-data-secrets | 8098 | — | `localdev-operator/scheduler/*` pw (svc-scheduler) | ~14 MiB |
| event-relay | reference | aos-svc, aos-data-secrets | 8101 | — | `localdev-operator/scheduler/*` pw (svc-scheduler) | ~13 MiB |
| scheduler | reference | aos-svc, aos-data-secrets | 8103 | — | `localdev-operator/scheduler/*` pw (svc-scheduler) | ~17 MiB |
| postgres | postgres:16-alpine | aos-data-facts | 5432 | `localdev_pg` | — (holds DB roles `kernel_app`/`network_app`/`identity_lockout`/`migrator`) | ~110 MiB |
| vault | hashicorp/vault:1.15 | aos-data-secrets | 8200 | `localdev_vault` | — (holds everything; root in `/vault/data/init.json`) | ~63 MiB |

Notes: every service authenticates to Vault with **its own AppRole** (role-id/secret-id in a per-service
`env_file`; login in `prod-guard.sh`); there is **no shared root token on any service** (DEBT-B58, slice-1b).
Only nginx publishes a host port; everything else is reachable only on its ARC network(s). Idle total RSS across
the 16 containers ≈ **0.5 GiB**; CPU at idle is <0.5 % per container.

## 2. Host requirements

| Item | Requirement | Source / measured |
|---|---|---|
| OS | Linux (any modern distro with a current kernel) | upstream + Debian/Alpine base images |
| Architecture | **amd64** for production (EC2). Local-dev is proven on arm64 (Apple Silicon) too — first-party images must be built/pushed for the target arch | measured: local-dev host arm64 |
| Docker Engine | ≥ 24; tested on **29.6.2** | measured |
| Docker Compose | v2; tested on **5.3.1** | measured |
| vCPU | **≥ 2** (installer pre-flight fails below) | `deploy/installer/install.sh` pre-flight |
| Memory | **8 GiB** recommended. Idle footprint ≈ 0.5 GiB; headroom for Postgres working set + LLM/ingestion bursts | measured (local-dev host = 7.75 GiB) |
| Disk | **≥ 100 GiB** on an encrypted volume, with **log rotation**. First-party images are several GiB; the `kernel` Postgres DB for the current ~1M-row bitemporal registry + indexes is a few GiB and grows with versions/events; filestore blobs + app-bundles are unbounded. The 2026-11-01 EC2 incident filled a 100 GiB root (85 G docker volumes + 14 G IDE caches) — size the data volume generously and rotate logs | `deploy/installer/install.sh` pre-flight (≥10 GiB floor) + EC2 disk-full incident |

**Registry sizing (~1M rows):** the fact store is a single bitemporal registry in Postgres (versioned rows). A
million rows with JSONB + the live-schema index is on the order of a few GiB; plan Postgres `shared_buffers` and
the data volume with 3–5× headroom for version growth and the `platform.event`/audit tables (whose physical
split-out is a separate backlog item, not in this BOM).

## 3. AWS services — required vs optional

Each linked to the FIX-PLAN / RELEASE-PLAN item it serves.

| AWS service | Need | Serves |
|---|---|---|
| **EC2** (compute host) | **Required** | RELEASE-PLAN — first prod deploy is a fresh install on an EC2-class host |
| **EBS, encryption at rest** | **Required** | ARC-7 (secrets/facts at rest) + installer pre-flight disk-encryption check; FIX-PLAN §0 (credential/secret handling) |
| **EBS snapshots** | Recommended | FIX-PLAN L1 slice-1b step 6 — restore runbook / backup |
| **Security Group** | **Required** | ARC-5 — the internet reaches only the edge (`:443`/`:80`); SG is the perimeter (the box must NOT use host iptables — see the EC2 no-iptables incident) |
| **TLS** (ACM cert at the edge, or on nginx) | **Required for prod** | DEBT-B45 — the session cookie needs `Secure`, which requires TLS; the edge terminates it (local-dev is plain http on 127.0.0.1) |
| **KMS auto-unseal** | Recommended | Vault unseal — replaces the demo single-unseal-key-on-the-data-volume (`vault/entrypoint.sh`); §5 open decision |
| **IAM instance role** (for Vault/host) | Recommended | enables KMS auto-unseal + S3 backups without static creds; supports slice-1b "root used only during install" posture |
| **S3** (backups) | Recommended | FIX-PLAN slice-1b step 6 — Vault + Postgres backup/restore |
| **SSM Session Manager** | Optional | ops access without opening SSH / extra SG ports (keeps ARC-5 perimeter tight) |
| **CloudWatch** (logs + alarms) | Recommended | FIX-PLAN "before first production" — runtime decision records + alerting (auth-failure / denial-spike / off-map-flow) |
| **Route 53** (DNS) | Optional | public hostname for the edge; any DNS works |

## 4. External providers

What each service calls out to, and whether the platform **starts** without it. **Only Postgres and Vault are
hard dependencies** — every external provider below is optional and degrades gracefully; the platform boots and
serves without any of them.

| Provider | Used by | Starts without it? | Behaviour when absent |
|---|---|---|---|
| **LLM** (model provider API) | model-gateway `/complete`,`/embed` (key from Vault) | **Yes** | AI features (assist drawer, converse, embeddings) fail/omit; core platform unaffected |
| **Email / SMTP** (per-tenant) | join email-verify / mail relay (SMTP creds in Vault, per tenant) | **Yes** | email verification + outbound mail degrade; configured per tenant |
| **Telegram** | app-host (`TELEGRAM_BOT_TOKEN`, empty = disabled) | **Yes** | the Telegram webhook/bot front door is off |
| **Transcription (Bodhan STT)** | model-gateway/app-host `/transcribe` (`BODHAN_TRANSCRIBE_URL` unset = disabled) | **Yes** | dictation returns 503; typing unaffected |
| **SMS** | *(no SMS provider integrated in the compose)* | **Yes** | n/a — not wired; notifications use the in-platform `platform.inbox_item` |
| **Payment** | service-gateway fee/consent (ADR-0067 S5) — *no payment processor container* | **Yes** | fee-quote/consent flow exists; no live processor wired |
| **Data sources** (GEE, Open-Meteo, CPCB, OSM, MoSPI eSankhyiki, …) | per-tenant ingestion drivers via the broker (keys in Vault) | **Yes** | city-scan / domain data not ingested until a tenant configures the driver + key |

## 5. Open decisions

1. **Single-host Compose vs ECS/EKS.** Today: single-host Docker Compose (`docker-compose.dev.yml`) with the five
   ARC networks (edge/svc/data-facts/data-secrets/component) as docker networks. Moving to ECS/EKS means mapping
   the ARC boundaries to task/pod networking + security groups (or a mesh), adapting the per-service Vault AppRole
   login (sidecar/agent), and replacing the compose `env_file` secret-id delivery. **Open:** stay single-host for
   the first production (simplest, matches the fresh-install model) vs orchestrate for HA.
2. **Container Postgres vs RDS.** Today: `postgres:16-alpine` with least-privilege roles (`kernel_app`,
   `network_app`, `identity_lockout`, `migrator`) created by the installer's split-role step, passwords in Vault,
   and the `localdev_pg` volume. For **RDS** the installer would need to: create those roles on the managed
   instance (it cannot own the superuser), store the role passwords in Vault, reach RDS over TLS from the
   `aos-data-facts` network only (ARC-3 — the fact store is Kernel/network/identity-reachable only; map to the RDS
   security group), and drop the local pg volume. **Open:** what the installer must do for a managed DB, and
   whether to keep container Postgres for the first production.
3. **Vault unseal method — DECIDED (not open).** Production uses **KMS auto-unseal** (AWS KMS, keys off-box) —
   now a RELEASE-PLAN gate, not an open decision (`deploy/RELEASE-PLAN.md` §2c). Today's local-dev is the demo
   auto-unseal (single unseal key + root token on the data volume, `vault/entrypoint.sh`, file storage). Slice-1b
   already removed the shared root from every service (per-service AppRole, DEBT-B58) and uses root only during
   install; the Vault image is pinned by digest on a current supported release (1.20.x / Alpine 3.22, off the EOL
   3.18 base). Remaining prod work for the gate: the KMS seal stanza + a Vault Agent renewer (recorded).

---

*This BOM is descriptive of the repository as it stands; it introduces no code changes. Residual items it points
at (RDS installer support, KMS unseal, TLS edge, CloudWatch alerting, physical split of the event/audit tables)
are tracked in FIX-PLAN / the backlog, not here.*

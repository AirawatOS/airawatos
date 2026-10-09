# AirawatOS — Pilot Deployment Requirements

A single Linux server running Docker. Everything below runs on one VM; nothing cloud-vendor-specific is
required. (Mapped onto a specific cloud — e.g. Oracle Cloud for the DJB engagement — the equivalents are:
VM = Compute, disk = Block Volume, bucket = Object Storage, registry = Container Registry, etc. The pilot
does not need Kubernetes, a managed database, or a load balancer.)

## Server
- 1 × Linux VM: **8 vCPU, 64 GB RAM**
- Disk: **~256 GB SSD** (OS + container images + database + file store)
- Architecture: x86-64

## Operating system & runtime
- **Linux** (Ubuntu 22.04 LTS or equivalent; Oracle Linux 9 if on OCI)
- **Docker Engine (v24+)** and **Docker Compose v2**
- `git`

## Storage
- The ~256 GB disk holds the PostgreSQL database and the file store.
- A separate **object/bucket store (~100 GB)** for backups and uploaded documents (optional for the pilot —
  can start on local disk).

## Software stack (all containers, open-source, no licenses)
- **PostgreSQL 16** — the system of record (governed, bitemporal registry)
- **Keycloak** — user login (OIDC)
- **HashiCorp Vault** — secrets
- **OpenFGA** — authorization
- **nginx** — TLS / web entry point
- ~16 **AirawatOS platform service containers** (pulled from a private image registry)

## Network
- One public **DNS name** + **TLS certificate** for the portal
- Inbound: **port 443 (HTTPS) only**
- Outbound: internet access to pull container images; an optional allow-list for external data sources and
  the LLM (see below)
- No other public ports

## Access (build + deploy from anywhere)
- **SSH access** to the VM using the admin's **SSH public key** (no passwords)
- Admin user in the `docker` group (+ sudo for setup)
- A **private container image registry** with a push/pull token, so images can be built on a laptop, pushed,
  and deployed on the server over SSH
- Reachable via SSH from any location — either a public IP with port 22 restricted to the admin, or a
  bastion / jump host

## AI / LLM (optional — can be deferred for the pilot)
The AI features call an LLM through an internal gateway. Provide **one** of:
- a hosted LLM API endpoint + key, or
- a self-hosted model on a GPU server, or
- leave it off for phase 1 (everything else works normally).

## Backup & data residency
- Daily PostgreSQL backup + document-store backup to the bucket/object store
- Host the server **in an India region** so all data stays in-country

## Not needed for the pilot
- No Kubernetes, no managed database, no load balancer — those belong to a later high-availability setup and
  do not change the application.
- No software licenses — the entire stack is open-source / self-hosted.

---

**One-line summary:** one Ubuntu VM (8 vCPU / 64 GB / 256 GB disk) with Docker, a DNS name + TLS cert, SSH
access via your key, a private image registry, and outbound internet — hosted in an India region. Optional:
an LLM endpoint and an object-storage bucket for backups.

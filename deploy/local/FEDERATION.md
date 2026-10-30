# Cross-install federation — connect two AirawatOS installs (ADR-0116 / ADR-0084)

A tenant on one install (say a **municipality**) can join a network run on a **different** install (say a
**Health ministry**) by URL. On approval the Health network establishes trust in the municipality's issuer, so
its tokens are honoured across the boundary. This is the tenant-free membership of ADR-0116 + the JWKS trust map
of ADR-0084.

The trust **mechanism** is proven (a foreign-issuer token is rejected before approval, accepted after — approval
registers the issuer's JWKS). This recipe runs it across two genuinely separate local installs.

## Prerequisite — distinct issuers
Each install's reference IdP must use its OWN issuer, or two installs collide on the default `ds:airawat:identity`.
Set per-install issuers before bringing each up:
```
IDENTITY_PER_TENANT_ISSUER=1          # iss = ds:<tenant>:identity, unique per install
```
(Exposed on the identity service in compose; add it to the install's `.env`.)

## Two stacks on one machine (port-separated)

```bash
# ── Install A = the municipality (default ports; web on :80) ──
cd deploy/local
INSTANCE=pune OPERATOR_PASSWORD='A@12345' ./airawatos-install.sh

# ── Install B = the Health network (second project, web on :8080) ──
#   a copy of deploy/local with COMPOSE_PROJECT_NAME=airawatos-health and nginx published on 8080,
#   its own volumes (vault/postgres/filestore) — nothing shared with A.
cp -r deploy/local /tmp/health && cd /tmp/health
echo "COMPOSE_PROJECT_NAME=airawatos-health" >> .env         # isolate containers + volumes
#   remap the published web port 80 -> 8080 in this copy's docker-compose.yml (nginx ports:)
INSTANCE=health OPERATOR_PASSWORD='B@12345' ./airawatos-install.sh
```

Now two independent installs run: A at `http://localhost/`, B (the Health network) at `http://localhost:8080/`.

## Connect A → B
1. Sign in to **A** (`http://localhost/login`) as `admin@pune`.
2. **Settings → Networks → Add a network by URL** → `http://host.docker.internal:8080/network`
   (A's app-host reaches B's network through the host; on Linux use the host IP or a shared docker network).
   A posts a **self-asserted application** to B carrying `pune`'s issuer + JWKS.
3. Sign in to **B** (`http://localhost:8080/login`) as `admin@health` → **Network Admin → Membership** →
   **Approve** the `pune` request. B registers `ds:pune:identity` in its trust map (trust handshake).
4. From then on, `pune`'s tokens are honoured by the Health network — `pune` can provide services into Health or
   consume Health's services for its users (the provide/consume paths are the next slice).

## Notes
- `host.docker.internal` is how A's containers reach B's published port on macOS/Windows Docker Desktop. On Linux,
  either use the host's LAN IP, or attach both stacks to one external docker network and use B's service DNS.
- Trust is bounded to the participant tenant and torn down on **revoke**.
- Scope/consent enforcement on the provide/consume paths + routing the request into B's Inbox are the next slice.

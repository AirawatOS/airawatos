#!/usr/bin/env python3
"""service-gateway — a standalone, stateless, horizontally-scalable READ tier for the citizen-service path
(ADR-0105 S1). It fronts the HIGH-VOLUME, read-dominated service interactions — discover an offering and read
an application's status — so they scale independently of the shared app_host and never contend with app-serving.

WHY A SEPARATE SERVICE
  Citizen-service delivery (search → init → confirm → status, ADR-0067) is the busiest public path and is
  read-heavy. In app_host it competes with every app bundle and bridge. Peeled into its own replicable service
  behind a load balancer, the read interactions scale linearly. This tier is a SCALING boundary, not a trust
  boundary: it forwards the caller's token unchanged; authorization, jurisdiction scoping and grant-gating stay
  exactly where they are (the network gateway + the kernel). It holds NO elevated authority and does NO writes.

  Reads go through KERNEL_READ_URL / NETWORK_URL, which can be pointed at a Postgres READ REPLICA (ADR-0105
  axis A) with no code change. Writes (init/confirm) are deliberately NOT here yet — they stay on the app_host
  BFF until the write-tier strategy (partition/split/tier, ADR-0105 axis B) lands (S5).

ENDPOINTS  (read-only)
  GET  /health
  POST /search  {q?, jurisdiction?, tenant?}      → proxy the network gateway's offering search (scoped)
  POST /status  {case}                            → read a provider platform.case (grant-gated, caller token)

Real data only — on an upstream failure it returns an error, never fabricated results. No secrets.
"""
import json, os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NETWORK_URL = os.environ.get("NETWORK_URL", "http://network:8090")          # governed offering directory / gateway
KERNEL_READ_URL = os.environ.get("KERNEL_READ_URL", "http://kernel:8080")   # point at a READ REPLICA at scale
PORT = int(os.environ.get("PORT", "8110"))
TIMEOUT = int(os.environ.get("UPSTREAM_TIMEOUT", "30"))


def _post(url, body, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = token if token.startswith("Bearer ") else "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read() or b"{}")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception:
            return None

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            return self._send(200, {"ok": True, "service": "service-gateway", "role": "read-tier",
                                    "network_url": NETWORK_URL, "kernel_read_url": KERNEL_READ_URL})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        tok = self.headers.get("Authorization")
        b = self._body()
        if b is None:
            return self._send(400, {"error": "bad json"})
        path = self.path.rstrip("/")
        try:
            if path == "/search":
                # discover offerings — proxy the governed network gateway search (read-only). The network returns
                # the full catalog under message.catalog; the caller token is forwarded unchanged.
                #
                # ⚠️ SCOPING NOT YET APPLIED HERE. Today the app_host BFF (routes/service_routes.py
                # :_bridge_service_search) applies TWO filters the network does NOT: an AUDIENCE gate (show an
                # offering only to viewers who hold its governed role, default civic.resident) and a JURISDICTION
                # scope (show it only if its serving jurisdiction is an ancestor-or-self of the citizen's
                # residence/property jurisdiction, from their profile). Both fail CLOSED. Serving the raw catalog
                # from here would LEAK cross-jurisdiction / officer-only offerings onto a citizen's home.
                # Before this path is wired into the LB (ADR-0105 S2), that scoping must be LIFTED — either into
                # the network gateway's /v1/service/search (preferred: it becomes governed + centrally testable)
                # or replicated here against the citizen profile. Until then this endpoint is scaffold-only and is
                # NOT registered on the public router.
                intent = b.get("intent") or {"domain": b.get("domain"), "service": b.get("service"),
                                              "query": b.get("query")}
                res = _post(NETWORK_URL + "/v1/service/search", {"intent": intent}, tok)
                res.setdefault("context", {})["scoping"] = "unscoped-scaffold: audience+jurisdiction filter pending (ADR-0105 S2)"
                return self._send(200, res)
            if path == "/status":
                # read a provider platform.case by id (grant-gated cross-tenant read; caller token forwarded).
                # Reads only — safe to serve from a read replica (KERNEL_READ_URL).
                case = b.get("case")
                if not case:
                    return self._send(400, {"error": "case required"})
                res = _post(KERNEL_READ_URL + "/v1/registry/resolve",
                            {"id": case, "filter": {"schema": "platform.case"}}, tok)
                hits = res.get("results") or []
                if not hits:
                    return self._send(404, {"error": f"case not found (or no read grant): {case}"})
                o = hits[0].get("object") or hits[0]
                return self._send(200, {"case": case, "status": o.get("status"),
                                        "current_step": o.get("current_step"), "object": o})
        except urllib.error.HTTPError as e:
            return self._send(e.code, {"error": f"upstream {e.code}: " + e.read().decode()[:200]})
        except Exception as e:
            return self._send(502, {"error": str(e)[:200]})
        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"[service-gateway] read-tier on :{PORT}  network={NETWORK_URL}  kernel_read={KERNEL_READ_URL}", flush=True)
    ThreadingHTTPServer((os.environ.get("BIND_HOST", "0.0.0.0"), PORT), H).serve_forever()

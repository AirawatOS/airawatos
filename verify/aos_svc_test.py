#!/usr/bin/env python3
"""DEBT-B174 — the shared internal service client (deploy/runtime/lib/aos_svc) behaves as declared.

Against a local fake door (no stack): the client
  • attaches the audience-bound token for the door being called, and with no credential sends NOTHING (status 0 → 503);
  • retries the declared number of times on 502/503/504, never on a refusal (403) and never for a streamed body;
  • maps a refusal to DoorError with the door's own reason and an answerable status (403 → 502, 404 → 404), never 500;
  • carries X-Request-Id — the inbound one bound by request_context, the same on every retry;
  • reads a public operation (healthz) without a token;
  • has methods only for declared operations: undeclared door / operation / caller → NotDeclared.
Exit 1 on failure.
"""
import io, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deploy/runtime/lib"))
import aos_svc            # noqa: E402
import aos_svc.tokens     # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (" — " + str(detail)[:180] if detail else ""))
    if not ok:
        fails.append(name)


SEEN, PLAN = [], {}          # PLAN[path] = list of statuses to answer in order (then 200)


class Door(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _h(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "rid": self.headers.get("X-Request-Id")})
        q = PLAN.get(self.path.split("?")[0]) or []
        code = q.pop(0) if q else 200
        body = json.dumps({"error": "door says %d" % code} if code != 200 else {"id": "sha2-256:x", "content": "ok"}).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    do_GET = do_POST = _h


srv = ThreadingHTTPServer(("127.0.0.1", 0), Door)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d" % srv.server_address[1]
os.environ["FILESTORE_URL"] = URL
os.environ["EMBED_URL"] = URL
TOK = {"on": True}
aos_svc.tokens.token = lambda principal=None, tenant=None, audience=None: ("T:%s:%s" % (principal, audience)) if TOK["on"] else None
aos_svc.time.sleep = lambda s: None          # no real backoff in the test

app = aos_svc.client_for("app-host", tenant="t")
kern = aos_svc.client_for("kernel")
lnch = aos_svc.client_for("launcher")

# token per door
SEEN.clear(); app.filestore.put(b"abc"); app.model_gateway.complete({"messages": []})
check("each door gets ITS audience token for THIS caller",
      [s["auth"] for s in SEEN] == ["Bearer T:app-host:svc:filestore", "Bearer T:app-host:svc:model-gateway"], [s["auth"] for s in SEEN])

# request id
SEEN.clear()
with aos_svc.request_context("req-123"):
    PLAN["/complete"] = [503]
    kern.model_gateway.complete({"messages": []})
check("X-Request-Id = the bound inbound id, on the first try AND the retry", [s["rid"] for s in SEEN] == ["req-123", "req-123"], SEEN)

# retries: transient yes (declared count), refusal no, streamed body no
SEEN.clear(); PLAN["/complete"] = [502, 503, 504]
r = kern.model_gateway.complete({"messages": []})
check("complete retries its declared 3 times on 502/503/504, then succeeds", len(SEEN) == 4 and r.get("content") == "ok", len(SEEN))
SEEN.clear(); PLAN["/files"] = [403]
try:
    app.filestore.put(b"x"); e = None
except aos_svc.DoorError as x:
    e = x
check("a refusal (403) is NOT retried and surfaces as DoorError with the door's reason",
      len(SEEN) == 1 and e and e.status == 403 and "door says 403" in e.reason, (len(SEEN), e))
check("refused → http_status 502 (an upstream refusal), never 500", e and e.http_status == 502)
SEEN.clear(); PLAN["/files"] = [503, 503]
try:
    app.filestore.put(io.BytesIO(b"stream"), length=6); e = None
except aos_svc.DoorError as x:
    e = x
check("a streamed body is never retried (cannot be re-read)", len(SEEN) == 1 and e and e.status == 503, len(SEEN))
PLAN.clear()
SEEN.clear(); PLAN["/files/missing"] = [404]
try:
    lnch.filestore.get("missing"); e = None
except aos_svc.DoorError as x:
    e = x
check("404 stays 404 (the thing asked for is absent)", e and e.http_status == 404, e)

# no credential → nothing sent
TOK["on"] = False; SEEN.clear()
try:
    app.filestore.get("a"); e = None
except aos_svc.DoorError as x:
    e = x
check("no credential: NOTHING sent; DoorError names the missing credential; answer 503",
      not SEEN and e and e.status == 0 and "credential missing" in str(e) and "svc:filestore" in str(e) and e.http_status == 503, (SEEN, e))
SEEN.clear(); h = app.model_gateway.healthz()
check("a public operation (healthz) is read without a token", SEEN and SEEN[0]["auth"] is None and h.get("content") == "ok", SEEN)
TOK["on"] = True

# declared-only methods
def refused(fn):
    try:
        fn(); return False
    except aos_svc.NotDeclared:
        return True
check("launcher has no model-gateway door", refused(lambda: lnch.model_gateway))
check("launcher may get but not put on the filestore", refused(lambda: lnch.filestore.put(b"x")) and not refused(lambda: lnch.filestore._op("get")))
check("kernel may not set provider keys", refused(lambda: kern.model_gateway.provider_key({})))
check("an undeclared caller gets no client", refused(lambda: aos_svc.client_for("not-a-service")))
check("call_url refuses an undeclared path", refused(lambda: app.model_gateway.call_url("POST", URL + "/admin/other")))
SEEN.clear(); app.model_gateway.call_url("POST", URL + "/complete", data=b"{}")
check("call_url resolves a declared path to its operation (token attached)", SEEN and SEEN[0]["auth"] == "Bearer T:app-host:svc:model-gateway")

print("ALL PASS" if not fails else "FAILED: %d" % len(fails))
sys.exit(1 if fails else 0)

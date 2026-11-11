#!/usr/bin/env python3
"""Secret-name validation and no-redirect test for the secrets broker and model-gateway (slice-1g, DEBT-B90 / review N5).

Drives the REAL secrets-broker HTTP handler (platform-spec/reference/secrets.py) in-process against a FAKE Vault +
upstream that records every request it receives. The ingress gates are admitted (this test is about what the broker
does with a name once a caller is in), so every refusal below is the broker's own name check.

  1. Traversal names — '../', '..', encoded '%2e%2e', '..%2F', '%2e%2e%2f', embedded 'x/../y', NUL, backslash — in the
     secret name, the tenant or the component, on /set, /materialize, /fetch(inject) → 400, and Vault is NEVER asked.
  2. A Vault 307 redirect (to a platform credential) is NOT followed.
  3. A /fetch upstream 302 redirect is NOT followed — the injected key never reaches the redirect target.
  4. model-gateway's _vault_read / _vault_put refuse the same names without asking Vault.
  5. Positive: a valid (tenant, component, name) still reads.

Runs inside the reference image (needs `cryptography`):  make secret-names
  docker run --rm --network none -v $PWD/platform-spec/reference:/r:ro -v $PWD/verify:/v:ro <reference image> \
      python /v/secret_names_test.py
REF=<dir> selects the reference source (to run against an older secrets.py). Exits 1 on any failure.
"""
import http.server, json, os, sys, threading, urllib.request, urllib.error

REF = os.environ.get("REF", "/r")
sys.path.insert(0, REF)

hits = []                       # (method, raw path, authorization header) seen by the fake Vault/upstream


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _rec(self):
        hits.append((self.command, self.path, self.headers.get("Authorization") or self.headers.get("X-Vault-Token") or ""))

    def _json(self, code, obj, extra=None):
        b = json.dumps(obj).encode()
        self.send_response(code)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self._rec()
        if self.path.endswith("/redir"):
            return self._json(307, {}, {"Location": "/v1/secret/data/localdev/kernel-app/password"})
        if self.path == "/upstream":
            return self._json(302, {}, {"Location": "http://127.0.0.1:%d/leak" % FPORT})
        return self._json(200, {"data": {"data": {"value": "fake-secret-value"}}})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._rec()
        return self._json(200, {})


fsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
FPORT = fsrv.server_address[1]
threading.Thread(target=fsrv.serve_forever, daemon=True).start()
os.environ["VAULT_ADDR"] = "http://127.0.0.1:%d" % FPORT
os.environ["VAULT_TOKEN"] = "fake-broker-token"

import secrets as S                                        # noqa: E402  (the broker under test)
S._secrets_gate_denied = lambda h: None                    # admit: this test is about names, not callers
S.H._admin = lambda self, tenant: ({"tenant": tenant}, None)
bsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S.H)
BPORT = bsrv.server_address[1]
threading.Thread(target=bsrv.serve_forever, daemon=True).start()

fails = []


def call(route, body):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (BPORT, route), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:                  # the handler crashed / dropped the connection — not a refusal
        return "dropped (%s)" % type(e).__name__, {}


def check(name, ok, detail):
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail)
    if not ok:
        fails.append(name)


BAD = ["../x", "..", "../../secret/data/localdev/kernel-app/password", "x/../../y", "%2e%2e", "%2e%2e%2fx", "..%2Fx",
       "%2E%2E%2F%2E%2E%2Fsecret", ".%2e/x", "x\x00y", "..\\x", "x/y", " ", ""]
BAD_COMPONENT = ["..", "../../secret", "ds:x/../../secret", "ds:x/./y", "ds:x//y", "ds%3Ax%2F..", "%2e%2e"]
GOOD = {"tenant": "t1", "component": "ds:airawat:provider/anthropic", "name": "api_key"}

print("▶ secret-name test (B90) — broker under test: %s/secrets.py" % REF)
for route in ("/set", "/materialize", "/fetch"):
    for field, values in (("name", BAD), ("tenant", BAD), ("component", BAD_COMPONENT)):
        for v in values:
            b = dict(GOOD, **{field: v})
            if route == "/set":
                b["value"] = "x"
            if route == "/fetch":
                if field == "name" and v == "":
                    continue                 # no name = no injection requested (a plain declared-egress fetch)
                b = {"tenant": b["tenant"], "component": b["component"], "url": "http://127.0.0.1:%d/ok" % FPORT,
                     "inject": {"name": b["name"], "header": "Authorization"}}
            before = len(hits)
            st, body = call(route, b)
            vault_asked = [h for h in hits[before:] if h[1].startswith("/v1/")]
            check("%s refuses %s=%r" % (route, field, v), st == 400 and not vault_asked,
                  "status %s, Vault asked: %s" % (st, [h[1] for h in vault_asked] or "no"))

before = len(hits)
st, body = call("/materialize", dict(GOOD, name="redir"))
followed = [h[1] for h in hits[before:] if "kernel-app" in h[1]]
check("a Vault 307 redirect (to a platform credential) is NOT followed", not followed and st != 200,
      "status %s, redirect target requested: %s" % (st, followed or "no"))

before = len(hits)
st, body = call("/fetch", {"tenant": "t1", "component": GOOD["component"], "url": "http://127.0.0.1:%d/upstream" % FPORT,
                           "inject": {"name": "api_key", "header": "Authorization"}})
leaked = [h for h in hits[before:] if h[1] == "/leak"]
check("a /fetch upstream 302 is NOT followed — the injected key never reaches the redirect target",
      not leaked and str(body.get("upstream_status")) == "302",
      "upstream_status %s, /leak requested: %s" % (body.get("upstream_status"), "YES with %r" % leaked[0][2] if leaked else "no"))

before = len(hits)
st, body = call("/materialize", GOOD)
check("positive: a valid (tenant, component, name) still reads", st == 200 and body.get("value") == "fake-secret-value",
      "status %s, Vault path %s" % (st, [h[1] for h in hits[before:]]))

try:
    import model_gateway as MG                          # noqa: E402
    MG.VAULT = os.environ["VAULT_ADDR"]
    for v in ("../x", "%2e%2e", "..%2Fx", "x/../y"):
        before = len(hits)
        r = MG._vault_read("t1", GOOD["component"], v)
        check("model-gateway _vault_read refuses name %r" % v, r is None and len(hits) == before,
              "returned %r, Vault asked: %s" % (r, len(hits) > before))
        before = len(hits)
        try:
            MG._vault_put("t1", GOOD["component"], v, "x"); raised = False
        except ValueError:
            raised = True
        except Exception:
            raised = False
        check("model-gateway _vault_put refuses name %r" % v, raised and len(hits) == before,
              "refused=%s, Vault asked: %s" % (raised, len(hits) > before))
except Exception as e:
    check("model-gateway importable for the name check", False, "%s: %s" % (type(e).__name__, str(e)[:120]))

print(("✗" if fails else "✓") + " secret-name test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

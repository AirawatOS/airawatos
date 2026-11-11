#!/usr/bin/env python3
"""DEV-ONLY stub model provider — the model gateway's SOUTH-SIDE contract (OpenAI-compatible), no external API.

Built into its OWN image (manishsv/airawatos-devstub), never into a shipped image, and run only by the local-dev
stack. It REFUSES TO START when AIRAWAT_ENV=production; the model gateway also refuses to route to a provider record
flagged `dev_stub` (or pointing at this host) in production, and verify/banned_patterns.py fails any production
configuration that names it.

Contract (what model_gateway.py calls on a provider's base_url):
  POST /v1/chat/completions   {model, messages, max_tokens?, temperature?} → {choices:[{message:{role,content},finish_reason}], usage}
  POST /v1/embeddings         {model, input:[text]}                      → {data:[{embedding:[…]}], model}
  POST /v1/audio/transcriptions  multipart (file, model, language?, vad?) → {text}
  GET  /healthz
Every POST requires `Authorization: Bearer <key>` (the gateway sends the provider key from Vault) — a missing key is
401, exactly like a real provider, so the stub also proves the key path. Answers are DETERMINISTIC and marked
`[stub-provider]`, so a test can tell a stub answer from a real one.
"""
import hashlib, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MARK = "[stub-provider]"


def _refuse_production():
    if (os.environ.get("AIRAWAT_ENV") or "").strip().lower() in ("prod", "production"):
        sys.stderr.write("✗ the dev-only stub model provider refuses to start in production (AIRAWAT_ENV=%s)\n" % os.environ["AIRAWAT_ENV"])
        sys.exit(78)


def _digest(s):
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:12]


def _vec(text, dim=8):
    h = hashlib.sha256((text or "").encode()).digest()
    v = [((b / 255.0) * 2 - 1) for b in h[:dim]]
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [round(x / n, 6) for x in v]


class Handler(BaseHTTPRequestHandler):
    server_version = "airawat-devstub/0.1"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok", "stub": True})
        return self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer ") or not auth[7:].strip():
            return self._send(401, {"error": {"message": "missing provider key (Authorization: Bearer …)"}})
        path = self.path.split("?", 1)[0]
        if path == "/v1/chat/completions":
            try:
                b = json.loads(raw or b"{}")
            except Exception:
                return self._send(400, {"error": {"message": "bad json"}})
            msgs = b.get("messages") or []
            last = next((m.get("content") or "" for m in reversed(msgs) if m.get("role") == "user"), "")
            text = "%s answer to %d message(s); last user message %d chars, digest %s" % (MARK, len(msgs), len(last), _digest(last))
            pt, ct = sum(len(str(m.get("content") or "")) for m in msgs) // 4 + 1, len(text) // 4 + 1
            return self._send(200, {"id": "stub-" + _digest(last), "object": "chat.completion", "model": b.get("model") or "stub-chat",
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}})
        if path == "/v1/embeddings":
            try:
                b = json.loads(raw or b"{}")
            except Exception:
                return self._send(400, {"error": {"message": "bad json"}})
            inp = b.get("input") or []
            inp = [inp] if isinstance(inp, str) else inp
            return self._send(200, {"object": "list", "model": b.get("model") or "stub-embed",
                                    "data": [{"object": "embedding", "index": i, "embedding": _vec(t)} for i, t in enumerate(inp)]})
        if path == "/v1/audio/transcriptions":
            if b'name="file"' not in raw:
                return self._send(400, {"error": {"message": "multipart field `file` required"}})
            return self._send(200, {"text": "%s transcript of %d bytes" % (MARK, len(raw))})
        return self._send(404, {"error": {"message": "no such route: " + path}})


if __name__ == "__main__":
    _refuse_production()
    port = int(os.environ.get("PORT", "8110"))
    print("[devstub] DEV-ONLY stub model provider on :%d (OpenAI-compatible south side)" % port, flush=True)
    ThreadingHTTPServer((os.environ.get("BIND_HOST", "0.0.0.0"), port), Handler).serve_forever()

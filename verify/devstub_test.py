#!/usr/bin/env python3
"""Fixtures decision — the DEV-ONLY stub model provider honours the model gateway's south-side contract, and refuses
production.

Runs deploy/local-dev/devstub/stub_provider.py (no stack): chat completions / embeddings / audio transcriptions answer
in the OpenAI-compatible shapes model_gateway.py parses, marked `[stub-provider]`, deterministically; a POST without
the provider key (Bearer) is 401 like a real provider; and the process REFUSES TO START under AIRAWAT_ENV=production.
Exit 1 on failure.
"""
import json, os, subprocess, sys, threading, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB = os.path.join(ROOT, "deploy/local-dev/devstub/stub_provider.py")
sys.path.insert(0, os.path.dirname(STUB))
import stub_provider as sp                     # noqa: E402
from http.server import ThreadingHTTPServer   # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (" — " + str(detail)[:160] if detail else ""))
    if not ok:
        fails.append(name)


srv = ThreadingHTTPServer(("127.0.0.1", 0), sp.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % srv.server_address[1]


def post(path, data, ctype="application/json", key="k"):
    h = {"Content-Type": ctype}
    if key:
        h["Authorization"] = "Bearer " + key
    try:
        r = urllib.request.urlopen(urllib.request.Request(B + path, data=data, headers=h, method="POST"), timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


body = json.dumps({"model": "stub-chat", "messages": [{"role": "user", "content": "Which ward?"}]}).encode()
s, d = post("/v1/chat/completions", body)
c = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
check("chat completion: choices[0].message.content + finish_reason + usage (the shape the gateway parses)",
      s == 200 and c.startswith("[stub-provider]") and d["choices"][0].get("finish_reason") == "stop" and d.get("usage"), (s, d))
s2, d2 = post("/v1/chat/completions", body)
check("deterministic: the same request gets the same answer", d2 == d)
s, d = post("/v1/embeddings", json.dumps({"model": "stub-embed", "input": ["a", "b"]}).encode())
check("embeddings: data[i].embedding per input", s == 200 and len(d.get("data") or []) == 2 and len(d["data"][0]["embedding"]) == 8, (s, d))
mp = b'--x\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\nRIFF....\r\n--x--\r\n'
s, d = post("/v1/audio/transcriptions", mp, "multipart/form-data; boundary=x")
check("transcriptions: multipart file → {text}", s == 200 and (d.get("text") or "").startswith("[stub-provider]"), (s, d))
s, d = post("/v1/chat/completions", body, key=None)
check("no provider key → 401 (like a real provider)", s == 401, (s, d))
r = subprocess.run([sys.executable, STUB], env=dict(os.environ, AIRAWAT_ENV="production", PORT="0"), capture_output=True, text=True, timeout=20)
check("refuses to start under AIRAWAT_ENV=production", r.returncode != 0 and "refuses to start in production" in r.stderr, (r.returncode, r.stderr[-120:]))

print("ALL PASS" if not fails else "FAILED: %d" % len(fails))
sys.exit(1 if fails else 0)

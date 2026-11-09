#!/usr/bin/env python3
"""The installer's write guard turns ANY failed write into a failed helper (slice-1i, DEBT-B127/B135). No stack needed:
a local HTTP server answers 500 / 401 / 409; helpers that SWALLOW the error in different spellings must still exit 1:
  1. the final review's case: `except … as err: return err.code`
  2. `except Exception: pass`
  3. prints the error and exits 0 explicitly (sys.exit(0))
  4. a 401 on a POST login, then carries on
  5. a connection refused on a write
  positive: a 409 (idempotent already-exists) and failed GETs do NOT fail the helper; a clean helper exits 0.
Exit 1 on failure.
"""
import http.server, os, subprocess, sys, tempfile, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.environ.get("GUARD", os.path.join(ROOT, "deploy/installer/_write_guard.py"))


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _r(self):
        code = int(self.path.strip("/").split("/")[0] or 200)
        self.send_response(code); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")
    do_GET = do_POST = do_PUT = _r


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
U = "http://127.0.0.1:%d" % srv.server_address[1]
PRE = "import urllib.request as u, urllib.error as ue, sys\nR=lambda p,m='POST': u.Request('%s'+p, data=b'{}', method=m)\n" % U
CASES = [
    ("swallowed as `except … as err: return err.code` (final-review case)", "def w():\n  try: return u.urlopen(R('/500')).status\n  except ue.HTTPError as err: return err.code\nprint(w())", 1),
    ("swallowed by `except Exception: pass`", "try: u.urlopen(R('/500'))\nexcept Exception: pass", 1),
    ("printed, then sys.exit(0)", "try: u.urlopen(R('/503'))\nexcept Exception as e: print('warn', e)\nsys.exit(0)", 1),
    ("a 401 on a POST login, then carries on", "try: u.urlopen(R('/401'))\nexcept Exception: print('login failed, continuing')", 1),
    ("connection refused on a write", "try: u.urlopen(u.Request('http://127.0.0.1:1/x', data=b'{}'), timeout=2)\nexcept Exception: pass", 1),
    ("positive: 409 already-exists is idempotent", "try: u.urlopen(R('/409'))\nexcept Exception: pass", 0),
    ("positive: a failed GET (absence probe)", "try: u.urlopen(R('/404','GET'))\nexcept Exception: pass", 0),
    ("positive: a clean helper", "u.urlopen(R('/200'))", 0),
]
fails = []
print("▶ installer write-guard test (B127/B135) — guard %s" % os.path.relpath(GUARD, ROOT))
with tempfile.TemporaryDirectory() as td:
    os.symlink(os.path.abspath(GUARD), os.path.join(td, "sitecustomize.py"))
    for name, code, want in CASES:
        r = subprocess.run([sys.executable, "-c", PRE + code], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=td))
        ok = (r.returncode != 0) == bool(want)
        print(("  ✓ " if ok else "  ✗ ") + "%s → helper exit %d" % (name, r.returncode))
        if not ok:
            fails.append(name)
print(("✗" if fails else "✓") + " write-guard test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

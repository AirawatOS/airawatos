# sitecustomize — the installer's WRITE GUARD (slice-1i, DEBT-B127/B135).
#
# Loaded (via PYTHONPATH) into EVERY Python helper the installer runs — inline heredoc phases and helper scripts alike
# (ensure_install, seed_base, seed_base_os, mint_base_listings, the trust-schema tool, _deliver_fixture, …). It wraps
# urllib.request.urlopen and records every WRITE (any method but GET/HEAD/OPTIONS) that fails — an HTTP error status or an
# exception — whatever the helper then does with the error (swallow it, print it, return its code). At interpreter exit a
# recorded failure FORCES a non-zero exit, so the installer's phase fails loudly. This fixes the class: no helper has to
# get its own error handling right for a failed write to stop the install.
#
#   409 Conflict is an idempotent "already exists" and is not a failure.
#   Test hook (dev profile only, set by install.sh): AOS_INSTALL_FAULT_WRITE=<url substring> makes the FIRST matching write
#   fail with HTTP 503 — fault injection INSIDE a write, not at a phase banner.
import atexit
import os
import sys
import urllib.error
import urllib.request

_orig = urllib.request.urlopen
_FAILS = []
_FAULT = os.environ.get("AOS_INSTALL_FAULT_WRITE", "")
_fired = [False]
_OK = {409}


def _method(req, a, k):
    if hasattr(req, "get_method"):
        return req.get_method()
    return "POST" if (a[:1] and a[0] is not None) or k.get("data") is not None else "GET"


def _url(req):
    return getattr(req, "full_url", None) or str(req)


def urlopen(req, *a, **k):
    m, u = _method(req, a, k), _url(req)
    write = m not in ("GET", "HEAD", "OPTIONS")
    if write and _FAULT and not _fired[0] and _FAULT in u:
        _fired[0] = True
        _FAILS.append("%s %s -> 503 (INJECTED test fault)" % (m, u))
        raise urllib.error.HTTPError(u, 503, "injected installer test fault", {}, None)
    try:
        return _orig(req, *a, **k)
    except urllib.error.HTTPError as e:
        if write and e.code not in _OK:
            _FAILS.append("%s %s -> %s" % (m, u, e.code))
        raise
    except Exception as e:
        if write:
            _FAILS.append("%s %s -> %s" % (m, u, type(e).__name__))
        raise


urllib.request.urlopen = urlopen


@atexit.register
def _verdict():
    if _FAILS:
        sys.stderr.write("✗ installer helper: %d WRITE(S) FAILED — the phase fails:\n    %s\n" % (len(_FAILS), "\n    ".join(_FAILS[:10])))
        sys.stderr.flush()
        os._exit(1)

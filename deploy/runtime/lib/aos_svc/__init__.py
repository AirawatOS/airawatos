"""aos_svc — the shared internal service client, used by every platform service (DEBT-B174 class fix).

One package, shipped in every platform image at /opt/airawat/lib (root deploy/runtime/lib → kernel, network,
reference images; importable via a .pth file). A caller asks for ITS client:

    from aos_svc import client_for
    svc = client_for("app-host", tenant=...)          # who I am (the declared caller name)
    fid = svc.filestore.put(blob)["id"]
    text = svc.model_gateway.complete({"messages": [...]})["content"]

The doors and operations a caller has are DECLARED, not hand-written: they come from the caller→door edge table in
docs/specs/ARCHITECTURE-FLOWS-v0.1.md (block `svc-edges`), compiled into edges.json (verify/svc_edges.py keeps the
two identical). A caller gets a method ONLY for an operation it is a declared caller of; anything else raises
NotDeclared — e.g. `client_for("launcher").model_gateway` does not exist.

Every call:
  • obtains the audience-bound service token for the door being called (aos_svc.tokens — the one minting code)
    and attaches it; with no credential NOTHING is sent;
  • applies the operation's declared timeout and bounded retries on transient failures (502/503/504/unreachable;
    never for a streamed body);
  • carries a request/trace id (X-Request-Id: the inbound one bound with `request_context`, else a new one);
  • maps any refusal or failure to DoorError — door, operation, status, the door's reason, request id, and the
    status a caller should answer with (`.http_status`, never 500).

Implemented doors now: filestore, model-gateway. The first post-merge slice (DEBT-B179) adds the remaining doors
of ARCHITECTURE-FLOWS §h and turns on the banned-pattern rule "no raw HTTP to an internal service outside aos_svc".
"""
import contextvars
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from aos_svc import tokens

_HERE = os.path.dirname(os.path.abspath(__file__))
EDGES = json.load(open(os.path.join(_HERE, "edges.json")))
_REQ_ID = contextvars.ContextVar("aos_svc_request_id", default=None)


class NotDeclared(AttributeError):
    """The caller is not a declared caller of that door / operation (ARCHITECTURE-FLOWS svc-edges)."""


class DoorError(Exception):
    """A call to an internal door failed. `status` = the door's HTTP status (0 = not sent / unreachable);
    `reason` = the door's own reason; `http_status` = what the caller should answer its user with (never 500)."""

    def __init__(self, door, op, status, reason, request_id):
        self.door, self.op, self.status, self.reason, self.request_id = door, op, status, reason, request_id
        super().__init__("%s %s %s: %s [request %s]" % (door, op, status or "not sent", reason, request_id))

    @property
    def http_status(self):
        if self.status in (400, 404, 409, 413, 422):
            return self.status                      # the caller's input / the thing asked for
        if self.status == 0:
            return 503                              # not sent (no credential) or unreachable
        return 502                                  # the door refused or failed: an upstream problem, reported as such

    def body(self):
        return {"error": str(self), "door": self.door, "operation": self.op, "door_status": self.status,
                "reason": self.reason, "request_id": self.request_id}


class request_context:
    """Bind the inbound request id so every door call made while handling it carries the same id."""

    def __init__(self, request_id=None):
        self.rid = request_id or uuid.uuid4().hex[:16]

    def __enter__(self):
        self._t = _REQ_ID.set(self.rid)
        return self.rid

    def __exit__(self, *a):
        _REQ_ID.reset(self._t)


def bind_request_id(request_id=None):
    """For threaded HTTP handlers: bind (for the rest of this thread's request) and return the id."""
    rid = request_id or uuid.uuid4().hex[:16]
    _REQ_ID.set(rid)
    return rid


def current_request_id():
    return _REQ_ID.get() or uuid.uuid4().hex[:16]


_TRANSIENT = (502, 503, 504)


class Door:
    """One door as seen by one caller: only the operations the caller is declared for."""

    def __init__(self, caller, name, spec, principal, tenant):
        self.caller, self.name, self.spec = caller, name, spec
        self._principal, self._tenant = principal, tenant
        self._ops = {op: o for op, o in spec["operations"].items() if caller in o["callers"]}
        self.audience = spec["audience"]

    # ── plumbing ────────────────────────────────────────────────────────────────────────────────────────────────
    def base(self):
        return (os.environ.get(self.spec["base_env"]) or self.spec.get("base_default") or "").rstrip("/")

    def owns(self, url):
        b = self.base()
        return bool(b) and (url == b or url.startswith(b + "/"))

    def _op(self, op):
        o = self._ops.get(op)
        if o is None:
            raise NotDeclared("%s is not a declared caller of %s.%s (ARCHITECTURE-FLOWS svc-edges)" % (self.caller, self.name, op))
        return o

    def _headers(self, o, op, extra, rid):
        h = dict(extra or {})
        h["X-Request-Id"] = rid
        if not o.get("public"):
            # audience "platform" = the platform token (identity's default audience), e.g. a kernel registry write
            t = tokens.token(self._principal, self._tenant, None if self.audience == "platform" else self.audience)
            if not t:
                raise DoorError(self.name, op, 0, "%s holds no %s service token (credential missing) — not sent"
                                % (self.caller, self.audience), rid)
            h["Authorization"] = "Bearer " + t
        return h

    def open(self, op, path_args=None, data=None, headers=None, timeout=None, retries=None):
        """The raw response (stream it; close it). Retries (the declared count) only on transient failures, and never
        a streamed body (a file object cannot be re-read)."""
        o = self._op(op)
        rid = current_request_id()
        method, tmpl = o["method"], o["path"]
        path = tmpl.format(**{k: urllib.parse.quote(str(v), safe=":") for k, v in (path_args or {}).items()})
        to = timeout if timeout is not None else o.get("timeout", 30)
        n = retries if retries is not None else (0 if hasattr(data, "read") else o.get("retries", 0))
        last = None
        for attempt in range(n + 1):
            hdr = self._headers(o, op, headers, rid)
            req = urllib.request.Request(self.base() + path, data=data, method=method, headers=hdr)
            try:
                return urllib.request.urlopen(req, timeout=to)
            except urllib.error.HTTPError as e:
                try:
                    reason = e.read()[:400].decode(errors="replace")
                    reason = (json.loads(reason).get("error") or json.loads(reason).get("detail") or reason) if reason.startswith("{") else reason
                except Exception:
                    reason = str(e.reason)
                last = DoorError(self.name, op, e.code, str(reason) or str(e.reason), rid)
                if e.code not in _TRANSIENT:
                    raise last
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last = DoorError(self.name, op, 0, "unreachable: %s" % (getattr(e, "reason", None) or e), rid)
            if attempt < n:
                time.sleep(0.5 * (attempt + 1))
        raise last

    def call(self, op, **kw):
        with self.open(op, **kw) as r:
            return r.read()

    def call_url(self, method, url, data=None, headers=None, timeout=None):
        """For generic helpers holding a URL (e.g. an in-process engine's ctx['http'](embed_url + '/complete')):
        resolve the DECLARED operation from method + path, then call it like any other. Undeclared → NotDeclared."""
        import re as _re
        path = url[len(self.base()):] if self.owns(url) else url
        for op, o in self._ops.items():
            rx = "^" + _re.sub(r"\\\{(\w+)\\\}", lambda m: "(?P<%s>[^/?]+)" % m.group(1), _re.escape(o["path"])) + "$"
            m = _re.match(rx, path.split("?", 1)[0])
            if o["method"] == method.upper() and m:
                args = {k: urllib.parse.unquote(v) for k, v in m.groupdict().items()}
                return self.call(op, path_args=args, data=data, headers=headers, timeout=timeout)
        raise NotDeclared("%s is not a declared caller of %s %s on %s (ARCHITECTURE-FLOWS svc-edges)" % (self.caller, method, path, self.name))

    def call_json(self, op, payload=None, **kw):
        data = json.dumps(payload).encode() if payload is not None else None
        hdr = dict(kw.pop("headers", None) or {})
        if data is not None:
            hdr.setdefault("Content-Type", "application/json")
        raw = self.call(op, data=data, headers=hdr, **kw)
        return json.loads(raw or b"{}")

    def __getattr__(self, op):
        # an operation the door has but this caller is not declared for → a clear NotDeclared, not AttributeError
        if not op.startswith("_") and op in self.spec["operations"]:
            raise NotDeclared("%s is not a declared caller of %s.%s (ARCHITECTURE-FLOWS svc-edges)" % (self.caller, self.name, op))
        raise AttributeError(op)


class Filestore(Door):
    def put(self, data, length=None, timeout=None):
        """Store bytes (or a binary file object — pass `length` so it streams with a Content-Length) → {id, size}."""
        h = {"Content-Type": "application/octet-stream"}
        if length is not None:
            h["Content-Length"] = str(length)
        return json.loads(self.call("put", data=data, headers=h, timeout=timeout) or b"{}")

    def get(self, fid, timeout=None):
        return self.call("get", path_args={"id": fid}, timeout=timeout)

    def open_blob(self, fid, timeout=None):
        """A streaming response for a blob (caller closes it)."""
        return self.open("get", path_args={"id": fid}, timeout=timeout)


class ModelGateway(Door):
    def complete(self, body, timeout=None):
        return self.call_json("complete", body, timeout=timeout)

    def embed(self, body, timeout=None):
        return self.call_json("embed", body, timeout=timeout)

    def transcribe(self, payload_bytes, timeout=None):
        return self.call("transcribe", data=payload_bytes, headers={"Content-Type": "application/json"}, timeout=timeout)

    def provider_key(self, body, timeout=None):
        return self.call_json("provider_key", body, timeout=timeout)

    def healthz(self, timeout=None):
        return self.call_json("healthz", timeout=timeout)


_KINDS = {"filestore": Filestore, "model-gateway": ModelGateway}


class Client:
    def __init__(self, caller, principal=None, tenant=None):
        self.caller = caller
        self._doors = {}
        for name, spec in EDGES["doors"].items():
            if any(caller in o["callers"] for o in spec["operations"].values()):
                self._doors[name] = _KINDS.get(name, Door)(caller, name, spec, principal or caller,
                                                            tenant or tokens.default_tenant())

    def door(self, name):
        d = self._doors.get(name)
        if d is None:
            raise NotDeclared("%s is not a declared caller of %s (ARCHITECTURE-FLOWS svc-edges)" % (self.caller, name))
        return d

    def door_for(self, url):
        """The declared door `url` addresses, or None (for generic helpers that must hand gated URLs to the client)."""
        return next((d for d in self._doors.values() if d.owns(url)), None)

    def doors(self):
        return sorted(self._doors)

    def __getattr__(self, attr):
        name = attr.replace("_", "-")
        if name in EDGES["doors"]:
            return self.door(name)
        raise AttributeError(attr)


def client_for(caller, principal=None, tenant=None):
    """The client for declared caller `caller` (its ARCHITECTURE-FLOWS name), minting as `principal`@`tenant`
    (default: principal = the caller name, tenant = SERVICE_TENANT)."""
    if caller not in EDGES["callers"]:
        raise NotDeclared("%s is not a declared caller of any door (ARCHITECTURE-FLOWS svc-edges)" % caller)
    return Client(caller, principal, tenant)

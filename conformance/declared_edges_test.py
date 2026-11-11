#!/usr/bin/env python3
"""Declared edges WORK (decision 1c) — for every caller→door edge in ARCHITECTURE-FLOWS, the caller makes a REAL,
PERMITTED call and it SUCCEEDS. Permission proven, not only refusal (the refusal side is net_doors_test / conformance).

Edges come from the spec, never from this file: the three machine-readable blocks of docs/specs/ARCHITECTURE-FLOWS-v0.1.md
— `svc-edges` (doors on the shared client aos_svc), `declared-edges` (the §h doors whose callers still build requests,
DEBT-B179) and `net-doors` (the Network internal doors + gated lists). Every edge MUST have a probe here and every probe
MUST correspond to an edge; a difference fails.

Each probe runs INSIDE THE CALLER'S OWN CONTAINER (docker exec), with that service's own process environment (its Vault
AppRole token, which by policy reads only its own credential): the token is minted as the caller's own principal through
aos_svc.tokens (the one minting code), and a `svc-edges` door is called through aos_svc.client_for(<caller>) — the real
client. A probe passes only on a 2xx that does the door's job (a completion from the stub provider, a stored blob read
back, an installed component run to `ok`, …). Benign inputs only; dev fixtures (installer Phase 15, dev profile) supply the
data a fresh install lacks. Secrets that come back (a run token, a materialized secret) are never printed.

Known failure (XFAIL, with its debt): kernel → runtime-manager /v1/ensure-connector — local-dev does not place components
in containers yet (no Docker socket), DEBT-B181. If it ever succeeds it is XPASS, which fails the matrix until updated.

Runs on the HOST against the running local-dev stack. Writes conformance/results/local-dev-edges.json. Exit 1 on any FAIL.
"""
import json, os, re, subprocess, sys, time
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INST = os.environ.get("INSTANCE", "localdev")
OP = INST + "-operator"
CID = "ds:%s-developer:engine/pipeline-probe-step" % INST
READER = "ds:%s-developer:engine/edge-probe-reader" % INST
KNOWN = {("runtime-manager", "ensure_connector", "kernel"): "DEBT-B181"}

doc = open(os.path.join(ROOT, "docs/specs/ARCHITECTURE-FLOWS-v0.1.md")).read()


def block(name):
    return doc.split("<!-- %s:begin -->" % name, 1)[1].split("<!-- %s:end -->" % name, 1)[0]


def rows(name, ncols):
    out = []
    for l in block(name).splitlines():
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if len(c) == ncols and c[0] not in ("door", "") and not set(c[0]) <= {"-"}:
            out.append(c)
    return out


def callers(cell):
    return [x.strip() for x in cell.split(",") if x.strip() not in ("", "—", "-")]


EDGES = []   # (door, op, method, path, caller, source)
for door, aud, base, op, reqs, to, rt, cs in rows("svc-edges", 8):
    m, p = reqs.split()[:2]
    EDGES += [(door, op, m, p, c, "svc-edges") for c in callers(cs)]
for door, op, reqs, cs in rows("declared-edges", 4):
    m, p = reqs.split()[:2]
    EDGES += [(door, op, m, p, c, "declared-edges") for c in callers(cs)]
for d, cs in [(m.group(2), m.group(3)) if not m.group(1) else ("list " + m.group(2), m.group(3))
              for m in re.finditer(r"^\| (list )?`([^`]+)` \| ([^|]+) \|$", block("net-doors"), re.M)]:
    is_list = d.startswith("list ")
    path = d[5:] if is_list else d
    EDGES += [("network", path, "GET" if is_list else "POST", path, c, "net-doors") for c in callers(cs)]

# ── the probes: (door, op) → request + success test. Built from install facts only (benign inputs). ────────────────────
B64AUDIO = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA="     # a 44-byte empty WAV
P = {
    ("filestore", "put"): {"body_raw": "edge-probe", "ok": "id"},
    ("filestore", "get"): {"fid": True, "ok": "bytes"},
    ("model-gateway", "complete"): {"json": {"messages": [{"role": "user", "content": "declared-edges probe"}]}, "ok": "stub"},
    ("model-gateway", "embed"): {"json": {"texts": ["declared-edges probe"]}, "ok": "vectors"},
    ("model-gateway", "transcribe"): {"json": {"tenant": INST, "audio": B64AUDIO, "mime": "audio/wav"}, "ok": "stub"},
    ("model-gateway", "provider_key"): {"json": {"tenant": "edgeprobe", "component": "ds:edgeprobe:provider/none", "key_secret": "EDGE_PROBE_KEY", "value": "x"}},
    ("model-gateway", "healthz"): {},
    ("notify", "notify"): {"json": {"actor": "user://%s/admin" % INST, "tenant": INST, "kind": "notification", "title": "declared-edges probe",
                                    "source": "declared-edges-net"}, "ok": "201"},
    ("kernel", "inbox_put"): {"via": ("notify", "notify")},       # notify answers 201 ONLY after the kernel's notify lane accepted
    ("scheduler", "reload"): {"json": {}},
    ("scheduler", "run"): {"json": {"component": CID, "tenant": INST, "reason": "declared-edges-net", "env": {"STEP": "edges", "PROBE_RUN": "edges"}},
                           "ok": "status_ok", "timeout": 600},
    ("automation", "events"): {"json": {"subject_schema": "conformance.probe"}},
    ("secrets", "fetch"): {"json": {"url": "http://127.0.0.1:1/"}, "ok": "json_ok"},
    ("secrets", "materialize"): {"json": {"tenant": INST, "component": "ds:%s-developer:fixture/edge-probe" % INST, "name": "EDGE_PROBE_SECRET"}, "secret": True},
    ("runtime-manager", "invoke"): {"json": {"component": "connectors/demo-connector", "run_token": ""}},
    ("runtime-manager", "ensure_connector"): {"json": {"component": "connectors/demo-connector"}},
    ("identity", "realms"): {},
    ("identity", "realm_users"): {"path_args": {"tenant": OP}},
    ("identity", "users_list"): {"query": "?tenant=" + OP},
    ("identity", "users_write"): {"json_self": True},
    ("identity", "set_password"): {"json_self": True, "extra": {"only_if_unset": True}},
    ("identity", "prefs"): {"json_self": True},
    ("kernel", "run_token"): {"json": {"component_id": CID, "tenant": INST}, "secret": True},
    ("network", "runtime_attest"): {"json": {"runtime_id": "ds:%s-developer:runtime/edge-probe" % INST, "node": "declared-edges-net", "local_image_id": "", "match": False}},
    ("network", "/v1/certificates/resolve"): {"json": {"subject_id": CID}},
    ("network", "/v1/directory/resolve"): {"json": {"participant_id": "ds:%s:steward" % INST}},
    ("network", "/v1/grants/resolve"): {"json": {"tenant": INST, "component_id": CID}},
    ("network", "/v1/interfaces/resolve"): {"json": {"interface_id": "dev.edge-probe"}},
    ("network", "/v1/jurisdictions/resolve"): {"json": {"code": "DEV-EDGE"}},
    ("network", "/v1/keys/resolve"): {"json": {"id": "user://%s/edge-probe" % OP}},
    ("network", "/v1/receipts/data-read"): {"json": {"provider": INST, "requester": READER, "schema": "platform.inbox_item", "count": 0,
                                                     "response_digest": "sha2-256:0"}},
    ("network", "/v1/resolve"): {"json": {"ref": "ds:%s:edge-probe" % INST}},
    ("network", "/v1/schemas/resolve"): {"json": {"schema_id": "governance.capability_grant"}},
    ("network", "/v1/service-offerings/resolve"): {"json": {"offering_id": "ds:%s:service_offering/dev-edge-probe" % INST}},
    ("network", "/v1/store/resolve"): {"json": {"component_id": CID}},
    ("network", "/v1/tenants/resolve"): {"json": {"tenant_id": INST}},
    ("network", "/v1/tenants"): {},
    ("network", "/v1/interfaces/bindings"): {},
    ("network", "/v1/join"): {},
}
# the door's base + audience for the doors NOT on the client (the client knows its own from svc-edges)
RAW = {"scheduler": ("http://scheduler:8103", "svc:scheduler"), "automation": ("http://automation:8098", "svc:automation"),
       "secrets": ("http://secrets:8102", "svc:secrets"), "runtime-manager": ("http://runtime-manager:8105", "svc:runtime-manager"),
       "identity": ("http://identity:8093", "svc:identity"), "kernel": ("http://kernel:8080", None),
       "network": ("http://network:8090", "svc:network")}
# caller → (container, principal it signs in as). event-relay runs as localdev-operator/scheduler (ARCHITECTURE-FLOWS §h).
WHO = {"app-host": ("app-host", "app-host"), "kernel": ("kernel", "kernel"), "launcher": ("runtime-manager", "launcher"),
       "scheduler": ("scheduler", "scheduler"), "event-relay": ("event-relay", "scheduler"), "decision": ("decision", "decision"),
       "workflow": ("workflow", "workflow"), "notify": ("notify", "notify"), "provisioner": ("identity", "provisioner"),
       "identity": ("identity", "identity")}

PROBE = r'''
import base64, glob, json, os, sys, urllib.error, urllib.parse, urllib.request
envs = [open(f, "rb").read() for f in sorted(glob.glob("/proc/[0-9]*/environ"), key=lambda x: int(x.split("/")[2])) if os.access(f, os.R_OK)]
env = next((e for e in envs if b"VAULT_TOKEN=" in e), b"")
for kv in env.split(b"\0"):                          # this service's OWN process environment (its Vault AppRole token)
    k, _, v = kv.partition(b"=")
    if k and k.decode() not in ("PATH", "HOME", "HOSTNAME"):
        os.environ[k.decode()] = v.decode()
sys.path.insert(0, "/opt/airawat/lib")
import aos_svc, aos_svc.tokens as T
A = json.loads(os.environ["EDGE_ARGS"]); CALLER, PRINCIPAL, OPR = A["caller"], A["principal"], A["op_tenant"]
out = []
def raw(method, url, body=None, tok=None, raw_body=None, timeout=60):
    h = {"Content-Type": "application/json", "X-Request-Id": aos_svc.current_request_id()}
    if tok: h["Authorization"] = "Bearer " + tok
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=timeout)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()
def mint(aud):
    if CALLER == "identity":
        sys.argv = ["identity.py"]; sys.path.insert(0, "/app/reference"); import identity
        return identity._self_network_token()
    return T.token(PRINCIPAL, OPR, aud)
for e in A["edges"]:
    door, op, method, path, src, p = e["door"], e["op"], e["method"], e["path"], e["source"], e["probe"]
    body = dict(p.get("json") or {})
    if p.get("json_self"): body = dict({"username": PRINCIPAL, "tenant": OPR}, **(p.get("extra") or {}))
    if p.get("fid"): p["path_args"] = {"id": A.get("fid", "")}
    st, b = 0, b""
    with aos_svc.request_context("edges-" + CALLER):
        if src == "svc-edges":                       # THE shared client, as this caller
            try:
                d = aos_svc.client_for(CALLER, principal=PRINCIPAL, tenant=OPR).door(door)
                data = p["body_raw"].encode() if "body_raw" in p else (json.dumps(body).encode() if body else None)
                hdr = {"Content-Type": "application/octet-stream" if "body_raw" in p else "application/json"} if data else None
                with d.open(op, path_args=p.get("path_args"), data=data, headers=hdr, timeout=p.get("timeout", 90)) as r:
                    st, b = r.status, r.read()
            except aos_svc.DoorError as x:
                st, b = x.status, x.reason.encode()
            except Exception as x:
                st, b = 0, ("%s: %s" % (type(x).__name__, x)).encode()
        else:
            base, aud = A["raw"][door]
            tok = mint(aud)
            url = base + path.format(**(p.get("path_args") or {})) + (p.get("query") or "")
            st, b = raw(method, url, body if method != "GET" else None, tok, timeout=p.get("timeout", 60)) if tok else (0, b"no token minted for this caller")
    txt = b.decode("utf-8", "replace")
    ok = 200 <= st < 300; why = ""
    try: j = json.loads(txt)
    except Exception: j = None
    k = p.get("ok")
    if ok and k == "id": ok = bool(isinstance(j, dict) and str(j.get("id", "")).startswith("sha2-256:")); why = "stored id" if ok else "no id"
    if ok and k == "bytes": ok = txt == "edge-probe"; why = "read back the stored bytes" if ok else "bytes differ"
    if ok and k == "stub": ok = "[stub-provider]" in txt; why = "answered by the stub provider" if ok else "not the stub's answer"
    if ok and k == "vectors": ok = bool(isinstance(j, dict) and j.get("vectors")); why = "provider %s" % ((j or {}).get("provider"))
    if ok and k == "201": ok = st == 201; why = "delivered (201)"
    if ok and k == "status_ok": ok = isinstance(j, dict) and j.get("status") == "ok"; why = "run status %s" % ((j or {}).get("status"))
    if ok and k == "json_ok": ok = isinstance(j, dict) and j.get("ok") is True; why = "answered ok"
    if e["op"] == "invoke" and isinstance(j, dict): why = "exit_code %s (placement verdict)" % j.get("exit_code")
    detail = "(secret value withheld)" if p.get("secret") else txt[:160]
    if door == "filestore" and op == "put" and isinstance(j, dict): A["fid"] = j.get("id", "")
    out.append({"door": door, "op": op, "caller": CALLER, "status": st, "ok": ok, "why": why, "detail": detail, "fid": A.get("fid")})
print("OUT " + json.dumps(out))
'''

cases, bad = [], 0


def rec(name, kind, detail, rules=("ARC-1", "FND-9")):
    global bad
    cases.append({"case": name, "rules": list(rules), "result": kind, "detail": detail})
    print(("  ✓ " if kind == "PASS" else ("  ~ " if kind == "XFAIL" else "  ✗ ")) + "%s %s — %s" % (kind, name, detail[:200]))
    bad += kind in ("FAIL", "XPASS")


print("▶ declared edges work (ARCHITECTURE-FLOWS svc-edges + declared-edges + net-doors): %d edges" % len(EDGES))
keys = {(d, o) for d, o, *_ in EDGES}
rec("every declared edge has a probe, and every probe an edge", "PASS" if keys == set(P) else "FAIL",
    "edges without a probe %s; probes without an edge %s" % (sorted(keys - set(P)), sorted(set(P) - keys)))
unknown = sorted({c for *_, c, _s in EDGES if c not in WHO})
rec("every declared caller is a running service this net can act as", "PASS" if not unknown else "FAIL", "unknown callers %s" % unknown)

ORDER = ["app-host", "kernel", "launcher", "scheduler", "event-relay", "decision", "workflow", "notify", "provisioner", "identity"]
RES, fid = {}, ""
for caller in ORDER:
    mine = [e for e in EDGES if e[4] == caller and "via" not in P.get((e[0], e[1]), {})]
    if not mine:
        continue
    cont, princ = WHO[caller]
    args = {"caller": caller, "principal": princ, "op_tenant": OP, "fid": fid, "raw": RAW,
            "edges": [{"door": d, "op": o, "method": m, "path": p, "source": s, "probe": P[(d, o)]} for d, o, m, p, c, s in mine]}
    r = subprocess.run(["docker", "exec", "-e", "EDGE_ARGS=" + json.dumps(args), "airawat-ld-" + cont, "python3", "-c", PROBE],
                       capture_output=True, text=True, timeout=1500)
    m = re.search(r"^OUT (.*)$", r.stdout, re.M)
    if not m:
        for d, o, *_ in mine:
            RES[(d, o, caller)] = {"ok": False, "status": 0, "why": "", "detail": "probe did not run in %s: %s" % (cont, (r.stderr or r.stdout)[-200:])}
        continue
    for x in json.loads(m.group(1)):
        RES[(x["door"], x["op"], caller)] = x
        fid = x.get("fid") or fid

for d, o, mth, pth, c, s in sorted(EDGES, key=lambda e: (e[0], e[1], e[4])):
    name = "%s → %s %s (%s %s)" % (c, d, o, mth, pth)
    via = P[(d, o)].get("via")
    if via:
        dep = [RES.get((via[0], via[1], cc)) for cc in ("decision", "workflow")]
        ok = all(x and x.get("ok") for x in dep)
        rec(name, "PASS" if ok else "FAIL", "proven through %s.%s: notify answered 201 only after the kernel accepted its write (%s)"
            % (via[0], via[1], [x and x.get("status") for x in dep]))
        continue
    x = RES.get((d, o, c)) or {"ok": False, "status": 0, "why": "", "detail": "not probed"}
    debt = KNOWN.get((d, o, c))
    kind = ("XPASS" if x["ok"] else "XFAIL") if debt else ("PASS" if x["ok"] else "FAIL")
    rec(name, kind, "%s%s %s · %s" % ("[known: %s] " % debt if debt else "", x["status"], x.get("why") or "", x.get("detail", "")))

os.makedirs(os.path.join(ROOT, "conformance", "results"), exist_ok=True)
OUTF = os.path.join(ROOT, "conformance", "results", "local-dev-edges.json")
json.dump({"env": "local-dev", "mode": "edges", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "", "cases": cases},
          open(OUTF, "w"), indent=1)
_ev.seal(OUTF)
n_pass = sum(c["result"] == "PASS" for c in cases)
print(("✗" if bad else "✓") + " declared edges: %d PASS, %d known failure(s), %d FAIL/XPASS" % (n_pass, sum(c["result"] == "XFAIL" for c in cases), bad))
sys.exit(1 if bad else 0)

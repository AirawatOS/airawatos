#!/usr/bin/env python3
"""Restore DRILL: back up, destroy, restore, prove nothing was lost (slice-1h, DEBT-B102 / re-review R4-2).

  1. MARK: a self-registered citizen (identity volume), a component secret (Vault KV), the registry row count
     (Postgres), the identity JWKS (Vault transit keys), a file in each of the filestore and app-bundles volumes.
  2. BACK UP with deploy/local-dev/backup.sh (quiesced, every durable volume + host secrets, checksummed manifest).
  3. DESTROY: `docker compose down -v` — proven: no container and no volume of the project remains.
  4. RESTORE with deploy/local-dev/restore.sh — the stack must come back healthy (RTO recorded).
  5. PROVE, BEFORE ANY ROOT TOKEN EXISTS (slice-1k, DEBT-B160b): the restored Vault holds no root token, and every
     Vault-using service is healthy and reads its OWN paths with its OWN token.
  6. Only then a root token is generated ON DEMAND (vault_root.py) for the checks that need one: every mark is back; the
     JWKS is identical; every service still reads only its own Vault paths (vault_scope_test.py).
  7. REVOKE every root token found by accessor enumeration — incl. the pre-backup one restored with Vault's storage
     (DEBT-B161) — and FAIL if any root token remains at the end (DEBT-B160a/c).
Writes conformance/results/local-dev-restoredrill.json. Exit 1 on any failure.
"""
import json, os, re, subprocess, sys, tempfile, time, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402

P = "airawatos-localdev"
LD = os.path.join(ROOT, "deploy/local-dev")
C = ["docker", "compose", "-p", P, "--project-directory", LD, "-f", os.path.join(LD, "docker-compose.dev.yml")]
cases, bad = [], 0
TAG = "drill" + uuid.uuid4().hex[:8]


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def check(name, ok, detail):
    global bad
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail, flush=True)
    cases.append({"case": name, "rules": ["ARC-3", "ARC-7"], "result": "PASS" if ok else "FAIL", "detail": detail[:300]})
    bad += (not ok)


def net_py(code):
    return sh("docker", "exec", "airawat-ld-network", "python3", "-c", code).stdout.strip()


def vroot(*args):
    vr = sh("docker", "exec", "airawat-ld-vault", "sh", "-lc",
            'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"').stdout.strip()
    return sh("docker", "exec", "-e", "VAULT_TOKEN=" + vr, "-e", "VAULT_ADDR=http://127.0.0.1:8200", "airawat-ld-vault", *args)


def _volumes():
    cfg = json.loads(sh(*C, "config", "--format", "json").stdout)
    return sorted(cfg.get("volumes", {}))


_TAR_IMG = None


def _volmark(v, write=False):
    """slice-1h (R7-2): EVERY durable volume carries a marker file — a volume left out of the backup set loses it."""
    global _TAR_IMG
    if not _TAR_IMG:
        _TAR_IMG = json.loads(sh(*C, "config", "--format", "json").stdout)["services"]["vault"]["image"]
    cmd = ("echo %s > /v/.drill-%s" % (TAG, TAG)) if write else ("cat /v/.drill-%s 2>/dev/null" % TAG)
    name = json.loads(sh(*C, "config", "--format", "json").stdout)["volumes"][v]["name"]   # slice-1k: the ACTIVE set's volume
    return sh("docker", "run", "--rm", "--user", "0:0", "--entrypoint", "sh", "-v", "%s:/v" % name, _TAR_IMG, "-c", cmd).stdout.strip()


def marks():
    m = {"vol:" + v: _volmark(v) for v in _volumes()}
    m["citizen"] = TAG in sh("docker", "exec", "airawat-ld-identity", "sh", "-c", "cat /data/identity/identity-users.json").stdout
    m["vault_secret"] = vroot("vault", "kv", "get", "-field=value", "components/drill/" + TAG).stdout.strip()
    m["registry_rows"] = sh("docker", "exec", "airawat-ld-postgres", "sh", "-c",
                            'psql -U "$POSTGRES_USER" -d kernel -tAc "select count(*) from registry_version"').stdout.strip()
    m["jwks"] = net_py("import urllib.request;print(urllib.request.urlopen('http://identity:8093/jwks',timeout=5).read().decode())")
    m["filestore"] = sh("docker", "exec", "airawat-ld-filestore", "cat", "/data/filestore/" + TAG).stdout.strip()
    m["appbundles"] = sh("docker", "exec", "airawat-ld-app-host", "cat", "/data/app-bundles/" + TAG).stdout.strip()
    return m


print("▶ restore drill (B102): mark → back up → destroy → restore → prove", flush=True)
_g0 = sh(sys.executable, os.path.join(LD, "vault_root.py"), "generate")     # slice-1k: root ON DEMAND (the marks need it)
if _g0.returncode:
    print("  ✗ could not obtain a root token on demand: " + (_g0.stdout + _g0.stderr).strip()[:200]); sys.exit(1)
reg = net_py("import json,urllib.request;r=urllib.request.Request('http://identity:8093/register',data=json.dumps({'username':'%s'}).encode(),"
             "headers={'Content-Type':'application/json'});print(urllib.request.urlopen(r,timeout=10).status)" % TAG)
vroot("vault", "kv", "put", "components/drill/" + TAG, "value=" + TAG)
sh("docker", "exec", "--user", "0:0", "airawat-ld-filestore", "sh", "-c", "echo %s > /data/filestore/%s" % (TAG, TAG))
sh("docker", "exec", "--user", "0:0", "airawat-ld-app-host", "sh", "-c", "echo %s > /data/app-bundles/%s" % (TAG, TAG))
for _v in _volumes():
    _volmark(_v, write=True)
before = marks()
check("marks written before the backup (incl. a marker on every one of %d volumes)" % len([k for k in before if k.startswith("vol:")]),
      reg == "200" and all(before.values()) and before["citizen"],
      "citizen %s, secret %s, rows %s, jwks %d bytes, filestore %s, appbundles %s" % (
          before["citizen"], bool(before["vault_secret"]), before["registry_rows"], len(before["jwks"]), bool(before["filestore"]), bool(before["appbundles"])))
with tempfile.TemporaryDirectory(prefix="aos-drill-") as td:
    b = sh(os.path.join(LD, "backup.sh"), os.path.join(td, "bk"))
    check("backup.sh took a consistent backup of every volume + host secrets", b.returncode == 0, (b.stdout + b.stderr).strip().splitlines()[-1][:200])
    sh(*C, "down", "-v", "--remove-orphans")
    left_c = sh("docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + P).stdout.split()
    left_v = sh("docker", "volume", "ls", "-q", "--filter", "label=com.docker.compose.project=" + P).stdout.split()
    check("the stack was DESTROYED (no container, no volume)", not left_c and not left_v, "containers %d, volumes %s" % (len(left_c), left_v or "none"))
    # slice-1i (DEBT-B134) / slice-1k: restore to a NEW host — the WHOLE host-side layout (every volume set's host secrets,
    # the active pointer and the .env / vault/approle links) is DELETED before the restore and must come back
    import hashlib, glob as _g, shutil as _sh
    hostfiles = [os.path.join(LD, ".env")] + sorted(_g.glob(os.path.join(LD, "vault/approle/*.env")))
    strip = lambda b: b"\n".join(l for l in b.split(b"\n") if not l.startswith(b"AOS_VOLSET="))   # the set name differs by design
    host_before = {os.path.relpath(f, LD): hashlib.sha256(strip(open(f, "rb").read())).hexdigest() for f in hostfiles}
    _sh.rmtree(os.path.join(LD, "sets"), ignore_errors=True)
    for f in (os.path.join(LD, ".env"), os.path.join(LD, "vault/approle")):
        if os.path.islink(f):
            os.unlink(f)
    check("host secrets DELETED before the restore (a new host)",      # case name kept: the evidence baseline keys on it
          not os.path.exists(os.path.join(LD, "sets")) and not os.path.lexists(os.path.join(LD, ".env")),
          "%d files removed; no volume set, no pointer, no .env link left" % len(hostfiles))
    r = sh(os.path.join(LD, "restore.sh"), os.path.join(td, "bk"))
    host_after = {k: (hashlib.sha256(strip(open(os.path.join(LD, k), "rb").read())).hexdigest() if os.path.exists(os.path.join(LD, k)) else None)
                  for k in host_before}
    check("restore brought back every host secret byte-identical (.env + %d AppRole env files)" % (len(hostfiles) - 1),
          host_after == host_before, "missing/changed: %s" % [k for k in host_before if host_after[k] != host_before[k]])
    check("restore.sh restored every volume and the stack is healthy", r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-1][:200])
# ── slice-1k (DEBT-B160b): BEFORE any root token exists — the services must work on their OWN credentials ────────────
VR = [sys.executable, os.path.join(LD, "vault_root.py")]
st = sh(*VR, "status").stdout.strip()
check("after the restore the Vault holds NO root token at rest (none regenerated at start)", st == "absent", "init.json root token: %s" % st)
sys.path.insert(0, os.path.join(ROOT, "conformance"))
import vault_scope_test as _vst  # noqa: E402  (probe/caps use each container's OWN token — no root)
for svc, (own, foreign) in sorted(_vst.TIGHT.items()):
    o = _vst.probe(svc, own, foreign)
    check("BEFORE root: %s reads its own Vault path with its OWN token (and not a foreign one)" % svc,
          bool(o.get("TOKEN")) and o.get("OWN") in ("200", "404") and o.get("FOREIGN") == "403",
          "own %s -> %s; foreign -> %s" % (own, o.get("OWN"), o.get("FOREIGN")))
for svc, comp in sorted(_vst.BROKERS.items()):
    cp = "%s/data/%s" % (_vst.COMPONENT_MOUNT, comp)
    cc = _vst.caps(svc, [cp])["CAP"].get(cp)
    check("BEFORE root: %s may read+write its component mount with its OWN token" % svc, _vst.granted(cc) and _vst.granted(cc, write=True), "%s caps=%s" % (cp, cc))
hs = sh("docker", "ps", "-a", "--filter", "label=com.docker.compose.project=" + P, "--format", "{{.Names}}|{{.Status}}").stdout.splitlines()
check("BEFORE root: every service healthy", hs and all("(healthy)" in x or "nginx" in x for x in hs), "%d containers" % len(hs))
# ── only now: a root token ON DEMAND for the checks that need one ────────────────────────────────────────────────────
g = sh(*VR, "generate")
check("a root token generated ON DEMAND (generate-root with the unseal key) for the root-only checks", g.returncode == 0, (g.stdout + g.stderr).strip()[:150])
after = marks()
for k in ["citizen", "vault_secret", "registry_rows", "filestore", "appbundles"] + sorted(x for x in before if x.startswith("vol:")):
    check("restored: %s identical" % k, after[k] == before[k] and bool(after[k]), "before %r / after %r" % (str(before[k])[:40], str(after[k])[:40]))
check("restored: identity's signing keys identical (JWKS) — tokens issued before the restore still verify",
      after["jwks"] == before["jwks"] and bool(after["jwks"]), "%d bytes" % len(after["jwks"]))
vs = sh(sys.executable, os.path.join(ROOT, "conformance/vault_scope_test.py"))
check("after the restore every service reads its own Vault paths (AppRole logins intact)", vs.returncode == 0,
      (vs.stdout.strip().splitlines() or ["?"])[-1])
vroot("vault", "kv", "metadata", "delete", "components/drill/" + TAG)
# ── slice-1k (DEBT-B161 / B160a,c): revoke EVERY root token (incl. the pre-backup one restored with Vault's storage) ─────
rv = sh(*VR, "revoke-all")
n = int(re.search(r"revoked (\d+)", rv.stdout).group(1)) if re.search(r"revoked (\d+)", rv.stdout) else 0
check("every root token REVOKED by accessor enumeration as soon as the post-restore checks finished (incl. the pre-backup root)",
      rv.returncode == 0 and n >= 2, "%s (want ≥ 2: the restored pre-backup root + the on-demand one)" % (rv.stdout.strip() or rv.stderr.strip())[:160])
vn = sh(*VR, "verify-none")
check("NO root token remains at the end of the drill (probe enumeration finds none; init.json blank)", vn.returncode == 0, vn.stdout.strip()[:160])
evidence.write("restoredrill", cases)
print(("✗" if bad else "✓") + " restore drill: %d failure(s)" % bad)
sys.exit(1 if bad else 0)

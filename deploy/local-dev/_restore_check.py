#!/usr/bin/env python3
"""restore.sh step 1+2 (slice-1j, DEBT-B139/B140): validate a backup against the DECLARED stack and scan every archive
member. Prints "<lists-dir> <vol> <vol> …" on success; exits non-zero with the reasons otherwise.
  _restore_check.py <backup-dir> <compose-file>
"""
import hashlib, json, os, posixpath, re, sys, tarfile
d, cf = sys.argv[1], sys.argv[2]
src = open(cf).read()
# the compose file's top-level `volumes:` block (keys at two-space indent) and every AppRole env file it references
blk = re.search(r"^volumes:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", src, re.M)
declared = sorted(re.findall(r"^  ([A-Za-z0-9_.-]+):", blk.group(1), re.M)) if blk else []
roles = sorted(set(re.findall(r"vault/approle/([A-Za-z0-9_-]+)\.env", src)))
errs = []
if not declared:
    errs.append("could not read the declared volumes from %s" % cf)
try:
    m = json.load(open(os.path.join(d, "manifest.json")))
except Exception as e:
    raise SystemExit("✗ manifest.json missing or unreadable: %s" % e)
vols, host = m.get("volumes") or {}, m.get("host") or {}
present = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".tgz"))
hostf = sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(os.path.join(d, "host")) for f in fs)
need_host = sorted(["host/.env"] + ["host/approle/%s.env" % r for r in roles])
for what, have in (("manifest volumes", sorted(vols)), ("archives present", present)):
    miss, extra = sorted(set(declared) - set(have)), sorted(set(have) - set(declared))
    if miss: errs.append("%s MISSING declared volume(s) %s" % (what, miss))
    if extra: errs.append("%s include UNDECLARED volume(s) %s" % (what, extra))
for what, have in (("manifest host files", sorted(host)), ("host files present", hostf)):
    miss, extra = sorted(set(need_host) - set(have)), sorted(set(have) - set(need_host))
    if miss: errs.append("%s MISSING %s" % (what, miss))
    if extra: errs.append("%s include UNEXPECTED %s" % (what, extra))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
for v, h in vols.items():
    p = os.path.join(d, v + ".tgz")
    if os.path.exists(p) and sha(p) != h: errs.append("%s.tgz does not match its sha256" % v)
for f, h in host.items():
    p = os.path.join(d, f)
    if os.path.isfile(p) and sha(p) != h: errs.append("host file %s does not match its sha256" % f)
for r in roles:
    p = os.path.join(d, "host/approle/%s.env" % r)
    if os.path.isfile(p):
        kv = dict(l.split("=", 1) for l in open(p).read().splitlines() if "=" in l)
        if not kv.get("VAULT_ROLE_ID", "").strip() or not kv.get("VAULT_SECRET_ID", "").strip():
            errs.append("host/approle/%s.env lacks VAULT_ROLE_ID / VAULT_SECRET_ID" % r)
if errs:
    raise SystemExit("✗ backup does not validate against the declared stack — refusing to restore:\n    " + "\n    ".join(errs))
def bad_member(t):
    n = t.name
    parts = [x for x in n.split("/") if x not in ("", ".")]
    if n.startswith("/") or ".." in parts: return "path outside the volume"
    if t.isdev() or t.isfifo(): return "device/fifo member"
    if t.issym() or t.islnk():
        tgt = t.linkname
        base = posixpath.dirname("/".join(parts)) if t.issym() else ""
        if tgt.startswith("/") or posixpath.normpath(posixpath.join(base, tgt)).split("/")[0] == "..":
            return "link to %s (outside the volume)" % tgt
    return None
listing = {}
for v in declared:
    p = os.path.join(d, v + ".tgz")
    names = {"."}
    try:
        with tarfile.open(p, "r:gz") as tf:
            for t in tf:            # iterating decompresses the WHOLE archive (integrity)
                why = bad_member(t)
                if why: errs.append("%s.tgz: member %r — %s" % (v, t.name, why))
                parts = [x for x in t.name.split("/") if x not in ("", ".")]
                for i in range(1, len(parts) + 1): names.add("./" + "/".join(parts[:i]))
    except Exception as e:
        errs.append("%s.tgz is not a readable gzip/tar archive (%s)" % (v, e))
    listing[v] = sorted(names)
if errs:
    raise SystemExit("✗ archive scan failed — refusing to restore:\n    " + "\n    ".join(errs[:20]))
import tempfile
ld = tempfile.mkdtemp(prefix="aos-restore-lists-")
for v, ns in listing.items():
    open(os.path.join(ld, v), "w").write("\n".join(ns) + "\n")
sys.stderr.write("  ✓ validated against the declared stack: %d volumes, .env + %d AppRole files; every member scanned\n" % (len(declared), len(roles)))
print(ld + " " + " ".join(declared))

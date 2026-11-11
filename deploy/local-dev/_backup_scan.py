#!/usr/bin/env python3
"""No backup may carry a Vault ROOT TOKEN (slice-1j step 4).

Scans every archive member (full decompression) and every host file of a backup directory for:
  1. a non-empty "root_token" field (Vault's init.json — the cause: the local-dev Vault keeps its init output, root token
     included, on its own data volume, and backup.sh archived that volume as-is);
  2. the LIVE root token's value, anywhere (AOS_ROOT_TOKEN, when the caller knows it);
  3. any Vault service/batch token literal (hvs.… / hvb.…, the Vault ≥1.10 formats this stack issues) in clear text.
Vault's own storage is barrier-encrypted and its audit log HMACs tokens, so a clean backup has no hit.
  _backup_scan.py <backup-dir>      exit 0 = clean; 1 = a token was found (each hit named, never printed)
"""
import os, re, sys, tarfile

PAT = [
    (re.compile(rb'"root_token"\s*:\s*"[^"\s]+"'), "a non-empty root_token field"),
    (re.compile(rb'(?<![A-Za-z0-9_.-])hv[sb]\.[A-Za-z0-9_-]{20,}'), "a Vault token literal (hvs./hvb.)"),
]


def hits(data, live):
    out = [why for rx, why in PAT if rx.search(data)]
    if live and live.encode() in data:
        out.append("the LIVE root token")
    return out


def scan(d, live=""):
    found = []
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if f.endswith(".tgz"):
            try:
                with tarfile.open(p, "r:gz") as tf:
                    for t in tf:
                        if t.isfile():
                            for why in hits(tf.extractfile(t).read(), live):
                                found.append("%s:%s — %s" % (f, t.name, why))
            except Exception as e:
                found.append("%s — unreadable (%s)" % (f, e))
    for r, _, fs in os.walk(os.path.join(d, "host")):
        for f in fs:
            p = os.path.join(r, f)
            for why in hits(open(p, "rb").read(), live):
                found.append("%s — %s" % (os.path.relpath(p, d), why))
    return found


if __name__ == "__main__":
    found = scan(sys.argv[1], os.environ.get("AOS_ROOT_TOKEN", ""))
    if found:
        sys.stderr.write("✗ the backup carries a Vault ROOT/SERVICE TOKEN — a backup must never hold one:\n    "
                         + "\n    ".join(found[:20]) + "\n")
        sys.exit(1)
    sys.stderr.write("  ✓ no Vault root (or any) token in any archive or host file\n")

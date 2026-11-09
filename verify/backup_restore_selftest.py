#!/usr/bin/env python3
"""Backup/restore must validate before it destroys, and a failed backup must never leave the stack down (slice-1i,
DEBT-B124/B126). Live; takes ONE real backup, then works on corrupted COPIES of it:

  restore must REFUSE — exit non-zero, and the running stack must be UNTOUCHED (same containers, still running):
    1. the final review's case: an empty manifest + a corrupted pg archive
    2. the final review's case: host/.env missing from the backup
    3. an EXTRA archive the manifest does not list
    4. an AppRole env file edited after the backup (hash mismatch)
    5. a corrupted archive whose manifest hash was recomputed to match (only a test-extract catches it)
  backup must FAIL LOUDLY and RESTART the stack:
    6. a volume missing mid-backup
    7. an output directory inside the repository that is not the gitignored default
Exit 1 on failure.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LD = os.path.join(ROOT, "deploy/local-dev")
P = "airawatos-localdev"
fails = []


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def stack():
    return sorted(sh("docker", "ps", "--filter", "label=com.docker.compose.project=" + P, "--format", "{{.ID}} {{.State}}").stdout.split("\n"))


def check(name, ok, detail):
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail, flush=True)
    if not ok:
        fails.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


print("▶ backup/restore self-test (B124/B126)", flush=True)
with tempfile.TemporaryDirectory(prefix="aos-brst-") as td:
    bk = os.path.join(td, "bk")
    b = sh(os.path.join(LD, "backup.sh"), bk)
    check("a real backup succeeds and the stack is running again", b.returncode == 0 and all(" running" in x for x in stack() if x),
          (b.stdout + b.stderr).strip().splitlines()[-1][:120])

    def corrupt_copy(fn):
        c = os.path.join(td, "c"); shutil.rmtree(c, ignore_errors=True); shutil.copytree(bk, c); fn(c); return c

    def man(c, upd):
        m = json.load(open(os.path.join(c, "manifest.json"))); upd(m); json.dump(m, open(os.path.join(c, "manifest.json"), "w"))

    def flip(path):
        b_ = bytearray(open(path, "rb").read()); b_[len(b_) // 2] ^= 0xFF; open(path, "wb").write(bytes(b_))

    cases = [
        ("empty manifest + corrupted pg archive (final-review case)", lambda c: (man(c, lambda m: m.update(volumes={})), flip(os.path.join(c, "localdev_pg.tgz")))),
        ("host/.env missing (final-review case)", lambda c: os.remove(os.path.join(c, "host/.env"))),
        ("an extra archive the manifest does not list", lambda c: shutil.copy(os.path.join(c, "localdev_netfiles.tgz"), os.path.join(c, "localdev_extra.tgz"))),
        ("an AppRole env file edited after the backup", lambda c: open(os.path.join(c, "host/approle/kernel.env"), "a").write("X=1\n")),
        ("corrupted archive with a recomputed matching hash", lambda c: (flip(os.path.join(c, "localdev_identity.tgz")),
                                                                        man(c, lambda m: m["volumes"].update(localdev_identity=sha(os.path.join(c, "localdev_identity.tgz")))))),
    ]
    for name, fn in cases:
        before = stack()
        c = corrupt_copy(fn)
        r = sh(os.path.join(LD, "restore.sh"), c)
        after = stack()
        check("restore REFUSES: %s — stack untouched" % name, r.returncode != 0 and before == after and "REFUSED" in (r.stdout + r.stderr),
              "exit %s; containers unchanged %s; %s" % (r.returncode, before == after, (r.stderr.strip().splitlines() or [""])[0][:100]))
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(td, "bk2"), env=dict(os.environ, AOS_BACKUP_VOLS="localdev_pg localdev_does_not_exist localdev_vault"))
    st = stack()
    check("backup FAILS loudly on a missing volume and the stack is RESTARTED", r.returncode != 0 and "✗ backup FAILED" in r.stderr
          and st and all(" running" in x for x in st if x), "exit %s; %d containers running" % (r.returncode, sum(" running" in x for x in st)))
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(ROOT, "verify", "bk-in-repo"))
    check("backup REFUSES an output directory inside the repo (not the ignored default)", r.returncode != 0 and not os.path.exists(os.path.join(ROOT, "verify", "bk-in-repo")),
          "exit %s" % r.returncode)
print(("✗" if fails else "✓") + " backup/restore self-test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

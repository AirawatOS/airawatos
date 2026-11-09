#!/usr/bin/env python3
"""Backup/restore must validate against the DECLARED stack, stage before it switches, and roll back if the restored stack
is not healthy (slice-1i DEBT-B124/B126; slice-1j DEBT-B139/B140). Live; takes ONE real backup, then works on COPIES:

  restore must REFUSE — exit non-zero, and the running stack must be UNTOUCHED (same containers, still running):
     1. (final review) an empty manifest + a corrupted pg archive
     2. (final review) host/.env missing from the backup
     3. an EXTRA archive the manifest does not list
     4. an AppRole env file edited after the backup (hash mismatch)
     5. a corrupted archive whose manifest hash was recomputed to match
     6. (conditions review F-C4-1) a SELF-CONSISTENT backup of 6 of the 7 declared volumes (filestore left out)
     7. (conditions review F-C4-1) a self-consistent backup with NO AppRole env files
     8. an archive for a volume compose does NOT declare, listed consistently in the manifest
     9. an AppRole env file for a role compose does not reference
    10. an AppRole env file without VAULT_SECRET_ID (rehashed)
    11. (conditions review F-C4-2) an archive member that is an ABSOLUTE symlink (link-etc -> /etc)
    12. a `../` member
    13. an absolute member path
    14. a hardlink to an absolute path
    15. a relative symlink that escapes the volume (../../etc)
    16. an archive that scans clean but FAILS TO EXTRACT (a file, then a member under it) — caught in the STAGE
  restore must ROLL BACK — exit non-zero, the PREVIOUS state back and healthy:
    17. a backup that validates and stages but whose stack cannot become healthy (decision's secret-id wrong, rehashed);
        a marker written AFTER the backup must still be there afterwards
  backup must FAIL LOUDLY and RESTART the stack:
    18. a volume missing mid-backup
    19. an output directory inside the repository that is not the gitignored default
RESTORE=<path> runs another restore script (e.g. the slice-1i one, to show what it missed). Exit 1 on failure.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LD = os.path.join(ROOT, "deploy/local-dev")
RESTORE = os.environ.get("RESTORE", os.path.join(LD, "restore.sh"))
P = "airawatos-localdev"
fails = []


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def stack():
    return sorted(x for x in sh("docker", "ps", "--filter", "label=com.docker.compose.project=" + P, "--format", "{{.ID}} {{.State}}").stdout.split("\n") if x)


def healthy():
    st = sh("docker", "ps", "-a", "--filter", "label=com.docker.compose.project=" + P, "--format", "{{.Names}}|{{.Status}}").stdout.split("\n")
    st = [x for x in st if x]
    return len(st) >= 17 and all("(healthy)" in x or "nginx" in x for x in st)


def check(name, ok, detail):
    print(("  ✓ " if ok else "  ✗ ") + name + " — " + detail, flush=True)
    if not ok:
        fails.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rehash(c):
    m = json.load(open(os.path.join(c, "manifest.json")))
    m["volumes"] = {f[:-4]: sha(os.path.join(c, f)) for f in os.listdir(c) if f.endswith(".tgz")}
    m["host"] = {os.path.relpath(os.path.join(r, f), c): sha(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(c, "host")) for f in fs}
    json.dump(m, open(os.path.join(c, "manifest.json"), "w"))


def man(c, upd):
    m = json.load(open(os.path.join(c, "manifest.json"))); upd(m); json.dump(m, open(os.path.join(c, "manifest.json"), "w"))


def flip(path):
    b_ = bytearray(open(path, "rb").read()); b_[len(b_) // 2] ^= 0xFF; open(path, "wb").write(bytes(b_))


def add_members(c, vol, members):
    """rewrite <vol>.tgz with extra members: (name, type, linkname-or-data)"""
    p = os.path.join(c, vol + ".tgz")
    src = tarfile.open(p, "r:gz"); buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as out:
        for t in src:
            out.addfile(t, src.extractfile(t) if t.isfile() else None)
        for name, kind, extra in members:
            ti = tarfile.TarInfo(name)
            if kind == "file":
                data = extra.encode(); ti.size = len(data); out.addfile(ti, io.BytesIO(data))
            else:
                ti.type = tarfile.SYMTYPE if kind == "sym" else tarfile.LNKTYPE; ti.linkname = extra; out.addfile(ti)
    src.close(); open(p, "wb").write(buf.getvalue())
    rehash(c)


def edit_member(c, vol, member, fn):
    p = os.path.join(c, vol + ".tgz")
    src = tarfile.open(p, "r:gz"); buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as out:
        for t in src:
            data = src.extractfile(t).read() if t.isfile() else None
            if data is not None and t.name.lstrip("./") == member:
                data = fn(data); t.size = len(data)
            out.addfile(t, io.BytesIO(data) if data is not None else None)
    src.close(); open(p, "wb").write(buf.getvalue())
    rehash(c)


def drop_approle(c):
    shutil.rmtree(os.path.join(c, "host/approle")); rehash(c)


def no_secret(c):
    p = os.path.join(c, "host/approle/workflow.env")
    lines = open(p).readlines()
    open(p, "w").write("".join(l for l in lines if not l.startswith("VAULT_SECRET_ID"))); rehash(c)


def wrong_secret(c):
    p = os.path.join(c, "host/approle/decision.env")
    lines = open(p).readlines()
    open(p, "w").write("".join(("VAULT_SECRET_ID=00000000-0000-0000-0000-000000000000\n" if l.startswith("VAULT_SECRET_ID") else l) for l in lines)); rehash(c)


print("▶ backup/restore self-test (B124/B126/B139/B140) — restore under test: %s" % os.path.relpath(RESTORE, ROOT), flush=True)
with tempfile.TemporaryDirectory(prefix="aos-brst-") as td:
    bk = os.path.join(td, "bk")
    b = sh(os.path.join(LD, "backup.sh"), bk)
    check("a real backup succeeds and the stack is running again", b.returncode == 0 and all(" running" in x for x in stack()),
          (b.stdout + b.stderr).strip().splitlines()[-1][:120])

    def copy(fn):
        c = os.path.join(td, "c"); shutil.rmtree(c, ignore_errors=True); shutil.copytree(bk, c); fn(c); return c

    refuse = [
        ("empty manifest + corrupted pg archive (final-review case)", lambda c: (man(c, lambda m: m.update(volumes={})), flip(os.path.join(c, "localdev_pg.tgz")))),
        ("host/.env missing (final-review case)", lambda c: os.remove(os.path.join(c, "host/.env"))),
        ("an extra archive the manifest does not list", lambda c: shutil.copy(os.path.join(c, "localdev_netfiles.tgz"), os.path.join(c, "localdev_extra.tgz"))),
        ("an AppRole env file edited after the backup", lambda c: open(os.path.join(c, "host/approle/kernel.env"), "a").write("X=1\n")),
        ("corrupted archive with a recomputed matching hash", lambda c: (flip(os.path.join(c, "localdev_identity.tgz")), rehash(c))),
        ("self-consistent backup of 6 of 7 volumes (conditions-review case)", lambda c: (os.remove(os.path.join(c, "localdev_filestore.tgz")), rehash(c))),
        ("self-consistent backup with no AppRole files (conditions-review case)", drop_approle),
        ("an archive for an UNDECLARED volume, consistently listed", lambda c: (shutil.copy(os.path.join(c, "localdev_netfiles.tgz"), os.path.join(c, "localdev_bogus.tgz")), rehash(c))),
        ("an AppRole file for a role compose does not reference", lambda c: (shutil.copy(os.path.join(c, "host/approle/kernel.env"), os.path.join(c, "host/approle/rogue.env")), rehash(c))),
        ("an AppRole file without VAULT_SECRET_ID", no_secret),
        ("archive member: ABSOLUTE symlink link-etc -> /etc (conditions-review case)", lambda c: add_members(c, "localdev_netfiles", [("./link-etc", "sym", "/etc")])),
        ("archive member: ../escape", lambda c: add_members(c, "localdev_netfiles", [("../escape", "file", "x")])),
        ("archive member: absolute path /abs", lambda c: add_members(c, "localdev_netfiles", [("/abs", "file", "x")])),
        ("archive member: hardlink to /etc/passwd", lambda c: add_members(c, "localdev_netfiles", [("./hl", "lnk", "/etc/passwd")])),
        ("archive member: relative symlink escaping the volume", lambda c: add_members(c, "localdev_netfiles", [("./d/up", "sym", "../../etc")])),
        ("archive that scans clean but fails to EXTRACT (file, then a member under it)", lambda c: add_members(c, "localdev_netfiles", [("./blk", "file", "x"), ("./blk/under", "file", "y")])),
    ]
    for name, fn in refuse:
        before = stack()
        c = copy(fn)
        r = sh(RESTORE, c)
        after = stack()
        out = r.stdout + r.stderr
        check("restore REFUSES: %s — stack untouched" % name, r.returncode != 0 and before == after and "REFUSED" in out,
              "exit %s; containers unchanged %s; %s" % (r.returncode, before == after, ([l for l in out.splitlines() if "✗" in l] or [""])[0][:110]))
        if before != after and not healthy():
            print("    ↳ the stack was changed — recovering with a restore of the good backup", flush=True)
            sh(os.path.join(LD, "restore.sh"), bk)
    # 17. rollback
    sh("docker", "exec", "--user", "0:0", "airawat-ld-filestore", "sh", "-c", "echo after-backup > /data/filestore/.brst-mark")
    c = copy(wrong_secret)
    r = sh(RESTORE, c, env=dict(os.environ, AOS_RESTORE_WAIT_S="75"))
    mark = sh("docker", "exec", "airawat-ld-filestore", "cat", "/data/filestore/.brst-mark").stdout.strip()
    ok = r.returncode != 0 and "ROLLED BACK" in (r.stdout + r.stderr) and mark == "after-backup" and healthy()
    check("restore ROLLS BACK when the restored stack is not healthy (decision secret-id wrong) — previous state back + healthy",
          ok, "exit %s; marker written after the backup %s; stack healthy %s; %s" % (r.returncode, "present" if mark else "GONE", healthy(),
              ([l for l in (r.stdout + r.stderr).splitlines() if "✗" in l] or [""])[-1][:140]))
    if not ok:
        print("    ↳ recovering with a restore of the good backup", flush=True); sh(os.path.join(LD, "restore.sh"), bk)
    sh("docker", "exec", "--user", "0:0", "airawat-ld-filestore", "rm", "-f", "/data/filestore/.brst-mark")
    left = [v for v in sh("docker", "volume", "ls", "-q").stdout.split() if v.startswith(P + "-stage-") or v.startswith(P + "-prev-")]
    check("no staging / previous-state volume is left behind", not left and not os.path.exists(os.path.join(LD, ".restore-prev")), "left: %s" % (left or "none"))
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(td, "bk2"), env=dict(os.environ, AOS_BACKUP_VOLS="localdev_pg localdev_does_not_exist localdev_vault"))
    st = stack()
    check("backup FAILS loudly on a missing volume and the stack is RESTARTED", r.returncode != 0 and "✗ backup FAILED" in r.stderr
          and st and all(" running" in x for x in st), "exit %s; %d containers running" % (r.returncode, sum(" running" in x for x in st)))
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(ROOT, "verify", "bk-in-repo"))
    check("backup REFUSES an output directory inside the repo (not the ignored default)", r.returncode != 0 and not os.path.exists(os.path.join(ROOT, "verify", "bk-in-repo")),
          "exit %s" % r.returncode)
print(("✗" if fails else "✓") + " backup/restore self-test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

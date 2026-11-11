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
    17. (slice-1j step 4) a Vault ROOT TOKEN in the vault archive's init.json; 18. a token literal in a host file;
    19. a token literal in another volume's archive — and the real backup itself must carry NO root token
    20. a backup that validates and stages but whose stack cannot become healthy (decision's secret-id wrong, rehashed);
        a marker written AFTER the backup must still be there afterwards
  backup must FAIL LOUDLY and RESTART the stack:
    21. a volume missing mid-backup
    22. an output directory inside the repository that is not the gitignored default
RESTORE=<path> runs another restore script (e.g. the slice-1i one, to show what it missed). Exit 1 on failure.
"""
import hashlib, io, json, os, re, shutil, signal, subprocess, sys, tarfile, tempfile, time

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


print("▶ backup/restore self-test (B124/B126/B139/B140/B154/B155/B156) — restore under test: %s" % os.path.relpath(RESTORE, ROOT), flush=True)
with tempfile.TemporaryDirectory(prefix="aos-brst-") as td:
    bk = os.path.join(td, "bk")
    b = sh(os.path.join(LD, "backup.sh"), bk)
    check("a real backup succeeds and the stack is running again", b.returncode == 0 and all(" running" in x for x in stack()),
          (b.stdout + b.stderr).strip().splitlines()[-1][:120])

    sys.path.insert(0, LD)
    import _backup_scan
    vr = sh("docker", "exec", "airawat-ld-vault", "sh", "-c", "tr -d '\\n ' < /vault/data/init.json | sed -n 's/.*\"root_token\":\"\\([^\"]*\\)\".*/\\1/p'").stdout.strip()
    hits = _backup_scan.scan(bk, vr)
    blank = b'"root_token": ""' in tarfile.open(os.path.join(bk, "localdev_vault.tgz"), "r:gz").extractfile("./init.json").read()
    check("the backup carries NO Vault root token (init.json root_token blank; no token anywhere; the live root's value absent)",
          blank and not hits, "live root known %s; archived root_token blank %s; hits %s" % (bool(vr), blank, hits or "none"))

    sys.path.insert(0, LD)
    import _sets as _sets_mod
    COMPOSE = ["docker", "compose", "-p", P, "--project-directory", LD, "-f", os.path.join(LD, "docker-compose.dev.yml")]

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
        # slice-1j step 4: a backup must never carry a Vault root (or any) token
        ("a Vault ROOT TOKEN in the vault archive's init.json (the reviewers' backups)",
         lambda c: edit_member(c, "localdev_vault", "init.json", lambda d: re.sub(rb'"root_token": *"[^"]*"', b'"root_token": "hvs.SELFTESTROOTTOKEN0123456789abcd"', d))),
        ("a Vault token literal in a host file (.env)", lambda c: (open(os.path.join(c, "host/.env"), "a").write("VAULT_TOKEN=hvs.SELFTESTTOKEN0123456789abcdefgh\n"), rehash(c))),
        ("a Vault token literal inside another volume's archive", lambda c: add_members(c, "localdev_netfiles", [("./notes.txt", "file", "root=hvs.SELFTESTTOKEN0123456789abcdefgh")])),
    ]
    for name, fn in refuse:
        before = stack()
        c = copy(fn)
        r = sh(RESTORE, c)
        after = stack()
        out = r.stdout + r.stderr
        check("restore REFUSES: %s — stack untouched" % name, r.returncode != 0 and before == after and "REFUSED" in out and _sets_mod.all_sets() == [_sets_mod.active()],
              "exit %s; containers unchanged %s; %s" % (r.returncode, before == after, ([l for l in out.splitlines() if "✗" in l] or [""])[0][:110]))
        if before != after and not healthy():
            print("    ↳ the stack was changed — recovering with a restore of the good backup", flush=True)
            sh(os.path.join(LD, "restore.sh"), bk)
    # ── slice-1k (B154/B155/B156): restore NEVER in place ──────────────────────────────────────────────────────────
    sys.path.insert(0, LD)
    import _sets
    IMG = [l.split()[1] for l in open(os.path.join(LD, "docker-compose.dev.yml")) if l.strip().startswith("image: hashicorp/vault")][0]
    VOLS = _sets.declared_vols()

    def fp_set(s):
        """byte-level fingerprint of a whole set: every file's name/mode/owner/size/mtime + sha256, per volume, + host secrets."""
        h = hashlib.sha256()
        for v in VOLS:
            r = sh("docker", "run", "--rm", "--user", "0:0", "--entrypoint", "sh", "-v", "%s_%s:/v:ro" % (s, v), IMG, "-c",
                   "cd /v && find . -exec stat -c '%n|%a|%u|%g|%s|%Y' {} + | LC_ALL=C sort && find . -type f -exec sha256sum {} + | LC_ALL=C sort")
            vol_ok = sh("docker", "volume", "inspect", "%s_%s" % (s, v)).returncode == 0
            h.update(("%s:%s:%s\n" % (v, vol_ok, hashlib.sha256(r.stdout.encode()).hexdigest() if vol_ok else "MISSING")).encode())
        d = os.path.join(LD, "sets", s)
        for r_, _, fs in sorted(os.walk(d)):
            for f in sorted(fs):
                p = os.path.join(r_, f)
                h.update(("%s:%s\n" % (os.path.relpath(p, d), sha(p))).encode())
        return h.hexdigest()

    def other_sets(prev):
        return sorted(set(_sets.all_sets()) - {prev})

    J = os.path.join(LD, "sets", ".restore-journal")
    PREV = _sets.active()

    def run_restore(c, env=None, pause=None, sig=None, timeout=900):
        e = dict(os.environ, AOS_RESTORE_TEST="1", **(env or {}))
        pf = os.path.join(td, "pause-flag")
        if os.path.exists(pf):
            os.remove(pf)
        if pause:
            e.update(AOS_RESTORE_TEST_PAUSE=pause, AOS_RESTORE_TEST_PAUSE_FILE=pf)
        pr = subprocess.Popen([RESTORE, c], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        reached = None
        if pause:
            t0 = time.time()
            while time.time() - t0 < 300 and pr.poll() is None and not os.path.exists(pf):
                time.sleep(0.3)
            reached = os.path.exists(pf)
            if reached and sig:
                pr.send_signal(sig)
        try:
            out, _ = pr.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            pr.kill(); out, _ = pr.communicate()
        return pr.returncode, out, reached

    def identity_case(name, mutate=None, env=None, pause=None, sig=None):
        """stack STOPPED (so nothing else writes the previous set): run the restore, recover if a journal is left, and
        require the previous set byte-identical, the pointer unchanged, no other set left and no journal."""
        sh(*COMPOSE, "stop")
        before = fp_set(PREV)
        c = copy(mutate or (lambda c: None))
        rc, out, reached = run_restore(c, env=env, pause=pause, sig=sig)
        extra = ""
        if os.path.exists(J):           # SIGKILL: the next restore must REFUSE, then --recover finishes the rollback
            r2 = sh(RESTORE, c)
            refused = r2.returncode != 0 and "interrupted restore" in (r2.stdout + r2.stderr)
            r3 = sh(RESTORE, "--recover")
            extra = "; next restore refused %s; --recover rc %s" % (refused, r3.returncode)
            if not refused or r3.returncode:
                extra += " ✗"
        after = fp_set(PREV)
        ok = (rc != 0 and before == after and _sets.active() == PREV and not other_sets(PREV) and not os.path.exists(J)
              and (pause is None or reached) and "✗" not in extra)
        check("%s → previous set BYTE-IDENTICAL, pointer unchanged, only the new set removed" % name, ok,
              "exit %s%s; previous identical %s; active %s; other sets %s; journal %s%s" % (
                  rc, "" if pause is None else " (stage reached %s)" % reached, before == after, _sets.active() == PREV,
                  other_sets(PREV) or "none", os.path.exists(J), extra))
        if not ok:
            for s_ in other_sets(PREV):
                if s_ != PREV and s_.startswith(P + "-r"):
                    sh(sys.executable, os.path.join(LD, "_sets.py"), "prune", s_)
            if _sets.active() != PREV:
                sh(sys.executable, os.path.join(LD, "_sets.py"), "switch", PREV)

    def corrupt_extract(vol):
        return lambda c: add_members(c, vol, [("./blk", "file", "x"), ("./blk/under", "file", "y")])

    first, middle, last = VOLS[0], VOLS[len(VOLS) // 2], VOLS[-1]
    for pos, vol in (("first", first), ("middle", middle), ("last", last)):
        identity_case("extract FAILS at the %s volume (%s)" % (pos, vol), mutate=corrupt_extract(vol))
    identity_case("disk FULL while staging (%s as a 1 MB tmpfs)" % "localdev_pg", env={"AOS_RESTORE_TEST_TMPFS": "localdev_pg:1m"})
    for stage in ("verified", "secrets", "stopped", "switched", "started"):
        identity_case("injected FAILURE at stage '%s'" % stage, env={"AOS_RESTORE_TEST_FAULT": stage})
    for stage in ("validated", "extract-first", "extract-middle", "extract-last", "verified", "secrets", "stopped", "switched", "started"):
        identity_case("SIGTERM at stage '%s'" % stage, pause=stage, sig=signal.SIGTERM)
        identity_case("SIGKILL at stage '%s'" % stage, pause=stage, sig=signal.SIGKILL)
    identity_case("the new stack never becomes healthy (decision secret-id wrong)", mutate=wrong_secret, env={"AOS_RESTORE_WAIT_S": "60"})
    # the re-check reviewer's case (F-C4-3): a tiny tmpfs where the old restore copied the live volumes aside
    sh("docker", "volume", "create", "--driver", "local", "--opt", "type=tmpfs", "--opt", "device=tmpfs", "--opt", "o=size=64k",
       "%s-prev-localdev_filestore" % P)
    sh(*COMPOSE, "stop")
    before = fp_set(PREV)
    rc, out, _ = run_restore(copy(lambda c: None))
    new = _sets.active()
    sh(*COMPOSE, "stop")
    after = fp_set(PREV)
    ok = rc == 0 and new != PREV and before == after
    check("re-check reviewer's case (a 64 KB tmpfs '-prev-' volume): restore succeeds into a NEW set and the previous set is BYTE-IDENTICAL",
          ok, "exit %s; new active set %s; previous identical %s" % (rc, new if new != PREV else "NONE", before == after))
    sh("docker", "volume", "rm", "-f", "%s-prev-localdev_filestore" % P)
    # B156: a later restore never touches an older set; deleting one is the explicit prune
    sh(*COMPOSE, "up", "-d")
    rc2, out2, _ = run_restore(copy(lambda c: None))
    newer = _sets.active()
    sh(*COMPOSE, "stop")
    still = fp_set(PREV) == before
    check("a SECOND restore leaves BOTH older sets in place (no -prev-/.restore-prev deletion), prev still byte-identical",
          rc2 == 0 and newer not in (PREV, new) and PREV in _sets.all_sets() and new in _sets.all_sets() and still,
          "exit %s; sets now %s; original identical %s" % (rc2, _sets.all_sets(), still))
    r = sh(sys.executable, os.path.join(LD, "_sets.py"), "prune", newer)
    check("prune REFUSES the active set", r.returncode != 0 and "ACTIVE" in (r.stdout + r.stderr), (r.stdout + r.stderr).strip()[:100])
    # back to the original set; the two restored sets are removed by the explicit operator action
    sh(*COMPOSE, "down", "--remove-orphans")      # containers (not volumes) off the restored set before the explicit prune
    sh(sys.executable, os.path.join(LD, "_sets.py"), "switch", PREV)
    for s_ in (new, newer):
        sh(sys.executable, os.path.join(LD, "_sets.py"), "prune", s_)
    sh(*COMPOSE, "up", "-d")
    for _ in range(90):
        if healthy():
            break
        time.sleep(3)
    check("back on the original set, healthy; only it remains", _sets.active() == PREV and _sets.all_sets() == [PREV] and healthy(),
          "active %s; sets %s" % (_sets.active(), _sets.all_sets()))
    # rollback with the stack RUNNING: the previous stack comes back healthy with data written after the backup
    sh("docker", "exec", "--user", "0:0", "airawat-ld-filestore", "sh", "-c", "echo after-backup > /data/filestore/.brst-mark")
    rc, out, _ = run_restore(copy(wrong_secret), env={"AOS_RESTORE_WAIT_S": "75"})
    mark = sh("docker", "exec", "airawat-ld-filestore", "cat", "/data/filestore/.brst-mark").stdout.strip()
    ok = rc != 0 and "ROLLED BACK" in out and mark == "after-backup" and healthy() and _sets.active() == PREV and not other_sets(PREV)
    check("stack RUNNING, restored stack unhealthy → ROLLED BACK: previous stack healthy with data written after the backup, new set removed",
          ok, "exit %s; marker %s; healthy %s; active %s; other sets %s" % (rc, "present" if mark else "GONE", healthy(), _sets.active() == PREV, other_sets(PREV) or "none"))
    sh("docker", "exec", "--user", "0:0", "airawat-ld-filestore", "rm", "-f", "/data/filestore/.brst-mark")
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(td, "bk2"), env=dict(os.environ, AOS_BACKUP_VOLS="localdev_pg localdev_does_not_exist localdev_vault"))
    st = stack()
    check("backup FAILS loudly on a missing volume and the stack is RESTARTED", r.returncode != 0 and "✗ backup FAILED" in r.stderr
          and st and all(" running" in x for x in st), "exit %s; %d containers running" % (r.returncode, sum(" running" in x for x in st)))
    r = sh(os.path.join(LD, "backup.sh"), os.path.join(ROOT, "verify", "bk-in-repo"))
    check("backup REFUSES an output directory inside the repo (not the ignored default)", r.returncode != 0 and not os.path.exists(os.path.join(ROOT, "verify", "bk-in-repo")),
          "exit %s" % r.returncode)
print(("✗" if fails else "✓") + " backup/restore self-test: %d failure(s)" % len(fails))
sys.exit(1 if fails else 0)

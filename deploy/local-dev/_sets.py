#!/usr/bin/env python3
"""Volume SETS for the local-dev stack (slice-1k, DEBT-B154/B155/B156) — restore is NEVER in place.

A set is: a group of Docker volumes named <set>_<vol> (one per volume the compose file declares) + a host-secrets
directory deploy/local-dev/sets/<set>/ holding .env (POSTGRES_PASSWORD, AOS_VOLSET=<set>) and approle/*.env.
ONE pointer selects the live set:
    deploy/local-dev/sets/active      -> <set>              (symlink, replaced ATOMICALLY with os.replace)
    deploy/local-dev/.env             -> sets/active/.env   (compose reads it: AOS_VOLSET names the volumes)
    deploy/local-dev/vault/approle    -> ../sets/active/approle
so every existing compose call, script and test keeps working unchanged, and switching sets is one atomic rename.
restore.sh builds a NEW set beside the live one and only moves the pointer; it never writes or deletes another set.
Deleting a set is a separate, explicit operator action (`prune`), refused for the active set and while a restore
journal exists.

  _sets.py ensure-layout          create the layout (installer); migrates a legacy flat .env + vault/approle/ by MOVING
                                  them unchanged into sets/<project>/ (volume names stay <project>_<vol>)
  _sets.py active                 print the active set name ('' if none)
  _sets.py volname <vol> [set]    print the Docker volume name of <vol> in <set> (default: active)
  _sets.py vols                   print the declared volume keys
  _sets.py switch <set>           atomically point the stack at <set>
  _sets.py list                   every set (dir and/or volumes), the active one marked
  _sets.py prune <set>            delete <set>'s volumes and host-secrets dir (refused for the active set / a journal)
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.environ.get("AOS_LD_PROJECT", "airawatos-localdev")
SETS = os.path.join(HERE, "sets")
ACTIVE = os.path.join(SETS, "active")
ENV_LINK = os.path.join(HERE, ".env")
APPROLE_LINK = os.path.join(HERE, "vault", "approle")
JOURNAL = os.path.join(SETS, ".restore-journal")
CF = os.path.join(HERE, "docker-compose.dev.yml")


def declared_vols():
    src = open(CF).read()
    blk = re.search(r"^volumes:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", src, re.M)
    return sorted(re.findall(r"^  ([A-Za-z0-9_.-]+):", blk.group(1), re.M)) if blk else []


def active():
    try:
        return os.readlink(ACTIVE)
    except OSError:
        return ""


def volname(vol, s=None):
    return "%s_%s" % (s or active() or P, vol)


def _atomic_symlink(target, path):
    tmp = path + ".tmp-%d" % os.getpid()
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    os.symlink(target, tmp)
    os.replace(tmp, path)          # atomic on POSIX, also over an existing symlink-to-directory


def switch(s):
    if not os.path.isdir(os.path.join(SETS, s)):
        raise SystemExit("✗ no such set: %s" % s)
    _atomic_symlink(s, ACTIVE)


def write_env(s, base_text):
    """write sets/<s>/.env from base_text with AOS_VOLSET pinned to <s> (0600)."""
    d = os.path.join(SETS, s)
    os.makedirs(os.path.join(d, "approle"), exist_ok=True)
    lines = [l for l in base_text.splitlines() if not l.startswith("AOS_VOLSET=")]
    fd = os.open(os.path.join(d, ".env"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines + ["AOS_VOLSET=%s" % s]) + "\n")


def ensure_layout():
    os.makedirs(SETS, mode=0o700, exist_ok=True)
    legacy_env = os.path.isfile(ENV_LINK) and not os.path.islink(ENV_LINK)
    legacy_ar = os.path.isdir(APPROLE_LINK) and not os.path.islink(APPROLE_LINK)
    if not active():
        d = os.path.join(SETS, P)
        os.makedirs(os.path.join(d, "approle"), exist_ok=True)
        if legacy_env:                                    # MOVE (bytes unchanged) — the first set keeps <project>_<vol> names
            os.replace(ENV_LINK, os.path.join(d, ".env.legacy"))
        if legacy_ar:
            for f in os.listdir(APPROLE_LINK):
                os.replace(os.path.join(APPROLE_LINK, f), os.path.join(d, "approle", f))
            os.rmdir(APPROLE_LINK)
        base = open(os.path.join(d, ".env.legacy")).read() if os.path.exists(os.path.join(d, ".env.legacy")) else (
            open(os.path.join(d, ".env")).read() if os.path.exists(os.path.join(d, ".env")) else "")
        write_env(P, base)
        if os.path.exists(os.path.join(d, ".env.legacy")):
            os.unlink(os.path.join(d, ".env.legacy"))
        switch(P)
        print("  · volume-set layout created (active set: %s)" % P)
    elif legacy_env or legacy_ar:
        raise SystemExit("✗ both a set layout and a legacy flat .env / vault/approle exist — resolve by hand")
    if not os.path.islink(ENV_LINK):
        _atomic_symlink("sets/active/.env", ENV_LINK)
    if not os.path.islink(APPROLE_LINK):
        _atomic_symlink("../sets/active/approle", APPROLE_LINK)


def set_volumes(s):
    out = subprocess.run(["docker", "volume", "ls", "-q"], capture_output=True, text=True).stdout.split()
    return sorted(v for v in out if v.startswith(s + "_") and v[len(s) + 1:] in declared_vols())


def all_sets():
    names = set()
    if os.path.isdir(SETS):
        names |= {n for n in os.listdir(SETS) if n not in ("active",) and not n.startswith(".") and os.path.isdir(os.path.join(SETS, n))}
    vols = subprocess.run(["docker", "volume", "ls", "-q", "--filter", "label=com.docker.compose.project=" + P],
                          capture_output=True, text=True).stdout.split()
    for v in vols:
        for k in declared_vols():
            if v.endswith("_" + k):
                names.add(v[: -len(k) - 1])
    return sorted(names)


def prune(s):
    if s == active():
        raise SystemExit("✗ refusing to prune the ACTIVE set %s" % s)
    if os.path.exists(JOURNAL):
        raise SystemExit("✗ a restore journal exists (%s) — run restore.sh --recover first" % JOURNAL)
    for v in set_volumes(s):
        r = subprocess.run(["docker", "volume", "rm", v], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("✗ could not remove %s: %s" % (v, r.stderr.strip()[:200]))
    d = os.path.join(SETS, s)
    if os.path.isdir(d):
        import shutil
        shutil.rmtree(d)
    print("  ✓ pruned set %s" % s)


if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "ensure-layout":
        ensure_layout()
    elif a[0] == "active":
        print(active())
    elif a[0] == "volname":
        print(volname(a[1], a[2] if len(a) > 2 else None))
    elif a[0] == "vols":
        print(" ".join(declared_vols()))
    elif a[0] == "switch":
        switch(a[1])
    elif a[0] == "list":
        for s in all_sets():
            print(("* " if s == active() else "  ") + s + "  (%d volumes%s)" % (len(set_volumes(s)), ", host secrets" if os.path.isdir(os.path.join(SETS, s)) else ""))
    elif a[0] == "prune":
        prune(a[1])
    else:
        raise SystemExit(__doc__)

#!/usr/bin/env python3
"""ONE way to write and read assurance-net evidence (slice-1h, DEBT-B99 / re-review R3-5–R3-7, R6-1/R6-2).

Every net writes conformance/results/local-dev-<mode>.json through write(): the file carries the RUN ID of this
`make verify` (AOS_RUN_ID, minted once by the Makefile), the git HEAD of all five repositories and a timestamp, and it
must contain at least one case. The matrix (build_matrix.py) accepts ONLY files of the current run id — stale, missing,
empty or failed evidence fails the build. Outside `make` (a single net run by hand) AOS_RUN_ID is minted here.
"""
import json, os, subprocess, time, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "conformance", "results")
REPOS = {"root": ".", "platform-spec": "platform-spec", "kernel": "kernel", "network": "network", "components": "components"}


def run_id():
    rid = os.environ.get("AOS_RUN_ID")
    if not rid:
        rid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8] + "-adhoc"
        os.environ["AOS_RUN_ID"] = rid
    return rid


def git_heads():
    out = {}
    for k, d in REPOS.items():
        r = subprocess.run(["git", "-C", os.path.join(ROOT, d), "rev-parse", "HEAD"], capture_output=True, text=True)
        dirty = subprocess.run(["git", "-C", os.path.join(ROOT, d), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True).stdout.strip()
        out[k] = (r.stdout.strip() or "?") + ("+dirty" if dirty else "")
    return out


def stamp(doc):
    doc.update({"env": doc.get("env", "local-dev"), "run_id": run_id(), "git": git_heads(),
                "git_sha": git_heads()["root"], "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return doc


def write(mode, cases, **extra):
    """Write the evidence file for `mode`. Refuses an empty case list (a net that checked nothing proves nothing)."""
    if not cases:
        raise SystemExit("✗ evidence for '%s' has ZERO cases — a net that checked nothing cannot pass" % mode)
    os.makedirs(RESULTS, exist_ok=True)
    doc = stamp({"mode": mode, "cases": cases, **extra})
    path = os.path.join(RESULTS, "local-dev-%s.json" % mode)
    with open(path, "w") as f:
        json.dump(doc, f, indent=1)
    return path


def seal(path):
    """Stamp an evidence file JUST WRITTEN by this process (run id, git heads, ts). Refuses zero cases."""
    with open(path) as f:
        doc = json.load(f)
    if not doc.get("cases"):
        raise SystemExit("✗ evidence %s has ZERO cases — a net that checked nothing cannot pass" % os.path.basename(path))
    stamp(doc)
    with open(path, "w") as f:
        json.dump(doc, f, indent=1)
    return path


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["seal"] and len(sys.argv) == 3:
        seal(sys.argv[2]); print("sealed", os.path.basename(sys.argv[2]), "run", run_id())
    elif sys.argv[1:2] == ["new-run-id"]:
        print(time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
    else:
        raise SystemExit("usage: evidence.py seal <results.json> | new-run-id")

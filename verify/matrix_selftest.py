#!/usr/bin/env python3
"""Mutation self-test of the strict matrix (slice-1i, DEBT-B117/B118).

Works on a SCRATCH copy of the latest evidence (re-stamped to the current HEAD and run id so the copy itself is
coherent), records a scratch case baseline from it, then applies one mutation at a time and requires
`build_matrix.py --strict` to FAIL — the real conformance/results, baseline and matrix files are never touched:
  1. the final review's case: internal conformance drops its SKIP_BUILD cases (HELD 5→17 with strict green before)
  2. internal PASS cases silently become SKIP_BUILD
  3. internal cut to ONE case
  4. one file's recorded git heads are from another commit
  5. one file's recorded heads carry a "+dirty" marker
  6. one file carries no git heads at all
MATRIX=<path> runs another copy of build_matrix.py. Exit 1 on failure.
"""
import copy, glob, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "verify"))
import evidence  # noqa: E402
MATRIX = os.environ.get("MATRIX", os.path.join(ROOT, "conformance/build_matrix.py"))
heads, rid = evidence.git_heads(), "selftest-" + evidence.run_id()


def run(td, *extra):
    env = dict(os.environ, AOS_RESULTS_DIR=os.path.join(td, "r"), AOS_EVIDENCE_BASELINE=os.path.join(td, "baseline.json"),
               AOS_MATRIX_OUT_MD=os.path.join(td, "m.md"), AOS_MATRIX_OUT_JSON=os.path.join(td, "m.json"), AOS_RUN_ID=rid)
    return subprocess.run([sys.executable, MATRIX, "--strict"] + list(extra), capture_output=True, text=True, env=env)


def mutate(files, mode, fn):
    for f in files:
        d = json.load(open(f))
        if d.get("mode") == mode:
            fn(d); json.dump(d, open(f, "w"))
            return True
    return False


MUT = [
    ("internal drops its SKIP_BUILD cases (final-review case)", "internal", lambda d: d.update(cases=[c for c in d["cases"] if c["result"] != "SKIP_BUILD"])),
    ("internal PASS cases become SKIP_BUILD", "internal", lambda d: [c.update(result="SKIP_BUILD") for c in d["cases"] if c["result"] == "PASS"]),
    ("internal cut to one case", "internal", lambda d: d.update(cases=d["cases"][:1])),
    ("internal drops HALF of one case group (same normalised name)", "internal", lambda d: d.update(cases=[c for c in d["cases"]
        if not (c["result"] == "PASS" and c["case"].endswith(("0", "1", "2", "3")))])),
    ("git heads from another commit", "flowmap", lambda d: d["git"].update(kernel="0" * 40)),
    ("git heads carry +dirty", "routes", lambda d: d["git"].update(network=d["git"]["network"] + "+dirty")),
    ("no git heads recorded", "listen", lambda d: d.pop("git", None)),
]
fails = []
print("▶ strict-matrix self-test (B117/B118) — matrix under test: %s" % os.path.relpath(MATRIX, ROOT))
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, "r"))
    # a complete, coherent SYNTHETIC evidence set (every required net), stamped with the current HEAD and this run id
    req = ["banned", "gtwstatic", "knownviolations", "functional", "external", "internal", "flowmap", "vaultscope", "netdoors", "edges",
           "routes", "listen", "scans", "vaultrenewal", "dbgrants", "ops", "restoredrill"]
    for m in req:
        cases = [{"case": "%s case %d" % (m, i), "rules": ["ARC-7"], "result": "PASS"} for i in range(8)]
        if m == "internal":
            cases += [{"case": "internal planned case %d" % i, "rules": ["ARC-4"], "result": "SKIP_BUILD"} for i in range(6)]
        json.dump({"env": "local-dev", "mode": m, "run_id": rid, "git": dict(heads), "git_sha": heads["root"],
                   "ts": "2026-11-09T00:00:00Z", "cases": cases}, open(os.path.join(td, "r", "local-dev-%s.json" % m), "w"))
    run(td, "--update-baseline")
    base = run(td)
    print(("  ✓" if base.returncode == 0 else "  ✗") + " baseline: the coherent copy passes strict (exit %d) %s" % (base.returncode, base.stdout.strip().splitlines()[-1][:120] if base.stdout.strip() else ""))
    fails += [] if base.returncode == 0 else ["baseline"]
    pristine = {f: open(f).read() for f in glob.glob(os.path.join(td, "r", "*.json"))}
    for name, mode, fn in MUT:
        for f, t in pristine.items():
            open(f, "w").write(t)
        applied = mutate(list(pristine), mode, fn)
        r = run(td)
        caught = applied and r.returncode != 0
        why = next((l.strip() for l in r.stdout.splitlines() if l.strip().startswith("✗ ")), "")
        print(("  ✓" if caught else "  ✗") + " %s → strict %s %s" % (name, "FAILS" if r.returncode else "STAYED GREEN", why[:110]))
        if not caught:
            fails.append(name)
print(("✗" if fails else "✓") + " strict-matrix self-test: %d of %d mutation(s) not caught" % (len(fails), len(MUT)))
sys.exit(1 if fails else 0)

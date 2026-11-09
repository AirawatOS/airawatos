#!/usr/bin/env python3
"""Generate docs/specs/STATUS-MATRIX.md (+ .json) from conformance results.

Reads every conformance/results/<env>-<mode>.json (written by `run.py --matrix`), groups the cases by the
spec rule they cite, reduces each rule×env to one derived status (worst-first), and writes a rule×environment
status matrix. The conformance results are the single source of truth; the specs reference this file.

Reduction (STATUS-MATRIX-DESIGN.md): FAIL→REGRESSION; XPASS→REVIEW; PASS+XFAIL→PARTIAL; XFAIL (no PASS)→VIOLATED;
any SKIP_BUILD→PLANNED(needs-build) (never HELD — slice-1e); any SKIP_CREDS→UNVERIFIED(creds) (never HELD —
slice-1d); only PASS→HELD; no case→NO TEST.
Environments with no results file are shown PROJECTED (never asserted) per the design's environment-truth limit.

Usage: python3 conformance/build_matrix.py   (run from the repo; reads conformance/results/, writes docs/specs/)
"""
import os, json, glob, collections, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS_DIR = os.environ.get("AOS_RESULTS_DIR") or os.path.join(HERE, "results")
OUT_MD = os.environ.get("AOS_MATRIX_OUT_MD") or os.path.join(REPO, "docs", "specs", "STATUS-MATRIX.md")
OUT_JSON = os.environ.get("AOS_MATRIX_OUT_JSON") or os.path.join(REPO, "docs", "specs", "STATUS-MATRIX.json")

# Full rule inventory per spec (so rules with no test show NO TEST, not silently absent). Numbers per README.
INVENTORY = [
    ("FOUNDATIONS", "FND", [str(i) for i in range(1, 20)]),   # FND-1..FND-19 (FND-18 horizontal safety, FND-19 core-reserved kinds)
    ("REGISTRY",    "REG", [str(i) for i in range(1, 19)]),
    ("DECISION",    "DEC", [str(i) for i in range(1, 13)]),
    ("NETWORK",     "NET", [str(i) for i in range(1, 13)]),
    ("ACCOUNT",     "ACC", [str(i) for i in range(1, 10)] + ["W1", "W2", "W3", "W4"]),
    ("CLIENT",      "CLI", [str(i) for i in range(1, 7)]),
    ("PLATFORM",    "PLT", [str(i) for i in range(1, 22)] + ["5a", "8a"]),
    ("COMPONENT",   "CMP", [str(i) for i in range(1, 19)]),
    ("OFFERINGS",   "OFF", [str(i) for i in range(1, 13)]),
    ("POLICY",      "POL", [str(i) for i in range(1, 9)]),
    ("PARTICIPANT", "PTC", [str(i) for i in range(1, 13)]),
    ("FEDERATION",  "FED", [str(i) for i in range(1, 9)]),
    ("ARCHITECTURE","ARC", [str(i) for i in range(1, 8)]),   # ARC-1..ARC-7 (ARCHITECTURE-FLOWS; flow-map test)
    ("GATEWAY",     "GTW", [str(i) for i in range(1, 15)]),  # GTW-1..GTW-14 (GATEWAY-v0.1, ADR-0130) — slice-1d
]
# Inventory drift guard (slice-1d follow-up): every rule a spec DEFINES (a heading or a first-column table cell)
# must be in INVENTORY, so a newly added rule can never be silently absent from the matrix. Fails the build.
SPEC_FILES = {"FND": "FOUNDATIONS", "REG": "REGISTRY", "DEC": "DECISION", "NET": "NETWORK", "ACC": "ACCOUNT",
              "CLI": "CLIENT", "PLT": "PLATFORM", "CMP": "COMPONENT", "OFF": "OFFERINGS", "POL": "POLICY",
              "PTC": "PARTICIPANT", "FED": "FEDERATION", "ARC": "ARCHITECTURE-FLOWS", "GTW": "GATEWAY"}


def _inventory_drift():
    import re
    have = {p: {rid(p, n) for n in nums} for _, p, nums in INVENTORY}
    missing = []
    for p, f in SPEC_FILES.items():
        path = os.path.join(REPO, "docs", "specs", f + "-v0.1.md")
        if not os.path.exists(path):
            continue
        txt = open(path).read()
        core = r"FED\d+[a-z]?" if p == "FED" else (r"ACC-W?\d+[a-z]?" if p == "ACC" else p + r"-\d+[a-z]?")
        defs = set(re.findall(r"^#+\s*\**(" + core + r")\b", txt, re.M)) | set(re.findall(r"^\|\s*\**(" + core + r")\**\s*\|", txt, re.M))
        missing += sorted(defs - have.get(p, set()))
    return missing


def rid(prefix, n):  # FND + "8" -> FND-8 ; FED + "3" -> FED3 (FED carries no hyphen)
    return ("%s%s" if prefix == "FED" else "%s-%s") % (prefix, n)

_DRIFT = _inventory_drift()
if _DRIFT:
    raise SystemExit("[build_matrix] ✗ rules defined in the specs but missing from INVENTORY (add them): " + ", ".join(_DRIFT))

# env -> rule -> list of (result_kind, case_name)
env_rule = collections.defaultdict(lambda: collections.defaultdict(list))
provenance = {}   # env -> {git_sha, ts, modes:set}
files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")))
# slice-1h (DEBT-B99, re-review R3-7/R6-2): `--strict` (make verify) accepts ONLY fresh, complete, passing evidence of THIS
# run: every file must carry the current AOS_RUN_ID, at least one case and known result kinds; every REQUIRED net must have
# written its file; any FAIL or XPASS fails the build. The matrix is still written, then the build exits non-zero.
STRICT = "--strict" in sys.argv
RUN_ID = os.environ.get("AOS_RUN_ID", "")
REQUIRED = ["banned", "gtwstatic", "knownviolations", "functional", "external", "internal", "flowmap", "vaultscope",
            "netdoors", "routes", "listen", "scans", "vaultrenewal", "dbgrants", "ops", "restoredrill"]
KINDS = {"PASS", "FAIL", "XFAIL", "XPASS", "SKIP_BUILD", "SKIP_CREDS", "needs-build", "needs-creds"}
problems, seen_modes = [], set()
# slice-1i (DEBT-B117): every file's recorded git heads must EQUAL the current HEAD of all five repositories, clean
# (no "+dirty"); slice-1i (DEBT-B118): per-net case BASELINE (verify/evidence-baseline.json) — no baseline case may
# disappear, no baseline PASS may become anything else, SKIP_BUILD may not exceed its ceiling.
import re as _re, subprocess as _sp
sys.path.insert(0, os.path.join(REPO, "verify"))
try:
    import evidence as _evd
    HEADS = _evd.git_heads()
except Exception as _e:
    HEADS = None
BASELINE_FILE = os.environ.get("AOS_EVIDENCE_BASELINE") or os.path.join(REPO, "verify", "evidence-baseline.json")
BASE = json.load(open(BASELINE_FILE)) if os.path.exists(BASELINE_FILE) else {}
UPDATE_BASELINE = "--update-baseline" in sys.argv
def _norm(name):
    # run-specific parts of a case name — generated ids (hex runs with a digit, e.g. a random user fnuserab12cbf) and
    # counts — collapse to '#', so the same case keeps the same key across runs
    n = _re.sub(r"[0-9a-f]*\d[0-9a-f]*", "#", name or "")
    return _re.sub(r"#+", "#", n).strip()
if STRICT and HEADS is None:
    problems.append("cannot read the current git heads (verify/evidence.py)")
if STRICT and HEADS and any(v.endswith("+dirty") for v in HEADS.values()):
    problems.append("the working tree is DIRTY (%s) — evidence must come from committed code" % sorted(k for k, v in HEADS.items() if v.endswith("+dirty")))
new_base = {}
if STRICT and not RUN_ID:
    problems.append("no AOS_RUN_ID — strict mode needs the run id of this make verify")
for f in files:
    d = json.load(open(f))
    seen_modes.add(d.get("mode"))
    if STRICT:
        name = os.path.basename(f)
        if d.get("run_id") != RUN_ID:
            problems.append("%s: STALE evidence (run_id %r, this run %r)" % (name, d.get("run_id"), RUN_ID))
        if not d.get("cases"):
            problems.append("%s: EMPTY evidence (0 cases)" % name)
        bad = sorted({c.get("result") for c in d.get("cases", [])} - KINDS)
        if bad:
            problems.append("%s: unknown result kind(s) %s" % (name, bad))
        for c in d.get("cases", []):
            if c.get("result") in ("FAIL", "XPASS"):
                problems.append("%s: %s — %s" % (name, c.get("result"), c.get("case", "")[:120]))
        if not d.get("ts") or not isinstance(d.get("git"), dict):
            problems.append("%s: evidence carries no ts / git heads" % name)
        elif HEADS and d["git"] != HEADS:
            diff = {k: (d["git"].get(k), v) for k, v in HEADS.items() if d["git"].get(k) != v}
            problems.append("%s: evidence from OTHER commits than HEAD: %s" % (name, {k: "%s ≠ HEAD %s" % (str(a)[:12], b[:12]) for k, (a, b) in diff.items()}))
        mode = d.get("mode")
        cur = {}
        for c in d.get("cases", []):
            cur.setdefault(_norm(c.get("case")), []).append(c.get("result"))
        # per normalised name: how many cases, and how many of them PASS
        new_base[mode] = {"cases": {k: {"count": len(v), "pass": v.count("PASS")} for k, v in cur.items()},
                          "skip_build_ceiling": sum(1 for c in d.get("cases", []) if c.get("result") == "SKIP_BUILD")}
        b = BASE.get(mode)
        if b and not UPDATE_BASELINE:
            gone = sorted("%s (%d→%d)" % (k, v["count"], len(cur.get(k, []))) for k, v in b["cases"].items() if len(cur.get(k, [])) < v["count"])
            if gone:
                problems.append("%s: %d baseline case group(s) LOST cases, e.g. %s" % (name, len(gone), gone[:3]))
            demoted = sorted("%s (PASS %d→%d)" % (k, v["pass"], cur.get(k, []).count("PASS")) for k, v in b["cases"].items()
                             if cur.get(k, []).count("PASS") < v["pass"])
            if demoted:
                problems.append("%s: %d baseline case group(s) LOST PASSes, e.g. %s" % (name, len(demoted), demoted[:3]))
            sb = new_base[mode]["skip_build_ceiling"]
            if sb > b.get("skip_build_ceiling", 0):
                problems.append("%s: SKIP_BUILD %d exceeds its ceiling %d" % (name, sb, b.get("skip_build_ceiling", 0)))
        elif STRICT and not b and not UPDATE_BASELINE:
            problems.append("%s: no case baseline recorded for net %r (run build_matrix.py --strict --update-baseline deliberately)" % (name, mode))
    env = d.get("env", "unknown")
    pr = provenance.setdefault(env, {"git_sha": d.get("git_sha", ""), "ts": d.get("ts", ""), "modes": set()})
    pr["modes"].add(d.get("mode", "?"))
    for c in d.get("cases", []):
        for r in c.get("rules", []):
            env_rule[env][r].append((c.get("result"), c.get("case", "")))

ENVS = sorted(env_rule.keys()) or ["local-dev"]
PROJECTED = ["production"]  # no conformance run yet → projected, never asserted (design: environment truth)

def reduce_status(results):
    kinds = [k for k, _ in results]
    if not kinds:                                   return "NO TEST"
    if "FAIL" in kinds:                             return "REGRESSION"
    if "XPASS" in kinds:                            return "REVIEW"
    has_pass = "PASS" in kinds; has_xfail = "XFAIL" in kinds
    if has_pass and has_xfail:                      return "PARTIAL"
    if has_xfail:                                   return "VIOLATED"
    # slice-1e: a needs-build case means part of the rule is NOT built — the rule is PLANNED, never HELD,
    # even when its other cases PASS (HELD requires every cited case to PASS).
    if "SKIP_BUILD" in kinds:                       return "PLANNED(needs-build)"
    # slice-1d: a case skipped for missing credentials means part of the rule was NOT verified — never HELD.
    if "SKIP_CREDS" in kinds:                       return "UNVERIFIED(creds)"
    if has_pass:                                    return "HELD"
    return "NO TEST"

matrix = {}   # spec -> rule -> {env: {status, cases:[...]}, projected:[...]}
for spec, prefix, nums in INVENTORY:
    matrix[spec] = {}
    for n in nums:
        r = rid(prefix, n)
        cell = {}
        for env in ENVS:
            res = env_rule[env].get(r, [])
            cell[env] = {"status": reduce_status(res), "cases": sorted({c for _, c in res})}
        matrix[spec][r] = cell

OPTIONAL = set(sys.argv[sys.argv.index("--optional") + 1].split(",")) if "--optional" in sys.argv else set()
if STRICT:
    for m in [x for x in REQUIRED if x not in OPTIONAL]:
        if m not in seen_modes:
            problems.append("MISSING evidence: no results file for the required net %r" % m)

# ---- write JSON ----
json_out = {"envs": ENVS, "projected": PROJECTED, "provenance": {e: {"git_sha": p["git_sha"], "ts": p["ts"],
            "modes": sorted(p["modes"])} for e, p in provenance.items()}, "matrix":
            {spec: {r: {e: matrix[spec][r][e]["status"] for e in ENVS} for r in matrix[spec]} for spec in matrix}}
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
json.dump(json_out, open(OUT_JSON, "w"), indent=2)

# ---- write Markdown ----
L = []
L.append("# AirawatOS status matrix — rule × environment (GENERATED)")
L.append("")
L.append("**Generated** by `conformance/build_matrix.py` from `conformance/results/*.json` "
         "(written by `conformance/run.py --matrix`). **Do not hand-edit** — regenerate after a conformance run. "
         "This is the conformance-derived single source of truth for per-rule status; the specs reference it "
         "(ADR: STATUS-MATRIX-DESIGN.md).")
L.append("")
for env in ENVS:
    p = provenance.get(env, {})
    L.append("- **%s** — measured: modes %s, git `%s`, %s" % (env, "+".join(sorted(p.get("modes", []))) or "?",
             p.get("git_sha", "?"), p.get("ts", "?")))
for env in PROJECTED:
    L.append("- **%s** — *PROJECTED*: no production conformance run yet; not asserted "
             "(stand up per docs/operator/FRESH-INSTALL-TEST.md §Step 3, then run the suite with AOS_ENV=production)." % env)
L.append("")
L.append("**Derived status:** HELD (all cited cases PASS) · PARTIAL (PASS + known-violation XFAIL) · "
         "VIOLATED (only XFAIL — tracked as debt) · PLANNED(needs-build) (any SKIP_BUILD case: part of the rule is unbuilt — never HELD) · "
         "UNVERIFIED(creds) (any SKIP_CREDS case: not verified — never HELD; fix the fixture) · REVIEW (XPASS — spec lags code) · "
         "REGRESSION (a FAIL — contradicts spec) · NO TEST (no case cites the rule yet).")
L.append("")
cols = ENVS + PROJECTED
tally = {e: collections.Counter() for e in cols}
for spec, prefix, nums in INVENTORY:
    L.append("## %s" % spec)
    L.append("")
    L.append("| rule | " + " | ".join(cols) + " | cases (provenance) |")
    L.append("|---|" + "|".join(["---"] * len(cols)) + "|---|")
    for n in nums:
        r = rid(prefix, n)
        row = ["`%s`" % r]
        cases = []
        for e in ENVS:
            st = matrix[spec][r][e]["status"]; row.append(st); tally[e][st] += 1
            cases += matrix[spec][r][e]["cases"]
        for e in PROJECTED:
            row.append("projected"); tally[e]["projected"] += 1
        uniq = sorted(set(cases))
        row.append((("; ".join(uniq))[:160]) if uniq else "—")
        L.append("| " + " | ".join(row) + " |")
    L.append("")
L.append("## Tally (rules per derived status, per environment)")
L.append("")
allst = ["HELD", "PARTIAL", "VIOLATED", "PLANNED(needs-build)", "UNVERIFIED(creds)", "REVIEW", "REGRESSION", "NO TEST", "projected"]
L.append("| environment | " + " | ".join(allst) + " |")
L.append("|---|" + "|".join(["---"] * len(allst)) + "|")
for e in cols:
    L.append("| %s | " % e + " | ".join(str(tally[e].get(s, 0)) for s in allst) + " |")
L.append("")
open(OUT_MD, "w").write("\n".join(L) + "\n")
print("[build_matrix] wrote %s and %s from %d result file(s): envs=%s" %
      (os.path.relpath(OUT_MD, REPO), os.path.relpath(OUT_JSON, REPO), len(files), ", ".join(ENVS)))

if STRICT and not UPDATE_BASELINE:
    if problems:
        print("[build_matrix] ✗ STRICT: %d evidence problem(s) — the matrix is NOT trustworthy:" % len(problems))
        for p_ in problems[:60]:
            print("    ✗ " + p_)
        sys.exit(1)
    print("[build_matrix] ✓ STRICT: every required net wrote fresh, non-empty, passing evidence for run %s" % RUN_ID)

if UPDATE_BASELINE:
    problems = [x for x in problems if "OTHER commits" not in x and "DIRTY" not in x]   # recording reads one consistent run
    if problems:
        print("[build_matrix] ✗ refusing to record a case baseline from evidence with problems"); sys.exit(1)
    json.dump({"_meta": {"note": "slice-1i (DEBT-B118): per-net case baseline — names normalised (digits → #); kind = the result "
                         "recorded; skip_build_ceiling = SKIP_BUILD count. Strict matrix: no baseline case may disappear, no PASS "
                         "may be demoted, SKIP_BUILD may not exceed the ceiling. Update DELIBERATELY with --update-baseline."},
               **{m: new_base[m] for m in sorted(new_base)}}, open(BASELINE_FILE, "w"), indent=1, sort_keys=True)
    print("[build_matrix] case baseline written: %s (%d nets)" % (os.path.relpath(BASELINE_FILE, REPO), len(new_base)))

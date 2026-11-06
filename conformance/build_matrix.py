#!/usr/bin/env python3
"""Generate docs/specs/STATUS-MATRIX.md (+ .json) from conformance results.

Reads every conformance/results/<env>-<mode>.json (written by `run.py --matrix`), groups the cases by the
spec rule they cite, reduces each rule×env to one derived status (worst-first), and writes a rule×environment
status matrix. The conformance results are the single source of truth; the specs reference this file.

Reduction (STATUS-MATRIX-DESIGN.md): FAIL→REGRESSION; XPASS→REVIEW; PASS+XFAIL→PARTIAL; only PASS→HELD;
only XFAIL→VIOLATED; only SKIP_CREDS→UNVERIFIED(creds); only SKIP_BUILD→PLANNED(needs-build); no case→NO TEST.
Environments with no results file are shown PROJECTED (never asserted) per the design's environment-truth limit.

Usage: python3 conformance/build_matrix.py   (run from the repo; reads conformance/results/, writes docs/specs/)
"""
import os, json, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(HERE, "results")
OUT_MD = os.path.join(REPO, "docs", "specs", "STATUS-MATRIX.md")
OUT_JSON = os.path.join(REPO, "docs", "specs", "STATUS-MATRIX.json")

# Full rule inventory per spec (so rules with no test show NO TEST, not silently absent). Numbers per README.
INVENTORY = [
    ("FOUNDATIONS", "FND", [str(i) for i in range(1, 18)]),
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
]
def rid(prefix, n):  # FND + "8" -> FND-8 ; FED + "3" -> FED3 (FED carries no hyphen)
    return ("%s%s" if prefix == "FED" else "%s-%s") % (prefix, n)

# env -> rule -> list of (result_kind, case_name)
env_rule = collections.defaultdict(lambda: collections.defaultdict(list))
provenance = {}   # env -> {git_sha, ts, modes:set}
files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")))
for f in files:
    d = json.load(open(f))
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
    if has_pass:                                    return "HELD"
    if has_xfail:                                   return "VIOLATED"
    if "SKIP_CREDS" in kinds:                       return "UNVERIFIED(creds)"
    if "SKIP_BUILD" in kinds:                       return "PLANNED(needs-build)"
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
         "VIOLATED (only XFAIL — tracked as debt) · PLANNED(needs-build) (only SKIP_BUILD, not black-box reachable) · "
         "UNVERIFIED(creds) (only SKIP_CREDS — fix the fixture) · REVIEW (XPASS — spec lags code) · "
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

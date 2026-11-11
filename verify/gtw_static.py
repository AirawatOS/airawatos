#!/usr/bin/env python3
"""Static evidence for GATEWAY (GTW) rules that no black-box case can reach on a fresh install (slice-1d).

Each case reproduces a KNOWN violation recorded as debt — reported as XFAIL (violation present) or XPASS (it looks
fixed: review the rule's status). Nothing here can make a GTW rule HELD: these are evidence of absence/presence in
the source, tagged with the debt that tracks the fix. Writes conformance/results/local-dev-gtwstatic.json.
"""
import glob, json, os, re, time
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "conformance", "results", "local-dev-gtwstatic.json")
cases = []


def xfail(rules, name, reproduced, detail):
    cases.append({"case": name, "rules": rules, "result": "XFAIL" if reproduced else "XPASS", "detail": detail})
    print(f"  {'XFAIL' if reproduced else 'XPASS'}  {'/'.join(rules):8} {name} — {detail}")


def read(p):
    try:
        return open(os.path.join(ROOT, p), errors="replace").read()
    except Exception:
        return ""

def code(p):
    """slice-1h (DEBT-B99, re-review R6-3): the source WITHOUT comments (tokenize) — evidence is matched on code, so a
    comment like `# rate_limit` cannot flip a case. A missing/unreadable target is recorded as a FAIL (broken target)."""
    import io, tokenize
    src = read(p)
    if not src:
        cases.append({"case": "evidence target readable: " + p, "rules": ["FND-8"], "result": "FAIL", "detail": "missing or empty"})
        print("  ✗ FAIL  evidence target missing: " + p)
        return ""
    try:                                         # blank ONLY the comment text; layout (and every string) is kept
        lines = src.split("\n")
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type == tokenize.COMMENT:
                (r, c0), (_, c1) = t.start, t.end
                lines[r - 1] = lines[r - 1][:c0] + " " * (c1 - c0) + lines[r - 1][c1:]
        return "\n".join(lines)
    except Exception:
        return src


def finish(name):
    """Exit non-zero on a FAIL (broken target) or an XPASS (the recorded violation no longer reproduces: either it was
    fixed — update the case + rule status — or the detector broke). A net that cannot fail proves nothing."""
    import sys
    bad = [c for c in cases if c["result"] in ("FAIL", "XPASS")]
    for c in bad:
        print("  ✗ %s: %s — %s" % (c["result"], c["case"], c.get("detail", "")))
    print(("✗" if bad else "✓") + " %s: %d case(s), %d needing attention" % (name, len(cases), len(bad)))
    sys.exit(1 if bad or not cases else 0)



print("▶ GTW static evidence")
# GTW-3 / DEBT-B65 — drivers whose provider SDK opens its own sockets (the broker never sees the call)
sdk = sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, "components/drivers/*/run.py")) if "ee.Initialize" in read(os.path.relpath(f, ROOT)))
xfail(["GTW-3"], "no component reaches a provider around the gateway (provider SDK egress, DEBT-B65)", bool(sdk),
      f"{len(sdk)} driver(s) call ee.Initialize (Earth Engine opens its own TLS)")
# GTW-3 / DEBT-A43 — automation fires raw-URL subscription actions unless SUBSCRIPTION_ENFORCE is set
auto = code("platform-spec/reference/automation.py")
shadow = bool(re.search(r'SUBSCRIPTION_ENFORCE\s*=\s*os\s*\.\s*environ\s*\.\s*get\s*\(\s*"SUBSCRIPTION_ENFORCE"\s*,\s*"0"\s*\)', auto))
xfail(["GTW-3"], "no outbound call to an arbitrary URL outside the webhooks gateway (automation raw-URL action, DEBT-A43)", shadow,
      "automation SUBSCRIPTION_ENFORCE defaults to shadow (raw-URL actions fire)" if shadow else "enforced by default")
# GTW-13 / DEBT-B68 — app bundles that load scripts/styles/tiles from third-party origins in the browser
third = {}
for f in glob.glob(os.path.join(ROOT, "components/apps/*/dist/index.html")):
    hosts = sorted(set(re.findall(r'(?:src|href)=["\']https?://([a-z0-9.-]+)', read(os.path.relpath(f, ROOT)))))
    if hosts:
        third[f.split("/apps/")[1].split("/")[0]] = hosts
xfail(["GTW-13"], "no app bundle loads code or tiles from a third-party origin (DEBT-B68)", bool(third),
      f"{len(third)} app bundle(s): " + ", ".join(f"{a}({len(h)})" for a, h in sorted(third.items())[:6]))
# GTW-4 / DEBT-B71 — the AI gateway applies no consent / cost / rate check between north and south
mg = code("platform-spec/reference/model_gateway.py").lower()
absent = not any(w in mg for w in ("consent", "cost_ceiling", "spend_limit", "rate_limit", "ratelimit"))
xfail(["GTW-4"], "the AI gateway checks consent, cost and rate limits before calling a provider (DEBT-B71)", absent,
      "model_gateway.py has no consent / cost / rate check" if absent else "a check is present — review")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"env": "local-dev", "mode": "gtwstatic", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "",
           "cases": cases}, open(OUT, "w"), indent=1)
_ev.seal(OUT)
finish('GTW static evidence')

#!/usr/bin/env python3
"""Static evidence for GATEWAY (GTW) rules that no black-box case can reach on a fresh install (slice-1d).

Each case reproduces a KNOWN violation recorded as debt — reported as XFAIL (violation present) or XPASS (it looks
fixed: review the rule's status). Nothing here can make a GTW rule HELD: these are evidence of absence/presence in
the source, tagged with the debt that tracks the fix. Writes conformance/results/local-dev-gtwstatic.json.
"""
import glob, json, os, re, time

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


print("▶ GTW static evidence")
# GTW-3 / DEBT-B65 — drivers whose provider SDK opens its own sockets (the broker never sees the call)
sdk = sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, "components/drivers/*/run.py")) if "ee.Initialize" in read(os.path.relpath(f, ROOT)))
xfail(["GTW-3"], "no component reaches a provider around the gateway (provider SDK egress, DEBT-B65)", bool(sdk),
      f"{len(sdk)} driver(s) call ee.Initialize (Earth Engine opens its own TLS)")
# GTW-3 / DEBT-A43 — automation fires raw-URL subscription actions unless SUBSCRIPTION_ENFORCE is set
auto = read("platform-spec/reference/automation.py")
shadow = bool(re.search(r'SUBSCRIPTION_ENFORCE\s*=\s*os\.environ\.get\("SUBSCRIPTION_ENFORCE",\s*"0"\)', auto))
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
mg = read("platform-spec/reference/model_gateway.py").lower()
absent = not any(w in mg for w in ("consent", "cost_ceiling", "spend_limit", "rate_limit", "ratelimit"))
xfail(["GTW-4"], "the AI gateway checks consent, cost and rate limits before calling a provider (DEBT-B71)", absent,
      "model_gateway.py has no consent / cost / rate check" if absent else "a check is present — review")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"env": "local-dev", "mode": "gtwstatic", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "",
           "cases": cases}, open(OUT, "w"), indent=1)

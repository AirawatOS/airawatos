#!/usr/bin/env python3
"""Secret scanning + dependency/image vulnerability scanning (FIX-PLAN §0 net 8, slice-1d). Runs on the HOST.

  secrets  — gitleaks (zricethezav/gitleaks, pinned) over the FULL git history of all five repositories.
  vulns    — trivy (aquasec/trivy, pinned): every image the local-dev compose runs (HIGH+CRITICAL) and the repos'
             dependency manifests (fs scan).

Every current finding is listed in verify/scan-baseline/{gitleaks,trivy}.json against a DEBT id. A finding NOT in
the baseline FAILS the run: a new leaked secret (any rule), a new CRITICAL CVE in any image, or any HIGH/CRITICAL in
a dependency manifest. HIGH image CVEs are counted and reported (base-image churn), not failed.

Usage: python3 verify/scans.py [secrets|vulns|all] [--update-baseline]
"""
import glob, json, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
GITLEAKS = "zricethezav/gitleaks:v8.21.2"; TRIVY = "aquasec/trivy:0.57.1"
REPOS = {"root": ".", "platform-spec": "platform-spec", "kernel": "kernel", "network": "network", "components": "components"}
BASE = os.path.join(HERE, "scan-baseline"); CACHE = os.path.expanduser("~/.cache/airawat-trivy")
COMPOSE = os.path.join(ROOT, "deploy", "local-dev", "docker-compose.dev.yml")
RESULTS = os.path.join(ROOT, "conformance", "results", "local-dev-scans.json")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def secrets():
    base = json.load(open(os.path.join(BASE, "gitleaks.json"))) if os.path.exists(os.path.join(BASE, "gitleaks.json")) else {}
    known = base.get("findings", {}); found = {}; new = []
    with tempfile.TemporaryDirectory() as td:
        for name, src in REPOS.items():
            sh(["docker", "run", "--rm", "-v", f"{os.path.join(ROOT, src)}:/repo:ro", "-v", f"{td}:/out", GITLEAKS, "detect",
                "--source", "/repo", "--no-banner", "--redact", "--report-format", "json", "--report-path", f"/out/{name}.json",
                "--log-level", "error"])
            for f in json.load(open(os.path.join(td, f"{name}.json"))) if os.path.exists(os.path.join(td, f"{name}.json")) else []:
                fp = f"{name}:{f['Fingerprint']}"
                found[fp] = {"rule": f["RuleID"], "file": f"{src}/{f['File']}".lstrip("./"), "line": f.get("StartLine"),
                             "commit": f.get("Commit", "")[:10], "debt": known.get(fp, {}).get("debt", "UNTRIAGED")}
                if fp not in known:
                    new.append(fp)
    print(f"▶ secrets (gitleaks, full history, 5 repos): {len(found)} finding(s); {len(found) - len(new)} baselined; {len(new)} NEW")
    for fp, v in sorted(found.items()):
        print(f"  {'✗ NEW' if fp in new else '·'} {v['rule']:18} {v['file']}:{v['line']} @{v['commit']}  [{v['debt']}]")
    return found, new


def images():
    out = []
    for l in open(COMPOSE):
        m = re.match(r"\s*image:\s*([^\s#]+)", l)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def trivy_image(img, td):
    n = re.sub(r"[/:@]", "_", img)[:80]
    args = ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", f"{CACHE}:/root/.cache",
            "-v", f"{td}:/out", TRIVY, "image", "--quiet", "--severity", "HIGH,CRITICAL", "--format", "json", "-o", f"/out/{n}.json"]
    r = sh(args + [img])
    if r.returncode or not os.path.exists(os.path.join(td, f"{n}.json")):   # multi-arch local store: read from the registry
        sh(args + ["--image-src", "remote", img])
    try:
        d = json.load(open(os.path.join(td, f"{n}.json")))
    except Exception:
        return None
    crit, high = set(), 0
    for res in d.get("Results", []):
        for v in res.get("Vulnerabilities") or []:
            if v["Severity"] == "CRITICAL":
                crit.add(f"{v['PkgName']}:{v['VulnerabilityID']}")
            else:
                high += 1
    return {"critical": sorted(crit), "high": high}


def vulns():
    os.makedirs(CACHE, exist_ok=True)
    base = json.load(open(os.path.join(BASE, "trivy.json"))) if os.path.exists(os.path.join(BASE, "trivy.json")) else {}
    bimg = base.get("images", {}); res = {"images": {}, "manifests": {}}; new = []
    with tempfile.TemporaryDirectory() as td:
        print("▶ vulnerabilities (trivy) — images run by the local-dev compose (HIGH+CRITICAL)")
        for img in images():
            r = trivy_image(img, td)
            if r is None:
                print(f"  ✗ {img}: scan failed"); new.append(f"scan-failed:{img}"); continue
            key = img.split("@")[0]
            known = set((bimg.get(key) or {}).get("critical", []))
            fresh = [c for c in r["critical"] if c not in known]
            new += [f"{key}:{c}" for c in fresh]
            res["images"][key] = {**r, "debt": (bimg.get(key) or {}).get("debt", "UNTRIAGED")}
            print(f"  {'✗' if fresh else '·'} {key:48} CRITICAL {len(r['critical'])} ({len(fresh)} NEW)  HIGH {r['high']}  [{res['images'][key]['debt']}]")
        print("▶ vulnerabilities (trivy fs) — repository dependency manifests (HIGH+CRITICAL fail)")
        for name, src in REPOS.items():
            sh(["docker", "run", "--rm", "-v", f"{os.path.join(ROOT, src)}:/src:ro", "-v", f"{CACHE}:/root/.cache", "-v", f"{td}:/out",
                TRIVY, "fs", "--quiet", "--scanners", "vuln", "--skip-dirs", "/src/.venv", "--skip-dirs", "/src/kernel",
                "--skip-dirs", "/src/network", "--skip-dirs", "/src/platform-spec", "--skip-dirs", "/src/components",
                "--severity", "HIGH,CRITICAL", "--format", "json", "-o", f"/out/fs-{name}.json", "/src"])
            try:
                d = json.load(open(os.path.join(td, f"fs-{name}.json")))
                items = sorted({f"{v['PkgName']}@{v['InstalledVersion']}:{v['VulnerabilityID']}" for x in d.get("Results", [])
                                for v in x.get("Vulnerabilities") or []})
            except Exception:
                items = ["scan-failed"]
            res["manifests"][name] = items; new += [f"{name}:{i}" for i in items]
            print(f"  {'✗' if items else '·'} {name:14} {len(items)} HIGH/CRITICAL in dependency manifests")
    return res, new


def main():
    what = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "all")
    update = "--update-baseline" in sys.argv
    cases, failed = [], 0
    if what in ("secrets", "all"):
        found, new = secrets()
        if update:
            old = (json.load(open(os.path.join(BASE, "gitleaks.json"))) if os.path.exists(os.path.join(BASE, "gitleaks.json")) else {}).get("findings", {})
            json.dump({"_meta": {"tool": GITLEAKS, "updated": time.strftime("%Y-%m-%d")},
                       "findings": {fp: {**v, "debt": old.get(fp, {}).get("debt", v["debt"])} for fp, v in found.items()}},
                      open(os.path.join(BASE, "gitleaks.json"), "w"), indent=1, sort_keys=True)
        failed += bool(new) and not update
        cases.append({"case": f"no new secret in any repository's history ({len(found)} known, {len(new)} new)", "rules": ["FND-9", "FND-16"],
                      "result": "PASS" if (not new or update) else "FAIL"})
    if what in ("vulns", "all"):
        res, new = vulns()
        if update:
            old = (json.load(open(os.path.join(BASE, "trivy.json"))) if os.path.exists(os.path.join(BASE, "trivy.json")) else {}).get("images", {})
            json.dump({"_meta": {"tool": TRIVY, "updated": time.strftime("%Y-%m-%d"),
                                 "rule": "a CRITICAL not listed here fails; HIGH counts are reported"},
                       "images": {k: {"critical": v["critical"], "high_at_baseline": v["high"], "debt": old.get(k, {}).get("debt", v["debt"])}
                                  for k, v in res["images"].items()}},
                      open(os.path.join(BASE, "trivy.json"), "w"), indent=1, sort_keys=True)
        failed += bool(new) and not update
        cases.append({"case": f"no new CRITICAL image CVE and no HIGH/CRITICAL dependency CVE ({len(new)} new)", "rules": [],
                      "result": "PASS" if (not new or update) else "FAIL"})
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    json.dump({"env": "local-dev", "mode": "scans", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_sha": "",
               "cases": cases}, open(RESULTS, "w"), indent=1)
    print(("✓" if not failed else "✗") + f" scans: {failed} failing")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

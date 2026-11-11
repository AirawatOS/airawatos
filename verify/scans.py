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
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
GITLEAKS = "zricethezav/gitleaks:v8.21.2@sha256:0e99e8821643ea5b235718642b93bb32486af9c8162c8b8731f7cbdc951a7f46"; TRIVY = "aquasec/trivy:0.57.1@sha256:5c59e08f980b5d4d503329773480fcea2c9bdad7e381d846fbf9f2ecb8050f6b"   # slice-1h B99: digest-pinned scanners
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
            r = sh(["docker", "run", "--rm", "-v", f"{os.path.join(ROOT, src)}:/repo:ro", "-v", f"{td}:/out", GITLEAKS, "detect",
                    "--source", "/repo", "--no-banner", "--redact", "--report-format", "json", "--report-path", f"/out/{name}.json",
                    "--log-level", "error"])
            rep = os.path.join(td, f"{name}.json")
            # slice-1g (DEBT-B92 / review N4): FAIL CLOSED — gitleaks exits 0 (clean) or 1 (leaks found); anything else, or
            # no report, is a scan that did not run, never "zero findings".
            try:
                findings = json.load(open(rep)) if r.returncode in (0, 1) and os.path.exists(rep) else None
            except Exception:
                findings = None
            if findings is None:
                fp = f"{name}:SCAN-DID-NOT-RUN"
                found[fp] = {"rule": "scan-error", "file": src, "line": 0, "commit": "",
                             "debt": f"exit {r.returncode}: {(r.stderr or r.stdout).strip()[:120]}"}
                new.append(fp)
                continue
            for f in findings:
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
        print("▶ vulnerabilities (trivy fs) — every tracked Python dependency manifest (HIGH+CRITICAL fail)")
        # slice-1h (re-review R7-1): trivy does not read `requirements.lock`, so the old repo-wide fs scan found NO language
        # file and passed vacuously. Every tracked requirements*.txt / *.lock is now STAGED as a requirements.txt trivy
        # recognises, and each scan must list as many packages as the manifest pins — or the case fails.
        import shutil
        stage = os.path.join(td, "manifests")
        for name, src in REPOS.items():
            ls = sh(["git", "-C", os.path.join(ROOT, src), "ls-files"]).stdout.split()
            mans = [f for f in ls if re.search(r"(^|/)requirements[^/]*\.(txt|lock)$", f) and "node_modules" not in f]
            items, scanned, expected = [], 0, 0
            for i, f in enumerate(mans):
                pins = [l for l in open(os.path.join(ROOT, src, f)) if re.match(r"^[A-Za-z0-9_.\[\]-]+==", l.strip())]
                if not pins:
                    continue
                d = os.path.join(stage, name, str(i)); os.makedirs(d, exist_ok=True)
                shutil.copy(os.path.join(ROOT, src, f), os.path.join(d, "requirements.txt"))
                expected += len(pins)
            if expected:
                sh(["docker", "run", "--rm", "-v", f"{os.path.join(stage, name)}:/src:ro", "-v", f"{CACHE}:/root/.cache", "-v", f"{td}:/out",
                    TRIVY, "fs", "--quiet", "--scanners", "vuln", "--list-all-pkgs", "--severity", "HIGH,CRITICAL",
                    "--format", "json", "-o", f"/out/fs-{name}.json", "/src"])
                try:
                    d = json.load(open(os.path.join(td, f"fs-{name}.json")))
                    scanned = sum(len(x.get("Packages") or []) for x in d.get("Results", []))
                    items = sorted({f"{v['PkgName']}@{v['InstalledVersion']}:{v['VulnerabilityID']}" for x in d.get("Results", [])
                                    for v in x.get("Vulnerabilities") or []})
                except Exception:
                    items = ["scan-failed"]
                if scanned < expected:
                    items = items + ["scan-incomplete: %d of %d pinned packages scanned" % (scanned, expected)]
            res["manifests"][name] = items; new += [f"{name}:{i}" for i in items]
            print(f"  {'✗' if items else '·'} {name:14} {len(mans)} manifest(s), {scanned}/{expected} pinned packages scanned, "
                  f"{len([i for i in items if not i.startswith('scan-')])} HIGH/CRITICAL")
    return res, new


def main():
    what = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "all")
    if what not in ("secrets", "vulns", "all"):          # slice-1h (DEBT-B99, re-review R3-6): an unknown mode scans NOTHING
        print("✗ scans: unknown mode %r (secrets | vulns | all) — nothing scanned" % what); sys.exit(2)
    update = "--update-baseline" in sys.argv
    cases, failed = [], 0
    if what in ("secrets", "all"):
        # slice-1g (DEBT-B92 / N4) self-test: a scanner that CANNOT run must surface as a failure, not as zero findings.
        global GITLEAKS, REPOS
        _g, _r = GITLEAKS, REPOS
        GITLEAKS, REPOS = "zricethezav/gitleaks:does-not-exist-selftest", dict(list(_r.items())[:1])
        _f, _n = secrets()
        GITLEAKS, REPOS = _g, _r
        if not any(fp.endswith("SCAN-DID-NOT-RUN") for fp in _n):
            print("✗ secret-scan self-test: a scanner that did not run was counted as zero findings (fail-open)"); sys.exit(2)
        print("✓ secret-scan self-test: a scanner that did not run is a failure (fail-closed)")
        found, new = secrets()
        # slice-1h (B99): EVERY repository must have been scanned; a SCAN-DID-NOT-RUN may never be written into the baseline
        _notrun = [fp for fp in found if fp.endswith("SCAN-DID-NOT-RUN")]
        cases.append({"case": "gitleaks scanned all %d repositories (%d did not run)" % (len(REPOS), len(_notrun)),
                      "rules": ["FND-9"], "result": "PASS" if not _notrun else "FAIL"})
        failed += bool(_notrun)
        if update and _notrun:
            print("✗ refusing --update-baseline: %s did not run" % _notrun); sys.exit(2)
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
        # slice-1h (B99): every image the stack runs and every repository manifest must have produced a scan
        _exp_img, _got_img = len(images()), len(res["images"])
        _failed_fs = [k for k, v in res["manifests"].items() if any(str(i).startswith("scan-") for i in v)]
        cases.append({"case": "trivy scanned every stack image (%d/%d) and every repository manifest (%d/%d)" % (
                          _got_img, _exp_img, len(res["manifests"]) - len(_failed_fs), len(REPOS)),
                      "rules": ["FND-16"], "result": "PASS" if (_got_img == _exp_img and _exp_img > 0 and not _failed_fs
                                                                and len(res["manifests"]) == len(REPOS)) else "FAIL"})
        failed += not (_got_img == _exp_img and _exp_img > 0 and not _failed_fs)
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
    _ev.seal(RESULTS)
    print(("✓" if not failed else "✗") + f" scans: {failed} failing")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

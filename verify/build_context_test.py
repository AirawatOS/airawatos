#!/usr/bin/env python3
"""No secret, credential or runtime data enters a Docker build context (slice-1g, DEBT-B94 / review R4).

For every image build (the reference image from the workspace root with its own allow-list
platform-spec/Dockerfile.reference.dockerignore; anything else built from the root with the root .dockerignore; the
kernel and network images from their repositories with theirs), a PROBE build sends the REAL context through the REAL
ignore file to BuildKit and lists, from inside the build, every file that arrived matching: .env / .env.* / *.env,
AppRole credential dirs, .creds.json, Vault init.json, conformance results, *.jsonl. Canary files of each kind are
planted in each context for the duration of the run (and removed), so the check never passes vacuously.
IGNORE_<NAME>=<file> substitutes an ignore file (to run against an older one). Exit 1 on any leak.
"""
import os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDS = [  # name, context, ignore file
    ("reference", ".", "platform-spec/Dockerfile.reference.dockerignore"),
    ("root", ".", ".dockerignore"),
    ("kernel", "kernel", "kernel/.dockerignore"),
    ("network", "network", "network/.dockerignore"),
]
CANARY = ["zz-b94-canary/.env", "zz-b94-canary/svc.env", "zz-b94-canary/.env.local", "zz-b94-canary/.creds.json",
          "zz-b94-canary/approle/x.env", "zz-b94-canary/results/r.json", "zz-b94-canary/vault/init.json", "zz-b94-canary/t.jsonl",
          # slice-1h (R7-4): keys, credential files and runtime data dirs too
          "zz-b94-canary/tls.pem", "zz-b94-canary/id.key", "zz-b94-canary/svc-creds.json", "zz-b94-canary/pgdata/PG_VERSION",
          "zz-b94-canary/vault-data/core.json"]
PROBE = """# syntax=docker/dockerfile:1
FROM busybox:1.36.1
RUN --mount=type=bind,target=/ctx cd /ctx && find . \\( -name .env -o -name '.env.*' -o -name '*.env' -o -name .creds.json \
    -o -name init.json -o -path '*/approle/*' -o -path '*/results/*' -o -name '*.jsonl' -o -name '*.pem' -o -name '*.key' \
    -o -name '*creds*.json' -o -path '*/pgdata/*' -o -path '*/vault-data/*' \\) -type f > /tmp/l; \
    sed 's/^/LEAK /' /tmp/l; echo "COUNT $(wc -l < /tmp/l)"
"""
leaks_total = 0
print("▶ build-context test (B94): what reaches the build daemon")
for name, ctx, ign in BUILDS:
    ctxp = os.path.join(ROOT, ctx)
    ign = os.environ.get("IGNORE_" + name.upper(), os.path.join(ROOT, ign))
    planted = []
    try:
        for c in CANARY:
            fp = os.path.join(ctxp, c); os.makedirs(os.path.dirname(fp), exist_ok=True)
            open(fp, "w").write("canary\n"); planted.append(fp)
        with tempfile.TemporaryDirectory() as td:
            df = os.path.join(td, "probe.Dockerfile")
            open(df, "w").write(PROBE)
            shutil.copy(ign, df + ".dockerignore")            # BuildKit: <Dockerfile>.dockerignore governs the context
            # the docker-driver builder of the current context: no separate builder container on the host (slice-1h, B99)
            _b = os.environ.get("AOS_BUILDER") or subprocess.run(["docker", "context", "show"], capture_output=True, text=True).stdout.strip() or "default"
            r = subprocess.run(["docker", "buildx", "build", "--builder", _b, "--no-cache", "--progress=plain", "-f", df, "--output", "type=cacheonly", ctxp],
                               capture_output=True, text=True, env={**os.environ, "DOCKER_BUILDKIT": "1"})
        out = r.stdout + r.stderr
        leaks = sorted(set(re.findall(r"LEAK \./(\S+)", out)))
        count = re.search(r"COUNT (\d+)", out)
        if not count:
            print(f"  ✗ {name}: probe build did not run: {out[-300:]}"); leaks_total += 1; continue
        canary_seen = [l for l in leaks if l.startswith("zz-b94-canary/")]
        real = [l for l in leaks if not l.startswith("zz-b94-canary/")]
        ok = not leaks
        print(f"  {'✓' if ok else '✗'} {name:9} context {ctx!r} via {os.path.relpath(ign, ROOT)}: {len(leaks)} sensitive file(s) reached the daemon"
              + (f" — canaries {len(canary_seen)}/{len(CANARY)}, real: {real[:12]}" if leaks else f" (all {len(CANARY)} canaries excluded)"))
        leaks_total += len(leaks)
    finally:
        for fp in planted:
            os.remove(fp)
        shutil.rmtree(os.path.join(ctxp, "zz-b94-canary"), ignore_errors=True)
print(("✗" if leaks_total else "✓") + f" build-context test: {leaks_total} leak(s)")
sys.exit(1 if leaks_total else 0)

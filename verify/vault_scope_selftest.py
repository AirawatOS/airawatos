#!/usr/bin/env python3
"""Mutation self-test of the Vault scope check (slice-1i, DEBT-B132).

Widens ONE service's live Vault policy at a time — on a mount or path the old check never looked at — runs
conformance/vault_scope_test.py and requires it to FAIL, then writes the policy back from its .hcl file and requires PASS:
  1. the final review's case: decision may read components/data/* (every tenant's component secrets)
  2. kernel may read another realm's secret/ path (secret/data/localdev-developer/*)
  3. workflow may read identity's transit key (transit/keys/airawat-identity)
  4. app-host may list every policy (sys/policies/acl)
  5. scheduler may read the metadata (names) of every secret (secret/metadata/*)
SCOPE=<path> runs another copy of the check. Exit 1 on failure.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = os.environ.get("SCOPE", os.path.join(ROOT, "conformance/vault_scope_test.py"))
POL = os.path.join(ROOT, "deploy/local-dev/vault/policies")
MUT = [
    ("decision reads components/data/* (final-review case)", "svc-decision", 'path "components/data/*" { capabilities = ["read"] }'),
    ("kernel reads another realm's secret/ path", "svc-kernel", 'path "secret/data/localdev-developer/*" { capabilities = ["read"] }'),
    ("workflow reads identity's transit key", "svc-workflow", 'path "transit/keys/airawat-identity" { capabilities = ["read"] }'),
    ("app-host lists every policy", "svc-app-host", 'path "sys/policies/acl" { capabilities = ["list"] }'),
    ("scheduler reads every secret's metadata", "svc-scheduler", 'path "secret/metadata/*" { capabilities = ["read", "list"] }'),
]
VR = subprocess.run(["docker", "exec", "airawat-ld-vault", "sh", "-lc",
                     'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"'], capture_output=True, text=True).stdout.strip()


def write_policy(name, text):
    return subprocess.run(["docker", "exec", "-i", "-e", "VAULT_TOKEN=" + VR, "-e", "VAULT_ADDR=http://127.0.0.1:8200", "airawat-ld-vault",
                           "vault", "policy", "write", name, "-"], input=text, capture_output=True, text=True).returncode == 0


def scope():
    return subprocess.run([sys.executable, SCOPE], capture_output=True, text=True).returncode


fails = []
print("▶ Vault scope self-test (B132) — check under test: %s" % os.path.relpath(SCOPE, ROOT))
rc = scope()
print(("  ✓" if rc == 0 else "  ✗") + " baseline: the scope check passes (exit %d)" % rc)
fails += [] if rc == 0 else ["baseline"]
for name, pol, extra in MUT:
    orig = open(os.path.join(POL, pol + ".hcl")).read()
    try:
        if not write_policy(pol, orig + "\n" + extra + "\n"):
            print("  ✗ %s: could not widen %s" % (name, pol)); fails.append(name); continue
        rc = scope()
    finally:
        write_policy(pol, orig)
    after = scope()
    ok = rc != 0 and after == 0
    print(("  ✓" if ok else "  ✗") + " %s → scope check %s; after restoring %s.hcl %s" % (name, "FAILS" if rc else "STAYED GREEN", pol, "passes" if after == 0 else "FAILS"))
    if not ok:
        fails.append(name)
print(("✗" if fails else "✓") + " Vault scope self-test: %d of %d mutation(s) not caught" % (len(fails), len(MUT)))
sys.exit(1 if fails else 0)

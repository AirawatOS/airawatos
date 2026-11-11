#!/usr/bin/env python3
"""Mutation self-test of the Vault scope check (slice-1i DEBT-B132; slice-1j DEBT-B138).

Changes the LIVE Vault one way at a time, runs conformance/vault_scope_test.py and requires it to FAIL, then reverts and
requires PASS. slice-1i cases (a policy widened on a path the old check never looked at):
   1. decision may read components/data/* (final review)          2. kernel reads another realm's secret/ path
   3. workflow reads identity's transit key                         4. app-host lists every policy (sys/policies/acl)
   5. scheduler reads every secret's metadata (secret/metadata/*)
slice-1j — the conditions review's cases (each also proven a REAL read with decision's own token before the check runs):
   6. a KV-v1 mount + decision may read it                          7. a TOTP engine + decision may read its codes
   8. decision may LIST every secret name (list-only grant)         9. decision may read+list identity/entity/name/*
  10. decision may sudo+read sys/policies/acl/*
slice-1j — neighbours of the same class:
  11. an extra capability on decision's OWN path ("list" on its data path — no new path at all)
  12. a new auth method (userpass)                                 13. an identity GROUP attaching a policy to decision's entity
  14. Vault's built-in `default` policy re-attached to the decision role (token_no_default_policy=false)
  15. an extra policy name nobody declared                         16. an EXTRA audit device (a second file device)
SCOPE=<path> runs another copy of the check. Exit 1 on failure.
"""
import json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = os.environ.get("SCOPE", os.path.join(ROOT, "conformance/vault_scope_test.py"))
POL = os.path.join(ROOT, "deploy/local-dev/vault/policies")
VR = subprocess.run(["docker", "exec", "airawat-ld-vault", "sh", "-lc",
                     'tr -d "\\n " < /vault/data/init.json | sed "s/.*\\"root_token\\":\\"\\([^\\"]*\\)\\".*/\\1/"'], capture_output=True, text=True).stdout.strip()


def v(*args, stdin=None):
    return subprocess.run(["docker", "exec", "-i", "-e", "VAULT_TOKEN=" + VR, "-e", "VAULT_ADDR=http://127.0.0.1:8200", "airawat-ld-vault", "vault"]
                          + list(args), input=stdin, capture_output=True, text=True)


def write_policy(name, text):
    return v("policy", "write", name, "-", stdin=text).returncode == 0


def widen(pol, extra):
    orig = open(os.path.join(POL, pol + ".hcl")).read()
    return (lambda: write_policy(pol, orig + "\n" + extra + "\n")), (lambda: write_policy(pol, orig))


def as_decision(path, list_=False):
    """an ACTUAL request with decision's own token (proves the exposure is real, not just a policy line)."""
    code = ("import glob,urllib.request,urllib.error\ntok=''\n"
            "for p in sorted(glob.glob('/proc/[0-9]*/environ'),key=lambda x:int(x.split('/')[2])):\n"
            "  try: d=open(p,'rb').read()\n  except Exception: continue\n"
            "  for l in d.split(b'\\0'):\n    if l.startswith(b'VAULT_TOKEN=') and not tok: tok=l.split(b'=',1)[1].decode()\n"
            "  if tok: break\n"
            "r=urllib.request.Request('http://vault:8200/v1/%s', headers={'X-Vault-Token':tok}%s)\n"
            "try: print(urllib.request.urlopen(r,timeout=6).status)\nexcept urllib.error.HTTPError as e: print(e.code)\n"
            % (path, ", method='LIST'" if list_ else ""))
    return subprocess.run(["docker", "exec", "airawat-ld-decision", "python3", "-c", code], capture_output=True, text=True).stdout.strip()


def ent_id():
    code = ("import glob,json,urllib.request\ntok=''\n"
            "for p in sorted(glob.glob('/proc/[0-9]*/environ'),key=lambda x:int(x.split('/')[2])):\n"
            "  try: d=open(p,'rb').read()\n  except Exception: continue\n"
            "  for l in d.split(b'\\0'):\n    if l.startswith(b'VAULT_TOKEN=') and not tok: tok=l.split(b'=',1)[1].decode()\n"
            "  if tok: break\n"
            "print(json.loads(urllib.request.urlopen(urllib.request.Request('http://vault:8200/v1/auth/token/lookup-self',headers={'X-Vault-Token':tok}),timeout=6).read())['data'].get('entity_id',''))\n")
    return subprocess.run(["docker", "exec", "airawat-ld-decision", "python3", "-c", code], capture_output=True, text=True).stdout.strip()


def seq(*fs):
    return lambda: all(f() is not False for f in fs)


def ok(r):
    return r.returncode == 0


MUT = []
for name, pol, extra in [
    ("decision reads components/data/* (final-review case)", "svc-decision", 'path "components/data/*" { capabilities = ["read"] }'),
    ("kernel reads another realm's secret/ path", "svc-kernel", 'path "secret/data/localdev-developer/*" { capabilities = ["read"] }'),
    ("workflow reads identity's transit key", "svc-workflow", 'path "transit/keys/airawat-identity" { capabilities = ["read"] }'),
    ("app-host lists every policy", "svc-app-host", 'path "sys/policies/acl" { capabilities = ["list"] }'),
    ("scheduler reads every secret's metadata", "svc-scheduler", 'path "secret/metadata/*" { capabilities = ["read", "list"] }'),
]:
    a, r = widen(pol, extra); MUT.append((name, a, r, None))

_kv1a, _kv1r = widen("svc-decision", 'path "aosst-kv1/*" { capabilities = ["read"] }')
MUT.append(("KV-v1 mount + decision reads it (conditions-review case)",
            seq(lambda: ok(v("secrets", "enable", "-path=aosst-kv1", "-version=1", "kv")), lambda: ok(v("write", "aosst-kv1/tenantx", "value=x")), _kv1a),
            seq(_kv1r, lambda: ok(v("secrets", "disable", "aosst-kv1/"))), lambda: as_decision("aosst-kv1/tenantx")))
_ta, _tr = widen("svc-decision", 'path "aosst-totp/code/*" { capabilities = ["read"] }')
MUT.append(("TOTP engine + decision reads its codes (conditions-review case)",
            seq(lambda: ok(v("secrets", "enable", "-path=aosst-totp", "totp")),
                lambda: ok(v("write", "aosst-totp/keys/k1", "generate=true", "issuer=aos", "account_name=x")), _ta),
            seq(_tr, lambda: ok(v("secrets", "disable", "aosst-totp/"))), lambda: as_decision("aosst-totp/code/k1")))
for name, extra, probe in [
    ("decision LISTs every secret name (list-only; conditions-review case)", 'path "secret/metadata/*" { capabilities = ["list"] }', ("secret/metadata/", True)),
    ("decision reads+lists identity/entity/name (conditions-review case)", 'path "identity/entity/name/*" { capabilities = ["read", "list"] }', ("identity/entity/name", True)),
    ("decision sudo-reads sys/policies/acl/* (conditions-review case)", 'path "sys/policies/acl/*" { capabilities = ["read", "sudo"] }', ("sys/policies/acl/svc-network", False)),
    ("an extra capability on decision's OWN path (list on its data path)", 'path "secret/data/localdev-operator/decision/*" { capabilities = ["read", "list"] }', None),
]:
    a, r = widen("svc-decision", extra)
    MUT.append((name, a, r, (lambda p=probe: as_decision(*p)) if probe else None))
MUT.append(("a new auth method (userpass)", lambda: ok(v("auth", "enable", "-path=aosst-up", "userpass")), lambda: ok(v("auth", "disable", "aosst-up/")), None))
_g = {}
MUT.append(("an identity GROUP attaches a policy to decision's entity",
            lambda: ok(v("write", "identity/group", "name=aosst-group", "policies=svc-secrets", "member_entity_ids=" + ent_id())),
            lambda: ok(v("delete", "identity/group/name/aosst-group")), None))
MUT.append(("Vault's built-in default policy re-attached to the decision role",
            lambda: ok(v("write", "auth/approle/role/decision", "token_no_default_policy=false")),
            lambda: ok(v("write", "auth/approle/role/decision", "token_no_default_policy=true")), None))
MUT.append(("an extra, undeclared policy", lambda: write_policy("aosst-extra", 'path "secret/data/x" { capabilities = ["read"] }\n'),
            lambda: ok(v("policy", "delete", "aosst-extra")), None))
MUT.append(("an extra audit device", lambda: ok(v("audit", "enable", "-path=aosst-audit", "file", "file_path=/vault/audit/aosst.log")),
            lambda: ok(v("audit", "disable", "aosst-audit/")), None))


def scope():
    r = subprocess.run([sys.executable, SCOPE], capture_output=True, text=True)
    return r.returncode, [l for l in r.stdout.splitlines() if "✗" in l]


fails = []
print("▶ Vault scope self-test (B132/B138) — check under test: %s" % os.path.relpath(SCOPE, ROOT), flush=True)
rc, bad = scope()
print(("  ✓" if rc == 0 else "  ✗") + " baseline: the scope check passes (exit %d)%s" % (rc, (" — " + bad[0][:140]) if bad else ""), flush=True)
fails += [] if rc == 0 else ["baseline"]
only = os.environ.get("ONLY", "")
for name, apply, revert, probe in MUT:
    if only and only not in name:
        continue
    real = None
    try:
        if not apply():
            print("  ✗ %s: could not apply the mutation" % name, flush=True); fails.append(name); revert(); continue
        time.sleep(1)
        if probe:
            real = probe()
        rc, bad = scope()
    finally:
        revert()
    after, _ = scope()
    good = rc != 0 and after == 0
    print(("  ✓" if good else "  ✗") + " %s%s → scope check %s%s; after revert %s" % (
        name, (" [real request with decision's token → %s]" % real) if probe else "", "FAILS" if rc else "STAYED GREEN",
        (" (" + bad[0].strip()[:110] + ")") if rc and bad else "", "passes" if after == 0 else "FAILS"), flush=True)
    if not good:
        fails.append(name)
print(("✗" if fails else "✓") + " Vault scope self-test: %d of %d mutation(s) not caught" % (len(fails), len(MUT) if not only else len([m for m in MUT if only in m[0]])))
sys.exit(1 if fails else 0)

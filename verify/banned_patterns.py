#!/usr/bin/env python3
"""Banned-pattern checks (FIX-PLAN §0 net 6, slice-1d). Static; runs on the source tree, no stack needed.

Each check names the constitution rule it protects. Two kinds:
  * BASELINED — existing occurrences are recorded in verify/banned-baseline.json (fingerprint = file + normalised
    line); the check FAILS only on a NEW occurrence and reports the baselined count: TOKEN_ROLES (the DEBT-B1
    thread), FAIL_OPEN_GATE (baseline 0 since slice-1f closed DEBT-B47) and PROD_SHADOW_OR_INPROCESS (RELEASE-PLAN §5 flips).
    Secrets and literal gates are HARD — no baseline.
  * HARD — any occurrence fails. No baseline.

Scope: the CURRENT platform — kernel/, network/, platform-spec/reference/, components/_common/, deploy/installer/,
deploy/local-dev/ (+ conformance/ and verify/ themselves are excluded: they contain the probes' own fixtures).
OUT OF SCOPE (listed on every run, not silently skipped): the LEGACY stacks that pin pre-A71 images and are slated
for retirement — the root docker-compose.yml, deploy/local/, platform-spec/deploy/ec2/ — and tests (test_*.py).

Usage: python3 verify/banned_patterns.py [--update-baseline] [--json out.json]
"""
import json, os, re, sys, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BASELINE = os.path.join(HERE, "banned-baseline.json")
SCOPE = ["kernel", "network", "platform-spec/reference", "components/_common", "deploy/installer", "deploy/local-dev"]
OUT_OF_SCOPE = ["docker-compose.yml (root, legacy)", "deploy/local/ (legacy)", "platform-spec/deploy/ec2/ (legacy EC2)",
                "kernel/deploy/ (standalone kernel dev compose + Keycloak seam test, superseded by deploy/local-dev — its literals were removed anyway; DB_USER=kernel superuser remains)",
                "tests (test_*.py)", "conformance/, verify/ (probe fixtures)"]
SKIP_PATHS = ("kernel/deploy/",)
SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git", "developer", "developer-assets", "dist", "vendor", "results"}


_TRACKED = None


def _tracked():
    """Only files under version control are checked (runtime files such as the gitignored .env / AppRole env files
    are the secret SCANNER's job, step 4, not a code pattern). Each nested repo is listed with its own git."""
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = set()
        for repo in (".", "kernel", "network", "platform-spec", "components"):
            out = subprocess.run(["git", "-C", os.path.join(ROOT, repo), "ls-files"], capture_output=True, text=True).stdout
            pre = "" if repo == "." else repo + "/"
            _TRACKED |= {pre + l for l in out.split("\n") if l}
    return _TRACKED


def files(exts):
    for f in sorted(_tracked()):
        if not any(f == t or f.startswith(t + "/") for t in SCOPE) or f.startswith(SKIP_PATHS):
            continue
        parts = f.split("/")
        if any(p in SKIP_DIRS for p in parts) or parts[-1].startswith("test_") or not f.endswith(exts):
            continue
        yield f


def lines(path):
    try:
        return open(os.path.join(ROOT, path), errors="replace").read().split("\n")
    except Exception:
        return []


def norm(s):
    return re.sub(r"\s+", " ", s.strip())


# ── the checks ────────────────────────────────────────────────────────────────────────────────────────────────
TOKEN_ROLES = re.compile(r"""(claims|_cl|cl|c|tok|token|payload|_claims|me)\s*(\.get\(\s*["']roles["']|\[\s*["']roles["']\s*\])""")
LITERAL_GATE = re.compile(r"""X-Internal-Token|_INTERNAL["']\s*,\s*["'][^"']+["']|INTERNAL_TOKEN\s*=\s*["'][^"']+["']"""
                          r"""|-H\s*["'](X-[A-Za-z-]*Token|Authorization):\s*(Bearer\s+)?[A-Za-z0-9][^"'$\s]*["']""")   # literal token header
# a secret-bearing NAME (not an audience / URL / path / Vault key-name / file reference) with a literal default value
_SECRET_NAME = r"[A-Z0-9_]*(PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)(?!_(AUDIENCE|AUD|URL|FILE|PATH|VAULT_PATH|TTL|NAME|REQUIRED|HEADER)\b)(?![A-Z0-9_]*(AUDIENCE|_URL|_FILE|_PATH|KEY_SECRET))[A-Z0-9_]*"
DEFAULT_SECRET_PY = re.compile(r"""os\.environ\.get\(\s*["'](""" + _SECRET_NAME + r""")["']\s*,\s*["']([^"'/][^"']*)["']""")
SECRET_ASSIGN_YAML = re.compile(r"""(?:^|(?<!\$)[{,]\s*)-?\s*["']?(""" + _SECRET_NAME + r""")["']?\s*[:=]\s*["']?([^"'\s#${},*\-][^"'\s#},]*)""")
WEBHOOK_LITERAL = re.compile(r"""(WEBHOOK_SECRET|GATEWAY_TOKEN|SMS_GATEWAY|TELEGRAM_WEBHOOK)[A-Z_]*["']?\s*[:=,]\s*["']([^"'${}\s][^"'\s]*)["']""")
FAIL_OPEN = re.compile(r"""except\b[^:]*:\s*(return\s+(True|\(True|ok\b)|pass\s*#.*(allow|admit|open))""", re.I)
PASSWORD_KWARG = re.compile(r"""\b(password|passwd|secret|token)\s*=\s*["']([^"'{}\s][^"']*)["']""", re.I)
SUPERUSER_DEFAULT = re.compile(r"""os\.environ\.get\(\s*["']DB_USER["']\s*,\s*["'](kernel|postgres)["']|user\s*=\s*["'](kernel|postgres)["']""")
SUPERUSER_DB = re.compile(r"""(DB_USER|POSTGRES_USER|user)\s*[:=]\s*["']?(postgres|kernel)["']?\s*($|[,}#])""")
PROD_SHADOW = re.compile(r"""(?x)
    \b[A-Z0-9_]*_SHADOW["']?\s*[:=]\s*["']?(1|true|yes|on)\b                                   # a *_SHADOW flag turned on
  | \b[A-Z0-9_]*(_REQUIRE_TOKEN|_REQUIRED|_ENFORCE[A-Z0-9_]*|REQUIRE_[A-Z0-9_]*)["']?\s*[:=]\s*["']?(0|false|no|off|shadow)\b
  | \b[A-Z0-9_]*_MODE["']?\s*[:=]\s*["']?(shadow|legacy|off|permissive)\b                        # a *_MODE left non-enforcing
  | \bAIRAWAT_INPROCESS_COMPONENTS["']?\s*[:=]\s*["']?(1|true|yes|on)\b                          # in-process placement
    """, re.I)


def check_token_roles():
    hits = []
    for f in files((".py",)):
        for i, l in enumerate(lines(f), 1):
            if TOKEN_ROLES.search(l) and not l.lstrip().startswith("#"):
                hits.append((f, i, l))
    return hits


def check_literal_gates():
    hits = []
    for f in files((".py", ".sh", ".yml", ".yaml", ".env")):
        for i, l in enumerate(lines(f), 1):
            s = l.lstrip()
            if s.startswith("#"):
                continue
            if LITERAL_GATE.search(l):
                hits.append((f, i, l, "shared internal token/literal gate"))
            m = DEFAULT_SECRET_PY.search(l)
            if m and not m.group(1).endswith(("KEY_SECRET", "SECRET_NAME")):   # names of Vault keys, not values
                hits.append((f, i, l, f"hardcoded default for a secret: {m.group(1)}"))
            if f.endswith(".py"):
                m = PASSWORD_KWARG.search(l)
                if m and m.group(2) not in ("", "Bearer ") and not re.fullmatch(r"[A-Z0-9_]+", m.group(2)) \
                        and not m.group(2).startswith(("conformance-probe", "x-access-token")):
                    hits.append((f, i, l, f"literal credential argument: {m.group(1)}="))
            if f.endswith((".yml", ".yaml", ".env")):
                for m in SECRET_ASSIGN_YAML.finditer(l):
                    if m.group(m.lastindex).lower() not in ("true", "false", "0", "1", "required", "shadow", "enforce", "null", "none"):
                        hits.append((f, i, l, f"secret value in config: {m.group(1)}"))
    return hits


def check_webhook_secrets():
    hits = []
    for f in files((".py", ".sh", ".yml", ".yaml", ".env", ".json")):
        for i, l in enumerate(lines(f), 1):
            if l.lstrip().startswith("#"):
                continue
            m = WEBHOOK_LITERAL.search(l)
            if m:
                hits.append((f, i, l, "external webhook secret as a literal (must be Vault-held, per provider/tenant, signature-verified)"))
    return hits


_DENY_PRED = re.compile(r"^\s*def\s+(_?\w*(on_hold|_hold|denied|blocked|revoked|suspended|banned|is_disabled|refused)\w*)\s*\(")


def check_fail_open():
    """An exception handler on a gate path that ADMITS instead of refusing: (a) an allow-predicate returning
    True/ok on error; (b) a DENY-predicate (is_on_hold / is_revoked / ...) returning False on error — that admits."""
    hits = []
    for f in files((".py",)):
        L = lines(f)
        fn = None
        for i, l in enumerate(L, 1):
            m = _DENY_PRED.match(l)
            if m:
                fn = m.group(1); continue
            if re.match(r"^\s*def\s", l):
                fn = None
            if fn:
                two = l + " " + (L[i].strip() if i < len(L) and re.match(r"\s*except\b[^:]*:\s*$", l) else "")
                if re.search(r"except\b[^:]*:\s*return\s+False\b", two):
                    hits.append((f, i, l, f"deny-check {fn}() returns False (admit) on error"))
        for i, l in enumerate(L, 1):
            # one-line form, or `except ...:` followed by an admitting return on the next line
            two = l + " " + (L[i].strip() if i < len(L) and re.match(r"\s*except\b[^:]*:\s*$", l) else "")
            if FAIL_OPEN.search(two) or re.search(r"except\b[^:]*:\s*return\s+(True|ok|\(True)", two):
                ctx = " ".join(L[max(0, i - 12):i]).lower()
                if any(w in ctx for w in ("gate", "authoriz", "admit", "verify", "allowed", "ingress", "require")):
                    hits.append((f, i, l, "fail-open exception handler on a gate path"))
    return hits


def check_superuser_db():
    hits = []
    for f in files((".py", ".yml", ".yaml", ".env", ".sh")):
        if f.endswith(("install.sh", "_split_roles.py")) or "/tools/db_migrate" in f:  # the install-time superuser step
            continue
        for i, l in enumerate(lines(f), 1):
            if l.lstrip().startswith("#"):
                continue
            if (SUPERUSER_DB.search(l) and "POSTGRES_USER" not in l) or (f.endswith(".py") and SUPERUSER_DEFAULT.search(l)):
                hits.append((f, i, l, "connects as (or defaults to) the database superuser"))
    return hits


PROD_FILES = []


def check_prod_shadow():
    """Shadow / non-enforcing flags or in-process component placement in PRODUCTION config = any tracked compose /
    env file that sets AIRAWAT_ENV=production, in ANY repo (today that is only the legacy EC2 compose — there is no
    production compose for the current stack yet, RELEASE-PLAN Stage 0c). BASELINED: RELEASE-PLAN §5 flips those
    flags one per change window on purpose; a NEW shadow flag in production config fails."""
    hits = []
    for f in sorted(_tracked()):
        if not f.endswith((".yml", ".yaml", ".env")) or any(p in SKIP_DIRS for p in f.split("/")):
            continue
        L = lines(f)
        if not any(re.search(r"AIRAWAT_ENV[\"']?\s*[:=]\s*[\"']?production", l) and not l.lstrip().startswith("#") for l in L):
            continue
        PROD_FILES.append(f)
        for i, l in enumerate(L, 1):
            if not l.lstrip().startswith("#") and PROD_SHADOW.search(l):
                hits.append((f, i, l, "shadow / non-enforcing flag or in-process placement in production config"))
    return hits


def check_undeclared_routes():
    out = subprocess.run([sys.executable, os.path.join(HERE, "route_extract.py")], capture_output=True, text=True)
    routes = json.loads(out.stdout); inv = json.load(open(os.path.join(HERE, "route-inventory.json")))
    hits = []
    for svc, rs in routes.items():
        for r in rs:
            k = f"{r['method']} {r['path']}"
            if k not in (inv.get(svc) or {}):
                hits.append((f"route:{svc}", 0, k, "undeclared route"))
    return hits


CHECKS = [  # name, rule protected, fn, baselined?
    ("TOKEN_ROLES", "FND-1/FND-2 (identity carries no authority; authority only from recorded state) — DEBT-B1", check_token_roles, True),
    ("UNDECLARED_ROUTE", "FND-8 (every privileged endpoint declared + authenticated) — §0 net 4", check_undeclared_routes, False),
    ("LITERAL_SECRET_OR_GATE", "FND-9 (audience-bound, Vault-minted service tokens; no shared literals) + FND-16 (no hardcoded defaults) — DEBT-A71", check_literal_gates, False),
    ("WEBHOOK_SECRET_LITERAL", "FND-9 + GTW-14 (inbound provider secrets Vault-held per provider/tenant, signature-verified) — DEBT-B64", check_webhook_secrets, False),
    ("FAIL_OPEN_GATE", "FND-8 (fail-closed) — baseline 0 since slice-1f fixed DEBT-B47 (the account-hold check)", check_fail_open, True),
    ("SUPERUSER_DB", "ARC-3 / FND-10 (per-service least-privilege DB roles) — DEBT-B57", check_superuser_db, False),
    ("PROD_SHADOW_OR_INPROCESS", "FND-16 (enforce by default) + CMP-5 (confinement) — DEBT-A72/B51; RELEASE-PLAN §5", check_prod_shadow, True),
]


SELFTEST = [  # (pattern, a line it MUST catch) — proves no check passes vacuously
    (TOKEN_ROLES, 'roles = set(claims.get("roles", []))'),
    (LITERAL_GATE, 'if self.headers.get("X-Internal-Token") != SECRET:'),
    (LITERAL_GATE, 'curl -H "X-Run-Token: dev-run-air" "$K/v1/write"'),
    (DEFAULT_SECRET_PY, 'PW = os.environ.get("DB_PASSWORD", "kernel")'),
    (SECRET_ASSIGN_YAML, '    environment: { POSTGRES_PASSWORD: kernel }'),
    (PASSWORD_KWARG, 'psycopg2.connect(user="x", password="hunter2")'),
    (WEBHOOK_LITERAL, 'TELEGRAM_WEBHOOK_SECRET: "abc123"'),
    (FAIL_OPEN, '    except Exception: return True'),
    (SUPERUSER_DEFAULT, 'user=os.environ.get("DB_USER", "postgres")'),
    (_DENY_PRED, 'def _account_on_hold(tenant, user):'),
    (PROD_SHADOW, '      PLATFORM_AUTHORITY_MODE: shadow'),
]


def selftest():
    bad = [p.pattern[:50] for p, line in SELFTEST if not p.search(line)]
    print(("✓" if not bad else "✗") + f" banned-pattern self-test: {len(SELFTEST) - len(bad)}/{len(SELFTEST)} patterns catch their positive")
    for b in bad:
        print("    MISSES:", b)
    return not bad


def main():
    update = "--update-baseline" in sys.argv
    if not selftest():
        sys.exit(2)
    base = json.load(open(BASELINE)) if os.path.exists(BASELINE) else {}
    failed = 0; cases = []; new_base = {}
    print("▶ banned patterns (scope: " + ", ".join(SCOPE) + ")")
    print("  out of scope (legacy / fixtures — listed, not hidden): " + "; ".join(OUT_OF_SCOPE))
    for name, rule, fn, baselined in CHECKS:
        hits = fn()
        if baselined:
            fps = {}
            for h in hits:
                fp = f"{h[0]}::{norm(h[2])}"; fps[fp] = fps.get(fp, 0) + 1
            new_base[name] = fps
            old = base.get(name, {})
            new = [(fp, n - old.get(fp, 0)) for fp, n in fps.items() if n > old.get(fp, 0)]
            fixed = sum(max(0, n - fps.get(fp, 0)) for fp, n in old.items())
            ok = update or not new
            print(f"  {'✓' if ok else '✗'} {name:24} {len(hits)} occurrence(s), baselined {sum(old.values())}, "
                  f"NEW {sum(n for _, n in new)}, removed since baseline {fixed}   [{rule}]")
            for fp, n in new[:20]:
                print(f"      NEW ×{n}: {fp[:150]}")
            if name == "PROD_SHADOW_OR_INPROCESS":
                print(f"      production config files found: {len(PROD_FILES)} {PROD_FILES or '(none in the tree yet — RELEASE-PLAN Stage 0c; the check is armed for when one lands)'}")
        else:
            ok = not hits
            print(f"  {'✓' if ok else '✗'} {name:24} {len(hits)} occurrence(s) — hard fail   [{rule}]")
            for h in hits[:40]:
                print(f"      {h[0]}:{h[1]}  {h[3]}  | {norm(h[2])[:110]}")
        failed += not ok
        # matrix honesty: a baselined check with KNOWN occurrences is evidence of a violation (XFAIL), never a PASS —
        # "no new token-role read" must not make FND-1 look held while 41 baselined reads remain.
        known = len(hits) if baselined else 0
        cases.append({"case": f"banned pattern {name}: " + (f"{known} known occurrence(s), none new" if known else "no occurrence"),
                      "rules": [r.strip() for r in re.findall(r"(FND-\d+|ARC-\d+|CMP-\d+|GTW-\d+)", rule)][:3],
                      "result": "FAIL" if not ok else ("XFAIL" if known else "PASS")})
    if update:
        json.dump({"_meta": {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "note": "TOKEN_ROLES = existing token-role reads, retired by the DEBT-B1 thread layer by layer; FAIL_OPEN_GATE = DEBT-B47; PROD_SHADOW_OR_INPROCESS = RELEASE-PLAN §5"},
                   **new_base}, open(BASELINE, "w"), indent=1, sort_keys=True)
        print("  baseline written:", os.path.relpath(BASELINE, ROOT))
    if "--json" in sys.argv:
        json.dump({"env": "local-dev", "mode": "banned", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "git_sha": "", "cases": cases}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    print(("✓" if not failed else "✗") + f" banned patterns: {failed} check(s) failing")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

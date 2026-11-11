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
import sys as _s_ev, os as _o_ev; _s_ev.path.insert(0, _o_ev.path.join(_o_ev.path.dirname(_o_ev.path.dirname(_o_ev.path.abspath(__file__))), "verify")); import evidence as _ev  # slice-1h B99

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
        docker = parts[-1].startswith("Dockerfile") and ".sh" in exts           # Dockerfiles join the shell-like checks
        if any(p in SKIP_DIRS for p in parts) or parts[-1].startswith("test_") or not (f.endswith(exts) or docker):
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
# slice-1g (DEBT-B92 / review N2): EVERY form of reading `roles` — the old pattern required a token-ish receiver NAME and
# missed the dominant `(claims or {}).get("roles")` idiom (≈52 uncounted reads). Any read of the "roles" key counts;
# reads of recorded state are BASELINED with the rest and retired by the DEBT-B1 thread (an over-count is reviewable, an
# under-count is a silent hole).
TOKEN_ROLES = re.compile(r"""(?x)
    \.get\(\s*["']roles["']                                   # x.get("roles") — any receiver: (claims or {}).get, chained .get(...).get
  | \[\s*["']roles["']\s*\]                                  # x["roles"]
  | \bgetattr\(\s*[^,()]+,\s*["']roles["']                     # getattr(x, "roles")
  | ["']roles["']\s+(?:not\s+)?in\b                             # "roles" in claims
  | \.(?:pop|setdefault)\(\s*["']roles["']                      # x.pop("roles") / x.setdefault("roles", …)
  | \b(?:claims|_claims|cl|_cl|tok|token|payload|me|principal|ident|identity|session|jwt|bearer)\.roles\b   # attribute form
  | \bitemgetter\(\s*["']roles["']                               # operator.itemgetter("roles")
    """)
LITERAL_GATE = re.compile(r"""X-Internal-Token|_INTERNAL["']\s*,\s*["'][^"']+["']|INTERNAL_TOKEN\s*=\s*["'][^"']+["']"""
                          r"""|-H\s*["'](X-[A-Za-z-]*Token|Authorization):\s*(Bearer\s+)?[A-Za-z0-9][^"'$\s]*["']""")   # literal token header
# a secret-bearing NAME (not an audience / URL / path / Vault key-name / file reference) with a literal default value
_SECRET_NAME = r"[A-Z0-9_]*(PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)(?!_(AUDIENCE|AUD|URL|FILE|PATH|VAULT_PATH|TTL|NAME|REQUIRED|HEADER)\b)(?![A-Z0-9_]*(AUDIENCE|_AUD\b|_URL|_FILE|_PATH|KEY_SECRET|_MOUNT|_READERS|_CALLERS|_PERIOD|_TTL))[A-Z0-9_]*"
DEFAULT_SECRET_PY = re.compile(r"""os\.(?:environ\.get|getenv)\(\s*["'](""" + _SECRET_NAME + r""")["']\s*,\s*["']([^"'/][^"']*)["']""")
# slice-1g (DEBT-B92 / review N3) — the forms that evaded the literal checks:
OR_LITERAL_PY = re.compile(r"""os\.(?:environ\.get|getenv)\(\s*["'](""" + _SECRET_NAME + r""")["'][^)]*\)\s*or\s*["']([^"'/\s][^"']*)["']""")   # env or "lit"
SHELL_DEFAULT = re.compile(r"""\$\{(""" + _SECRET_NAME + r"""):?[-=]([^}$:?][^}]*)\}""")                                   # ${X_TOKEN:-lit}
SHELL_ASSIGN = re.compile(r"""^\s*(?:export\s+)?(""" + _SECRET_NAME + r""")=["']?([^"'\s$`(][^"'\s]*)""")                  # export X_PASSWORD=lit
DOCKER_ENV = re.compile(r"""^\s*(?:ENV|ARG)\s+(""" + _SECRET_NAME + r""")[=\s]+["']?([^"'\s$][^"'\s]*)""")                  # Dockerfile ENV/ARG
DSN_CRED = re.compile(r"""\b[a-z][a-z0-9+.-]*://[^:/\s"'@${}]+:([^@\s"'${}<>]+)@""")                                         # scheme://user:pass@
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
            m = OR_LITERAL_PY.search(l)
            if m:
                hits.append((f, i, l, f"literal fallback for a secret (`or \"…\"`): {m.group(1)}"))
            if f.endswith(".sh") or f.split("/")[-1].startswith("Dockerfile"):
                for rx, what in ((SHELL_DEFAULT, "shell default"), (SHELL_ASSIGN, "shell assignment"), (DOCKER_ENV, "Dockerfile ENV/ARG")):
                    m = rx.search(l)
                    if m:
                        hits.append((f, i, l, f"literal secret in {what}: {m.group(1)}"))
            m = DSN_CRED.search(l)
            if m and m.group(1) not in ("password", "PASSWORD", "pass", "***", "…"):
                hits.append((f, i, l, "credential in a connection URL"))
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



# ── GATED_DOOR_DIRECT (DEBT-B174 class fix) ──────────────────────────────────────────────────────────────────────
# The filestore (svc:filestore) and the model gateway (svc:model-gateway) ENFORCE an audience-bound token from a
# declared caller (ARCHITECTURE-FLOWS §h). Each calling service reaches them ONLY through its one client, which always
# attaches its token — the shared aos_svc package; ~35 hand-built requests that forgot it broke upload, aos upload and
# the AI drawer. HARD: any
# other use of a door's URL to BUILD a request fails — a variable bound to the door's env var (FILESTORE_URL /
# EMBED_URL / …, or imported from hostcore) used in a URL expression or call, or a literal door host — in EVERY
# repository (components included: a component is not a declared caller at all; it goes through the broker).
# Presence tests (`if not FILESTORE_URL:`) and assignments are not calls and are allowed.
GATED_DOOR_ENVS = {"FILESTORE_URL", "FILESTORE", "EMBED_URL", "MODEL_GATEWAY_URL", "MODELGW_URL"}
GATED_DOOR_HOST = re.compile(r"https?://(?:airawat-[a-z-]*)?(?:filestore|model-gateway|embed)(?::\d+)?(?:/|$)")
GATED_DOOR_SCOPE = ["kernel", "network", "platform-spec/reference", "components", "deploy"]
GATED_DOOR_CLIENTS = {   # the ONE shared internal service client (every platform image, /opt/airawat/lib) — nothing else
    "deploy/runtime/lib/aos_svc/__init__.py": {"*"}, "deploy/runtime/lib/aos_svc/tokens.py": {"*"},
}
GATED_DOOR_HANDOFFS = {  # (file, function): why a door URL is passed on rather than called
    ("platform-spec/reference/app_host.py", "_engine_ctx"): "ctx['embed_url'] for in-process engines — their ctx['http'] goes through Handler._http, which hands any door URL to hostcore.SVC (aos_svc)",
}
GATED_DOOR_RECORDED = {  # legacy dev tools against the retired deploy/local stack — listed every run, debt DEBT-B178
    "platform-spec/reference/tools/republish_portal.py", "components/engines/lifecycle-engine/publish_governed.py",
    "components/drivers/crowd-sim-vision/tools/harvest_sprites.py",
    "components/tools/deploy_component.py", "components/tools/stage_and_publish.py", "components/tools/upload_bind_run.py",   # EC2-era operator scripts
    "components/tools/publish_to_staging.py",                                                                                 # legacy staging publish (2026-11-11)
}


def _gated_door_hits_in(src, path="<src>"):
    import ast, warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(src)
    except SyntaxError:
        return []
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    def env_door(v):           # os.environ.get("FILESTORE_URL", …) / os.getenv(…) / os.environ["…"] anywhere in v
        for n in ast.walk(v):
            if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value in GATED_DOOR_ENVS:
                f = n.func
                if (isinstance(f, ast.Attribute) and f.attr in ("get", "getenv")) or (isinstance(f, ast.Name) and f.id == "getenv"):
                    return True
            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in GATED_DOOR_ENVS:
                return True
        return False
    doorvars = set(GATED_DOOR_ENVS)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and env_door(n.value):
            doorvars |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    def func_of(n):
        while n in parent:
            n = parent[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n.name
        return None
    def env_default(n):        # the literal default inside os.environ.get("X", "<here>")
        p = parent.get(n)
        return isinstance(p, ast.Call) and n in p.args[1:] and env_door(p)
    def docstring(n):
        p = parent.get(n)
        return isinstance(p, ast.Expr)
    def presence_only(n):      # if X: / if not X: / X and … — not a call
        p = parent.get(n)
        return isinstance(p, (ast.If, ast.IfExp, ast.While, ast.BoolOp, ast.UnaryOp, ast.Compare)) and getattr(p, "test", n) is n or \
               (isinstance(p, (ast.BoolOp, ast.UnaryOp, ast.Compare)))
    hits = []
    for n in ast.walk(tree):
        use = None
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in doorvars:
            use = n.id
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and n.attr in GATED_DOOR_ENVS:
            use = n.attr
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and GATED_DOOR_HOST.search(n.value) \
                and not env_default(n) and not docstring(n):
            use = "literal " + n.value[:60]
        if not use or (not use.startswith("literal") and presence_only(n)):
            continue
        hits.append((path, getattr(n, "lineno", 0), use, func_of(n)))
    return hits


def check_gated_door_direct():
    hits = []
    for f in sorted(_tracked()):
        if not f.endswith(".py") or not any(f.startswith(t + "/") for t in GATED_DOOR_SCOPE):
            continue
        parts = f.split("/")
        if any(p in SKIP_DIRS for p in parts) or parts[-1].startswith(("test_", "selftest_")):
            continue
        allowed = GATED_DOOR_CLIENTS.get(f, set())
        if "*" in allowed:
            continue
        for path, ln, use, fn in _gated_door_hits_in("\n".join(lines(f)), f):
            if fn in allowed or (f, fn) in GATED_DOOR_HANDOFFS:
                continue
            if f in GATED_DOOR_RECORDED:
                print(f"      recorded exception (DEBT-B178, legacy dev tool): {f}:{ln} {use}")
                continue
            hits.append((f, ln, f"{use} in {fn or '<module>'}", "direct request to a gated door outside its client"))
    return hits


GATED_DOOR_SELFTEST = [  # (source, must_hit)
    ('import os, urllib.request\nFS = os.environ.get("FILESTORE_URL", "http://filestore:8095")\ndef f(b):\n    return urllib.request.urlopen(FS + "/files", data=b)\n', True),
    ('from hostcore import EMBED_URL\ndef f(r):\n    return urllib.request.Request(EMBED_URL + "/complete", data=r)\n', True),
    ('import hostcore\ndef f(fid):\n    return urlopen(f"{hostcore.FILESTORE_URL}/files/{fid}")\n', True),
    ('def f():\n    return urlopen("http://model-gateway:8104/complete")\n', True),
    ('import os\nFILESTORE = os.getenv("FILESTORE_URL")\ndef f(x):\n    return _http("GET", FILESTORE + "/files/" + x)\n', True),
    ('import os\nFILESTORE_URL = os.environ.get("FILESTORE_URL", "http://filestore:8095")\ndef f():\n    if not FILESTORE_URL:\n        raise X()\n', False),
    ('import hostcore, os\nhostcore.FILESTORE_URL = os.environ.get("FILESTORE_URL", "http://filestore:8095")\n', False),
    ('def f():\n    """Calls http://filestore:8095 via the broker."""\n    return broker.put(b)\n', False),
]


def selftest_gated_door():
    bad = [src.split("\n")[-2].strip() for src, must in GATED_DOOR_SELFTEST if bool(_gated_door_hits_in(src)) != must]
    print(("✓" if not bad else "✗") + f" GATED_DOOR_DIRECT self-test: {len(GATED_DOOR_SELFTEST) - len(bad)}/{len(GATED_DOOR_SELFTEST)}")
    for b in bad:
        print("    WRONG ON:", b)
    return not bad


# ── DEV_STUB_OUTSIDE_LOCALDEV (fixtures decision) ────────────────────────────────────────────────────────────────
# The stub model provider is DEV-ONLY: its image (airawatos-devstub), its host (stub-provider) and its code may be named
# ONLY by the local-dev stack, the image build, the dev-profile installer fixtures and the verification nets. Any other
# tracked file naming it — a production compose / manifest, a shipped Dockerfile, a service's code — fails. (At runtime
# the stub also refuses AIRAWAT_ENV=production, and the gateway drops a dev_stub provider in production.)
DEV_STUB_REF = re.compile(r"airawatos-devstub|stub[-_]provider")
DEV_STUB_ALLOWED = ("deploy/local-dev/", "deploy/build-images.sh", "deploy/installer/", "verify/", "conformance/", "docs/",
                    "platform-spec/reference/model_gateway.py",          # the production REFUSAL itself
                    "platform-spec/reference/test_", ".github/")


def check_dev_stub_outside_localdev():
    hits = []
    for f in sorted(_tracked()):
        if f.startswith(DEV_STUB_ALLOWED) or any(p in SKIP_DIRS for p in f.split("/")) or f.endswith((".png", ".jpg", ".pdf", ".gz")):
            continue
        for i, l in enumerate(lines(f), 1):
            if DEV_STUB_REF.search(l):
                hits.append((f, i, l.strip()[:120], "dev-only stub provider named outside local-dev"))
    return hits

CHECKS = [  # name, rule protected, fn, baselined?
    ("TOKEN_ROLES", "FND-1/FND-2 (identity carries no authority; authority only from recorded state) — DEBT-B1", check_token_roles, True),
    ("UNDECLARED_ROUTE", "FND-8 (every privileged endpoint declared + authenticated) — §0 net 4", check_undeclared_routes, False),
    ("LITERAL_SECRET_OR_GATE", "FND-9 (audience-bound, Vault-minted service tokens; no shared literals) + FND-16 (no hardcoded defaults) — DEBT-A71", check_literal_gates, False),
    ("WEBHOOK_SECRET_LITERAL", "FND-9 + GTW-14 (inbound provider secrets Vault-held per provider/tenant, signature-verified) — DEBT-B64", check_webhook_secrets, False),
    ("FAIL_OPEN_GATE", "FND-8 (fail-closed) — baseline 0 since slice-1f fixed DEBT-B47 (the account-hold check)", check_fail_open, True),
    ("SUPERUSER_DB", "ARC-3 / FND-10 (per-service least-privilege DB roles) — DEBT-B57", check_superuser_db, False),
    ("PROD_SHADOW_OR_INPROCESS", "FND-16 (enforce by default) + CMP-5 (confinement) — DEBT-A72/B51; RELEASE-PLAN §5", check_prod_shadow, True),
    ("DEV_STUB_OUTSIDE_LOCALDEV", "FND-16 (no dev convenience in production) — fixtures decision: the stub model provider is dev-only", check_dev_stub_outside_localdev, False),
    ("GATED_DOOR_DIRECT", "FND-9 (audience-bound service tokens on every internal call) + ARC-1 (declared edges only) — DEBT-B174", check_gated_door_direct, False),
]


SELFTEST = [  # (pattern, a line it MUST catch) — proves no check passes vacuously
    (TOKEN_ROLES, 'roles = set(claims.get("roles", []))'),
    # slice-1g (DEBT-B92): one self-test per token-role READ FORM
    (TOKEN_ROLES, 'if "admin" in (claims or {}).get("roles", []):'),
    (TOKEN_ROLES, 'r = (self._claims() or {}).get("roles") or []'),
    (TOKEN_ROLES, 'roles = cl.get("realm_access", {}).get("roles", [])'),
    (TOKEN_ROLES, 'roles = set((_current_session().get("claims") or {}).get( "roles" , []))'),
    (TOKEN_ROLES, "ok = 'platform.steward' in user['roles']"),
    (TOKEN_ROLES, 'rs = decoded [ "roles" ]'),
    (TOKEN_ROLES, 'rs = getattr(principal_obj, "roles", ())'),
    (TOKEN_ROLES, 'if "roles" in claims and claims_ok:'),
    (TOKEN_ROLES, 'rs = c.pop("roles", [])'),
    (TOKEN_ROLES, 'payload.setdefault("roles", [])'),
    (TOKEN_ROLES, 'if "steward" in principal.roles:'),
    (TOKEN_ROLES, 'get_roles = operator.itemgetter("roles")'),
    (DEFAULT_SECRET_PY, 'PW = os.getenv("DB_PASSWORD", "kernel")'),
    (OR_LITERAL_PY, '_login = {"password": os.environ.get("AIRAWAT_PASSWORD") or "Airawat@123"}'),
    (SHELL_DEFAULT, 'VAULT_TOKEN=${VAULT_TOKEN:-airawat-dev-root} python3 x.py'),
    (SHELL_ASSIGN, 'export ADMIN_PASSWORD=hunter2'),
    (DOCKER_ENV, 'ENV VAULT_TOKEN=airawat-dev-root'),
    (DSN_CRED, 'DATABASE_URL = "postgresql://kernel:kernel@postgres:5432/airawat"'),
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


SELFTEST_NEG = [  # (pattern, a line it must NOT catch) — the broadened patterns stay precise
    (TOKEN_ROLES, 'role = rec.get("role")'),
    (TOKEN_ROLES, '# roles come from the decision function, never claims.get("x")'),
    (SHELL_DEFAULT, 'VAULT_TOKEN=${VAULT_TOKEN:?set VAULT_TOKEN}'),
    (SHELL_ASSIGN, 'export VAULT_TOKEN="$(cat /vault/token)"'),
    (DSN_CRED, 'DSN = f"postgresql://{user}:{pw}@{host}/db"'),
    (OR_LITERAL_PY, 'tok = os.environ.get("VAULT_TOKEN") or ""'),
    (DEFAULT_SECRET_PY, 'CMOUNT = os.environ.get("COMPONENT_SECRETS_MOUNT", "components")'),
    (SHELL_DEFAULT, 'token_period=${AOS_VAULT_TOKEN_PERIOD:-1h}'),                                   # a duration, not a secret (R7-6)   # a mount NAME, not a secret
    (OR_LITERAL_PY, 'R = (os.environ.get("RUN_TOKEN_READERS") or "scheduler")'),                   # a caller list
    (OR_LITERAL_PY, 'A = (os.environ.get("SECRETS_ACCEPT_AUD") or "svc:secrets")'),               # an audience
]


def selftest():
    bad = [p.pattern[:50] + " ⟵ " + line for p, line in SELFTEST if not p.search(line)]
    bad += ["FALSE POSITIVE " + p.pattern[:40] + " ⟵ " + line for p, line in SELFTEST_NEG if p.search(line)]
    print(("✓" if not bad else "✗") + f" banned-pattern self-test: {len(SELFTEST) + len(SELFTEST_NEG) - len(bad)}/{len(SELFTEST) + len(SELFTEST_NEG)} "
          "(every positive caught, every negative left alone)")
    for b in bad:
        print("    MISSES:", b)
    return not bad


def main():
    update = "--update-baseline" in sys.argv
    if not (selftest() & selftest_gated_door()):
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
            if name == "TOKEN_ROLES":     # slice-1h (exit condition 6, DEBT-B103): every baselined file has an OWNING debt id
                owners = base.get("TOKEN_ROLES_DEBTS", {})
                unowned = sorted({h[0] for h in hits} - set(owners))
                if unowned:
                    ok = False
                    print(f"      ✗ token-role reads in files with NO owning debt id (add to TOKEN_ROLES_DEBTS): {unowned}")
                else:
                    print(f"      every file with a known token-role read has an owning debt id ({len(owners)} files: "
                          + ", ".join(sorted({v.split(' · ')[1].split(' (')[0] for v in owners.values()})) + ")")
                if update:
                    new_base["TOKEN_ROLES_DEBTS"] = {f: owners[f] for f in sorted({h[0] for h in hits}) if f in owners}
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
        _ev.seal(sys.argv[sys.argv.index("--json") + 1])
    print(("✓" if not failed else "✗") + f" banned patterns: {failed} check(s) failing")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

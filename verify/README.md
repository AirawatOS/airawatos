# verify/ — the assurance nets (FIX-PLAN §0), runnable locally

| Net | Script | What it proves |
|---|---|---|
| 4 · route inventory | `route_inventory_test.py` (+ `route_extract.py`, `route_probe.py`, `route-inventory.json`) | every route each service exposes is declared (public / login / authority / internal); every non-public route refuses an anonymous call; prints the REVIEW list (public routes that should not be) |

`route-inventory.json` is the declaration. Adding a route without declaring it fails TEST 1. Declaring a route
`public` requires a `why`; a route public today that should not be also carries `review` (with its debt id) and is
listed on every run. A handler that validates before authenticating carries a `body`/`sample` so the probe reaches
its gate, plus an `ordering` note (DEBT-B74).
| 6 · banned patterns | `banned_patterns.py` (+ `banned-baseline.json`) | static checks, each mapped to the rule it protects: TOKEN_ROLES (FND-1/FND-2, **baselined** against DEBT-B1 — fails only on NEW reads), UNDECLARED_ROUTE (FND-8), LITERAL_SECRET_OR_GATE + WEBHOOK_SECRET_LITERAL (FND-9/FND-16/GTW-14 — **hard fail, no baseline**), FAIL_OPEN_GATE (FND-8, baselined: the one DEBT-B47 entry), SUPERUSER_DB (ARC-3/FND-10, hard), PROD_SHADOW_OR_INPROCESS (FND-16/CMP-5, baselined against RELEASE-PLAN §5; production config in the tree: none yet). A self-test proves every pattern catches its positive. Legacy stacks are listed as out of scope on every run. |
| 8 · secret + vulnerability scans | `scans.py` (+ `scan-baseline/{gitleaks,trivy}.json`) | gitleaks over the full history of all five repos; trivy over every image the compose runs and over the repos' dependency manifests. Every current finding is in the baseline against a DEBT id (B77–B81); a NEW secret, a NEW CRITICAL image CVE, or any HIGH/CRITICAL dependency CVE fails. Pinned tool images: gitleaks v8.21.2, trivy 0.57.1. |
| 7 · fresh install (integrity) | `fresh_install.sh` | tears the project down with its volumes, **refuses (exit 3) unless it proves a clean slate** (0 containers, 0 volumes, 0 networks of the project), runs the installer (Phase 15 functional proof included), then proves every project volume was **created by this run**. Proven to refuse: a leftover volume → exit 3. |

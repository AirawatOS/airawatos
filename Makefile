# AirawatOS — the assurance nets, runnable locally with one command (FIX-PLAN §0, slice-1d).
#   make verify        everything: static checks, a FRESH install (with the functional proof), conformance both
#                      modes, flow-map, Vault scope, route inventory, secret + vulnerability scans, the status matrix
#   make verify-fast   everything except the fresh install (runs against the stack that is up)
#   make <target>      any single net below
# Needs: docker (with compose v2), python3, git. The fresh install WIPES the local-dev stack's volumes.
.PHONY: verify verify-fast banned gtw-static fresh-install conformance flowmap vaultscope routes scans matrix decide-unit

verify: banned gtw-static decide-unit fresh-install conformance flowmap vaultscope routes scans matrix
	@echo "✓ make verify: all assurance nets green"

verify-fast: banned gtw-static decide-unit conformance flowmap vaultscope routes scans matrix
	@echo "✓ make verify-fast: all assurance nets green (no fresh install)"

banned:          ## net 6 — banned patterns (static), each mapped to its rule
	python3 verify/banned_patterns.py --json conformance/results/local-dev-banned.json

gtw-static:      ## GTW — static evidence for gateway rules no black-box case reaches (XFAIL = known violation)
	python3 verify/gtw_static.py

decide-unit:     ## net 5 — unit tests of the one decision function
	cd kernel && python3 services/authz/test_decide.py

fresh-install:   ## net 7 — fresh install from a PROVEN-empty slate, incl. the Phase 15 functional proof
	verify/fresh_install.sh

conformance:     ## net 7 — conformance, internal + external modes, writing matrix results
	verify/conformance_matrix.sh 1

flowmap:         ## ARC — flow-map test (network membership + live probes)
	python3 conformance/flow_map_test.py

vaultscope:      ## ARC-7 — each service reads only its own Vault paths
	python3 conformance/vault_scope_test.py

routes:          ## net 4 — route inventory: every route declared; every non-public route refuses anonymous
	python3 verify/route_inventory_test.py

scans:           ## net 8 — gitleaks (history) + trivy (images, manifests)
	python3 verify/scans.py all

matrix:          ## the status matrix from every results file
	python3 conformance/build_matrix.py

# AirawatOS — the assurance nets, runnable locally with one command (FIX-PLAN §0, slice-1d).
#   make verify        everything: static checks, a FRESH install (with the functional proof), conformance both
#                      modes, flow-map, Vault scope, route inventory, secret + vulnerability scans, the status matrix
#   make verify-fast   everything except the fresh install (runs against the stack that is up)
#   make <target>      any single net below
# Needs: docker (with compose v2), python3, git. The fresh install WIPES the local-dev stack's volumes.
# slice-1h (DEBT-B99): ONE run id per make invocation, exported to every net; each results file carries it and the strict
# matrix refuses any file of another run. `clean-results` deletes the previous run's evidence FIRST.
ifeq ($(origin AOS_RUN_ID),undefined)
AOS_RUN_ID := $(shell python3 verify/evidence.py new-run-id)
endif
export AOS_RUN_ID

.PHONY: svcclient unit matrix-fast clean-results vault-renewal dbgrants ops restore-drill listen verify verify-fast banned gtw-static known-violations fresh-install conformance flowmap vaultscope routes scans matrix decide-unit secret-names gateflags netdoors build-context images installer

verify: clean-results banned svcclient gtw-static known-violations decide-unit unit secret-names gateflags build-context images installer fresh-install conformance flowmap vaultscope vault-renewal netdoors dbgrants routes listen ops scans restore-drill matrix
	@echo "✓ make verify: all assurance nets green"

verify-fast: clean-results banned svcclient gtw-static known-violations decide-unit secret-names gateflags build-context images conformance flowmap vaultscope vault-renewal netdoors dbgrants routes listen ops scans restore-drill matrix-fast
	@echo "✓ make verify-fast: all assurance nets green (no fresh install)"

clean-results:   ## slice-1h B99 — delete the previous run's evidence so only THIS run's can reach the matrix
	rm -f conformance/results/*.json
	@echo "▶ run $(AOS_RUN_ID): previous evidence removed"

banned:          ## net 6 — banned patterns (static), each mapped to its rule
	python3 verify/banned_patterns.py --json conformance/results/local-dev-banned.json

svcclient:       ## B174 — the shared internal service client (aos_svc): edges == ARCHITECTURE-FLOWS table, CI pins current, behaviour
	python3 verify/svc_edges.py
	python3 verify/aos_svc_test.py

gtw-static:      ## GTW — static evidence for gateway rules no black-box case reaches (XFAIL = known violation)
	python3 verify/gtw_static.py

known-violations: ## matrix honesty — recorded violations of rules that narrow PASS cases would show HELD (XFAIL)
	python3 verify/known_violations.py

REF_IMAGE ?= $(shell awk '/^ *image: *manishsv\/airawatos-reference:/{print $$2; exit}' deploy/local-dev/docker-compose.dev.yml)
secret-names:    ## B90 — the secrets broker + model-gateway refuse traversal names and follow no redirects (no network)
	docker run --rm --network none -e AIRAWAT_ENV=development -v $(CURDIR)/platform-spec/reference:/r:ro -v $(CURDIR)/verify:/v:ro $(REF_IMAGE) python /v/secret_names_test.py

gateflags:       ## B83 — one flag parser for gates + prod guard; production refuses any shadow flag set at all (throwaway containers)
	python3 verify/gateflags_test.py

build-context:   ## B94 — no env file, credential or runtime data reaches any image build context (probe builds + canaries)
	python3 verify/build_context_test.py

images:          ## B80/B94 — Dockerfiles digest-pinned + locked; every stack image recorded in IMAGES.lock.json and running as recorded
	python3 verify/images_test.py
	python3 verify/images_selftest.py

installer:       ## B100/R7-1 — installer survives a clean host and names any failing phase (live fault injection)
	python3 verify/write_guard_test.py
	python3 verify/installer_test.py --live

decide-unit:     ## net 5 — unit tests of the one decision function
	cd kernel && python3 services/authz/test_decide.py

unit:            ## every repository's OWN unit suites (kernel pytest, network, platform-spec, components) in their images
	python3 verify/unit_suites.py

fresh-install:   ## net 7 — fresh install from a PROVEN-empty slate, incl. the Phase 15 functional proof
	verify/fresh_install.sh

conformance:     ## net 7 — conformance, internal + external modes, writing matrix results
	verify/conformance_matrix.sh 1

flowmap:         ## ARC — flow-map test (network membership + live probes)
	python3 conformance/flow_map_test.py

vaultscope:      ## ARC-7 — each service reads only its own Vault paths
	python3 conformance/vault_scope_test.py
	python3 verify/vault_scope_selftest.py

netdoors:        ## B86 — every Network internal door admits EXACTLY its declared callers (ARCHITECTURE-FLOWS table, live)
	python3 conformance/net_doors_test.py

routes:          ## net 4 — route inventory: every route declared; every non-public route refuses anonymous
	python3 verify/route_inventory_test.py

listen:          ## ARC-5 — no Airawat service listens on a non-loopback address (compose + live) — slice-1g B95
	python3 verify/listen_test.py

scans:           ## net 8 — gitleaks (history) + trivy (images, manifests)
	python3 verify/scans.py all

matrix:          ## the status matrix — STRICT: fresh, complete, passing evidence of THIS run only (B99)
	python3 verify/matrix_selftest.py
	python3 conformance/build_matrix.py --strict

matrix-fast:     ## verify-fast's matrix: strict, except the fresh install's functional evidence (not produced without a fresh install)
	python3 conformance/build_matrix.py --strict --optional functional

vault-renewal:   ## B96 — every service keeps Vault access across several short token lifetimes; a lost token is loud + unhealthy
	python3 verify/svc_health_test.py
	python3 verify/vault_renewal_test.py

ops:             ## B102 — log rotation everywhere, a rotated Vault audit device, the backup set covers every volume
	python3 verify/ops_test.py

restore-drill:   ## B102 — back up, DESTROY (down -v), restore, prove every store came back (identity, Vault, Postgres, files)
	python3 verify/backup_restore_selftest.py
	python3 verify/restore_drill.py

dbgrants:        ## B93/ARC-3 — DB-grant audit: least-privilege roles, only kernel/network/identity reach the fact store
	python3 verify/db_grant_audit.py
	python3 verify/db_grant_audit_selftest.py

#!/usr/bin/env python3
"""Seed a SYNTHETIC, NON-PERSONAL perf dataset into local-dev (Consolidation phase 4).

~1,000,000 registry_version rows across several `perf.*` schemas, several versions each, spread over several
synthetic tenants, bulk-loaded via COPY into the kernel's Postgres. Bitemporal invariants are respected (one
open row per id; older versions closed with tx_to) and `content_hash` is computed EXACTLY as the kernel does
(sha256 of the sorted-compact object minus `version`), so the audit-chain verifier sees consistent hashes.

SYNTHETIC + DEV-ONLY + LOUD:
  * Refuses unless you pass --confirm-dev (or SEED_CONFIRM=1); refuses if AIRAWAT_ENV=production.
  * Writes ONLY `perf.*` schemas under `perfcity-*` tenants — never a real schema or tenant.
  * NEVER run against production. This bypasses the governed write path (no schema governance, no signature) —
    it is a read/query/point-in-time load fixture only; synthetic rows are deliberately UNSIGNED.
  * Idempotent: if the target is already present it no-ops; otherwise it DELETEs `perf.*` rows and re-seeds.

Run (host; needs docker):  python3 perf/seed.py --confirm-dev [--total 1000000]
"""
import argparse, hashlib, json, os, subprocess, sys, time

PG = os.environ.get("PERF_PG_CONTAINER", "airawat-ld-postgres")
PSQL = ["docker", "exec", "-i", PG, "psql", "-U", "kernel", "-d", "kernel", "-v", "ON_ERROR_STOP=1", "-qtA"]
TENANTS = ["perfcity-a", "perfcity-b", "perfcity-c"]
SCHEMAS = ["perf.record_alpha", "perf.record_beta", "perf.record_gamma", "perf.record_delta", "perf.record_epsilon"]
VERSIONS = 4                     # versions per base id → bitemporal history for point-in-time
OWNER = "user://perfcity-a/perf-seeder"   # non-personal; a synthetic service principal as the row agent

# A small point-in-time fixture stewarded by the SAME tenant a harness principal authenticates as
# (component-publisher@localdev-network), so the owner-gated history endpoint returns 200 and the bitemporal
# as-of lookup is measurable on a record with real version history. ids are `ds:localdev-network:perf.pit/…`.
PIT_TENANT = "localdev-network"
PIT_SCHEMA = "perf.pit"
PIT_IDS = 50
PIT_VERSIONS = 6
PIT_OWNER = "user://localdev-network/perf-seeder"


def _chash(obj):
    body = {k: v for k, v in obj.items() if k != "version"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _psql(sql):
    return subprocess.run(PSQL + ["-c", sql], capture_output=True, text=True)


def _copy_escape(s):
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-dev", action="store_true")
    ap.add_argument("--total", type=int, default=1_000_000)
    a = ap.parse_args()
    if os.environ.get("AIRAWAT_ENV") == "production":
        sys.exit("REFUSED: AIRAWAT_ENV=production — synthetic perf seed is dev-only.")
    if not (a.confirm_dev or os.environ.get("SEED_CONFIRM") == "1"):
        sys.exit("REFUSED: pass --confirm-dev (or SEED_CONFIRM=1). This loads SYNTHETIC dev-only data; never in production.")

    groups = len(TENANTS) * len(SCHEMAS)
    ids_per_group = max(1, a.total // (groups * VERSIONS))
    pit_rows = PIT_IDS * PIT_VERSIONS
    target = ids_per_group * groups * VERSIONS + pit_rows
    print(f"[seed] target ≈ {target:,} rows: {len(TENANTS)} tenants × {len(SCHEMAS)} schemas × {ids_per_group:,} ids × {VERSIONS} versions"
          f" + {pit_rows} point-in-time fixture rows ({PIT_SCHEMA} @ {PIT_TENANT})")

    # idempotency: already seeded?
    r = _psql("SELECT count(*) FROM registry_version WHERE object #>> '{schema}' LIKE 'perf.%'")
    have = int((r.stdout or "0").strip() or 0) if r.returncode == 0 else 0
    if have >= target:
        print(f"[seed] already present ({have:,} perf.* rows ≥ target) — no-op (idempotent)."); return
    if have:
        print(f"[seed] {have:,} stale perf.* rows — deleting for a clean re-seed…")
        _psql("DELETE FROM registry_version WHERE object #>> '{schema}' LIKE 'perf.%'")

    base_t = int(time.time()) - 86400 * 30     # start 30 days ago so versions spread over time
    def ts(sec): return time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(sec))

    cols = "id,kind,version,object,valid_from,valid_to,tx_from,tx_to,content_hash,retracted,agent,schema_version"
    proc = subprocess.Popen(PSQL + ["-c", f"COPY registry_version({cols}) FROM STDIN"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    t0 = time.perf_counter(); n = 0
    try:
        for ti, tenant in enumerate(TENANTS):
            for si, schema in enumerate(SCHEMAS):
                for i in range(ids_per_group):
                    oid = f"ds:{tenant}:{schema}/perf-{si}-{i}"
                    for v in range(1, VERSIONS + 1):
                        tx = base_t + (ti * 7 + si) * 1000 + i * VERSIONS + v     # monotone-ish per id
                        txf = ts(tx)
                        txt = ts(tx + 1) if v < VERSIONS else "\\N"              # close older versions; last open
                        obj = {"schema": schema, "id": oid, "tenant": tenant,
                               "code": f"{si}-{i}", "value": i * 10 + v, "rev": v,
                               "note": f"synthetic perf fixture v{v}", "payload": {"a": i % 97, "b": (i * v) % 1000}}
                        ch = _chash(obj)
                        row = "\t".join([oid, "entity", str(v), _copy_escape(json.dumps(obj, separators=(",", ":"))),
                                         txf, "\\N", txf, txt, ch, "f", OWNER, f"perf.v0/{schema}"])
                        proc.stdin.write(row + "\n"); n += 1
        # point-in-time fixture (owned/stewarded by localdev-network) — versions spread over days for as-of
        for i in range(PIT_IDS):
            oid = f"ds:{PIT_TENANT}:{PIT_SCHEMA}/pit-{i}"
            for v in range(1, PIT_VERSIONS + 1):
                tx = base_t + i * PIT_VERSIONS * 86400 + v * 86400     # one version per day
                txf = ts(tx)
                txt = ts(tx + 86400) if v < PIT_VERSIONS else "\\N"
                obj = {"schema": PIT_SCHEMA, "id": oid, "tenant": PIT_TENANT,
                       "code": f"pit-{i}", "value": i * 100 + v, "rev": v,
                       "note": f"synthetic point-in-time fixture v{v}"}
                ch = _chash(obj)
                row = "\t".join([oid, "entity", str(v), _copy_escape(json.dumps(obj, separators=(",", ":"))),
                                 txf, "\\N", txf, txt, ch, "f", PIT_OWNER, f"perf.v0/{PIT_SCHEMA}"])
                proc.stdin.write(row + "\n"); n += 1
        proc.stdin.close()
        out, err = proc.communicate(timeout=1800)
        if proc.returncode != 0:
            sys.exit(f"[seed] COPY failed: {err[:400]}")
    except BrokenPipeError:
        _, err = proc.communicate()
        sys.exit(f"[seed] COPY pipe broke: {err[:400]}")
    dt = time.perf_counter() - t0
    r = _psql("SELECT count(*) FROM registry_version WHERE object #>> '{schema}' LIKE 'perf.%'")
    final = (r.stdout or "").strip()
    print(f"[seed] wrote {n:,} rows in {dt:.1f}s ({n/dt:,.0f} rows/s via COPY); perf.* now = {final}")
    print(f"[seed] tenants={TENANTS} schemas={SCHEMAS} — SYNTHETIC, dev-only. Remove with:")
    print("       docker exec -i %s psql -U kernel -d kernel -c \"DELETE FROM registry_version WHERE object #>> '{schema}' LIKE 'perf.%%'\"" % PG)


if __name__ == "__main__":
    main()

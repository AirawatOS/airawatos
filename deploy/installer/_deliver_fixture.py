"""Installer helper (Phase 15, dev profile) — certify + deliver (source as a filestore component_asset) the
component directories staged under /app/_seed3 into this install, re-homed to the <instance>-developer steward.
Runs INSIDE app-host (reuses seed_base_os helpers + hostcore._store_bundle), fed on stdin by install.sh.
Env: INSTANCE, OPERATOR_PASSWORD, COMPS (comma list of <kind>s/<name> dirs under /app/_seed3). Exit 1 on any failure."""
import os, sys
os.environ.setdefault("MODE", "deliver")
sys.path.insert(0, "/app/reference")
import seed_base_os as S
from hostcore import _store_bundle
tok = S._login(S.DEVELOPER)
comps = [c for c in os.environ["COMPS"].split(",") if c]; ok = 0
for rel in comps:
    src = os.path.join("/app/_seed3", rel); dst = os.path.join("/tmp/_seed3", rel)
    txt = S._rehome(src, dst); m = S._meta(txt); cid = m["component_id"]
    cert, err = S._post(f"{S.NET}/v1/certify", {"subject_id": cid, "subject_kind": "component", "meta_yaml": txt,
                                               "files": S._files(dst)}, tok)
    if err:
        print(f"[phase15] CERTIFY-FAIL {cid}: {err[:400]}"); continue
    fid = _store_bundle(cid, m.get("version", "0.1.0"), dst, tok, is_app=False)
    print(f"[phase15] delivered {cid} (source asset {fid})"); ok += 1
print(f"[phase15] delivered {ok}/{len(comps)}")
sys.exit(0 if ok == len(comps) else 1)

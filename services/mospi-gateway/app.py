#!/usr/bin/env python3
"""MoSPI eSankhyiki GATEWAY — a small, standalone, dependency-free service that fronts the Government of
India's official MoSPI eSankhyiki open APIs (https://api.mospi.gov.in) and exposes a clean, normalized
internal HTTP API for AirawatOS drivers to consume.

WHY A SEPARATE SERVICE
  The MoSPI endpoint runs an older TLS stack that requires legacy renegotiation (modern OpenSSL rejects it
  with UNSAFE_LEGACY_RENEGOTIATION_DISABLED). Rather than relax the shared platform broker's egress TLS, we
  confine that quirk to THIS one purpose-built gateway. Certificate verification stays ON (CA + hostname);
  only the legacy-renegotiation option is enabled, and only for MoSPI. Drivers reach this gateway over the
  ordinary platform network, so the broker's strict egress TLS is unaffected.

  It is also the natural home for MoSPI concerns that don't belong in a driver: response normalization,
  polite pacing, pagination, and (later) other MoSPI products (IIP, WPI, NAS, PLFS, ASI) behind one host.

ENDPOINTS
  GET /health
  GET /cpi?base_year=2012&series=Current&state_code=99&year=2025[,2024]&month_code=&group_code=&limit=&page=
        → {"ok":true, "count":N, "records":[ normalized CPI rows ]}  (normalized field names, typed numbers)
  GET /cpi/base_years                                   → available base years / levels (passthrough)

Real official statistics only — on an upstream/parse failure it returns an error, never fabricated data.
No secrets, no auth to MoSPI (the official reference client is keyless — only a User-Agent).
"""
import json, os, ssl, urllib.parse, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOSPI_BASE = os.environ.get("MOSPI_BASE", "https://api.mospi.gov.in")
PORT = int(os.environ.get("PORT", "8107"))
UA = os.environ.get("MOSPI_UA", "AirawatOS-eSankhyiki-Gateway/0.1 (+https://airos.airawat.org)")
TIMEOUT = int(os.environ.get("MOSPI_TIMEOUT", "60"))

# Legacy-TLS context — CA + hostname verification stay ON; only enable the legacy-server-connect option
# that MoSPI's old stack needs. Scoped to this gateway; the platform broker is untouched.
_TLS = ssl.create_default_context()
_TLS.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
           "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}


def _get(path, params):
    """GET a MoSPI endpoint with legacy-TLS + polite UA; return parsed JSON (raises on transport error)."""
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    url = f"{MOSPI_BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_TLS) as r:
        return json.loads(r.read().decode("utf-8", "replace")), r.status


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _normalize_cpi(row, base_year, series):
    """Map a raw MoSPI CPI row to normalized, typed fields the driver writes verbatim into stat.price_index."""
    month_name = (row.get("month") or "").strip()
    mcode = _MONTHS.get(month_name.lower())
    year = row.get("year")
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = None
    period = f"{year:04d}-{mcode:02d}" if (year and mcode) else None
    state = (row.get("state") or "").strip()
    status = (row.get("status") or "").strip().upper()
    return {
        "indicator": "CPI",
        "base_year": str(row.get("baseyear") or base_year),
        "series": series,
        "geo_level": "national" if state.lower() in ("all india", "allindia") else "state",
        "geo_name": state or None,
        "sector": (row.get("sector") or "").strip() or None,
        "group": (row.get("group") or "").strip() or None,
        "subgroup": (row.get("subgroup") or "").strip() or None,
        "year": year,
        "month": mcode,
        "month_name": month_name or None,
        "period": period,
        "index": _num(row.get("index")),
        "inflation_pct": _num(row.get("inflation")),
        "status": {"F": "Final", "P": "Provisional"}.get(status, status or None),
    }


# ---- generic multi-dataset series (IIP / WPI / NAS / PLFS / ASI) --------------------------------------
# Each MoSPI dataset has its own endpoint + required params; we front them all behind one /series?dataset=…
# and normalize every row to a common stat.series record. Params beyond the required defaults are passed
# through from the query (year, indicator_code, month_code, state_code, …) so the driver drives coverage.
DATASETS = {
    "IIP":  {"path": "/api/iip/getIipData",   "defaults": {"base_year": "2011-12", "frequency": "Monthly", "type": "All", "Format": "JSON"}},
    "WPI":  {"path": "/api/wpi/getWpiRecords", "defaults": {"Format": "JSON"}},
    "NAS":  {"path": "/api/nas/getNASData",    "defaults": {"base_year": "2011-12", "series": "Current", "frequency_code": "Annually", "Format": "JSON"}},
    "ASI":  {"path": "/api/asi/getASIData",    "defaults": {"classification_year": "2008", "sector_code": "Combined", "nic_type": "All", "Format": "JSON"}},
    "PLFS": {"path": "/api/plfs/getData",      "defaults": {"frequency_code": "1", "Format": "JSON"}},
}
_PASSTHRU = ("year", "financial_year", "month_code", "indicator_code", "state_code", "sector_code",
             "gender_code", "age_code", "quarter_code", "category_code", "subcategory_code",
             "group_code", "major_group_code", "nic_code", "frequency")
_IDX_UNIT = "index (2011-12=100)"


def _fy_year(s):
    try:
        return int(str(s)[:4])
    except (TypeError, ValueError):
        return None


def _norm_series(ds, row):
    """Map one raw MoSPI row (any dataset) → a common stat.series record (typed value + dims)."""
    def geo(name):
        nm = (name or "").strip()
        return ("national" if nm.lower() in ("all india", "allindia", "") else "state"), (nm or "All India")
    if ds == "IIP":
        y = row.get("year"); m = _MONTHS.get((row.get("month") or "").lower())
        y = int(y) if str(y).isdigit() else None
        return {"dataset": "IIP", "indicator": "Index of Industrial Production", "unit": _IDX_UNIT,
                "geo_level": "national", "geo_name": "All India", "base_year": row.get("base_year"),
                "year": y, "month": m, "period": (f"{y}-{m:02d}" if y and m else None),
                "value": _num(row.get("index")), "value2": _num(row.get("growth_rate")), "value2_label": "growth_rate_pct",
                "category": row.get("type") or None, "subgroup": row.get("category") or None,
                "dims": {"type": row.get("type"), "category": row.get("category"), "sub_category": row.get("sub_category")}}
    if ds == "WPI":
        y = row.get("year"); m = _MONTHS.get((row.get("month") or "").lower())
        y = int(y) if str(y).isdigit() else None
        return {"dataset": "WPI", "indicator": "Wholesale Price Index", "unit": _IDX_UNIT,
                "geo_level": "national", "geo_name": "All India", "year": y, "month": m,
                "period": (f"{y}-{m:02d}" if y and m else None), "value": _num(row.get("index_value")),
                "category": row.get("majorgroup") or None, "subgroup": row.get("group") or None,
                "dims": {"majorgroup": row.get("majorgroup"), "group": row.get("group"),
                         "subgroup": row.get("subgroup"), "sub_subgroup": row.get("sub_subgroup"), "item": row.get("item")}}
    if ds == "NAS":
        return {"dataset": "NAS", "indicator": row.get("indicator") or "National Accounts", "unit": row.get("unit") or "₹ Crore",
                "geo_level": "national", "geo_name": "All India", "base_year": row.get("base_year"), "series": row.get("series"),
                "year": _fy_year(row.get("year")), "period": str(row.get("year")) if row.get("year") else None,
                "value": _num(row.get("current_price")), "value2": _num(row.get("constant_price")), "value2_label": "constant_price",
                "category": row.get("industry") or None, "subgroup": row.get("subindustry") or None,
                "dims": {"industry": row.get("industry"), "subindustry": row.get("subindustry"),
                         "institutional_sector": row.get("institutional_sector"), "revision": row.get("revision")}}
    if ds == "ASI":
        lvl, nm = geo(row.get("state"))
        u = row.get("unit"); u = None if u in ("-", "", None) else u
        return {"dataset": "ASI", "indicator": row.get("indicator") or "ASI", "unit": u,
                "geo_level": lvl, "geo_name": nm, "year": _fy_year(row.get("year")),
                "period": str(row.get("year")) if row.get("year") else None, "value": _num(row.get("value")),
                "category": row.get("sector") or None, "subgroup": row.get("nic_description") or None,
                "dims": {"sector": row.get("sector"), "nic_code": row.get("nic_code"),
                         "nic_description": row.get("nic_description"), "nic_type": row.get("nic_type")}}
    if ds == "PLFS":
        lvl, nm = geo(row.get("state"))
        return {"dataset": "PLFS", "indicator": row.get("indicator") or "PLFS", "unit": row.get("unit") or "%",
                "geo_level": lvl, "geo_name": nm, "year": _fy_year(row.get("year")),
                "period": str(row.get("year")) if row.get("year") else None, "value": _num(row.get("value")),
                "category": row.get("gender") or None, "subgroup": row.get("sector") or None,
                "dims": {"gender": row.get("gender"), "sector": row.get("sector"), "age_group": row.get("AgeGroup"),
                         "weekly_status": row.get("weekly_status"), "religion": row.get("religion"),
                         "social_group": row.get("socialGroup"), "education": row.get("General_Education"),
                         "year_type": row.get("year_type")}}
    return None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/health":
            return self._send(200, {"ok": True, "service": "mospi-gateway", "upstream": MOSPI_BASE})
        if u.path == "/cpi/base_years":
            try:
                data, st = _get("/api/cpi/getCpiBaseYear", {})
                return self._send(200, {"ok": True, "upstream_status": st, "data": data})
            except Exception as e:
                return self._send(502, {"ok": False, "error": f"MoSPI unreachable: {type(e).__name__}: {e}"})
        if u.path == "/cpi":
            base_year = q.get("base_year", "2012")
            series = q.get("series", "Current")
            base = {
                "base_year": base_year, "series": series, "Format": "JSON",
                "state_code": q.get("state_code", "99"),
                "year": q.get("year"), "month_code": q.get("month_code"),
                "group_code": q.get("group_code"), "sector_code": q.get("sector_code"),
            }
            # MoSPI's endpoint returns HTTP 502 for large pages (>~100 rows), so page through it politely
            # at PAGE_SIZE and accumulate. Stop on a short/empty page or the safety cap.
            PAGE_SIZE = int(os.environ.get("MOSPI_PAGE_SIZE", "100"))
            MAX_PAGES = int(os.environ.get("MOSPI_MAX_PAGES", "80"))
            rows, page, last_st, last_msg = [], 1, None, None
            while page <= MAX_PAGES:
                params = dict(base, limit=str(PAGE_SIZE), page=str(page))
                try:
                    data, st = _get("/api/cpi/getCPIIndex", params)
                except Exception as e:
                    if page == 1:
                        return self._send(502, {"ok": False, "error": f"MoSPI unreachable: {type(e).__name__}: {e}"})
                    break  # a mid-pagination transport hiccup: return what we have
                last_st, last_msg = st, (data or {}).get("msg")
                if not isinstance(data, dict) or data.get("statusCode") is False:
                    if page == 1:
                        return self._send(502, {"ok": False, "upstream_status": st,
                                                "error": last_msg or "MoSPI error", "raw": data})
                    break
                batch = data.get("data") or []
                rows.extend(batch)
                if len(batch) < PAGE_SIZE:
                    break
                page += 1
            recs = [_normalize_cpi(r, base_year, series) for r in rows]
            return self._send(200, {"ok": True, "upstream_status": last_st, "count": len(recs),
                                    "pages": page, "msg": last_msg, "records": recs})
        if u.path == "/series":
            ds = (q.get("dataset") or "").upper()
            spec = DATASETS.get(ds)
            if not spec:
                return self._send(400, {"ok": False, "error": f"unknown dataset '{ds}' (one of {sorted(DATASETS)})"})
            base = dict(spec["defaults"])
            for k in _PASSTHRU:
                if q.get(k) not in (None, ""):
                    base[k] = q[k]
            PAGE_SIZE = int(os.environ.get("MOSPI_PAGE_SIZE", "100"))
            MAX_PAGES = int(os.environ.get("MOSPI_MAX_PAGES", "200"))
            rows, page, last_st, last_msg = [], 1, None, None
            while page <= MAX_PAGES:
                params = dict(base, limit=str(PAGE_SIZE), page=str(page))
                try:
                    data, st = _get(spec["path"], params)
                except Exception as e:
                    if page == 1:
                        return self._send(502, {"ok": False, "error": f"MoSPI unreachable: {type(e).__name__}: {e}"})
                    break
                last_st, last_msg = st, (data or {}).get("msg")
                if not isinstance(data, dict) or data.get("statusCode") is False:
                    if page == 1:
                        return self._send(502, {"ok": False, "upstream_status": st, "error": last_msg or "MoSPI error", "raw": data})
                    break
                batch = data.get("data") or []
                rows.extend(batch)
                if len(batch) < PAGE_SIZE:
                    break
                page += 1
            recs = [r for r in (_norm_series(ds, x) for x in rows) if r]
            if q.get("agg") in ("1", "true", "yes") and ds == "WPI":
                # headline WPI only: all-commodities + major-group level (no sub/sub-sub/item breakdown)
                recs = [r for r in recs if not (r["dims"].get("item") or r["dims"].get("sub_subgroup") or r["dims"].get("subgroup"))]
            if q.get("agg") in ("1", "true", "yes") and ds == "PLFS":
                # headline PLFS only: drop the religion / social-group / education cross-tabs (keep 'all')
                def _all(v): return v is None or str(v).lower() == "all"
                recs = [r for r in recs if _all(r["dims"].get("religion")) and _all(r["dims"].get("social_group")) and _all(r["dims"].get("education"))]
            return self._send(200, {"ok": True, "dataset": ds, "upstream_status": last_st, "count": len(recs),
                                    "pages": page, "msg": last_msg, "records": recs})
        if u.path == "/plfs/indicators":
            try:
                out = {}
                for fc, label in [("1", "Annual"), ("2", "Quarterly")]:
                    d, _ = _get("/api/plfs/getIndicatorListByFrequency", {"frequency_code": fc})
                    out[fc] = [{"code": r.get("indicator_code"), "description": r.get("description")} for r in (d.get("data") or [])]
                return self._send(200, {"ok": True, "by_frequency": out})
            except Exception as e:
                return self._send(502, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"ok": False, "error": "not found"})


if __name__ == "__main__":
    print(f"[mospi-gateway] listening on :{PORT} → {MOSPI_BASE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

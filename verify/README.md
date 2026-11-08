# verify/ — the assurance nets (FIX-PLAN §0), runnable locally

| Net | Script | What it proves |
|---|---|---|
| 4 · route inventory | `route_inventory_test.py` (+ `route_extract.py`, `route_probe.py`, `route-inventory.json`) | every route each service exposes is declared (public / login / authority / internal); every non-public route refuses an anonymous call; prints the REVIEW list (public routes that should not be) |

`route-inventory.json` is the declaration. Adding a route without declaring it fails TEST 1. Declaring a route
`public` requires a `why`; a route public today that should not be also carries `review` (with its debt id) and is
listed on every run. A handler that validates before authenticating carries a `body`/`sample` so the probe reaches
its gate, plus an `ordering` note (DEBT-B74).

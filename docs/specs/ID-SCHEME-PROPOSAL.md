# Proposal — distinct rule / debt ID scheme (NOT YET APPLIED)

**Status:** Proposal only. This document proposes a rename; it changes **no** rule IDs in the specs or the
debt register. Nothing cites these new IDs yet. Adoption is a separate, mechanical slice (find/replace per
file + a redirect note), gated on review.

## Why

Today's IDs use short, overlapping prefixes that collide across documents, so a bare ID is ambiguous without
knowing which file you're in:

- **`A#` means two different things** — ACCOUNT rules (`A1`–`A9`) **and** debt items (`A1`–`A73`). "A5" is both
  an ACCOUNT rule *and* a debt item.
- **The `P-` family is ambiguous** — PLATFORM `P#`, PARTICIPANT `PP#`, POLICY `PL#` all start with `P`.
- **`C` vs `CP`** — CLIENT `C#` vs COMPONENT `CP#` (one is a prefix of the other).
- **`D#` vs "debt"** — DECISION `D#` reads like a debt prefix in prose.

A reader (or a future conformance tool) cannot resolve an ID to its document from the ID alone.

## Proposed scheme

A **distinct 3-letter prefix per spec**, a hyphen, then the existing number (and any sub-letter) unchanged;
debt keeps its two series under an unambiguous `DEBT-` prefix.

| Spec | Old prefix | **New prefix** | Range (unchanged numbers) |
|---|---|---|---|
| FOUNDATIONS | `F#` | **`FND-`** | FND-1 … FND-17 |
| REGISTRY | `R#` | **`REG-`** | REG-1 … REG-18 |
| DECISION | `D#` | **`DEC-`** | DEC-1 … DEC-12 |
| NETWORK | `N#` | **`NET-`** | NET-1 … NET-12 |
| ACCOUNT | `A#` (+ `W#` wallet) | **`ACC-`** (+ `ACC-W#`) | ACC-1 … ACC-9, ACC-W1 … ACC-W4 |
| CLIENT | `C#` | **`CLI-`** | CLI-1 … CLI-6 |
| PLATFORM | `P#` (incl. `P5a`,`P8a`) | **`PLT-`** | PLT-1 … PLT-21 (sub-letters kept: PLT-5a, PLT-8a) |
| COMPONENT | `CP#` | **`CMP-`** | CMP-1 … CMP-18 |
| OFFERINGS | `O#` | **`OFF-`** | OFF-1 … OFF-12 |
| POLICY | `PL#` | **`POL-`** | POL-1 … POL-8 |
| PARTICIPANT | `PP#` | **`PTC-`** | PTC-1 … PTC-12 |
| Debt (transitional mechanisms) | `A#` | **`DEBT-A#`** | DEBT-A1 … DEBT-A73 |
| Debt (invariant violations) | `B#` | **`DEBT-B#`** | DEBT-B1 … DEBT-B21 |

Rules: the **number never changes** (F11 → FND-11, P4 → PLT-4, A5 → ACC-5, debt A5 → DEBT-A5); only the prefix
does. Sub-letters are preserved (P5a → PLT-5a). The `DEBT-` prefix removes the ACCOUNT↔debt `A#` collision
outright (ACC-5 vs DEBT-A5).

## Old → new mapping (every current prefix)

| Old | New | Collision it removes |
|---|---|---|
| `F1`–`F17` | `FND-1`–`FND-17` | — (reads as a debt-free namespace) |
| `R1`–`R18` | `REG-1`–`REG-18` | — |
| `D1`–`D12` | `DEC-1`–`DEC-12` | `D#` no longer reads as "debt" |
| `N1`–`N12` | `NET-1`–`NET-12` | — |
| `A1`–`A9` | `ACC-1`–`ACC-9` | **ACCOUNT vs debt `A#`** |
| `W1`–`W4` | `ACC-W1`–`ACC-W4` | wallet grouped under ACCOUNT |
| `C1`–`C6` | `CLI-1`–`CLI-6` | **CLIENT `C` vs COMPONENT `CP`** |
| `P1`–`P21` | `PLT-1`–`PLT-21` | **PLATFORM vs PARTICIPANT/POLICY `P-`** |
| `CP1`–`CP18` | `CMP-1`–`CMP-18` | `CP` vs `C` |
| `O1`–`O12` | `OFF-1`–`OFF-12` | — |
| `PL1`–`PL8` | `POL-1`–`POL-8` | `PL` vs `P`/`PP` |
| `PP1`–`PP12` | `PTC-1`–`PTC-12` | `PP` vs `P` |
| debt `A1`–`A73` | `DEBT-A1`–`DEBT-A73` | **debt vs ACCOUNT `A#`** |
| debt `B1`–`B21` | `DEBT-B1`–`DEBT-B21` | `B#` reads as a spec prefix |

## Cross-reference impact (what a later apply-slice must sweep)

Renaming touches every cross-citation, not just the defining spec. The apply-slice must find/replace across:

- `docs/specs/*.md` (every "Refs:" line, every "Builds on" header, the README tallies and layering diagram).
- `docs/consolidation/DEBT-REGISTER.md`, `FOUNDATIONS-v0.1` §4 (debt→principle map), `CURRENT-STATE.md`.
- `docs/conformance/PLAN.md` + `conformance/run.py` (the rule IDs each case cites).
- ADRs and operator docs that cite rule IDs in prose (e.g. "N7 VIOLATED", "P4/B2").

Because the **numbers are stable**, the sweep is a prefix-only substitution per namespace (`\bF(\d)` → `FND-\1`,
`\bA(\d)` in spec context → `ACC-\1` but in debt context → `DEBT-A\1` — the two `A#` cases are the only ones
needing context, which is itself the argument for the rename). A redirect table (this document) should ship
with the apply-slice so old IDs in external notes still resolve.

## Not decided here

Whether to adopt, and when. This proposal does not renumber, does not touch rule text, and does not change any
status. If adopted, the mapping table above is the authoritative old→new redirect.

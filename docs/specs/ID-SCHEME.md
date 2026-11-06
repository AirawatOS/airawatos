# Rule / debt ID scheme (ADOPTED — authoritative old → new alias table)

**Status:** Adopted and applied repo-wide (2026-11-06). Every rule, debt, finding and assurance ID in the
normative surface now uses a distinct, collision-free prefix. This document is the **authoritative old → new
alias table**: old IDs in external notes, ADRs, git history or chat resolve here.

## Why

The old IDs used short, overlapping prefixes that collided across documents, so a bare ID was ambiguous
without knowing which file you were in:

- **`A#` meant three things** — ACCOUNT rules (`A1`–`A9`), debt items (`A1`–`A74`), **and** identity assurance
  levels (`A0`–`A3`). "A5" was both an ACCOUNT rule *and* a debt item.
- **The `P-` family was ambiguous** — PLATFORM `P#`, PARTICIPANT `PP#`, POLICY `PL#` all start with `P`; and
  `P0`/`P1` are also used as task/priority labels.
- **`C` vs `CP`** — CLIENT `C#` vs COMPONENT `CP#` (one a prefix of the other).
- **`D#` vs "debt"** — DECISION `D#` read like a debt prefix, and `D1`–`D6` also named pipeline findings.
- **`R#`/`W#` overloaded** — REGISTRY rules vs filestore read/write **caller-site** labels; wallet `W#` vs
  those write-caller labels vs ADR-0097 workflow build-slices `W0`–`W6`.

A reader (or a conformance tool) could not resolve an ID to its document from the ID alone. The new scheme
fixes this: **a distinct 3-letter prefix per spec**, a hyphen, then the existing number (and any sub-letter)
unchanged; debt keeps its two series under an unambiguous `DEBT-` prefix; assurance levels become `AL#`;
pipeline findings become `FIND-#`.

## The scheme

| Family | Old prefix | **New prefix** | Range (unchanged numbers) |
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
| FEDERATION | `FED#` | **`FED-`** *(unchanged)* | FED1 … FED8 |
| Assurance levels | `A0`–`A3` | **`AL#`** | AL0 … AL3 |
| Debt — transitional mechanisms | `A#` | **`DEBT-A#`** | DEBT-A1 … DEBT-A74 |
| Debt — invariant violations | `B#` | **`DEBT-B#`** | DEBT-B1 … DEBT-B21 |
| Debt — duplication / dead-code clusters | `C#` | **`DEBT-C#`** | DEBT-REGISTER §C (numbered list; no bare `C#` tokens exist) |
| Pipeline-proof findings | `D1`–`D6`, `D-R13` | **`FIND-#`**, `FIND-R13` | FIND-1 … FIND-6, FIND-R13 |

**Rule:** the number never changes (`F11` → `FND-11`, `P4` → `PLT-4`, `A5` → `ACC-5`, debt `A5` → `DEBT-A5`);
only the prefix does. Sub-letters are preserved (`P5a` → `PLT-5a`). The three `A#` meanings split cleanly:
assurance → `AL#`, ACCOUNT rule → `ACC-#`, debt → `DEBT-A#`. `FED#` was already distinct and is unchanged.

## Old → new mapping (every current prefix)

| Old | New | Collision it removes |
|---|---|---|
| `F1`–`F17` | `FND-1`–`FND-17` | reads as a debt-free namespace |
| `R1`–`R18` | `REG-1`–`REG-18` | REGISTRY rule vs filestore read-caller `R#` |
| `D1`–`D12` | `DEC-1`–`DEC-12` | `D#` no longer reads as "debt"; split from findings |
| `N1`–`N12` | `NET-1`–`NET-12` | — |
| `A0`–`A3` (assurance) | `AL0`–`AL3` | assurance vs ACCOUNT vs debt `A#` |
| `A1`–`A9` (ACCOUNT) | `ACC-1`–`ACC-9` | **ACCOUNT vs debt `A#`** |
| `W1`–`W4` (wallet) | `ACC-W1`–`ACC-W4` | wallet grouped under ACCOUNT; split from caller/slice `W#` |
| `C1`–`C6` | `CLI-1`–`CLI-6` | **CLIENT `C` vs COMPONENT `CP`** |
| `P1`–`P21` | `PLT-1`–`PLT-21` | **PLATFORM vs PARTICIPANT/POLICY `P-`** and vs task labels |
| `CP1`–`CP18` | `CMP-1`–`CMP-18` | `CP` vs `C` |
| `O1`–`O12` | `OFF-1`–`OFF-12` | — |
| `PL1`–`PL8` | `POL-1`–`POL-8` | `PL` vs `P`/`PP` |
| `PP1`–`PP12` | `PTC-1`–`PTC-12` | `PP` vs `P` |
| debt `A1`–`A74` | `DEBT-A1`–`DEBT-A74` | **debt vs ACCOUNT vs assurance `A#`** |
| debt `B1`–`B21` | `DEBT-B1`–`DEBT-B21` | `B#` reads as a spec prefix |
| finding `D1`–`D6`, `D-R13` | `FIND-1`–`FIND-6`, `FIND-R13` | pipeline findings vs DECISION rules |

## Scope applied

The sweep ran over the **normative surface**: `docs/specs/*.md` (all v0.1 specs incl. FEDERATION, README,
GLOSSARY, STATUS-MATRIX-DESIGN), `docs/consolidation/{DEBT-REGISTER, PIPELINE-PROOF-FINDINGS,
FILESTORE-CALLER-INVENTORY, KERNEL-MEDIATED-FILES-DESIGN, CURRENT-STATE, FACT-MIGRATION-PLAN}.md`,
`conformance/run.py`, and the reader docs (`docs/PRIMER.md`, `docs/AIRAWAT-FOR-ENGINEERS.md`). `conformance/PLAN.md`
carries no rule-ID tokens. The two `A#` cases that need context (assurance / ACCOUNT / debt) and the `D#`,
`P#`, `C#`, `R#`, `W#` collisions were resolved per-occurrence.

**Out of scope — the ADRs (`docs/decisions/*.md`).** ADRs are dated decision records and use `P0`–`P5`,
`S1`–`S5`, `W0`–`W6` as their *own* phase / slice labels, not as rule references; rewriting them would corrupt
those labels and add churn to a historical record. Old rule IDs appearing in ADR prose resolve through this
table.

## Legitimate bare tokens left in scope

A small set of bare tokens that **match an old pattern but are not rule IDs** are deliberately left unchanged;
they are enumerated in [`ID-ALLOWLIST.txt`](ID-ALLOWLIST.txt) with file and reason (REGISTRY task-priority
labels `P0`/`P1`; filestore caller-site labels `R1`–`R13` / `W1`–`W10`; CURRENT-STATE route-authz test labels
`C1`–`C4`; ADR-0097 workflow-slice refs `W5`; `conformance/run.py` Python function identifiers `case_B15` /
`case_R10`, whose emitted label strings *are* renamed).

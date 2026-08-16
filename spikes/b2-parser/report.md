# Spike B2 Report — FantasyPros HTML Parser Robustness

**Date:** 2026-04-18
**Validates:** §9.1.4 — one parser handles QB/RB/WR/TE MultiIndex shapes.
**Kill criterion:** any position needs a strategy not in {by_name, by_index, fantasypros_multi_header}.

## Results

| Position | Rows | Columns | All mapped | Unmapped |
|---|---|---|---|---|
| QB | 88 | 11 | ✓ | none |
| RB | 152 | 9 | ✓ | none |
| WR | 224 | 9 | ✓ | none |
| TE | 127 | 6 | ✓ | none |

## Verdict

- [x] **PASS** — all positions fully covered by the existing map.

## Details

All four positions use consistent MultiIndex column structure: `(section, code)` tuples where section is one of `{PASSING, RUSHING, RECEIVING, MISC}` and code is a short statistic identifier (e.g., `ATT`, `YDS`, `TDS`).

- **QB**: PASSING (5 stats) + RUSHING (3 stats) + MISC (2 stats including fumbles)
- **RB**: RUSHING (3 stats) + RECEIVING (4 stats) + MISC (2 stats)
- **WR**: RECEIVING (4 stats) + RUSHING (3 stats) + MISC (2 stats)
- **TE**: RECEIVING (3 stats) + MISC (2 stats, no rushing/passing)

The mapping table `FP_SECTION_MAP` in `parse.py` handles all observed columns across all positions. No new strategies or unmapped columns encountered.

## Recommendation

Map table as in `parse.py` is complete and sufficient. Promote to `api/app/import_pipeline/column_mapper.py` as the canonical `FP_SECTION_MAP`. The single parser using `by_index`/`by_name` strategies with this mapping table is sufficient for all four positional layouts.

## Artifacts

- `parse.py` — promotable to `api/tests/unit/test_csv_parser_fantasypros.py` after minor edits.

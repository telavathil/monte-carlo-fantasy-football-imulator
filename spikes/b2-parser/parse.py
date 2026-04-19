"""
Spike B2: Verify one parser + mapping table handles all four positional
MultiIndex layouts from FantasyPros HTML.
Kill criterion: any position needs a strategy not in {by_name, by_index,
fantasypros_multi_header}.
"""
from __future__ import annotations
import pathlib
import pandas as pd

FIXTURES = pathlib.Path(__file__).parents[2] / "tests" / "fixtures"

# Canonical stat vocabulary = nflreadpy column names.
# Section × short-code → canonical name (or None = ignored).
FP_SECTION_MAP = {
    ("PASSING", "ATT"): "attempts",
    ("PASSING", "CMP"): "completions",
    ("PASSING", "YDS"): "passing_yards",
    ("PASSING", "TDS"): "passing_tds",
    ("PASSING", "INTS"): "passing_interceptions",
    ("RUSHING", "ATT"): "carries",
    ("RUSHING", "YDS"): "rushing_yards",
    ("RUSHING", "TDS"): "rushing_tds",
    ("RECEIVING", "REC"): "receptions",
    ("RECEIVING", "YDS"): "receiving_yards",
    ("RECEIVING", "TDS"): "receiving_tds",
    ("RECEIVING", "TGT"): "targets",
    ("MISC", "FL"): "rushing_fumbles_lost",
    ("MISC", "FPTS"): None,  # ignored; we compute our own
}


def parse_position(path: pathlib.Path, pos: str):
    tables = pd.read_html(path)
    df = max(tables, key=lambda t: t.shape[0])
    if not isinstance(df.columns, pd.MultiIndex):
        raise AssertionError(f"{pos}: expected MultiIndex columns, got flat")

    mapped = {}
    unmapped = []
    for lvl0, lvl1 in df.columns:
        if lvl0.startswith("Unnamed"):
            continue  # Player column
        key = (lvl0, lvl1)
        if key in FP_SECTION_MAP:
            mapped[(lvl0, lvl1)] = FP_SECTION_MAP[key]
        else:
            unmapped.append(key)
    return mapped, unmapped, df.shape


def main() -> int:
    ok = True
    for pos in ["qb", "rb", "wr", "te"]:
        path = FIXTURES / f"fantasypros_{pos}.html"
        mapped, unmapped, shape = parse_position(path, pos)
        print(f"\n=== {pos.upper()} ({shape[0]} rows, {shape[1]} cols) ===")
        print("Mapped:")
        for k, v in mapped.items():
            print(f"  {k} → {v}")
        if unmapped:
            print("UNMAPPED:")
            for k in unmapped:
                print(f"  {k} !!")
            ok = False
        else:
            print("  (all columns mapped)")

    print("\nPASS" if ok else "\nFAIL — some columns unmapped; update FP_SECTION_MAP")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

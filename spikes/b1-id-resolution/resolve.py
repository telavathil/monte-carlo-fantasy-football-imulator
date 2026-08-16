"""
Spike B1: Identity resolution hit-rate for FantasyPros HTML.
Kill criterion: <80% resolved.
"""
from __future__ import annotations
import csv
import pathlib
import re
import pandas as pd
import nflreadpy as nfl

FIXTURES = pathlib.Path(__file__).parents[2] / "tests" / "fixtures"
POSITIONS = ["qb", "rb", "wr", "te"]

# Known ID columns we look for in Tier 1 (FantasyPros default export has none,
# but we include for completeness — users may hand-augment).
KNOWN_ID_COLS = {
    "fantasypros_id", "espn_id", "yahoo_id", "sleeper_id",
    "cbs_id", "pfr_id", "fantasy_data_id", "rotowire_id", "nfl_id",
}


def normalize_name(name: str) -> str:
    """Apply the same transform nflreadpy uses for merge_name."""
    s = name.lower().strip()
    s = re.sub(r"[.']", "", s)          # strip periods and apostrophes
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", s)  # strip suffixes
    s = re.sub(r"\s+", " ", s)
    return s


def split_name_team(combined: str) -> tuple[str, str]:
    """'Jalen Hurts PHI' → ('Jalen Hurts', 'PHI')."""
    parts = combined.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def load_canonical():
    df = nfl.load_ff_playerids().to_pandas()
    df = df[df["gsis_id"].notna()]
    return df


def resolve_row(csv_row: dict, pos: str, canonical: pd.DataFrame) -> str:
    """Return 'tier1' | 'tier3_single' | 'tier3_ambiguous' | 'unresolved'."""
    # Tier 1
    for col in csv_row:
        if col in KNOWN_ID_COLS and pd.notna(csv_row[col]):
            match = canonical[canonical[col] == csv_row[col]]
            if len(match) >= 1:
                return "tier1"
    # Tier 3
    combined = csv_row.get("player", "")
    name, team = split_name_team(combined)
    merge = normalize_name(name)
    match = canonical[
        (canonical["merge_name"] == merge)
        & (canonical["team"] == team)
        & (canonical["position"] == pos.upper())
    ]
    if len(match) == 1:
        return "tier3_single"
    if len(match) > 1:
        return "tier3_ambiguous"
    return "unresolved"


def main() -> int:
    canonical = load_canonical()
    print(f"Canonical player table: {len(canonical)} rows (gsis_id NOT NULL)")

    outcomes: list[dict] = []
    for pos in POSITIONS:
        html_path = FIXTURES / f"fantasypros_{pos}.html"
        tables = pd.read_html(html_path)
        # FantasyPros projection table is the largest one
        projection = max(tables, key=lambda t: t.shape[0])
        # Flatten MultiIndex if present
        if isinstance(projection.columns, pd.MultiIndex):
            projection.columns = [
                lvl1 if lvl0.startswith("Unnamed") else f"{lvl0}_{lvl1}"
                for lvl0, lvl1 in projection.columns
            ]
        print(f"\n{pos.upper()}: {len(projection)} rows")
        for _, row in projection.iterrows():
            csv_row = {c: row[c] for c in projection.columns}
            # FantasyPros combines name+team under "Player"
            csv_row.setdefault("player", row.get("Player", ""))
            result = resolve_row(csv_row, pos, canonical)
            outcomes.append({"pos": pos.upper(), "row": csv_row["player"],
                             "outcome": result})

    # Summary
    by_pos: dict[str, dict[str, int]] = {}
    for o in outcomes:
        by_pos.setdefault(o["pos"], {}).setdefault(o["outcome"], 0)
        by_pos[o["pos"]][o["outcome"]] += 1

    csv_path = pathlib.Path(__file__).parent / "hit_rates.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pos", "row", "outcome"])
        w.writeheader()
        w.writerows(outcomes)

    print("\n=== Summary ===")
    total_resolved = 0
    total = 0
    for pos, counts in by_pos.items():
        n = sum(counts.values())
        resolved = counts.get("tier1", 0) + counts.get("tier3_single", 0)
        total += n
        total_resolved += resolved
        print(f"  {pos}: {counts} → resolved {resolved}/{n} ({100*resolved/n:.0f}%)")
    print(f"\nOVERALL: {total_resolved}/{total} ({100*total_resolved/total:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Column mapping strategies for CSV imports (ADR-0009)."""
from __future__ import annotations
from typing import Literal
import pandas as pd


MappingStrategy = Literal["by_name", "by_index", "fantasypros_multi_header"]


FP_SECTION_MAP: dict[tuple[str, str], str | None] = {
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


def map_columns(df: pd.DataFrame, strategy: MappingStrategy,
                mapping: dict | None = None) -> tuple[pd.DataFrame, list]:
    """Return (mapped_df, unmapped_list)."""
    unmapped: list = []
    if strategy == "fantasypros_multi_header":
        assert isinstance(df.columns, pd.MultiIndex), "expected MultiIndex"
        new_cols: list[str] = []
        keep: list = []
        for lvl0, lvl1 in df.columns:
            if str(lvl0).startswith("Unnamed"):
                new_cols.append("Player")
                keep.append((lvl0, lvl1))
                continue
            key = (lvl0, lvl1)
            if key in FP_SECTION_MAP:
                canonical = FP_SECTION_MAP[key]
                if canonical is not None:
                    new_cols.append(canonical)
                    keep.append(key)
            else:
                unmapped.append(key)
        sub = df.loc[:, keep].copy()
        sub.columns = new_cols
        return sub, unmapped

    if strategy == "by_name":
        assert mapping is not None
        rename = {c: mapping[c] for c in df.columns if c in mapping and mapping[c] != "ignored"}
        unmapped = [c for c in df.columns if c not in mapping]
        out = df[list(rename.keys())].rename(columns=rename)
        return out, unmapped

    if strategy == "by_index":
        assert mapping is not None
        keep_cols = []
        new_cols = []
        for idx, col in enumerate(df.columns):
            key = str(idx)
            if key in mapping:
                keep_cols.append(col)
                new_cols.append(mapping[key])
            else:
                unmapped.append(col)
        out = df[keep_cols].copy()
        out.columns = new_cols
        return out, unmapped

    raise ValueError(f"unknown strategy: {strategy}")

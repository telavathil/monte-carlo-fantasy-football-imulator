import pandas as pd
import pytest
from app.import_pipeline.column_mapper import (
    FP_SECTION_MAP, map_columns, MappingStrategy
)


def test_fp_section_map_has_all_expected_keys():
    expected = {
        ("PASSING", "ATT"), ("PASSING", "CMP"), ("PASSING", "YDS"),
        ("PASSING", "TDS"), ("PASSING", "INTS"),
        ("RUSHING", "ATT"), ("RUSHING", "YDS"), ("RUSHING", "TDS"),
        ("RECEIVING", "REC"), ("RECEIVING", "YDS"), ("RECEIVING", "TDS"),
        ("RECEIVING", "TGT"),
        ("MISC", "FL"), ("MISC", "FPTS"),
    }
    assert set(FP_SECTION_MAP.keys()) == expected


def test_fantasypros_multi_header_strategy():
    df = pd.DataFrame({
        ("Unnamed: 0_level_0", "Player"): ["Jalen Hurts PHI"],
        ("PASSING", "ATT"): [400],
        ("PASSING", "YDS"): [4200],
        ("PASSING", "TDS"): [28],
        ("RUSHING", "ATT"): [120],
        ("RUSHING", "YDS"): [800],
    })
    mapped, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    # The player column preserves raw values; stat columns re-keyed
    assert "attempts" in mapped.columns
    assert "passing_yards" in mapped.columns
    assert "carries" in mapped.columns
    assert unmapped == []


def test_by_name_strategy():
    df = pd.DataFrame({"Player": ["X"], "pass_yds": [4000], "Pass Yds": [0]})
    mapping = {"Player": "Player", "pass_yds": "passing_yards", "Pass Yds": "ignored"}
    mapped, unmapped = map_columns(df, strategy="by_name", mapping=mapping)
    assert "passing_yards" in mapped.columns


def test_by_index_strategy():
    df = pd.DataFrame([[100, 1000, 10]], columns=["a", "b", "c"])
    mapping = {"0": "attempts", "1": "passing_yards", "2": "passing_tds"}
    mapped, unmapped = map_columns(df, strategy="by_index", mapping=mapping)
    assert list(mapped.columns) == ["attempts", "passing_yards", "passing_tds"]


def test_unmapped_columns_surfaced():
    df = pd.DataFrame({
        ("Unnamed: 0_level_0", "Player"): ["X"],
        ("PASSING", "SOMETHING_NEW"): [1],
    })
    mapped, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    assert ("PASSING", "SOMETHING_NEW") in unmapped

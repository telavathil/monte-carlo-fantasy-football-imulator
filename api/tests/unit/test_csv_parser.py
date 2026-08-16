import pathlib
import pandas as pd
import pytest
from app.import_pipeline.csv_parser import parse_file, split_name_team


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def test_split_name_team_basic():
    assert split_name_team("Jalen Hurts PHI") == ("Jalen Hurts", "PHI")


def test_split_name_team_two_letter_code():
    assert split_name_team("Patrick Mahomes KC") == ("Patrick Mahomes", "KC")


def test_split_name_team_suffix():
    assert split_name_team("Michael Penix Jr. ATL") == ("Michael Penix Jr.", "ATL")


def test_split_name_team_no_team_suffix():
    assert split_name_team("Just A Name") == ("Just A Name", "")


@pytest.mark.parametrize("pos", ["qb", "rb", "wr", "te"])
def test_parse_fantasypros_html_multiindex(pos):
    path = FIXTURES / f"fantasypros_{pos}.html"
    df, meta = parse_file(path.read_bytes(), filename=path.name)
    assert meta["format"] == "html"
    assert isinstance(df.columns, pd.MultiIndex)
    # Largest table has many rows
    assert len(df) > 5


def test_parse_plain_csv():
    csv_bytes = b"Player,Team,passing_yards\nJosh Allen,BUF,4500\n"
    df, meta = parse_file(csv_bytes, filename="custom.csv")
    assert meta["format"] == "csv"
    assert len(df) == 1
    assert df.iloc[0]["Player"] == "Josh Allen"

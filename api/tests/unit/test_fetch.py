import pathlib
import shutil
import pytest
import polars as pl
import pandas as pd
from unittest.mock import patch
from app.historical.fetch import ensure_seasons, game_logs, seed_players, _dedupe_by_gsis_id
from app.models.orm import Player


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures" / "nflreadpy"


@pytest.fixture()
def mock_nflreadpy():
    def fake_load_player_stats(seasons):
        return pl.read_parquet(FIXTURES / f"player_stats_{seasons[0]}.parquet")

    def fake_load_ff_playerids():
        return pl.read_parquet(FIXTURES / "ff_playerids.parquet")

    with patch("app.historical.fetch.nfl") as mock:
        mock.load_player_stats.side_effect = fake_load_player_stats
        mock.load_ff_playerids.side_effect = fake_load_ff_playerids
        yield mock


def test_ensure_seasons_writes_parquet(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    assert (tmp_path / "player_stats_2024.parquet").exists()


def test_ensure_seasons_is_idempotent(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    # Second call should not re-fetch.
    ensure_seasons([2024], hist_dir=tmp_path)
    assert mock_nflreadpy.load_player_stats.call_count == 1


def test_game_logs_filters_reg_and_active(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    # Use an actual GSIS id from the cassette — Mahomes
    df = game_logs("00-0033873", [2024], hist_dir=tmp_path)
    # All rows should be REG; no POST
    assert (df["season_type"] == "REG").all()
    # No zero-activity rows for a QB (attempts + carries + targets > 0)
    nonzero = (df["attempts"] + df["carries"] + df["targets"]) > 0
    assert nonzero.all()


def test_seed_players_filters_gsis_not_null(session, mock_nflreadpy):
    count = seed_players(session)
    # All rows in canonical should have gsis_id set
    rows = session.query(Player).all()
    assert len(rows) == count
    assert all(r.gsis_id for r in rows)
    assert len(rows) > 5000  # cassette has ~7700 rows


def test_dedupe_by_gsis_id_prefers_real_team_over_free_agent():
    # Two distinct mfl_id rows incorrectly crosswalked to the same gsis_id —
    # this happens in the real ff_playerids data (see fetch.py docstring).
    # A row with a real team should always beat a "FA" (free agent /
    # inactive placeholder) row, regardless of source order.
    df = pd.DataFrame([
        {"mfl_id": 1, "gsis_id": "00-0099999", "name": "Real Team Guy",
         "team": "KCC", "db_season": 2026, "draft_year": 2010},
        {"mfl_id": 2, "gsis_id": "00-0099999", "name": "Free Agent Guy",
         "team": "FA", "db_season": 2026, "draft_year": 2015},
    ])
    result = _dedupe_by_gsis_id(df)
    assert len(result) == 1
    assert result.iloc[0]["mfl_id"] == 1
    assert result.iloc[0]["name"] == "Real Team Guy"


def test_dedupe_by_gsis_id_breaks_remaining_ties_by_mfl_id(caplog):
    # Two real-team rows, same db_season and draft_year (both criteria
    # exhausted without resolving the tie) — falls back to lower mfl_id,
    # deterministically, and logs the drop.
    df = pd.DataFrame([
        {"mfl_id": 200, "gsis_id": "00-0088888", "name": "Higher Mfl Id",
         "team": "SEA", "db_season": 2026, "draft_year": 2014},
        {"mfl_id": 100, "gsis_id": "00-0088888", "name": "Lower Mfl Id",
         "team": "KCC", "db_season": 2026, "draft_year": 2014},
    ])
    with caplog.at_level("WARNING"):
        result = _dedupe_by_gsis_id(df)
    assert len(result) == 1
    assert result.iloc[0]["mfl_id"] == 100
    assert "dropping duplicate gsis_id=00-0088888 mfl_id=200" in caplog.text

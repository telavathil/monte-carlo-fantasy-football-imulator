import json
from datetime import datetime

import numpy as np
import polars as pl
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.orm import (
    PlayerProjection, PlayerDistributionParams, PlayerDistributionSummary,
)
from app.sim import summary as summary_mod


def test_summary_is_keyed_by_player_and_preset(session, seeded_players):
    """The same player may hold one summary per preset simultaneously."""
    session.add_all([
        PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                  status="ok", computed_at="2026-09-05T00:00:00"),
        PlayerDistributionSummary(player_id=1, scoring_preset="full_ppr",
                                  status="ok", computed_at="2026-09-05T00:00:00"),
    ])
    session.commit()
    assert session.query(PlayerDistributionSummary).count() == 2


def test_summary_rejects_unknown_status(session, seeded_players):
    session.add(PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                          status="banana",
                                          computed_at="2026-09-05T00:00:00"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_non_ok_summary_leaves_metrics_null(session, seeded_players):
    """A terminal-failure row carries the reason and no metrics."""
    session.add(PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                          status="insufficient_history",
                                          computed_at="2026-09-05T00:00:00"))
    session.commit()
    row = session.get(PlayerDistributionSummary, (1, "half_ppr"))
    assert row.status == "insufficient_history"
    assert row.median_p50 is None and row.histogram is None


def _fake_logs(monkeypatch, n_games: int):
    """Stub game_logs so unit tests never touch parquet or the network."""
    rng = np.random.default_rng(3)
    df = pl.DataFrame({
        "receptions": rng.integers(2, 9, n_games).astype(float),
        "receiving_yards": rng.normal(70, 25, n_games),
        "receiving_tds": rng.integers(0, 2, n_games).astype(float),
    })
    monkeypatch.setattr(summary_mod, "game_logs", lambda *a, **k: df)


def _projection(session, player_id: int) -> PlayerProjection:
    now = datetime.utcnow().isoformat()
    proj = PlayerProjection(player_id=player_id, import_batch_id=1, position="WR",
                            stats=json.dumps({"receptions": 6.0,
                                              "receiving_yards": 85.0,
                                              "receiving_tds": 0.5}),
                            created_at=now)
    session.add(proj)
    session.commit()
    return proj


def test_compute_and_store_writes_ok_row(session, seeded_players, monkeypatch):
    _fake_logs(monkeypatch, 40)
    proj = _projection(session, 4)
    player = seeded_players[3]  # CeeDee Lamb, WR
    row = summary_mod.compute_and_store(
        session, player=player, projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023, 2024, 2025])
    session.commit()
    assert row.status == "ok"
    assert row.floor_p10 <= row.p25 <= row.median_p50 <= row.p75 <= row.ceiling_p90
    assert json.loads(row.histogram)["counts"]
    assert row.n_samples == summary_mod.SUMMARY_N


def test_compute_and_store_marks_insufficient_history(session, seeded_players, monkeypatch):
    """Fewer than MIN_GAMES career games is terminal, not an error to retry."""
    _fake_logs(monkeypatch, 2)
    proj = _projection(session, 4)
    row = summary_mod.compute_and_store(
        session, player=seeded_players[3], projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "insufficient_history"
    assert row.median_p50 is None


def test_compute_and_store_marks_insufficient_history_from_stale_cache(
        session, seeded_players, monkeypatch):
    """A cached params row whose games_used has since fallen below MIN_GAMES
    must still produce insufficient_history, exactly like the cold path.

    game_logs is stubbed to return plenty of games, so if the cache-hit path
    ignored the stored games_used (as it did before this fix), it would
    return the cached params and this would come back "ok" instead."""
    _fake_logs(monkeypatch, 40)
    session.add(PlayerDistributionParams(
        player_id=4, params=json.dumps({}), fitted_at="2026-01-01T00:00:00",
        historical_seasons="2023", games_used=summary_mod.MIN_GAMES - 1))
    session.commit()
    proj = _projection(session, 4)
    row = summary_mod.compute_and_store(
        session, player=seeded_players[3], projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "insufficient_history"
    assert row.median_p50 is None
    assert row.histogram is None


def test_compute_and_store_marks_unsupported_position(session, seeded_players, monkeypatch):
    _fake_logs(monkeypatch, 40)
    player = seeded_players[2]
    player.position = "K"
    session.commit()
    proj = _projection(session, player.mfl_id)
    row = summary_mod.compute_and_store(
        session, player=player, projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "unsupported_position"


def test_compute_and_store_is_idempotent_per_preset(session, seeded_players, monkeypatch):
    """Recomputing replaces the row rather than raising on the composite key."""
    _fake_logs(monkeypatch, 40)
    proj = _projection(session, 4)
    kwargs = dict(player=seeded_players[3], projected_stats=json.loads(proj.stats),
                  projection_id=proj.id, preset_name="half_ppr",
                  historical_seasons=[2023])
    first = summary_mod.compute_and_store(session, **kwargs)
    session.commit()
    first_median = first.median_p50
    second = summary_mod.compute_and_store(session, **kwargs)
    session.commit()
    assert session.query(PlayerDistributionSummary).count() == 1
    assert second.median_p50 == first_median  # deterministic seed


def test_invalidate_for_players_drops_every_preset(session, seeded_players):
    now = datetime.utcnow().isoformat()
    session.add_all([
        PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                  status="ok", computed_at=now),
        PlayerDistributionSummary(player_id=1, scoring_preset="full_ppr",
                                  status="ok", computed_at=now),
        PlayerDistributionSummary(player_id=2, scoring_preset="half_ppr",
                                  status="ok", computed_at=now),
    ])
    session.commit()
    dropped = summary_mod.invalidate_for_players(session, [1])
    session.commit()
    assert dropped == 2
    assert session.query(PlayerDistributionSummary).count() == 1


def test_progress_counts_terminal_rows_as_done(session, seeded_players, monkeypatch):
    """A player that can never be computed still counts as done, or the
    progress bar would never reach 100%."""
    _projection(session, 4)
    _projection(session, 1)
    now = datetime.utcnow().isoformat()
    session.add(PlayerDistributionSummary(player_id=4, scoring_preset="half_ppr",
                                          status="insufficient_history",
                                          computed_at=now))
    session.commit()
    done, total = summary_mod.summary_progress(session, "half_ppr")
    assert (done, total) == (1, 2)


def test_players_needing_summary_excludes_done(session, seeded_players):
    """Both a completed and a terminal-status row must exclude their player,
    or the precompute loop would spin forever re-selecting players that can
    never be computed (K/DEF, insufficient history)."""
    _projection(session, 4)
    _projection(session, 1)
    _projection(session, 2)
    now = datetime.utcnow().isoformat()
    session.add_all([
        PlayerDistributionSummary(player_id=4, scoring_preset="half_ppr",
                                  status="ok", computed_at=now),
        PlayerDistributionSummary(player_id=2, scoring_preset="half_ppr",
                                  status="insufficient_history", computed_at=now),
    ])
    session.commit()
    pending = summary_mod.players_needing_summary(session, "half_ppr", limit=25)
    assert [p.mfl_id for p, _ in pending] == [1]


def test_compute_and_store_nulls_non_finite_skewness(session, seeded_players, monkeypatch):
    """A zero-variance sample makes scipy's skew return nan, which is not
    valid JSON. It must be stored as NULL, not NaN.

    Every game-log column is all-NaN, so after NaN-dropping every stat has
    zero usable observations and is skipped by the fitting loop. The player
    still has enough rows to clear MIN_GAMES (so this isn't
    insufficient_history), but ends up with an empty params dict, so
    simulate_from_params scores an empty stat line for every draw and every
    simulated point is identically 0.0 — the constant-sample case."""
    n_games = 40
    nan_col = np.full(n_games, np.nan)
    df = pl.DataFrame({
        "receptions": nan_col,
        "receiving_yards": nan_col,
        "receiving_tds": nan_col,
    })
    monkeypatch.setattr(summary_mod, "game_logs", lambda *a, **k: df)
    proj = _projection(session, 4)
    row = summary_mod.compute_and_store(
        session, player=seeded_players[3], projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "ok"
    assert row.skewness is None
    assert row.median_p50 == 0.0

import pytest
from sqlalchemy.exc import IntegrityError
from app.models.orm import PlayerDistributionSummary


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

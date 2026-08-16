from app.identity.resolver import resolve


def test_tier1_match_by_fantasypros_id(session, seeded_players):
    result = resolve(
        session,
        csv_row={"fantasypros_id": 16737, "Player": "Patrick Mahomes KC"},
        position="QB",
    )
    assert result == 1


def test_tier3_match_with_team_canonicalization(session, seeded_players):
    # CSV has "Mahomes KC"; canonical stores team KCC — should still match.
    result = resolve(
        session,
        csv_row={"Player": "Patrick Mahomes KC"},
        position="QB",
    )
    assert result == 1


def test_tier3_ambiguous_returns_none(session, seeded_players):
    # Two Josh Allens exist in canonical, but the resolver filters by position.
    # QB Josh Allen (BUF) should match uniquely.
    result = resolve(
        session,
        csv_row={"Player": "Josh Allen BUF"},
        position="QB",
    )
    assert result == 2


def test_tier3_no_match_returns_none(session, seeded_players):
    result = resolve(
        session,
        csv_row={"Player": "Nonexistent Person CAR"},
        position="WR",
    )
    assert result is None


def test_tier3_wrong_position_returns_none(session, seeded_players):
    # The LB Josh Allen is in canonical as LB, not RB.
    result = resolve(
        session,
        csv_row={"Player": "Josh Allen JAX"},
        position="RB",
    )
    assert result is None


def test_split_name_with_suffix(session, seeded_players):
    # Add a player with a suffix to test normalization.
    from app.models.orm import Player
    from datetime import datetime
    session.add(Player(mfl_id=6, gsis_id="00-0099999", name="Michael Penix Jr.",
                       merge_name="michael penix", team="ATL", position="QB",
                       seeded_at=datetime.utcnow().isoformat()))
    session.commit()
    result = resolve(
        session,
        csv_row={"Player": "Michael Penix Jr. ATL"},
        position="QB",
    )
    assert result == 6

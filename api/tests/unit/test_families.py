import pytest
from app.sim.families import STAT_FAMILY, family_for
from app.scoring.presets import PRESETS


@pytest.mark.parametrize("stat,expected", [
    ("passing_yards", "skewnorm"),
    ("rushing_yards", "skewnorm"),
    ("receiving_yards", "skewnorm"),
    ("receptions", "skewnorm"),
    ("passing_tds", "nbinom"),
    ("rushing_tds", "nbinom"),
    ("receiving_tds", "nbinom"),
    ("passing_interceptions", "nbinom"),
    ("rushing_fumbles_lost", "nbinom"),
])
def test_stat_family_dispatch(stat, expected):
    assert STAT_FAMILY[stat] == expected
    assert family_for(stat) == expected


def test_family_for_unknown_defaults_to_skewnorm():
    # New stats default to continuous family; safe default.
    assert family_for("some_future_yards_stat") == "skewnorm"


def test_all_scoreable_stats_registered():
    scoreable = set()
    for preset in PRESETS.values():
        scoreable.update(preset["multipliers"].keys())
    missing = scoreable - set(STAT_FAMILY.keys())
    assert not missing, f"missing family for: {missing}"

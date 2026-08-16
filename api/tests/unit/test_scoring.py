import pytest
from app.scoring.engine import score
from app.scoring.presets import PRESETS, STANDARD, FULL_PPR


def test_standard_qb_line_no_bonus():
    stats = {"passing_yards": 250, "passing_tds": 2, "passing_interceptions": 1}
    # 250*0.04 + 2*4 - 1 = 10 + 8 - 1 = 17
    assert score(stats, STANDARD) == pytest.approx(17.0)


def test_standard_300yd_bonus_exactly_at_threshold():
    stats = {"passing_yards": 300, "passing_tds": 0, "passing_interceptions": 0}
    # 300*0.04 + 3 (bonus) = 15
    assert score(stats, STANDARD) == pytest.approx(15.0)


def test_standard_299yd_no_bonus():
    stats = {"passing_yards": 299, "passing_tds": 0, "passing_interceptions": 0}
    assert score(stats, STANDARD) == pytest.approx(299 * 0.04)


def test_full_ppr_reception_multiplier():
    stats = {"receptions": 10, "receiving_yards": 100, "receiving_tds": 1}
    # 10*1 + 100*0.1 + 1*6 + 3(bonus) = 10 + 10 + 6 + 3 = 29
    assert score(stats, FULL_PPR) == pytest.approx(29.0)


def test_missing_stat_treated_as_zero():
    stats = {"passing_yards": 200}
    assert score(stats, STANDARD) == pytest.approx(8.0)


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        _ = PRESETS["not_a_preset"]


@pytest.mark.parametrize("preset_name", ["standard", "half_ppr", "full_ppr"])
def test_all_presets_have_required_keys(preset_name):
    p = PRESETS[preset_name]
    for stat in ["passing_yards", "passing_tds", "passing_interceptions",
                 "rushing_yards", "rushing_tds", "receiving_yards",
                 "receiving_tds", "receptions"]:
        assert stat in p["multipliers"], f"{preset_name} missing {stat}"

"""Three scoring presets. Keys are nflreadpy canonical stat names (ADR-0009)."""
from __future__ import annotations
from typing import TypedDict


class ScoringPreset(TypedDict):
    multipliers: dict[str, float]
    bonuses: list[tuple[str, float, float]]  # (stat, threshold, bonus_points)


def _common_bonuses() -> list[tuple[str, float, float]]:
    return [
        ("passing_yards", 300.0, 3.0),
        ("rushing_yards", 100.0, 3.0),
        ("receiving_yards", 100.0, 3.0),
    ]


STANDARD: ScoringPreset = {
    "multipliers": {
        "passing_yards": 0.04,
        "passing_tds": 4.0,
        "passing_interceptions": -1.0,
        "rushing_yards": 0.1,
        "rushing_tds": 6.0,
        "receiving_yards": 0.1,
        "receiving_tds": 6.0,
        "receptions": 0.0,
        "rushing_fumbles_lost": -1.0,
    },
    "bonuses": _common_bonuses(),
}

HALF_PPR: ScoringPreset = {
    "multipliers": {**STANDARD["multipliers"], "receptions": 0.5},
    "bonuses": _common_bonuses(),
}

FULL_PPR: ScoringPreset = {
    "multipliers": {**STANDARD["multipliers"], "receptions": 1.0},
    "bonuses": _common_bonuses(),
}

PRESETS: dict[str, ScoringPreset] = {
    "standard": STANDARD,
    "half_ppr": HALF_PPR,
    "full_ppr": FULL_PPR,
}

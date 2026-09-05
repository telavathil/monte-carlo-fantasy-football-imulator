"""Pure score function: stat line -> float fantasy points."""
from __future__ import annotations
from app.scoring.presets import ScoringPreset


def score(stats: dict[str, float], preset: ScoringPreset) -> float:
    total = 0.0
    for stat, mult in preset["multipliers"].items():
        total += float(stats.get(stat, 0)) * mult
    for stat, threshold, bonus in preset["bonuses"]:
        if float(stats.get(stat, 0)) >= threshold:
            total += bonus
    return total

"""Stat -> distribution family registry per ADR-0012 and ADR-0015."""
from __future__ import annotations


STAT_FAMILY: dict[str, str] = {
    # Continuous (skew-normal with 1.10x scale inflation; near-zero routes to Poisson)
    "passing_yards": "skewnorm",
    "rushing_yards": "skewnorm",
    "receiving_yards": "skewnorm",
    "receptions": "skewnorm",
    "completions": "skewnorm",
    "attempts": "skewnorm",
    "carries": "skewnorm",
    "targets": "skewnorm",
    # Count (nbinom method-of-moments; Poisson fallback on near-zero or invalid)
    "passing_tds": "nbinom",
    "passing_interceptions": "nbinom",
    "rushing_tds": "nbinom",
    "receiving_tds": "nbinom",
    "rushing_fumbles_lost": "nbinom",
}


def family_for(stat: str) -> str:
    """Return family; default to 'skewnorm' for unknown continuous-looking stats."""
    return STAT_FAMILY.get(stat, "skewnorm")

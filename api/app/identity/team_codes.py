"""Team abbreviation normalization per ADR-0013."""
from __future__ import annotations


TEAM_CODE_ALIASES: dict[str, str] = {
    "KC":  "KCC",
    "TB":  "TBB",
    "SF":  "SFO",
    "GB":  "GBP",
    "NO":  "NOS",
    "NE":  "NEP",
    "LV":  "LVR",
    "JAX": "JAC",
    "LA":  "LAR",
}


def canonicalize_team(code: str) -> str:
    code = code.strip().upper()
    return TEAM_CODE_ALIASES.get(code, code)

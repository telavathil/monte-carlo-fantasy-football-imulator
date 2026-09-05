import pytest
from app.identity.team_codes import canonicalize_team, TEAM_CODE_ALIASES


@pytest.mark.parametrize("inp,expected", [
    ("KC", "KCC"),
    ("TB", "TBB"),
    ("SF", "SFO"),
    ("GB", "GBP"),
    ("NO", "NOS"),
    ("NE", "NEP"),
    ("LV", "LVR"),
    ("JAX", "JAC"),
    ("LA", "LAR"),
    ("kc", "KCC"),           # case insensitive
    ("  TB  ", "TBB"),       # strips whitespace
])
def test_known_aliases(inp, expected):
    assert canonicalize_team(inp) == expected


@pytest.mark.parametrize("inp,expected", [
    ("DAL", "DAL"),
    ("PHI", "PHI"),
    ("BAL", "BAL"),
    ("NYJ", "NYJ"),
])
def test_unaliased_passthrough(inp, expected):
    assert canonicalize_team(inp) == expected


def test_empty_returns_empty():
    assert canonicalize_team("") == ""


def test_alias_table_has_all_nine_entries():
    assert len(TEAM_CODE_ALIASES) == 9

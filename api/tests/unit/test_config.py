from pathlib import Path
from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.api_token == "dev-token"
    assert s.data_dir == Path("/data")
    assert 2025 in s.historical_seasons
    assert s.sqlite_url.endswith("/sqlite.db")
    assert s.historical_dir.name == "historical"


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "overridden")
    s = Settings(_env_file=None)
    assert s.api_token == "overridden"

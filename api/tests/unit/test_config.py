import pytest
from pathlib import Path
from pydantic import ValidationError
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


def test_default_token_rejected_when_fly_app_name_set(monkeypatch):
    """A deployed-looking environment (FLY_APP_NAME set) must refuse to boot
    with the publicly-known 'dev-token' default rather than failing open."""
    monkeypatch.setenv("FLY_APP_NAME", "mc-ff-simulator")
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_default_token_allowed_without_fly_app_name(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    s = Settings(_env_file=None)
    assert s.api_token == "dev-token"


def test_custom_token_allowed_with_fly_app_name(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "mc-ff-simulator")
    monkeypatch.setenv("API_TOKEN", "a-real-secret")
    s = Settings(_env_file=None)
    assert s.api_token == "a-real-secret"


def test_cors_origins_accepts_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_accepts_json_array_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.com", "https://b.com"]')
    s = Settings(_env_file=None)
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_historical_seasons_accepts_comma_separated_string(monkeypatch):
    monkeypatch.setenv("HISTORICAL_SEASONS", "2022,2023,2024")
    s = Settings(_env_file=None)
    assert s.historical_seasons == [2022, 2023, 2024]


def test_historical_seasons_accepts_json_array_string(monkeypatch):
    monkeypatch.setenv("HISTORICAL_SEASONS", "[2022, 2023, 2024]")
    s = Settings(_env_file=None)
    assert s.historical_seasons == [2022, 2023, 2024]


def test_historical_seasons_accepts_single_bare_value(monkeypatch):
    """A single value with no comma is still valid JSON (a bare int), so it
    must not be treated as already-decoded and passed through unwrapped."""
    monkeypatch.setenv("HISTORICAL_SEASONS", "2025")
    s = Settings(_env_file=None)
    assert s.historical_seasons == [2025]


def test_cors_origins_accepts_single_bare_value(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["https://a.com"]

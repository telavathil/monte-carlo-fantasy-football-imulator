"""Application settings loaded from env vars."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Annotated
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_token: str = Field(default="dev-token")
    data_dir: Path = Field(default=Path("/data"))
    # NoDecode: pydantic-settings normally auto-JSON-decodes env values for
    # list-typed fields *before* any validator runs, raising its own
    # SettingsError on a plain comma-separated string. NoDecode disables that
    # so our field_validator below gets the raw string and can handle both
    # JSON-array and comma-separated forms itself.
    historical_seasons: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [2023, 2024, 2025]
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", "historical_seasons", mode="before")
    @classmethod
    def _accept_comma_separated_string(cls, value, info):
        """Accept plain comma-separated strings for list-typed env vars.

        pydantic-settings normally requires JSON-encoded values for list
        fields sourced from the environment (e.g. `'["a","b"]'`), but a plain
        comma-separated string (`"a,b"`) is the far more natural way to set a
        multi-value env var/secret — and it's what actually crash-looped the
        deployed app in production (`fly secrets set CORS_ORIGINS="url1,url2"`).
        If it's already a list, pass through unchanged. If it's a string, try
        JSON first (preserves existing behavior), then fall back to splitting
        on commas.
        """
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pieces = [piece.strip() for piece in value.split(",") if piece.strip()]
            if info.field_name == "historical_seasons":
                return [int(piece) for piece in pieces]
            return pieces

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.data_dir}/sqlite.db"

    @property
    def historical_dir(self) -> Path:
        return self.data_dir / "historical"

    @model_validator(mode="after")
    def _reject_default_token_when_deployed(self) -> "Settings":
        """Fail loudly instead of failing open.

        `api_token` keeps its "dev-token" default for local/test ergonomics
        (many tests construct `Settings()` and rely on it). But if we're
        clearly running on a real deployment — Fly.io sets FLY_APP_NAME on
        every deployed machine automatically — and API_TOKEN was never
        actually set, booting with the publicly-known default would silently
        accept "dev-token" as valid auth. Refuse to start instead.
        """
        if self.api_token == "dev-token" and os.getenv("FLY_APP_NAME"):
            raise ValueError(
                "API_TOKEN is unset (still the 'dev-token' default) while running "
                "in what looks like a deployed environment (FLY_APP_NAME is set). "
                "Set the API_TOKEN secret before deploying — refusing to boot with "
                "a publicly-known auth token."
            )
        return self


def get_settings() -> Settings:
    return Settings()

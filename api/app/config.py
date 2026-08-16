"""Application settings loaded from env vars."""
from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_token: str = Field(default="dev-token")
    data_dir: Path = Field(default=Path("/data"))
    historical_seasons: list[int] = Field(default_factory=lambda: [2023, 2024, 2025])
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.data_dir}/sqlite.db"

    @property
    def historical_dir(self) -> Path:
        return self.data_dir / "historical"


def get_settings() -> Settings:
    return Settings()

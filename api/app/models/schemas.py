"""Pydantic request/response schemas."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


Preset = Literal["standard", "half_ppr", "full_ppr"]


class LeagueConfigOut(BaseModel):
    scoring_preset: Preset
    num_teams: int
    updated_at: str


class LeagueConfigIn(BaseModel):
    scoring_preset: Preset | None = None
    num_teams: int | None = None


class ImportBatchResult(BaseModel):
    import_batch_id: int
    kind: Literal["stats", "adp"]
    source: str
    position: str | None = None
    status: str
    total_rows: int
    matched_rows: int
    unresolved_rows: int
    unmapped_columns: list = Field(default_factory=list)


class PlayerRow(BaseModel):
    player_id: int
    gsis_id: str
    name: str
    team: str | None
    position: str
    projected_stats: dict[str, float] = Field(default_factory=dict)
    projected_points: float | None = None
    adp_snake: float | None = None
    adp_auction: float | None = None


class Histogram(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class DistributionBody(BaseModel):
    n_samples: int
    floor_p10: float
    median_p50: float
    ceiling_p90: float
    mean: float
    std: float
    histogram: Histogram


class FitInfo(BaseModel):
    fitted_at: str
    historical_seasons: list[int]
    games_used: int


class DistributionResponse(BaseModel):
    player_id: int
    gsis_id: str
    projection: dict
    scoring_preset: Preset
    computed_points: float
    distribution: DistributionBody
    fit: FitInfo


class HistoricalStatus(BaseModel):
    seasons: list[int]
    last_refreshed_at: str | None
    ready: bool


class AdminRefreshResult(BaseModel):
    players_added: int
    players_updated: int
    unresolved_promoted: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict = Field(default_factory=dict)

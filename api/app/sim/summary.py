"""Compute, persist, invalidate, and query per-player distribution summaries.

A summary is the points-denominated output of a simulation run, cached per
(player, scoring_preset). It is distinct from PlayerDistributionParams, which
caches the preset-independent per-stat fits.

Every summary carries a `status`. A player who can never produce a
distribution — wrong position, too little history — gets a terminal row rather
than being silently skipped, so the precompute loop converges.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.historical.fetch import game_logs
from app.models.orm import (
    Player, PlayerProjection, PlayerDistributionParams,
    PlayerDistributionSummary,
)
from app.scoring.engine import score
from app.scoring.presets import PRESETS
from app.sim.families import family_for
from app.sim.fitting import dispatch_fit
from app.sim.runner import simulate_from_params

MIN_GAMES = 4
K_DEF_POSITIONS = {"K", "DEF"}
SUMMARY_N = 5000
SUMMARY_SEED = 42

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_history"
STATUS_UNSUPPORTED = "unsupported_position"


def _finite_or_none(value: float | None) -> float | None:
    """Coerce a non-finite float (NaN/inf) to None.

    scipy.stats.skew returns NaN for a zero-variance sample (every simulated
    point identical) — reachable when a projection's fitted params are all
    degenerate. NaN is not valid JSON, so it must never reach the response
    layer; the summary columns are nullable precisely so this is
    representable.
    """
    if value is None:
        return None
    return value if math.isfinite(value) else None


def _fit_params(session: Session, player: Player, projected_stats: dict,
                historical_seasons: list[int]) -> tuple[dict | None, str, int]:
    """Return (params, fitted_at, games_used); params is None when history is short.

    Reuses the cached per-stat fits when present — they are the expensive part
    and do not depend on the scoring preset.
    """
    cached = session.get(PlayerDistributionParams, player.mfl_id)
    if cached is not None:
        params = {k: tuple(v) for k, v in json.loads(cached.params).items()}
        return params, cached.fitted_at, cached.games_used

    logs = game_logs(player.gsis_id, historical_seasons)
    if logs.height < MIN_GAMES:
        return None, datetime.utcnow().isoformat(), logs.height

    params: dict[str, tuple] = {}
    for stat, target in projected_stats.items():
        if stat not in logs.columns:
            continue
        values = logs[stat].to_numpy()
        values = values[~(values != values)]  # drop NaN
        if len(values) < MIN_GAMES:
            continue
        params[stat] = dispatch_fit(values, float(target), family_for(stat))

    now = datetime.utcnow().isoformat()
    session.add(PlayerDistributionParams(
        player_id=player.mfl_id,
        params=json.dumps({k: list(v) for k, v in params.items()}),
        fitted_at=now,
        historical_seasons=",".join(str(y) for y in historical_seasons),
        games_used=logs.height,
    ))
    return params, now, logs.height


def compute_and_store(session: Session, *, player: Player,
                      projected_stats: dict, projection_id: int,
                      preset_name: str,
                      historical_seasons: list[int]) -> PlayerDistributionSummary:
    """Simulate and persist one summary. Adds to the session; caller commits."""
    now = datetime.utcnow().isoformat()
    existing = session.get(PlayerDistributionSummary, (player.mfl_id, preset_name))
    if existing is not None:
        session.delete(existing)
        session.flush()

    def _terminal(status: str) -> PlayerDistributionSummary:
        row = PlayerDistributionSummary(
            player_id=player.mfl_id, scoring_preset=preset_name,
            status=status, source_projection_id=projection_id,
            computed_at=now,
        )
        session.add(row)
        return row

    if player.position in K_DEF_POSITIONS:
        return _terminal(STATUS_UNSUPPORTED)

    params, _fitted_at, _games = _fit_params(
        session, player, projected_stats, historical_seasons)
    if params is None:
        return _terminal(STATUS_INSUFFICIENT)

    preset = PRESETS[preset_name]
    result = simulate_from_params(params, preset=preset,
                                  n=SUMMARY_N, seed=SUMMARY_SEED)
    row = PlayerDistributionSummary(
        player_id=player.mfl_id, scoring_preset=preset_name, status=STATUS_OK,
        floor_p10=_finite_or_none(result["floor_p10"]),
        p25=_finite_or_none(result["p25"]),
        median_p50=_finite_or_none(result["median_p50"]),
        p75=_finite_or_none(result["p75"]),
        ceiling_p90=_finite_or_none(result["ceiling_p90"]),
        mean=_finite_or_none(result["mean"]),
        std=_finite_or_none(result["std"]),
        skewness=_finite_or_none(result["skewness"]),
        histogram=json.dumps(result["histogram"]),
        computed_points=score(projected_stats, preset),
        n_samples=result["n_samples"], source_projection_id=projection_id,
        computed_at=now,
    )
    session.add(row)
    return row


def invalidate_for_players(session: Session, player_ids: Iterable[int]) -> int:
    """Drop every preset's summary for the given players. Caller commits."""
    ids = list(player_ids)
    if not ids:
        return 0
    return (session.query(PlayerDistributionSummary)
                   .filter(PlayerDistributionSummary.player_id.in_(ids))
                   .delete(synchronize_session=False))


def invalidate_all(session: Session) -> int:
    """Drop every summary. Caller commits."""
    return session.query(PlayerDistributionSummary).delete(
        synchronize_session=False)


def _latest_projection_ids(session: Session) -> dict[int, int]:
    """player_id -> id of that player's most recent projection."""
    latest = (session.query(PlayerProjection.player_id.label("pid"),
                            func.max(PlayerProjection.created_at).label("mx"))
                     .group_by(PlayerProjection.player_id).subquery())
    rows = (session.query(PlayerProjection)
                   .join(latest, (PlayerProjection.player_id == latest.c.pid)
                         & (PlayerProjection.created_at == latest.c.mx))
                   .all())
    out: dict[int, int] = {}
    for row in rows:
        if row.player_id not in out or row.id > out[row.player_id]:
            out[row.player_id] = row.id
    return out


def summary_progress(session: Session, preset_name: str) -> tuple[int, int]:
    """(done, total) for the given preset.

    Terminal rows count as done — a player who can never be simulated must not
    hold the progress bar below 100% forever.
    """
    total = session.query(func.count(func.distinct(
        PlayerProjection.player_id))).scalar() or 0
    done = (session.query(func.count(PlayerDistributionSummary.player_id))
                   .filter(PlayerDistributionSummary.scoring_preset == preset_name)
                   .scalar() or 0)
    return int(done), int(total)


def players_needing_summary(session: Session, preset_name: str,
                            limit: int) -> list[tuple[Player, PlayerProjection]]:
    """Players holding a projection but no summary under this preset."""
    have = {pid for (pid,) in session.query(PlayerDistributionSummary.player_id)
            .filter(PlayerDistributionSummary.scoring_preset == preset_name).all()}
    latest_ids = _latest_projection_ids(session)
    pending = [pid for pid in latest_ids if pid not in have]
    pending.sort()
    chosen = pending[:limit]
    if not chosen:
        return []
    players = {p.mfl_id: p for p in session.query(Player)
               .filter(Player.mfl_id.in_(chosen)).all()}
    projections = {pr.id: pr for pr in session.query(PlayerProjection)
                   .filter(PlayerProjection.id.in_(
                       [latest_ids[pid] for pid in chosen])).all()}
    return [(players[pid], projections[latest_ids[pid]])
            for pid in chosen if pid in players]

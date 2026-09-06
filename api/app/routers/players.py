import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.config import get_settings
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, LeagueConfig,
    PlayerDistributionParams, PlayerDistributionSummary,
)
from app.models.schemas import PlayerRow, DistributionResponse, DistributionBody, FitInfo, Histogram, DistributionSummary, PrecomputeResult
from app.scoring.presets import PRESETS
from app.scoring.engine import score
from app.sim import summary as summary_mod

router = APIRouter(dependencies=[Depends(require_token)])


def _latest_projection(db: Session, player_id: int) -> PlayerProjection | None:
    return (db.query(PlayerProjection)
              .filter_by(player_id=player_id)
              .order_by(desc(PlayerProjection.created_at))
              .first())


def _latest_adp(db: Session, player_id: int) -> PlayerAdp | None:
    return (db.query(PlayerAdp)
              .filter_by(player_id=player_id)
              .order_by(desc(PlayerAdp.created_at))
              .first())


def _latest_by_player(db: Session, model) -> dict[int, object]:
    """Batch-fetch the latest row per player_id for `model` (PlayerProjection
    or PlayerAdp) in ~1 query instead of one correlated subquery per player.

    Replaces an O(N) per-player query loop (up to ~15,800 queries over the
    full ~7,900-player registry) with two queries total across both models.
    """
    latest_created = (
        db.query(model.player_id.label("player_id"),
                 func.max(model.created_at).label("max_created_at"))
          .group_by(model.player_id)
          .subquery()
    )
    candidates = (
        db.query(model)
          .join(latest_created,
                (model.player_id == latest_created.c.player_id)
                & (model.created_at == latest_created.c.max_created_at))
          .all()
    )
    result: dict[int, object] = {}
    for row in candidates:
        # Ties on (player_id, max created_at) — e.g. rows from the same
        # import batch — are broken by highest id (most recently inserted),
        # mirroring the previous per-row `.order_by(desc(created_at)).first()`.
        existing = result.get(row.player_id)
        if existing is None or row.id > existing.id:
            result[row.player_id] = row
    return result


def _summaries_by_player(db: Session, preset_name: str) -> dict[int, DistributionSummary]:
    """One query for every summary under the active preset.

    Mirrors the batching in _latest_by_player — this must not become an N+1.
    """
    rows = (db.query(PlayerDistributionSummary)
              .filter(PlayerDistributionSummary.scoring_preset == preset_name)
              .all())
    return {
        row.player_id: DistributionSummary(
            status=row.status, floor_p10=row.floor_p10, p25=row.p25,
            median_p50=row.median_p50, p75=row.p75, ceiling_p90=row.ceiling_p90,
            mean=row.mean, std=row.std, skewness=row.skewness,
            histogram=Histogram(**json.loads(row.histogram)) if row.histogram else None,
            computed_at=row.computed_at,
        )
        for row in rows
    }


@router.get("", response_model=list[PlayerRow])
def list_players(position: str | None = None, has_projection: bool = False,
                 db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    preset = PRESETS[cfg.scoring_preset]
    proj_by_player = _latest_by_player(db, PlayerProjection)
    adp_by_player = _latest_by_player(db, PlayerAdp)
    summary_by_player = _summaries_by_player(db, cfg.scoring_preset)
    q = db.query(Player)
    if position:
        q = q.filter(Player.position == position.upper())
    rows: list[PlayerRow] = []
    for p in q.all():
        proj = proj_by_player.get(p.mfl_id)
        if has_projection and proj is None:
            continue
        stats = json.loads(proj.stats) if proj else {}
        computed = score(stats, preset) if stats else None
        adp = adp_by_player.get(p.mfl_id)
        rows.append(PlayerRow(
            player_id=p.mfl_id, gsis_id=p.gsis_id, name=p.name,
            team=p.team, position=p.position,
            projected_stats={k: float(v) for k, v in stats.items()},
            projected_points=computed,
            adp_snake=adp.adp_snake if adp else None,
            adp_auction=adp.adp_auction if adp else None,
            distribution=summary_by_player.get(p.mfl_id),
        ))
    return rows


@router.post("/precompute", response_model=PrecomputeResult)
def precompute(limit: int = Query(25, ge=1, le=100),
               db: Session = Depends(get_db)):
    """Compute the next chunk of missing summaries under the active preset.

    Chunked and client-driven on purpose: a full import is 250-350 players at
    roughly 250ms each, which is far too long for one request, and a detached
    background task would race Fly's auto-stop. The caller loops until
    `remaining` is 0, which is also what drives the import progress bar.
    """
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    settings = get_settings()
    pending = summary_mod.players_needing_summary(db, cfg.scoring_preset, limit)
    for player, projection in pending:
        summary_mod.compute_and_store(
            db, player=player,
            projected_stats=json.loads(projection.stats),
            projection_id=projection.id,
            preset_name=cfg.scoring_preset,
            historical_seasons=settings.historical_seasons,
        )
    db.commit()
    done, total = summary_mod.summary_progress(db, cfg.scoring_preset)
    return PrecomputeResult(computed=len(pending), done=done, total=total,
                            remaining=max(total - done, 0))


@router.get("/{player_id}/distribution", response_model=DistributionResponse)
def get_distribution(player_id: int, db: Session = Depends(get_db)):
    p = db.get(Player, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail="player not found")
    if p.position in summary_mod.K_DEF_POSITIONS:
        raise HTTPException(status_code=422,
                            detail={"error": "not_supported_mvp",
                                    "message": "K/DEF distributions not supported in MVP"})
    proj = _latest_projection(db, player_id)
    if proj is None:
        raise HTTPException(status_code=404,
                            detail="no projection for player")
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    settings = get_settings()
    projected_stats = json.loads(proj.stats)

    row = db.get(PlayerDistributionSummary, (player_id, cfg.scoring_preset))
    if row is None:
        row = summary_mod.compute_and_store(
            db, player=p, projected_stats=projected_stats,
            projection_id=proj.id, preset_name=cfg.scoring_preset,
            historical_seasons=settings.historical_seasons)
        db.commit()

    if row.status == summary_mod.STATUS_UNSUPPORTED:
        raise HTTPException(
            status_code=422,
            detail={"error": "not_supported_mvp",
                    "message": "K/DEF distributions not supported in MVP"})
    if row.status == summary_mod.STATUS_INSUFFICIENT:
        raise HTTPException(
            status_code=422,
            detail={"error": "insufficient_history",
                    "message": "Not enough career games to model this player",
                    "details": {"min_games": summary_mod.MIN_GAMES}})

    params_row = db.get(PlayerDistributionParams, player_id)
    adp = _latest_adp(db, player_id)
    return DistributionResponse(
        player_id=player_id, gsis_id=p.gsis_id, name=p.name, team=p.team,
        position=p.position, adp_snake=adp.adp_snake if adp else None,
        projection={"stats": projected_stats,
                    "import_batch_id": proj.import_batch_id},
        scoring_preset=cfg.scoring_preset,
        computed_points=row.computed_points,
        distribution=DistributionBody(
            n_samples=row.n_samples, floor_p10=row.floor_p10, p25=row.p25,
            median_p50=row.median_p50, p75=row.p75, ceiling_p90=row.ceiling_p90,
            mean=row.mean, std=row.std, skewness=row.skewness,
            histogram=Histogram(**json.loads(row.histogram)),
        ),
        fit=FitInfo(
            fitted_at=params_row.fitted_at if params_row else row.computed_at,
            historical_seasons=settings.historical_seasons,
            games_used=params_row.games_used if params_row else 0),
    )

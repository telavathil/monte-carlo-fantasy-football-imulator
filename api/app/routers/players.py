import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.config import get_settings
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, LeagueConfig,
    PlayerDistributionParams,
)
from app.models.schemas import PlayerRow, DistributionResponse, DistributionBody, FitInfo, Histogram
from app.scoring.presets import PRESETS
from app.scoring.engine import score
from app.sim.families import family_for
from app.sim.fitting import dispatch_fit
from app.sim.runner import simulate_from_params
from app.historical.fetch import game_logs

router = APIRouter(dependencies=[Depends(require_token)])

K_DEF_POSITIONS = {"K", "DEF"}
MIN_GAMES = 4


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


@router.get("", response_model=list[PlayerRow])
def list_players(position: str | None = None, has_projection: bool = False,
                 db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    preset = PRESETS[cfg.scoring_preset]
    proj_by_player = _latest_by_player(db, PlayerProjection)
    adp_by_player = _latest_by_player(db, PlayerAdp)
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
        ))
    return rows


@router.get("/{player_id}/distribution", response_model=DistributionResponse)
def get_distribution(player_id: int, n: int = Query(5000, ge=100, le=20000),
                     db: Session = Depends(get_db)):
    p = db.get(Player, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail="player not found")
    if p.position in K_DEF_POSITIONS:
        raise HTTPException(status_code=422,
                            detail={"error": "not_supported_mvp",
                                    "message": "K/DEF distributions not supported in MVP"})
    proj = _latest_projection(db, player_id)
    if proj is None:
        raise HTTPException(status_code=404,
                            detail="no projection for player")
    projected_stats = json.loads(proj.stats)
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    preset = PRESETS[cfg.scoring_preset]
    settings = get_settings()

    # Load historical
    logs = game_logs(p.gsis_id, settings.historical_seasons)
    if logs.height < MIN_GAMES:
        raise HTTPException(
            status_code=422,
            detail={"error": "insufficient_history",
                    "message": f"Only {logs.height} career games",
                    "details": {"games_found": logs.height}},
        )

    # Fit per stat (using cache if present)
    cached = db.get(PlayerDistributionParams, player_id)
    if cached is not None:
        import json as _json
        params = {k: tuple(v) for k, v in _json.loads(cached.params).items()}
        fitted_at = cached.fitted_at
        games_used = cached.games_used
    else:
        params = {}
        for stat, target in projected_stats.items():
            if stat not in logs.columns:
                continue
            vals = logs[stat].to_numpy()
            vals = vals[~(vals != vals)]  # drop NaN
            if len(vals) < MIN_GAMES:
                continue
            fam_cat = family_for(stat)
            params[stat] = dispatch_fit(vals, float(target), fam_cat)
        import json as _json
        db.add(PlayerDistributionParams(
            player_id=player_id,
            params=_json.dumps({k: list(v) for k, v in params.items()}),
            fitted_at=datetime.utcnow().isoformat(),
            historical_seasons=",".join(str(y) for y in settings.historical_seasons),
            games_used=logs.height,
        ))
        db.commit()
        fitted_at = datetime.utcnow().isoformat()
        games_used = logs.height

    result = simulate_from_params(params, preset=preset, n=n, seed=42)
    computed = score(projected_stats, preset)
    return DistributionResponse(
        player_id=player_id, gsis_id=p.gsis_id,
        projection={"stats": projected_stats, "import_batch_id": proj.import_batch_id},
        scoring_preset=cfg.scoring_preset,
        computed_points=computed,
        distribution=DistributionBody(
            n_samples=result["n_samples"],
            floor_p10=result["floor_p10"],
            median_p50=result["median_p50"],
            ceiling_p90=result["ceiling_p90"],
            mean=result["mean"], std=result["std"],
            histogram=Histogram(**result["histogram"]),
        ),
        fit=FitInfo(fitted_at=fitted_at,
                    historical_seasons=settings.historical_seasons,
                    games_used=games_used),
    )

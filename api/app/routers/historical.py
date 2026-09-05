from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.config import get_settings
from app.historical.fetch import ensure_seasons
from app.models.orm import PlayerDistributionParams

router = APIRouter(dependencies=[Depends(require_token)])


class RefreshBody(BaseModel):
    seasons: list[int] | None = None


@router.get("/status")
def status():
    settings = get_settings()
    seasons = []
    if settings.historical_dir.is_dir():
        for p in settings.historical_dir.glob("player_stats_*.parquet"):
            try:
                seasons.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
    return {
        "seasons": sorted(seasons),
        "last_refreshed_at": None,  # not tracked in MVP
        "ready": bool(seasons),
    }


@router.post("/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    settings = get_settings()
    years = body.seasons or settings.historical_seasons
    # Re-fetch: delete parquet first so ensure_seasons re-downloads
    for y in years:
        path = settings.historical_dir / f"player_stats_{y}.parquet"
        if path.exists():
            path.unlink()
    ensure_seasons(years)
    # Invalidate all cached fit params
    db.query(PlayerDistributionParams).delete()
    db.commit()
    return {"job_status": "complete"}

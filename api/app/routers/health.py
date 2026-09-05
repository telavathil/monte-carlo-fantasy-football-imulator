from fastapi import APIRouter, Depends
from app.config import get_settings
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    seasons = []
    if settings.historical_dir.is_dir():
        for p in settings.historical_dir.glob("player_stats_*.parquet"):
            try:
                seasons.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
    return {
        "status": "ok",
        "db": db_ok,
        "historical_ready": bool(seasons),
        "historical_seasons": sorted(seasons),
    }

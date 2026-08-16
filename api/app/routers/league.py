from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.models.orm import LeagueConfig
from app.models.schemas import LeagueConfigOut, LeagueConfigIn

router = APIRouter(dependencies=[Depends(require_token)])


@router.get("/config", response_model=LeagueConfigOut)
def get_config(db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    return LeagueConfigOut(scoring_preset=cfg.scoring_preset,
                           num_teams=cfg.num_teams, updated_at=cfg.updated_at)


@router.put("/config", response_model=LeagueConfigOut)
def put_config(body: LeagueConfigIn, db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    if body.scoring_preset is not None:
        cfg.scoring_preset = body.scoring_preset
    if body.num_teams is not None:
        cfg.num_teams = body.num_teams
    cfg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return LeagueConfigOut(scoring_preset=cfg.scoring_preset,
                           num_teams=cfg.num_teams, updated_at=cfg.updated_at)

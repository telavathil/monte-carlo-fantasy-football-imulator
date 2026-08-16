import json
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.historical.fetch import seed_players
from app.identity.resolver import resolve
from app.models.orm import (
    Player, ImportUnresolved, PlayerProjection, ImportBatch,
)
from app.models.schemas import AdminRefreshResult

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/refresh-players", response_model=AdminRefreshResult)
def refresh_players(db: Session = Depends(get_db)):
    before = db.query(Player).count()
    seed_players(db)
    after = db.query(Player).count()
    added = after - before
    updated = after - added  # Upserts touched all rows; rough accounting for MVP.

    # Re-run resolver on pending unresolved rows
    promoted = 0
    unresolved = (db.query(ImportUnresolved)
                    .filter(ImportUnresolved.resolution.is_(None),
                            ImportUnresolved.resolved_player_id.is_(None))
                    .all())
    now = datetime.utcnow().isoformat()
    for u in unresolved:
        batch = db.get(ImportBatch, u.import_batch_id)
        if batch is None or batch.kind != "stats":
            continue
        csv_row = json.loads(u.csv_row)
        mfl_id = resolve(db, csv_row=csv_row, position=batch.position or "QB")
        if mfl_id is not None:
            u.resolved_player_id = mfl_id
            u.resolution = "manual"  # auto-promoted
            stats = {k: float(v) for k, v in csv_row.items()
                     if isinstance(v, (int, float)) and k not in ("Player", "player")}
            db.add(PlayerProjection(
                player_id=mfl_id, import_batch_id=batch.id, position=batch.position,
                stats=json.dumps(stats), created_at=now,
            ))
            promoted += 1
    db.commit()
    return AdminRefreshResult(players_added=added, players_updated=updated,
                              unresolved_promoted=promoted)

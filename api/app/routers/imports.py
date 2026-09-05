import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.import_pipeline.stats_importer import import_stats
from app.import_pipeline.adp_importer import import_adp
from app.models.orm import ImportBatch, ImportUnresolved
from app.models.schemas import ImportBatchResult, UnresolvedRow

router = APIRouter(dependencies=[Depends(require_token)])


def _to_result(batch: ImportBatch, summary: dict) -> ImportBatchResult:
    return ImportBatchResult(
        import_batch_id=batch.id,
        kind=batch.kind, source=batch.source, position=batch.position,
        status=batch.status, total_rows=batch.total_rows,
        matched_rows=batch.matched_rows, unresolved_rows=batch.unresolved_rows,
        unmapped_columns=summary.get("unmapped_columns", []),
    )


@router.post("/stats", response_model=ImportBatchResult)
async def post_stats(file: UploadFile = File(...), source: str = Form(...),
                     position: str = Form(...),
                     db: Session = Depends(get_db)):
    content = await file.read()
    batch_id, summary = import_stats(db, content=content, filename=file.filename or "upload",
                                      source=source, position=position)
    batch = db.get(ImportBatch, batch_id)
    return _to_result(batch, summary)


@router.post("/adp", response_model=ImportBatchResult)
async def post_adp(file: UploadFile = File(...), source: str = Form(...),
                   db: Session = Depends(get_db)):
    content = await file.read()
    batch_id, summary = import_adp(db, content=content, filename=file.filename or "upload",
                                    source=source)
    batch = db.get(ImportBatch, batch_id)
    return _to_result(batch, summary)


@router.get("/{batch_id}/unresolved", response_model=list[UnresolvedRow])
def get_unresolved(batch_id: int, db: Session = Depends(get_db)):
    """Rows that failed identity resolution. Read-only by design."""
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    rows = (db.query(ImportUnresolved)
              .filter(ImportUnresolved.import_batch_id == batch_id)
              .all())
    return [
        UnresolvedRow(
            parsed_name=row.parsed_name,
            parsed_team=row.parsed_team,
            position=batch.position,
            resolution=row.resolution or "no_canonical_match",
            csv_row=json.loads(row.csv_row),
        )
        for row in rows
    ]


@router.get("/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return _to_result(batch, {})

"""Orchestrates stats-CSV import: parse → map → resolve → persist."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.import_pipeline.csv_parser import parse_file
from app.import_pipeline.column_mapper import map_columns
from app.identity.resolver import resolve
from app.models.orm import (
    ImportBatch, PlayerProjection, ImportUnresolved, PlayerDistributionParams,
)
from app.sim import summary as summary_mod


def invalidate_caches_for(session: Session, player_ids) -> None:
    """Drop every cached derivation for these players.

    Fits and summaries must go together: a new projection changes the target
    means the fits were shifted to, so both are stale.
    """
    ids = list(player_ids)
    if not ids:
        return
    (session.query(PlayerDistributionParams)
            .filter(PlayerDistributionParams.player_id.in_(ids))
            .delete(synchronize_session=False))
    summary_mod.invalidate_for_players(session, ids)


def import_stats(session: Session, *, content: bytes, filename: str,
                 source: str, position: str) -> tuple[int, dict]:
    df, meta = parse_file(content, filename=filename)

    # Default to fantasypros_multi_header for FP HTML; by_name for flat CSV.
    if meta["format"] == "html" and source == "fantasypros":
        mapped_df, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    else:
        # Minimal pass-through: keep column names as-is.
        mapped_df = df.copy()
        unmapped = []

    now = datetime.utcnow().isoformat()
    batch = ImportBatch(
        kind="stats", source=source, position=position, filename=filename,
        status="pending", total_rows=len(mapped_df), matched_rows=0,
        unresolved_rows=0, unmapped_columns=json.dumps([list(k) if isinstance(k, tuple) else k for k in unmapped]),
        created_at=now,
    )
    session.add(batch)
    session.flush()  # get batch.id

    matched = 0
    unresolved = 0
    matched_player_ids: set[int] = set()
    for _, row in mapped_df.iterrows():
        csv_row = {c: row[c] for c in mapped_df.columns}
        try:
            mfl_id = resolve(session, csv_row=csv_row, position=position)
            if mfl_id is not None:
                stats = {k: float(v) for k, v in csv_row.items()
                         if k != "Player" and k != "player" and isinstance(v, (int, float)) and v == v}
                session.add(PlayerProjection(
                    player_id=mfl_id, import_batch_id=batch.id, position=position,
                    stats=json.dumps(stats), created_at=now,
                ))
                matched += 1
                matched_player_ids.add(mfl_id)
            else:
                from app.import_pipeline.csv_parser import split_name_team
                from app.identity.resolver import normalize_name
                from app.identity.team_codes import canonicalize_team
                combined = csv_row.get("Player") or csv_row.get("player") or ""
                name, team = split_name_team(combined)
                session.add(ImportUnresolved(
                    import_batch_id=batch.id,
                    csv_row=json.dumps({k: (float(v) if isinstance(v, (int, float)) else v)
                                        for k, v in csv_row.items() if v == v}),
                    parsed_name=normalize_name(name),
                    parsed_team=canonicalize_team(team),
                ))
                unresolved += 1
        except Exception as e:
            session.add(ImportUnresolved(
                import_batch_id=batch.id,
                csv_row=json.dumps({k: str(v) for k, v in csv_row.items()}),
                parsed_name=None,
                parsed_team=None,
                resolution=f"error: {e}"[:255],
            ))
            unresolved += 1
            continue

    # Invalidate any cached fitted distribution params and summaries for
    # players whose projection just changed, so /distribution re-fits
    # against fresh data instead of silently serving stale derivations.
    invalidate_caches_for(session, matched_player_ids)

    batch.matched_rows = matched
    batch.unresolved_rows = unresolved
    batch.status = "resolved" if unresolved == 0 else "partial"
    session.commit()
    return batch.id, {
        "matched_rows": matched, "unresolved_rows": unresolved,
        "unmapped_columns": unmapped,
    }

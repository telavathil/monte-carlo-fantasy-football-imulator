"""ADP CSV importer: similar orchestration but simpler target table."""
from __future__ import annotations
import json
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session
from app.import_pipeline.csv_parser import parse_file, split_name_team
from app.identity.resolver import resolve, normalize_name
from app.identity.team_codes import canonicalize_team
from app.models.orm import ImportBatch, PlayerAdp, ImportUnresolved


_ADP_COLUMNS = {"adp_snake", "adp_auction", "ecr", "bye_week"}


def import_adp(session: Session, *, content: bytes, filename: str,
               source: str) -> tuple[int, dict]:
    df, meta = parse_file(content, filename=filename)
    now = datetime.utcnow().isoformat()
    batch = ImportBatch(
        kind="adp", source=source, position=None, filename=filename,
        status="pending", total_rows=len(df), matched_rows=0,
        unresolved_rows=0, unmapped_columns=json.dumps([]),
        created_at=now,
    )
    session.add(batch)
    session.flush()

    matched = 0
    unresolved = 0
    for _, row in df.iterrows():
        csv_row = {c: row[c] for c in df.columns}
        try:
            # ADP CSVs are typically NOT split by position (overall ADP rankings
            # spanning all positions), so there is usually no `position` column
            # at all. Pass an empty string through in that case rather than
            # guessing "QB" — resolve() treats an empty position as "no filter"
            # and matches on name + team alone (still guarded by the Tier-3
            # ambiguity check).
            position = str(csv_row.get("position", "")).strip().upper()
            # resolve()'s Tier-3 match expects a combined "Name TEAM" string in the
            # "Player" field (as produced by FantasyPros HTML tables). ADP CSVs
            # commonly carry name and team as separate columns instead, so
            # reconstruct the combined form here without mutating the row we
            # persist to ImportUnresolved.
            resolve_row = csv_row
            team_val = csv_row.get("Team") or csv_row.get("team")
            if team_val not in (None, ""):
                name_val = csv_row.get("Player") or csv_row.get("player") or ""
                resolve_row = {**csv_row, "Player": f"{name_val} {str(team_val).strip().upper()}"}
            mfl_id = resolve(session, csv_row=resolve_row, position=position)
            if mfl_id is not None:
                kwargs = {}
                for c in _ADP_COLUMNS:
                    val = csv_row.get(c)
                    kwargs[c] = float(val) if val is not None and val == val else None
                session.add(PlayerAdp(
                    player_id=mfl_id, import_batch_id=batch.id,
                    created_at=now, **kwargs,
                ))
                matched += 1
            else:
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

    batch.matched_rows = matched
    batch.unresolved_rows = unresolved
    batch.status = "resolved" if unresolved == 0 else "partial"
    session.commit()
    return batch.id, {"matched_rows": matched, "unresolved_rows": unresolved}

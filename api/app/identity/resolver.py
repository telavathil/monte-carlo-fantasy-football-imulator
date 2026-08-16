"""Identity resolution per ADR-0005 + ADR-0013 (Tier 1 + Tier 3 with team aliases)."""
from __future__ import annotations
import re
from sqlalchemy.orm import Session
from app.models.orm import Player
from app.identity.team_codes import canonicalize_team


KNOWN_ID_COLS: dict[str, str] = {
    # csv column name -> player ORM attribute
    "fantasypros_id": "fantasypros_id",
    "espn_id": "espn_id",
    "yahoo_id": "yahoo_id",
    "sleeper_id": "sleeper_id",
    "cbs_id": "cbs_id",
    "pfr_id": "pfr_id",
    "fantasy_data_id": "fantasy_data_id",
    "rotowire_id": "rotowire_id",
    "nfl_id": "nfl_id",
}

_SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv)\.?$", re.IGNORECASE)


def normalize_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[.'’]", "", s)
    s = _SUFFIX_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s


def split_name_team(combined: str) -> tuple[str, str]:
    parts = combined.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def resolve(session: Session, csv_row: dict, position: str) -> int | None:
    """Return mfl_id or None."""
    # Tier 1: direct ID match on any known ID column
    for csv_col, orm_attr in KNOWN_ID_COLS.items():
        if csv_col in csv_row and csv_row[csv_col] not in (None, ""):
            val = csv_row[csv_col]
            match = (session.query(Player)
                     .filter(getattr(Player, orm_attr) == val)
                     .one_or_none())
            if match is not None:
                return match.mfl_id

    # Tier 3: normalized name + canonicalized team + position
    combined = csv_row.get("Player") or csv_row.get("player") or ""
    name, team_raw = split_name_team(combined)
    merge = normalize_name(name)
    team = canonicalize_team(team_raw)
    if not merge or not team:
        return None
    matches = (session.query(Player)
               .filter(Player.merge_name == merge,
                       Player.team == team,
                       Player.position == position)
               .all())
    if len(matches) == 1:
        return matches[0].mfl_id
    return None

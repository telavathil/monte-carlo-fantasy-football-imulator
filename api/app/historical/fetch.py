"""Historical data wrapper per ADR-0014: we write parquet ourselves."""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
import polars as pl
import nflreadpy as nfl
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from app.config import get_settings
from app.models.orm import Player

logger = logging.getLogger(__name__)


def ensure_seasons(years: list[int], hist_dir: Path | None = None) -> None:
    """Fetch + persist each missing season's parquet."""
    hist_dir = hist_dir or get_settings().historical_dir
    hist_dir.mkdir(parents=True, exist_ok=True)
    for y in years:
        path = hist_dir / f"player_stats_{y}.parquet"
        if not path.exists():
            df = nfl.load_player_stats(seasons=[y])
            df.write_parquet(path)


def game_logs(gsis_id: str, years: list[int], hist_dir: Path | None = None) -> pl.DataFrame:
    """Read cached parquet, filter to REG + active weeks for the given player."""
    hist_dir = hist_dir or get_settings().historical_dir
    dfs = [pl.read_parquet(hist_dir / f"player_stats_{y}.parquet") for y in years]
    df = pl.concat(dfs)
    return df.filter(
        (pl.col("player_id") == gsis_id)
        & (pl.col("season_type") == "REG")
        & ((pl.col("attempts").fill_null(0)
            + pl.col("carries").fill_null(0)
            + pl.col("targets").fill_null(0)) > 0)
    )


# Columns we persist from ff_playerids into our `player` table.
_PLAYER_COLUMNS = [
    "mfl_id", "gsis_id", "name", "merge_name", "team", "position",
    "fantasypros_id", "espn_id", "yahoo_id", "sleeper_id", "cbs_id",
    "pfr_id", "fantasy_data_id", "rotowire_id", "nfl_id",
    "birthdate", "draft_year", "db_season",
]


def _dedupe_by_gsis_id(df):
    """Resolve gsis_id collisions in ff_playerids before upserting.

    Real ff_playerids data contains a handful of gsis_id values duplicated
    across distinct mfl_id rows (nflreadpy crosswalk data-quality quirk —
    e.g. two different real people incorrectly mapped to the same gsis_id
    upstream). player.gsis_id is UNIQUE, so exactly one row per gsis_id must
    survive. Rather than an arbitrary "whatever order the source emitted"
    keep, we sort so the more plausible row wins:
      1. A row with a real team beats one parked at "FA" (free agent/
         inactive placeholder) — an active roster spot is stronger signal
         than an inactive one.
      2. Among remaining ties, prefer the more recent db_season, then the
         more recent draft_year — newer crosswalk data is more likely
         correct than stale data.
      3. If still tied (e.g. two active-team rows from the same draft
         class — this happens in practice, see e.g. gsis_id 00-0031320:
         "Fred Williams"/KCC vs "Kevin Smith"/SEA, both draft_year 2014),
         fall back to the lower mfl_id. This tiebreak carries no real-world
         meaning; its only job is to be deterministic and stable across
         runs/pandas versions, since sort_values is not guaranteed stable
         for multi-key sorts.
    Every dropped row is logged (gsis_id, mfl_id, name) so a future reader
    can audit exactly what was discarded and why.
    """
    ranked = df.copy()
    ranked["_is_fa"] = ranked["team"] == "FA"
    ranked = ranked.sort_values(
        by=["_is_fa", "db_season", "draft_year", "mfl_id"],
        ascending=[True, False, False, True],
    )
    dup_mask = ranked.duplicated(subset=["gsis_id"], keep="first")
    if dup_mask.any():
        for _, dropped in ranked[dup_mask].iterrows():
            logger.warning(
                "seed_players: dropping duplicate gsis_id=%s mfl_id=%s name=%r "
                "(kept a different mfl_id row for this gsis_id)",
                dropped["gsis_id"], dropped["mfl_id"], dropped["name"],
            )
    return ranked[~dup_mask].drop(columns=["_is_fa"])


def seed_players(session: Session) -> int:
    """Upsert player registry from ff_playerids (filtered to gsis_id NOT NULL)."""
    df = nfl.load_ff_playerids().to_pandas()
    df = df[df["gsis_id"].notna()].copy()
    df = _dedupe_by_gsis_id(df)
    now = datetime.utcnow().isoformat()

    count = 0
    for _, row in df.iterrows():
        values = {col: (row[col] if col in df.columns and row[col] == row[col] else None)
                  for col in _PLAYER_COLUMNS}
        # Some ints may be floats due to nullability; coerce to int where known int columns
        for int_col in ("mfl_id", "fantasypros_id", "espn_id", "sleeper_id",
                        "cbs_id", "fantasy_data_id", "rotowire_id", "nfl_id",
                        "draft_year", "db_season"):
            if values.get(int_col) is not None:
                try:
                    values[int_col] = int(values[int_col])
                except (ValueError, TypeError):
                    values[int_col] = None
        values["seeded_at"] = now
        stmt = sqlite_upsert(Player).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["mfl_id"],
            set_={k: v for k, v in values.items() if k != "mfl_id"},
        )
        session.execute(stmt)
        count += 1
    session.commit()
    return count

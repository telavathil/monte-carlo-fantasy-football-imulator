"""SQLAlchemy ORM models matching spec §3."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, CheckConstraint,
    UniqueConstraint, Index, DateTime
)
from sqlalchemy.orm import relationship
from app.db import Base


class Player(Base):
    __tablename__ = "player"
    mfl_id = Column(Integer, primary_key=True)
    gsis_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    merge_name = Column(String, nullable=False, index=True)
    team = Column(String)
    position = Column(String, nullable=False)
    fantasypros_id = Column(Integer, index=True)
    espn_id = Column(Integer, index=True)
    yahoo_id = Column(String, index=True)
    sleeper_id = Column(Integer, index=True)
    cbs_id = Column(Integer, index=True)
    pfr_id = Column(String, index=True)
    fantasy_data_id = Column(Integer, index=True)
    rotowire_id = Column(Integer, index=True)
    nfl_id = Column(Integer, index=True)
    birthdate = Column(String)
    draft_year = Column(Integer)
    db_season = Column(Integer)
    seeded_at = Column(String, nullable=False)


Index("idx_player_merge_team_pos", Player.merge_name, Player.team, Player.position)


class ImportBatch(Base):
    __tablename__ = "import_batch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String, nullable=False)
    source = Column(String, nullable=False)
    position = Column(String)
    filename = Column(String)
    status = Column(String, nullable=False)
    total_rows = Column(Integer, nullable=False)
    matched_rows = Column(Integer, nullable=False)
    unresolved_rows = Column(Integer, nullable=False)
    unmapped_columns = Column(Text)  # JSON array
    created_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('stats','adp')"),
    )


class PlayerProjection(Base):
    __tablename__ = "player_projection"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.mfl_id"), nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    position = Column(String, nullable=False)
    stats = Column(Text, nullable=False)  # JSON
    created_at = Column(String, nullable=False)


Index("idx_proj_player_latest", PlayerProjection.player_id, PlayerProjection.created_at.desc())


class PlayerAdp(Base):
    __tablename__ = "player_adp"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.mfl_id"), nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    adp_snake = Column(Float)
    adp_auction = Column(Float)
    ecr = Column(Float)
    bye_week = Column(Integer)
    created_at = Column(String, nullable=False)


Index("idx_adp_player_latest", PlayerAdp.player_id, PlayerAdp.created_at.desc())


class ImportUnresolved(Base):
    __tablename__ = "import_unresolved"
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    csv_row = Column(Text, nullable=False)
    parsed_name = Column(String)
    parsed_team = Column(String)
    resolved_player_id = Column(Integer, ForeignKey("player.mfl_id"))
    resolution = Column(String)


class SourceColumnMapping(Base):
    __tablename__ = "source_column_mapping"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    position = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    mapping = Column(Text, nullable=False)
    updated_at = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("source", "position"),
        CheckConstraint("strategy IN ('by_name','by_index','fantasypros_multi_header')"),
    )


class LeagueConfig(Base):
    __tablename__ = "league_config"
    id = Column(Integer, primary_key=True, default=1)
    scoring_preset = Column(String, nullable=False)
    num_teams = Column(Integer, nullable=False, default=12)
    updated_at = Column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("id = 1"),
        CheckConstraint("scoring_preset IN ('standard','half_ppr','full_ppr')"),
    )


class PlayerDistributionParams(Base):
    __tablename__ = "player_distribution_params"
    player_id = Column(Integer, ForeignKey("player.mfl_id"), primary_key=True)
    params = Column(Text, nullable=False)  # JSON
    fitted_at = Column(String, nullable=False)
    historical_seasons = Column(String, nullable=False)
    games_used = Column(Integer, nullable=False)

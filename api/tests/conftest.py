"""Shared pytest fixtures."""
from __future__ import annotations
import json
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db import Base
from app.models.orm import Player


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def seeded_players(session: Session) -> list[Player]:
    """Small canonical table covering duplicates, retirees, and a team alias case."""
    now = datetime.utcnow().isoformat()
    players = [
        Player(mfl_id=1, gsis_id="00-0033873", name="Patrick Mahomes",
               merge_name="patrick mahomes", team="KCC", position="QB",
               fantasypros_id=16737, seeded_at=now),
        Player(mfl_id=2, gsis_id="00-0034796", name="Josh Allen",
               merge_name="josh allen", team="BUF", position="QB",
               seeded_at=now),
        Player(mfl_id=3, gsis_id="00-0035467", name="Josh Allen",
               merge_name="josh allen", team="JAX", position="LB",
               seeded_at=now),
        Player(mfl_id=4, gsis_id="00-0036264", name="CeeDee Lamb",
               merge_name="ceedee lamb", team="DAL", position="WR",
               fantasypros_id=21685, seeded_at=now),
        Player(mfl_id=5, gsis_id="00-0037000", name="Retired RB",
               merge_name="retired rb", team="FA", position="RB",
               seeded_at=now),
    ]
    session.add_all(players)
    session.commit()
    return players

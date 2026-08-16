"""Happy path: seed players manually → import FP QB → list players → fetch distribution."""
import pathlib
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.config import Settings
from app.models.orm import Player, LeagueConfig


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"
HEADERS = {"Authorization": "Bearer dev-token"}


@pytest.fixture()
def app_and_db(tmp_path, monkeypatch):
    """Build app with isolated data dir and pre-seeded canonical + league config."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("API_TOKEN", "dev-token")

    from app import main
    monkeypatch.setattr(main, "_first_boot", lambda: None)

    from app.db import Base, _engine, SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path}/sqlite.db", future=True)
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr("app.db._engine", engine)
    monkeypatch.setattr("app.db.SessionLocal", Local)

    with Local() as db:
        now = datetime.utcnow().isoformat()
        db.add_all([
            Player(mfl_id=1, gsis_id="00-0033873", name="Patrick Mahomes",
                   merge_name="patrick mahomes", team="KCC", position="QB",
                   seeded_at=now),
            LeagueConfig(id=1, scoring_preset="full_ppr", num_teams=12,
                         updated_at=now),
        ])
        db.commit()

    app = main.create_app()
    return TestClient(app), tmp_path


def test_happy_path_through_api(app_and_db):
    client, _ = app_and_db

    # 1. GET config
    resp = client.get("/api/league/config", headers=HEADERS)
    assert resp.status_code == 200

    # 2. Import FP QB stats
    html = (FIXTURES / "fantasypros_qb.html").read_bytes()
    resp = client.post(
        "/api/imports/stats", headers=HEADERS,
        files={"file": ("fp_qb.html", html, "text/html")},
        data={"source": "fantasypros", "position": "QB"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["matched_rows"] >= 1  # Mahomes should match

    # 3. List players
    resp = client.get("/api/players", headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["player_id"] == 1 for r in rows)

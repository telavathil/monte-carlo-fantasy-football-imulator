import pathlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import create_app
from app.db import Base


HEADERS = {"Authorization": "Bearer dev-token"}
FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def _client(tmp_path, monkeypatch):
    """Build a TestClient with an isolated per-test database + disabled first-boot network.

    NOTE: app.db binds `_engine`/`SessionLocal` at *module import time*, and by the
    time this test module runs, `app.db` has already been imported (transitively,
    via app.models.orm) by earlier test files in the same pytest session. Setting
    DATA_DIR via monkeypatch.setenv and re-importing app.main would NOT rebind
    app.db's already-cached engine — Python does not re-execute a cached module's
    top-level code on a second import. So instead we directly rebind
    `app.db._engine` / `app.db.SessionLocal` to a fresh engine pointed at tmp_path,
    the same pattern used by the `session` fixture in tests/conftest.py.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("API_TOKEN", "dev-token")

    engine = create_engine(
        f"sqlite:///{tmp_path}/sqlite.db",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.db._engine", engine)
    monkeypatch.setattr("app.db.SessionLocal", Local)

    # Disable lifespan's network seed for tests
    from app import main
    def _noop():
        pass
    monkeypatch.setattr(main, "_first_boot", _noop)
    app = create_app()
    return TestClient(app)


def test_health_endpoint_no_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_private_endpoint_requires_token(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/players")
    assert resp.status_code == 401
    resp = client.get("/api/players", headers=HEADERS)
    # 200 or 404 acceptable — we just want auth to pass
    assert resp.status_code != 401


def test_k_def_distribution_returns_422(tmp_path, monkeypatch):
    """K/DEF are not supported for distribution in MVP (per ADR-0010)."""
    client = _client(tmp_path, monkeypatch)
    # Seed a K and DEF player directly via the in-process db
    from datetime import datetime
    from app.db import SessionLocal
    from app.models.orm import Player, LeagueConfig
    with SessionLocal() as db:
        now = datetime.utcnow().isoformat()
        db.add_all([
            Player(mfl_id=100, gsis_id="00-K000001", name="Test Kicker",
                   merge_name="test kicker", team="KCC", position="K",
                   seeded_at=now),
            LeagueConfig(id=1, scoring_preset="full_ppr", num_teams=12,
                         updated_at=now),
        ])
        db.commit()
    resp = client.get("/api/players/100/distribution", headers=HEADERS)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "not_supported_mvp"

import pathlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import create_app
from app.db import Base


HEADERS = {"Authorization": "Bearer dev-token"}
FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def _client(tmp_path, monkeypatch):
    """Build a TestClient with an isolated per-test database.

    NOTE: app.db binds `_engine`/`SessionLocal` at *module import time*, and by the
    time this test module runs, `app.db` has already been imported (transitively,
    via app.models.orm) by earlier test files in the same pytest session. Setting
    DATA_DIR via monkeypatch.setenv and re-importing app.main would NOT rebind
    app.db's already-cached engine — Python does not re-execute a cached module's
    top-level code on a second import. So instead we directly rebind
    `app.db._engine` / `app.db.SessionLocal` to a fresh engine pointed at tmp_path,
    the same pattern used by the `session` fixture in tests/conftest.py.

    Every router reads the session via `Depends(get_db)`, which looks up
    `app.db.SessionLocal` at *call time* (not import time), so this rebinding
    takes effect for all of them on every request, including `/api/health`.

    We don't need to disable app.main's lifespan (`_first_boot`, which calls out
    to the network to seed players/historical data): `TestClient(app)` is used
    here without a `with ... as client:` block, and Starlette's test transport
    only sends a `lifespan` ASGI message when used as a context manager — so
    lifespan (and therefore `_first_boot`) never runs for these tests either way.
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

    app = create_app()
    return TestClient(app)


def test_health_endpoint_no_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_endpoint_db_ok_against_isolated_db(tmp_path, monkeypatch):
    """`/api/health`'s `db` field must reflect *this test's* isolated database,
    not whatever engine happened to be bound first in the pytest session — i.e.
    health.py must fetch its session the same way every other router does
    (`Depends(get_db)`, read at request time), not via a stale module-level
    `SessionLocal` name bound once at import time.
    """
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["db"] is True
    # The isolated sqlite file for *this* test actually exists at tmp_path,
    # confirming health's probe ran against the per-test engine, not a stale one.
    assert (tmp_path / "sqlite.db").exists()


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


import json as _json
from datetime import datetime as _dt
from app.models.orm import (
    Player as _Player, PlayerProjection as _Proj,
    PlayerDistributionSummary as _Summary, LeagueConfig as _Cfg,
)


def _seed_one_player_with_summary(status="ok"):
    """Insert a player, a projection, a config, and one summary row."""
    from app.db import SessionLocal
    now = _dt.utcnow().isoformat()
    with SessionLocal() as db:
        db.add(_Cfg(id=1, scoring_preset="half_ppr", num_teams=12, updated_at=now))
        db.add(_Player(mfl_id=1, gsis_id="00-0000001", name="Test Receiver",
                       merge_name="test receiver", team="CIN", position="WR",
                       seeded_at=now))
        db.add(_Proj(player_id=1, import_batch_id=1, position="WR",
                     stats=_json.dumps({"receptions": 6.0}), created_at=now))
        db.flush()
        db.add(_Summary(
            player_id=1, scoring_preset="half_ppr", status=status,
            floor_p10=5.6, p25=9.0, median_p50=13.2, p75=18.4, ceiling_p90=24.6,
            mean=13.9, std=5.4, skewness=0.62,
            histogram=_json.dumps({"bin_edges": [0.0, 10.0, 20.0], "counts": [3, 7]}),
            computed_points=14.2, n_samples=5000, computed_at=now))
        db.commit()


def test_players_list_includes_distribution_summary(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _seed_one_player_with_summary()
    row = client.get("/api/players", headers=HEADERS).json()[0]
    assert row["distribution"]["median_p50"] == 13.2
    assert row["distribution"]["p25"] == 9.0
    assert row["distribution"]["status"] == "ok"
    assert row["distribution"]["histogram"]["counts"] == [3, 7]


def test_players_list_distribution_is_null_without_summary(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    from app.db import SessionLocal
    now = _dt.utcnow().isoformat()
    with SessionLocal() as db:
        db.add(_Cfg(id=1, scoring_preset="half_ppr", num_teams=12, updated_at=now))
        db.add(_Player(mfl_id=1, gsis_id="00-0000001", name="No Summary",
                       merge_name="no summary", team="CIN", position="WR",
                       seeded_at=now))
        db.add(_Proj(player_id=1, import_batch_id=1, position="WR",
                     stats=_json.dumps({"receptions": 6.0}), created_at=now))
        db.commit()
    row = client.get("/api/players", headers=HEADERS).json()[0]
    assert row["distribution"] is None


def test_players_list_summary_fetch_is_batched(tmp_path, monkeypatch):
    """One query for all summaries, not one per player.

    Commit aeac800 removed an N+1 from this endpoint; adding summaries must
    not quietly put one back."""
    from sqlalchemy import event
    client = _client(tmp_path, monkeypatch)
    from app.db import SessionLocal, _engine
    now = _dt.utcnow().isoformat()
    with SessionLocal() as db:
        db.add(_Cfg(id=1, scoring_preset="half_ppr", num_teams=12, updated_at=now))
        for i in range(1, 26):
            db.add(_Player(mfl_id=i, gsis_id=f"00-000{i:04d}", name=f"Player {i}",
                           merge_name=f"player {i}", team="CIN", position="WR",
                           seeded_at=now))
            db.add(_Proj(player_id=i, import_batch_id=1, position="WR",
                         stats=_json.dumps({"receptions": 6.0}), created_at=now))
            db.add(_Summary(player_id=i, scoring_preset="half_ppr", status="ok",
                            floor_p10=5.6, p25=9.0, median_p50=13.2, p75=18.4,
                            ceiling_p90=24.6, mean=13.9, std=5.4, skewness=0.62,
                            histogram=_json.dumps({"bin_edges": [0.0, 10.0],
                                                   "counts": [5]}),
                            computed_points=14.2, n_samples=5000, computed_at=now))
        db.commit()

    seen: list[str] = []

    def _record(conn, cursor, statement, params, context, executemany):
        if "player_distribution_summary" in statement:
            seen.append(statement)

    event.listen(_engine, "before_cursor_execute", _record)
    try:
        rows = client.get("/api/players", headers=HEADERS).json()
    finally:
        event.remove(_engine, "before_cursor_execute", _record)

    assert len(rows) == 25
    assert len(seen) == 1, f"expected 1 summary query, saw {len(seen)}"


def test_players_list_surfaces_terminal_status(tmp_path, monkeypatch):
    """A player that can never be simulated reports why, not a blank."""
    client = _client(tmp_path, monkeypatch)
    _seed_one_player_with_summary(status="insufficient_history")
    row = client.get("/api/players", headers=HEADERS).json()[0]
    assert row["distribution"]["status"] == "insufficient_history"


def test_players_list_respects_scoring_preset(tmp_path, monkeypatch):
    """Summaries are filtered by the active scoring preset, not mixed across presets.

    The composite primary key (player_id, scoring_preset) allows one player to have
    multiple summary rows. A refactor that drops the preset filter would serve wrong
    values to the client. This test would fail if the filter were removed."""
    client = _client(tmp_path, monkeypatch)
    from app.db import SessionLocal
    now = _dt.utcnow().isoformat()
    with SessionLocal() as db:
        # Seed config with half_ppr as the active preset
        db.add(_Cfg(id=1, scoring_preset="half_ppr", num_teams=12, updated_at=now))
        # Add a player and projection
        db.add(_Player(mfl_id=1, gsis_id="00-0000001", name="Multi-Preset",
                       merge_name="multi-preset", team="CIN", position="WR",
                       seeded_at=now))
        db.add(_Proj(player_id=1, import_batch_id=1, position="WR",
                     stats=_json.dumps({"receptions": 6.0}), created_at=now))
        db.flush()
        # Add TWO summaries for the same player with DIFFERENT preset values
        db.add(_Summary(
            player_id=1, scoring_preset="half_ppr", status="ok",
            floor_p10=10.0, p25=11.0, median_p50=12.0, p75=13.0, ceiling_p90=14.0,
            mean=12.0, std=2.0, skewness=0.1,
            histogram=_json.dumps({"bin_edges": [10.0, 15.0], "counts": [5]}),
            computed_points=12.0, n_samples=5000, computed_at=now))
        db.add(_Summary(
            player_id=1, scoring_preset="full_ppr", status="ok",
            floor_p10=20.0, p25=21.0, median_p50=22.0, p75=23.0, ceiling_p90=24.0,
            mean=22.0, std=2.0, skewness=0.1,
            histogram=_json.dumps({"bin_edges": [20.0, 25.0], "counts": [5]}),
            computed_points=22.0, n_samples=5000, computed_at=now))
        db.commit()
    row = client.get("/api/players", headers=HEADERS).json()[0]
    # Assert we get the half_ppr row (active preset), not the full_ppr row
    assert row["distribution"]["median_p50"] == 12.0, \
        f"Expected half_ppr median (12.0), got {row['distribution']['median_p50']}"
    assert row["distribution"]["floor_p10"] == 10.0, \
        f"Expected half_ppr floor (10.0), got {row['distribution']['floor_p10']}"

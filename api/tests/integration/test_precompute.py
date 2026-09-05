import json
from datetime import datetime
import numpy as np
import polars as pl
import pytest
from app.models.orm import (
    Player, PlayerProjection, PlayerDistributionSummary, LeagueConfig,
)
from tests.integration.test_routers import HEADERS, _client


@pytest.fixture()
def stub_logs(monkeypatch):
    rng = np.random.default_rng(11)
    df = pl.DataFrame({
        "receptions": rng.integers(2, 9, 40).astype(float),
        "receiving_yards": rng.normal(70, 25, 40),
    })
    monkeypatch.setattr("app.sim.summary.game_logs", lambda *a, **k: df)


def _seed(n_players: int, position: str = "WR"):
    from app.db import SessionLocal
    now = datetime.utcnow().isoformat()
    with SessionLocal() as db:
        db.add(LeagueConfig(id=1, scoring_preset="half_ppr", num_teams=12,
                            updated_at=now))
        for i in range(1, n_players + 1):
            db.add(Player(mfl_id=i, gsis_id=f"00-000{i:04d}", name=f"Player {i}",
                          merge_name=f"player {i}", team="CIN", position=position,
                          seeded_at=now))
            db.add(PlayerProjection(
                player_id=i, import_batch_id=1, position=position,
                stats=json.dumps({"receptions": 6.0, "receiving_yards": 85.0}),
                created_at=now))
        db.commit()


def test_precompute_processes_one_chunk(tmp_path, monkeypatch, stub_logs):
    client = _client(tmp_path, monkeypatch)
    _seed(5)
    body = client.post("/api/players/precompute?limit=2", headers=HEADERS).json()
    assert body == {"computed": 2, "done": 2, "total": 5, "remaining": 3}


def test_precompute_is_resumable_to_completion(tmp_path, monkeypatch, stub_logs):
    """Looping until remaining == 0 must terminate."""
    client = _client(tmp_path, monkeypatch)
    _seed(5)
    guard = 0
    while True:
        body = client.post("/api/players/precompute?limit=2", headers=HEADERS).json()
        guard += 1
        assert guard < 10, "precompute failed to converge"
        if body["remaining"] == 0:
            break
    assert body["done"] == 5


def test_precompute_skips_already_computed(tmp_path, monkeypatch, stub_logs):
    client = _client(tmp_path, monkeypatch)
    _seed(3)
    client.post("/api/players/precompute?limit=3", headers=HEADERS)
    body = client.post("/api/players/precompute?limit=3", headers=HEADERS).json()
    assert body["computed"] == 0 and body["remaining"] == 0


def test_precompute_terminates_on_unsimulatable_players(tmp_path, monkeypatch, stub_logs):
    """K/DEF players get a terminal row instead of being retried forever."""
    client = _client(tmp_path, monkeypatch)
    _seed(2, position="K")
    body = client.post("/api/players/precompute?limit=10", headers=HEADERS).json()
    assert body["remaining"] == 0
    from app.db import SessionLocal
    with SessionLocal() as db:
        rows = db.query(PlayerDistributionSummary).all()
        assert {r.status for r in rows} == {"unsupported_position"}


def test_precompute_requires_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.post("/api/players/precompute").status_code == 401

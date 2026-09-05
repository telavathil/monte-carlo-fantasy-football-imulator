import json
from datetime import datetime
import numpy as np
import polars as pl
import pytest
from app.models.orm import (
    Player, PlayerProjection, PlayerDistributionSummary, LeagueConfig,
    PlayerDistributionParams,
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


def test_new_projection_invalidates_summary(tmp_path, monkeypatch, stub_logs):
    """Re-importing a projection must drop the stale summary."""
    client = _client(tmp_path, monkeypatch)
    _seed(1)
    client.post("/api/players/precompute?limit=1", headers=HEADERS)
    from app.db import SessionLocal
    from app.import_pipeline import stats_importer
    with SessionLocal() as db:
        assert db.query(PlayerDistributionSummary).count() == 1
        stats_importer.invalidate_caches_for(db, [1])
        db.commit()
        assert db.query(PlayerDistributionSummary).count() == 0


def test_historical_refresh_invalidates_every_summary(tmp_path, monkeypatch, stub_logs):
    client = _client(tmp_path, monkeypatch)
    _seed(3)
    client.post("/api/players/precompute?limit=3", headers=HEADERS)
    from app.db import SessionLocal
    from app.sim import summary as summary_mod
    with SessionLocal() as db:
        assert summary_mod.invalidate_all(db) == 3
        db.commit()
        assert db.query(PlayerDistributionSummary).count() == 0


def test_invalidate_caches_for_empty_list_is_noop(session):
    """The empty-list short-circuit must not raise or touch the DB."""
    from app.import_pipeline.stats_importer import invalidate_caches_for
    invalidate_caches_for(session, [])


def test_historical_refresh_endpoint_invalidates_summaries(tmp_path, monkeypatch, stub_logs):
    """POST /api/historical/refresh must invalidate every cached summary and
    param, not just the summary_mod functions in isolation."""
    client = _client(tmp_path, monkeypatch)
    _seed(2)
    client.post("/api/players/precompute?limit=2", headers=HEADERS)

    # ensure_seasons would otherwise try to fetch real historical data over
    # the network; the invalidation happens unconditionally after the call
    # regardless of what it does, so a no-op stub is correct here.
    monkeypatch.setattr("app.routers.historical.ensure_seasons", lambda *a, **k: None)

    from app.db import SessionLocal
    with SessionLocal() as db:
        assert db.query(PlayerDistributionSummary).count() == 2

    resp = client.post("/api/historical/refresh", json={}, headers=HEADERS)
    assert resp.status_code == 200

    with SessionLocal() as db:
        assert db.query(PlayerDistributionSummary).count() == 0
        assert db.query(PlayerDistributionParams).count() == 0


def test_admin_refresh_players_invalidates_promoted_players_summaries(tmp_path, monkeypatch, stub_logs):
    """A promotion through /api/admin/refresh-players must invalidate the
    promoted player's cached summary — this is the exact stale-identity bug
    class the MVP's original fix wave left open on this second path."""
    client = _client(tmp_path, monkeypatch)
    _seed(1)
    client.post("/api/players/precompute?limit=1", headers=HEADERS)

    from app.db import SessionLocal
    with SessionLocal() as db:
        assert db.query(PlayerDistributionSummary).count() == 1

        # seed_players would otherwise hit the network; refresh_players's
        # promotion logic doesn't depend on what it does here.
        # resolve is stubbed to force a successful promotion deterministically
        # rather than re-testing the identity resolver, which has its own suite.
        from app.models.orm import ImportBatch, ImportUnresolved
        import json as _json
        now = datetime.utcnow().isoformat()
        batch = ImportBatch(kind="stats", source="fantasypros", position="WR",
                            filename="x.csv", status="partial", total_rows=1,
                            matched_rows=0, unresolved_rows=1, created_at=now)
        db.add(batch)
        db.flush()
        db.add(ImportUnresolved(import_batch_id=batch.id,
                                csv_row=_json.dumps({"Player": "Ghost WR ARI"}),
                                parsed_name="Ghost WR", parsed_team="ARI"))
        db.commit()

    monkeypatch.setattr("app.routers.admin.seed_players", lambda db: None)
    monkeypatch.setattr("app.routers.admin.resolve", lambda db, csv_row, position: 1)

    resp = client.post("/api/admin/refresh-players", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["unresolved_promoted"] == 1

    with SessionLocal() as db:
        assert db.query(PlayerDistributionSummary).count() == 0

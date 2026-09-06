import json
from datetime import datetime
from app.models.orm import ImportBatch, ImportUnresolved
from tests.integration.test_routers import HEADERS, _client


def _seed_batch_with_unresolved(n: int = 2) -> int:
    from app.db import SessionLocal
    now = datetime.utcnow().isoformat()
    with SessionLocal() as db:
        batch = ImportBatch(kind="stats", source="fantasypros", position="RB",
                            filename="rb.csv", status="complete", total_rows=n,
                            matched_rows=0, unresolved_rows=n, created_at=now)
        db.add(batch)
        db.flush()
        for i in range(n):
            db.add(ImportUnresolved(
                import_batch_id=batch.id,
                csv_row=json.dumps({"Player": f"Ghost Player {i} ARI"}),
                parsed_name=f"Ghost Player {i}", parsed_team="ARI",
                resolution=None))
        db.commit()
        return batch.id


def test_unresolved_returns_rows_with_position_from_batch(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    batch_id = _seed_batch_with_unresolved(2)
    rows = client.get(f"/api/imports/{batch_id}/unresolved", headers=HEADERS).json()
    assert len(rows) == 2
    assert rows[0]["parsed_name"] == "Ghost Player 0"
    assert rows[0]["parsed_team"] == "ARI"
    assert rows[0]["position"] == "RB"


def test_unresolved_reports_a_reason(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    batch_id = _seed_batch_with_unresolved(1)
    rows = client.get(f"/api/imports/{batch_id}/unresolved", headers=HEADERS).json()
    assert rows[0]["resolution"] == "no_canonical_match"


def test_unresolved_unknown_batch_is_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/imports/9999/unresolved", headers=HEADERS)
    assert resp.status_code == 404


def test_unresolved_requires_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/imports/1/unresolved").status_code == 401

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.auth import require_token


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/private")
    def private(_: None = Depends(require_token)):
        return {"ok": True}

    return app


def test_auth_missing_token_returns_401():
    client = TestClient(_build_app())
    resp = client.get("/private")
    assert resp.status_code == 401


def test_auth_bad_token_returns_401(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "expected")
    client = TestClient(_build_app())
    resp = client.get("/private", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_auth_valid_token_returns_200(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "good")
    # Re-import to pick up env change
    from app.config import Settings
    from app import auth
    auth._settings_fn = Settings  # reload on each call
    client = TestClient(_build_app())
    resp = client.get("/private", headers={"Authorization": "Bearer good"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

"""Single bearer-token middleware per ADR-0007."""
from __future__ import annotations
import secrets
from fastapi import Header, HTTPException, status
from app.config import Settings


def _settings_fn() -> Settings:
    return Settings()


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = _settings_fn().api_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid token")

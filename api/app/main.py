"""FastAPI app factory."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db import Base, _engine, SessionLocal
from app.historical.fetch import ensure_seasons, seed_players
from app.models.orm import Player, LeagueConfig


log = logging.getLogger("uvicorn.error")


def _first_boot():
    """Apply migrations and seed if empty."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_engine)  # idempotent; alembic handles real migrations in Docker CMD

    with SessionLocal() as db:
        if db.query(Player).count() == 0:
            log.info("Seeding canonical player registry ...")
            seed_players(db)
        if db.query(LeagueConfig).count() == 0:
            db.add(LeagueConfig(id=1, scoring_preset="full_ppr",
                                num_teams=12,
                                updated_at=datetime.utcnow().isoformat()))
            db.commit()

    log.info("Ensuring historical seasons ...")
    ensure_seasons(settings.historical_seasons)
    log.info("First-boot complete.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _first_boot()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MC Fantasy Football Simulator API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from app.routers import (
        health, league, imports as imports_router,
        players, historical, admin,
    )
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(league.router, prefix="/api/league", tags=["league"])
    app.include_router(imports_router.router, prefix="/api/imports", tags=["imports"])
    app.include_router(players.router, prefix="/api/players", tags=["players"])
    app.include_router(historical.router, prefix="/api/historical", tags=["historical"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    return app


app = create_app()

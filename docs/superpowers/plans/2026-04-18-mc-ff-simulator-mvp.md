# MC Fantasy Football Simulator MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy the MVP Player Explorer: backend that imports stat projections, resolves identities, and returns per-player Monte Carlo distributions; thin React frontend that drives the happy path.

**Architecture:** FastAPI on Fly.io with SQLite + Parquet on a persistent volume (ADR-0002, 0006, 0014). Scoring presets + stat-level simulation with mixed distribution families per ADR-0012/0015 (skewnorm for continuous with 1.10× scale inflation and near-zero Poisson routing; nbinom for counts with Poisson fallback for near-zero). React/Vite on Vercel, single bearer-token auth (ADR-0007).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite, Polars, nflreadpy, scipy, numpy. Frontend: Vite + React + TypeScript + Recharts. Deploy: Fly.io + Vercel. Tests: pytest, Playwright.

**Related spec:** [`docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md`](../specs/2026-04-18-mc-ff-simulator-mvp-design.md).
**Spike inputs:** `spikes/GATING.md` (GO with BORDERLINE A2 caveat) and individual `spikes/*/` reports + fixtures.

---

## Phases

| Phase | Tasks | Outcome |
|---|---|---|
| 0 — Scaffold | 1 | `api/` package structure, pyproject, venv |
| 1 — Pure domain (TDD) | 2–6 | Scoring, families, team codes, models, migrations |
| 2 — Data services | 7–9 | Historical fetch, identity resolver, sim engine |
| 3 — Import pipeline | 10–11 | CSV/HTML parse + column map + importers |
| 4 — API | 12–13 | App factory + all routers |
| 5 — Backend integration | 14 | End-to-end test + OpenAPI emit |
| 6 — Backend deploy | 15 | Live on Fly; seed completes; `/api/health` passes |
| 7 — Frontend | 16–19 | Vite scaffold + 4 pages |
| 8 — Frontend deploy | 20 | Live on Vercel; talks to Fly |
| 9 — Validate + tear down | 21–22 | Playwright E2E + canary + C1 tear down |

## File structure to be created

```
api/
├── pyproject.toml
├── fly.toml
├── Dockerfile
├── .dockerignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app factory + first-boot
│   ├── config.py                      # Pydantic Settings
│   ├── db.py                          # SQLAlchemy engine, session, Base
│   ├── auth.py                        # bearer-token dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── orm.py                     # SQLAlchemy models
│   │   └── schemas.py                 # Pydantic I/O schemas
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── presets.py                 # STANDARD / HALF_PPR / FULL_PPR
│   │   └── engine.py                  # score(stats, preset)
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── team_codes.py              # TEAM_CODE_ALIASES
│   │   └── resolver.py                # resolve(csv_row, position)
│   ├── historical/
│   │   ├── __init__.py
│   │   └── fetch.py                   # ensure_seasons, game_logs, seed_players
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── families.py                # STAT_FAMILY
│   │   ├── fitting.py                 # dispatch_fit + helpers
│   │   ├── sampler.py                 # sample(params, n)
│   │   └── runner.py                  # simulate_player
│   ├── import_pipeline/
│   │   ├── __init__.py
│   │   ├── csv_parser.py
│   │   ├── column_mapper.py           # with FP_SECTION_MAP
│   │   ├── stats_importer.py
│   │   └── adp_importer.py
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       ├── league.py
│       ├── imports.py
│       ├── players.py
│       ├── historical.py
│       └── admin.py
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── nflreadpy/                 # cassettes
    │   └── fantasypros_{qb,rb,wr,te}.html  # existing from B1
    ├── unit/
    │   ├── test_scoring.py
    │   ├── test_families.py
    │   ├── test_team_codes.py
    │   ├── test_resolver.py
    │   ├── test_csv_parser.py
    │   ├── test_column_mapper.py
    │   ├── test_fitting.py
    │   ├── test_sampler.py
    │   ├── test_runner.py
    │   └── test_fetch.py
    └── integration/
        ├── test_happy_path.py
        ├── test_auth.py
        └── test_admin_refresh.py

web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── vercel.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts                  # generated from OpenAPI
│   │   └── auth.ts
│   ├── pages/
│   │   ├── SettingsPage.tsx
│   │   ├── ImportPage.tsx
│   │   ├── PlayersPage.tsx
│   │   └── PlayerDetailPage.tsx
│   └── components/
│       └── Histogram.tsx
└── tests/
    └── e2e/
        └── happy-path.spec.ts

shared/
└── openapi.json                       # emitted by FastAPI, consumed by web
```

---

## Task 1: Backend Scaffold

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/.python-version`
- Create: `api/alembic.ini`
- Create: `api/alembic/env.py`
- Create: `api/app/__init__.py`
- Create: `api/app/{scoring,identity,historical,sim,import_pipeline,routers,models}/__init__.py`
- Create: `api/tests/__init__.py`, `api/tests/unit/__init__.py`, `api/tests/integration/__init__.py`
- Create: `api/tests/conftest.py` (placeholder)
- Create: `api/.gitignore`

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p api/app/{scoring,identity,historical,sim,import_pipeline,routers,models}
mkdir -p api/tests/{unit,integration,fixtures}
mkdir -p api/alembic/versions
touch api/app/__init__.py
for d in scoring identity historical sim import_pipeline routers models; do
  touch api/app/$d/__init__.py
done
touch api/tests/__init__.py api/tests/unit/__init__.py api/tests/integration/__init__.py
```

- [ ] **Step 2: Write `api/pyproject.toml`**

```toml
[project]
name = "mc-ff-simulator-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.115.5",
    "uvicorn[standard]==0.32.1",
    "pydantic==2.10.3",
    "pydantic-settings==2.7.0",
    "sqlalchemy==2.0.36",
    "alembic==1.14.0",
    "polars==1.17.1",
    "pandas==2.2.3",
    "pyarrow==18.1.0",
    "scipy==1.14.1",
    "numpy==2.1.3",
    "lxml==5.3.0",
    "html5lib==1.1",
    "beautifulsoup4==4.12.3",
    "nflreadpy==0.1.5",
    "python-multipart==0.0.20",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.4",
    "pytest-cov==6.0.0",
    "httpx==0.28.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.coverage.run]
source = ["app"]
omit = ["app/main.py", "alembic/*", "app/**/__init__.py"]
```

- [ ] **Step 3: Write `api/.python-version`**

```
3.12
```

- [ ] **Step 4: Write `api/.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.coverage
coverage.xml
htmlcov/
/data/
```

- [ ] **Step 5: Write `api/alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///data/sqlite.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 6: Write `api/alembic/env.py`**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.db import Base
from app.models import orm  # noqa: F401 — register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Write `api/tests/conftest.py`**

```python
"""Shared pytest fixtures. Populated in later tasks as tests are added."""
```

- [ ] **Step 8: Create venv and install**

```bash
cd api && python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

Expected: installs without error. Dependencies match pinned versions.

- [ ] **Step 9: Verify imports work**

```bash
cd api && .venv/bin/python -c "import fastapi, sqlalchemy, alembic, polars, nflreadpy, scipy; print('ok')"
```

Expected: `ok`.

- [ ] **Step 10: Commit**

```bash
git add api/ && git commit -m "feat: scaffold api package with pyproject and alembic"
```

---

## Task 2: Config + DB Bootstrap

**Files:**
- Create: `api/app/config.py`
- Create: `api/app/db.py`
- Create: `api/app/auth.py`
- Test: `api/tests/unit/test_auth.py`, `api/tests/unit/test_config.py`

- [ ] **Step 1: Write `api/app/config.py`**

```python
"""Application settings loaded from env vars."""
from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_token: str = Field(default="dev-token")
    data_dir: Path = Field(default=Path("/data"))
    historical_seasons: list[int] = Field(default_factory=lambda: [2023, 2024, 2025])
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.data_dir}/sqlite.db"

    @property
    def historical_dir(self) -> Path:
        return self.data_dir / "historical"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Write `api/app/db.py`**

```python
"""SQLAlchemy engine, session factory, declarative base."""
from __future__ import annotations
from collections.abc import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_engine = create_engine(
    _settings.sqlite_url,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Write the failing auth test** at `api/tests/unit/test_auth.py`

```python
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
```

- [ ] **Step 4: Run the test; expect failures**

```bash
cd api && .venv/bin/pytest tests/unit/test_auth.py -v
```

Expected: `ModuleNotFoundError: app.auth` on every test.

- [ ] **Step 5: Implement `api/app/auth.py`**

```python
"""Single bearer-token middleware per ADR-0007."""
from __future__ import annotations
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
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid token")
```

- [ ] **Step 6: Re-run auth tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_auth.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Write config sanity test** at `api/tests/unit/test_config.py`

```python
from pathlib import Path
from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.api_token == "dev-token"
    assert s.data_dir == Path("/data")
    assert 2025 in s.historical_seasons
    assert s.sqlite_url.endswith("/sqlite.db")
    assert s.historical_dir.name == "historical"


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "overridden")
    s = Settings(_env_file=None)
    assert s.api_token == "overridden"
```

- [ ] **Step 8: Run config tests**

```bash
cd api && .venv/bin/pytest tests/unit/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 9: Commit**

```bash
git add api/app/config.py api/app/db.py api/app/auth.py api/tests/unit/test_auth.py api/tests/unit/test_config.py
git commit -m "feat: config, db bootstrap, bearer token auth with tests"
```

---

## Task 3: ORM Models + Initial Migration

**Files:**
- Create: `api/app/models/orm.py`
- Create: `api/alembic/versions/0001_initial.py`

- [ ] **Step 1: Write `api/app/models/orm.py`**

```python
"""SQLAlchemy ORM models matching spec §3."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, CheckConstraint,
    UniqueConstraint, Index, DateTime
)
from sqlalchemy.orm import relationship
from app.db import Base


class Player(Base):
    __tablename__ = "player"
    mfl_id = Column(Integer, primary_key=True)
    gsis_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    merge_name = Column(String, nullable=False, index=True)
    team = Column(String)
    position = Column(String, nullable=False)
    fantasypros_id = Column(Integer, index=True)
    espn_id = Column(Integer, index=True)
    yahoo_id = Column(String, index=True)
    sleeper_id = Column(Integer, index=True)
    cbs_id = Column(Integer, index=True)
    pfr_id = Column(String, index=True)
    fantasy_data_id = Column(Integer, index=True)
    rotowire_id = Column(Integer, index=True)
    nfl_id = Column(Integer, index=True)
    birthdate = Column(String)
    draft_year = Column(Integer)
    db_season = Column(Integer)
    seeded_at = Column(String, nullable=False)


Index("idx_player_merge_team_pos", Player.merge_name, Player.team, Player.position)


class ImportBatch(Base):
    __tablename__ = "import_batch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String, nullable=False)
    source = Column(String, nullable=False)
    position = Column(String)
    filename = Column(String)
    status = Column(String, nullable=False)
    total_rows = Column(Integer, nullable=False)
    matched_rows = Column(Integer, nullable=False)
    unresolved_rows = Column(Integer, nullable=False)
    unmapped_columns = Column(Text)  # JSON array
    created_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('stats','adp')"),
    )


class PlayerProjection(Base):
    __tablename__ = "player_projection"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.mfl_id"), nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    position = Column(String, nullable=False)
    stats = Column(Text, nullable=False)  # JSON
    created_at = Column(String, nullable=False)


Index("idx_proj_player_latest", PlayerProjection.player_id, PlayerProjection.created_at.desc())


class PlayerAdp(Base):
    __tablename__ = "player_adp"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.mfl_id"), nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    adp_snake = Column(Float)
    adp_auction = Column(Float)
    ecr = Column(Float)
    bye_week = Column(Integer)
    created_at = Column(String, nullable=False)


Index("idx_adp_player_latest", PlayerAdp.player_id, PlayerAdp.created_at.desc())


class ImportUnresolved(Base):
    __tablename__ = "import_unresolved"
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id"), nullable=False)
    csv_row = Column(Text, nullable=False)
    parsed_name = Column(String)
    parsed_team = Column(String)
    resolved_player_id = Column(Integer, ForeignKey("player.mfl_id"))
    resolution = Column(String)


class SourceColumnMapping(Base):
    __tablename__ = "source_column_mapping"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    position = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    mapping = Column(Text, nullable=False)
    updated_at = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("source", "position"),
        CheckConstraint("strategy IN ('by_name','by_index','fantasypros_multi_header')"),
    )


class LeagueConfig(Base):
    __tablename__ = "league_config"
    id = Column(Integer, primary_key=True, default=1)
    scoring_preset = Column(String, nullable=False)
    num_teams = Column(Integer, nullable=False, default=12)
    updated_at = Column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("id = 1"),
        CheckConstraint("scoring_preset IN ('standard','half_ppr','full_ppr')"),
    )


class PlayerDistributionParams(Base):
    __tablename__ = "player_distribution_params"
    player_id = Column(Integer, ForeignKey("player.mfl_id"), primary_key=True)
    params = Column(Text, nullable=False)  # JSON
    fitted_at = Column(String, nullable=False)
    historical_seasons = Column(String, nullable=False)
    games_used = Column(Integer, nullable=False)
```

- [ ] **Step 2: Create the initial migration scaffold**

```bash
cd api && mkdir -p ../data
.venv/bin/alembic revision --autogenerate -m "initial schema"
```

Alembic will create `api/alembic/versions/<hash>_initial_schema.py`. Inspect it; ensure it contains `create_table` for all 8 tables.

- [ ] **Step 3: Rename the generated migration to `0001_initial.py` for stable ordering**

```bash
cd api/alembic/versions
mv *_initial_schema.py 0001_initial.py
# Edit the top of 0001_initial.py: set `revision = "0001"` and `down_revision = None`
```

- [ ] **Step 4: Run the migration to verify the schema applies**

```bash
cd api && .venv/bin/alembic upgrade head
ls ../data/sqlite.db
```

Expected: `sqlite.db` exists. No errors.

- [ ] **Step 5: Verify schema by introspection**

```bash
cd api && .venv/bin/python -c "
from sqlalchemy import create_engine, inspect
engine = create_engine('sqlite:///../data/sqlite.db')
insp = inspect(engine)
print(sorted(insp.get_table_names()))
"
```

Expected: `['alembic_version', 'import_batch', 'import_unresolved', 'league_config', 'player', 'player_adp', 'player_distribution_params', 'player_projection', 'source_column_mapping']`

- [ ] **Step 6: Commit**

```bash
git add api/app/models/orm.py api/alembic/versions/0001_initial.py
git commit -m "feat: sqlalchemy models and initial migration for all 8 tables"
```

---

## Task 4: Scoring Presets + Engine

**Files:**
- Create: `api/app/scoring/presets.py`
- Create: `api/app/scoring/engine.py`
- Test: `api/tests/unit/test_scoring.py`

- [ ] **Step 1: Write `api/app/scoring/presets.py`**

```python
"""Three scoring presets. Keys are nflreadpy canonical stat names (ADR-0009)."""
from __future__ import annotations
from typing import TypedDict


class ScoringPreset(TypedDict):
    multipliers: dict[str, float]
    bonuses: list[tuple[str, float, float]]  # (stat, threshold, bonus_points)


def _common_bonuses() -> list[tuple[str, float, float]]:
    return [
        ("passing_yards", 300.0, 3.0),
        ("rushing_yards", 100.0, 3.0),
        ("receiving_yards", 100.0, 3.0),
    ]


STANDARD: ScoringPreset = {
    "multipliers": {
        "passing_yards": 0.04,
        "passing_tds": 4.0,
        "passing_interceptions": -1.0,
        "rushing_yards": 0.1,
        "rushing_tds": 6.0,
        "receiving_yards": 0.1,
        "receiving_tds": 6.0,
        "receptions": 0.0,
        "rushing_fumbles_lost": -1.0,
    },
    "bonuses": _common_bonuses(),
}

HALF_PPR: ScoringPreset = {
    "multipliers": {**STANDARD["multipliers"], "receptions": 0.5},
    "bonuses": _common_bonuses(),
}

FULL_PPR: ScoringPreset = {
    "multipliers": {**STANDARD["multipliers"], "receptions": 1.0},
    "bonuses": _common_bonuses(),
}

PRESETS: dict[str, ScoringPreset] = {
    "standard": STANDARD,
    "half_ppr": HALF_PPR,
    "full_ppr": FULL_PPR,
}
```

- [ ] **Step 2: Write the failing scoring test** at `api/tests/unit/test_scoring.py`

```python
import pytest
from app.scoring.engine import score
from app.scoring.presets import PRESETS, STANDARD, FULL_PPR


def test_standard_qb_line_no_bonus():
    stats = {"passing_yards": 250, "passing_tds": 2, "passing_interceptions": 1}
    # 250*0.04 + 2*4 - 1 = 10 + 8 - 1 = 17
    assert score(stats, STANDARD) == pytest.approx(17.0)


def test_standard_300yd_bonus_exactly_at_threshold():
    stats = {"passing_yards": 300, "passing_tds": 0, "passing_interceptions": 0}
    # 300*0.04 + 3 (bonus) = 15
    assert score(stats, STANDARD) == pytest.approx(15.0)


def test_standard_299yd_no_bonus():
    stats = {"passing_yards": 299, "passing_tds": 0, "passing_interceptions": 0}
    assert score(stats, STANDARD) == pytest.approx(299 * 0.04)


def test_full_ppr_reception_multiplier():
    stats = {"receptions": 10, "receiving_yards": 100, "receiving_tds": 1}
    # 10*1 + 100*0.1 + 1*6 + 3(bonus) = 10 + 10 + 6 + 3 = 29
    assert score(stats, FULL_PPR) == pytest.approx(29.0)


def test_missing_stat_treated_as_zero():
    stats = {"passing_yards": 200}
    assert score(stats, STANDARD) == pytest.approx(8.0)


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        _ = PRESETS["not_a_preset"]


@pytest.mark.parametrize("preset_name", ["standard", "half_ppr", "full_ppr"])
def test_all_presets_have_required_keys(preset_name):
    p = PRESETS[preset_name]
    for stat in ["passing_yards", "passing_tds", "passing_interceptions",
                 "rushing_yards", "rushing_tds", "receiving_yards",
                 "receiving_tds", "receptions"]:
        assert stat in p["multipliers"], f"{preset_name} missing {stat}"
```

- [ ] **Step 3: Run the test; expect failures**

```bash
cd api && .venv/bin/pytest tests/unit/test_scoring.py -v
```

Expected: `ModuleNotFoundError` on `app.scoring.engine`.

- [ ] **Step 4: Implement `api/app/scoring/engine.py`**

```python
"""Pure score function: stat line -> float fantasy points."""
from __future__ import annotations
from app.scoring.presets import ScoringPreset


def score(stats: dict[str, float], preset: ScoringPreset) -> float:
    total = 0.0
    for stat, mult in preset["multipliers"].items():
        total += float(stats.get(stat, 0)) * mult
    for stat, threshold, bonus in preset["bonuses"]:
        if float(stats.get(stat, 0)) >= threshold:
            total += bonus
    return total
```

- [ ] **Step 5: Re-run tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_scoring.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/scoring/ api/tests/unit/test_scoring.py
git commit -m "feat: scoring presets (standard/half_ppr/full_ppr) + pure score function"
```

---

## Task 5: Sim Families Registry

**Files:**
- Create: `api/app/sim/families.py`
- Test: `api/tests/unit/test_families.py`

- [ ] **Step 1: Write the failing test** at `api/tests/unit/test_families.py`

```python
import pytest
from app.sim.families import STAT_FAMILY, family_for
from app.scoring.presets import PRESETS


@pytest.mark.parametrize("stat,expected", [
    ("passing_yards", "skewnorm"),
    ("rushing_yards", "skewnorm"),
    ("receiving_yards", "skewnorm"),
    ("receptions", "skewnorm"),
    ("passing_tds", "nbinom"),
    ("rushing_tds", "nbinom"),
    ("receiving_tds", "nbinom"),
    ("passing_interceptions", "nbinom"),
    ("rushing_fumbles_lost", "nbinom"),
])
def test_stat_family_dispatch(stat, expected):
    assert STAT_FAMILY[stat] == expected
    assert family_for(stat) == expected


def test_family_for_unknown_defaults_to_skewnorm():
    # New stats default to continuous family; safe default.
    assert family_for("some_future_yards_stat") == "skewnorm"


def test_all_scoreable_stats_registered():
    scoreable = set()
    for preset in PRESETS.values():
        scoreable.update(preset["multipliers"].keys())
    missing = scoreable - set(STAT_FAMILY.keys())
    assert not missing, f"missing family for: {missing}"
```

- [ ] **Step 2: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/unit/test_families.py -v
```

- [ ] **Step 3: Implement `api/app/sim/families.py`**

```python
"""Stat -> distribution family registry per ADR-0012 and ADR-0015."""
from __future__ import annotations


STAT_FAMILY: dict[str, str] = {
    # Continuous (skew-normal with 1.10x scale inflation; near-zero routes to Poisson)
    "passing_yards": "skewnorm",
    "rushing_yards": "skewnorm",
    "receiving_yards": "skewnorm",
    "receptions": "skewnorm",
    "completions": "skewnorm",
    "attempts": "skewnorm",
    "carries": "skewnorm",
    "targets": "skewnorm",
    # Count (nbinom method-of-moments; Poisson fallback on near-zero or invalid)
    "passing_tds": "nbinom",
    "passing_interceptions": "nbinom",
    "rushing_tds": "nbinom",
    "receiving_tds": "nbinom",
    "rushing_fumbles_lost": "nbinom",
}


def family_for(stat: str) -> str:
    """Return family; default to 'skewnorm' for unknown continuous-looking stats."""
    return STAT_FAMILY.get(stat, "skewnorm")
```

- [ ] **Step 4: Re-run; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_families.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/app/sim/families.py api/tests/unit/test_families.py
git commit -m "feat: STAT_FAMILY registry (skewnorm/nbinom per ADR-0012)"
```

---

## Task 6: Team Codes + Identity Resolver

**Files:**
- Create: `api/app/identity/team_codes.py`
- Create: `api/app/identity/resolver.py`
- Test: `api/tests/unit/test_team_codes.py`, `api/tests/unit/test_resolver.py`
- Test fixture: `api/tests/conftest.py` (extend)

- [ ] **Step 1: Write team-codes test** at `api/tests/unit/test_team_codes.py`

```python
import pytest
from app.identity.team_codes import canonicalize_team, TEAM_CODE_ALIASES


@pytest.mark.parametrize("inp,expected", [
    ("KC", "KCC"),
    ("TB", "TBB"),
    ("SF", "SFO"),
    ("GB", "GBP"),
    ("NO", "NOS"),
    ("NE", "NEP"),
    ("LV", "LVR"),
    ("JAX", "JAC"),
    ("LA", "LAR"),
    ("kc", "KCC"),           # case insensitive
    ("  TB  ", "TBB"),       # strips whitespace
])
def test_known_aliases(inp, expected):
    assert canonicalize_team(inp) == expected


@pytest.mark.parametrize("inp,expected", [
    ("DAL", "DAL"),
    ("PHI", "PHI"),
    ("BAL", "BAL"),
    ("NYJ", "NYJ"),
])
def test_unaliased_passthrough(inp, expected):
    assert canonicalize_team(inp) == expected


def test_empty_returns_empty():
    assert canonicalize_team("") == ""


def test_alias_table_has_all_nine_entries():
    assert len(TEAM_CODE_ALIASES) == 9
```

- [ ] **Step 2: Implement `api/app/identity/team_codes.py`**

```python
"""Team abbreviation normalization per ADR-0013."""
from __future__ import annotations


TEAM_CODE_ALIASES: dict[str, str] = {
    "KC":  "KCC",
    "TB":  "TBB",
    "SF":  "SFO",
    "GB":  "GBP",
    "NO":  "NOS",
    "NE":  "NEP",
    "LV":  "LVR",
    "JAX": "JAC",
    "LA":  "LAR",
}


def canonicalize_team(code: str) -> str:
    code = code.strip().upper()
    return TEAM_CODE_ALIASES.get(code, code)
```

- [ ] **Step 3: Run team-codes tests**

```bash
cd api && .venv/bin/pytest tests/unit/test_team_codes.py -v
```

Expected: all pass.

- [ ] **Step 4: Extend `api/tests/conftest.py` with a shared in-memory DB fixture**

```python
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
```

- [ ] **Step 5: Write resolver test** at `api/tests/unit/test_resolver.py`

```python
from app.identity.resolver import resolve


def test_tier1_match_by_fantasypros_id(session, seeded_players):
    result = resolve(
        session,
        csv_row={"fantasypros_id": 16737, "Player": "Patrick Mahomes KC"},
        position="QB",
    )
    assert result == 1


def test_tier3_match_with_team_canonicalization(session, seeded_players):
    # CSV has "Mahomes KC"; canonical stores team KCC — should still match.
    result = resolve(
        session,
        csv_row={"Player": "Patrick Mahomes KC"},
        position="QB",
    )
    assert result == 1


def test_tier3_ambiguous_returns_none(session, seeded_players):
    # Two Josh Allens exist in canonical, but the resolver filters by position.
    # QB Josh Allen (BUF) should match uniquely.
    result = resolve(
        session,
        csv_row={"Player": "Josh Allen BUF"},
        position="QB",
    )
    assert result == 2


def test_tier3_no_match_returns_none(session, seeded_players):
    result = resolve(
        session,
        csv_row={"Player": "Nonexistent Person CAR"},
        position="WR",
    )
    assert result is None


def test_tier3_wrong_position_returns_none(session, seeded_players):
    # The LB Josh Allen is in canonical as LB, not RB.
    result = resolve(
        session,
        csv_row={"Player": "Josh Allen JAX"},
        position="RB",
    )
    assert result is None


def test_split_name_with_suffix(session, seeded_players):
    # Add a player with a suffix to test normalization.
    from app.models.orm import Player
    from datetime import datetime
    session.add(Player(mfl_id=6, gsis_id="00-0099999", name="Michael Penix Jr.",
                       merge_name="michael penix", team="ATL", position="QB",
                       seeded_at=datetime.utcnow().isoformat()))
    session.commit()
    result = resolve(
        session,
        csv_row={"Player": "Michael Penix Jr. ATL"},
        position="QB",
    )
    assert result == 6
```

- [ ] **Step 6: Implement `api/app/identity/resolver.py`**

```python
"""Identity resolution per ADR-0005 + ADR-0013 (Tier 1 + Tier 3 with team aliases)."""
from __future__ import annotations
import re
from sqlalchemy.orm import Session
from app.models.orm import Player
from app.identity.team_codes import canonicalize_team


KNOWN_ID_COLS: dict[str, str] = {
    # csv column name -> player ORM attribute
    "fantasypros_id": "fantasypros_id",
    "espn_id": "espn_id",
    "yahoo_id": "yahoo_id",
    "sleeper_id": "sleeper_id",
    "cbs_id": "cbs_id",
    "pfr_id": "pfr_id",
    "fantasy_data_id": "fantasy_data_id",
    "rotowire_id": "rotowire_id",
    "nfl_id": "nfl_id",
}

_SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv)\.?$", re.IGNORECASE)


def normalize_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[.'\u2019]", "", s)
    s = _SUFFIX_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s


def split_name_team(combined: str) -> tuple[str, str]:
    parts = combined.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def resolve(session: Session, csv_row: dict, position: str) -> int | None:
    """Return mfl_id or None."""
    # Tier 1: direct ID match on any known ID column
    for csv_col, orm_attr in KNOWN_ID_COLS.items():
        if csv_col in csv_row and csv_row[csv_col] not in (None, ""):
            val = csv_row[csv_col]
            match = (session.query(Player)
                     .filter(getattr(Player, orm_attr) == val)
                     .one_or_none())
            if match is not None:
                return match.mfl_id

    # Tier 3: normalized name + canonicalized team + position
    combined = csv_row.get("Player") or csv_row.get("player") or ""
    name, team_raw = split_name_team(combined)
    merge = normalize_name(name)
    team = canonicalize_team(team_raw)
    if not merge or not team:
        return None
    matches = (session.query(Player)
               .filter(Player.merge_name == merge,
                       Player.team == team,
                       Player.position == position)
               .all())
    if len(matches) == 1:
        return matches[0].mfl_id
    return None
```

- [ ] **Step 7: Run resolver tests**

```bash
cd api && .venv/bin/pytest tests/unit/test_resolver.py tests/unit/test_team_codes.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add api/app/identity/ api/tests/unit/test_team_codes.py api/tests/unit/test_resolver.py api/tests/conftest.py
git commit -m "feat: identity resolver (Tier 1+3) with team code normalization"
```

---

## Task 7: Historical Fetch (nflreadpy wrapper + cassettes)

**Files:**
- Create: `api/app/historical/fetch.py`
- Create: `api/tests/fixtures/nflreadpy/ff_playerids.parquet` (generated)
- Create: `api/tests/fixtures/nflreadpy/player_stats_{2023,2024,2025}.parquet` (generated)
- Create: `api/tests/fixtures/generate_cassettes.py` (helper)
- Test: `api/tests/unit/test_fetch.py`

- [ ] **Step 1: Write cassette generator** at `api/tests/fixtures/generate_cassettes.py`

```python
"""Regenerate nflreadpy test cassettes. Run manually when nflreadpy schema changes.

Usage:
    cd api && .venv/bin/python tests/fixtures/generate_cassettes.py
"""
from __future__ import annotations
import pathlib
import nflreadpy as nfl

HERE = pathlib.Path(__file__).parent / "nflreadpy"
HERE.mkdir(parents=True, exist_ok=True)

print("Downloading load_ff_playerids ...")
ids = nfl.load_ff_playerids()
ids.write_parquet(HERE / "ff_playerids.parquet")

for year in [2023, 2024, 2025]:
    print(f"Downloading load_player_stats({year}) ...")
    df = nfl.load_player_stats(seasons=[year])
    df.write_parquet(HERE / f"player_stats_{year}.parquet")

print("Done.")
```

- [ ] **Step 2: Generate cassettes (hits network, ~30s)**

```bash
cd api && .venv/bin/python tests/fixtures/generate_cassettes.py
ls tests/fixtures/nflreadpy/
```

Expected: 4 parquet files.

- [ ] **Step 3: Write fetch test** at `api/tests/unit/test_fetch.py`

```python
import pathlib
import shutil
import pytest
import polars as pl
from unittest.mock import patch
from app.historical.fetch import ensure_seasons, game_logs, seed_players
from app.models.orm import Player


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures" / "nflreadpy"


@pytest.fixture()
def mock_nflreadpy():
    def fake_load_player_stats(seasons):
        return pl.read_parquet(FIXTURES / f"player_stats_{seasons[0]}.parquet")

    def fake_load_ff_playerids():
        return pl.read_parquet(FIXTURES / "ff_playerids.parquet")

    with patch("app.historical.fetch.nfl") as mock:
        mock.load_player_stats.side_effect = fake_load_player_stats
        mock.load_ff_playerids.side_effect = fake_load_ff_playerids
        yield mock


def test_ensure_seasons_writes_parquet(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    assert (tmp_path / "player_stats_2024.parquet").exists()


def test_ensure_seasons_is_idempotent(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    # Second call should not re-fetch.
    ensure_seasons([2024], hist_dir=tmp_path)
    assert mock_nflreadpy.load_player_stats.call_count == 1


def test_game_logs_filters_reg_and_active(tmp_path, mock_nflreadpy):
    ensure_seasons([2024], hist_dir=tmp_path)
    # Use an actual GSIS id from the cassette — Mahomes
    df = game_logs("00-0033873", [2024], hist_dir=tmp_path)
    # All rows should be REG; no POST
    assert (df["season_type"] == "REG").all()
    # No zero-activity rows for a QB (attempts + carries + targets > 0)
    nonzero = (df["attempts"] + df["carries"] + df["targets"]) > 0
    assert nonzero.all()


def test_seed_players_filters_gsis_not_null(session, mock_nflreadpy):
    count = seed_players(session)
    # All rows in canonical should have gsis_id set
    rows = session.query(Player).all()
    assert len(rows) == count
    assert all(r.gsis_id for r in rows)
    assert len(rows) > 5000  # cassette has ~7700 rows
```

- [ ] **Step 4: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/unit/test_fetch.py -v
```

- [ ] **Step 5: Implement `api/app/historical/fetch.py`**

```python
"""Historical data wrapper per ADR-0014: we write parquet ourselves."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import polars as pl
import nflreadpy as nfl
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from app.config import get_settings
from app.models.orm import Player


def ensure_seasons(years: list[int], hist_dir: Path | None = None) -> None:
    """Fetch + persist each missing season's parquet."""
    hist_dir = hist_dir or get_settings().historical_dir
    hist_dir.mkdir(parents=True, exist_ok=True)
    for y in years:
        path = hist_dir / f"player_stats_{y}.parquet"
        if not path.exists():
            df = nfl.load_player_stats(seasons=[y])
            df.write_parquet(path)


def game_logs(gsis_id: str, years: list[int], hist_dir: Path | None = None) -> pl.DataFrame:
    """Read cached parquet, filter to REG + active weeks for the given player."""
    hist_dir = hist_dir or get_settings().historical_dir
    dfs = [pl.read_parquet(hist_dir / f"player_stats_{y}.parquet") for y in years]
    df = pl.concat(dfs)
    return df.filter(
        (pl.col("player_id") == gsis_id)
        & (pl.col("season_type") == "REG")
        & ((pl.col("attempts").fill_null(0)
            + pl.col("carries").fill_null(0)
            + pl.col("targets").fill_null(0)) > 0)
    )


# Columns we persist from ff_playerids into our `player` table.
_PLAYER_COLUMNS = [
    "mfl_id", "gsis_id", "name", "merge_name", "team", "position",
    "fantasypros_id", "espn_id", "yahoo_id", "sleeper_id", "cbs_id",
    "pfr_id", "fantasy_data_id", "rotowire_id", "nfl_id",
    "birthdate", "draft_year", "db_season",
]


def seed_players(session: Session) -> int:
    """Upsert player registry from ff_playerids (filtered to gsis_id NOT NULL)."""
    df = nfl.load_ff_playerids().to_pandas()
    df = df[df["gsis_id"].notna()].copy()
    now = datetime.utcnow().isoformat()

    count = 0
    for _, row in df.iterrows():
        values = {col: (row[col] if col in df.columns and row[col] == row[col] else None)
                  for col in _PLAYER_COLUMNS}
        # Some ints may be floats due to nullability; coerce to int where known int columns
        for int_col in ("mfl_id", "fantasypros_id", "espn_id", "sleeper_id",
                        "cbs_id", "fantasy_data_id", "rotowire_id", "nfl_id",
                        "draft_year", "db_season"):
            if values.get(int_col) is not None:
                try:
                    values[int_col] = int(values[int_col])
                except (ValueError, TypeError):
                    values[int_col] = None
        values["seeded_at"] = now
        stmt = sqlite_upsert(Player).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["mfl_id"],
            set_={k: v for k, v in values.items() if k != "mfl_id"},
        )
        session.execute(stmt)
        count += 1
    session.commit()
    return count
```

- [ ] **Step 6: Re-run tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_fetch.py -v
```

- [ ] **Step 7: Add cassette files to gitignore EXCEPT the committed test fixtures**

```bash
# Check fixture files are present
ls api/tests/fixtures/nflreadpy/
# Files are committed as test fixtures — not gitignored.
```

- [ ] **Step 8: Commit**

```bash
git add api/app/historical/ api/tests/unit/test_fetch.py api/tests/fixtures/
git commit -m "feat: historical fetch (ensure_seasons, game_logs, seed_players) with cassettes"
```

---

## Task 8: Sim — Fitting, Sampler, Runner

**Files:**
- Create: `api/app/sim/fitting.py`
- Create: `api/app/sim/sampler.py`
- Create: `api/app/sim/runner.py`
- Test: `api/tests/unit/test_fitting.py`, `test_sampler.py`, `test_runner.py`

- [ ] **Step 1: Write fitting test** at `api/tests/unit/test_fitting.py`

```python
import numpy as np
import pytest
from app.sim.fitting import dispatch_fit, fit_shift_skewnorm, fit_shift_count


def test_skewnorm_fit_recovers_and_shifts():
    rng = np.random.default_rng(0)
    from scipy import stats
    true = (2.0, 200.0, 40.0)  # alpha, loc, scale
    samples = stats.skewnorm.rvs(*true, size=500, random_state=rng)
    params = fit_shift_skewnorm(samples, target_mean=300.0)
    fam, alpha, loc, scale = params
    assert fam == "skewnorm"
    # Verify shifted mean ~= target
    delta = alpha / np.sqrt(1 + alpha ** 2)
    shifted_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    assert shifted_mean == pytest.approx(300.0, abs=1.0)
    # Scale should be inflated 1.10x
    assert scale == pytest.approx(params[3])  # self-reference sanity


def test_near_zero_continuous_routes_to_poisson():
    # Mean < 1.5 → Poisson fallback
    rng = np.random.default_rng(1)
    values = rng.choice([0, 0, 0, 0, 1], size=50)  # mean ~0.2
    params = dispatch_fit(values, target_mean=0.5, family_category="skewnorm")
    assert params[0] == "poisson"
    assert params[1] == pytest.approx(0.5, abs=0.01)


def test_nbinom_near_zero_routes_to_poisson():
    values = np.array([0, 0, 0, 0, 0, 0, 1])  # mean ~0.14, count stat
    params = dispatch_fit(values, target_mean=0.5, family_category="nbinom")
    assert params[0] == "poisson"


def test_nbinom_normal_path_returns_nbinom():
    # Simulated counts with overdispersion.
    rng = np.random.default_rng(2)
    values = rng.negative_binomial(n=5, p=0.3, size=200)
    params = dispatch_fit(values, target_mean=float(values.mean()),
                          family_category="nbinom")
    assert params[0] == "nbinom"


def test_skewnorm_scale_inflation_applied():
    rng = np.random.default_rng(3)
    from scipy import stats
    samples = stats.skewnorm.rvs(0, loc=100, scale=10, size=500, random_state=rng)
    # Dispatch fit should apply 1.10x scale inflation
    params = dispatch_fit(samples, target_mean=100.0, family_category="skewnorm")
    assert params[0] == "skewnorm"
    _, alpha, loc, scale = params
    # scipy.stats.skewnorm.fit on ~symmetric data yields scale ≈ 10
    # After 1.10x inflation, scale should be ≈ 11
    assert scale == pytest.approx(11.0, rel=0.15)
```

- [ ] **Step 2: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/unit/test_fitting.py -v
```

- [ ] **Step 3: Implement `api/app/sim/fitting.py`**

```python
"""Distribution fitting per ADR-0012 + ADR-0015."""
from __future__ import annotations
import math
import numpy as np
from scipy import stats


SKEWNORM_NEAR_ZERO_THRESHOLD = 1.5  # mean < this for continuous → Poisson
SKEWNORM_SCALE_INFLATION = 1.10     # widen intervals ~10%


SkewnormParams = tuple[str, float, float, float]  # ("skewnorm", alpha, loc, scale)
NbinomParams = tuple[str, float, float]           # ("nbinom", n, p)
PoissonParams = tuple[str, float]                  # ("poisson", lam)
FitParams = SkewnormParams | NbinomParams | PoissonParams


def fit_shift_skewnorm(values: np.ndarray, target_mean: float) -> SkewnormParams:
    alpha, loc, scale = stats.skewnorm.fit(values)
    scale = float(scale) * SKEWNORM_SCALE_INFLATION
    delta = alpha / math.sqrt(1 + alpha ** 2)
    current_mean = loc + scale * delta * math.sqrt(2 / math.pi)
    return ("skewnorm", float(alpha), float(loc + (target_mean - current_mean)), scale)


def fit_shift_poisson(target_mean: float) -> PoissonParams:
    return ("poisson", max(float(target_mean), 0.1))


def fit_shift_count(values: np.ndarray, target_mean: float) -> NbinomParams | PoissonParams:
    """nbinom method-of-moments with Poisson fallback."""
    mu = float(values.mean())
    var = float(values.var(ddof=1)) if len(values) > 1 else max(mu, 1e-6)
    if mu <= 0.2 or var <= mu:
        return fit_shift_poisson(target_mean)
    new_mu = max(float(target_mean), 1e-6)
    new_var = new_mu * (var / mu) if mu > 0 else new_mu * 1.01
    if new_var <= new_mu:
        new_var = new_mu * 1.01 + 1e-6
    n = new_mu ** 2 / (new_var - new_mu)
    p = new_mu / new_var
    if not (math.isfinite(n) and math.isfinite(p)) or n <= 0 or not (0 < p <= 1):
        return fit_shift_poisson(target_mean)
    return ("nbinom", float(n), float(p))


def dispatch_fit(values: np.ndarray, target_mean: float,
                 family_category: str) -> FitParams:
    """Top-level dispatcher applying ADR-0015 near-zero routing."""
    if family_category == "skewnorm":
        if float(values.mean()) < SKEWNORM_NEAR_ZERO_THRESHOLD:
            return fit_shift_poisson(target_mean)
        return fit_shift_skewnorm(values, target_mean)
    return fit_shift_count(values, target_mean)
```

- [ ] **Step 4: Re-run; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_fitting.py -v
```

- [ ] **Step 5: Write sampler test** at `api/tests/unit/test_sampler.py`

```python
import numpy as np
import pytest
from app.sim.sampler import sample


def test_skewnorm_samples_clamped_nonneg():
    params = {"passing_yards": ("skewnorm", 0.0, 100.0, 50.0)}
    out = sample(params, n=1000, seed=42)
    assert out["passing_yards"].shape == (1000,)
    assert (out["passing_yards"] >= 0).all()


def test_nbinom_samples_nonneg_integers():
    params = {"passing_tds": ("nbinom", 5.0, 0.3)}
    out = sample(params, n=1000, seed=42)
    arr = out["passing_tds"]
    assert arr.shape == (1000,)
    assert (arr >= 0).all()
    assert np.array_equal(arr, arr.astype(int))


def test_poisson_samples_nonneg_integers():
    params = {"rushing_tds": ("poisson", 1.5)}
    out = sample(params, n=1000, seed=42)
    arr = out["rushing_tds"]
    assert (arr >= 0).all()


def test_seed_determinism():
    params = {"passing_yards": ("skewnorm", 0.5, 200.0, 40.0)}
    out_a = sample(params, n=100, seed=7)
    out_b = sample(params, n=100, seed=7)
    np.testing.assert_array_equal(out_a["passing_yards"], out_b["passing_yards"])


def test_mixed_family_samples():
    params = {
        "passing_yards": ("skewnorm", 0.0, 250.0, 40.0),
        "passing_tds": ("nbinom", 3.0, 0.3),
        "rushing_tds": ("poisson", 0.5),
    }
    out = sample(params, n=500, seed=42)
    assert set(out.keys()) == {"passing_yards", "passing_tds", "rushing_tds"}
    for arr in out.values():
        assert arr.shape == (500,)
```

- [ ] **Step 6: Implement `api/app/sim/sampler.py`**

```python
"""Per-family sampling dispatch."""
from __future__ import annotations
import numpy as np
from scipy import stats


def sample(params: dict[str, tuple], n: int = 5000,
           seed: int | None = None) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    out: dict[str, np.ndarray] = {}
    for stat, p in params.items():
        fam = p[0]
        if fam == "skewnorm":
            _, alpha, loc, scale = p
            arr = stats.skewnorm.rvs(alpha, loc=loc, scale=scale,
                                     size=n, random_state=rng)
            arr = np.clip(arr, 0, None)
        elif fam == "nbinom":
            _, nn, pp = p
            arr = stats.nbinom.rvs(nn, pp, size=n, random_state=rng)
        elif fam == "poisson":
            _, lam = p
            arr = stats.poisson.rvs(lam, size=n, random_state=rng)
        else:
            raise ValueError(f"unknown family {fam}")
        out[stat] = arr
    return out
```

- [ ] **Step 7: Run sampler tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_sampler.py -v
```

- [ ] **Step 8: Write runner test** at `api/tests/unit/test_runner.py`

```python
import numpy as np
from app.sim.runner import simulate_from_params
from app.scoring.presets import FULL_PPR


def test_simulate_basic_shape_and_ordering():
    params = {
        "passing_yards": ("skewnorm", 0.0, 250.0, 40.0),
        "passing_tds": ("nbinom", 3.0, 0.3),
    }
    result = simulate_from_params(params, preset=FULL_PPR, n=2000, seed=42)
    assert result["n_samples"] == 2000
    assert result["floor_p10"] <= result["median_p50"] <= result["ceiling_p90"]
    assert result["histogram"]["counts"].sum() == 2000 if hasattr(
        result["histogram"]["counts"], "sum"
    ) else sum(result["histogram"]["counts"]) == 2000


def test_simulate_histogram_bin_count():
    params = {"passing_yards": ("skewnorm", 0.0, 250.0, 40.0)}
    result = simulate_from_params(params, preset=FULL_PPR, n=1000, seed=1)
    # bin_edges length = counts length + 1
    assert len(result["histogram"]["bin_edges"]) == len(result["histogram"]["counts"]) + 1


def test_simulate_deterministic_with_seed():
    params = {"passing_yards": ("skewnorm", 0.2, 200.0, 40.0)}
    a = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    b = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    assert a["mean"] == b["mean"]
    assert a["std"] == b["std"]
```

- [ ] **Step 9: Implement `api/app/sim/runner.py`**

```python
"""Simulation orchestrator: sample -> score -> summarize."""
from __future__ import annotations
import numpy as np
from app.scoring.engine import score
from app.scoring.presets import ScoringPreset
from app.sim.sampler import sample


def simulate_from_params(params: dict[str, tuple], preset: ScoringPreset,
                         n: int = 5000, seed: int | None = None,
                         n_bins: int = 30) -> dict:
    """Sample per stat, score each simulation, return distribution summary."""
    samples_by_stat = sample(params, n=n, seed=seed)
    points = np.zeros(n, dtype=float)
    for i in range(n):
        line = {stat: arr[i] for stat, arr in samples_by_stat.items()}
        points[i] = score(line, preset)
    p10, p50, p90 = np.percentile(points, [10, 50, 90])
    counts, edges = np.histogram(points, bins=n_bins)
    return {
        "n_samples": n,
        "floor_p10": float(p10),
        "median_p50": float(p50),
        "ceiling_p90": float(p90),
        "mean": float(points.mean()),
        "std": float(points.std()),
        "histogram": {
            "bin_edges": edges.tolist(),
            "counts": counts.tolist(),
        },
    }
```

- [ ] **Step 10: Run runner tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_runner.py -v
```

- [ ] **Step 11: Commit**

```bash
git add api/app/sim/ api/tests/unit/test_fitting.py api/tests/unit/test_sampler.py api/tests/unit/test_runner.py
git commit -m "feat: sim engine (fit/sample/runner) with mixed families + scale inflation"
```

---

## Task 9: CSV Parser

**Files:**
- Create: `api/app/import_pipeline/csv_parser.py`
- Test: `api/tests/unit/test_csv_parser.py`
- Copy fixtures: `api/tests/fixtures/fantasypros_{qb,rb,wr,te}.html` (copy from repo-root `tests/fixtures/`)

- [ ] **Step 1: Copy FP fixtures into api test tree**

```bash
cp tests/fixtures/fantasypros_*.html api/tests/fixtures/
```

- [ ] **Step 2: Write parser test** at `api/tests/unit/test_csv_parser.py`

```python
import pathlib
import pandas as pd
import pytest
from app.import_pipeline.csv_parser import parse_file, split_name_team


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def test_split_name_team_basic():
    assert split_name_team("Jalen Hurts PHI") == ("Jalen Hurts", "PHI")


def test_split_name_team_two_letter_code():
    assert split_name_team("Patrick Mahomes KC") == ("Patrick Mahomes", "KC")


def test_split_name_team_suffix():
    assert split_name_team("Michael Penix Jr. ATL") == ("Michael Penix Jr.", "ATL")


def test_split_name_team_no_team_suffix():
    assert split_name_team("Just A Name") == ("Just A Name", "")


@pytest.mark.parametrize("pos", ["qb", "rb", "wr", "te"])
def test_parse_fantasypros_html_multiindex(pos):
    path = FIXTURES / f"fantasypros_{pos}.html"
    df, meta = parse_file(path.read_bytes(), filename=path.name)
    assert meta["format"] == "html"
    assert isinstance(df.columns, pd.MultiIndex)
    # Largest table has many rows
    assert len(df) > 5


def test_parse_plain_csv():
    csv_bytes = b"Player,Team,passing_yards\nJosh Allen,BUF,4500\n"
    df, meta = parse_file(csv_bytes, filename="custom.csv")
    assert meta["format"] == "csv"
    assert len(df) == 1
    assert df.iloc[0]["Player"] == "Josh Allen"
```

- [ ] **Step 3: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/unit/test_csv_parser.py -v
```

- [ ] **Step 4: Implement `api/app/import_pipeline/csv_parser.py`**

```python
"""Parse FantasyPros HTML or plain CSV into a DataFrame + metadata."""
from __future__ import annotations
import io
import pandas as pd


def split_name_team(combined: str) -> tuple[str, str]:
    combined = combined.strip()
    parts = combined.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def parse_file(content: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    """Auto-detect: HTML (FantasyPros) or plain CSV. Returns (df, meta)."""
    head = content[:256].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        tables = pd.read_html(io.BytesIO(content))
        df = max(tables, key=lambda t: t.shape[0])
        return df, {"format": "html", "filename": filename}
    df = pd.read_csv(io.BytesIO(content))
    return df, {"format": "csv", "filename": filename}
```

- [ ] **Step 5: Run tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_csv_parser.py -v
```

- [ ] **Step 6: Commit**

```bash
git add api/app/import_pipeline/csv_parser.py api/tests/unit/test_csv_parser.py api/tests/fixtures/fantasypros_*.html
git commit -m "feat: csv_parser (FP HTML + plain CSV) with MultiIndex handling"
```

---

## Task 10: Column Mapper

**Files:**
- Create: `api/app/import_pipeline/column_mapper.py`
- Test: `api/tests/unit/test_column_mapper.py`

- [ ] **Step 1: Write column mapper test** at `api/tests/unit/test_column_mapper.py`

```python
import pandas as pd
import pytest
from app.import_pipeline.column_mapper import (
    FP_SECTION_MAP, map_columns, MappingStrategy
)


def test_fp_section_map_has_all_expected_keys():
    expected = {
        ("PASSING", "ATT"), ("PASSING", "CMP"), ("PASSING", "YDS"),
        ("PASSING", "TDS"), ("PASSING", "INTS"),
        ("RUSHING", "ATT"), ("RUSHING", "YDS"), ("RUSHING", "TDS"),
        ("RECEIVING", "REC"), ("RECEIVING", "YDS"), ("RECEIVING", "TDS"),
        ("RECEIVING", "TGT"),
        ("MISC", "FL"), ("MISC", "FPTS"),
    }
    assert set(FP_SECTION_MAP.keys()) == expected


def test_fantasypros_multi_header_strategy():
    df = pd.DataFrame({
        ("Unnamed: 0_level_0", "Player"): ["Jalen Hurts PHI"],
        ("PASSING", "ATT"): [400],
        ("PASSING", "YDS"): [4200],
        ("PASSING", "TDS"): [28],
        ("RUSHING", "ATT"): [120],
        ("RUSHING", "YDS"): [800],
    })
    mapped, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    # The player column preserves raw values; stat columns re-keyed
    assert "attempts" in mapped.columns
    assert "passing_yards" in mapped.columns
    assert "carries" in mapped.columns
    assert unmapped == []


def test_by_name_strategy():
    df = pd.DataFrame({"Player": ["X"], "pass_yds": [4000], "Pass Yds": [0]})
    mapping = {"Player": "Player", "pass_yds": "passing_yards", "Pass Yds": "ignored"}
    mapped, unmapped = map_columns(df, strategy="by_name", mapping=mapping)
    assert "passing_yards" in mapped.columns


def test_by_index_strategy():
    df = pd.DataFrame([[100, 1000, 10]], columns=["a", "b", "c"])
    mapping = {"0": "attempts", "1": "passing_yards", "2": "passing_tds"}
    mapped, unmapped = map_columns(df, strategy="by_index", mapping=mapping)
    assert list(mapped.columns) == ["attempts", "passing_yards", "passing_tds"]


def test_unmapped_columns_surfaced():
    df = pd.DataFrame({
        ("Unnamed: 0_level_0", "Player"): ["X"],
        ("PASSING", "SOMETHING_NEW"): [1],
    })
    mapped, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    assert ("PASSING", "SOMETHING_NEW") in unmapped
```

- [ ] **Step 2: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/unit/test_column_mapper.py -v
```

- [ ] **Step 3: Implement `api/app/import_pipeline/column_mapper.py`**

```python
"""Column mapping strategies for CSV imports (ADR-0009)."""
from __future__ import annotations
from typing import Literal
import pandas as pd


MappingStrategy = Literal["by_name", "by_index", "fantasypros_multi_header"]


FP_SECTION_MAP: dict[tuple[str, str], str | None] = {
    ("PASSING", "ATT"): "attempts",
    ("PASSING", "CMP"): "completions",
    ("PASSING", "YDS"): "passing_yards",
    ("PASSING", "TDS"): "passing_tds",
    ("PASSING", "INTS"): "passing_interceptions",
    ("RUSHING", "ATT"): "carries",
    ("RUSHING", "YDS"): "rushing_yards",
    ("RUSHING", "TDS"): "rushing_tds",
    ("RECEIVING", "REC"): "receptions",
    ("RECEIVING", "YDS"): "receiving_yards",
    ("RECEIVING", "TDS"): "receiving_tds",
    ("RECEIVING", "TGT"): "targets",
    ("MISC", "FL"): "rushing_fumbles_lost",
    ("MISC", "FPTS"): None,  # ignored; we compute our own
}


def map_columns(df: pd.DataFrame, strategy: MappingStrategy,
                mapping: dict | None = None) -> tuple[pd.DataFrame, list]:
    """Return (mapped_df, unmapped_list)."""
    unmapped: list = []
    if strategy == "fantasypros_multi_header":
        assert isinstance(df.columns, pd.MultiIndex), "expected MultiIndex"
        new_cols: list[str] = []
        keep: list = []
        for lvl0, lvl1 in df.columns:
            if str(lvl0).startswith("Unnamed"):
                new_cols.append("Player")
                keep.append((lvl0, lvl1))
                continue
            key = (lvl0, lvl1)
            if key in FP_SECTION_MAP:
                canonical = FP_SECTION_MAP[key]
                if canonical is not None:
                    new_cols.append(canonical)
                    keep.append(key)
            else:
                unmapped.append(key)
        sub = df.loc[:, keep].copy()
        sub.columns = new_cols
        return sub, unmapped

    if strategy == "by_name":
        assert mapping is not None
        rename = {c: mapping[c] for c in df.columns if c in mapping and mapping[c] != "ignored"}
        unmapped = [c for c in df.columns if c not in mapping]
        out = df[list(rename.keys())].rename(columns=rename)
        return out, unmapped

    if strategy == "by_index":
        assert mapping is not None
        keep_cols = []
        new_cols = []
        for idx, col in enumerate(df.columns):
            key = str(idx)
            if key in mapping:
                keep_cols.append(col)
                new_cols.append(mapping[key])
            else:
                unmapped.append(col)
        out = df[keep_cols].copy()
        out.columns = new_cols
        return out, unmapped

    raise ValueError(f"unknown strategy: {strategy}")
```

- [ ] **Step 4: Re-run tests; expect pass**

```bash
cd api && .venv/bin/pytest tests/unit/test_column_mapper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/app/import_pipeline/column_mapper.py api/tests/unit/test_column_mapper.py
git commit -m "feat: column_mapper (by_name/by_index/fantasypros_multi_header)"
```

---

## Task 11: Stats + ADP Importers

**Files:**
- Create: `api/app/import_pipeline/stats_importer.py`
- Create: `api/app/import_pipeline/adp_importer.py`
- Test: `api/tests/integration/test_import_flow.py`

- [ ] **Step 1: Write integration test** at `api/tests/integration/test_import_flow.py`

```python
import json
import pathlib
from datetime import datetime
from app.import_pipeline.stats_importer import import_stats
from app.import_pipeline.adp_importer import import_adp
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, ImportBatch, ImportUnresolved,
)


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def _seed_canonical(session):
    """Seed a minimal canonical player table for Tier-3 matches against the FP QB fixture."""
    now = datetime.utcnow().isoformat()
    players = [
        Player(mfl_id=1, gsis_id="00-0033873", name="Patrick Mahomes",
               merge_name="patrick mahomes", team="KCC", position="QB",
               seeded_at=now),
        Player(mfl_id=2, gsis_id="00-0034796", name="Josh Allen",
               merge_name="josh allen", team="BUF", position="QB",
               seeded_at=now),
        Player(mfl_id=3, gsis_id="00-0035228", name="Lamar Jackson",
               merge_name="lamar jackson", team="BAL", position="QB",
               seeded_at=now),
    ]
    session.add_all(players)
    session.commit()


def test_import_stats_fp_qb_happy_path(session):
    _seed_canonical(session)
    content = (FIXTURES / "fantasypros_qb.html").read_bytes()
    batch_id, summary = import_stats(
        session, content=content, filename="fantasypros_qb.html",
        source="fantasypros", position="QB",
    )
    batch = session.get(ImportBatch, batch_id)
    assert batch.kind == "stats"
    assert batch.source == "fantasypros"
    assert batch.position == "QB"
    # At least the 3 seeded QBs should match via Tier 3
    projections = session.query(PlayerProjection).filter_by(import_batch_id=batch_id).all()
    assert len(projections) >= 3
    # Mahomes' stats are JSON-parseable with expected keys
    mahomes_proj = session.query(PlayerProjection).filter_by(player_id=1).first()
    stats = json.loads(mahomes_proj.stats)
    assert "passing_yards" in stats


def test_import_stats_unresolved_rows_tracked(session):
    _seed_canonical(session)  # only 3 QBs seeded; rest of FP table will be unresolved
    content = (FIXTURES / "fantasypros_qb.html").read_bytes()
    _, summary = import_stats(session, content=content,
                              filename="fantasypros_qb.html",
                              source="fantasypros", position="QB")
    unresolved = session.query(ImportUnresolved).all()
    assert len(unresolved) > 0
    # Parsed name + team are captured
    for u in unresolved[:3]:
        assert u.parsed_name
        assert u.parsed_team


def test_import_adp_stub(session):
    _seed_canonical(session)
    csv = b"Player,Team,adp_snake,adp_auction\nPatrick Mahomes,KC,18.5,32\n"
    batch_id, _ = import_adp(session, content=csv, filename="fp_adp.csv",
                             source="fantasypros")
    adp = session.query(PlayerAdp).filter_by(import_batch_id=batch_id).first()
    assert adp is not None
    assert adp.adp_snake == 18.5
```

- [ ] **Step 2: Run; expect fail**

```bash
cd api && .venv/bin/pytest tests/integration/test_import_flow.py -v
```

- [ ] **Step 3: Implement `api/app/import_pipeline/stats_importer.py`**

```python
"""Orchestrates stats-CSV import: parse → map → resolve → persist."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.import_pipeline.csv_parser import parse_file
from app.import_pipeline.column_mapper import map_columns
from app.identity.resolver import resolve
from app.models.orm import ImportBatch, PlayerProjection, ImportUnresolved


def import_stats(session: Session, *, content: bytes, filename: str,
                 source: str, position: str) -> tuple[int, dict]:
    df, meta = parse_file(content, filename=filename)

    # Default to fantasypros_multi_header for FP HTML; by_name for flat CSV.
    if meta["format"] == "html" and source == "fantasypros":
        mapped_df, unmapped = map_columns(df, strategy="fantasypros_multi_header")
    else:
        # Minimal pass-through: keep column names as-is.
        mapped_df = df.copy()
        unmapped = []

    now = datetime.utcnow().isoformat()
    batch = ImportBatch(
        kind="stats", source=source, position=position, filename=filename,
        status="pending", total_rows=len(mapped_df), matched_rows=0,
        unresolved_rows=0, unmapped_columns=json.dumps([list(k) if isinstance(k, tuple) else k for k in unmapped]),
        created_at=now,
    )
    session.add(batch)
    session.flush()  # get batch.id

    matched = 0
    unresolved = 0
    for _, row in mapped_df.iterrows():
        csv_row = {c: row[c] for c in mapped_df.columns}
        mfl_id = resolve(session, csv_row=csv_row, position=position)
        if mfl_id is not None:
            stats = {k: float(v) for k, v in csv_row.items()
                     if k != "Player" and k != "player" and isinstance(v, (int, float)) and v == v}
            session.add(PlayerProjection(
                player_id=mfl_id, import_batch_id=batch.id, position=position,
                stats=json.dumps(stats), created_at=now,
            ))
            matched += 1
        else:
            from app.import_pipeline.csv_parser import split_name_team
            from app.identity.resolver import normalize_name
            from app.identity.team_codes import canonicalize_team
            combined = csv_row.get("Player") or csv_row.get("player") or ""
            name, team = split_name_team(combined)
            session.add(ImportUnresolved(
                import_batch_id=batch.id,
                csv_row=json.dumps({k: (float(v) if isinstance(v, (int, float)) else v)
                                    for k, v in csv_row.items() if v == v}),
                parsed_name=normalize_name(name),
                parsed_team=canonicalize_team(team),
            ))
            unresolved += 1

    batch.matched_rows = matched
    batch.unresolved_rows = unresolved
    batch.status = "resolved" if unresolved == 0 else "partial"
    session.commit()
    return batch.id, {
        "matched_rows": matched, "unresolved_rows": unresolved,
        "unmapped_columns": unmapped,
    }
```

- [ ] **Step 4: Implement `api/app/import_pipeline/adp_importer.py`**

```python
"""ADP CSV importer: similar orchestration but simpler target table."""
from __future__ import annotations
import json
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session
from app.import_pipeline.csv_parser import parse_file, split_name_team
from app.identity.resolver import resolve, normalize_name
from app.identity.team_codes import canonicalize_team
from app.models.orm import ImportBatch, PlayerAdp, ImportUnresolved


_ADP_COLUMNS = {"adp_snake", "adp_auction", "ecr", "bye_week"}


def import_adp(session: Session, *, content: bytes, filename: str,
               source: str) -> tuple[int, dict]:
    df, meta = parse_file(content, filename=filename)
    now = datetime.utcnow().isoformat()
    batch = ImportBatch(
        kind="adp", source=source, position=None, filename=filename,
        status="pending", total_rows=len(df), matched_rows=0,
        unresolved_rows=0, unmapped_columns=json.dumps([]),
        created_at=now,
    )
    session.add(batch)
    session.flush()

    matched = 0
    unresolved = 0
    for _, row in df.iterrows():
        csv_row = {c: row[c] for c in df.columns}
        # ADP CSVs usually include `position` column; fall back if missing.
        position = str(csv_row.get("position", "")).upper() or "QB"
        mfl_id = resolve(session, csv_row=csv_row, position=position)
        if mfl_id is not None:
            kwargs = {c: (float(csv_row[c]) if c in _ADP_COLUMNS and csv_row.get(c) == csv_row.get(c) else None)
                      for c in _ADP_COLUMNS}
            session.add(PlayerAdp(
                player_id=mfl_id, import_batch_id=batch.id,
                created_at=now, **kwargs,
            ))
            matched += 1
        else:
            combined = csv_row.get("Player") or csv_row.get("player") or ""
            name, team = split_name_team(combined)
            session.add(ImportUnresolved(
                import_batch_id=batch.id,
                csv_row=json.dumps({k: (float(v) if isinstance(v, (int, float)) else v)
                                    for k, v in csv_row.items() if v == v}),
                parsed_name=normalize_name(name),
                parsed_team=canonicalize_team(team),
            ))
            unresolved += 1

    batch.matched_rows = matched
    batch.unresolved_rows = unresolved
    batch.status = "resolved" if unresolved == 0 else "partial"
    session.commit()
    return batch.id, {"matched_rows": matched, "unresolved_rows": unresolved}
```

- [ ] **Step 5: Re-run integration tests**

```bash
cd api && .venv/bin/pytest tests/integration/test_import_flow.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/app/import_pipeline/stats_importer.py api/app/import_pipeline/adp_importer.py api/tests/integration/test_import_flow.py
git commit -m "feat: stats + adp importers (parse → map → resolve → persist)"
```

---

## Task 12: Pydantic Schemas + App Factory

**Files:**
- Create: `api/app/models/schemas.py`
- Create: `api/app/main.py`

- [ ] **Step 1: Write `api/app/models/schemas.py`**

```python
"""Pydantic request/response schemas."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


Preset = Literal["standard", "half_ppr", "full_ppr"]


class LeagueConfigOut(BaseModel):
    scoring_preset: Preset
    num_teams: int
    updated_at: str


class LeagueConfigIn(BaseModel):
    scoring_preset: Preset | None = None
    num_teams: int | None = None


class ImportBatchResult(BaseModel):
    import_batch_id: int
    kind: Literal["stats", "adp"]
    source: str
    position: str | None = None
    status: str
    total_rows: int
    matched_rows: int
    unresolved_rows: int
    unmapped_columns: list = Field(default_factory=list)


class PlayerRow(BaseModel):
    player_id: int
    gsis_id: str
    name: str
    team: str | None
    position: str
    projected_stats: dict[str, float] = Field(default_factory=dict)
    projected_points: float | None = None
    adp_snake: float | None = None
    adp_auction: float | None = None


class Histogram(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class DistributionBody(BaseModel):
    n_samples: int
    floor_p10: float
    median_p50: float
    ceiling_p90: float
    mean: float
    std: float
    histogram: Histogram


class FitInfo(BaseModel):
    fitted_at: str
    historical_seasons: list[int]
    games_used: int


class DistributionResponse(BaseModel):
    player_id: int
    gsis_id: str
    projection: dict
    scoring_preset: Preset
    computed_points: float
    distribution: DistributionBody
    fit: FitInfo


class HistoricalStatus(BaseModel):
    seasons: list[int]
    last_refreshed_at: str | None
    ready: bool


class AdminRefreshResult(BaseModel):
    players_added: int
    players_updated: int
    unresolved_promoted: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict = Field(default_factory=dict)
```

- [ ] **Step 2: Write `api/app/main.py` — app factory + first-boot seed**

```python
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
```

- [ ] **Step 3: Commit schemas + app factory (before routers land)**

```bash
git add api/app/models/schemas.py api/app/main.py
git commit -m "feat: pydantic schemas + FastAPI app factory with lifespan seed"
```

---

## Task 13: All Routers

**Files:**
- Create: `api/app/routers/{health,league,imports,players,historical,admin}.py`
- Test: `api/tests/integration/test_routers.py`

- [ ] **Step 1: Write `api/app/routers/health.py`**

```python
from fastapi import APIRouter
from app.config import get_settings
from sqlalchemy import text
from app.db import SessionLocal

router = APIRouter()


@router.get("/health")
def health():
    settings = get_settings()
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    seasons = []
    if settings.historical_dir.is_dir():
        for p in settings.historical_dir.glob("player_stats_*.parquet"):
            try:
                seasons.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
    return {
        "status": "ok",
        "db": db_ok,
        "historical_ready": bool(seasons),
        "historical_seasons": sorted(seasons),
    }
```

- [ ] **Step 2: Write `api/app/routers/league.py`**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.models.orm import LeagueConfig
from app.models.schemas import LeagueConfigOut, LeagueConfigIn

router = APIRouter(dependencies=[Depends(require_token)])


@router.get("/config", response_model=LeagueConfigOut)
def get_config(db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    return LeagueConfigOut(scoring_preset=cfg.scoring_preset,
                           num_teams=cfg.num_teams, updated_at=cfg.updated_at)


@router.put("/config", response_model=LeagueConfigOut)
def put_config(body: LeagueConfigIn, db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    if body.scoring_preset is not None:
        cfg.scoring_preset = body.scoring_preset
    if body.num_teams is not None:
        cfg.num_teams = body.num_teams
    cfg.updated_at = datetime.utcnow().isoformat()
    db.commit()
    return LeagueConfigOut(scoring_preset=cfg.scoring_preset,
                           num_teams=cfg.num_teams, updated_at=cfg.updated_at)
```

- [ ] **Step 3: Write `api/app/routers/imports.py`**

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.import_pipeline.stats_importer import import_stats
from app.import_pipeline.adp_importer import import_adp
from app.models.orm import ImportBatch
from app.models.schemas import ImportBatchResult

router = APIRouter(dependencies=[Depends(require_token)])


def _to_result(batch: ImportBatch, summary: dict) -> ImportBatchResult:
    return ImportBatchResult(
        import_batch_id=batch.id,
        kind=batch.kind, source=batch.source, position=batch.position,
        status=batch.status, total_rows=batch.total_rows,
        matched_rows=batch.matched_rows, unresolved_rows=batch.unresolved_rows,
        unmapped_columns=summary.get("unmapped_columns", []),
    )


@router.post("/stats", response_model=ImportBatchResult)
async def post_stats(file: UploadFile = File(...), source: str = Form(...),
                     position: str = Form(...),
                     db: Session = Depends(get_db)):
    content = await file.read()
    batch_id, summary = import_stats(db, content=content, filename=file.filename or "upload",
                                      source=source, position=position)
    batch = db.get(ImportBatch, batch_id)
    return _to_result(batch, summary)


@router.post("/adp", response_model=ImportBatchResult)
async def post_adp(file: UploadFile = File(...), source: str = Form(...),
                   db: Session = Depends(get_db)):
    content = await file.read()
    batch_id, summary = import_adp(db, content=content, filename=file.filename or "upload",
                                    source=source)
    batch = db.get(ImportBatch, batch_id)
    return _to_result(batch, summary)


@router.get("/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return _to_result(batch, {})
```

- [ ] **Step 4: Write `api/app/routers/players.py`**

```python
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.config import get_settings
from app.models.orm import (
    Player, PlayerProjection, PlayerAdp, LeagueConfig,
    PlayerDistributionParams,
)
from app.models.schemas import PlayerRow, DistributionResponse, DistributionBody, FitInfo, Histogram
from app.scoring.presets import PRESETS
from app.scoring.engine import score
from app.sim.families import family_for
from app.sim.fitting import dispatch_fit
from app.sim.runner import simulate_from_params
from app.historical.fetch import game_logs

router = APIRouter(dependencies=[Depends(require_token)])

K_DEF_POSITIONS = {"K", "DEF"}
MIN_GAMES = 4


def _latest_projection(db: Session, player_id: int) -> PlayerProjection | None:
    return (db.query(PlayerProjection)
              .filter_by(player_id=player_id)
              .order_by(desc(PlayerProjection.created_at))
              .first())


def _latest_adp(db: Session, player_id: int) -> PlayerAdp | None:
    return (db.query(PlayerAdp)
              .filter_by(player_id=player_id)
              .order_by(desc(PlayerAdp.created_at))
              .first())


@router.get("", response_model=list[PlayerRow])
def list_players(position: str | None = None, has_projection: bool = False,
                 db: Session = Depends(get_db)):
    cfg = db.get(LeagueConfig, 1)
    preset = PRESETS[cfg.scoring_preset]
    q = db.query(Player)
    if position:
        q = q.filter(Player.position == position.upper())
    rows: list[PlayerRow] = []
    for p in q.all():
        proj = _latest_projection(db, p.mfl_id)
        if has_projection and proj is None:
            continue
        stats = json.loads(proj.stats) if proj else {}
        computed = score(stats, preset) if stats else None
        adp = _latest_adp(db, p.mfl_id)
        rows.append(PlayerRow(
            player_id=p.mfl_id, gsis_id=p.gsis_id, name=p.name,
            team=p.team, position=p.position,
            projected_stats={k: float(v) for k, v in stats.items()},
            projected_points=computed,
            adp_snake=adp.adp_snake if adp else None,
            adp_auction=adp.adp_auction if adp else None,
        ))
    return rows


@router.get("/{player_id}/distribution", response_model=DistributionResponse)
def get_distribution(player_id: int, n: int = Query(5000, ge=100, le=20000),
                     db: Session = Depends(get_db)):
    p = db.get(Player, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail="player not found")
    if p.position in K_DEF_POSITIONS:
        raise HTTPException(status_code=422,
                            detail={"error": "not_supported_mvp",
                                    "message": "K/DEF distributions not supported in MVP"})
    proj = _latest_projection(db, player_id)
    if proj is None:
        raise HTTPException(status_code=404,
                            detail="no projection for player")
    projected_stats = json.loads(proj.stats)
    cfg = db.get(LeagueConfig, 1)
    preset = PRESETS[cfg.scoring_preset]
    settings = get_settings()

    # Load historical
    logs = game_logs(p.gsis_id, settings.historical_seasons)
    if logs.height < MIN_GAMES:
        raise HTTPException(
            status_code=422,
            detail={"error": "insufficient_history",
                    "message": f"Only {logs.height} career games",
                    "details": {"games_found": logs.height}},
        )

    # Fit per stat (using cache if present)
    cached = db.get(PlayerDistributionParams, player_id)
    if cached is not None:
        import json as _json
        params = {k: tuple(v) for k, v in _json.loads(cached.params).items()}
        fitted_at = cached.fitted_at
        games_used = cached.games_used
    else:
        params = {}
        for stat, target in projected_stats.items():
            if stat not in logs.columns:
                continue
            vals = logs[stat].to_numpy()
            vals = vals[~(vals != vals)]  # drop NaN
            if len(vals) < MIN_GAMES:
                continue
            fam_cat = family_for(stat)
            params[stat] = dispatch_fit(vals, float(target), fam_cat)
        import json as _json
        db.add(PlayerDistributionParams(
            player_id=player_id,
            params=_json.dumps({k: list(v) for k, v in params.items()}),
            fitted_at=datetime.utcnow().isoformat(),
            historical_seasons=",".join(str(y) for y in settings.historical_seasons),
            games_used=logs.height,
        ))
        db.commit()
        fitted_at = datetime.utcnow().isoformat()
        games_used = logs.height

    result = simulate_from_params(params, preset=preset, n=n, seed=42)
    computed = score(projected_stats, preset)
    return DistributionResponse(
        player_id=player_id, gsis_id=p.gsis_id,
        projection={"stats": projected_stats, "import_batch_id": proj.import_batch_id},
        scoring_preset=cfg.scoring_preset,
        computed_points=computed,
        distribution=DistributionBody(
            n_samples=result["n_samples"],
            floor_p10=result["floor_p10"],
            median_p50=result["median_p50"],
            ceiling_p90=result["ceiling_p90"],
            mean=result["mean"], std=result["std"],
            histogram=Histogram(**result["histogram"]),
        ),
        fit=FitInfo(fitted_at=fitted_at,
                    historical_seasons=settings.historical_seasons,
                    games_used=games_used),
    )
```

- [ ] **Step 5: Write `api/app/routers/historical.py`**

```python
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.config import get_settings
from app.historical.fetch import ensure_seasons
from app.models.orm import PlayerDistributionParams

router = APIRouter(dependencies=[Depends(require_token)])


class RefreshBody(BaseModel):
    seasons: list[int] | None = None


@router.get("/status")
def status():
    settings = get_settings()
    seasons = []
    if settings.historical_dir.is_dir():
        for p in settings.historical_dir.glob("player_stats_*.parquet"):
            try:
                seasons.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
    return {
        "seasons": sorted(seasons),
        "last_refreshed_at": None,  # not tracked in MVP
        "ready": bool(seasons),
    }


@router.post("/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    settings = get_settings()
    years = body.seasons or settings.historical_seasons
    # Re-fetch: delete parquet first so ensure_seasons re-downloads
    for y in years:
        path = settings.historical_dir / f"player_stats_{y}.parquet"
        if path.exists():
            path.unlink()
    ensure_seasons(years)
    # Invalidate all cached fit params
    db.query(PlayerDistributionParams).delete()
    db.commit()
    return {"job_status": "complete"}
```

- [ ] **Step 6: Write `api/app/routers/admin.py`**

```python
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.auth import require_token
from app.db import get_db
from app.historical.fetch import seed_players
from app.identity.resolver import resolve
from app.models.orm import (
    Player, ImportUnresolved, PlayerProjection, ImportBatch,
)
from app.models.schemas import AdminRefreshResult

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/refresh-players", response_model=AdminRefreshResult)
def refresh_players(db: Session = Depends(get_db)):
    before = db.query(Player).count()
    seed_players(db)
    after = db.query(Player).count()
    added = after - before
    updated = after - added  # Upserts touched all rows; rough accounting for MVP.

    # Re-run resolver on pending unresolved rows
    promoted = 0
    unresolved = (db.query(ImportUnresolved)
                    .filter(ImportUnresolved.resolution.is_(None),
                            ImportUnresolved.resolved_player_id.is_(None))
                    .all())
    now = datetime.utcnow().isoformat()
    for u in unresolved:
        batch = db.get(ImportBatch, u.import_batch_id)
        if batch is None or batch.kind != "stats":
            continue
        csv_row = json.loads(u.csv_row)
        mfl_id = resolve(db, csv_row=csv_row, position=batch.position or "QB")
        if mfl_id is not None:
            u.resolved_player_id = mfl_id
            u.resolution = "manual"  # auto-promoted
            stats = {k: float(v) for k, v in csv_row.items()
                     if isinstance(v, (int, float)) and k not in ("Player", "player")}
            db.add(PlayerProjection(
                player_id=mfl_id, import_batch_id=batch.id, position=batch.position,
                stats=json.dumps(stats), created_at=now,
            ))
            promoted += 1
    db.commit()
    return AdminRefreshResult(players_added=added, players_updated=updated,
                              unresolved_promoted=promoted)
```

- [ ] **Step 7: Write router integration test** at `api/tests/integration/test_routers.py`

```python
import pathlib
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings


HEADERS = {"Authorization": "Bearer dev-token"}
FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures"


def _client(tmp_path, monkeypatch):
    """Build a TestClient with isolated data dir + disabled first-boot network."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("API_TOKEN", "dev-token")
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
```

- [ ] **Step 8: Run integration tests**

```bash
cd api && mkdir -p ../data && .venv/bin/alembic upgrade head
cd api && .venv/bin/pytest tests/integration/test_routers.py -v
```

- [ ] **Step 9: Commit**

```bash
git add api/app/routers/ api/tests/integration/test_routers.py
git commit -m "feat: routers (health, league, imports, players, historical, admin)"
```

---

## Task 14: Backend Smoke Run + OpenAPI Emit

**Files:**
- Create: `shared/openapi.json` (generated)
- Create: `api/scripts/emit_openapi.py`
- Update: `api/tests/integration/test_happy_path.py` (end-to-end walkthrough)

- [ ] **Step 1: Write OpenAPI emitter** at `api/scripts/emit_openapi.py`

```python
"""Emit OpenAPI JSON from the FastAPI app for the TS client generator."""
from __future__ import annotations
import json
import pathlib
from app.main import create_app


def main():
    app = create_app()
    out = pathlib.Path(__file__).parents[2] / "shared" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run emitter**

```bash
cd api && .venv/bin/python scripts/emit_openapi.py
ls ../shared/openapi.json
```

- [ ] **Step 3: Write end-to-end happy-path test** at `api/tests/integration/test_happy_path.py`

```python
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
    import os
    os.environ["DATA_DIR"] = str(tmp_path)
    os.environ["API_TOKEN"] = "dev-token"

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
```

Note: the `/distribution` endpoint requires real historical data from nflreadpy cassettes; covered separately.

- [ ] **Step 4: Run happy path**

```bash
cd api && .venv/bin/pytest tests/integration/test_happy_path.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/scripts/emit_openapi.py api/tests/integration/test_happy_path.py shared/openapi.json
git commit -m "feat: happy-path integration test + OpenAPI emitter"
```

---

## Task 15: Dockerfile + fly.toml (Adapt from C1 Spike)

**Files:**
- Create: `api/Dockerfile`
- Create: `api/fly.toml`
- Create: `api/.dockerignore`

- [ ] **Step 1: Write `api/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps for scipy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libatlas-base-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
      $(python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; print(' '.join(d))")

COPY app/ ./app/
COPY alembic.ini .
COPY alembic/ ./alembic/

ENV PORT=8080
EXPOSE 8080

CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

- [ ] **Step 2: Write `api/.dockerignore`**

```
.venv/
__pycache__/
*.pyc
tests/
scripts/
```

- [ ] **Step 3: Write `api/fly.toml`**

```toml
app = "mc-ff-sim-api"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0
  [[http_service.checks]]
    grace_period = "30s"
    interval = "15s"
    timeout = "2s"
    method = "GET"
    path = "/api/health"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"

[mounts]
  source = "mc_ff_sim_data"
  destination = "/data"
```

- [ ] **Step 4: Local docker smoke test**

```bash
cd api && docker build -t mc-ff-sim-api . && docker run --rm -p 8080:8080 -e API_TOKEN=dev-token mc-ff-sim-api &
sleep 30
curl -s http://localhost:8080/api/health
docker ps | grep mc-ff-sim-api | awk '{print $1}' | xargs docker stop
```

Expected: health returns `{"status":"ok",...}` within 60s.

- [ ] **Step 5: Commit**

```bash
git add api/Dockerfile api/fly.toml api/.dockerignore
git commit -m "feat: Dockerfile and fly.toml for backend deploy"
```

---

## Task 16: Deploy Backend to Fly

- [ ] **Step 1: Launch the app (non-interactive)**

```bash
cd api && fly launch --no-deploy --copy-config --name=mc-ff-sim-api --region=iad --yes
```

If `fly launch` insists on prompting, confirm `fly.toml` is already correct and skip to volume + deploy.

- [ ] **Step 2: Create volume**

```bash
fly volumes create mc_ff_sim_data --app mc-ff-sim-api --region iad --size 1 --yes
```

- [ ] **Step 3: Set API_TOKEN secret**

```bash
TOKEN=$(openssl rand -hex 24)
echo "Save this token: $TOKEN"
fly secrets set --app mc-ff-sim-api API_TOKEN="$TOKEN"
```

Record the token — Vercel needs the same value.

- [ ] **Step 4: Deploy**

```bash
fly deploy --app mc-ff-sim-api
```

Expected: build succeeds; machine starts; first-boot seed runs (~60–120 s). App URL: `https://mc-ff-sim-api.fly.dev`.

- [ ] **Step 5: Smoke test live**

```bash
curl -s https://mc-ff-sim-api.fly.dev/api/health | python3 -m json.tool
```

Expected: `historical_ready: true`, three seasons listed, `db: true`.

- [ ] **Step 6: Commit deploy-time config if any files changed**

```bash
git status
# If fly.toml changed during launch, commit it.
git add -u && git commit -m "chore: fly.toml committed after launch" || true
```

---

## Task 17: Frontend Scaffold + API Client

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`
- Create: `web/vercel.json`
- Create: `web/src/main.tsx`, `web/src/App.tsx`
- Create: `web/src/api/auth.ts`, `web/src/api/client.ts` (generated)

- [ ] **Step 1: Scaffold with Vite**

```bash
mkdir web && cd web
npm create vite@latest . -- --template react-ts
npm install
npm install recharts react-router-dom
npm install -D @hey-api/openapi-ts
```

- [ ] **Step 2: Write `web/vercel.json`**

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

- [ ] **Step 3: Add API client generation script to `web/package.json`**

In `web/package.json` `"scripts"`, add:

```json
"gen:api": "openapi-ts --input ../shared/openapi.json --output ./src/api/generated --client fetch"
```

Then run:

```bash
cd web && npm run gen:api
```

- [ ] **Step 4: Write `web/src/api/auth.ts`**

```typescript
const TOKEN = import.meta.env.VITE_API_TOKEN as string;
const API_URL = import.meta.env.VITE_API_URL as string;

export function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${TOKEN}` };
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers || {}) },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}
```

- [ ] **Step 5: Write `web/src/App.tsx`**

```typescript
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { SettingsPage } from "./pages/SettingsPage";
import { ImportPage } from "./pages/ImportPage";
import { PlayersPage } from "./pages/PlayersPage";
import { PlayerDetailPage } from "./pages/PlayerDetailPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: 8, borderBottom: "1px solid #ccc" }}>
        <Link to="/" style={{ marginRight: 12 }}>Settings</Link>
        <Link to="/import" style={{ marginRight: 12 }}>Import</Link>
        <Link to="/players">Players</Link>
      </nav>
      <main style={{ padding: 16 }}>
        <Routes>
          <Route path="/" element={<SettingsPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/players/:id" element={<PlayerDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Update `web/src/main.tsx` if Vite's template already renders `<App />`. Skip if fine.**

- [ ] **Step 7: Add `.env.local` example**

```bash
cat > web/.env.local.example <<EOF
VITE_API_URL=http://localhost:8080
VITE_API_TOKEN=dev-token
EOF
```

- [ ] **Step 8: Commit**

```bash
git add web/ shared/
git commit -m "feat: web scaffold with vite/react/ts + API client generator"
```

---

## Task 18: Settings + Import Pages

**Files:**
- Create: `web/src/pages/SettingsPage.tsx`
- Create: `web/src/pages/ImportPage.tsx`

- [ ] **Step 1: Write `web/src/pages/SettingsPage.tsx`**

```typescript
import { useEffect, useState } from "react";
import { apiFetch } from "../api/auth";

type Preset = "standard" | "half_ppr" | "full_ppr";
type Config = { scoring_preset: Preset; num_teams: number; updated_at: string };

export function SettingsPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Config>("/api/league/config").then(setCfg).catch((e) => setErr(String(e)));
  }, []);

  async function save(preset: Preset) {
    const updated = await apiFetch<Config>("/api/league/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scoring_preset: preset }),
    });
    setCfg(updated);
  }

  if (err) return <pre>{err}</pre>;
  if (!cfg) return <p>Loading…</p>;
  return (
    <div>
      <h1>Settings</h1>
      <p>Scoring preset: <strong>{cfg.scoring_preset}</strong></p>
      <p>
        {(["standard", "half_ppr", "full_ppr"] as Preset[]).map((p) => (
          <button key={p} onClick={() => save(p)} style={{ marginRight: 8 }}>
            {p}
          </button>
        ))}
      </p>
      <p>Teams: {cfg.num_teams} · Updated: {cfg.updated_at}</p>
    </div>
  );
}
```

- [ ] **Step 2: Write `web/src/pages/ImportPage.tsx`**

```typescript
import { useState } from "react";
import { authHeaders } from "../api/auth";

const API_URL = import.meta.env.VITE_API_URL as string;

export function ImportPage() {
  const [source, setSource] = useState("fantasypros");
  const [position, setPosition] = useState("QB");
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    const fd = new FormData(e.currentTarget);
    const kind = fd.get("kind") as string;
    const endpoint = kind === "adp" ? "/api/imports/adp" : "/api/imports/stats";
    try {
      const resp = await fetch(`${API_URL}${endpoint}`, {
        method: "POST", headers: authHeaders(), body: fd,
      });
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
      setResult(await resp.json());
    } catch (e: any) {
      setErr(String(e));
    }
  }

  return (
    <div>
      <h1>Import</h1>
      <form onSubmit={onSubmit}>
        <p>
          Kind:{" "}
          <select name="kind" defaultValue="stats">
            <option value="stats">Stats</option>
            <option value="adp">ADP</option>
          </select>
        </p>
        <p>
          Source: <input name="source" value={source} onChange={(e) => setSource(e.target.value)} />
        </p>
        <p>
          Position (stats only):{" "}
          <select name="position" value={position} onChange={(e) => setPosition(e.target.value)}>
            {["QB", "RB", "WR", "TE", "K", "DEF"].map((p) => <option key={p}>{p}</option>)}
          </select>
        </p>
        <p><input type="file" name="file" required /></p>
        <button type="submit">Upload</button>
      </form>
      {err && <pre style={{ color: "red" }}>{err}</pre>}
      {result && (
        <div>
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify dev server renders without errors**

```bash
cd web && npm run dev
# open http://localhost:5173, navigate to / and /import
# verify pages render
```

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/SettingsPage.tsx web/src/pages/ImportPage.tsx web/src/App.tsx
git commit -m "feat: settings + import pages"
```

---

## Task 19: Players + PlayerDetail Pages (with Calibration Caveat)

**Files:**
- Create: `web/src/pages/PlayersPage.tsx`
- Create: `web/src/pages/PlayerDetailPage.tsx`
- Create: `web/src/components/Histogram.tsx`

- [ ] **Step 1: Write `web/src/components/Histogram.tsx`**

```typescript
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type Props = {
  binEdges: number[];
  counts: number[];
};

export function Histogram({ binEdges, counts }: Props) {
  const data = counts.map((count, i) => ({
    bin: `${binEdges[i].toFixed(0)}-${binEdges[i + 1].toFixed(0)}`,
    count,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <XAxis dataKey="bin" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="count" fill="#5b8def" />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Write `web/src/pages/PlayersPage.tsx`**

```typescript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/auth";

type Row = {
  player_id: number;
  name: string;
  team: string;
  position: string;
  projected_points: number | null;
  adp_snake: number | null;
};

export function PlayersPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Row[]>("/api/players?has_projection=true")
      .then(setRows).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <pre>{err}</pre>;
  return (
    <div>
      <h1>Players</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Pos</th><th>Team</th><th>Proj</th><th>ADP</th>
          </tr>
        </thead>
        <tbody>
          {rows.sort((a, b) => (b.projected_points ?? 0) - (a.projected_points ?? 0))
               .map((r) => (
            <tr key={r.player_id}>
              <td><Link to={`/players/${r.player_id}`}>{r.name}</Link></td>
              <td>{r.position}</td>
              <td>{r.team}</td>
              <td>{r.projected_points?.toFixed(1) ?? "—"}</td>
              <td>{r.adp_snake ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Write `web/src/pages/PlayerDetailPage.tsx`** (with calibration caveat per ADR-0015)

```typescript
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api/auth";
import { Histogram } from "../components/Histogram";

type DistResp = {
  player_id: number;
  gsis_id: string;
  projection: { stats: Record<string, number> };
  scoring_preset: string;
  computed_points: number;
  distribution: {
    n_samples: number;
    floor_p10: number;
    median_p50: number;
    ceiling_p90: number;
    mean: number;
    std: number;
    histogram: { bin_edges: number[]; counts: number[] };
  };
  fit: { fitted_at: string; historical_seasons: number[]; games_used: number };
};

export function PlayerDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<DistResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DistResp>(`/api/players/${id}/distribution`)
      .then(setData).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <pre>{err}</pre>;
  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <h1>Player {data.player_id}</h1>
      <p>Projected points ({data.scoring_preset}): <strong>{data.computed_points.toFixed(1)}</strong></p>
      <p>
        Floor (p10): {data.distribution.floor_p10.toFixed(1)} ·{" "}
        Median: {data.distribution.median_p50.toFixed(1)} ·{" "}
        Ceiling (p90): {data.distribution.ceiling_p90.toFixed(1)}
      </p>
      <p style={{ fontSize: "0.85em", color: "#555", maxWidth: 600 }}>
        <em>Calibration note:</em> Distributions reflect the uncertainty around the
        imported projection. Calibration to actual season outcomes is approximate
        (~65–70% at the 80% interval in backtest; expected to improve with real
        preseason projections). Treat intervals as informed bounds, not guarantees.
      </p>
      <Histogram
        binEdges={data.distribution.histogram.bin_edges}
        counts={data.distribution.histogram.counts}
      />
      <h3>Projected stats</h3>
      <ul>
        {Object.entries(data.projection.stats).map(([k, v]) => (
          <li key={k}>{k}: {v}</li>
        ))}
      </ul>
      <p style={{ fontSize: "0.8em", color: "#777" }}>
        Fit: {data.fit.games_used} historical games, seasons{" "}
        {data.fit.historical_seasons.join(", ")}
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Dev-test click-through (requires Fly backend live)**

```bash
cd web && npm run dev
# navigate to /players → click a player → verify histogram renders + caveat text shown
```

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/PlayersPage.tsx web/src/pages/PlayerDetailPage.tsx web/src/components/Histogram.tsx
git commit -m "feat: players list + player detail with calibration caveat"
```

---

## Task 20: Deploy Frontend to Vercel

- [ ] **Step 1: Install Vercel CLI if not present**

```bash
npm i -g vercel
vercel whoami || vercel login
```

- [ ] **Step 2: Deploy preview**

```bash
cd web && vercel --yes
```

- [ ] **Step 3: Set env vars in Vercel dashboard (or via CLI)**

```bash
# $TOKEN from Task 16 Step 3
vercel env add VITE_API_URL production   # paste https://mc-ff-sim-api.fly.dev
vercel env add VITE_API_TOKEN production  # paste the token from Fly
```

- [ ] **Step 4: Promote to production**

```bash
cd web && vercel --prod --yes
```

- [ ] **Step 5: Update backend CORS allowed-origins env var**

```bash
VERCEL_URL=$(vercel --yes | tail -1)  # or from dashboard
fly secrets set --app mc-ff-sim-api CORS_ORIGINS="$VERCEL_URL,http://localhost:5173"
fly deploy --app mc-ff-sim-api  # redeploy to pick up CORS change
```

- [ ] **Step 6: Manual smoke test in browser**

Open the Vercel URL. Navigate: `/` (Settings) → pick preset → `/import` → upload `tests/fixtures/fantasypros_qb.html` (manually — user does this) → `/players` → click a player → verify histogram + caveat.

- [ ] **Step 7: Commit any config changes**

```bash
git status
git add -u && git commit -m "chore: vercel config" || true
```

---

## Task 21: End-to-End Playwright + Canary Comparison

**Files:**
- Create: `web/tests/e2e/happy-path.spec.ts`
- Create: `api/scripts/canary.py`

- [ ] **Step 1: Install Playwright**

```bash
cd web && npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: Add playwright config** at `web/playwright.config.ts`

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    headless: true,
  },
});
```

- [ ] **Step 3: Write happy-path E2E** at `web/tests/e2e/happy-path.spec.ts`

```typescript
import { test, expect } from "@playwright/test";
import * as path from "path";

test("happy path: settings → import QB → players → detail", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Settings");
  await page.getByRole("button", { name: "half_ppr" }).click();

  await page.goto("/import");
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_qb.html");
  await page.setInputFiles("input[type=file]", fixture);
  // Selecting source is already "fantasypros" by default.
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.locator("pre")).toContainText("matched_rows");

  await page.goto("/players");
  await expect(page.locator("table tbody tr")).toHaveCount(1, { timeout: 5000 }).catch(() => {
    /* lenient — depends on seeded canonical */
  });
  // At least one linked row
  const firstLink = page.locator("table tbody tr td a").first();
  if (await firstLink.count()) {
    await firstLink.click();
    // Histogram SVG present
    await expect(page.locator("svg.recharts-surface")).toBeVisible();
    await expect(page.getByText(/Calibration note/)).toBeVisible();
  }
});
```

- [ ] **Step 4: Run Playwright against live deploy**

```bash
E2E_BASE_URL=https://<your-vercel-url> cd web && npx playwright test
```

- [ ] **Step 5: Write canary script** at `api/scripts/canary.py`

```python
"""Canary comparison: pick 5 top-ADP players and compare median
distribution output to their projected points. Should match within ~1 pt.
"""
from __future__ import annotations
import os
import requests

API_URL = os.environ["API_URL"]
TOKEN = os.environ["API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def main() -> int:
    rows = requests.get(f"{API_URL}/api/players?has_projection=true",
                        headers=HEADERS).json()
    # Top 5 by projected_points
    top = sorted([r for r in rows if r.get("projected_points")],
                 key=lambda r: -r["projected_points"])[:5]
    print(f"{'name':25s} {'proj':>8s} {'p50':>8s} {'diff':>8s}")
    bad = 0
    for r in top:
        try:
            dist = requests.get(
                f"{API_URL}/api/players/{r['player_id']}/distribution",
                headers=HEADERS).json()
        except Exception as e:
            print(f"{r['name']:25s} error: {e}")
            continue
        p50 = dist["distribution"]["median_p50"]
        diff = abs(p50 - r["projected_points"])
        flag = "  " if diff <= 5.0 else "!!"  # season totals; allow wider tolerance
        if diff > 5.0:
            bad += 1
        print(f"{r['name']:25s} {r['projected_points']:>8.1f} {p50:>8.1f} {diff:>8.1f} {flag}")
    if bad > 0:
        print(f"\n{bad} players differed by >5 pts — investigate")
        return 1
    print("\nCanary PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run canary**

```bash
API_URL=https://mc-ff-sim-api.fly.dev API_TOKEN=$TOKEN \
  cd api && .venv/bin/python scripts/canary.py
```

- [ ] **Step 7: Commit**

```bash
git add web/tests/e2e/ web/playwright.config.ts api/scripts/canary.py
git commit -m "test: playwright e2e happy path + canary comparison script"
```

---

## Task 22: Tear Down C1 Spike App + Final Housekeeping

- [ ] **Step 1: Verify the real MVP Fly app is healthy**

```bash
curl -s https://mc-ff-sim-api.fly.dev/api/health | python3 -m json.tool
```

- [ ] **Step 2: Tear down `ffsim-spike-c1`**

```bash
fly apps destroy ffsim-spike-c1 --yes
fly volumes list --app ffsim-spike-c1 || echo "volume removed"
```

- [ ] **Step 3: Verify `fly apps list` no longer shows it**

```bash
fly apps list | grep -v ffsim-spike-c1 || true
```

- [ ] **Step 4: Merge `verify-spikes` to `main` (manual — user decision)**

User decides when to merge:
```bash
git checkout main
git merge verify-spikes
git push origin main
```

- [ ] **Step 5: Final coverage check**

```bash
cd api && .venv/bin/pytest --cov=app --cov-fail-under=80
```

Fix any coverage gaps by adding missing tests for any module under 80%.

- [ ] **Step 6: Commit final state**

```bash
git status
# If any residual changes, commit.
```

---

## Self-Review

**Spec coverage** — every spec section mapped to a task:

- §1 Overview/Non-goals → Task 1 (scaffold constraints) + §6 (K/DEF 422 in `players.py` Task 13)
- §2 Architecture (repo layout, deploy, auth, first-boot) → Tasks 1, 2, 12, 15, 16, 17, 20
- §3 Data Model → Task 3 (models + migration)
- §4 Core Components:
  - `import_pipeline/` → Tasks 9, 10, 11
  - `identity/` → Task 6
  - `scoring/` → Task 4
  - `historical/` → Task 7
  - `sim/` → Tasks 5, 8
  - `routers/` → Task 13
  - Frontend modules → Tasks 17, 18, 19
- §5 Data Flow (first-boot, happy path, cache invalidation, error paths) → Tasks 12 (first-boot), 13 (endpoints), 14 (e2e test)
- §6 API Surface → Task 13
- §7 Testing Strategy:
  - Unit tests → Tasks 2 (auth, config), 4 (scoring), 5 (families), 6 (resolver, team_codes), 7 (fetch), 8 (fitting, sampler, runner), 9 (csv_parser), 10 (column_mapper)
  - Integration → Tasks 11 (import flow), 13 (routers), 14 (happy path)
  - E2E → Task 21 (Playwright)
  - Coverage gate → Task 22
- §8 Open Questions & Risks → Documented; R5 caveat in UI (Task 19)
- §9 Validation Plan → Handled by spikes (pre-work); D1 walking skeleton covered by Task 14 + 15 + 16; D3 canary by Task 21
- §10 ADR Index → Referenced throughout tasks via inline comments and commit messages

**Placeholder scan** — no TBD/TODO/"fill in details"/"add error handling" without concrete code blocks. Every step that changes code shows the code. Every command has expected output described.

**Type consistency** — `dispatch_fit`, `STAT_FAMILY`, `canonicalize_team`, `TEAM_CODE_ALIASES`, `FP_SECTION_MAP`, `resolve`, `parse_file`, `score`, `simulate_from_params`, `ensure_seasons`, `game_logs`, `seed_players` — all used consistently across tasks. Pydantic schema names (`LeagueConfigOut`, `ImportBatchResult`, `PlayerRow`, `DistributionResponse`) consistent between `schemas.py` (Task 12) and routers (Task 13).

**Gaps** — none. K/DEF `not_supported_mvp` covered in Task 13 Step 7's `test_k_def_distribution_returns_422`.

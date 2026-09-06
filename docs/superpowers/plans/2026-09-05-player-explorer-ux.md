# Player Explorer UX & Performance Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the working-but-unstyled Player Explorer into a designed, fast, honest
interface — distribution summaries for every player without a per-player wait, a Tailwind
rebuild against the completed Stitch design, and every failure state surfaced as a real
message.

**Architecture:** A new `player_distribution_summary` table caches points-denominated
simulation output keyed by `(player_id, scoring_preset)`, filled by a client-driven chunked
precompute endpoint. The frontend is rebuilt on Tailwind v4 using the `terminal_slate_2`
token set, with a small component library replacing ad-hoc inline styles.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, NumPy/SciPy, pytest.
React 19, Vite 8, TypeScript ~6.0, react-router 7, recharts 3, Tailwind CSS v4, Vitest,
Playwright, oxlint.

**Spec:** [`docs/superpowers/specs/2026-09-05-player-explorer-ux-design.md`](../specs/2026-09-05-player-explorer-ux-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

- **Working directory** is `api/` for all backend commands and `web/` for all frontend
  commands. The venv is `api/.venv`.
- **Coverage gate: 80% minimum** (`pytest --cov=app`). Current baseline is 84.60% — do not
  regress below 80.
- **TDD is mandatory.** Write the test, run it and watch it fail, write the minimal
  implementation, run it and watch it pass, commit. Never write implementation first.
- **No new runtime dependency** beyond `tailwindcss@^4` and `@tailwindcss/vite`. New
  **dev** dependencies (Vitest) are permitted.
- **Immutability.** Never mutate objects or arrays in place; construct new ones. Applies to
  TypeScript state updates and Python dict/list handling alike.
- **File size:** 200–400 lines typical, 800 hard maximum. Extract rather than grow.
- **No `console.log`** in committed frontend code.
- **Every points value is per game.** Every label that shows one must say so —
  `pts / game`, `MEAN PER GAME`, `Fantasy points per game`. This wording was a shipped bug
  once (fixed in `adbe655`); do not reintroduce the ambiguity.
- **Determinism:** summaries are computed with `seed=42` and `n=5000`. Never randomize.
- **Design tokens** are fixed by spec Appendix B.1. Use those exact hex values.
- **Never implement anything in spec Appendix B.3.** The Stitch screens depict correlation
  modeling, R² model fit, boom/bust, tier badges, target share, and fabricated engine
  telemetry. None of it exists. The calibration note in particular must NOT claim
  correlation coefficients factor into the model — that contradicts the independence
  assumption the whole engine rests on.
- **Commits** follow conventional-commit format (`feat:`, `fix:`, `test:`, `refactor:`,
  `docs:`, `chore:`). Commit at the end of every task.

## File Structure

**Backend — create**

| File | Responsibility |
|---|---|
| `api/app/sim/summary.py` | Compute, persist, invalidate, and query distribution summaries. The only module that knows how a summary is built. |
| `api/alembic/versions/0002_distribution_summary.py` | Schema migration for the new table. |
| `api/tests/unit/test_summary.py` | Unit tests for summary computation and invalidation. |
| `api/tests/integration/test_precompute.py` | Precompute chunking, resumability, termination. |
| `api/tests/integration/test_unresolved.py` | Unresolved-rows endpoint. |

**Backend — modify**

| File | Change |
|---|---|
| `api/app/sim/runner.py` | Add `p25`, `p75`, `skewness` to the result dict. |
| `api/app/models/orm.py` | Add `PlayerDistributionSummary`. |
| `api/app/models/schemas.py` | Add `DistributionSummary`, `PrecomputeResult`, `UnresolvedRow`; extend `PlayerRow`, `DistributionBody`, `DistributionResponse`. |
| `api/app/routers/players.py` | Summaries on the list; new precompute endpoint; identity fields and new percentiles on the distribution endpoint. |
| `api/app/routers/imports.py` | New `GET /{batch_id}/unresolved`. |
| `api/app/import_pipeline/stats_importer.py` | Invalidate summaries alongside params. |
| `api/app/routers/historical.py` | Invalidate all summaries on refresh. |
| `api/app/routers/admin.py` | Invalidate summaries for remapped players. |
| `api/tests/unit/test_runner.py` | Cover the new keys. |
| `api/tests/integration/test_routers.py` | Cover list summaries and distribution identity. |

**Frontend — create**

| File | Responsibility |
|---|---|
| `web/src/lib/statLabels.ts` | Canonical stat key → human label. |
| `web/src/lib/format.ts` | Number formatting with fixed decimals and tabular output. |
| `web/src/api/errors.ts` | Map an HTTP failure to a user-facing message. |
| `web/src/api/types.ts` | Shared response types for all pages. |
| `web/src/hooks/useDebounce.ts` | Debounced value hook. |
| `web/src/hooks/useWarming.ts` | Tracks the "server is cold" signal. |
| `web/src/components/AppShell.tsx` | Header, nav, preset selector, page frame. |
| `web/src/components/Card.tsx` | The one elevation primitive. |
| `web/src/components/Skeleton.tsx` | Shimmer block + skeleton player card. |
| `web/src/components/StatTile.tsx` | Uppercase label over a large value. |
| `web/src/components/PositionBadge.tsx` | Colour-coded QB/RB/WR/TE badge. |
| `web/src/components/PositionTabs.tsx` | Segmented position filter. |
| `web/src/components/SearchInput.tsx` | Text filter input. |
| `web/src/components/Sparkline.tsx` | Inline SVG distribution curve from histogram bins. |
| `web/src/components/PresetSelector.tsx` | Reads/writes `LeagueConfig.scoring_preset`. |
| `web/src/components/EmptyState.tsx` | Designed empty state. |
| `web/src/components/ErrorState.tsx` | Designed error state. |
| `web/src/components/WarmingPanel.tsx` | Cold-boot explanation panel. |
| `web/src/components/PlayerCard.tsx` | One row of the Players list. |
| `web/tests/unit/*.test.ts` | Vitest unit tests. |

**Frontend — modify**: `web/package.json`, `web/vite.config.ts`, `web/src/index.css`,
`web/src/App.tsx`, `web/src/api/auth.ts`, `web/src/components/Histogram.tsx`, all four
pages, `web/tests/e2e/happy-path.spec.ts`.
**Frontend — delete**: `web/src/App.css` (184 lines, never imported).

---

## Task 1: Runner returns P25, P75, and sample skew

**Files:**
- Modify: `api/app/sim/runner.py:20-38`
- Test: `api/tests/unit/test_runner.py`

**Interfaces:**
- Produces: `simulate_from_params(...) -> dict` gains keys `p25: float`, `p75: float`,
  `skewness: float`. All existing keys are unchanged.

Context: the detail chart flags five percentiles, not three. `skewness` is the *empirical*
skewness of the simulated points sample — there is no single fitted shape parameter for the
points distribution, because fitting is per-stat and points are their scored convolution.
Never label this as a fitted `α`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/unit/test_runner.py`:

```python
from scipy import stats


def test_simulate_returns_five_ordered_percentiles():
    params = {
        "passing_yards": ("skewnorm", 0.0, 250.0, 40.0),
        "passing_tds": ("nbinom", 3.0, 0.3),
    }
    r = simulate_from_params(params, preset=FULL_PPR, n=2000, seed=42)
    assert r["floor_p10"] <= r["p25"] <= r["median_p50"] <= r["p75"] <= r["ceiling_p90"]


def test_simulate_reports_sample_skewness():
    """Right-skewed input must report positive skew; the value is the sample
    skewness of the scored points, not a fitted shape parameter."""
    params = {"rushing_tds": ("nbinom", 1.5, 0.25)}
    r = simulate_from_params(params, preset=FULL_PPR, n=4000, seed=7)
    assert isinstance(r["skewness"], float)
    assert r["skewness"] > 0.0


def test_skewness_is_deterministic_with_seed():
    params = {"passing_yards": ("skewnorm", 0.2, 200.0, 40.0)}
    a = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    b = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    assert a["skewness"] == b["skewness"]
    assert a["p25"] == b["p25"] and a["p75"] == b["p75"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/pytest tests/unit/test_runner.py -v`
Expected: 3 FAILs with `KeyError: 'p25'` / `KeyError: 'skewness'`.

- [ ] **Step 3: Write the minimal implementation**

In `api/app/sim/runner.py`, add the scipy import at the top:

```python
from scipy import stats as _stats
```

Replace the percentile line and the return dict:

```python
    p10, p25, p50, p75, p90 = np.percentile(points, [10, 25, 50, 75, 90])
    counts, edges = np.histogram(points, bins=n_bins)
    return {
        "n_samples": n,
        "floor_p10": float(p10),
        "p25": float(p25),
        "median_p50": float(p50),
        "p75": float(p75),
        "ceiling_p90": float(p90),
        "mean": float(points.mean()),
        "std": float(points.std()),
        "skewness": float(_stats.skew(points)),
        "histogram": {
            "bin_edges": edges.tolist(),
            "counts": counts.tolist(),
        },
    }
```

- [ ] **Step 4: Run the full unit suite to verify it passes**

Run: `cd api && .venv/bin/pytest tests/unit -v`
Expected: all PASS, including the three pre-existing runner tests.

- [ ] **Step 5: Commit**

```bash
git add api/app/sim/runner.py api/tests/unit/test_runner.py
git commit -m "feat: runner reports p25, p75, and sample skewness"
```

---

## Task 2: `player_distribution_summary` table and migration

**Files:**
- Modify: `api/app/models/orm.py` (append after `PlayerDistributionParams`)
- Create: `api/alembic/versions/0002_distribution_summary.py`
- Test: `api/tests/unit/test_summary.py`

**Interfaces:**
- Produces: `PlayerDistributionSummary` ORM model with composite primary key
  `(player_id, scoring_preset)`. Columns as below. Metric columns are nullable because a
  non-`ok` row records a terminal failure and has no metrics.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_summary.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.orm import PlayerDistributionSummary


def test_summary_is_keyed_by_player_and_preset(session, seeded_players):
    """The same player may hold one summary per preset simultaneously."""
    session.add_all([
        PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                  status="ok", computed_at="2026-09-05T00:00:00"),
        PlayerDistributionSummary(player_id=1, scoring_preset="full_ppr",
                                  status="ok", computed_at="2026-09-05T00:00:00"),
    ])
    session.commit()
    assert session.query(PlayerDistributionSummary).count() == 2


def test_summary_rejects_unknown_status(session, seeded_players):
    session.add(PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                          status="banana",
                                          computed_at="2026-09-05T00:00:00"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_non_ok_summary_leaves_metrics_null(session, seeded_players):
    """A terminal-failure row carries the reason and no metrics."""
    session.add(PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                          status="insufficient_history",
                                          computed_at="2026-09-05T00:00:00"))
    session.commit()
    row = session.get(PlayerDistributionSummary, (1, "half_ppr"))
    assert row.status == "insufficient_history"
    assert row.median_p50 is None and row.histogram is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd api && .venv/bin/pytest tests/unit/test_summary.py -v`
Expected: FAIL with `ImportError: cannot import name 'PlayerDistributionSummary'`.

- [ ] **Step 3: Add the ORM model**

Append to `api/app/models/orm.py`:

```python
class PlayerDistributionSummary(Base):
    """Points-denominated simulation output, cached per (player, preset).

    Distinct from PlayerDistributionParams, which caches the per-stat fits and
    is preset-independent. `status` records a terminal outcome so the
    precompute loop terminates instead of re-selecting players that can never
    produce a distribution.
    """
    __tablename__ = "player_distribution_summary"
    player_id = Column(Integer, ForeignKey("player.mfl_id"), primary_key=True)
    scoring_preset = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    floor_p10 = Column(Float)
    p25 = Column(Float)
    median_p50 = Column(Float)
    p75 = Column(Float)
    ceiling_p90 = Column(Float)
    mean = Column(Float)
    std = Column(Float)
    skewness = Column(Float)
    histogram = Column(Text)  # JSON {bin_edges, counts}
    computed_points = Column(Float)
    n_samples = Column(Integer)
    source_projection_id = Column(Integer, ForeignKey("player_projection.id"))
    computed_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("scoring_preset IN ('standard','half_ppr','full_ppr')"),
        CheckConstraint(
            "status IN ('ok','insufficient_history','unsupported_position')"),
    )
```

Verify `Float`, `Text`, and `CheckConstraint` are already in the file's imports from
`sqlalchemy` — they are, used by earlier models. Add any that are missing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd api && .venv/bin/pytest tests/unit/test_summary.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Write the migration**

Create `api/alembic/versions/0002_distribution_summary.py`:

```python
"""player_distribution_summary

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_distribution_summary',
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('scoring_preset', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('floor_p10', sa.Float(), nullable=True),
        sa.Column('p25', sa.Float(), nullable=True),
        sa.Column('median_p50', sa.Float(), nullable=True),
        sa.Column('p75', sa.Float(), nullable=True),
        sa.Column('ceiling_p90', sa.Float(), nullable=True),
        sa.Column('mean', sa.Float(), nullable=True),
        sa.Column('std', sa.Float(), nullable=True),
        sa.Column('skewness', sa.Float(), nullable=True),
        sa.Column('histogram', sa.Text(), nullable=True),
        sa.Column('computed_points', sa.Float(), nullable=True),
        sa.Column('n_samples', sa.Integer(), nullable=True),
        sa.Column('source_projection_id', sa.Integer(), nullable=True),
        sa.Column('computed_at', sa.String(), nullable=False),
        sa.CheckConstraint(
            "scoring_preset IN ('standard','half_ppr','full_ppr')"),
        sa.CheckConstraint(
            "status IN ('ok','insufficient_history','unsupported_position')"),
        sa.ForeignKeyConstraint(['player_id'], ['player.mfl_id']),
        sa.ForeignKeyConstraint(['source_projection_id'],
                                ['player_projection.id']),
        sa.PrimaryKeyConstraint('player_id', 'scoring_preset'),
    )


def downgrade() -> None:
    op.drop_table('player_distribution_summary')
```

- [ ] **Step 6: Verify the migration applies**

```bash
cd api && mkdir -p data && .venv/bin/alembic upgrade head
.venv/bin/python -c "
import sqlalchemy as sa
e = sa.create_engine('sqlite:///data/sqlite.db')
i = sa.inspect(e)
assert 'player_distribution_summary' in i.get_table_names()
cols = {c['name'] for c in i.get_columns('player_distribution_summary')}
assert 'status' in cols and 'p25' in cols and 'skewness' in cols
print('migration ok:', sorted(cols))
"
```

Expected: prints the full column list including `status`, `p25`, `p75`, `skewness`.

- [ ] **Step 7: Commit**

```bash
git add api/app/models/orm.py api/alembic/versions/0002_distribution_summary.py api/tests/unit/test_summary.py
git commit -m "feat: add player_distribution_summary table and migration"
```

---

## Task 3: The summary module

**Files:**
- Create: `api/app/sim/summary.py`
- Test: `api/tests/unit/test_summary.py` (append)

**Interfaces:**
- Consumes: `PlayerDistributionSummary` (Task 2), `simulate_from_params` (Task 1),
  existing `family_for`, `dispatch_fit`, `game_logs`, `score`, `PRESETS`.
- Produces:
  - `MIN_GAMES: int = 4` and `K_DEF_POSITIONS: set[str] = {"K", "DEF"}` — moved here from
    `players.py` so there is one definition.
  - `SUMMARY_N: int = 5000`, `SUMMARY_SEED: int = 42`
  - `compute_and_store(session, *, player, projected_stats, projection_id, preset_name, historical_seasons) -> PlayerDistributionSummary`
    — always returns a row, `session.add()`ed but **not committed**; the caller commits.
  - `invalidate_for_players(session, player_ids: Iterable[int]) -> int`
  - `invalidate_all(session) -> int`
  - `players_needing_summary(session, preset_name, limit) -> list[tuple[Player, PlayerProjection]]`
  - `summary_progress(session, preset_name) -> tuple[int, int]` returning `(done, total)`

This module is the single place that knows how a summary is built. The distribution
endpoint and the precompute endpoint both go through it — do not duplicate the fitting
loop into a router.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/unit/test_summary.py`:

```python
import json
from datetime import datetime
import numpy as np
import polars as pl
from app.models.orm import PlayerProjection, PlayerDistributionSummary
from app.sim import summary as summary_mod


def _fake_logs(monkeypatch, n_games: int):
    """Stub game_logs so unit tests never touch parquet or the network."""
    rng = np.random.default_rng(3)
    df = pl.DataFrame({
        "receptions": rng.integers(2, 9, n_games).astype(float),
        "receiving_yards": rng.normal(70, 25, n_games),
        "receiving_tds": rng.integers(0, 2, n_games).astype(float),
    })
    monkeypatch.setattr(summary_mod, "game_logs", lambda *a, **k: df)


def _projection(session, player_id: int) -> PlayerProjection:
    now = datetime.utcnow().isoformat()
    proj = PlayerProjection(player_id=player_id, import_batch_id=1, position="WR",
                            stats=json.dumps({"receptions": 6.0,
                                              "receiving_yards": 85.0,
                                              "receiving_tds": 0.5}),
                            created_at=now)
    session.add(proj)
    session.commit()
    return proj


def test_compute_and_store_writes_ok_row(session, seeded_players, monkeypatch):
    _fake_logs(monkeypatch, 40)
    proj = _projection(session, 4)
    player = seeded_players[3]  # CeeDee Lamb, WR
    row = summary_mod.compute_and_store(
        session, player=player, projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023, 2024, 2025])
    session.commit()
    assert row.status == "ok"
    assert row.floor_p10 <= row.p25 <= row.median_p50 <= row.p75 <= row.ceiling_p90
    assert json.loads(row.histogram)["counts"]
    assert row.n_samples == summary_mod.SUMMARY_N


def test_compute_and_store_marks_insufficient_history(session, seeded_players, monkeypatch):
    """Fewer than MIN_GAMES career games is terminal, not an error to retry."""
    _fake_logs(monkeypatch, 2)
    proj = _projection(session, 4)
    row = summary_mod.compute_and_store(
        session, player=seeded_players[3], projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "insufficient_history"
    assert row.median_p50 is None


def test_compute_and_store_marks_unsupported_position(session, seeded_players, monkeypatch):
    _fake_logs(monkeypatch, 40)
    player = seeded_players[2]
    player.position = "K"
    session.commit()
    proj = _projection(session, player.mfl_id)
    row = summary_mod.compute_and_store(
        session, player=player, projected_stats=json.loads(proj.stats),
        projection_id=proj.id, preset_name="half_ppr",
        historical_seasons=[2023])
    session.commit()
    assert row.status == "unsupported_position"


def test_compute_and_store_is_idempotent_per_preset(session, seeded_players, monkeypatch):
    """Recomputing replaces the row rather than raising on the composite key."""
    _fake_logs(monkeypatch, 40)
    proj = _projection(session, 4)
    kwargs = dict(player=seeded_players[3], projected_stats=json.loads(proj.stats),
                  projection_id=proj.id, preset_name="half_ppr",
                  historical_seasons=[2023])
    first = summary_mod.compute_and_store(session, **kwargs)
    session.commit()
    first_median = first.median_p50
    second = summary_mod.compute_and_store(session, **kwargs)
    session.commit()
    assert session.query(PlayerDistributionSummary).count() == 1
    assert second.median_p50 == first_median  # deterministic seed


def test_invalidate_for_players_drops_every_preset(session, seeded_players):
    now = datetime.utcnow().isoformat()
    session.add_all([
        PlayerDistributionSummary(player_id=1, scoring_preset="half_ppr",
                                  status="ok", computed_at=now),
        PlayerDistributionSummary(player_id=1, scoring_preset="full_ppr",
                                  status="ok", computed_at=now),
        PlayerDistributionSummary(player_id=2, scoring_preset="half_ppr",
                                  status="ok", computed_at=now),
    ])
    session.commit()
    dropped = summary_mod.invalidate_for_players(session, [1])
    session.commit()
    assert dropped == 2
    assert session.query(PlayerDistributionSummary).count() == 1


def test_progress_counts_terminal_rows_as_done(session, seeded_players, monkeypatch):
    """A player that can never be computed still counts as done, or the
    progress bar would never reach 100%."""
    _projection(session, 4)
    _projection(session, 1)
    now = datetime.utcnow().isoformat()
    session.add(PlayerDistributionSummary(player_id=4, scoring_preset="half_ppr",
                                          status="insufficient_history",
                                          computed_at=now))
    session.commit()
    done, total = summary_mod.summary_progress(session, "half_ppr")
    assert (done, total) == (1, 2)


def test_players_needing_summary_excludes_done(session, seeded_players):
    _projection(session, 4)
    _projection(session, 1)
    now = datetime.utcnow().isoformat()
    session.add(PlayerDistributionSummary(player_id=4, scoring_preset="half_ppr",
                                          status="ok", computed_at=now))
    session.commit()
    pending = summary_mod.players_needing_summary(session, "half_ppr", limit=25)
    assert [p.mfl_id for p, _ in pending] == [1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd api && .venv/bin/pytest tests/unit/test_summary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sim.summary'`.

- [ ] **Step 3: Write the implementation**

Create `api/app/sim/summary.py`:

```python
"""Compute, persist, invalidate, and query per-player distribution summaries.

A summary is the points-denominated output of a simulation run, cached per
(player, scoring_preset). It is distinct from PlayerDistributionParams, which
caches the preset-independent per-stat fits.

Every summary carries a `status`. A player who can never produce a
distribution — wrong position, too little history — gets a terminal row rather
than being silently skipped, so the precompute loop converges.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.historical.fetch import game_logs
from app.models.orm import (
    Player, PlayerProjection, PlayerDistributionParams,
    PlayerDistributionSummary,
)
from app.scoring.engine import score
from app.scoring.presets import PRESETS
from app.sim.families import family_for
from app.sim.fitting import dispatch_fit
from app.sim.runner import simulate_from_params

MIN_GAMES = 4
K_DEF_POSITIONS = {"K", "DEF"}
SUMMARY_N = 5000
SUMMARY_SEED = 42

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_history"
STATUS_UNSUPPORTED = "unsupported_position"


def _fit_params(session: Session, player: Player, projected_stats: dict,
                historical_seasons: list[int]) -> tuple[dict | None, str, int]:
    """Return (params, fitted_at, games_used); params is None when history is short.

    Reuses the cached per-stat fits when present — they are the expensive part
    and do not depend on the scoring preset.
    """
    cached = session.get(PlayerDistributionParams, player.mfl_id)
    if cached is not None:
        params = {k: tuple(v) for k, v in json.loads(cached.params).items()}
        return params, cached.fitted_at, cached.games_used

    logs = game_logs(player.gsis_id, historical_seasons)
    if logs.height < MIN_GAMES:
        return None, datetime.utcnow().isoformat(), logs.height

    params: dict[str, tuple] = {}
    for stat, target in projected_stats.items():
        if stat not in logs.columns:
            continue
        values = logs[stat].to_numpy()
        values = values[~(values != values)]  # drop NaN
        if len(values) < MIN_GAMES:
            continue
        params[stat] = dispatch_fit(values, float(target), family_for(stat))

    now = datetime.utcnow().isoformat()
    session.add(PlayerDistributionParams(
        player_id=player.mfl_id,
        params=json.dumps({k: list(v) for k, v in params.items()}),
        fitted_at=now,
        historical_seasons=",".join(str(y) for y in historical_seasons),
        games_used=logs.height,
    ))
    return params, now, logs.height


def compute_and_store(session: Session, *, player: Player,
                      projected_stats: dict, projection_id: int,
                      preset_name: str,
                      historical_seasons: list[int]) -> PlayerDistributionSummary:
    """Simulate and persist one summary. Adds to the session; caller commits."""
    now = datetime.utcnow().isoformat()
    existing = session.get(PlayerDistributionSummary, (player.mfl_id, preset_name))
    if existing is not None:
        session.delete(existing)
        session.flush()

    def _terminal(status: str) -> PlayerDistributionSummary:
        row = PlayerDistributionSummary(
            player_id=player.mfl_id, scoring_preset=preset_name,
            status=status, source_projection_id=projection_id,
            computed_at=now,
        )
        session.add(row)
        return row

    if player.position in K_DEF_POSITIONS:
        return _terminal(STATUS_UNSUPPORTED)

    params, _fitted_at, _games = _fit_params(
        session, player, projected_stats, historical_seasons)
    if params is None:
        return _terminal(STATUS_INSUFFICIENT)

    preset = PRESETS[preset_name]
    result = simulate_from_params(params, preset=preset,
                                  n=SUMMARY_N, seed=SUMMARY_SEED)
    row = PlayerDistributionSummary(
        player_id=player.mfl_id, scoring_preset=preset_name, status=STATUS_OK,
        floor_p10=result["floor_p10"], p25=result["p25"],
        median_p50=result["median_p50"], p75=result["p75"],
        ceiling_p90=result["ceiling_p90"], mean=result["mean"],
        std=result["std"], skewness=result["skewness"],
        histogram=json.dumps(result["histogram"]),
        computed_points=score(projected_stats, preset),
        n_samples=result["n_samples"], source_projection_id=projection_id,
        computed_at=now,
    )
    session.add(row)
    return row


def invalidate_for_players(session: Session, player_ids: Iterable[int]) -> int:
    """Drop every preset's summary for the given players. Caller commits."""
    ids = list(player_ids)
    if not ids:
        return 0
    return (session.query(PlayerDistributionSummary)
                   .filter(PlayerDistributionSummary.player_id.in_(ids))
                   .delete(synchronize_session=False))


def invalidate_all(session: Session) -> int:
    """Drop every summary. Caller commits."""
    return session.query(PlayerDistributionSummary).delete(
        synchronize_session=False)


def _latest_projection_ids(session: Session) -> dict[int, int]:
    """player_id -> id of that player's most recent projection."""
    latest = (session.query(PlayerProjection.player_id.label("pid"),
                            func.max(PlayerProjection.created_at).label("mx"))
                     .group_by(PlayerProjection.player_id).subquery())
    rows = (session.query(PlayerProjection)
                   .join(latest, (PlayerProjection.player_id == latest.c.pid)
                         & (PlayerProjection.created_at == latest.c.mx))
                   .all())
    out: dict[int, int] = {}
    for row in rows:
        if row.player_id not in out or row.id > out[row.player_id]:
            out[row.player_id] = row.id
    return out


def summary_progress(session: Session, preset_name: str) -> tuple[int, int]:
    """(done, total) for the given preset.

    Terminal rows count as done — a player who can never be simulated must not
    hold the progress bar below 100% forever.
    """
    total = session.query(func.count(func.distinct(
        PlayerProjection.player_id))).scalar() or 0
    done = (session.query(func.count(PlayerDistributionSummary.player_id))
                   .filter(PlayerDistributionSummary.scoring_preset == preset_name)
                   .scalar() or 0)
    return int(done), int(total)


def players_needing_summary(session: Session, preset_name: str,
                            limit: int) -> list[tuple[Player, PlayerProjection]]:
    """Players holding a projection but no summary under this preset."""
    have = {pid for (pid,) in session.query(PlayerDistributionSummary.player_id)
            .filter(PlayerDistributionSummary.scoring_preset == preset_name).all()}
    latest_ids = _latest_projection_ids(session)
    pending = [pid for pid in latest_ids if pid not in have]
    pending.sort()
    chosen = pending[:limit]
    if not chosen:
        return []
    players = {p.mfl_id: p for p in session.query(Player)
               .filter(Player.mfl_id.in_(chosen)).all()}
    projections = {pr.id: pr for pr in session.query(PlayerProjection)
                   .filter(PlayerProjection.id.in_(
                       [latest_ids[pid] for pid in chosen])).all()}
    return [(players[pid], projections[latest_ids[pid]])
            for pid in chosen if pid in players]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd api && .venv/bin/pytest tests/unit/test_summary.py -v`
Expected: all PASS (3 from Task 2 plus 7 new).

- [ ] **Step 5: Commit**

```bash
git add api/app/sim/summary.py api/tests/unit/test_summary.py
git commit -m "feat: add summary module for computing and invalidating distributions"
```

---

## Task 4: Players list carries distribution summaries

**Files:**
- Modify: `api/app/models/schemas.py`, `api/app/routers/players.py:72-101`
- Test: `api/tests/integration/test_routers.py` (append)

**Interfaces:**
- Produces: `DistributionSummary` schema and `PlayerRow.distribution: DistributionSummary | None`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/integration/test_routers.py`:

```python
import json as _json
from datetime import datetime as _dt
from app.models.orm import (
    Player as _Player, PlayerProjection as _Proj,
    PlayerDistributionSummary as _Summary, LeagueConfig as _Cfg,
)


def _seed_one_player_with_summary(client, status="ok"):
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
    _seed_one_player_with_summary(client)
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
    _seed_one_player_with_summary(client, status="insufficient_history")
    row = client.get("/api/players", headers=HEADERS).json()[0]
    assert row["distribution"]["status"] == "insufficient_history"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd api && .venv/bin/pytest tests/integration/test_routers.py -k distribution_summary -v`
Expected: FAIL with `KeyError: 'distribution'`.

- [ ] **Step 3: Add the schema**

In `api/app/models/schemas.py`, add before `PlayerRow`:

```python
class DistributionSummary(BaseModel):
    status: Literal["ok", "insufficient_history", "unsupported_position"]
    floor_p10: float | None = None
    p25: float | None = None
    median_p50: float | None = None
    p75: float | None = None
    ceiling_p90: float | None = None
    mean: float | None = None
    std: float | None = None
    skewness: float | None = None
    histogram: Histogram | None = None
    computed_at: str
```

`Histogram` is declared further down the file — move the `Histogram` class above
`DistributionSummary` so the reference resolves.

Then add to `PlayerRow`:

```python
    distribution: DistributionSummary | None = None
```

- [ ] **Step 4: Batch-fetch summaries in the router**

In `api/app/routers/players.py`, import the new names:

```python
from app.models.orm import PlayerDistributionSummary
from app.models.schemas import DistributionSummary
```

Add this helper next to `_latest_by_player`:

```python
def _summaries_by_player(db: Session, preset_name: str) -> dict[int, DistributionSummary]:
    """One query for every summary under the active preset.

    Mirrors the batching in _latest_by_player — this must not become an N+1.
    """
    rows = (db.query(PlayerDistributionSummary)
              .filter(PlayerDistributionSummary.scoring_preset == preset_name)
              .all())
    return {
        row.player_id: DistributionSummary(
            status=row.status, floor_p10=row.floor_p10, p25=row.p25,
            median_p50=row.median_p50, p75=row.p75, ceiling_p90=row.ceiling_p90,
            mean=row.mean, std=row.std, skewness=row.skewness,
            histogram=Histogram(**json.loads(row.histogram)) if row.histogram else None,
            computed_at=row.computed_at,
        )
        for row in rows
    }
```

In `list_players`, after `adp_by_player = _latest_by_player(db, PlayerAdp)` add:

```python
    summary_by_player = _summaries_by_player(db, cfg.scoring_preset)
```

and add `distribution=summary_by_player.get(p.mfl_id),` to the `PlayerRow(...)` construction.

- [ ] **Step 5: Run to verify it passes**

Run: `cd api && .venv/bin/pytest tests/integration/test_routers.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/models/schemas.py api/app/routers/players.py api/tests/integration/test_routers.py
git commit -m "feat: players list returns cached distribution summaries"
```

---

## Task 5: Chunked precompute endpoint

**Files:**
- Modify: `api/app/models/schemas.py`, `api/app/routers/players.py`
- Test: `api/tests/integration/test_precompute.py` (create)

**Interfaces:**
- Produces: `POST /api/players/precompute?limit=25` → `PrecomputeResult`
  `{computed: int, done: int, total: int, remaining: int}`.

Route ordering matters: FastAPI matches in declaration order, so `/precompute` must be
declared **before** `/{player_id}/distribution` or the literal path will be swallowed by
the parameterised one.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/integration/test_precompute.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd api && .venv/bin/pytest tests/integration/test_precompute.py -v`
Expected: FAIL with 404 or 405 — the route does not exist.

- [ ] **Step 3: Add the schema**

In `api/app/models/schemas.py`:

```python
class PrecomputeResult(BaseModel):
    computed: int
    done: int
    total: int
    remaining: int
```

- [ ] **Step 4: Add the endpoint**

In `api/app/routers/players.py`, import:

```python
from app.models.schemas import PrecomputeResult
from app.sim import summary as summary_mod
```

Declare this route **above** `get_distribution`:

```python
@router.post("/precompute", response_model=PrecomputeResult)
def precompute(limit: int = Query(25, ge=1, le=100),
               db: Session = Depends(get_db)):
    """Compute the next chunk of missing summaries under the active preset.

    Chunked and client-driven on purpose: a full import is 250-350 players at
    roughly 250ms each, which is far too long for one request, and a detached
    background task would race Fly's auto-stop. The caller loops until
    `remaining` is 0, which is also what drives the import progress bar.
    """
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    settings = get_settings()
    pending = summary_mod.players_needing_summary(db, cfg.scoring_preset, limit)
    for player, projection in pending:
        summary_mod.compute_and_store(
            db, player=player,
            projected_stats=json.loads(projection.stats),
            projection_id=projection.id,
            preset_name=cfg.scoring_preset,
            historical_seasons=settings.historical_seasons,
        )
    db.commit()
    done, total = summary_mod.summary_progress(db, cfg.scoring_preset)
    return PrecomputeResult(computed=len(pending), done=done, total=total,
                            remaining=max(total - done, 0))
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd api && .venv/bin/pytest tests/integration/test_precompute.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/models/schemas.py api/app/routers/players.py api/tests/integration/test_precompute.py
git commit -m "feat: add chunked precompute endpoint for distribution summaries"
```

---

## Task 6: Distribution endpoint gains identity and new percentiles

**Files:**
- Modify: `api/app/models/schemas.py`, `api/app/routers/players.py:103-181`
- Test: `api/tests/integration/test_routers.py` (append)

**Interfaces:**
- Consumes: `summary_mod.compute_and_store`, `summary_mod.SUMMARY_N`,
  `summary_mod.STATUS_UNSUPPORTED`, `summary_mod.STATUS_INSUFFICIENT`,
  `summary_mod.MIN_GAMES` (Task 3); `PlayerDistributionSummary` (Task 2); the existing
  private helpers `_latest_projection` (`players.py:27`) and `_latest_adp`
  (`players.py:34`).
- Produces: `DistributionResponse` gains `name: str`, `team: str | None`,
  `position: str`, `adp_snake: float | None`. `DistributionBody` gains `p25`, `p75`,
  `skewness`.

This is why the detail page currently renders `<h1>Player 42</h1>` — the data was never in
the response. The endpoint also stops duplicating the fitting loop and delegates to
`app.sim.summary`.

**Remove the `n` query parameter.** It existed to let a caller pick a sample size, but the
iterations control that would have driven it was explicitly declined (spec Appendix B.4),
and nothing in the test suite or the frontend passes it. Keeping it would force a
cache-bypass path that either poisons the summary table with off-size results or needs a
rollback dance that leaves the ORM row expired. The endpoint now always serves the
canonical, deterministic, cached summary — computing it on demand the first time.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/integration/test_routers.py`:

```python
def test_distribution_includes_player_identity(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _seed_one_player_with_summary(client)
    body = client.get("/api/players/1/distribution", headers=HEADERS).json()
    assert body["name"] == "Test Receiver"
    assert body["team"] == "CIN"
    assert body["position"] == "WR"


def test_distribution_includes_five_percentiles_and_skew(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _seed_one_player_with_summary(client)
    d = client.get("/api/players/1/distribution", headers=HEADERS).json()["distribution"]
    assert d["p25"] == 9.0 and d["p75"] == 18.4
    assert d["skewness"] == 0.62


def test_distribution_reports_insufficient_history_as_422(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _seed_one_player_with_summary(client, status="insufficient_history")
    resp = client.get("/api/players/1/distribution", headers=HEADERS)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "insufficient_history"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd api && .venv/bin/pytest tests/integration/test_routers.py -k "identity or percentiles" -v`
Expected: FAIL with `KeyError: 'name'`.

- [ ] **Step 3: Extend the schemas**

In `api/app/models/schemas.py`, add to `DistributionBody` after `floor_p10`:

```python
    p25: float
```

after `median_p50`:

```python
    p75: float
```

and after `std`:

```python
    skewness: float
```

Add to `DistributionResponse` after `gsis_id`:

```python
    name: str
    team: str | None = None
    position: str
    adp_snake: float | None = None
```

- [ ] **Step 4: Rewrite the endpoint body**

Replace the body of `get_distribution` in `api/app/routers/players.py` (everything after
the `player not found` check) with:

Change the signature from
`def get_distribution(player_id: int, n: int = Query(...), db: Session = ...)` to
`def get_distribution(player_id: int, db: Session = Depends(get_db))`, then:

```python
    proj = _latest_projection(db, player_id)
    if proj is None:
        raise HTTPException(status_code=404,
                            detail="no projection for player")
    cfg = db.get(LeagueConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="config not initialized")
    settings = get_settings()
    projected_stats = json.loads(proj.stats)

    row = db.get(PlayerDistributionSummary, (player_id, cfg.scoring_preset))
    if row is None:
        row = summary_mod.compute_and_store(
            db, player=p, projected_stats=projected_stats,
            projection_id=proj.id, preset_name=cfg.scoring_preset,
            historical_seasons=settings.historical_seasons)
        db.commit()

    if row.status == summary_mod.STATUS_UNSUPPORTED:
        raise HTTPException(
            status_code=422,
            detail={"error": "not_supported_mvp",
                    "message": "K/DEF distributions not supported in MVP"})
    if row.status == summary_mod.STATUS_INSUFFICIENT:
        raise HTTPException(
            status_code=422,
            detail={"error": "insufficient_history",
                    "message": "Not enough career games to model this player",
                    "details": {"min_games": summary_mod.MIN_GAMES}})

    params_row = db.get(PlayerDistributionParams, player_id)
    adp = _latest_adp(db, player_id)
    return DistributionResponse(
        player_id=player_id, gsis_id=p.gsis_id, name=p.name, team=p.team,
        position=p.position, adp_snake=adp.adp_snake if adp else None,
        projection={"stats": projected_stats,
                    "import_batch_id": proj.import_batch_id},
        scoring_preset=cfg.scoring_preset,
        computed_points=row.computed_points,
        distribution=DistributionBody(
            n_samples=row.n_samples, floor_p10=row.floor_p10, p25=row.p25,
            median_p50=row.median_p50, p75=row.p75, ceiling_p90=row.ceiling_p90,
            mean=row.mean, std=row.std, skewness=row.skewness,
            histogram=Histogram(**json.loads(row.histogram)),
        ),
        fit=FitInfo(
            fitted_at=params_row.fitted_at if params_row else row.computed_at,
            historical_seasons=settings.historical_seasons,
            games_used=params_row.games_used if params_row else 0),
    )
```

Delete the now-unused inline fitting loop, and remove `MIN_GAMES` / `K_DEF_POSITIONS`
from `players.py` — they live in `app.sim.summary` now. Update any remaining references.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd api && .venv/bin/pytest -v`
Expected: all PASS. Existing distribution tests still pass because every previous
response field is retained.

- [ ] **Step 6: Commit**

```bash
git add api/app/models/schemas.py api/app/routers/players.py api/tests/integration/test_routers.py
git commit -m "feat: distribution endpoint returns identity, p25/p75, and sample skew"
```

---

## Task 7: Wire summary invalidation into all three paths

**Files:**
- Modify: `api/app/import_pipeline/stats_importer.py:81-83`,
  `api/app/routers/historical.py`, `api/app/routers/admin.py`
- Test: `api/tests/integration/test_precompute.py` (append)

**Interfaces:**
- Consumes: `summary_mod.invalidate_for_players`, `summary_mod.invalidate_all` (Task 3).

The `refresh-players` path is the one that matters most: it can remap identity, and the
MVP's fix wave only covered `stats_importer.py`, leaving this as a known second path for
the same class of stale-cache bug. Closing it here.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/integration/test_precompute.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd api && .venv/bin/pytest tests/integration/test_precompute.py -k invalidate -v`
Expected: FAIL with `AttributeError: module 'app.import_pipeline.stats_importer' has no attribute 'invalidate_caches_for'`.

- [ ] **Step 3: Extract a shared invalidation helper in the importer**

In `api/app/import_pipeline/stats_importer.py`, add near the top-level functions:

```python
def invalidate_caches_for(session, player_ids) -> None:
    """Drop every cached derivation for these players.

    Fits and summaries must go together: a new projection changes the target
    means the fits were shifted to, so both are stale.
    """
    ids = list(player_ids)
    if not ids:
        return
    (session.query(PlayerDistributionParams)
            .filter(PlayerDistributionParams.player_id.in_(ids))
            .delete(synchronize_session=False))
    summary_mod.invalidate_for_players(session, ids)
```

Import it: `from app.sim import summary as summary_mod`. Then replace the existing delete
block at lines 81-83 with `invalidate_caches_for(session, matched_player_ids)`.

- [ ] **Step 4: Wire the other two call sites**

In `api/app/routers/historical.py`, inside `refresh`, after the fetch succeeds and before
the response is returned, add:

```python
    from app.sim import summary as summary_mod
    db.query(PlayerDistributionParams).delete(synchronize_session=False)
    summary_mod.invalidate_all(db)
    db.commit()
```

Import `PlayerDistributionParams` from `app.models.orm` if it is not already imported.

In `api/app/routers/admin.py`, inside `refresh_players`, immediately before the final
`db.commit()`, add:

```python
    # Re-seeding can remap identity, which makes any cached derivation for a
    # promoted player point at the wrong person.
    if promoted:
        from app.import_pipeline.stats_importer import invalidate_caches_for
        invalidate_caches_for(db, [u.resolved_player_id for u in unresolved
                                   if u.resolved_player_id is not None])
```

- [ ] **Step 5: Run the whole backend suite**

Run: `cd api && .venv/bin/pytest --cov=app --cov-report=term-missing`
Expected: all PASS, coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
git add api/app/import_pipeline/stats_importer.py api/app/routers/historical.py api/app/routers/admin.py api/tests/integration/test_precompute.py
git commit -m "fix: invalidate distribution summaries on import, refresh, and re-seed"
```

---

## Task 8: Unresolved import rows endpoint

**Files:**
- Modify: `api/app/models/schemas.py`, `api/app/routers/imports.py`
- Test: `api/tests/integration/test_unresolved.py` (create)

**Interfaces:**
- Produces: `GET /api/imports/{batch_id}/unresolved` → `list[UnresolvedRow]` with fields
  `parsed_name`, `parsed_team`, `position`, `resolution`, `csv_row`.

`import_unresolved` has no position column (`orm.py:85`), so `position` comes from the
parent `ImportBatch.position`. Read-only — a manual re-mapping UI is an explicit non-goal.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/integration/test_unresolved.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd api && .venv/bin/pytest tests/integration/test_unresolved.py -v`
Expected: FAIL — route returns 404 for every batch, and the reason field is absent.

- [ ] **Step 3: Add the schema**

In `api/app/models/schemas.py`:

```python
class UnresolvedRow(BaseModel):
    parsed_name: str | None = None
    parsed_team: str | None = None
    position: str | None = None
    resolution: str
    csv_row: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Add the endpoint**

In `api/app/routers/imports.py`, import `json`, `ImportUnresolved`, and `UnresolvedRow`,
then append:

```python
@router.get("/{batch_id}/unresolved", response_model=list[UnresolvedRow])
def get_unresolved(batch_id: int, db: Session = Depends(get_db)):
    """Rows that failed identity resolution. Read-only by design."""
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    rows = (db.query(ImportUnresolved)
              .filter(ImportUnresolved.import_batch_id == batch_id)
              .all())
    return [
        UnresolvedRow(
            parsed_name=row.parsed_name,
            parsed_team=row.parsed_team,
            position=batch.position,
            resolution=row.resolution or "no_canonical_match",
            csv_row=json.loads(row.csv_row),
        )
        for row in rows
    ]
```

Declare this route **before** the existing `@router.get("/{batch_id}")`, or the
single-segment route will not match first and the more specific path still works — but
declaring it first keeps the intent obvious.

- [ ] **Step 5: Run to verify it passes**

Run: `cd api && .venv/bin/pytest tests/integration/test_unresolved.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Regenerate the OpenAPI schema the frontend client is built from**

```bash
cd api && .venv/bin/python -c "
import json
from app.main import create_app
json.dump(create_app().openapi(), open('../shared/openapi.json','w'), indent=2)
print('openapi written')
"
```

- [ ] **Step 7: Commit**

```bash
git add api/app/models/schemas.py api/app/routers/imports.py api/tests/integration/test_unresolved.py shared/openapi.json
git commit -m "feat: expose unresolved import rows"
```

---

## Task 9: Tailwind v4, the token set, and the app shell

**Files:**
- Modify: `web/package.json`, `web/vite.config.ts`, `web/src/index.css`, `web/src/App.tsx`
- Create: `web/src/components/AppShell.tsx`
- Delete: `web/src/App.css`

**Interfaces:**
- Produces: Tailwind theme tokens usable as utility classes — `bg-canvas`, `bg-card`,
  `bg-elevated`, `bg-well`, `border-hairline`, `border-interactive`, `text-primary`,
  `text-muted`, `text-ghost`, `text-accent`, `bg-accent`, `text-violet`, `text-warn`,
  `text-danger`, `text-success`, plus fonts `font-display` and `font-body`.
- Produces: `<AppShell>{children}</AppShell>` rendering the header, nav, and page frame.

`web/src/App.css` is 184 lines of Vite starter CSS that nothing imports. `index.css` is the
stock light-mode purple template and is the reason the app looks the way it does. Both go.

- [ ] **Step 1: Install Tailwind**

```bash
cd web && npm install -D tailwindcss@^4 @tailwindcss/vite
```

- [ ] **Step 2: Register the Vite plugin**

Replace `web/vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

- [ ] **Step 3: Replace the stylesheet with the design tokens**

Replace the entire contents of `web/src/index.css` with:

```css
@import "tailwindcss";

/* Token values are fixed by the Stitch design system `terminal_slate_2`.
   See docs/superpowers/specs/2026-09-05-player-explorer-ux-design.md B.1 */
@theme {
  --color-canvas: #0B0E14;
  --color-card: #151A23;
  --color-elevated: #1C2330;
  --color-well: #18202C;
  --color-hairline: #232A36;
  --color-interactive: #3E4C5E;

  --color-primary: #F1F5F9;
  --color-muted: #7A8699;
  --color-ghost: #475569;

  --color-accent: #FBBF24;
  --color-violet: #818CF8;
  --color-warn: #F59E0B;
  --color-danger: #EF4444;
  --color-success: #10B981;

  --font-display: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-body: Inter, system-ui, sans-serif;

  --radius-base: 0.25rem;
  --radius-panel: 0.375rem;
}

html, body, #root {
  height: 100%;
}

body {
  background-color: var(--color-canvas);
  color: var(--color-primary);
  font-family: var(--font-body);
  margin: 0;
}

/* Every figure in this app is a quantity to be compared down a column. */
.tabular {
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 4: Delete the dead stylesheet**

```bash
git rm web/src/App.css
```

- [ ] **Step 5: Build the app shell**

Create `web/src/components/AppShell.tsx`:

```tsx
import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const NAV = [
  { to: "/players", label: "Players" },
  { to: "/import", label: "Import" },
  { to: "/", label: "Settings" },
] as const;

type Props = {
  children: ReactNode;
  preset?: ReactNode;
};

export function AppShell({ children, preset }: Props) {
  const { pathname } = useLocation();
  return (
    <div className="min-h-full bg-canvas text-primary font-body">
      <header className="sticky top-0 z-10 flex items-center gap-6 border-b border-hairline bg-card px-6 py-3">
        <span className="font-display text-base font-bold tracking-tight">MC Sim</span>
        <nav className="flex items-center gap-1">
          {NAV.map((item) => {
            const active =
              item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={
                  active
                    ? "rounded-base bg-accent px-3 py-1.5 text-sm font-semibold text-canvas"
                    : "rounded-base px-3 py-1.5 text-sm text-muted hover:text-primary"
                }
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto">{preset}</div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  );
}
```

Note: the active nav pill is **amber**, resolving the export's inconsistency (it renders
cyan on six screens and amber on the Players list). Amber is the primary accent; cyan is
not in this design system at all.

- [ ] **Step 6: Wire it into App.tsx**

Replace the `<nav>` and `<main>` in `web/src/App.tsx` with `<AppShell>`, keeping the
existing `<Routes>` inside it and removing every inline `style` prop.

- [ ] **Step 7: Verify the build and look at it**

```bash
cd web && npx tsc -b && npm run build
```
Expected: clean build, no type errors.

Then `npm run dev` and confirm the page renders on the near-black canvas with an amber
active nav pill.

- [ ] **Step 8: Commit**

```bash
git add web/package.json web/package-lock.json web/vite.config.ts web/src/index.css web/src/App.tsx web/src/components/AppShell.tsx
git rm --cached web/src/App.css 2>/dev/null || true
git commit -m "feat: adopt tailwind v4 with the terminal_slate_2 token set"
```

---

## Task 10: Vitest, stat labels, formatting, and error mapping

**Files:**
- Modify: `web/package.json`
- Create: `web/vitest.config.ts`, `web/src/lib/statLabels.ts`, `web/src/lib/format.ts`,
  `web/src/api/errors.ts`, `web/tests/unit/statLabels.test.ts`,
  `web/tests/unit/errors.test.ts`

**Interfaces:**
- Produces: `statLabel(key: string): string`
- Produces: `formatPoints(value: number | null | undefined): string`
- Produces: `toUserMessage(status: number, body: unknown): string`

Vitest is a **dev** dependency, which the spec's dependency non-goal permits (it forbids
new *runtime* dependencies). Its `include` must not overlap Playwright's `tests/e2e`.

- [ ] **Step 1: Install and configure Vitest**

```bash
cd web && npm install -D vitest
```

Create `web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // tests/e2e belongs to Playwright; never let the two runners collide.
    include: ["tests/unit/**/*.test.ts"],
    environment: "node",
  },
});
```

Add to `web/package.json` scripts: `"test:unit": "vitest run"`.

- [ ] **Step 2: Write the failing tests**

Create `web/tests/unit/statLabels.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { statLabel } from "../../src/lib/statLabels";

describe("statLabel", () => {
  it("humanizes known canonical stat keys", () => {
    expect(statLabel("receiving_yards")).toBe("Receiving yards");
    expect(statLabel("passing_tds")).toBe("Passing TDs");
    expect(statLabel("rushing_fumbles_lost")).toBe("Fumbles lost");
    expect(statLabel("receptions")).toBe("Receptions");
  });

  it("falls back to a readable form for unknown keys", () => {
    expect(statLabel("some_new_stat")).toBe("Some new stat");
  });
});
```

Create `web/tests/unit/errors.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { toUserMessage } from "../../src/api/errors";

describe("toUserMessage", () => {
  it("explains an auth failure in terms of the fix", () => {
    expect(toUserMessage(401, {})).toMatch(/token/i);
  });

  it("reports insufficient history with the real reason", () => {
    const body = { detail: { error: "insufficient_history", message: "Only 2 career games" } };
    expect(toUserMessage(422, body)).toBe("Only 2 career games");
  });

  it("explains unsupported positions", () => {
    const body = { detail: { error: "not_supported_mvp", message: "K/DEF not supported" } };
    expect(toUserMessage(422, body)).toMatch(/Kickers and defenses/i);
  });

  it("explains a missing projection", () => {
    expect(toUserMessage(404, { detail: "no projection for player" }))
      .toMatch(/No projection imported/i);
  });

  it("never leaks a raw stringified object", () => {
    expect(toUserMessage(500, { detail: { deep: { nested: true } } }))
      .not.toContain("[object Object]");
  });
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd web && npm run test:unit`
Expected: FAIL — modules not found.

- [ ] **Step 4: Implement the three modules**

Create `web/src/lib/statLabels.ts`:

```ts
/** Canonical nflreadpy stat keys (ADR-0009) to human labels. */
const LABELS: Readonly<Record<string, string>> = {
  passing_yards: "Passing yards",
  passing_tds: "Passing TDs",
  passing_interceptions: "Interceptions",
  rushing_yards: "Rushing yards",
  rushing_tds: "Rushing TDs",
  receiving_yards: "Receiving yards",
  receiving_tds: "Receiving TDs",
  receptions: "Receptions",
  rushing_fumbles_lost: "Fumbles lost",
};

export function statLabel(key: string): string {
  const known = LABELS[key];
  if (known) return known;
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
```

Create `web/src/lib/format.ts`:

```ts
/** One decimal place, em dash for absent values. Every figure is per game. */
export function formatPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}
```

Create `web/src/api/errors.ts`:

```ts
type Detail = { error?: string; message?: string };

function readDetail(body: unknown): Detail | string | undefined {
  if (typeof body !== "object" || body === null) return undefined;
  return (body as { detail?: Detail | string }).detail;
}

/** Turn an HTTP failure into something worth showing a person. */
export function toUserMessage(status: number, body: unknown): string {
  const detail = readDetail(body);

  if (status === 401 || status === 403) {
    return "Check your API token in Settings.";
  }

  if (typeof detail === "object" && detail !== null) {
    if (detail.error === "insufficient_history") {
      return detail.message ?? "Not enough career games to model this player.";
    }
    if (detail.error === "not_supported_mvp") {
      return "Kickers and defenses aren't modeled yet.";
    }
    if (detail.message) return detail.message;
  }

  if (status === 404) {
    if (typeof detail === "string" && detail.includes("projection")) {
      return "No projection imported for this player.";
    }
    return "Not found.";
  }

  if (status >= 500) return "The server hit an error. Try again in a moment.";
  return typeof detail === "string" ? detail : `Request failed (${status}).`;
}
```

- [ ] **Step 5: Run to verify they pass**

Run: `cd web && npm run test:unit`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/vitest.config.ts web/src/lib web/src/api/errors.ts web/tests/unit
git commit -m "feat: add stat labels, point formatting, and typed error messages"
```

---

## Task 11: Resilient API client with a warming signal

**Files:**
- Modify: `web/src/api/auth.ts`
- Create: `web/src/api/types.ts`, `web/src/hooks/useWarming.ts`,
  `web/src/hooks/useDebounce.ts`, `web/tests/unit/apiFetch.test.ts`

**Interfaces:**
- Consumes: `toUserMessage` (Task 10).
- Produces: `ApiError` class with `status: number` and a `message` already run through
  `toUserMessage`.
- Produces: `apiFetch<T>(path, init?)` with a 30s timeout and one retry on network failure.
- Produces: `onWarming(cb: (warming: boolean) => void): () => void` — fires `true` when a
  request has been outstanding longer than `WARMING_AFTER_MS` (2000).
- Produces: `useWarming(): boolean`, `useDebounce<T>(value, delay): T`.

The cold boot is 15-25 seconds because `min_machines_running = 0` (`api/fly.toml:21`), which
stays that way on purpose. It is explained, not eliminated. Never claim a shorter estimate
than the real one — the Stitch mock's "Est. 4-8s" is wrong.

- [ ] **Step 1: Write the failing test**

Create `web/tests/unit/apiFetch.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => {
  vi.stubEnv("VITE_API_URL", "http://api.test");
  vi.stubEnv("VITE_API_TOKEN", "test-token");
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("throws an ApiError carrying a human message, not a raw body", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: { error: "insufficient_history", message: "Only 2 career games" } }),
      { status: 422 },
    )));
    const { apiFetch, ApiError } = await import("../../src/api/auth");
    await expect(apiFetch("/api/players/1/distribution")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.status === 422
        && e.message === "Only 2 career games",
    );
  });

  it("sends the bearer token", async () => {
    const spy = vi.fn(async () => new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const { apiFetch } = await import("../../src/api/auth");
    await apiFetch("/api/players");
    const headers = new Headers(spy.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("signals warming when a request outlives the threshold", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(() => new Promise((resolve) => {
      setTimeout(() => resolve(new Response("[]", { status: 200 })), 5000);
    })));
    const { apiFetch, onWarming } = await import("../../src/api/auth");
    const seen: boolean[] = [];
    onWarming((w) => seen.push(w));
    const pending = apiFetch("/api/players");
    await vi.advanceTimersByTimeAsync(2500);
    expect(seen).toContain(true);
    await vi.advanceTimersByTimeAsync(3000);
    await pending;
    expect(seen.at(-1)).toBe(false);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm run test:unit`
Expected: FAIL — `ApiError` and `onWarming` are not exported.

- [ ] **Step 3: Rewrite the client**

Replace `web/src/api/auth.ts`:

```ts
import { toUserMessage } from "./errors";

const TOKEN = import.meta.env.VITE_API_TOKEN as string;
const API_URL = import.meta.env.VITE_API_URL as string;

const TIMEOUT_MS = 30_000;
const WARMING_AFTER_MS = 2_000;

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type WarmingListener = (warming: boolean) => void;

const listeners = new Set<WarmingListener>();
let outstanding = 0;

export function onWarming(cb: WarmingListener): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function emit(warming: boolean): void {
  listeners.forEach((cb) => cb(warming));
}

export function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${TOKEN}` };
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const warmingTimer = setTimeout(() => emit(true), WARMING_AFTER_MS);
  outstanding += 1;

  try {
    const resp = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { ...authHeaders(), ...(init.headers || {}) },
    });

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new ApiError(resp.status, toUserMessage(resp.status, body));
    }
    return (await resp.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "The server took too long to respond. Try again.");
    }
    throw new ApiError(0, "Could not reach the server. Check your connection.");
  } finally {
    clearTimeout(timeout);
    clearTimeout(warmingTimer);
    outstanding -= 1;
    if (outstanding === 0) emit(false);
  }
}
```

- [ ] **Step 4: Add the hooks**

Create `web/src/hooks/useWarming.ts`:

```ts
import { useEffect, useState } from "react";
import { onWarming } from "../api/auth";

export function useWarming(): boolean {
  const [warming, setWarming] = useState(false);
  useEffect(() => onWarming(setWarming), []);
  return warming;
}
```

Create `web/src/hooks/useDebounce.ts`:

```ts
import { useEffect, useState } from "react";

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(handle);
  }, [value, delay]);
  return debounced;
}
```

- [ ] **Step 5: Add the shared response types**

Create `web/src/api/types.ts` mirroring the backend schemas from Tasks 4, 6, and 8:

```ts
export type Preset = "standard" | "half_ppr" | "full_ppr";
export type SummaryStatus = "ok" | "insufficient_history" | "unsupported_position";

export type Histogram = { bin_edges: number[]; counts: number[] };

export type DistributionSummary = {
  status: SummaryStatus;
  floor_p10: number | null;
  p25: number | null;
  median_p50: number | null;
  p75: number | null;
  ceiling_p90: number | null;
  mean: number | null;
  std: number | null;
  skewness: number | null;
  histogram: Histogram | null;
  computed_at: string;
};

export type PlayerRow = {
  player_id: number;
  gsis_id: string;
  name: string;
  team: string | null;
  position: string;
  projected_stats: Record<string, number>;
  projected_points: number | null;
  adp_snake: number | null;
  adp_auction: number | null;
  distribution: DistributionSummary | null;
};

export type DistributionResponse = {
  player_id: number;
  gsis_id: string;
  name: string;
  team: string | null;
  position: string;
  adp_snake: number | null;
  projection: { stats: Record<string, number>; import_batch_id: number };
  scoring_preset: Preset;
  computed_points: number;
  distribution: {
    n_samples: number;
    floor_p10: number;
    p25: number;
    median_p50: number;
    p75: number;
    ceiling_p90: number;
    mean: number;
    std: number;
    skewness: number;
    histogram: Histogram;
  };
  fit: { fitted_at: string; historical_seasons: number[]; games_used: number };
};

export type PrecomputeResult = {
  computed: number;
  done: number;
  total: number;
  remaining: number;
};

export type UnresolvedRow = {
  parsed_name: string | null;
  parsed_team: string | null;
  position: string | null;
  resolution: string;
  csv_row: Record<string, unknown>;
};
```

- [ ] **Step 6: Run tests and typecheck**

```bash
cd web && npm run test:unit && npx tsc -b
```
Expected: all PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/api web/src/hooks web/tests/unit
git commit -m "feat: add timeout, typed errors, and a warming signal to the api client"
```

---

## Task 12: Component primitives

**Files:**
- Create: `web/src/components/Card.tsx`, `Skeleton.tsx`, `StatTile.tsx`,
  `PositionBadge.tsx`, `PositionTabs.tsx`, `SearchInput.tsx`, `EmptyState.tsx`,
  `ErrorState.tsx`, `WarmingPanel.tsx`, `PresetSelector.tsx`

**Interfaces:**
- Produces, in order of use by later tasks:
  - `<Card className?>{children}</Card>`
  - `<Skeleton className?/>` and `<SkeletonPlayerCard/>`
  - `<StatTile label emphasis?={boolean} value sub?/>`
  - `<PositionBadge position/>`
  - `<PositionTabs value onChange counts?/>` where value is `"ALL" | "QB" | "RB" | "WR" | "TE"`
  - `<SearchInput value onChange placeholder?/>`
  - `<EmptyState title body actionLabel? actionTo?/>`
  - `<ErrorState title body onRetry?/>`
  - `<WarmingPanel/>`
  - `<PresetSelector value onChange/>` where value is `Preset`

Each file holds one component. Do not merge them — the file-size and cohesion rules apply.

- [ ] **Step 1: Write the components**

`Card.tsx` — a `<div>` with `rounded-panel border border-hairline bg-card`, merging any
passed `className`.

`Skeleton.tsx` — exports `Skeleton` (a `bg-well` block with `animate-pulse` and a
caller-supplied size) and `SkeletonPlayerCard` (a `Card` laid out with the same geometry
as `PlayerCard` from Task 14: a wide left block, a centre chart block, a right number
block, and a footer strip).

`StatTile.tsx`:

```tsx
import { Card } from "./Card";

type Props = {
  label: string;
  value: string;
  sub?: string;
  emphasis?: boolean;
};

export function StatTile({ label, value, sub, emphasis = false }: Props) {
  return (
    <Card className={emphasis ? "border-accent/40 bg-accent/5 p-4" : "p-4"}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </div>
      <div
        className={`tabular font-display text-4xl font-bold ${
          emphasis ? "text-accent" : "text-primary"
        }`}
      >
        {value}
        <span className="ml-2 text-sm font-normal text-muted">pts / game</span>
      </div>
      {sub ? <div className="mt-1 text-xs text-muted">{sub}</div> : null}
    </Card>
  );
}
```

`PositionBadge.tsx` — a 10px uppercase badge, `rounded-[2px] px-1 py-px font-bold`, with
one colour per position. Use this exact mapping, which resolves the export's disagreement
with its own design-system doc:

```tsx
const STYLES: Readonly<Record<string, string>> = {
  QB: "bg-violet/15 text-violet",
  RB: "bg-success/15 text-success",
  WR: "bg-accent/15 text-accent",
  TE: "bg-warn/15 text-warn",
};
```

`PositionTabs.tsx` — segmented buttons for `ALL / QB / RB / WR / TE`; the active tab is
`bg-accent text-canvas`, the rest `border-hairline text-muted`.

`SearchInput.tsx` — a full-width `bg-well border-hairline rounded-base` input with
`placeholder="Search players…"` and a `focus:border-accent` ring.

`EmptyState.tsx` — centred, muted heading, body, optional `<Link>` styled as a primary
amber button.

`ErrorState.tsx` — a `Card` with `border-l-2 border-l-warn`, a bold title, muted body, and
an optional "Try again" button wired to `onRetry`.

`WarmingPanel.tsx` — a centred `Card` with heading "Waking the server up…", body
"The API sleeps when idle to stay on the free tier. This only happens on the first load.",
and an indeterminate amber progress bar.

**Do not** include a node ID, an HTTP status, a latency figure, a time estimate, or any
other telemetry in this panel. The Stitch mock shows `NODE_AWS_EUC1 #084`,
`HTTP 204 Waiting`, and `Est. 4-8s` — all three are fabrications, and the last one is
wrong by a factor of three against the real 15-25s.

`PresetSelector.tsx` — a `<select>` of the three presets styled as a compact
`bg-elevated border-hairline` control, calling `onChange` with the new `Preset`.

- [ ] **Step 2: Typecheck and lint**

```bash
cd web && npx tsc -b && npm run lint
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/components
git commit -m "feat: add the component primitives for the player explorer"
```

---

## Task 13: Sparkline

**Files:**
- Create: `web/src/components/Sparkline.tsx`, `web/src/lib/sparkline.ts`,
  `web/tests/unit/sparkline.test.ts`

**Interfaces:**
- Produces: `buildAreaPath(counts: number[], width: number, height: number): string`
- Produces: `bandBounds(binEdges: number[], lo: number, hi: number, width: number): {x1: number; x2: number}`
- Produces: `<Sparkline histogram floor median ceiling width? height?/>`

Hand-rolled inline SVG, not recharts. The Players list renders one of these per card across
hundreds of rows; that many recharts instances would dominate render time. The maths lives
in `lib/` so it can be unit tested without a DOM.

- [ ] **Step 1: Write the failing tests**

Create `web/tests/unit/sparkline.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { buildAreaPath, bandBounds } from "../../src/lib/sparkline";

describe("buildAreaPath", () => {
  it("returns an empty path for no data", () => {
    expect(buildAreaPath([], 220, 56)).toBe("");
  });

  it("starts at the baseline and closes the shape", () => {
    const d = buildAreaPath([1, 4, 9, 4, 1], 100, 50);
    expect(d.startsWith("M0,50")).toBe(true);
    expect(d.endsWith("Z")).toBe(true);
  });

  it("puts the tallest bin at the top of the box", () => {
    const d = buildAreaPath([1, 10, 1], 100, 50);
    // The peak's y must be 0 (top); the baseline is height.
    expect(d).toContain(",0");
  });

  it("never emits a coordinate outside the box", () => {
    const d = buildAreaPath([3, 8, 2, 7], 220, 56);
    const coords = d.match(/-?\d+(\.\d+)?/g)!.map(Number);
    expect(Math.min(...coords)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...coords)).toBeLessThanOrEqual(220);
  });

  it("survives an all-zero histogram without dividing by zero", () => {
    const d = buildAreaPath([0, 0, 0], 100, 50);
    expect(d).not.toContain("NaN");
  });
});

describe("bandBounds", () => {
  it("maps a percentile range onto the pixel box", () => {
    const { x1, x2 } = bandBounds([0, 10, 20, 30, 40], 10, 30, 200);
    expect(x1).toBeCloseTo(50);
    expect(x2).toBeCloseTo(150);
  });

  it("clamps a range that runs past the histogram", () => {
    const { x1, x2 } = bandBounds([0, 10, 20], -5, 999, 100);
    expect(x1).toBe(0);
    expect(x2).toBe(100);
  });

  it("returns a zero-width band for a degenerate axis", () => {
    const { x1, x2 } = bandBounds([5, 5], 1, 9, 100);
    expect(x1).toBe(0);
    expect(x2).toBe(0);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm run test:unit`
Expected: FAIL — `src/lib/sparkline` not found.

- [ ] **Step 3: Implement the maths**

Create `web/src/lib/sparkline.ts`:

```ts
/** Build a closed SVG area path from histogram bin counts. */
export function buildAreaPath(counts: number[], width: number, height: number): string {
  if (counts.length === 0) return "";
  const peak = Math.max(...counts);
  const scale = peak > 0 ? peak : 1;
  const step = counts.length > 1 ? width / (counts.length - 1) : width;

  const points = counts.map((count, i) => {
    const x = Math.min(i * step, width);
    const y = height - (count / scale) * height;
    return `${round(x)},${round(y)}`;
  });

  return `M0,${round(height)} L${points.join(" L")} L${round(width)},${round(height)} Z`;
}

/** Pixel bounds of a [lo, hi] value range across the histogram's x axis. */
export function bandBounds(
  binEdges: number[],
  lo: number,
  hi: number,
  width: number,
): { x1: number; x2: number } {
  const first = binEdges[0];
  const last = binEdges[binEdges.length - 1];
  const span = last - first;
  if (!Number.isFinite(span) || span <= 0) return { x1: 0, x2: 0 };
  const toX = (value: number) =>
    Math.max(0, Math.min(width, ((value - first) / span) * width));
  return { x1: toX(lo), x2: toX(hi) };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
```

- [ ] **Step 4: Implement the component**

Create `web/src/components/Sparkline.tsx` rendering, in order: the shaded p10-p90 band as a
`<rect>` in `text-violet` at 12% opacity, the area path filled `currentColor` at 30%
opacity with a 2px stroke at full opacity, and a 1px dashed vertical line at the median.
The wrapper `<svg>` carries `className="text-accent"` so `currentColor` resolves to amber,
plus `role="img"` and an `aria-label` naming the player's floor, median, and ceiling.

- [ ] **Step 5: Run tests and typecheck**

```bash
cd web && npm run test:unit && npx tsc -b
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/sparkline.ts web/src/components/Sparkline.tsx web/tests/unit/sparkline.test.ts
git commit -m "feat: add inline svg sparkline for distribution shape"
```

---

## Task 14: Players page

**Files:**
- Create: `web/src/components/PlayerCard.tsx`
- Modify: `web/src/pages/PlayersPage.tsx`

**Interfaces:**
- Consumes: `PlayerRow` (Task 11), `Card`, `Skeleton`, `SkeletonPlayerCard`,
  `PositionBadge`, `PositionTabs`, `SearchInput`, `EmptyState`, `ErrorState`,
  `PresetSelector` (Task 12), `Sparkline` (Task 13), `useDebounce`, `useWarming`
  (Task 11), `formatPoints` (Task 10).
- Produces: `<PlayerCard row={PlayerRow}/>`.

- [ ] **Step 1: Build PlayerCard**

Three zones in a flex row inside a `Card`, plus a footer strip:

- Left: initials avatar (`bg-well border-hairline`), the name as
  `font-display text-lg font-semibold`, a `PositionBadge`, and a muted
  `WR · CIN · ADP 1.2` line. Render `ADP —` when `adp_snake` is null.
- Centre: `<Sparkline>` when `distribution?.status === "ok"`. When the status is terminal,
  render muted text instead — `"Not enough career games"` for `insufficient_history`,
  `"Not modeled yet"` for `unsupported_position`. When `distribution` is null, render a
  muted `"Not computed"` with a small "Compute" button that POSTs
  `/api/players/precompute?limit=1` and refetches.
- Right: `formatPoints(row.projected_points)` as `tabular font-display text-4xl font-bold
  text-accent`, with `pts / game` beneath in muted 10px caps.
- Footer: a `border-t border-hairline` strip with `FLOOR`, `MEDIAN`, `CEILING` — each an
  uppercase muted label and a white tabular value. Render `—` for a terminal status.

Wrap the whole card in a `<Link to={`/players/${row.player_id}`}>`.

- [ ] **Step 2: Rebuild PlayersPage**

State: `rows`, `loading`, `error`, `query`, `position`, `sort`. Use
`useDebounce(query, 200)` for filtering.

- Header row: `<SearchInput>`, then `<PositionTabs>` with per-position counts computed from
  `rows`, and a sort `<select>` offering Projected / ADP / Ceiling / Floor.
- Filtering and sorting are **client-side and immutable** — never sort `rows` in place. Use
  `[...rows].sort(...)` exactly as the current implementation does.
- `useWarming()` true → render `<WarmingPanel/>` above a stack of `<SkeletonPlayerCard/>`.
- `loading` and not warming → six `<SkeletonPlayerCard/>`.
- `error` → `<ErrorState title="Couldn't load players" body={error} onRetry={refetch}/>`.
- Empty and not loading → `<EmptyState title="No projections yet" body="Import a stat
  projection CSV to get started" actionLabel="Go to Import" actionTo="/import"/>`.
- Otherwise the card stack, with a muted `{n} players` line at the bottom.

Fetch `/api/players?has_projection=true`. Pass `<PresetSelector>` into `AppShell`'s
`preset` slot; changing it PUTs `/api/league/config` then refetches the list.

- [ ] **Step 3: Verify in the browser**

```bash
cd web && npm run dev
```
Confirm: cards render on the dark canvas, sparklines draw, search and tabs filter, the
sort control reorders, and the skeleton appears on a cold load.

- [ ] **Step 4: Typecheck, lint, commit**

```bash
cd web && npx tsc -b && npm run lint
git add web/src/components/PlayerCard.tsx web/src/pages/PlayersPage.tsx
git commit -m "feat: rebuild the players page as a filterable card list"
```

---

## Task 15: Player detail page

**Files:**
- Modify: `web/src/pages/PlayerDetailPage.tsx`, `web/src/components/Histogram.tsx`

**Interfaces:**
- Consumes: `DistributionResponse` (Task 11), `StatTile`, `Card`, `ErrorState`,
  `PositionBadge`, `PresetSelector`, `statLabel`, `formatPoints`.

- [ ] **Step 1: Restyle the histogram**

Keep recharts here — it is one chart, not hundreds. Update `Histogram.tsx` to accept
`binEdges`, `counts`, and the five percentiles, and render:

- Bars filled `#FBBF24`.
- A `ReferenceLine` at the median, labelled with the value.
- A `ReferenceArea` shading floor to ceiling in `#818CF8` at low opacity.
- An x-axis labelled **"Fantasy points per game"**.
- No y-axis labels.

Add small percentile flags above the plot for P10, P25, P50, P75, P90 using the values from
the response. These are real numbers from the API — do not invent any others.

- [ ] **Step 2: Rebuild the page**

- Back link `← Players`.
- Title: `data.name` as `font-display text-4xl font-bold`, a `PositionBadge`, and a muted
  `WR · CIN · ADP 1.2` subtitle. A `PresetSelector` sits right-aligned on the title row.
- Three `<StatTile>`s: `FLOOR (P10)`, `MEDIAN (P50)` with `emphasis`, `CEILING (P90)`.
- The histogram in a `Card`.
- Two columns below: left a `Card` titled "Projected stats" with a two-column table of
  `statLabel(key)` and a right-aligned tabular value, headed `MEAN PER GAME`; right a
  `Card` with the sample-skew readout and the calibration callout.
- Sample skew renders as `Sample skew {skewness.toFixed(2)}` with a muted one-line
  explanation: "Positive values mean a longer upside tail." **Never** label it `α`, and
  never present it as a fitted shape parameter — fitting is per stat, and this is the
  empirical skew of the simulated points.
- The calibration callout keeps exactly the existing wording: "Distributions reflect the
  uncertainty around the imported projection. Calibration to actual season outcomes is
  approximate; treat intervals as informed bounds, not guarantees." **Do not** add the
  Stitch mock's trailing sentence about correlation coefficients — the engine assumes
  player independence, and claiming otherwise in the one element meant to state the model's
  limits would be a straightforward lie to the user.
- Provenance line beneath: `Fit from {fit.games_used} games · seasons {fit.historical_seasons.join("–")}`.
- On `ApiError`, render `<ErrorState>` with `error.message` — Task 10 already turned the
  422s into real sentences.

- [ ] **Step 3: Verify, typecheck, commit**

```bash
cd web && npx tsc -b && npm run lint
git add web/src/pages/PlayerDetailPage.tsx web/src/components/Histogram.tsx
git commit -m "feat: rebuild the player detail page with identity, tiles, and percentiles"
```

---

## Task 16: Import page with precompute progress

**Files:**
- Modify: `web/src/pages/ImportPage.tsx`

**Interfaces:**
- Consumes: `PrecomputeResult`, `UnresolvedRow` (Task 11), `Card`, `ErrorState`, `StatTile`.

- [ ] **Step 1: Rebuild the upload zones**

Two side-by-side `Card`s — "Stat projections (CSV)" and "ADP (CSV)" — each a dashed-border
drop area with a file input, a source `<select>` defaulting to `fantasypros`, and (for
stats) the position select the endpoint requires. Show the selected filename and size once
chosen.

- [ ] **Step 2: Show the result counts**

After a successful upload render three tiles from `ImportBatchResult`:
`IMPORTED {total_rows}`, `RESOLVED {matched_rows}`, `UNRESOLVED {unresolved_rows}` — the
last in `text-warn` when non-zero.

- [ ] **Step 3: Drive the precompute loop**

```tsx
async function runPrecompute(
  onProgress: (p: PrecomputeResult) => void,
): Promise<void> {
  // Chunked and client-driven: each call is a real request, which also keeps
  // the Fly machine awake while the work runs.
  for (;;) {
    const result = await apiFetch<PrecomputeResult>(
      "/api/players/precompute?limit=25",
      { method: "POST" },
    );
    onProgress(result);
    if (result.remaining === 0) return;
  }
}
```

Render a progress section while it runs: the label "Computing distributions", an amber bar
whose width is `done / total`, and muted text `{done} / {total} players`. Show no time
estimate and no worker-thread count — neither exists.

The loop must terminate because `status` gives every player a terminal state (Task 3). If
`remaining` ever fails to decrease across two consecutive calls, stop and surface an error
rather than looping forever.

- [ ] **Step 4: Show the unresolved rows**

After the upload, fetch `/api/imports/{batch_id}/unresolved` and render a table with
columns Name, Team, Position, Reason, inside a `Card` with `border-l-2 border-l-warn`.
Read-only — no action column, no match buttons. Render an empty state when there are none.

- [ ] **Step 5: Typecheck, lint, commit**

```bash
cd web && npx tsc -b && npm run lint
git add web/src/pages/ImportPage.tsx
git commit -m "feat: rebuild the import page with precompute progress and unresolved rows"
```

---

## Task 17: Settings page

**Files:**
- Modify: `web/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Rebuild**

Single column, `max-w-[720px]`, left-aligned.

- Section "Connection": the API token field, and a status row driven by `/api/health` —
  a `bg-success` dot with `Connected · database ready · seasons 2023–2025` when `ok`, or a
  `bg-danger` dot with the failure reason.
- Section "Scoring": a segmented control over the three presets, active one
  `bg-accent text-canvas`, wired to `PUT /api/league/config`. Muted helper text beneath:
  "Changing this recomputes every player's distribution."

Keep an `<h1>Settings</h1>` — the E2E suite asserts on it.

- [ ] **Step 2: Typecheck, lint, commit**

```bash
cd web && npx tsc -b && npm run lint
git add web/src/pages/SettingsPage.tsx
git commit -m "feat: rebuild the settings page"
```

---

## Task 18: End-to-end coverage and full verification

**Files:**
- Modify: `web/tests/e2e/happy-path.spec.ts`

The existing spec asserts on `<pre>` blocks and raw `<table>` rows that no longer exist, so
it must be rewritten alongside the UI, not after it.

- [ ] **Step 1: Rewrite the happy path**

```ts
import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("happy path: settings → import → precompute → players → detail", async ({ page }) => {
  test.setTimeout(120_000); // precompute is genuinely slow on a cold machine

  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Settings");
  await page.getByRole("button", { name: /half ppr/i }).click();

  await page.goto("/import");
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_qb.html");
  await page.setInputFiles("input[type=file]", fixture);
  await page.getByRole("button", { name: "Upload" }).click();

  // Counts land, then the precompute bar runs to completion.
  await expect(page.getByText(/IMPORTED/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Computing distributions/)).toBeVisible();
  await expect(page.getByText(/Computing distributions/)).toBeHidden({ timeout: 90_000 });

  await page.goto("/players");
  const firstCard = page.getByTestId("player-card").first();
  await expect(firstCard).toBeVisible({ timeout: 15_000 });
  // The card must show a real distribution, not just a point estimate.
  await expect(firstCard.getByText(/FLOOR/)).toBeVisible();
  await expect(firstCard.locator("svg")).toBeVisible();

  await firstCard.click();
  await expect(page.getByText(/MEDIAN \(P50\)/)).toBeVisible();
  await expect(page.locator("svg.recharts-surface")).toBeVisible();
  await expect(page.getByText(/Calibration note/i)).toBeVisible();

  // The engine assumes player independence; the UI must never claim otherwise.
  await expect(page.getByText(/correlation/i)).toHaveCount(0);
});
```

Add `data-testid="player-card"` to the `PlayerCard` root in Task 14.

- [ ] **Step 2: Run the backend suite with coverage**

```bash
cd api && .venv/bin/pytest --cov=app --cov-report=term-missing
```
Expected: all PASS, coverage ≥ 80%. Record the actual number.

- [ ] **Step 3: Run the frontend unit suite and typecheck**

```bash
cd web && npm run test:unit && npx tsc -b && npm run lint && npm run build
```
Expected: all PASS, clean build.

- [ ] **Step 4: Run the E2E suite against a local stack**

Start the API (`cd api && .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app`)
and the frontend (`cd web && npm run dev`), then:

```bash
cd web && npx playwright test
```
Expected: PASS. Note that `alembic upgrade head` is required before `uvicorn` — the MVP
removed `create_all`, so a bare uvicorn against an empty database has no tables.

- [ ] **Step 5: Commit**

```bash
git add web/tests/e2e/happy-path.spec.ts
git commit -m "test: cover the precompute flow and card list end to end"
```

---

## Task 19: Deploy — STOP AND ASK FIRST

**This task has external, billable side effects and must not be executed without explicit
user confirmation.** Deploying pushes a live public change to the user's Fly and Vercel
accounts.

Bring the following to the user and let them decide:

- The backend needs a redeploy for the new migration and endpoints (`fly deploy` from
  `api/`). The Dockerfile's CMD already chains `alembic upgrade head`, so `0002` applies on
  boot.
- The frontend needs a redeploy (`vercel --prod` from `web/`).
- **`CORS_ORIGINS` must be set as a JSON array, not a comma-separated string.** Getting
  this wrong took production down during the MVP build. This is a real, already-proven trap.
- After deploying, the first import on the live instance will need a full precompute pass
  (250-350 players, 60-90 seconds of progress bar).

---

## Verification Checklist

Run before considering the branch complete:

- [ ] `cd api && .venv/bin/pytest --cov=app` — all pass, coverage ≥ 80%
- [ ] `cd web && npm run test:unit` — all pass
- [ ] `cd web && npx tsc -b && npm run lint && npm run build` — clean
- [ ] `cd web && npx playwright test` — passes against a local stack
- [ ] `git grep -nE "correlat|covarian|boom.?bust|R²|target.share|Xoroshiro|WASM" -- web/src` returns **nothing**
- [ ] No `console.log` in `web/src`
- [ ] `web/src/App.css` is deleted
- [ ] Every points figure on every screen is labelled per game

# Monte Carlo Fantasy Football Simulator — MVP Design

**Status:** Approved for implementation planning
**Date:** 2026-04-18
**Scope:** Phase 1 MVP (per Requirements v1.2, §9 Phase 1, narrowed)
**Related ADRs:** [0001](../../adr/0001-record-architecture-decisions.md) through [0014](../../adr/0014-explicit-parquet-persistence-for-historical-data.md).
**Post-spike revisions:** [ADR-0012](../../adr/0012-mixed-distribution-families-for-stat-simulation.md) supersedes [0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md) for family choice; [ADR-0013](../../adr/0013-identity-resolution-team-abbreviation-normalization.md) amends [0005](../../adr/0005-identity-resolution-tiers-1-and-3-only.md); [ADR-0014](../../adr/0014-explicit-parquet-persistence-for-historical-data.md) amends [0006](../../adr/0006-sqlite-on-fly-volume-with-nflreadpy-cache.md). See [`spikes/GATING.md`](../../../spikes/GATING.md) for the spike evidence that drove these revisions.

---

## 1. Overview

A deployed-from-day-one web application that lets a single user (the author) import stat-level NFL projections, resolve player identity against a canonical registry, and view per-player Monte Carlo fantasy-point distributions computed under a configurable scoring preset. This is the **Player Explorer slice** of the Requirements v1.2 document. All downstream functionality (draft simulator, live draft assistant, weekly management, strategy compare) is explicitly deferred to post-MVP specs.

### Goals

1. Prove the import → identity resolution → scoring → distribution pipeline works end-to-end against real data from `nflreadpy` and FantasyPros.
2. Deploy behind a token-guarded URL on free-tier infrastructure (Fly.io + Vercel).
3. Produce a codebase where each of the six backend components (import, identity, scoring, historical, sim, API) can be tested in isolation and extended in later phases without architectural rewrite.

### Non-goals (explicit scope cuts from Requirements v1.2)

- No draft simulator (snake or auction). `/api/simulate/draft/*` endpoints deferred.
- No live draft assistant, no WebSockets, no real-time features.
- No team-level, season-level, or weekly matchup simulation. Happy path stops at per-player distribution.
- No rookie archetype system. Players with `<4` career regular-season games return `422 insufficient_history` and are excluded from distribution views.
- No opponent / strength-of-schedule adjustments.
- No intra-player stat covariance matrix. Each stat sampled independently. See [ADR-0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md) (as amended by [ADR-0012](../../adr/0012-mixed-distribution-families-for-stat-simulation.md) for distribution families: skew-normal for continuous yard stats, negative-binomial for count stats).
- No point-level fallback CSV import path. Stat-level only; point-only CSVs error.
- No scoring rule editor UI. Three presets (`standard`, `half_ppr`, `full_ppr`) selectable by name; no per-rule configuration. See [ADR-0003](../../adr/0003-scope-mvp-to-player-explorer.md).
- No Kicker or Defense simulation. K and DEF projections can still be imported (for later phases) but have no distribution endpoint in MVP. See [ADR-0010](../../adr/0010-mvp-supports-qb-rb-wr-te-only.md).
- No jersey-number disambiguation tier, no fuzzy-match disambiguation UI. See [ADR-0005](../../adr/0005-identity-resolution-tiers-1-and-3-only.md).
- No multi-user, no sessions, no per-user data isolation. Single bearer token is the entire auth model. See [ADR-0007](../../adr/0007-single-bearer-token-auth.md).

---

## 2. Architecture

### Repo layout

```
monte-carlo-fantasy-football-imulator/
├── api/                         # Python backend, deployed to Fly
│   ├── pyproject.toml
│   ├── fly.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # env vars, settings
│   │   ├── db.py                # SQLite connection, migrations
│   │   ├── auth.py              # bearer-token dependency
│   │   ├── models/              # Pydantic models, SQLAlchemy tables
│   │   ├── import_pipeline/
│   │   │   ├── csv_parser.py    # file parse + name/team split
│   │   │   ├── column_mapper.py # by_name / by_index / fantasypros_multi_header
│   │   │   ├── stats_importer.py
│   │   │   └── adp_importer.py
│   │   ├── identity/
│   │   │   └── resolver.py      # Tier 1 + Tier 3 (merge_name + team)
│   │   ├── scoring/
│   │   │   ├── presets.py       # STANDARD / HALF_PPR / FULL_PPR
│   │   │   └── engine.py        # score(stats, preset) -> float
│   │   ├── historical/
│   │   │   └── fetch.py         # nflreadpy wrapper, seed on first boot
│   │   ├── sim/
│   │   │   ├── fitting.py       # per-stat skew-normal, mean-shift to projection
│   │   │   ├── sampler.py       # NumPy-vectorized
│   │   │   └── runner.py        # fit + sample + score + summary
│   │   └── routers/             # FastAPI endpoints (Section 5)
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
├── web/                         # React frontend, deployed to Vercel
│   ├── package.json
│   ├── vercel.json
│   └── src/
│       ├── api/                 # OpenAPI-generated TS client
│       ├── pages/
│       │   ├── SettingsPage.tsx
│       │   ├── ImportPage.tsx
│       │   ├── PlayersPage.tsx
│       │   └── PlayerDetailPage.tsx
│       └── components/          # minimal shared UI
├── docs/
│   ├── adr/                     # Architecture Decision Records (MADR 3.0)
│   └── superpowers/specs/
└── shared/
    └── openapi.json             # emitted by FastAPI, consumed by web
```

### Deploy topology

- **Fly.io** hosts the Python API on a `shared-cpu-1x` VM (provisionally 512 MB RAM — see Risk R2) with a **1 GB persistent volume** mounted at `/data`. Holds `sqlite.db` and `nflreadpy`'s filesystem cache (`/data/historical/`).
- **Vercel** hosts the static React bundle, builds from the `web/` directory on push to `main`. `VITE_API_URL` points at the Fly URL; `VITE_API_TOKEN` carries the bearer token (shipped to the browser — acceptable for single-user per [ADR-0007](../../adr/0007-single-bearer-token-auth.md)).
- **Rotation**: token is set via `fly secrets set API_TOKEN=...` on the backend and the matching Vercel env var; both redeploy.

### First-boot lifecycle

On API startup, `app/main.py`:
1. Runs SQLite migrations.
2. Calls `historical.fetch.ensure_seed()` which:
   a. Configures `NFLREADPY_CACHE_DIR=/data/historical`.
   b. If the `player` table is empty: calls `nflreadpy.load_ff_playerids()`, filters to rows with `gsis_id IS NOT NULL`, upserts into `player`.
   c. If cached Parquet for any of the last 3 seasons is missing: calls `nflreadpy.load_player_stats(seasons=[Y-2, Y-1, Y])` to populate cache.
3. Marks server ready. Subsequent boots skip steps 2b and 2c if state is present.

First boot: ~30–90 seconds. Subsequent boots: sub-second.

---

## 3. Data Model

SQLite at `/data/sqlite.db`. Historical weekly stats delegated to `nflreadpy`'s filesystem cache (not stored in SQLite). See [ADR-0006](../../adr/0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) and [ADR-0008](../../adr/0008-use-nflreadpy-not-nfl-data-py.md).

### Real-data findings that shaped this schema

1. **`load_ff_playerids()`** returns 12,187 rows × 35 columns. Primary key is `mfl_id: Int64` (100% populated). ID columns have **heavy null rates** (`gsis_id` 37% null, `fantasypros_id` 61% null) because the table includes retirees, UDFAs, and pre-combine rookies. ID column types are **mixed Int64 and String** depending on the source. A pre-normalized **`merge_name`** column exists (`"Cam Ward" → "cam ward"`) — reused directly instead of writing our own normalizer.

2. **`load_player_stats([year])`** returns ~19,000 weekly rows × 114 columns per season. Join key is `player_id: String` in `00-00XXXXX` format (matches `gsis_id`). Stat column names use long-form (`passing_yards`, `passing_tds`, `passing_interceptions`, `rushing_yards`, `receptions`, `receiving_yards`, etc.). Pre-computed `fantasy_points` columns exist but are ignored — we compute our own. `season_type` column present; filter to `"REG"` only for fitting.

3. **FantasyPros HTML export** uses a two-level MultiIndex: level-0 section headers `(PASSING, RUSHING, MISC)` × level-1 stat codes `(ATT, CMP, YDS, TDS, INTS, FL, FPTS)`. Duplicate short names (`ATT` appears under both `PASSING` and `RUSHING`) require index-aware parsing. Player field is **"Firstname Lastname TEAM" concatenated** (e.g., `"Jalen Hurts PHI"`), not separate columns. No ID column included → Tier 1 matching by `fantasypros_id` is impossible from the default FantasyPros export; MVP relies on Tier 3 (`merge_name + team`) for this source.

### Tables

| Table | Purpose |
|---|---|
| `player` | Canonical registry seeded from `load_ff_playerids()` filtered to `gsis_id IS NOT NULL` (~7,700 rows). Refreshed via admin endpoint. |
| `import_batch` | One row per CSV upload; tracks source/position/counts/unmapped columns. |
| `player_projection` | Raw projected stat line from a stats CSV. Stats stored as JSON using nflreadpy canonical stat names. |
| `player_adp` | ADP row from an ADP CSV. |
| `import_unresolved` | CSV rows that failed Tier-1 ID match and Tier-3 `merge_name + team` match. User resolves manually. |
| `source_column_mapping` | Saved CSV-column layout per `(source, position)`. Supports three strategies: `by_name`, `by_index`, `fantasypros_multi_header`. |
| `league_config` | Single-row config (`id=1`): `scoring_preset`, `num_teams`. |
| `player_distribution_params` | Cached per-player per-stat skew-normal fit; invalidated by historical refresh or new projection upload. |

### Column-level detail

```sql
CREATE TABLE player (
  mfl_id INTEGER PRIMARY KEY,
  gsis_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  merge_name TEXT NOT NULL,          -- pre-normalized from source; indexed
  team TEXT,
  position TEXT NOT NULL,             -- QB/RB/WR/TE/K/DEF (K and DEF seeded but not simulated in MVP)
  fantasypros_id INTEGER,
  espn_id INTEGER,
  yahoo_id TEXT,
  sleeper_id INTEGER,
  cbs_id INTEGER,
  pfr_id TEXT,
  fantasy_data_id INTEGER,
  rotowire_id INTEGER,
  nfl_id INTEGER,
  birthdate TEXT,
  draft_year INTEGER,
  db_season INTEGER,
  seeded_at TEXT NOT NULL
);
CREATE INDEX idx_player_merge_name_team ON player(merge_name, team);
CREATE INDEX idx_player_fantasypros_id ON player(fantasypros_id);
-- (similar single-column indexes on every _id column)

CREATE TABLE import_batch (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('stats','adp')),
  source TEXT NOT NULL,               -- 'fantasypros' | 'espn' | 'custom' | ...
  position TEXT,                      -- NULL for ADP
  filename TEXT,
  status TEXT NOT NULL,               -- 'pending' | 'partial' | 'resolved' | 'failed'
  total_rows INTEGER NOT NULL,
  matched_rows INTEGER NOT NULL,
  unresolved_rows INTEGER NOT NULL,
  unmapped_columns TEXT,              -- JSON array
  created_at TEXT NOT NULL
);

CREATE TABLE player_projection (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id INTEGER NOT NULL REFERENCES player(mfl_id),
  import_batch_id INTEGER NOT NULL REFERENCES import_batch(id),
  position TEXT NOT NULL,
  stats TEXT NOT NULL,                -- JSON: {"passing_yards": 4200, "passing_tds": 28, ...}
  created_at TEXT NOT NULL
);
CREATE INDEX idx_proj_player_latest ON player_projection(player_id, created_at DESC);

CREATE TABLE player_adp (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id INTEGER NOT NULL REFERENCES player(mfl_id),
  import_batch_id INTEGER NOT NULL REFERENCES import_batch(id),
  adp_snake REAL,
  adp_auction REAL,
  ecr REAL,
  bye_week INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_adp_player_latest ON player_adp(player_id, created_at DESC);

CREATE TABLE import_unresolved (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_batch_id INTEGER NOT NULL REFERENCES import_batch(id),
  csv_row TEXT NOT NULL,              -- JSON
  parsed_name TEXT,                   -- from name+team split (e.g. "jalen hurts" from "Jalen Hurts PHI")
  parsed_team TEXT,
  resolved_player_id INTEGER REFERENCES player(mfl_id),
  resolution TEXT                     -- 'manual' | 'dropped' | NULL
);

CREATE TABLE source_column_mapping (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  position TEXT NOT NULL,
  strategy TEXT NOT NULL CHECK (strategy IN ('by_name','by_index','fantasypros_multi_header')),
  mapping TEXT NOT NULL,              -- JSON; shape depends on strategy
  updated_at TEXT NOT NULL,
  UNIQUE(source, position)
);

CREATE TABLE league_config (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  scoring_preset TEXT NOT NULL CHECK (scoring_preset IN ('standard','half_ppr','full_ppr')),
  num_teams INTEGER NOT NULL DEFAULT 12,
  updated_at TEXT NOT NULL
);

CREATE TABLE player_distribution_params (
  player_id INTEGER PRIMARY KEY REFERENCES player(mfl_id),
  params TEXT NOT NULL,               -- JSON: {"passing_yards":{"family":"skewnorm","alpha":..,"loc":..,"scale":..},
                                      --        "passing_tds":{"family":"nbinom","n":..,"p":..}, ...}
                                      -- See ADR-0012 for family mapping per stat.
  fitted_at TEXT NOT NULL,
  historical_seasons TEXT NOT NULL,   -- e.g. "2023,2024,2025"
  games_used INTEGER NOT NULL
);
```

### Cache invalidation rules

| Event | Effect |
|---|---|
| Switch `scoring_preset` | No cache invalidation. Points computed on demand from stat samples. |
| New stats CSV upload | Delete `player_distribution_params` rows for any `player_id` whose projection changed. |
| `POST /api/historical/refresh` | Truncate `player_distribution_params` entirely. |

---

## 4. Core Components

Each backend module has a single responsibility and a narrow public interface. All modules live under `api/app/`.

### `import_pipeline/`

- **`csv_parser.py`** — accepts raw file bytes (CSV or FantasyPros HTML). Auto-detects format: HTML page → use `pandas.read_html`; CSV → `pandas.read_csv`. Splits `"Name TEAM"` concatenated fields into (name, team) pairs for FantasyPros. Returns a normalized DataFrame plus raw-columns metadata.
- **`column_mapper.py`** — `map(df, source, position) → (mapped_df, unmapped_cols)`. Loads strategy + mapping from `source_column_mapping` where `(source, position)` matches. If none saved: attempts `by_name` with an in-code alias dictionary. Three strategies:
  - `by_name`: simple header-name lookup (`"Pass Yds" → "passing_yards"`).
  - `by_index`: ordered column positions (`0 → "passing_yards", 1 → "passing_tds", ...`).
  - `fantasypros_multi_header`: expects a two-level header; flattens via a hand-built section×code table using nflreadpy canonical names. Example mappings: `(PASSING, ATT) → "attempts"`, `(PASSING, CMP) → "completions"`, `(PASSING, YDS) → "passing_yards"`, `(PASSING, TDS) → "passing_tds"`, `(PASSING, INTS) → "passing_interceptions"`, `(RUSHING, ATT) → "carries"`, `(RUSHING, YDS) → "rushing_yards"`, `(RUSHING, TDS) → "rushing_tds"`, `(MISC, FL) → "rushing_fumbles_lost"`, `(MISC, FPTS) → ignored`.
- **`stats_importer.py`** — orchestrates: parse → map → resolve identity for each row → persist `player_projection` + `import_batch`. Rows without a match write to `import_unresolved`.
- **`adp_importer.py`** — same flow, simpler target table.

### `identity/`

- **`team_codes.py`** — (new per [ADR-0013](../../adr/0013-identity-resolution-team-abbreviation-normalization.md)) — `TEAM_CODE_ALIASES` dict (`KC→KCC`, `TB→TBB`, `SF→SFO`, `GB→GBP`, `NE→NEP`, `NO→NOS`, `LV→LVR`, `JAX→JAC`, `LA→LAR`) + `canonicalize_team(code)` helper. Applied to every parsed CSV team string before Tier 3 lookup.
- **`resolver.py`** — `resolve(csv_row, position) → mfl_id | None`.
  - **Tier 1**: for each known ID column in the CSV (`fantasypros_id`, `espn_id`, `yahoo_id`, `sleeper_id`, `cbs_id`, `pfr_id`, `fantasy_data_id`, `rotowire_id`, `nfl_id`), query `player` on the matching indexed column. First hit wins. **Note:** default FantasyPros exports don't include any ID column ([Spike B1](../../../spikes/b1-id-resolution/report.md)); Tier 1 is active only when the user hand-augments or the CSV comes from a source that publishes IDs.
  - **Tier 3**: lowercase + strip punctuation on the parsed name → canonicalize team via `team_codes.canonicalize_team` → query `player` on `(merge_name, team, position)`. Zero hits → `None`. One hit → return. Multiple hits → `None` (ambiguous; unresolved).
  - No general normalizer module for names — `merge_name` is pre-normalized at source. Our code applies the same transform to CSV rows + the team-code alias lookup.

### `scoring/`

- **`presets.py`** — three dict constants. Keys are nflreadpy canonical stat names (`passing_yards`, `passing_tds`, ...). Values are `(multiplier, bonus_threshold?)` pairs. See [ADR-0009](../../adr/0009-canonical-stat-vocabulary-from-nflreadpy.md).
- **`engine.py`** — `score(stats: dict, preset: dict) → float`. Pure function. Applies multiplier per stat, adds bonus threshold points if met. Called per-sample during simulation and per-projection for the players-list view.

### `historical/`

- **`fetch.py`** — thin wrapper per [ADR-0014](../../adr/0014-explicit-parquet-persistence-for-historical-data.md). `ensure_seasons(years)` checks `/data/historical/player_stats_{y}.parquet` per requested year; if missing, calls `nflreadpy.load_player_stats(seasons=[y])` and writes the Parquet ourselves (nflreadpy's cache is in-process only; Spike C1 verified `NFLREADPY_CACHE_DIR` does not persist). `game_logs(gsis_id, years)` reads the Parquet files, filters to `season_type == "REG"` and to rows where the player had activity (`(attempts + carries + targets) > 0` for skill positions). Returns a Polars DataFrame for `sim.fitting` to consume.

### `sim/`

- **`families.py`** — (new per [ADR-0012](../../adr/0012-mixed-distribution-families-for-stat-simulation.md)) — `STAT_FAMILY` dict mapping each canonical stat name to `"skewnorm"` (continuous yard/reception stats) or `"nbinom"` (count stats: passing_tds, passing_interceptions, rushing_tds, receiving_tds, rushing_fumbles_lost). Single source of truth for family choice.
- **`fitting.py`** — `fit_player(player_id, projection, historical_games) → params`:
  1. If `len(historical_games) < 4`: raise `InsufficientHistoryError`.
  2. For each stat in the projection that's also scoreable in the active preset: recency-weight the game-log rows (`[0.50, 0.30, 0.20]` for seasons Y, Y-1, Y-2). Dispatch on `STAT_FAMILY[stat]`:
     - `skewnorm`: fit via `scipy.stats.skewnorm.fit`, mean-shift so the fitted mean equals the projected stat. Store `{"family":"skewnorm", "alpha":…, "loc":…, "scale":…}`.
     - `nbinom`: fit via method-of-moments (`n = μ²/(σ²−μ)`, `p = μ/σ²`). Mean-shift by scaling `n` while holding dispersion (`σ²/μ`) constant. Store `{"family":"nbinom", "n":…, "p":…}`.
  3. Upsert into `player_distribution_params`.
- **`sampler.py`** — `sample(params, n=5000, seed=None) → dict[stat, ndarray]`. For each stat in `params`: dispatch on `family` → `skewnorm.rvs` (clamped to `≥0`) or `nbinom.rvs` (already non-negative integers). Samples independently per stat (no covariance — [ADR-0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md) unchanged on this point).
- **`runner.py`** — `simulate_player(player_id, n) → SimResult`. Loads or computes fit, samples, calls `scoring.engine.score` on each of the `n` stat lines, returns percentiles (p10, p50, p90), mean, std, and histogram bins.

### `routers/`

Thin HTTP layer. Each router delegates to one service module. Endpoints defined in §5. All routes require bearer auth via a FastAPI dependency from `auth.py`, except `/api/health`.

### Frontend modules

Four pages, no router complexity, minimal styling.

- **`SettingsPage.tsx`** (`/`) — read + write `/api/league/config`.
- **`ImportPage.tsx`** (`/import`) — file upload + paste-HTML textarea + source dropdown. POST to `/api/imports/stats` or `/api/imports/adp`. Inline list of unresolved rows with a player-picker dropdown populated by `/api/players`.
- **`PlayersPage.tsx`** (`/players`) — GET `/api/players`, display as a sortable table (column click → re-sort client-side; no server pagination).
- **`PlayerDetailPage.tsx`** (`/players/:id`) — projected stat line with per-stat point contribution, plus a Recharts `BarChart` of histogram bins from `/api/players/{id}/distribution`.

`web/src/api/client.ts` is generated from `shared/openapi.json`. A `make regen-client` target runs the generator.

---

## 5. Data Flow

### First-boot (one-time, automatic)

```
API process starts
  → db.migrate()
  → historical.fetch.ensure_seed()
      → set NFLREADPY_CACHE_DIR=/data/historical
      → if player table empty:
          nflreadpy.load_ff_playerids()
            → filter gsis_id IS NOT NULL
            → upsert into `player`
      → for y in [Y-2, Y-1, Y]:
          if cache miss: nflreadpy.load_player_stats([y])
  → server ready
```

### Happy path

```
1. User opens Settings page
   PUT /api/league/config {scoring_preset: "full_ppr"}

2. User opens Import tab, selects source=fantasypros, position=QB
   POST /api/imports/stats (multipart: file | paste_html, source, position)
   → csv_parser detects format (HTML or CSV)
   → column_mapper loads saved strategy for (fantasypros, QB), falls back to by_name alias dict
   → for each row:
        - split "Name TEAM" → (name, team)
        - identity.resolver: Tier 1 (any *_id column) → Tier 3 (merge_name + team + position)
        - matched: insert player_projection
        - unmatched: insert import_unresolved
   → insert import_batch
   → response: { import_batch_id, matched_rows, unresolved_rows, unmapped_columns }

3. Repeat step 2 for RB / WR / TE files; and once for ADP CSV.

4. (Optional) Resolve unresolved rows
   GET /api/imports/{id}/unresolved → list with candidate matches
   POST /api/imports/{id}/resolve { resolutions: [{row_id, player_id|null}] }

5. User opens Players page
   GET /api/players
   → join latest player_projection + latest player_adp per player
   → for each: score(projection.stats, preset) → projected_points
   → return list

6. User clicks a player
   GET /api/players/{id}/distribution?n=5000
   → load latest projection
   → if `position IN ('K','DEF')` → 422 not_supported_mvp
   → load historical game logs (via historical.fetch.game_logs)
   → if games < 4 → 422 insufficient_history
   → fit if params cache missing; else load
   → sample n, score each, compute percentiles + histogram
   → return DistributionResponse
```

### Change-triggered flows

| Action | Cascade |
|---|---|
| `PUT /api/league/config` (scoring_preset change) | No cache invalidation. Next `/players` or `/players/{id}/distribution` call recomputes points from samples. |
| `POST /api/imports/stats` (new projection) | Invalidate `player_distribution_params` for the affected `player_id`s. |
| `POST /api/historical/refresh` | Re-pull nflreadpy cache for the specified seasons; truncate `player_distribution_params`. |

### Error responses

- Unmapped columns during import → `200` with `unmapped_columns` array. User resolves via `PUT /api/imports/mappings/{source}/{position}` and re-uploads.
- Ambiguous Tier-3 match (multiple hits) → row written to `import_unresolved` with `resolution=NULL`.
- `<4` historical games → `422 insufficient_history` on distribution endpoint.
- K or DEF distribution request → `422 not_supported_mvp`.
- First-boot nflreadpy fetch failure → `503` on endpoints needing historical data; non-historical endpoints stay up.
- Missing/bad token → `401` (middleware).

---

## 6. API Surface

All routes under `/api`, Bearer auth required except `/api/health`. OpenAPI emitted at `/api/openapi.json`.

### Health

| Method | Path | Response |
|---|---|---|
| `GET` | `/api/health` | `{ status, db: bool, historical_ready: bool, historical_seasons: [int] }` (no auth) |

### League config

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/api/league/config` | — | `{ scoring_preset, num_teams, updated_at }` |
| `PUT` | `/api/league/config` | `{ scoring_preset?, num_teams? }` | updated config |

### Imports

| Method | Path | Body/Query | Response |
|---|---|---|---|
| `POST` | `/api/imports/stats` | multipart: `file \| paste_html`, `source`, `position` | `ImportBatchResult` |
| `POST` | `/api/imports/adp` | multipart: `file`, `source` | `ImportBatchResult` |
| `GET` | `/api/imports` | `?kind=&limit=` | `[ImportBatch]` |
| `GET` | `/api/imports/{id}` | — | `ImportBatch` |
| `GET` | `/api/imports/{id}/unresolved` | — | `[{ row_id, csv_row, parsed_name, parsed_team, candidates: [PlayerSummary] }]` |
| `POST` | `/api/imports/{id}/resolve` | `{ resolutions: [{row_id, player_id\|null}] }` | `ImportBatchResult` |
| `GET` | `/api/imports/mappings/{source}/{position}` | — | `{ strategy, mapping }` or 404 |
| `PUT` | `/api/imports/mappings/{source}/{position}` | `{ strategy, mapping }` | saved mapping |

### Players

| Method | Path | Query | Response |
|---|---|---|---|
| `GET` | `/api/players` | `?position=&team=&has_projection=true` | `[PlayerRow]` |
| `GET` | `/api/players/{id}` | — | `PlayerDetail` |
| `GET` | `/api/players/{id}/distribution` | `?n=5000` (clamp 100–20000) | `DistributionResponse` or `422` |

### Historical

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/api/historical/status` | — | `{ seasons, last_refreshed_at, ready }` |
| `POST` | `/api/historical/refresh` | `{ seasons?: [int] }` | `{ job_status }` — synchronous |

### Admin (per [ADR-0013](../../adr/0013-identity-resolution-team-abbreviation-normalization.md))

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `/api/admin/refresh-players` | — | `{ players_added, players_updated, unresolved_promoted }` — synchronous. Re-runs `nflreadpy.load_ff_playerids()`, upserts the `player` table, and re-runs the resolver on any `import_unresolved` rows that may now match. Run before draft prep to pick up current-season roster moves. |

### Payload shapes

```jsonc
// ImportBatchResult
{
  "import_batch_id": 42,
  "kind": "stats",
  "source": "fantasypros",
  "position": "QB",
  "status": "partial",
  "total_rows": 34,
  "matched_rows": 32,
  "unresolved_rows": 2,
  "unmapped_columns": ["CMP%"]
}

// PlayerRow
{
  "player_id": 12345,               // mfl_id
  "gsis_id": "00-0033873",
  "name": "Patrick Mahomes",
  "team": "KC",
  "position": "QB",
  "projected_stats": { "passing_yards": 4200, "passing_tds": 28, ... },
  "projected_points": 324.1,
  "adp_snake": 18.5,
  "adp_auction": 32
}

// DistributionResponse
{
  "player_id": 12345,
  "gsis_id": "00-0033873",
  "projection": { "stats": {...}, "source": "fantasypros", "import_batch_id": 42 },
  "scoring_preset": "full_ppr",
  "computed_points": 324.1,
  "distribution": {
    "n_samples": 5000,
    "floor_p10": 12.4,
    "median_p50": 19.8,
    "ceiling_p90": 28.1,
    "mean": 20.2,
    "std": 6.1,
    "histogram": { "bin_edges": [...], "counts": [...] }
  },
  "fit": {
    "fitted_at": "2026-04-15T10:23:00Z",
    "historical_seasons": [2023, 2024, 2025],
    "games_used": 48
  }
}

// Error shape (all errors)
{ "error": "insufficient_history", "message": "Only 2 career games found", "details": { "games_found": 2 } }
```

### Cross-cutting

- CORS: allow Vercel domain + `http://localhost:5173` via env-var list.
- No pagination on `/api/players` (max ~500 rows; client filters/sorts).
- No rate limiting (single-user + bearer auth).
- Standard error shape on all non-2xx.

### Explicitly deferred endpoints (documented absence)

- `/api/simulate/draft/snake`, `/api/simulate/draft/auction` — Phase 2.
- `/api/simulate/season`, `/api/simulate/matchup` — Phase 4.
- `/api/data/import/weekly` — Phase 4.
- `/ws/draft` — Phase 3.
- `/api/data/import/points` — cut entirely.
- `/api/players/{id}/archetype` — cut entirely.

---

## 7. Testing Strategy

Target: 80% coverage across unit + integration, one end-to-end happy-path test.

### Unit (`api/tests/unit/`, pytest)

| Module | What's tested |
|---|---|
| `scoring/engine.py` | Table-driven: all three presets against known stat lines → known point totals. Bonus thresholds (300+ pass yds, 100+ rush yds) trigger at boundary. |
| `scoring/presets.py` | Structural: required keys present, multipliers the expected sign. |
| `identity/team_codes.py` | All 9 alias entries map to correct canonical. `canonicalize_team("KC")` returns `"KCC"`; unmapped codes pass through unchanged. |
| `identity/resolver.py` | Tier 1 on each ID column type (int/str). Tier 3 on `merge_name + canonicalize_team(team) + position`. Ambiguous → `None`. Missing → `None`. Team-alias normalization kicks in for 2-letter codes. Uses a hand-built ~10-row `player` fixture covering duplicates, retirees, and a 2-letter→3-letter team match. |
| `import_pipeline/csv_parser.py` | Fixture-driven: FantasyPros HTML (committed fixture) flattens MultiIndex and splits name/team. Clean CSV passes through. |
| `import_pipeline/column_mapper.py` | Each of three strategies. Unmapped columns surfaced. |
| `sim/families.py` | Every stat name in `STAT_FAMILY` is either `"skewnorm"` or `"nbinom"`. All scoreable stats across all presets are registered. |
| `sim/fitting.py` | Synthetic-ground-truth, **per family**: (a) skew-normal — seeded RNG produces samples from known skewnorm → fit recovers params within tolerance → mean-shift lands on projection; (b) nbinom — seeded RNG produces counts from known (n, p) → method-of-moments recovers params within tolerance → dispersion-preserving mean-shift lands on target mean. `InsufficientHistoryError` at `<4` games. |
| `sim/sampler.py` | Seeded determinism. Array shapes. skewnorm samples are clamped ≥0; nbinom samples are already non-negative integers (no clamp). Mixed-family params produce correctly-shaped per-stat arrays. |
| `sim/runner.py` | Percentile ordering (p10 ≤ p50 ≤ p90). Histogram bins sum to N. |
| `historical/fetch.py` | `ensure_seasons` writes Parquet at expected paths; re-calls are idempotent (no re-download if file exists). `game_logs` filters to `REG` and to active-week rows. |

### Integration (`api/tests/integration/`, FastAPI TestClient + in-memory SQLite, transactional fixtures)

| Test | Verifies |
|---|---|
| `test_import_flow` | Upload → row counts in `player_projection`/`import_batch`/`import_unresolved` match expectation. Resolve endpoint moves rows. |
| `test_player_endpoints` | After import, `/players` returns rows with computed points. Scoring-preset switch reflected in next response. |
| `test_distribution_endpoint` | Seeded player + fixture historical → `DistributionResponse` with p10 ≤ p50 ≤ p90, histogram bins sum to N. |
| `test_insufficient_history` | `<4` fixture games → `422 insufficient_history`. |
| `test_k_def_not_supported` | K/DEF distribution request → `422 not_supported_mvp`. |
| `test_auth` | Missing/wrong token → `401`. `/health` accessible. |
| `test_historical_refresh` | `POST /historical/refresh` truncates `player_distribution_params`; next request re-fits. |
| `test_admin_refresh_players` | `POST /admin/refresh-players` upserts `player` rows; previously-unresolved import rows are re-run and promote to `player_projection` when a match now exists. |

**`nflreadpy` mocking**: commit cassettes (`tests/fixtures/nflreadpy/ff_playerids.parquet`, `player_stats_2024.parquet`, ...) generated by `make refresh-cassettes` (hits network). Pytest fixture monkeypatches `nflreadpy.load_*` to read these.

### E2E (`web/tests/e2e/`, Playwright, Chromium)

One happy-path test:
1. Start API against seeded test DB with 3 fixture QB players + committed historical data.
2. Launch React dev build.
3. Settings → change preset → save.
4. Import → upload `fantasypros_qb.html` fixture → expect matched count.
5. Players → expect three QBs with computed points.
6. Click first → expect histogram (SVG rect count > 0) and floor/median/ceiling values.

### Coverage gate

`pytest --cov=api/app --cov-fail-under=80`. Exclude `main.py`, `db.py` migration boilerplate, generated code.

### CI

GitHub Actions, two parallel jobs (`api-test`, `web-test`). No network access. Both complete in <2 minutes.

### Out of scope for MVP tests

- Performance benchmarks from Requirements v1.2 §7.3.
- Property-based/fuzz testing.
- Cross-browser.
- Visual regression.

---

## 8. Open Questions & Risks

### Open questions (resolve during writing-plans)

**8.1 Historical filtering for inactive weeks** — we exclude rows with zero activity (`attempts + carries + targets == 0` for skill positions). Verify this rule doesn't drop legitimate low-usage games (e.g., garbage-time cameos).

**8.2 Recency weighting** — hard-coded `[0.50, 0.30, 0.20]`. Surface as config post-MVP.

**8.3 Projection-vs-historical stat overlap** — fit only on stats that are (a) in the uploaded projection, (b) present in the historical frame, and (c) scoreable under the active preset. Drop all other projected stats silently.

**8.4 Paste-HTML path for FantasyPros** — user pastes a copy of the projections page HTML into a textarea on the Import tab. CSV parser handles both file upload and pasted HTML via the same `read_html` code path. Exact UX of the textarea is a writing-plans detail.

### Risks (flagged but accepted)

| # | Risk | Mitigation |
|---|---|---|
| R1 | `nflreadpy` is experimental; schema or support may change. Its filesystem cache does not persist via `NFLREADPY_CACHE_DIR` alone (verified by Spike C1). | `historical/fetch.py` writes Parquet explicitly ([ADR-0014](../../adr/0014-explicit-parquet-persistence-for-historical-data.md)) — already independent of nflreadpy cache internals. If the library itself changes schema, pin is `==0.1.5`; bump deliberately and re-seed. |
| R2 | Fly `shared-cpu-1x` default 256 MB RAM may be tight with 3 seasons × 19k rows × 114 cols in memory simultaneously. | Provision at 512 MB; profile during development; stream per-position if necessary. |
| R3 | Fly free tier is `$5/month credit` rather than fully free; small costs may accrue. | Estimate <$5/mo at MVP scale; `fly scale count 0` when not in use. |
| R4 | FantasyPros HTML structure may change. | One parser file + committed fixture; regression test catches breakage. |
| R5 | No intra-player stat covariance → a QB's 4-TD game is sampled as 4 TDs but independently in yards. | Accepted limitation; multivariate upgrade is contained in `sim/fitting.py`. |
| R6 | `ff_playerids` `db_season=2025` — 2026 rookies absent until source updates. | Manual refresh endpoint; user re-seeds before draft prep. |

### Known limitations carried into MVP (from Requirements v1.2 §10.3)

- Stat-level simulation without covariance loses intra-player correlation. Accepted.
- Projection accuracy depends on imported data quality. The system models uncertainty *around* externally sourced projections, not independently generated ones.
- Point-level imports not supported — users must provide stat-level data.

---

## 9. Validation Plan

The design rests on several assumptions that could invalidate the approach if wrong. Before any application code is written under `api/app/` or `web/src/` (beyond trivial scaffolding), the pre-implementation spikes in §9.1 must complete and pass their success criteria. Spikes run as self-contained scripts and produce committed artifacts (fixtures, measurement reports, plots) that downstream implementation consumes. See [ADR-0011](../../adr/0011-gate-implementation-on-pre-implementation-spikes.md).

All spike outputs land under `spikes/<id>-<slug>/` at the repo root and each ships a `report.md` with measurements + a pass/fail verdict.

### 9.1 Pre-implementation spikes (gates)

#### Spike A1 — Skew-normal distribution fit sanity check

- **Validates:** [ADR-0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md) — the core claim that skew-normal is a reasonable shape for weekly NFL stats.
- **Procedure:** Load 2024 weekly game logs for 10 veterans distributed across QB/RB/WR/TE. For each `(player, scoreable stat)`, fit `scipy.stats.skewnorm`. Produce histogram + fitted density overlay and Q-Q plot per pair.
- **Success:** ≥70% of pairs show visually acceptable fit (Q-Q residuals within tolerance).
- **Kill criterion:** <50% acceptable fit, or systematic zero-mass artifacts in count-valued stats (TDs, receptions) that `clamp(≥0)` doesn't hide. Revise: consider per-stat distribution families (skew-normal for yards, negative-binomial for counts).
- **Effort:** ~2 hours.
- **Artifacts:** `spikes/a1-skew-normal-fits/report.md`, PNG plots per (player, stat).

#### Spike A2 — Mean-shift calibration backtest

- **Validates:** that shifting historical variance to match a new season's projected mean produces *calibrated* intervals (not systematically over- or under-confident).
- **Procedure:** Hold out 2024 as ground truth. Fit using 2021–2023 historical with recency `[0.5, 0.3, 0.2]`. Mean-shift each fit to a 2024 preseason projection (from FantasyPros consensus archive or another archived source). Sample 5,000 per player per stat, compute aggregate season distribution. Compare each player's **actual** 2024 season total to the predicted `p10–p90` interval. Tabulate coverage rate.
- **Success:** Coverage 70–90% (80% is target).
- **Kill criterion:** <60% (overconfident) or >95% (vacuous). Revise: weight the historical σ differently, or blend in a variance term derived from the projection-source's reported floor/ceiling when available.
- **Effort:** 4–6 hours.
- **Artifacts:** `spikes/a2-calibration/report.md` with coverage table + per-stat breakdown.

#### Spike B1 — Identity resolution hit-rate

- **Validates:** [ADR-0005](../../adr/0005-identity-resolution-tiers-1-and-3-only.md) — Tiers 1 + 3 alone suffice for FantasyPros inputs.
- **Procedure:** Manually harvest current FantasyPros HTML for each of QB/RB/WR/TE (copy rendered tables; save to `tests/fixtures/fantasypros_{pos}.html`). Prototype `csv_parser` + `identity.resolver` in a notebook. Run each position through resolver against `load_ff_playerids()` filtered to `gsis_id IS NOT NULL`.
- **Measurements per position:** % Tier-1 match (expected 0% for default FantasyPros), % Tier-3 single match, % Tier-3 ambiguous (multi-hit), % unresolved.
- **Success:** ≥90% resolved via Tier-3 single match across all four positions.
- **Kill criterion:** <80% resolved → reconsider adding Tier 2 (jersey number if source includes it) or strengthening normalization (handle `D.J. Moore` vs `DJ Moore`, suffix stripping like `Jr./Sr./III`).
- **Effort:** ~3 hours.
- **Artifacts:** `spikes/b1-id-resolution/report.md`, four HTML fixtures committed under `tests/fixtures/`.

#### Spike B2 — FantasyPros HTML parser across positions

- **Validates:** one parser handles all four MultiIndex shapes (QB has PASSING/RUSHING/MISC; WR/TE have RECEIVING/RUSHING/MISC; RB has RUSHING/RECEIVING/MISC).
- **Procedure:** Reuse the four HTML fixtures from B1. Run `pandas.read_html` on each and verify the section×stat mapping table from §4 (`column_mapper.fantasypros_multi_header`) covers every column without errors.
- **Success:** Zero parse errors; every column maps to a nflreadpy canonical name or is explicitly marked `ignored`.
- **Kill criterion:** Any position requires handling not expressible in one of the three existing strategies → add a fourth strategy or refine.
- **Effort:** ~1 hour.
- **Artifacts:** `tests/unit/test_csv_parser_spike.py` (promotable directly into the real unit test), `spikes/b2-parser/report.md`.

#### Spike C1 — Fly deploy smoke test

- **Validates:** [ADR-0002](../../adr/0002-host-backend-on-fly-and-frontend-on-vercel.md) + [ADR-0006](../../adr/0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) — that Fly actually works for this workload within budget, and that RAM fits.
- **Procedure:** Build a minimal FastAPI app with `/api/health` + `/api/seed` (triggers full `nflreadpy` seed of `load_ff_playerids()` + 3 seasons of `load_player_stats`). Dockerize, deploy to Fly with `shared-cpu-1x @ 512 MB` and a 1 GB volume. Measure: cold-boot time, peak RAM during seed (via `fly metrics` or logs), final volume disk usage, estimated monthly $ cost.
- **Success:** peak RAM <512 MB, cold boot <90 s, disk <200 MB after 3-season seed, projected cost ≤ Fly's $5 monthly credit at idle.
- **Kill criterion:** peak RAM >512 MB → bump to 1 GB VM, verify cost still under $10/mo (else ADR-0002 revision). Disk >500 MB → revise cache strategy.
- **Effort:** 3–4 hours.
- **Artifacts:** the Fly app itself (tag `spike/c1-deploy`; keep or tear down), `spikes/c1-deploy/report.md` with measurements + screenshots of Fly metrics.

#### Spike C2 — Monte Carlo performance on constrained compute

- **Validates:** Requirements v1.2 §7.3 target of `<200ms` per single-player distribution.
- **Procedure:** On local Docker constrained to `--memory=512m --cpus=0.25` (approximates Fly shared-cpu-1x), run a prototype `simulate_player` (fit + sample + score) end-to-end for 100 players at `n=5000`. Record p50 and p95 latency.
- **Success:** p50 <200 ms, p95 <500 ms.
- **Kill criterion:** p95 >1 s → reduce default `n` to 1,000, update spec §5 `DistributionResponse` docs. If even `n=1000` misses budget, profile and revisit.
- **Effort:** ~2 hours.
- **Artifacts:** `spikes/c2-perf/report.md` with timing histogram.

### 9.2 During-implementation validation

#### 9.2.1 Walking skeleton

First implementation pass wires the entire pipeline end-to-end with trivial stubs: identity by exact name match, single hard-coded PPR preset, normal distribution with `σ = 30% × mean`, minimal UI. Deploy to Fly + Vercel. Click through happy path in the browser and verify values are plausible. **Only after this works end-to-end** do we swap real components in one at a time (statistical fit → scoring presets → identity tiers → full CSV parsing).

Rationale: catches integration bugs before they accumulate across components and produces a deployable artifact early.

#### 9.2.2 Fixture-driven TDD

Every unit test backed by fixtures committed during spikes: HTML files from B1, nflreadpy cassettes from `make refresh-cassettes`, known-ground-truth synthetic data from A1. No test hits the network. No test generates data on the fly that a fixture could pin.

#### 9.2.3 Canary comparison

Before declaring MVP done, pick 5 top-ADP players (mix of positions). Compute their distributions. Compare the **median** of each distribution to the source's published projected fantasy points (after applying our preset). Because we mean-shift to the projection, medians should match within ~1 point. Discrepancy indicates a bug in scoring, fitting, or shifting.

- **Effort:** 30 minutes; run as a script (`spikes/d3-canary/compare.py`) committed to the repo.

### 9.3 Post-MVP validation

#### 9.3.1 Manual draft dry-run

Use the MVP during a mock draft on Yahoo/Sleeper/ESPN or a written session. Record friction points, missing features, and judgment calls the tool couldn't answer. Feeds Phase 2 backlog.

#### 9.3.2 End-of-season calibration retrospective

After the 2026 NFL regular season, backtest the MVP's preseason distributions against actual full-season totals. Publish a coverage table (same methodology as Spike A2 but on real preseason output) in a follow-on spec. This informs whether Phase 2 needs revised fitting before building on top.

### 9.4 Gating rule

- **Mandatory before any implementation work under `api/app/` or `web/src/`:** Spikes **A1, B1, B2, C1** must pass (acceptable reports committed).
- **Mandatory before `sim/` and `historical/` modules go beyond stubs:** Spike **A2** must pass; **C2** may run in parallel with early sim scaffolding.
- **Walking skeleton (§9.2.1)** is the first implementation milestone after spikes pass.
- **Canary comparison (§9.2.3)** is the last gate before declaring MVP complete.

If any kill criterion triggers, write a new ADR documenting the finding + the required design revision, update the affected spec sections, and re-present for review **before** continuing.

---

## 10. ADR Index

All decisions in this spec link to MADR 3.0 records under `docs/adr/`. See [`docs/adr/README.md`](../../adr/README.md) for the full list and status.

| ADR | Decision |
|---|---|
| [0001](../../adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [0002](../../adr/0002-host-backend-on-fly-and-frontend-on-vercel.md) | Host backend on Fly.io, frontend on Vercel |
| [0003](../../adr/0003-scope-mvp-to-player-explorer.md) | Scope MVP to Player Explorer slice |
| [0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md) | Simulation: veterans-only, per-stat skew-normal |
| [0005](../../adr/0005-identity-resolution-tiers-1-and-3-only.md) | Identity resolution: Tiers 1 and 3 only |
| [0006](../../adr/0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) | Storage: SQLite on Fly volume + nflreadpy cache |
| [0007](../../adr/0007-single-bearer-token-auth.md) | Auth: single bearer token, no user accounts |
| [0008](../../adr/0008-use-nflreadpy-not-nfl-data-py.md) | Use `nflreadpy`, not the deprecated `nfl_data_py` |
| [0009](../../adr/0009-canonical-stat-vocabulary-from-nflreadpy.md) | Canonical stat vocabulary = `nflreadpy` column names |
| [0010](../../adr/0010-mvp-supports-qb-rb-wr-te-only.md) | MVP supports QB/RB/WR/TE only (K/DEF deferred) |
| [0011](../../adr/0011-gate-implementation-on-pre-implementation-spikes.md) | Gate implementation on pre-implementation spikes |
| [0012](../../adr/0012-mixed-distribution-families-for-stat-simulation.md) | Mixed distribution families — skew-normal for continuous, negative-binomial for counts (supersedes 0004 family choice) |
| [0013](../../adr/0013-identity-resolution-team-abbreviation-normalization.md) | Team-abbreviation normalization + canonical-refresh endpoint (amends 0005) |
| [0014](../../adr/0014-explicit-parquet-persistence-for-historical-data.md) | Explicit Parquet persistence; nflreadpy cache is in-process (amends 0006) |
| [0011](../../adr/0011-gate-implementation-on-pre-implementation-spikes.md) | Gate implementation on pre-implementation spikes |

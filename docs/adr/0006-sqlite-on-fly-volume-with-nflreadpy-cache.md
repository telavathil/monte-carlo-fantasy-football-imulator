# ADR-0006: Storage — SQLite on Fly volume, nflreadpy filesystem cache

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

The MVP needs to persist league config, imports, player registry, projections, and fit parameters across server restarts. It also needs to cache ~3 seasons of NFL weekly game logs (~30 MB as Parquet) so we don't re-download on every boot.

## Decision Drivers

- Single user; concurrent writers aren't a concern.
- Deployed on Fly.io with a mountable persistent volume available (see [ADR-0002](0002-host-backend-on-fly-and-frontend-on-vercel.md)).
- `nflreadpy` ships a configurable filesystem cache out of the box.
- Avoid external dependencies (Neon/Supabase) at MVP scale — fewer moving parts to monitor.

## Considered Options

1. **SQLite on the Fly volume + `nflreadpy` filesystem cache on the same volume.**
2. **Managed Postgres (Neon / Supabase free tier)**, historical data in a `bytea` column or re-downloaded on cold start.
3. **Ephemeral storage everywhere** — re-seed on every boot (rejected: slow boots, hits `nflreadpy` network on every restart).
4. **Write our own Parquet-save code** — ignore `nflreadpy`'s cache, manage files manually (rejected: more code to own).

## Decision Outcome

**Chosen: Option 1.** A 1 GB Fly volume mounted at `/data` holds:
- `/data/sqlite.db` — all transactional / relational state.
- `/data/historical/` — `nflreadpy` filesystem cache, populated via `NFLREADPY_CACHE_DIR=/data/historical`.

SQLite schema defined in the MVP spec §3. `historical/fetch.py` is a thin wrapper around `nflreadpy.load_player_stats()` that assumes the cache handles itself.

### Consequences

- **Good:** single persistence surface; no external DB service to configure, monitor, or pay for.
- **Good:** ~20 lines of historical-data code instead of ~100 (no custom Parquet management).
- **Good:** survives Fly VM restarts because the volume is persistent.
- **Bad:** SQLite's single-writer model means we can't easily horizontally scale the API. Irrelevant at MVP scale; real concern only if we need multiple concurrent users (revisit with a new ADR at that point).
- **Bad:** volume snapshots are our only backup. Mitigation: the data is reconstructable from nflreadpy + original CSVs, so volume loss is inconvenient but not catastrophic.
- **Bad:** if Fly's volume semantics ever change or pricing shifts, we'd need to migrate. Contained: SQLite file + parquet directory are both trivially copyable.

## More Information

- [Fly.io volumes](https://fly.io/docs/volumes/overview/)
- `nflreadpy` env-var config: `NFLREADPY_CACHE_DIR`, `NFLREADPY_CACHE_MODE` (see [repo](https://github.com/nflverse/nflreadpy)).
- Related: [ADR-0002](0002-host-backend-on-fly-and-frontend-on-vercel.md), [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md).

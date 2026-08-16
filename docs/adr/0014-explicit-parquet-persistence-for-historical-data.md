# ADR-0014: Explicit Parquet persistence for historical data (nflreadpy cache is in-process)

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil
- **Amends:** [ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) (storage topology unchanged; this ADR corrects the persistence mechanism for historical stats)

## Context and Problem Statement

[ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) assumed that setting `NFLREADPY_CACHE_DIR=/data/historical` would cause `nflreadpy` to persist its Parquet downloads to our Fly volume automatically — the point being to avoid re-downloading ~30 MB on every VM restart. [Spike C1](../../spikes/c1-deploy/report.md) deployed a minimal app with this env var set and ran the full seed. The seed succeeded in-process (loaded `ff_playerids` and three seasons of `player_stats`), but the `/api/seed` endpoint also reported `disk_mb: 0.0` — **nothing was written to `/data/historical/`.** The volume is mounted, writable, and verified — nflreadpy simply does not use it as a filesystem cache under the current configuration.

Possible root causes (not exhaustively investigated in the spike):

1. `NFLREADPY_CACHE_DIR` alone is insufficient; a separate `NFLREADPY_CACHE_MODE` (or similarly named) env var may be required to opt into filesystem caching vs. in-memory.
2. `nflreadpy` version `0.1.5` may have a documented or undocumented default of `memory` caching, with filesystem as an opt-in we missed.
3. The cache may be writing to a different path internally (XDG-style `~/.cache/nflreadpy`) that ignores our env var.

The implementer flagged this as a concern on an otherwise-passing spike. The architectural consequence is clear: **we cannot assume `nflreadpy` handles persistence for us.** We must either (a) investigate and reliably configure whichever mode produces filesystem caching, or (b) own the persistence step explicitly in our wrapper.

## Decision Drivers

- Cold boots should be fast; re-downloading 30+ MB on every Fly machine restart is wasteful and slow.
- Reliability matters more than code minimalism — owning the write path means no surprise when nflreadpy changes its cache internals.
- The spec already listed "fall back to explicit Parquet if nflreadpy misbehaves" as Risk R1 mitigation.
- One-time discovery tax (figure out nflreadpy) is acceptable if it saves code; recurring surprise tax is not.

## Considered Options

1. **Investigate nflreadpy cache configuration; use whichever env var enables filesystem mode.** Hopes the library can be made to cooperate.
2. **Ignore nflreadpy's cache entirely; write our own Parquet persistence in `historical/fetch.py`.** ~10 lines of pandas / polars `write_parquet` + existence checks.
3. **Hybrid: set the env var *and* write our own Parquet; whichever caches the data is fine.** Belt + suspenders.
4. **Accept re-download on cold boot.** Rejected — 30 s per boot is user-visible latency the spec targets <90 s boot for.

## Decision Outcome

**Chosen: Option 2 (own the persistence).** `historical/fetch.py` becomes:

```python
import nflreadpy as nfl
import polars as pl
from pathlib import Path

HIST_DIR = Path("/data/historical")

def ensure_seasons(years: list[int]) -> None:
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    for y in years:
        path = HIST_DIR / f"player_stats_{y}.parquet"
        if not path.exists():
            df = nfl.load_player_stats(seasons=[y])
            df.write_parquet(path)

def game_logs(gsis_id: str, years: list[int]) -> pl.DataFrame:
    dfs = [pl.read_parquet(HIST_DIR / f"player_stats_{y}.parquet") for y in years]
    df = pl.concat(dfs)
    return df.filter(
        (pl.col("player_id") == gsis_id)
        & (pl.col("season_type") == "REG")
    )
```

`ff_playerids` is smaller (~1 MB) and loaded once into SQLite at seed time — no Parquet caching needed for it.

### Consequences

- **Good:** deterministic persistence. Parquet files appear in `/data/historical/` under names we control; easy to inspect, delete, back up.
- **Good:** independent of nflreadpy cache internals. If nflreadpy changes its caching, we're unaffected.
- **Good:** testable. Our `historical/fetch.py` becomes a thin pandas/polars-level wrapper that's mocked by pointing `HIST_DIR` at a temp dir in tests.
- **Good:** correctly addresses Risk R1's "swap to reading nflverse Parquet releases directly" escape hatch — we're already there.
- **Bad:** duplicate caching potential. nflreadpy may still hold its own in-memory copy during `load_player_stats()`; not a correctness issue but a small memory overhead at seed time. Measured in C1 as 135 MB peak — well within 512 MB budget.
- **Bad:** if nflreadpy changes the *shape* of its returned DataFrame in a future version (e.g., adds/renames columns), our stored Parquet schema drifts. Mitigated by pinning nflreadpy version (already `==0.1.5`) and re-seeding on version bump.
- **Bad:** the ADR-0006 claim "~20 lines of historical-data code instead of ~100 (no custom Parquet management)" is no longer quite true; we're at ~15 lines. Still small.

## More Information

- Spike evidence: [`spikes/c1-deploy/report.md`](../../spikes/c1-deploy/report.md) (see `disk_mb: 0.0` in seed output).
- ADR-0006 storage topology remains correct (Fly volume at `/data`; SQLite at `/data/sqlite.db`; historical parquet at `/data/historical/`). Only the *who writes the parquet* detail changes.
- Related: [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md) (the library whose cache we're bypassing).
- Spec §3 "Historical data lifecycle" needs a small edit to reflect this change; §8 Risk R1 mitigation is partially already realized.

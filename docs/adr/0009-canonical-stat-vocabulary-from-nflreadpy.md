# ADR-0009: Canonical stat vocabulary = `nflreadpy` column names

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 §3.2 defines stat column names for CSV imports: `pass_yds`, `pass_tds`, `pass_int`, `rush_yds`, `rush_tds`, `rec`, `rec_yds`, `rec_tds`, etc. `nflreadpy.load_player_stats()` uses different long-form names: `passing_yards`, `passing_tds`, `passing_interceptions`, `rushing_yards`, `rushing_tds`, `receptions`, `receiving_yards`, `receiving_tds`, etc. The scoring engine, distribution fitter, and API schemas all need to pick **one** vocabulary.

## Decision Drivers

- A single canonical name per stat across import → scoring → fitting → API → frontend means less translation code.
- The historical data (`nflreadpy`) uses its own names in the Parquet files; we don't control those.
- The CSV import layer *has* to translate source-specific names regardless (FantasyPros uses `YDS`, ESPN uses `Pass Yds`, Yahoo uses others) — so adding one more translation target vs. another is the same cost.

## Considered Options

1. **Use Requirements v1.2 abbreviations** (`pass_yds`, `rec`) as canonical — translate nflreadpy columns into this vocabulary in `historical/fetch.py`.
2. **Use `nflreadpy`'s long-form names** (`passing_yards`, `receptions`) as canonical — translate CSV imports into this vocabulary in `column_mapper.py`.
3. **Use a third vocabulary of our own invention.**

## Decision Outcome

**Chosen: Option 2 (`nflreadpy` long-form names as canonical).** `scoring/presets.py` keys use nflreadpy names. `player_projection.stats` JSON uses nflreadpy names. `sim/fitting.py` and `sim/sampler.py` operate on nflreadpy names. `column_mapper.py` is the only place translations happen — per source, per position.

### Consequences

- **Good:** zero translation layer between historical and fitting. The fitter pulls weekly game logs from nflreadpy and uses column names directly.
- **Good:** long-form names are self-documenting (`passing_interceptions` > `pass_int`).
- **Good:** if nflreadpy adds a new stat, scoring and fitting can pick it up without renaming.
- **Bad:** diverges visibly from Requirements v1.2 §3.2 tables. Spec §3 notes this explicitly.
- **Bad:** API payloads are wordier. `stats: {"passing_yards": 4200, "passing_tds": 28, ...}` vs. `stats: {"pass_yds": 4200, "pass_tds": 28, ...}`. Acceptable for a JSON API.
- **Bad:** if we ever drop `nflreadpy` for another source with different names (`nflverse` Parquet releases use the same names, so this is low-risk), we'd rename broadly. Contained to one PR.

## More Information

- Requirements v1.2, §3.2 (the abbreviated schema we're diverging from).
- `nflreadpy` column reference: [`nflreadr::load_player_stats` docs](https://nflreadr.nflverse.com/reference/load_player_stats.html) — matching column set.
- Related: [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md).

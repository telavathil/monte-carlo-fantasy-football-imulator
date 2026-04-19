# ADR-0008: Use `nflreadpy`, not the deprecated `nfl_data_py`

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 §3.1.3 and §7.1 name `nfl_data_py` as the Python library for historical NFL data. Doc-check during brainstorming revealed that `nfl_data_py` has been **deprecated** — its README directs users to `nflreadpy`. We need to choose a library before committing the data-model schema.

## Decision Drivers

- The doc's chosen library is no longer maintained; future stat additions or format changes won't land there.
- `nflreadpy` is the official replacement from the same maintainers (nflverse).
- Must support the two operations the MVP needs: player ID cross-reference (`load_ff_playerids`) and weekly game-log stats (`load_player_stats`).
- Prefer a library with a built-in caching story so we don't write Parquet-management code ourselves.

## Considered Options

1. **Use `nfl_data_py` anyway** — follow the requirements doc verbatim; accept deprecation risk.
2. **Use `nflreadpy`** — the maintainer-endorsed replacement.
3. **Read nflverse Parquet releases from GitHub directly** — bypass any Python library; fetch Parquet URLs with `requests` + read with `pl.read_parquet`. Maximal control, more code.
4. **Call the R `nflreadr` package from Python** via `rpy2` — adds an R runtime dependency.

## Decision Outcome

**Chosen: Option 2 (`nflreadpy`).** Pinned in `pyproject.toml`. Used via a thin `historical/fetch.py` wrapper so we can swap to Option 3 (direct Parquet reads) if `nflreadpy` misbehaves.

### Consequences

- **Good:** matches the maintainer's direction. Future data additions from nflverse will appear here first.
- **Good:** built-in filesystem cache (`NFLREADPY_CACHE_DIR`) means we skip writing ~100 lines of Parquet management. See [ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md).
- **Good:** provides `load_ff_playerids()` — the cross-reference we need for identity resolution — without us assembling it ourselves.
- **Bad:** library is tagged "experimental"; the README notes "Most of the first version was written by Claude based on nflreadr." Schema drift or abandonment is plausible. Risk R1 in the MVP spec. Mitigation: thin wrapper makes swapping to Option 3 a ~100-line change.
- **Bad:** native format is Polars DataFrames (not pandas). We convert with `.to_pandas()` only at layer boundaries where it matters; the rest of `historical/` and `sim/fitting.py` operates on Polars or NumPy directly.
- **Bad:** canonical stat names differ from Requirements v1.2 (`passing_yards` not `pass_yds`, etc.). Addressed in [ADR-0009](0009-canonical-stat-vocabulary-from-nflreadpy.md).

## More Information

- `nfl_data_py` deprecation notice: [`cooperdff/nfl_data_py`](https://github.com/cooperdff/nfl_data_py) README.
- `nflreadpy` repo: [`nflverse/nflreadpy`](https://github.com/nflverse/nflreadpy).
- Cross-reference dictionary: [`dictionary_ff_playerids`](https://nflreadr.nflverse.com/articles/dictionary_ff_playerids.html).
- Verified during brainstorming via direct `load_ff_playerids()` and `load_player_stats([2024])` calls.

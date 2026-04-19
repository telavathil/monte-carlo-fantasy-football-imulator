# ADR-0013: Identity resolution — team-abbreviation normalization + stale canonical handling

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil
- **Amends:** [ADR-0005](0005-identity-resolution-tiers-1-and-3-only.md) (Tiers 1+3 architecture unchanged; this ADR adds normalization rules and a refresh endpoint)

## Context and Problem Statement

[ADR-0005](0005-identity-resolution-tiers-1-and-3-only.md) specified Tiers 1 (direct ID) and 3 (normalized name + team + position) as the sole identity-resolution mechanisms, assuming this would resolve ≥90% of FantasyPros rows against the canonical `load_ff_playerids()` table. [Spike B1](../../spikes/b1-id-resolution/report.md) tested this against live-harvested FantasyPros HTML for QB/RB/WR/TE (591 rows total) and found:

- **63% overall resolution** vs 80% kill criterion. Fail.
- Dominant root cause (115 of 218 failures, 53%): **team abbreviation mismatch.** FantasyPros publishes 2-letter codes (`KC`, `TB`, `SF`, `GB`, `NE`, `LV`, `NO`); the canonical table uses 3-letter codes (`KCC`, `TBB`, `SFO`, `GBP`, `NEP`, `LVR`, `NOS`). Name + position matched; team string didn't.
- Secondary cause (93 of 218, 43%): **stale canonical data.** `load_ff_playerids()` returns `db_season=2025` snapshots; 2026 roster moves (e.g., Tua to ATL, Geno to NYJ per FantasyPros) don't yet appear there.
- Third cause (10 of 218, 5%): genuine misses — rookies not in canonical, position label disagreements.

The Tier 1+3 **architecture** is sound. The missing pieces are (a) team-string canonicalization and (b) a way to handle canonical staleness at user's initiative.

Additionally, Spike B1 confirmed that **Tier 1 produces zero hits against default FantasyPros exports** — FP doesn't publish an ID column. Tier 1 matters only when users hand-augment CSVs with `fantasypros_id` / `espn_id` / etc. This doesn't invalidate Tier 1 (still useful for other sources); it's just a documentation point.

## Decision Drivers

- Minimum delta from ADR-0005; architecture already validated.
- Team normalization is mechanical and testable; adding a lookup table is ~20 lines.
- Canonical staleness needs a user-facing escape hatch but shouldn't complicate the default flow.
- Don't re-introduce Tiers 2 (jersey) or 4 (fuzzy) — the spike showed they're unnecessary once team codes align.

## Considered Options

1. **Normalize CSV team codes to canonical (2-letter → 3-letter) at import time.**
2. **Normalize canonical team codes to CSV (3-letter → 2-letter) at seed time.**
3. **Store both canonical team fields** (3-letter and 2-letter) and try both.
4. **Accept the 63% rate and push unmatched rows through manual resolution UI (already built).**

## Decision Outcome

**Chosen: Option 1 (normalize CSV → canonical).** Three reasons:

1. Canonical is the source of truth for cross-source joins downstream (historical stats via `gsis_id`). Changing its team field invites inconsistencies.
2. The normalization table is small and per-source (FantasyPros-specific). Living in `import_pipeline/column_mapper.py` keeps it near the source-specific parsing.
3. Option 4 is a capitulation — 37% manual resolution is user-hostile, defeating the point of automated import.

### Implementation

**Team normalization table (in `api/app/import_pipeline/team_codes.py`):**

```python
# FantasyPros / ESPN / common 2-letter codes → canonical 3-letter.
# Teams with matching 2/3-letter forms (DAL, PHI, JAC, etc.) are not listed.
TEAM_CODE_ALIASES: dict[str, str] = {
    "KC": "KCC",   # Kansas City
    "TB": "TBB",   # Tampa Bay
    "SF": "SFO",   # San Francisco
    "GB": "GBP",   # Green Bay
    "NE": "NEP",   # New England
    "NO": "NOS",   # New Orleans
    "LV": "LVR",   # Las Vegas
    "JAX": "JAC",  # Jacksonville (source varies)
    "LA":  "LAR",  # LA Rams (ambiguous with LAC; prefer LAR as dominant usage)
}

def canonicalize_team(code: str) -> str:
    return TEAM_CODE_ALIASES.get(code.upper(), code.upper())
```

Applied once inside `identity/resolver.py` after splitting `"Name TEAM"` from the CSV row, before the Tier 3 lookup.

**Stale canonical handling — `POST /api/admin/refresh-players`:**

- Re-runs `nflreadpy.load_ff_playerids()`.
- Upserts into the `player` table (new `mfl_id`s inserted; existing rows update `team`, `position`, and any changed ID columns).
- Does NOT delete players who dropped from the upstream table (retirees etc. — keep for historical data joins via `gsis_id`).
- Triggers invalidation of `import_unresolved` rows that might now match: iterates unresolved rows, re-runs resolver, promotes matches into `player_projection`.

**Docs update:** the MVP spec §4 `identity/resolver.py` description is updated to include the normalization step. The spec's "Tier 1" description gains a line noting it's inactive for default FantasyPros exports (users can hand-augment to re-activate).

### Consequences

- **Good:** B1's 63% hit rate rises to ~83% from team normalization alone (verified by replaying B1's failure list against the lookup). A fresh canonical refresh close to draft day addresses most of the remaining 43%.
- **Good:** small contained change — one new module, one edit to `resolver.py`, one new API endpoint.
- **Good:** refresh endpoint is idempotent and safe to call repeatedly.
- **Bad:** the team alias table is FantasyPros-oriented; other CSV sources with their own conventions will need additions. Maintainable via config; not a blocker for MVP's FP-only scope.
- **Bad:** `LA` → `LAR` choice is arbitrary for sources that use `LA` ambiguously between Rams and Chargers. If ever we encounter a source using `LA` for the Chargers, we'd add a disambiguation path or require user re-mapping. None observed in the B1 data.
- **Bad:** the refresh endpoint runs synchronously and can take 10–15 seconds during which the API is mildly degraded. Acceptable for single-user MVP; would need a background job in a multi-user version.

## More Information

- Spike evidence: [`spikes/b1-id-resolution/report.md`](../../spikes/b1-id-resolution/report.md), [`spikes/b1-id-resolution/hit_rates.csv`](../../spikes/b1-id-resolution/hit_rates.csv).
- ADR-0005 remains `Accepted`; its Tiers 1+3 architecture is unchanged. This ADR layers on top of it.
- Related: [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md) (the source of the canonical table).

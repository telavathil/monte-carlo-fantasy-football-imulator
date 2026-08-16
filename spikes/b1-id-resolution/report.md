# Spike B1 Report — Identity Resolution Hit-Rate

**Date:** 2026-04-18
**Validates:** ADR-0005 (Tiers 1 + 3 only).
**Kill criterion:** <80% resolved.

## Results

| Position | Tier 1 | Tier 3 single | Tier 3 ambiguous | Unresolved | Total | Resolved % |
|---|---|---|---|---|---|---|
| QB | 0 | 54 | 0 | 34 | 88 | 61% |
| RB | 0 | 99 | 0 | 53 | 152 | 65% |
| WR | 0 | 139 | 0 | 85 | 224 | 62% |
| TE | 0 | 81 | 0 | 46 | 127 | 64% |
| **Total** | **0** | **373** | **0** | **218** | **591** | **63%** |

No Tier 1 hits: FantasyPros HTML export embeds no machine-readable IDs in the projection table. No Tier 3 ambiguous hits: name+team+position always produced 0 or 1 match.

### Unresolved or ambiguous — sample

- `Baker Mayfield TB` — team abbreviation mismatch: FP uses `TB`, canonical uses `TBB`
- `Patrick Mahomes II KC` — team abbreviation mismatch: FP uses `KC`, canonical uses `KCC`; suffix `II` is correctly stripped
- `Kyler Murray MIN` — stale roster: FP projects on MIN (2025 offseason move), canonical still has him on ARI
- `Geno Smith NYJ` — stale roster: FP has him on NYJ, canonical has him on LVR
- `Travis Etienne Jr. NO` — stale roster: suffix stripped correctly; FP projects on NO, canonical has JAC
- `Hollywood Brown PHI` — no name match: absent from canonical table entirely
- `Chig Okonkwo WAS` — no name match: not in canonical (fringe roster / alias)
- `David Sills V TB` — no name match: suffix `V` not stripped (current regex only strips jr/sr/ii/iii/iv)
- `Velus Jones Jr. SEA` — position mismatch: FP lists as RB, canonical has him as WR
- `Brady Russell SEA` — position mismatch: FP lists as TE, canonical has him as RB

### Common failure patterns

1. **Team abbreviation mismatch — 115 rows (53% of unresolved):** FantasyPros uses 2-letter NFL short codes (`TB`, `SF`, `GB`, `NE`, `NO`, `LV`, `KC`) while nflreadpy canonical uses 3-letter codes (`TBB`, `SFO`, `GBP`, `NEP`, `NOS`, `LVR`, `KCC`). A static 9-entry lookup map eliminates all 115. Simulated: fixing this alone raises overall resolution to 83%.

2. **Stale roster data — 93 rows (43% of unresolved):** The nflreadpy `load_ff_playerids()` snapshot (`db_season=2025`) lags the current offseason. FantasyPros reflects 2025-26 rosters; canonical still has players on prior teams. This is a data freshness problem, not a logic failure.

3. **No name in canonical — 6 rows (3% of unresolved):** Players absent from nflreadpy entirely (injury absence, aliases, fringe practice-squad players).

4. **Position mismatch — 4 rows (2% of unresolved):** FP position label differs from canonical (WR projected as RB flex, TE listed as RB). Dropping the position filter would resolve these at risk of false matches.

## Verdict

Mark exactly one with `[x]`:
- [ ] **PASS** — ≥90% resolved.
- [ ] **BORDERLINE** — 80-90%; note failure modes.
- [x] **FAIL (KILL)** — <80%.

## Recommendation

"Add normalization rules: (a) team abbreviation translation map (`TB→TBB`, `SF→SFO`, `GB→GBP`, `NE→NEP`, `NO→NOS`, `LV→LVR`, `KC→KCC`, `LA→LAR`, `JAX→JAC`); (b) refresh canonical source to current-season roster via `nfl.load_rosters(seasons=[current_season])`. These two changes raise the simulated hit rate to ≥83% without adding fuzzy matching or jersey-number tiers. Revise ADR-0005 to include team abbreviation normalization as a required pre-filter step; the Tier 1+3 architecture otherwise stands."

## Artifacts

- `hit_rates.csv` — 591 rows, one per projection row across all four positions, with resolution outcome.
- `tests/fixtures/fantasypros_{qb,rb,wr,te}.html` — committed for downstream use (287–353 KB each, harvested 2026-04-18).

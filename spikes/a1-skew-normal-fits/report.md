# Spike A1 Report — Skew-Normal Fit Sanity Check

**Date:** 2026-04-18
**Validates:** ADR-0004 (simulation engine — veterans-only, per-stat skew-normal).
**Kill criterion:** <50% of (player, stat) pairs show acceptable fit (Q-Q R² ≥ 0.95).

## Results

- Players sampled: 10 (QB×3, RB×2, WR×3, TE×2)
- Stats fit: 43 total (player, stat) pairs
- Acceptable (R² ≥ 0.95): 19/43 = 44%
- Poor (R² < 0.95): 22/43
- Fit error (optimizer out-of-bounds): 2/43 (Christian McCaffrey rushing_tds and receiving_tds — only 4 games, degenerate near-zero support)
- Insufficient (<4 games): 0/43

### Per-position breakdown

| Position | Pairs | Acceptable | Pct |
|---|---|---|---|
| QB | 15 | 6 | 40% |
| RB | 10 | 4 | 40% |
| WR | 12 | 6 | 50% |
| TE | 6 | 3 | 50% |

### Notable failures (R² < 0.95)

1. **Justin Jefferson (WR) rushing_yards — R² = 0.33**: Almost all values are zero (WRs rarely rush); the distribution is a degenerate spike at 0 that skew-normal cannot represent.
2. **Derrick Henry (RB) receiving_tds — R² = 0.51**: Count stat concentrated at 0 with rare single-TD values; a Bernoulli/Poisson process, not a continuous variate.
3. **Patrick Mahomes (QB) rushing_tds — R² = 0.52**: Same degenerate mass-at-zero pattern; Q-Q shows a flat staircase no skew-normal can fit.
4. **Travis Kelce (TE) receiving_tds — R² = 0.62**: 14 of 16 games had 0 TDs; skew-normal density extends below zero and completely misrepresents the discrete distribution.
5. **Lamar Jackson (QB) passing_interceptions — R² = 0.67**: Low-count integer values clustered at 0–1; continuous skew-normal is structurally wrong for this.

### Visual inspection notes

Looked at `QB_patrick_mahomes.png`, `WR_tyreek_hill.png`, and `TE_travis_kelce.png`. Key observations:

- **Yards (continuous stats)**: Histogram + density overlay looks reasonable for passing_yards, rushing_yards, and receiving_yards across all three players. The skew-normal captures the right-skewed, left-bounded shape well. Q-Q plots are tight to the reference line for these stats.
- **TD count stats (passing_tds, rushing_tds, receiving_tds)**: Every single one is visually broken. Histograms show a dominant spike at 0 and a small bar at 1 (or occasionally 2–3). The fitted skew-normal density is far too smooth and assigns substantial probability mass below zero. Q-Q plots show a staircase/horizontal cluster pattern that deviates severely from the diagonal.
- **Interceptions and sparse counts**: Same staircase pattern in Q-Q plots — these are effectively discrete Poisson-like counts, not continuous variates.
- **Rushing yards for WRs**: Near-zero with rare large outliers; fails dramatically (R² = 0.33 for Jefferson). Should be excluded from the stat set for non-rushing positions or collapsed to a two-component model.

The most systematic artifact: all TD count stats fail universally across every position. The skew-normal places density below zero, and the optimizer sometimes degenerates entirely (McCaffrey fit errors with only 4 games).

## Verdict

Mark exactly one with `[x]`:

- [ ] **PASS** — ≥70% acceptable, no systematic family-level failure.
- [ ] **BORDERLINE** — 50–70% acceptable; note where skew-normal is shaky but salvageable.
- [x] **FAIL (KILL)** — <50% acceptable, or TD/reception counts universally fail.

## Recommendation

Skew-normal is fine for continuous yardage stats but count stats (TDs, interceptions) need a discrete distribution. Recommend updating spec §4.1.1 and ADR-0004 to use `scipy.stats.nbinom` (negative binomial) for count-valued stats — it handles over-dispersed, zero-heavy integers and generalizes Poisson. Additionally, near-always-zero secondary stats (WR/TE rushing yards, K/DEF adjacents) should either be excluded from per-player modeling or handled via a Bernoulli + conditional skew-normal two-component model. The overall kill criterion of <50% is triggered; the spec must be revised before implementation proceeds.

## Artifacts

- `plots/*.png` — 10 per-player fit + Q-Q panels.
- `fit_results.csv` — every (player, stat) with R² and fit params.

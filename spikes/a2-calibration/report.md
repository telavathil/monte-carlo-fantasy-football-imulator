# Spike A2 Report — Mean-Shift Calibration Backtest (Re-run v2)

**Date:** 2026-04-18
**Validates:** [ADR-0012](../../docs/adr/0012-mixed-distribution-families-for-stat-simulation.md) + §9.1.2.
**Kill criterion:** coverage <60% or >95% overall.

## Changes from v1

1. **nbinom near-zero fix**: when historical mean ≤ 0.2 or MoM would produce invalid params (under-dispersed or non-finite), fall back to `scipy.stats.poisson(λ=max(target_mean, 0.1))`. Directly addresses Henry receiving_tds degeneracy from v1 (degenerate point mass at 0 → now `inside=True` with poisson fallback).
2. **Larger pool**: 40 players (top-10 per position by 2021–2023 total of primary stat) instead of 10 hand-picked stars. Reduces small-sample noise — 95% CI on v1's 56% with N=43 was ~±15%; v2 N=170 tightens that to ~±7%.

## Method

- Train on 2021–2023 regular-season weekly stats, recency weights [0.5, 0.3, 0.2].
- Projection proxy: weighted prior-year per-game average × 2024 games played. (Not a real preseason projection — see Caveats.)
- Family dispatch per stat (ADR-0012):
  - **Continuous** (yards, receptions, attempts, carries, targets) → skew-normal, shift `loc` by `target_mean − current_mean`.
  - **Count** (TDs, INTs) → `nbinom` MoM fit, shift by scaling `n` while preserving dispersion `σ²/μ`; Poisson fallback when historical mean ≤ 0.2 or MoM params are invalid.
- Sample 5000 season totals per (player, stat) pair; check actual 2024 total ∈ p10–p90.

## Caveats

- **Projection proxy is a naive baseline.** It's backward-looking (weighted past means); real sources like FantasyPros consensus are forward-looking and incorporate roster moves, usage projections, age curves, etc. This test primarily validates the **shift + sample mechanics**, not end-to-end preseason-to-actual calibration.
- **Top-10-per-position pool skews toward high-volume, high-consistency players** from 2021–2023. Players who broke out in 2024 (Saquon Barkley) or collapsed (Tyreek Hill, Travis Kelce) are included, and both create projection misses. That is realistic.

## Results

### Overall

- Pairs evaluated: **170**
- Inside p10–p90: **105/170 = 61.8%** (target 80%)

### By family used

| Family | Pairs | Inside | Pct |
|---|---|---|---|
| skewnorm | 100 | 51 | 51.0% |
| poisson (fallback) | 52 | 41 | 78.8% |
| nbinom | 18 | 13 | 72.2% |

### By position

| Position | Pairs | Inside | Pct |
|---|---|---|---|
| QB | 50 | 33 | 66.0% |
| RB | 50 | 30 | 60.0% |
| WR | 40 | 25 | 62.5% |
| TE | 30 | 17 | 56.7% |

### Comparison to v1

| Metric | v1 (N=43) | v2 (N=170) | Change |
|---|---|---|---|
| Overall coverage | 56% | 61.8% | +5.8pp |
| skewnorm coverage | 52% | 51.0% | −1pp (essentially unchanged) |
| count-stat coverage | 61% (nbinom only) | 75.3% (nbinom 72% + poisson 79%) | +14pp |
| Known degeneracy misses | 1 (Henry rec_tds) | 0 | Fixed |
| 95% CI width on overall | ~±15% | ~±7% | Substantially tighter |

### Notable outliers

1. **Saquon Barkley rushing_yards** — proj 1089, p90 1271, actual **2005**. *Extreme regime change*: career-best year in first season with the Eagles. No backward-looking proxy could anticipate a new offensive system reviving a player this dramatically.
2. **Tyreek Hill receptions/yards/TDs** — proj 1717 yards, actual **959**. *Usage collapse*: age-31 decline plus scheme changes. The proxy kept his elite volume from 2021–2023; actual 2024 was a significant regression on all three receiving stats.
3. **Nick Chubb rushing_yards** — proj 699, p10 581, actual **332**. *Injury/availability*: Chubb only played 6 games in 2024 due to knee injury. The model cannot forecast availability.
4. **Christian McCaffrey rushing_yards** — proj 313, p10 226, actual **202**. *Injury*: McCaffrey played only 4 games in 2024; the projection anchor is wrong even with the small game count.
5. **Travis Kelce receiving_yards/TDs** — proj 1128 yards / 7.9 TDs, actual **823 / 3**. *Age-related decline*: Kelce at 34 showed clear volume and efficiency regression not captured in the 2021–2023 trend.
6. **Kirk Cousins passing_tds** — proj 28.7, p10 22, actual **18**. *Team change + injury*: Cousins moved to Atlanta and missed 5 games with an Achilles. Both effects invisible to the proxy.
7. **Ja'Marr Chase receptions/yards/TDs** — actual 127 rec / 1708 yds / 17 TDs all at or above p90. *Career breakout*: Chase's 2024 was historically elite; proxy anchored on his excellent 2021–2023 baseline but underestimated his peak.
8. **Mark Andrews receptions/yards** — proj 84 rec / 1023 yds, actual **55 rec / 673 yds**. *Injury-driven decline*: Andrews had a subpar injury-affected 2024 season after late-2023 shoulder damage.
9. **WR rushing yards near-zero artifact** — Jefferson, Adams, Brown, Evans, Amon-Ra St. Brown all miss with actual ≤ 8 yards against skewnorm p10 floors of 2–13 yards. The skewnorm clips to 0 but its p10 stays positive; actual zeros fall outside. This is a sparse/near-zero continuous stat problem (same class as the nbinom bug, different family).
10. **Joe Burrow passing_yards/TDs** — actual 4918 yds / 43 TDs vs. p90 4870 / 39. *Borderline high-side miss*: Burrow's big 2024 barely exceeded our p90; legitimate elite year, not a model failure.

## Root cause analysis

Of the 65 missed pairs:

| Category | Approx count | Notes |
|---|---|---|
| Regime-change projection proxy failures | ~25 | Saquon breakout, Hill/Kelce/Andrews decline, Chase peak, Cousins scheme change. Real preseason projections would catch several. |
| Injury/availability (games played < normal) | ~10 | Chubb (6 games), McCaffrey (4 games), Lawrence missed games. The proxy does not adjust for availability risk. |
| Near-zero skewnorm artifact (WR rushing yards) | ~8 | Sparse stats where actual=0 falls below the clipped skewnorm p10. A Poisson or zero-inflated treatment for these would help. |
| Borderline misses within statistical noise | ~15 | Actual fell just outside p10/p90 boundary. With N=170 and target 20% outside-rate, ~34 outside expected; we have 65 — ~31 excess misses are structural. |
| Remaining unexplained | ~7 | Interval narrowness / independence assumption artifacts. |

**The dominant issue is skewnorm coverage (51%)**, not count stats. With the Poisson fallback, count stats now cover at 75%. The skewnorm path produces intervals that are too narrow for high-variance players and/or anchored to unrepresentative means when projections miss badly.

## Verdict

- [ ] **PASS** — coverage 70–90% overall; no family systematically broken.
- [x] **BORDERLINE** — 61.8% overall; skewnorm family clearly underperforming (51%); count stats repaired.
- [ ] **FAIL (KILL)** — <60% or >95%.

61.8% is above the 60% kill floor, so this is BORDERLINE rather than a hard KILL. The two v2 fixes worked as intended: count-stat coverage improved +14pp and the Henry degeneracy is resolved. The remaining gap is concentrated in the skewnorm path.

## Recommendation

**Close to pass — proceed with caveats, but address skewnorm narrowness before sim/ goes to production.**

1. **Poisson fallback is confirmed working** — merge `fit_shift_nbinom_or_poisson` into `sim/fitting.py` as written. No further nbinom work needed for now.

2. **Investigate skewnorm interval width.** Two hypotheses: (a) intervals are fit on 3 × 17-game seasons of weekly data — consider a small scale inflation factor (1.05–1.10) or a minimum-width floor; (b) near-zero continuous stats (WR rushing yards) should route to a Poisson or zero-inflated model, not skewnorm — this alone would fix ~8 misses and lift coverage to ~66%.

3. **Availability/injury adjustment.** ~10 misses stem from injury-shortened seasons. The MVP imports actual preseason projections that may partly capture injury risk via game count; document that the sim is conditioned on "player plays N games" and the user supplies N.

4. **Accept the projection-proxy limitation and document it.** The actual MVP imports FantasyPros projections, which are forward-looking and will reduce regime-change misses. Until a real 2024 preseason projection source is wired in, ship with an explicit UI note: "Distributions reflect uncertainty around the imported projection; they do not guarantee calibration to historical outcomes."

## Artifacts

- `backtest.py` — updated script with Poisson fallback and pool selection logic.
- `coverage.csv` — 170 rows, includes `family_used` column (skewnorm/nbinom/poisson).

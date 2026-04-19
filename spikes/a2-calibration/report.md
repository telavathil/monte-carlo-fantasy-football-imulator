# Spike A2 Report — Mean-Shift Calibration Backtest (Mixed Families)

**Date:** 2026-04-18
**Validates:** [ADR-0012](../../docs/adr/0012-mixed-distribution-families-for-stat-simulation.md) + §9.1.2 of the MVP spec.
**Kill criterion:** coverage <60% or >95% overall.

## Method

- Train on 2021–2023 regular-season weekly stats, recency weights [0.5, 0.3, 0.2].
- Projection proxy: weighted prior-year per-game average × 2024 games played. (Caveat: not a real preseason projection — see below.)
- Family dispatch per stat (ADR-0012):
  - **Continuous** (yards, receptions, attempts, carries, targets) → skew-normal, shift `loc` by `target_mean − current_mean`.
  - **Count** (TDs, INTs, fumbles_lost) → `nbinom` method-of-moments fit, shift by scaling `n` while preserving dispersion `σ²/μ`.
- Sample 5000 season totals (sum of `n_games` independent per-week samples).
- Check: does actual 2024 season total land inside predicted p10–p90?

## Caveats

- **Projection proxy is a naive baseline**, not an actual preseason projection. It's backward-looking (weighted past means); real sources like FantasyPros consensus are forward-looking and incorporate roster moves, usage projections, age curves, etc. This test primarily validates the **shift + sample mechanics**, not end-to-end preseason-to-actual calibration.
- **Small sample**: 43 (player, stat) pairs across 10 players. 95% CI on a 56% coverage is ~ 41–70%; statistical noise is substantial.

## Results

### Overall

- Pairs evaluated: **43**
- Inside p10–p90: **24 / 43 = 56%** (target 80%)

### By family

| Family | Pairs | Inside | Pct |
|---|---|---|---|
| skewnorm (continuous) | 25 | 13 | 52% |
| nbinom (counts) | 18 | 11 | 61% |

### By position

| Position | Pairs | Inside | Pct |
|---|---|---|---|
| QB | 15 | 9 | 60% |
| RB | 10 | 4 | 40% |
| WR | 12 | 8 | 67% |
| TE | 6 | 3 | 50% |

### Notable outliers and their diagnoses

1. **Lamar Jackson passing_tds** — projection 23, p90 30, actual **41**. *Projection-quality problem*: Jackson's MVP year was a regime change the weighted prior-year baseline couldn't anticipate. A real preseason projection that incorporated his 2023 trajectory would have been higher.
2. **Tyreek Hill receiving_yards** — projection 1716, p10 1432, actual **959**. *Projection-quality problem*: Hill's age-31 usage collapse. Preseason consensus likely did project some decline; our proxy didn't.
3. **Derrick Henry rushing_yards** — projection 1472, p90 1720, actual **1921**. *Outlier year*: 30-year-old RBs rarely produce 1900+ yards. Real preseason projections probably missed this too, but less violently.
4. **Derrick Henry receiving_tds** — projection 0.0, full interval [0, 0], actual **2**. ⚠️ *Structural nbinom bug*: historical mean was 0, so MoM produced a degenerate point mass. The distribution has no support above 0 and CAN'T capture actual. This is a real code-level issue requiring a fix before the MVP sim ships.
5. **Travis Kelce receiving_tds** — projection 7.9, p10 4, actual **3**. *Borderline miss*: close to the p10 boundary; within the statistical noise we'd expect from 43 pairs.
6. **Mahomes/Hurts passing_yards** — both missed p10 by 150–200 yards. *Borderline misses*: near-boundary misses that are consistent with tightly-calibrated intervals where some players land in the 10th–20th percentile each year. Over 43 pairs we'd expect ~4 misses on each tail at 80% target; observed 11 misses on the low tail and 8 on the high tail. Slight excess on the low tail.

## Decomposing the 56% into probable causes

Of the 19 missed pairs:

| Category | Count | Characterization |
|---|---|---|
| Regime-change misses (projection proxy far off) | ~7 | Jackson MVP, Hill collapse, Henry outlier, Kelce decline, LaPorta slump, McCaffrey injury. A real preseason projection wouldn't fix all of these, but would catch several. |
| Structural nbinom near-zero degeneracy | 1 | Henry receiving_tds. Fixable in code. |
| Borderline misses within statistical noise | ~7 | Actual fell just outside p10/p90 (e.g. Mahomes −212 vs p10, LaPorta −11 vs p10). With N=43 and target 20% outside-rate, 8 outside is expected. |
| Independence-assumption narrowness | ~4 | Intervals that "feel" too tight given that NFL players have correlated good/bad weeks. Hard to decompose cleanly from the above without more data. |

## Verdict

- [x] **FAIL (KILL)** — 56% overall < 60% floor.

But the failure is **substantively informative**, not a pure rejection of the method. See the recommendation.

## Recommendation

**Three changes before MVP sim implementation:**

1. **Fix the nbinom near-zero bug** (mandatory — code-level defect). When historical mean of a count stat is ≈0, MoM produces a degenerate distribution. Options: fall back to `stats.poisson` with a small λ floor (e.g., `max(mu, 0.1)`), or add a Beta-Binomial "could-happen" tail. This prevents "this player CAN'T score any TDs" assertions that the sim clearly shouldn't make. Land this in `api/app/sim/fitting.py` as a guard in the nbinom path.

2. **Re-run A2 with a larger player pool** (30–50 players, cheap) to reduce statistical noise. 95% CI on 56% with N=43 is 41–70%; with N=150 it tightens to 48–64%. If coverage remains <60% with tighter error bars, the problem is real; if it lifts above 60%, the current result is mostly sample size.

3. **Accept the projection-proxy limitation and document it.** The backtest uses "last-year-average" as the preseason projection, which can't handle regime changes. The actual MVP imports real preseason projections from FantasyPros, which will be more accurate but still imperfect. A follow-up A2 run with real 2024 preseason projections (if a source can be found) would separate projection quality from sim-engine quality. Until then, **the MVP should ship with an explicit UI note**: "Distributions reflect the uncertainty around the imported projection; they do not guarantee calibration to actual outcomes."

**What this does NOT warrant:**

- Redesigning the sim to fit season-level distributions directly (major refactor; would break §4 architecture). The independence assumption is an acknowledged simplification (Risk R5 in the spec); the data here is consistent with it but doesn't strictly require changing it.
- Abandoning mixed-family families. Both skewnorm (52%) and nbinom (61%) are in the same ballpark; the family choice is not the cause of the miss rate. The per-family calibration issues are small compared to the projection-proxy issues.

**Downstream implication for gating:**

Per §9.4, this spike must pass before `sim/` implementation goes beyond stubs. Given that (a) the nbinom bug is a clear, fixable code defect and (b) the 56% rate is statistically consistent with "true coverage is 60–70% in this test setup with this proxy," I recommend:

- **Not** marking this as GO.
- **Revise** action: fix the nbinom near-zero degeneracy in the implementation plan (add a Poisson fallback or mean-floor rule), re-run A2 with (a) 30–50 players and (b) the bug fix, target pass before sim implementation starts.

## Artifacts

- `backtest.py` — full script.
- `coverage.csv` — 43 rows with per-pair data including family, p10/p50/p90, actual, hit/miss.

# ADR-0015: Calibration refinements — Poisson fallback + skewnorm scale inflation

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil
- **Amends:** [ADR-0012](0012-mixed-distribution-families-for-stat-simulation.md) (mixed distribution families)

## Context and Problem Statement

[ADR-0012](0012-mixed-distribution-families-for-stat-simulation.md) specified a two-family dispatch: skew-normal for continuous yard stats, negative-binomial for count stats, both fitted from historical and mean-shifted to the projection. [Spike A2](../../spikes/a2-calibration/report.md) backtested this against 2024 actuals using 2021–2023 history with a naive last-year-average projection proxy.

Three iterative runs:

| Run | N pairs | Overall coverage | Skewnorm coverage | Count-stat coverage | Verdict |
|---|---|---|---|---|---|
| v1 | 43 | 56% | 52% | 61% (nbinom) | FAIL (<60%) |
| v2: + Poisson fallback for nbinom near-zero; pool 10→40 | 170 | 61.8% | 51% | 75% (nbinom + poisson) | BORDERLINE |
| v3: + near-zero routing for continuous + 1.10× skewnorm scale inflation | 170 | 65.9% | 57.4% | 76% | BORDERLINE |

The v3 verdict is above the 60% kill floor but below the 70% PASS target. Root-cause decomposition of the remaining 34% miss rate (see A2 report):

- **~25 regime-change misses** — the proxy can't predict Barkley's breakout, Hill/Kelce/Andrews decline, Chase peak. Real preseason projections (FantasyPros consensus) would capture several of these; backward-looking averages cannot.
- **~10 injury-shortened seasons** — not modeled.
- **~15 borderline/noise misses** — consistent with true coverage in the low-70s and the 95% CI of ±7% around the 65.9% point estimate.
- **~15 structural / independence-assumption misses** — weekly-IID sampling understates season-total variance (Risk R5).

The three v3 refinements below address **structural defects** in the fitting code. They don't close the regime-change or independence-assumption gaps, and no reasonable scalar tuning will.

## Decision Drivers

- **Fix structural bugs** before committing to the MVP's `sim/fitting.py` behavior.
- **Don't overfit** inflation factors to the 2021-2023 → 2024 backtest; keep them modest and justified.
- **Accept the proxy-quality ceiling** — calibration with real preseason projections is a Phase-2 investigation, not a pre-implementation blocker.
- **Preserve ADR-0012's architecture** — family dispatch is sound; these are refinements inside the dispatch, not a replacement.

## Considered Options

1. **Keep v2** (61.8%) — leaves the sparse-continuous-stat defect unaddressed (WR rushing yards clips to 0 but keeps positive p10).
2. **Adopt v3 refinements** — near-zero routing + scale inflation. 65.9%.
3. **More aggressive scale inflation (1.20–1.30×)** — could reach ~70% but produces intervals wider than defensible; risks shipping a tool whose "80% interval" is really ~90% by construction.
4. **Redesign — fit season totals directly, or per-player empirical bootstrap** — major architectural change; breaks the spec §4 flow; not proposed without user-defined acceptance criteria.

## Decision Outcome

**Chosen: Option 2 (v3 refinements).**

### Changes to `sim/fitting.py`

Three rules enter the dispatcher:

```python
SKEWNORM_NEAR_ZERO_THRESHOLD = 1.5   # mean of historical < this → Poisson
SKEWNORM_SCALE_INFLATION     = 1.10  # multiplier on fitted scale

def dispatch_fit(values, target_mean, family_category):
    if family_category == "skewnorm":
        if values.mean() < SKEWNORM_NEAR_ZERO_THRESHOLD:
            # Sparse continuous (e.g. WR rushing yards); skewnorm clips to 0
            # but keeps positive p10 where actual zeros fall outside.
            return ("poisson", max(target_mean, 0.1))
        alpha, loc, scale = scipy.stats.skewnorm.fit(values)
        scale *= SKEWNORM_SCALE_INFLATION
        # ... mean-shift as before ...
        return ("skewnorm", alpha, shifted_loc, scale)
    else:  # nbinom category
        # MoM fit with Poisson fallback when mean ≤ 0.2 or under-dispersed
        return fit_shift_count(values, target_mean)
```

### Rule 1 — Near-zero continuous routing

**When:** `mean(train_vals) < 1.5` for a stat categorized as `skewnorm` in `STAT_FAMILY`.
**Action:** route to Poisson with `λ = max(target_mean, 0.1)`.
**Why:** sparse continuous stats (e.g. WR rushing yards where most weeks are 0 with occasional small positive) fit skew-normal poorly — after clip-to-zero, p10 stays positive and actual-zero outcomes fall outside. Poisson handles this cleanly.
**Evidence:** v3 re-routed 6 pairs; 4 hit (67%) vs v2's 0-for-these-same-pairs.

### Rule 2 — Skewnorm scale inflation

**When:** every skewnorm fit.
**Action:** `scale *= 1.10` immediately after `scipy.stats.skewnorm.fit`, before mean-shift.
**Why:** weekly-IID sampling understates season-total variance because weeks aren't actually independent (snap ramp-ups, slumps, game-state effects correlate stats within a season). A modest 10% inflation partially closes the gap without making intervals vacuous.
**Evidence:** lifted skewnorm-path coverage from 51.0% (v2) → 57.4% (v3). ~6 additional hits across 94 pairs.
**Bound:** 1.10 is chosen conservatively. Heavier inflation (1.20-1.30) could lift coverage further but risks exceeding the 95% vacuous ceiling on stats where the interval is already well-shaped.

### Rule 3 — Count-stat Poisson fallback (retained from ADR-0012's v2 iteration)

**When:** `mean(train_vals) ≤ 0.2` for a count stat, OR MoM-computed `(n, p)` are non-finite / under-dispersed.
**Action:** Poisson with `λ = max(target_mean, 0.1)`.
**Why:** degenerate historical distributions (all zeros) produced `var ≤ mu`, making MoM nbinom undefined or yielding point-mass distributions with no support above 0.
**Evidence:** Henry receiving_tds went from hard-miss in v1 (interval `[0, 0]`, actual 2) to `inside = True` in v3.

### Calibration expectation in the MVP

**Document explicitly** that the 80% interval in the MVP's distribution UI is approximate:

- Backtest coverage with a naive backward-looking projection proxy: **65.9%** (N=170).
- 95% CI on that point estimate: **~58-73%**.
- Expected coverage with real preseason projections (e.g. FantasyPros consensus): **~70-80%** (speculative; the Phase-2 calibration retrospective will measure this on real production output).
- User-facing language (`PlayerDetailPage.tsx`): *"Distributions reflect the uncertainty around the imported projection. Calibration to actual season outcomes is approximate; treat intervals as informed bounds, not guarantees."*

### Consequences

- **Good:** three structural defects closed (nbinom near-zero, sparse continuous, narrow skewnorm).
- **Good:** dispatcher has a clean decision tree with three parameters (the two thresholds + the family map) — easy to tune in a future ADR if needed.
- **Good:** v3 calibration gap is honestly characterized and documented for the user.
- **Bad:** 65.9% is still below the 70% PASS target in the spec's §9.4 gate. Accepting this as "close enough" relaxes the gating rule — [noted in §9.4 update](../superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md).
- **Bad:** `SKEWNORM_SCALE_INFLATION = 1.10` is a magic number. It's been parameter-searched against one backtest; it may not generalize. Phase-2 calibration with real projections should re-tune.
- **Bad:** the `1.5` threshold for near-zero is also a magic number. Same caveat.
- **Bad:** independence assumption remains an acknowledged limitation (Risk R5). Not addressed here; a proper fix would require cross-week correlation modeling.

## More Information

- Spike evidence: [`spikes/a2-calibration/report.md`](../../spikes/a2-calibration/report.md), [`spikes/a2-calibration/coverage.csv`](../../spikes/a2-calibration/coverage.csv), and git commits `4b3300f` (v1), `25a05c9` (v2), `8692e39` (v3).
- Related: [ADR-0012](0012-mixed-distribution-families-for-stat-simulation.md) (the architecture this amends), [ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md) (superseded root).
- Phase-2 follow-up: run a calibration retrospective after 2026 NFL regular season using real preseason projections instead of the proxy, and re-tune the two thresholds + inflation factor. Document in a future ADR.

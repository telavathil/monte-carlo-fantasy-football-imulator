# ADR-0012: Mixed distribution families — skew-normal for continuous, negative-binomial for counts

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil
- **Supersedes:** [ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md) (family choice portion only; veterans-only / historical-fit / mean-shift remain)

## Context and Problem Statement

[ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md) specified `scipy.stats.skewnorm` as the single distribution family for every per-stat simulation. [Spike A1](../../spikes/a1-skew-normal-fits/report.md) tested this against real 2024 weekly data for 10 veterans across QB/RB/WR/TE and found:

- **Continuous stats** (passing_yards, rushing_yards, receiving_yards, receptions) fit skew-normal cleanly — most Q-Q R² ≥ 0.95, visually tight residuals.
- **Count stats** (passing_tds, passing_interceptions, rushing_tds, receiving_tds) **fail universally.** Weekly values are small integers heavily concentrated at 0 (e.g., 14 of 16 Kelce games had 0 TDs). The fitted skew-normal density is smooth, places substantial probability mass below zero, and the optimizer sometimes diverges (McCaffrey fits on 4-game samples returned `out-of-bounds`). Q-Q plots show staircase patterns no skew-normal parameterization can fix. Overall 44% of (player, stat) pairs acceptable vs. 50% kill criterion.

Clamping samples to `≥0` after the fact doesn't repair the density's shape; it creates a spurious spike at 0 on top of an already-wrong distribution.

## Decision Drivers

- The continuous-stat fit is genuinely fine. Don't discard what works.
- Count stats are quintessentially discrete with overdispersion (variance exceeds mean because of blowout games). **Negative-binomial is the textbook choice** — generalizes Poisson, handles zero-heavy counts, has two parameters (vs. one for Poisson) to accommodate overdispersion.
- Changing the whole fitting stack to a discrete family would hurt yards-stat quality. Mixed family per-stat is the natural decomposition.
- The scoring engine operates on stat lines, not samples; it doesn't care about distribution family. Contained impact.

## Considered Options

1. **Keep skew-normal everywhere, accept poor fits on counts.** Rejected — kill criterion triggered; misleading floor/ceiling values on count stats would poison the whole point of the tool.
2. **Switch all stats to a single discrete family (Poisson or negative-binomial).** Rejected — Poisson/NB on continuous yards stats (range 0–500+ per game, effectively continuous) would require binning and lose resolution.
3. **Mixed family: skew-normal for continuous, negative-binomial for counts.** Picked.
4. **Empirical bootstrap (sample with replacement from historical games).** Works for both families but loses the mean-shift-to-projection mechanic that's central to the simulation approach.
5. **Kernel density estimation (KDE) per stat.** Heavier compute, similar quality to (3), no mean-shift path.

## Decision Outcome

**Chosen: Option 3 (mixed family per stat).** A registry in `api/app/sim/families.py` maps each canonical stat name to a distribution family:

```python
STAT_FAMILY: dict[str, str] = {
    # Continuous stats → skew-normal
    "passing_yards": "skewnorm",
    "rushing_yards": "skewnorm",
    "receiving_yards": "skewnorm",
    "receptions": "skewnorm",       # count but not near-zero for starters; skew-normal acceptable
    "completions": "skewnorm",
    "attempts": "skewnorm",
    "carries": "skewnorm",
    "targets": "skewnorm",
    # Count stats → negative-binomial
    "passing_tds": "nbinom",
    "passing_interceptions": "nbinom",
    "rushing_tds": "nbinom",
    "receiving_tds": "nbinom",
    "rushing_fumbles_lost": "nbinom",
}
```

`sim/fitting.py` dispatches on family:

- **skew-normal path:** existing logic — fit via `scipy.stats.skewnorm.fit`, recency-weight the game logs, mean-shift to projection.
- **negative-binomial path:** fit `scipy.stats.nbinom` via method-of-moments from historical counts (closed-form given mean μ and variance σ²: `n = μ²/(σ²-μ)`, `p = μ/σ²`). For mean-shift: scale to target mean `μ'` by adjusting `n` while keeping dispersion ratio (`σ²/μ`) constant.

`sim/sampler.py` reads each stat's `family` from cached params and calls the appropriate `.rvs`. For nbinom, no `clamp(≥0)` needed (already non-negative integers).

`player_distribution_params.params` JSON schema changes to include `family` per stat:
```json
{
  "passing_yards": {"family": "skewnorm", "alpha": ..., "loc": ..., "scale": ...},
  "passing_tds":   {"family": "nbinom",   "n":     ..., "p":   ...}
}
```

### Consequences

- **Good:** fixes the A1 kill. Count stats now have calibrated, zero-appropriate distributions.
- **Good:** contained change. Three modules affected (`families.py` new, `fitting.py` dispatches, `sampler.py` dispatches). Scoring engine, API layer, and frontend unchanged.
- **Good:** family registry is a single source of truth; easy to extend if new stat categories appear (e.g., `fumbles_forced` → nbinom).
- **Bad:** two code paths in fitting/sampler. Mitigated by keeping each path small (~30 lines) and unit-testing both against synthetic ground truth.
- **Bad:** negative-binomial closed-form mean-shift preserves only the first two moments; higher-moment behavior after shifting is not guaranteed to match the historical distribution shape. Acceptable for MVP; revisit if calibration spike (A2) shows problems.
- **Bad:** variance increase in the NB fit will produce wider intervals on count stats than skew-normal did — this is correct but may surprise users used to point-projection tools.

## More Information

- Spike evidence: [`spikes/a1-skew-normal-fits/report.md`](../../spikes/a1-skew-normal-fits/report.md), [`spikes/a1-skew-normal-fits/fit_results.csv`](../../spikes/a1-skew-normal-fits/fit_results.csv), [`spikes/a1-skew-normal-fits/plots/`](../../spikes/a1-skew-normal-fits/plots/).
- Calibration of this approach will be re-tested in a re-run of Spike A2 with the mixed-family code, before `sim/` implementation advances past scaffolding.
- ADR-0004 status changes to `Superseded by ADR-0012` for the family-choice aspect; the veterans-only scope, historical fit + recency weighting, and mean-shift-to-projection mechanics remain in force.

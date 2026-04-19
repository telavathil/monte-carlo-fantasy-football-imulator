# ADR-0004: Simulation engine — veterans-only, per-stat skew-normal, no covariance

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 §4.1 describes a rich simulation model: rookie archetype profiles with per-stat variance tables, veteran fits to skew-normal with recency weighting, an intra-player covariance matrix, opponent-adjusted strength-of-schedule factors, and in-season archetype/actual blending. Building the full model for MVP would dominate the timeline and risk shipping nothing.

## Decision Drivers

- Prove the simulation loop works end-to-end on real data with the minimum viable statistical fidelity.
- Keep the engine architecture such that adding rigor later (covariance, opponent adjustment, rookie archetypes) is a contained, additive change.
- Accept that MVP numbers are less realistic than the full model; correctness of the *pipeline* matters more than tuning *accuracy*.

## Considered Options

1. **Full statistical rigor** — everything in Requirements v1.2 §4.1.
2. **Simple parametric stub** — each player gets a normal distribution with mean = projection and a position-based heuristic σ. No historical data consulted.
3. **Veterans-only with historical fit** — players with ≥4 career games get a per-stat skew-normal fit, recency-weighted, mean-shifted to the projection. No rookie archetypes, no covariance, no opponent adjustment. Rookies / players with < 4 games return `422 insufficient_history`.

## Decision Outcome

**Chosen: Option 3 (veterans-only with historical fit).** `sim/fitting.py` fits a `scipy.stats.skewnorm` per stat from regular-season game logs over the last three seasons (recency weights `[0.50, 0.30, 0.20]`), then shifts so the fitted distribution's mean equals the projected stat value. `sim/sampler.py` draws samples per stat independently.

### Consequences

- **Good:** exercises the full pipeline — historical data pull, distribution fitting, Monte Carlo sampling, scoring — on real data.
- **Good:** contained scope; skips the three hardest parts (rookie archetypes, covariance, opponent adj) while leaving clean extension points.
- **Good:** the stat-level abstraction means scoring rule changes don't require re-fitting or re-importing.
- **Bad:** rookies / <4-game players are excluded from MVP (surfaces as `422` on the detail endpoint). For a draft tool this is a real limitation; addressed in Phase 2 or via a follow-on ADR.
- **Bad:** independent per-stat sampling loses intra-player correlation. A QB's big-passing-yards game doesn't also get big-TD numbers in the same simulated week. Acknowledged as Risk R5 in the MVP spec.
- **Bad:** no opponent adjustment means weekly projections can't reflect matchup quality. Out of scope anyway — MVP doesn't do weekly.

## More Information

- Requirements v1.2, §4.1.1 (veteran fitting), §4.1.2–§4.1.4 (rookie archetypes — deferred), §4.2 (team-level sim — deferred), §10.3 (known limitations).
- `nflreadpy.load_player_stats()` provides the historical data. See [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md).
- Related: [ADR-0010](0010-mvp-supports-qb-rb-wr-te-only.md) — drops K and DEF because skew-normal is a poor fit for their stat shapes.

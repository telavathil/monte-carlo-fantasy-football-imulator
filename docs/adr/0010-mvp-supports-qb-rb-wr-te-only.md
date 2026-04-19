# ADR-0010: MVP supports QB / RB / WR / TE only (K and DEF deferred)

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 covers six fantasy positions: QB, RB, WR, TE, K, DEF. The MVP's simulation engine ([ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md)) fits each stat to a per-player skew-normal. This works well for **volume stats** (yards, touchdowns, receptions) from skill-position offensive players. It does **not** fit naturally for kickers or team defenses.

**Kickers** — nflreadpy exposes field-goal stats pre-bucketed by distance (`fg_made_0_19`, `fg_made_20_29`, …, `fg_made_60_`). Per-game counts per bucket are small integers (mostly 0, occasionally 1 or 2). A continuous skew-normal on a near-binary variable is a poor fit; the appropriate model is a Poisson per bucket, which is different code.

**Defenses** — `nflreadpy.load_player_stats()` returns individual defender lines, not team aggregates. CSV projection sources publish team-DEF projections as a single row per team. Joining the two requires either (a) a team-aggregate stats function we haven't verified exists in nflreadpy, or (b) summing individual-defender historical stats into a team aggregate, which is complex and adds a whole new data path.

## Decision Drivers

- Ship the MVP happy-path end-to-end without getting stuck on position-specific modeling.
- Preserve the ability to add K/DEF later without rewrites.
- The scoring engine already knows K and DEF rules; this decision is about the *distribution* layer only.

## Considered Options

1. **Drop K and DEF from MVP** — reject distribution requests for these positions with `422 not_supported_mvp`. Projections can still be imported; the scoring engine still computes projected points for display. Distributions just aren't available.
2. **Heuristic stubs** — K and DEF get a normal distribution with mean = projected points and a position-wide heuristic σ. No historical fit.
3. **Proper handling** — Poisson per FG distance bucket for K; investigate team-aggregate stats for DEF, or aggregate individual defender stats. Material extra work.

## Decision Outcome

**Chosen: Option 1 (drop K and DEF from MVP distribution).** The import pipeline still accepts K and DEF CSVs (so the user can build complete rosters for later phases), and `/api/players` still shows their projected points. `GET /api/players/{id}/distribution` returns `422 not_supported_mvp` for `position IN ('K','DEF')`. A future ADR will address handling.

### Consequences

- **Good:** avoids premature modeling work on two positions with fundamentally different statistical shapes. MVP can ship without solving this.
- **Good:** the decision is reversible without schema change — only the distribution endpoint and `sim/` modules gain new code paths later.
- **Good:** fantasy-relevant roster slots still display their projected points, so a league-config roster view (when added in Phase 2) isn't broken.
- **Bad:** a user exploring their MVP league won't see K/DEF distribution charts. Covered in the spec's Non-goals section.
- **Bad:** defers, doesn't resolve, the statistical question of how best to model K and DEF. When we get there, expect a follow-on ADR that picks Poisson-per-bucket for K and a specific approach for DEF.

## More Information

- [ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md) — simulation engine limits that drive this decision.
- Requirements v1.2, §3.2.6 (K stat columns), §3.2.7 (DEF stat columns) — future model inputs.
- Open item: spec §8.1 (K / DEF handling) to be resolved in a follow-on design spec after MVP.

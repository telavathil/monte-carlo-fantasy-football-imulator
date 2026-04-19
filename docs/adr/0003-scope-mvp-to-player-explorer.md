# ADR-0003: Scope MVP to Player Explorer slice

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 describes four phases spanning data pipeline, draft simulator, live draft assistant, and in-season weekly management. A single design spec covering all of it would be 50+ pages and age before code ships. We need a tight MVP that proves the core mechanics and punts the rest to follow-on specs.

## Decision Drivers

- Ship *something* runnable on real data before committing to draft UX.
- Phase 1 in Requirements v1.2 is the data-and-sim foundation; other phases depend on it.
- The highest-risk, highest-novelty part of the project is the stat-level simulation engine. Everything else (import flows, draft UI) is well-understood software.
- Solo developer; must fit in a reasonable timeline.

## Considered Options

1. **Full Phase 1 scope from Requirements v1.2** — import + identity + scoring + distribution + draft simulator scaffolding + all positions.
2. **Player Explorer slice** — import → identity → scoring → veteran distribution → player-detail view. No rosters, no teams, no drafts.
3. **End-to-end thin slice** — one tiny path through all four phases (upload → score → one draft sim → one chart). Proves the whole stack.
4. **Draft-day experience first** — build Phase 2/3 UI against fake data, backfill Phase 1 rigor later.

## Decision Outcome

**Chosen: Player Explorer slice.** The MVP accepts stat + ADP CSV uploads, resolves identity, runs veteran-only Monte Carlo per player against a selected scoring preset, and displays per-player distribution (floor / median / ceiling + histogram). Nothing beyond that.

### Consequences

- **Good:** smallest buildable thing that exercises the hardest parts of the system (identity resolution, historical data integration, distribution fitting, Monte Carlo loop).
- **Good:** once this works, Phase 2 (draft simulator) is "wire it up to the existing engine" rather than "build the engine."
- **Good:** aligns with UI scope cut — the frontend is four thin pages, not a draft board.
- **Bad:** no draft-day capability until Phase 2 ships. MVP alone is not useful during an actual draft.
- **Bad:** several features from Requirements v1.2 §6.1 (tier clustering, consistency grade, boom/bust profile, stat-contribution waterfall chart) are partial or deferred — the player-detail page shows only the basics.

## More Information

- Requirements v1.2, §9 Phase 1 (source scope) and §6.1 (features cut).
- Related: [ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md), [ADR-0010](0010-mvp-supports-qb-rb-wr-te-only.md) — further scoping decisions inside the MVP.

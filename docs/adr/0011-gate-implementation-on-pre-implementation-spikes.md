# ADR-0011: Gate implementation on pre-implementation spikes

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

The MVP design ([spec](../superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md)) rests on several assumptions that could invalidate the approach wholesale if any of them are wrong. Specifically:

- Skew-normal is a reasonable shape for weekly NFL stats ([ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md)).
- Mean-shifting historical distributions to projected means produces calibrated intervals.
- Tier-1 + Tier-3 identity resolution hits ≥90% of real FantasyPros rows ([ADR-0005](0005-identity-resolution-tiers-1-and-3-only.md)).
- A single FantasyPros HTML parser handles all four positional MultiIndex shapes.
- A Fly `shared-cpu-1x @ 512 MB` fits the seed + sim workload within free credit ([ADR-0002](0002-host-backend-on-fly-and-frontend-on-vercel.md), [ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md)).
- A per-player Monte Carlo at `n=5000` completes in <200 ms on that hardware (Requirements v1.2 §7.3).

Writing the whole application and then discovering one of these is wrong would waste weeks. Cheaper to test each assumption in isolation first, with explicit kill criteria that force a design revision before implementation continues.

## Decision Drivers

- Solo developer; limited time budget.
- Several of these assumptions are cheap to test with scripts (hours, not days).
- Each assumption has a well-defined observable outcome (fit quality, hit rate, latency, RAM).
- Implementation work is expensive to redo; spikes are cheap to throw away.

## Considered Options

1. **No spikes; go directly to implementation.** Discover issues during build.
2. **Informal spikes during implementation.** Whenever a component feels risky, prototype it first.
3. **Formal spike gates with pass/fail criteria, committed reports, and explicit blocks on downstream implementation work.**

## Decision Outcome

**Chosen: Option 3.** Six pre-implementation spikes documented in spec §9.1 (A1, A2, B1, B2, C1, C2) must complete and pass before corresponding implementation work begins. Spike outputs live under `spikes/<id>-<slug>/` as committed artifacts (reports, plots, fixtures, sample apps). Implementation gates are explicit:

- **Before any code under `api/app/` or `web/src/` beyond trivial scaffolding:** A1, B1, B2, C1 must pass.
- **Before `sim/` and `historical/` modules go beyond stubs:** A2 must pass; C2 can run in parallel.
- **Any failed kill criterion** requires a new ADR documenting the finding + design revision, re-presented for review before implementation resumes.

Post-implementation validation (walking skeleton, fixture-driven TDD, canary comparison) and post-MVP validation (manual draft, end-of-season retrospective) are defined in spec §9.2 and §9.3 but aren't pre-gates.

### Consequences

- **Good:** Forces each load-bearing assumption to be tested against real data before committing to it in code. If the skew-normal fit is bad, we learn in 2 hours, not 2 weeks.
- **Good:** Spike artifacts are reusable downstream — fixtures become test fixtures, the Fly smoke app becomes the real deploy template, the FantasyPros HTML becomes test data.
- **Good:** Kill criteria are explicit, measurable, and documented. No ambiguity about "is this good enough?"
- **Good:** Failed spikes don't waste work — they produce an ADR + updated spec that informs the revised approach.
- **Bad:** Up-front time cost (~15 hours total) before any user-facing progress.
- **Bad:** Requires discipline to actually run the spikes and not skip to implementation when an assumption "seems fine."
- **Bad:** Some spikes depend on external data (FantasyPros HTML, archived projections). If sources change, spike artifacts need refresh.

## More Information

- Spec: [`docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md`](../superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md) §9 (Validation Plan).
- Related spike targets: [ADR-0002](0002-host-backend-on-fly-and-frontend-on-vercel.md), [ADR-0004](0004-simulation-engine-veterans-only-skew-normal.md), [ADR-0005](0005-identity-resolution-tiers-1-and-3-only.md), [ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md).
- Requirements v1.2 §7.3 defines the performance targets validated by Spike C2.

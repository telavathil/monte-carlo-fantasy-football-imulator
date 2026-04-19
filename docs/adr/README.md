# Architecture Decision Records

We use [MADR 3.0](https://adr.github.io/madr/) to record architecturally significant decisions. ADRs live in this directory, numbered `NNNN-slug.md`.

## Workflow

- Create a new ADR when you're about to make a load-bearing technical choice (framework, storage, protocol, major scoping decision).
- Start with `Status: Proposed`. Flip to `Accepted` once the team agrees and implementation begins.
- Never delete an ADR. Supersede it: write a new ADR and set the old one's status to `Superseded by ADR-NNNN`.
- Spec documents link to ADRs; ADRs don't restate spec details.
- Small scope cuts and non-architectural decisions stay in the spec's "Non-goals" section.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-host-backend-on-fly-and-frontend-on-vercel.md) | Host backend on Fly.io, frontend on Vercel | Accepted |
| [0003](0003-scope-mvp-to-player-explorer.md) | Scope MVP to Player Explorer slice | Accepted |
| [0004](0004-simulation-engine-veterans-only-skew-normal.md) | Simulation: veterans-only, per-stat skew-normal | Accepted |
| [0005](0005-identity-resolution-tiers-1-and-3-only.md) | Identity resolution: Tiers 1 and 3 only | Accepted |
| [0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) | Storage: SQLite on Fly volume + nflreadpy filesystem cache | Accepted |
| [0007](0007-single-bearer-token-auth.md) | Auth: single bearer token, no user accounts | Accepted |
| [0008](0008-use-nflreadpy-not-nfl-data-py.md) | Use `nflreadpy`, not the deprecated `nfl_data_py` | Accepted |
| [0009](0009-canonical-stat-vocabulary-from-nflreadpy.md) | Canonical stat vocabulary = `nflreadpy` column names | Accepted |
| [0010](0010-mvp-supports-qb-rb-wr-te-only.md) | MVP supports QB/RB/WR/TE only (K/DEF deferred) | Accepted |
| [0011](0011-gate-implementation-on-pre-implementation-spikes.md) | Gate implementation on pre-implementation spikes | Accepted |

## Template

See [MADR 3.0](https://adr.github.io/madr/). Quick skeleton:

```markdown
# ADR-NNNN: <title>

- Status: Proposed | Accepted | Superseded by ADR-NNNN
- Date: YYYY-MM-DD
- Deciders: <names>

## Context and Problem Statement
<what situation forced a decision>

## Decision Drivers
- <constraint or goal>

## Considered Options
- Option 1
- Option 2

## Decision Outcome
Chosen: "Option X", because <one-line rationale>.

### Consequences
- Good: ...
- Bad: ...

## More Information
<links, related ADRs>
```

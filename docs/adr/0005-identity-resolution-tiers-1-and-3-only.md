# ADR-0005: Identity resolution — Tiers 1 and 3 only

- **Status:** Accepted; amended by [ADR-0013](0013-identity-resolution-team-abbreviation-normalization.md) (adds team-abbreviation normalization + canonical-refresh endpoint)
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

Requirements v1.2 §3.1.4 specifies a four-tier identity resolution pipeline: (1) direct ID match, (2) normalized name + team + jersey number, (3) normalized name + team, (4) fuzzy Levenshtein with disambiguation UI. Tiers 2 and 4 add UI and data complexity. We need to decide what ships in MVP.

## Decision Drivers

- Single user who controls CSV sources — we can curate inputs.
- `load_ff_playerids()` provides 12+ source IDs including `fantasypros_id`, `espn_id`, `yahoo_id`, `sleeper_id`, `cbs_id`, `pfr_id`, `fantasy_data_id`, `rotowire_id`, `nfl_id` — Tier 1 has broad coverage when source CSVs include any ID column.
- The source data's `merge_name` column is pre-normalized by the upstream project — we don't need to write our own normalizer.
- Jersey numbers are rarely published in projection CSVs; Tier 2 would often be unusable.
- A fuzzy-match disambiguation UI is real UI work the thin-MVP frontend doesn't want.

## Considered Options

1. **All four tiers** as specified.
2. **Tiers 1 + 3 with a manual-override endpoint** — direct ID if any *_id column present, otherwise `merge_name + team + position`. Ambiguous or missed rows land in `import_unresolved` and the user picks the correct player via `POST /api/imports/{id}/resolve`.
3. **Tier 3 only** — no ID matching at all.

## Decision Outcome

**Chosen: Option 2 (Tiers 1 + 3 with manual override).** `identity/resolver.resolve()` walks every known ID column first; falls back to `(merge_name, team, position)` lookup against the `player` table. Zero or multiple Tier-3 hits → row goes to `import_unresolved` for human resolution.

### Consequences

- **Good:** covers the common cases without building a disambiguation UI.
- **Good:** `merge_name` is pre-normalized at source; our code is just the same transform applied to incoming CSV rows (lowercase + strip punctuation). No dedicated `normalize.py` module.
- **Good:** FantasyPros exports don't include an ID column → Tier 3 carries the load for our primary source. Verified: `merge_name + team + position` is unique enough in practice.
- **Bad:** ambiguous name+team matches (e.g., "Josh Allen" QB vs. "Josh Allen" LB) require manual resolution. Surfaced clearly in the UI.
- **Bad:** if CSV sources change (e.g., a new provider without IDs), we may need Tier 2 or Tier 4 later. Adding them is additive to the resolver module.

## More Information

- Requirements v1.2, §3.1.4.
- Cross-reference data: [nflverse FF Player IDs dictionary](https://nflreadr.nflverse.com/articles/dictionary_ff_playerids.html).
- Related: [ADR-0008](0008-use-nflreadpy-not-nfl-data-py.md).

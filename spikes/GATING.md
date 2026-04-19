# Pre-Implementation Gating Review

**Date:** 2026-04-18
**Spec reference:** [`docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md`](../docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md) §9.4.
**Plan reference:** [`docs/superpowers/plans/2026-04-18-mc-ff-simulator-spikes.md`](../docs/superpowers/plans/2026-04-18-mc-ff-simulator-spikes.md).

## Per-spike verdicts

| Spike | Verdict | Headline finding | Gate unblocks |
|---|---|---|---|
| [A1 — skew-normal fits](a1-skew-normal-fits/report.md) | ✗ **FAIL (KILL)** | 44% acceptable. Skew-normal fits continuous yard stats cleanly; fails systematically for count-valued stats (TDs, INTs) — fitted density leaks below zero; Q-Q plots show staircase artifacts. | Blocks all app code. |
| [A2 — calibration](a2-calibration/) | ⏸ **DEFERRED** | Depends on A1's revised fitting approach. Will run after design revision. | Blocks `sim/`, `historical/` beyond stubs. |
| [B1 — ID resolution](b1-id-resolution/report.md) | ✗ **FAIL (KILL)** | 63% resolved vs 80% target. Root cause is mechanical: FantasyPros uses 2-letter team codes (TB, KC, SF, GB, NE, LV) while canonical uses 3-letter (TBB, KCC, SFO, GBP, NEP, LVR). A 9-entry normalization table alone raises hit rate to ~83%. The remaining failures are canonical-data staleness (2025 snapshot vs 2026 FP roster). | Blocks all app code. |
| [B2 — parser](b2-parser/report.md) | ✓ **PASS** | One parser + 14-entry section×code map handles all four positional MultiIndex shapes (QB, RB, WR, TE). Promotable directly to `api/app/import_pipeline/column_mapper.py`. | All app code. |
| [C1 — Fly deploy](c1-deploy/report.md) | ✓ **PASS** | Huge headroom. Peak RSS 135 MB vs 512 MB budget (74% free). Cold boot ~15 s vs 90 s budget. Projected cost ~$0.15/mo at idle (volume only); ≤$1.50/mo with occasional use. Well inside Fly's $5 free credit. | All app code. |
| [C2 — MC perf](c2-perf/report.md) | ✓ **PASS** | p50 179 ms, p95 311 ms on `--memory=512m --cpus=0.25` Docker (Fly shared-cpu-1x proxy). Both below Requirements v1.2 §7.3 targets. **Notable:** dropping from n=5000 to n=1000 barely moves p95 (311 ms vs 313 ms), confirming `skewnorm.fit` — not sampling — is the dominant cost. Cache fit params aggressively. | `sim/` final tuning. |

## Required design revisions

Two fails + one important C1 concern → three revisions before MVP implementation:

### Revision 1 — Mixed-family distributions (from A1 kill)

- **New ADR-0012** "Use mixed distribution families (skew-normal for continuous, negative-binomial for count)".
- **ADR-0004** status → "Superseded by ADR-0012" (preserve the record; the *veterans-only* + *historical fit* + *mean-shift* part of ADR-0004 still stands — only the family choice changes).
- **Spec §3 / §4 / §5** updates: the `player_distribution_params.params` JSON schema now stores `{family: "skewnorm" | "nbinom", ...}` per stat; `sim/fitting.py` picks family per stat from a small registry (yards/rec count stats → skew-normal; TDs / INTs / fumbles_lost → negative-binomial); scoring engine unaffected.
- **Re-run A2** after this change to verify calibration with the mixed-family approach.

### Revision 2 — Identity resolution hardening (from B1 kill)

- **Amend ADR-0005** with a "Normalization rules" section: the nine 2→3 letter team code mappings (`TB→TBB`, `KC→KCC`, `SF→SFO`, `GB→GBP`, `NO→NOS`, `NE→NEP`, `LV→LVR`, plus `JAX` already matches, and `LA`/`LAR` variants). Either canonicalize incoming CSV team codes to 3-letter, or canonicalize the canonical table to 2-letter at seed time — pick one direction in the revision.
- **Call out** that Tier 1 match is effectively dead for default FantasyPros exports (no ID column is published). Users can still hand-augment; docs should note this. The resolver code is not dead, just inactive for this source.
- **Stale canonical data** — the `db_season=2025` snapshot from `load_ff_playerids()` lags FantasyPros's current-season roster. Add a `POST /api/admin/refresh-players` endpoint, and document that users should refresh before draft prep. B1's 63% → ~83% with team normalization alone; reaching 95%+ requires either a fresher source or accepting per-import unresolved rows (already designed for via `import_unresolved` table).

### Revision 3 — nflreadpy cache semantics (from C1 concern)

- **Amend ADR-0006** to clarify: `NFLREADPY_CACHE_DIR` alone does NOT persist historical stats to disk — nflreadpy's filesystem cache behavior requires verification and possibly `NFLREADPY_CACHE_MODE=filesystem` (or equivalent) to actually write parquet files. Update the ADR with the correct env-var incantation once verified. If nflreadpy can't be made to persist, fall back to explicit `df.write_parquet(…)` in our `historical/fetch.py` wrapper — a ~5-line change contained to one module. Spec §3 already has the fallback path documented in Risk R1.

## Overall gate

- [x] **REVISE** — two FAILs require spec/ADR updates before implementation. Actions listed above. Not a STOP (architecture is sound; every failure is contained and has a clear fix).
- [ ] GO
- [ ] STOP

## Next steps (in order)

1. **Write design-revision ADRs and spec patches** (`ADR-0012` new, `ADR-0004`/`-0005`/`-0006` amended). Re-present to user for approval.
2. **Re-run Spike A2** (calibration backtest) with the mixed-family fitting code. Must pass (coverage 70–90%) before `sim/` is implemented.
3. **Run `superpowers:writing-plans`** to produce the MVP implementation plan, referencing spike artifacts (`tests/fixtures/fantasypros_*.html`, the `FP_SECTION_MAP` from B2, the `bench.py` timing targets from C2, the Fly template from C1, and the normalization rules from B1's revised resolver).
4. **Tear down the C1 Fly spike app** (`fly apps destroy ffsim-spike-c1`) once the revised deploy template lands — keep it running for now as a live reference.

## Spike artifact inventory (inputs for MVP)

- `tests/fixtures/fantasypros_{qb,rb,wr,te}.html` — real projection HTML for unit-test fixtures.
- `spikes/a1-skew-normal-fits/fit.py` + `plots/*.png` + `fit_results.csv` — evidence supporting the mixed-family decision.
- `spikes/b1-id-resolution/hit_rates.csv` — per-row resolution outcomes (ground truth for the normalization changes).
- `spikes/b2-parser/parse.py` — reusable column-mapping logic (promotable to `api/app/import_pipeline/column_mapper.py`).
- `spikes/c1-deploy/app/main.py` + `Dockerfile` + `fly.toml` — deploy template.
- `spikes/c2-perf/bench.py` + `bench_result.json` — perf baseline (re-run post-revision).

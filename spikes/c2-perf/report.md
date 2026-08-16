# Spike C2 Report — Monte Carlo Performance

**Date:** 2026-04-18
**Validates:** Requirements v1.2 §7.3 (<200 ms per player distribution).
**Kill criterion:** p95 >1 s at both n=5000 and n=1000.
**Success:** p50 <200 ms AND p95 <500 ms at n=5000.

## Measurements

Hardware: `--memory=512m --cpus=0.25` (≈ Fly shared-cpu-1x / 512MB).
Benchmark: 81 passers from top-100 passing-yards leaders (2023–2024 REG) × (fit + sample + percentile) on `passing_yards`. 19 of 100 skipped due to zero/near-zero passing yards (non-passers).

| n_samples | count | p50 (ms) | p95 (ms) | max (ms) |
|---|---|---|---|---|
| 5000 | 81 | 179.42 | 310.92 | 386.07 |
| 1000 | 81 | 113.87 | 312.51 | 387.36 |

## Verdict

Mark one with `[x]`:
- [x] **PASS** — p50 <200 ms AND p95 <500 ms at n=5000.
- [ ] **BORDERLINE** — meets threshold at n=1000 but not n=5000. Recommend default n=1000.
- [ ] **FAIL (KILL)** — p95 >1 s at both settings.

## Recommendation

"n=5000 is comfortably within budget. Ship with this default."

p50 at n=5000 is 179 ms (under the 200 ms target) and p95 is 311 ms (well under 500 ms). Even the maximum observed latency of 386 ms stays under 500 ms. The distribution endpoint can safely default to n=5000 on Fly shared-cpu-1x / 512MB instances. There is no need to lower the default to n=1000; the smaller sample count does not meaningfully reduce latency (p95 at n=1000 is 313 ms, essentially the same as n=5000), suggesting that `skewnorm.fit` dominates over sampling cost at this data size.

## Caveat

This benchmark uses `skewnorm` for `passing_yards` (a continuous stat). Spike A1 showed skew-normal fails for count stats; the MVP will use mixed distribution families. Perf should be similar for `scipy.stats.nbinom` (both are scipy RVS loops), but a follow-up bench after the design revision should confirm.

## Artifacts

- `bench_result.json` — raw timing output.

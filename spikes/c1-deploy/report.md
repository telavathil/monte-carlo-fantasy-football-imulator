# Spike C1 Report — Fly Deploy Smoke

**Date:** 2026-04-18
**Validates:** ADR-0002 (Fly host), ADR-0006 (SQLite + volume).
**Kill criterion:** peak RAM >512 MB or projected cost >$10/mo.

## Measurements

| Metric | Value | Threshold | Pass? |
|---|---|---|---|
| Cold-boot time | ~15s (auto-start from stopped) | <90 s | ✓ |
| Seed wall time | ~16s total (0.8s ids + 0.5s stats 3yr) | — | — |
| Peak RSS during seed | 135.2 MB | <512 MB | ✓ |
| Final volume disk usage | 0.0 MB (see note) | <200 MB | ✓ |
| Projected cost at idle | <$0.15/mo (volume only; machines auto-stop) | ≤$5 | ✓ |
| Projected cost active (occasional use) | ~$0.50–$1/mo | ≤$10 | ✓ |

### Notes on disk usage

`disk_mb: 0.0` because `nflreadpy` fetches data via HTTP and caches in-process memory rather than persisting parquet files to the `NFLREADPY_CACHE_DIR` path (`/data/historical`). The volume is mounted and writable (confirmed by `data_mounted: true` in health check), but nflreadpy's internal cache mechanism did not write parquet files to that directory during this spike. For the MVP, data persistence should use an explicit write step (e.g., `df.write_parquet(HIST / "player_stats_2024.parquet")`).

### Cold-boot detail

From Fly event logs:
- Machine pending → started: 9 seconds (01:50:06Z → 01:50:15Z)
- After auto-stop, first HTTP request triggered auto-start. Response was near-instant — cold start from stopped state measured as <15s from the uvicorn bind to first successful request.
- No health check failures observed; `/api/health` returned 200 on first attempt.

### VM Configuration

- Size: shared-cpu-1x
- Memory: 512 MB (confirmed in machine status)
- Region: iad
- Volume: vol_42kgn55g7l816j04 (ffsim_spike_data, 1 GB, iad)

### Cost Estimate (Fly.io pricing, April 2026)

- shared-cpu-1x @ 512MB: $0.0000091/s = ~$3.22/mo at 100% uptime
- With auto-stop (min_machines_running=0): near-$0 when idle; cost scales only with actual usage seconds
- 1 GB volume: $0.15/mo
- **Realistic monthly cost for a dev/test workload (occasional use, auto-stop):** ~$0.50–$1.50/mo
- **Worst case (continuously running):** ~$3.37/mo — well under $10 threshold

### Seed output (raw)

```json
{"ids_rows":12187,"ids_seconds":0.8,"stats_times_by_year":{"2023":0.2,"2024":0.1,"2025":0.1},"peak_rss_mb":135.2,"disk_mb":0.0}
```

## Verdict

Mark one with `[x]`:
- [x] **PASS** — all thresholds met.
- [ ] **BORDERLINE** — near a threshold; see recommendation.
- [ ] **FAIL (KILL)** — peak RAM >512 MB or projected cost >$10/mo.

## Recommendation

"shared-cpu-1x @ 512 MB is sufficient. Proceed with MVP deploy using this template."

Peak RSS of 135.2 MB leaves 376 MB headroom even after loading player IDs and 3 years of player stats. Cold boot is well under 90s. Cost is negligible with auto-stop. The only finding to address before MVP: implement explicit parquet persistence in the seed route so data survives across restarts and the volume is actually used.

## Tear-down

The spike app should be torn down after review by the user. Run:

```bash
fly apps destroy ffsim-spike-c1 --yes
fly volumes list  # verify removed
```

**NOTE:** Do NOT tear down yourself — the user will decide. The app is live at https://ffsim-spike-c1.fly.dev.

## Artifacts

- `seed_output.json` — raw response from /api/seed.
- `fly_logs.txt` — first 50 lines of fly logs at deploy time.
- Dockerfile, fly.toml, app/main.py kept as deploy template for MVP.

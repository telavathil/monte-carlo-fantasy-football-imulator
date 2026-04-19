"""Minimal FastAPI app for Fly smoke test."""
from __future__ import annotations
import os
import pathlib
import time
import resource
from fastapi import FastAPI

app = FastAPI()
DATA = pathlib.Path("/data")
HIST = DATA / "historical"
os.environ.setdefault("NFLREADPY_CACHE_DIR", str(HIST))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_mounted": DATA.is_dir(),
        "historical_seasons": [p.stem for p in HIST.glob("*.parquet")]
                              if HIST.is_dir() else [],
    }


@app.post("/api/seed")
def seed():
    import nflreadpy as nfl
    HIST.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ids = nfl.load_ff_playerids()
    t_ids = time.time() - t0

    stats_times = {}
    for y in [2023, 2024, 2025]:
        t = time.time()
        nfl.load_player_stats(seasons=[y])
        stats_times[y] = round(time.time() - t, 1)

    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS returns bytes, Linux returns KB. Assume Linux on Fly.
    peak_mb = round(peak_kb / 1024, 1)

    return {
        "ids_rows": ids.height,
        "ids_seconds": round(t_ids, 1),
        "stats_times_by_year": stats_times,
        "peak_rss_mb": peak_mb,
        "disk_mb": round(sum(p.stat().st_size for p in HIST.rglob("*"))
                          / 1024 / 1024, 1),
    }

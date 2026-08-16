"""Regenerate nflreadpy test cassettes. Run manually when nflreadpy schema changes.

Usage:
    cd api && .venv/bin/python tests/fixtures/generate_cassettes.py
"""
from __future__ import annotations
import pathlib
import nflreadpy as nfl

HERE = pathlib.Path(__file__).parent / "nflreadpy"
HERE.mkdir(parents=True, exist_ok=True)

print("Downloading load_ff_playerids ...")
ids = nfl.load_ff_playerids()
ids.write_parquet(HERE / "ff_playerids.parquet")

for year in [2023, 2024, 2025]:
    print(f"Downloading load_player_stats({year}) ...")
    df = nfl.load_player_stats(seasons=[year])
    df.write_parquet(HERE / f"player_stats_{year}.parquet")

print("Done.")

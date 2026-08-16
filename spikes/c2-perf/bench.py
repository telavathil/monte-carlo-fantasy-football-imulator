"""
Spike C2: Monte Carlo performance on Fly-sized compute.
100 players × n=5000; measure p50 and p95 of simulate_player.
Kill criterion: p95 >1s at n=5000 AND p95 >1s at n=1000.
"""
from __future__ import annotations
import json
import pathlib
import time
import numpy as np
import nflreadpy as nfl
from scipy import stats

N_PLAYERS = 100
N_SAMPLES = 5000
SEED = 1337


def fit_player(train_vals: np.ndarray, target_mean: float):
    alpha, loc, scale = stats.skewnorm.fit(train_vals)
    delta = alpha / np.sqrt(1 + alpha ** 2)
    cur_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    return (alpha, loc + (target_mean - cur_mean), scale)


def simulate(params, n: int, rng) -> dict:
    samples = stats.skewnorm.rvs(*params, size=n, random_state=rng)
    samples = np.clip(samples, 0, None)
    return {
        "p10": float(np.percentile(samples, 10)),
        "p50": float(np.percentile(samples, 50)),
        "p90": float(np.percentile(samples, 90)),
    }


def main() -> int:
    print("Loading historical data …")
    df = nfl.load_player_stats(seasons=[2023, 2024]).to_pandas()
    df = df[df["season_type"] == "REG"]

    stat = "passing_yards"  # pick one per-player for benchmarking

    # Pick top N_PLAYERS by total passing yards (ensures passers only)
    top = (df.groupby("player_id")[stat]
             .sum()
             .sort_values(ascending=False)
             .head(N_PLAYERS).index)
    rng = np.random.default_rng(SEED)

    latencies_5k: list[float] = []
    latencies_1k: list[float] = []
    for pid in top:
        vals = df[df["player_id"] == pid][stat].dropna().to_numpy()
        if len(vals) < 4:
            continue
        # Skip degenerate cases: no variance or all zeros (non-passers)
        if vals.std() < 1e-6 or vals.mean() < 1.0:
            continue
        target = vals.mean()

        try:
            # n=5000
            t0 = time.perf_counter()
            p = fit_player(vals, target)
            simulate(p, 5000, rng)
            latencies_5k.append((time.perf_counter() - t0) * 1000)

            # n=1000
            t0 = time.perf_counter()
            p = fit_player(vals, target)
            simulate(p, 1000, rng)
            latencies_1k.append((time.perf_counter() - t0) * 1000)
        except Exception as exc:
            print(f"Skipping player {pid}: {exc}")
            continue

    def summarize(xs):
        return {
            "count": len(xs),
            "p50_ms": round(float(np.percentile(xs, 50)), 2),
            "p95_ms": round(float(np.percentile(xs, 95)), 2),
            "max_ms": round(max(xs), 2),
        }

    result = {
        "n_samples_5000": summarize(latencies_5k),
        "n_samples_1000": summarize(latencies_1k),
    }
    print(json.dumps(result, indent=2))

    pathlib.Path(__file__).parent.joinpath("bench_result.json").write_text(
        json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

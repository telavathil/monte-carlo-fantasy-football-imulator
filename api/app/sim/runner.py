"""Simulation orchestrator: sample -> score -> summarize."""
from __future__ import annotations
import numpy as np
from scipy import stats as _stats
from app.scoring.engine import score
from app.scoring.presets import ScoringPreset
from app.sim.sampler import sample


def simulate_from_params(params: dict[str, tuple], preset: ScoringPreset,
                         n: int = 5000, seed: int | None = None,
                         n_bins: int = 30) -> dict:
    """Sample per stat, score each simulation, return distribution summary."""
    samples_by_stat = sample(params, n=n, seed=seed)
    points = np.zeros(n, dtype=float)
    for i in range(n):
        line = {stat: arr[i] for stat, arr in samples_by_stat.items()}
        points[i] = score(line, preset)
    p10, p25, p50, p75, p90 = np.percentile(points, [10, 25, 50, 75, 90])
    counts, edges = np.histogram(points, bins=n_bins)
    return {
        "n_samples": n,
        "floor_p10": float(p10),
        "p25": float(p25),
        "median_p50": float(p50),
        "p75": float(p75),
        "ceiling_p90": float(p90),
        "mean": float(points.mean()),
        "std": float(points.std()),
        "skewness": float(_stats.skew(points)),
        "histogram": {
            "bin_edges": edges.tolist(),
            "counts": counts.tolist(),
        },
    }

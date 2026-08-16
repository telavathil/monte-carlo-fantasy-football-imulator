import numpy as np
from app.sim.runner import simulate_from_params
from app.scoring.presets import FULL_PPR


def test_simulate_basic_shape_and_ordering():
    params = {
        "passing_yards": ("skewnorm", 0.0, 250.0, 40.0),
        "passing_tds": ("nbinom", 3.0, 0.3),
    }
    result = simulate_from_params(params, preset=FULL_PPR, n=2000, seed=42)
    assert result["n_samples"] == 2000
    assert result["floor_p10"] <= result["median_p50"] <= result["ceiling_p90"]
    assert result["histogram"]["counts"].sum() == 2000 if hasattr(
        result["histogram"]["counts"], "sum"
    ) else sum(result["histogram"]["counts"]) == 2000


def test_simulate_histogram_bin_count():
    params = {"passing_yards": ("skewnorm", 0.0, 250.0, 40.0)}
    result = simulate_from_params(params, preset=FULL_PPR, n=1000, seed=1)
    # bin_edges length = counts length + 1
    assert len(result["histogram"]["bin_edges"]) == len(result["histogram"]["counts"]) + 1


def test_simulate_deterministic_with_seed():
    params = {"passing_yards": ("skewnorm", 0.2, 200.0, 40.0)}
    a = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    b = simulate_from_params(params, preset=FULL_PPR, n=500, seed=99)
    assert a["mean"] == b["mean"]
    assert a["std"] == b["std"]

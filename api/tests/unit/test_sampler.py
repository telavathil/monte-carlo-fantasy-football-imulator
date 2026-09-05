import numpy as np
import pytest
from app.sim.sampler import sample


def test_skewnorm_samples_clamped_nonneg():
    params = {"passing_yards": ("skewnorm", 0.0, 100.0, 50.0)}
    out = sample(params, n=1000, seed=42)
    assert out["passing_yards"].shape == (1000,)
    assert (out["passing_yards"] >= 0).all()


def test_nbinom_samples_nonneg_integers():
    params = {"passing_tds": ("nbinom", 5.0, 0.3)}
    out = sample(params, n=1000, seed=42)
    arr = out["passing_tds"]
    assert arr.shape == (1000,)
    assert (arr >= 0).all()
    assert np.array_equal(arr, arr.astype(int))


def test_poisson_samples_nonneg_integers():
    params = {"rushing_tds": ("poisson", 1.5)}
    out = sample(params, n=1000, seed=42)
    arr = out["rushing_tds"]
    assert (arr >= 0).all()


def test_seed_determinism():
    params = {"passing_yards": ("skewnorm", 0.5, 200.0, 40.0)}
    out_a = sample(params, n=100, seed=7)
    out_b = sample(params, n=100, seed=7)
    np.testing.assert_array_equal(out_a["passing_yards"], out_b["passing_yards"])


def test_mixed_family_samples():
    params = {
        "passing_yards": ("skewnorm", 0.0, 250.0, 40.0),
        "passing_tds": ("nbinom", 3.0, 0.3),
        "rushing_tds": ("poisson", 0.5),
    }
    out = sample(params, n=500, seed=42)
    assert set(out.keys()) == {"passing_yards", "passing_tds", "rushing_tds"}
    for arr in out.values():
        assert arr.shape == (500,)

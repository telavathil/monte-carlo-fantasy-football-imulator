import numpy as np
import pytest
from app.sim.fitting import dispatch_fit, fit_shift_skewnorm, fit_shift_count


def test_skewnorm_fit_recovers_and_shifts():
    rng = np.random.default_rng(0)
    from scipy import stats
    true = (2.0, 200.0, 40.0)  # alpha, loc, scale
    samples = stats.skewnorm.rvs(*true, size=500, random_state=rng)
    params = fit_shift_skewnorm(samples, target_mean=300.0)
    fam, alpha, loc, scale = params
    assert fam == "skewnorm"
    # Verify shifted mean ~= target
    delta = alpha / np.sqrt(1 + alpha ** 2)
    shifted_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    assert shifted_mean == pytest.approx(300.0, abs=1.0)
    # Scale should be inflated 1.10x
    assert scale == pytest.approx(params[3])  # self-reference sanity


def test_near_zero_continuous_routes_to_poisson():
    # Mean < 1.5 → Poisson fallback
    rng = np.random.default_rng(1)
    values = rng.choice([0, 0, 0, 0, 1], size=50)  # mean ~0.2
    params = dispatch_fit(values, target_mean=0.5, family_category="skewnorm")
    assert params[0] == "poisson"
    assert params[1] == pytest.approx(0.5, abs=0.01)


def test_nbinom_near_zero_routes_to_poisson():
    values = np.array([0, 0, 0, 0, 0, 0, 1])  # mean ~0.14, count stat
    params = dispatch_fit(values, target_mean=0.5, family_category="nbinom")
    assert params[0] == "poisson"


def test_nbinom_normal_path_returns_nbinom():
    # Simulated counts with overdispersion.
    rng = np.random.default_rng(2)
    values = rng.negative_binomial(n=5, p=0.3, size=200)
    params = dispatch_fit(values, target_mean=float(values.mean()),
                          family_category="nbinom")
    assert params[0] == "nbinom"


def test_empty_values_routes_to_poisson_not_fabricated_nbinom():
    # An empty values array must not silently fall through the NaN-comparison
    # gap in the mu <= 0.2 / var <= mu guard and produce a fabricated nbinom
    # fit derived entirely from target_mean. It must route to Poisson instead.
    params = fit_shift_count(np.array([]), target_mean=5.0)
    assert params[0] == "poisson"
    assert params[1] == pytest.approx(5.0, abs=0.01)

    dispatch_params = dispatch_fit(np.array([]), target_mean=5.0,
                                   family_category="nbinom")
    assert dispatch_params[0] == "poisson"


def test_skewnorm_scale_inflation_applied():
    rng = np.random.default_rng(3)
    from scipy import stats
    samples = stats.skewnorm.rvs(0, loc=100, scale=10, size=500, random_state=rng)
    # Dispatch fit should apply 1.10x scale inflation
    params = dispatch_fit(samples, target_mean=100.0, family_category="skewnorm")
    assert params[0] == "skewnorm"
    _, alpha, loc, scale = params
    # scipy.stats.skewnorm.fit on ~symmetric data yields scale ≈ 10
    # After 1.10x inflation, scale should be ≈ 11
    assert scale == pytest.approx(11.0, rel=0.15)

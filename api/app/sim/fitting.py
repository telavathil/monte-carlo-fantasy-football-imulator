"""Distribution fitting per ADR-0012 + ADR-0015."""
from __future__ import annotations
import math
import numpy as np
from scipy import stats


SKEWNORM_NEAR_ZERO_THRESHOLD = 1.5  # mean < this for continuous → Poisson
SKEWNORM_SCALE_INFLATION = 1.10     # widen intervals ~10%


SkewnormParams = tuple[str, float, float, float]  # ("skewnorm", alpha, loc, scale)
NbinomParams = tuple[str, float, float]           # ("nbinom", n, p)
PoissonParams = tuple[str, float]                  # ("poisson", lam)
FitParams = SkewnormParams | NbinomParams | PoissonParams


def fit_shift_skewnorm(values: np.ndarray, target_mean: float) -> SkewnormParams:
    alpha, loc, scale = stats.skewnorm.fit(values)
    scale = float(scale) * SKEWNORM_SCALE_INFLATION
    delta = alpha / math.sqrt(1 + alpha ** 2)
    current_mean = loc + scale * delta * math.sqrt(2 / math.pi)
    return ("skewnorm", float(alpha), float(loc + (target_mean - current_mean)), scale)


def fit_shift_poisson(target_mean: float) -> PoissonParams:
    return ("poisson", max(float(target_mean), 0.1))


def fit_shift_count(values: np.ndarray, target_mean: float) -> NbinomParams | PoissonParams:
    """nbinom method-of-moments with Poisson fallback."""
    if len(values) == 0:
        return fit_shift_poisson(target_mean)
    mu = float(values.mean())
    if not math.isfinite(mu):
        return fit_shift_poisson(target_mean)
    var = float(values.var(ddof=1)) if len(values) > 1 else max(mu, 1e-6)
    if mu <= 0.2 or var <= mu:
        return fit_shift_poisson(target_mean)
    new_mu = max(float(target_mean), 1e-6)
    new_var = new_mu * (var / mu) if mu > 0 else new_mu * 1.01
    if new_var <= new_mu:
        new_var = new_mu * 1.01 + 1e-6
    n = new_mu ** 2 / (new_var - new_mu)
    p = new_mu / new_var
    if not (math.isfinite(n) and math.isfinite(p)) or n <= 0 or not (0 < p <= 1):
        return fit_shift_poisson(target_mean)
    return ("nbinom", float(n), float(p))


def dispatch_fit(values: np.ndarray, target_mean: float,
                 family_category: str) -> FitParams:
    """Top-level dispatcher applying ADR-0015 near-zero routing."""
    if family_category == "skewnorm":
        if float(values.mean()) < SKEWNORM_NEAR_ZERO_THRESHOLD:
            return fit_shift_poisson(target_mean)
        return fit_shift_skewnorm(values, target_mean)
    return fit_shift_count(values, target_mean)

"""Per-family sampling dispatch."""
from __future__ import annotations
import numpy as np
from scipy import stats


def sample(params: dict[str, tuple], n: int = 5000,
           seed: int | None = None) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    out: dict[str, np.ndarray] = {}
    for stat, p in params.items():
        fam = p[0]
        if fam == "skewnorm":
            _, alpha, loc, scale = p
            arr = stats.skewnorm.rvs(alpha, loc=loc, scale=scale,
                                     size=n, random_state=rng)
            arr = np.clip(arr, 0, None)
        elif fam == "nbinom":
            _, nn, pp = p
            arr = stats.nbinom.rvs(nn, pp, size=n, random_state=rng)
        elif fam == "poisson":
            _, lam = p
            arr = stats.poisson.rvs(lam, size=n, random_state=rng)
        else:
            raise ValueError(f"unknown family {fam}")
        out[stat] = arr
    return out

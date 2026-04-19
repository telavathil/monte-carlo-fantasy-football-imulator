"""
Spike A2 (post-revision): Mean-shift calibration backtest, mixed families per ADR-0012.

Method: hold out 2024; fit on 2021–2023 regular-season weekly data
(recency [0.5, 0.3, 0.2]); mean-shift to 2024 projection proxy
(weighted prior-year per-game avg × 2024 games); sample 5000 season
totals; check actual 2024 season total ∈ p10–p90 interval.

Family dispatch:
  skewnorm path (continuous): mean-shift loc by (target − current).
  nbinom path (counts):       MoM fit, shift by scaling n to hit target mean
                              while preserving dispersion (σ²/μ).

Kill criterion: coverage <60% or >95% across player-stat pairs.
"""
from __future__ import annotations
import csv
import pathlib
import numpy as np
import nflreadpy as nfl
from scipy import stats

N_SAMPLES = 5000
SEED = 42

PLAYERS = {
    "QB": ["patrick mahomes", "jalen hurts", "lamar jackson"],
    "RB": ["christian mccaffrey", "derrick henry"],
    "WR": ["tyreek hill", "justin jefferson", "ceedee lamb"],
    "TE": ["travis kelce", "sam laporta"],
}

STATS_BY_POS = {
    "QB": ["passing_yards", "passing_tds", "passing_interceptions",
           "rushing_yards", "rushing_tds"],
    "RB": ["rushing_yards", "rushing_tds", "receptions",
           "receiving_yards", "receiving_tds"],
    "WR": ["receptions", "receiving_yards", "receiving_tds",
           "rushing_yards"],
    "TE": ["receptions", "receiving_yards", "receiving_tds"],
}

# Per ADR-0012
STAT_FAMILY = {
    "passing_yards": "skewnorm",
    "rushing_yards": "skewnorm",
    "receiving_yards": "skewnorm",
    "receptions": "skewnorm",
    "completions": "skewnorm",
    "attempts": "skewnorm",
    "carries": "skewnorm",
    "targets": "skewnorm",
    "passing_tds": "nbinom",
    "passing_interceptions": "nbinom",
    "rushing_tds": "nbinom",
    "receiving_tds": "nbinom",
    "rushing_fumbles_lost": "nbinom",
}

WEIGHTS = {2023: 0.50, 2022: 0.30, 2021: 0.20}


# --- Fitting + shifting ---

def fit_shift_skewnorm(values: np.ndarray, target_mean: float):
    """Fit skew-normal, shift loc so mean == target."""
    alpha, loc, scale = stats.skewnorm.fit(values)
    delta = alpha / np.sqrt(1 + alpha ** 2)
    current_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    return ("skewnorm", alpha, loc + (target_mean - current_mean), scale)


def fit_shift_nbinom(values: np.ndarray, target_mean: float):
    """Method-of-moments nbinom fit; shift by scaling n, preserving dispersion σ²/μ."""
    mu = float(values.mean())
    var = float(values.var(ddof=1)) if len(values) > 1 else max(mu, 1e-6)
    if var <= mu:
        # Under-dispersed (or all zeros): fall back to tiny nbinom ≈ Poisson
        var = mu * 1.01 + 1e-6
    # Historical params
    n0 = mu ** 2 / (var - mu)
    p0 = mu / var
    # Preserve dispersion: new_var = target_mean * (var / mu)
    new_mu = max(target_mean, 1e-6)
    new_var = new_mu * (var / mu) if mu > 0 else new_mu * 1.01
    if new_var <= new_mu:
        new_var = new_mu * 1.01 + 1e-6
    n = new_mu ** 2 / (new_var - new_mu)
    p = new_mu / new_var
    return ("nbinom", n, p)


def sample_season(params_tuple, n_games: int, rng) -> np.ndarray:
    fam = params_tuple[0]
    if fam == "skewnorm":
        _, alpha, loc, scale = params_tuple
        samples = stats.skewnorm.rvs(alpha, loc=loc, scale=scale,
                                     size=(N_SAMPLES, n_games),
                                     random_state=rng)
        samples = np.clip(samples, 0, None)
    elif fam == "nbinom":
        _, n, p = params_tuple
        samples = stats.nbinom.rvs(n, p, size=(N_SAMPLES, n_games),
                                   random_state=rng)
    else:
        raise ValueError(f"unknown family {fam}")
    return samples.sum(axis=1)


# --- Main ---

def main() -> int:
    print("Loading historical 2021–2024 …")
    hist = nfl.load_player_stats(seasons=[2021, 2022, 2023, 2024]).to_pandas()
    hist = hist[hist["season_type"] == "REG"]

    records = []
    rng = np.random.default_rng(SEED)

    for pos, names in PLAYERS.items():
        for merge in names:
            pr = hist[hist["player_display_name"].str.lower() == merge]
            if pr.empty:
                pr = hist[hist["player_name"].str.lower().str.contains(
                    merge.split()[-1], na=False)]

            train = pr[pr["season"].isin([2021, 2022, 2023])]
            test  = pr[pr["season"] == 2024]
            test_games = len(test)
            if test_games < 4 or len(train) < 4:
                print(f"  {pos} {merge}: insufficient data, skipping")
                continue

            for stat in STATS_BY_POS[pos]:
                train_vals = train[stat].to_numpy()
                train_vals = train_vals[~np.isnan(train_vals)]
                if len(train_vals) < 4:
                    continue

                per_season = {
                    y: train[train["season"] == y][stat].mean()
                    for y in [2021, 2022, 2023]
                }
                valid = {y: v for y, v in per_season.items() if not np.isnan(v)}
                if not valid:
                    continue
                w_sum = sum(WEIGHTS[y] for y in valid)
                weighted_avg = sum(WEIGHTS[y] * v for y, v in valid.items()) / w_sum
                projection_total = weighted_avg * test_games

                fam = STAT_FAMILY.get(stat, "skewnorm")
                try:
                    if fam == "skewnorm":
                        shifted = fit_shift_skewnorm(train_vals, weighted_avg)
                    else:
                        shifted = fit_shift_nbinom(train_vals, weighted_avg)
                except Exception as e:
                    print(f"    fit error {pos} {merge} {stat}: {e}")
                    continue

                sim_totals = sample_season(shifted, test_games, rng)
                p10, p50, p90 = np.percentile(sim_totals, [10, 50, 90])
                actual = test[stat].sum()
                inside = float(p10) <= float(actual) <= float(p90)

                records.append({
                    "pos": pos, "player": merge, "stat": stat, "family": fam,
                    "games_train": len(train_vals),
                    "games_test": test_games,
                    "projection_total": round(projection_total, 2),
                    "p10": round(float(p10), 2),
                    "p50": round(float(p50), 2),
                    "p90": round(float(p90), 2),
                    "actual": round(float(actual), 2),
                    "inside_p10_p90": inside,
                })

    csv_path = pathlib.Path(__file__).parent / "coverage.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    n = len(records)
    hits = sum(1 for r in records if r["inside_p10_p90"])
    print(f"\nOVERALL coverage: {hits}/{n} = {100*hits/n:.0f}% (target 80%)")

    by_fam = {}
    for r in records:
        by_fam.setdefault(r["family"], {"hit": 0, "total": 0})
        by_fam[r["family"]]["total"] += 1
        if r["inside_p10_p90"]:
            by_fam[r["family"]]["hit"] += 1
    print("By family:")
    for fam, c in by_fam.items():
        print(f"  {fam}: {c['hit']}/{c['total']} ({100*c['hit']/c['total']:.0f}%)")

    by_pos = {}
    for r in records:
        by_pos.setdefault(r["pos"], {"hit": 0, "total": 0})
        by_pos[r["pos"]]["total"] += 1
        if r["inside_p10_p90"]:
            by_pos[r["pos"]]["hit"] += 1
    print("By position:")
    for p, c in by_pos.items():
        print(f"  {p}: {c['hit']}/{c['total']} ({100*c['hit']/c['total']:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

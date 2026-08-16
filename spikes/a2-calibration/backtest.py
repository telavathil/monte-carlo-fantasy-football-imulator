"""
Spike A2 (re-run v3): v2 + two skewnorm fixes.

v3 adds:
- Near-zero continuous routing: if historical mean(values) < 1.5 for a
  skewnorm-categorized stat, use Poisson fallback instead. Catches sparse
  continuous stats (e.g. WR rushing yards) where clipped skewnorm produces
  a positive p10 that actual-zero misses.
- Scale inflation: skewnorm.scale *= 1.10 after fit, before mean-shift.
  Widens intervals by ~10% to account for cross-game correlation we don't
  model (weekly IID samples understate season-total variance).

Kill criterion: coverage <60% or >95%. Target pass: 70-90%.
"""
from __future__ import annotations
import csv
import math
import pathlib
import numpy as np
import nflreadpy as nfl
from scipy import stats

N_SAMPLES = 5000
SEED = 42
POOL_SIZE_PER_POSITION = 10

SKEWNORM_SCALE_INFLATION = 1.10
SKEWNORM_NEAR_ZERO_THRESHOLD = 1.5  # mean < this → Poisson

STATS_BY_POS = {
    "QB": ["passing_yards", "passing_tds", "passing_interceptions",
           "rushing_yards", "rushing_tds"],
    "RB": ["rushing_yards", "rushing_tds", "receptions",
           "receiving_yards", "receiving_tds"],
    "WR": ["receptions", "receiving_yards", "receiving_tds",
           "rushing_yards"],
    "TE": ["receptions", "receiving_yards", "receiving_tds"],
}

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

RANK_STAT = {"QB": "passing_yards", "RB": "rushing_yards",
             "WR": "receiving_yards", "TE": "receiving_yards"}


def select_pool(hist) -> dict:
    pool = {}
    train = hist[hist["season"].isin([2021, 2022, 2023])]
    for pos, rank_stat in RANK_STAT.items():
        totals = (train[train["position"] == pos]
                  .groupby(["player_id", "player_display_name"])[rank_stat]
                  .sum()
                  .sort_values(ascending=False))
        top = totals.head(POOL_SIZE_PER_POSITION)
        pool[pos] = [(pid, name) for (pid, name) in top.index.tolist()]
        print(f"  {pos}: {len(pool[pos])} players selected")
    return pool


def fit_shift_skewnorm(values: np.ndarray, target_mean: float):
    """Skew-normal fit with scale inflation + mean-shift."""
    alpha, loc, scale = stats.skewnorm.fit(values)
    scale = scale * SKEWNORM_SCALE_INFLATION   # v3: inflate
    delta = alpha / np.sqrt(1 + alpha ** 2)
    current_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    return ("skewnorm", alpha, loc + (target_mean - current_mean), scale)


def fit_shift_poisson(target_mean: float):
    return ("poisson", max(target_mean, 0.1))


def fit_shift_count(values: np.ndarray, target_mean: float):
    """nbinom MoM with Poisson fallback (v2 logic retained)."""
    mu = float(values.mean())
    var = float(values.var(ddof=1)) if len(values) > 1 else max(mu, 1e-6)
    if mu <= 0.2 or var <= mu:
        return fit_shift_poisson(target_mean)
    new_mu = max(target_mean, 1e-6)
    new_var = new_mu * (var / mu) if mu > 0 else new_mu * 1.01
    if new_var <= new_mu:
        new_var = new_mu * 1.01 + 1e-6
    n = new_mu ** 2 / (new_var - new_mu)
    p = new_mu / new_var
    if not (math.isfinite(n) and math.isfinite(p)) or n <= 0 or not (0 < p <= 1):
        return fit_shift_poisson(target_mean)
    return ("nbinom", n, p)


def dispatch_fit(values: np.ndarray, target_mean: float, family_cat: str):
    """Top-level dispatcher with v3 near-zero routing for continuous stats."""
    if family_cat == "skewnorm":
        if float(values.mean()) < SKEWNORM_NEAR_ZERO_THRESHOLD:
            # v3: sparse continuous stat → Poisson models this better
            return fit_shift_poisson(target_mean)
        return fit_shift_skewnorm(values, target_mean)
    else:  # "nbinom"
        return fit_shift_count(values, target_mean)


def sample_season(params_tuple, n_games: int, rng) -> np.ndarray:
    fam = params_tuple[0]
    if fam == "skewnorm":
        _, alpha, loc, scale = params_tuple
        s = stats.skewnorm.rvs(alpha, loc=loc, scale=scale,
                               size=(N_SAMPLES, n_games),
                               random_state=rng)
        s = np.clip(s, 0, None)
    elif fam == "nbinom":
        _, n, p = params_tuple
        s = stats.nbinom.rvs(n, p, size=(N_SAMPLES, n_games),
                             random_state=rng)
    elif fam == "poisson":
        _, lam = params_tuple
        s = stats.poisson.rvs(lam, size=(N_SAMPLES, n_games),
                              random_state=rng)
    else:
        raise ValueError(f"unknown family {fam}")
    return s.sum(axis=1)


def main() -> int:
    print("Loading historical 2021\u20132024 \u2026")
    hist = nfl.load_player_stats(seasons=[2021, 2022, 2023, 2024]).to_pandas()
    hist = hist[hist["season_type"] == "REG"]

    print("\nSelecting player pool:")
    pool = select_pool(hist)

    records = []
    rng = np.random.default_rng(SEED)

    for pos, players in pool.items():
        for pid, name in players:
            pr = hist[hist["player_id"] == pid]
            train = pr[pr["season"].isin([2021, 2022, 2023])]
            test  = pr[pr["season"] == 2024]
            test_games = len(test)
            if test_games < 4 or len(train) < 4:
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

                fam_cat = STAT_FAMILY.get(stat, "skewnorm")
                try:
                    shifted = dispatch_fit(train_vals, weighted_avg, fam_cat)
                except Exception as e:
                    print(f"    fit error {pos} {name} {stat}: {e}")
                    continue

                sim_totals = sample_season(shifted, test_games, rng)
                p10, p50, p90 = np.percentile(sim_totals, [10, 50, 90])
                actual = test[stat].sum()
                inside = float(p10) <= float(actual) <= float(p90)

                records.append({
                    "pos": pos, "player": name, "stat": stat,
                    "family_category": fam_cat,
                    "family_used": shifted[0],
                    "train_mean": round(float(train_vals.mean()), 3),
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
    print(f"\nOVERALL coverage: {hits}/{n} = {100*hits/n:.1f}% (target 80%)")

    by_used = {}
    for r in records:
        by_used.setdefault(r["family_used"], {"hit": 0, "total": 0})
        by_used[r["family_used"]]["total"] += 1
        if r["inside_p10_p90"]:
            by_used[r["family_used"]]["hit"] += 1
    print("By family USED:")
    for fam, c in by_used.items():
        print(f"  {fam}: {c['hit']}/{c['total']} ({100*c['hit']/c['total']:.1f}%)")

    # Breakdown by category (shows which continuous stats re-routed to poisson)
    by_cat = {}
    for r in records:
        key = f"{r['family_category']}\u2192{r['family_used']}"
        by_cat.setdefault(key, {"hit": 0, "total": 0})
        by_cat[key]["total"] += 1
        if r["inside_p10_p90"]:
            by_cat[key]["hit"] += 1
    print("By category \u2192 family USED:")
    for key, c in by_cat.items():
        print(f"  {key}: {c['hit']}/{c['total']} ({100*c['hit']/c['total']:.1f}%)")

    by_pos = {}
    for r in records:
        by_pos.setdefault(r["pos"], {"hit": 0, "total": 0})
        by_pos[r["pos"]]["total"] += 1
        if r["inside_p10_p90"]:
            by_pos[r["pos"]]["hit"] += 1
    print("By position:")
    for p, c in by_pos.items():
        print(f"  {p}: {c['hit']}/{c['total']} ({100*c['hit']/c['total']:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

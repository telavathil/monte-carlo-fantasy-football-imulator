"""
Spike A1: Skew-normal distribution fit sanity check.
Kill criterion: <50% of (player, stat) pairs show acceptable fit.
"""
from __future__ import annotations
import pathlib
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import nflreadpy as nfl
from scipy import stats

PLAYERS = {
    "QB": [("Patrick Mahomes", "patrick mahomes"),
           ("Jalen Hurts", "jalen hurts"),
           ("Lamar Jackson", "lamar jackson")],
    "RB": [("Christian McCaffrey", "christian mccaffrey"),
           ("Derrick Henry", "derrick henry")],
    "WR": [("Tyreek Hill", "tyreek hill"),
           ("Justin Jefferson", "justin jefferson"),
           ("CeeDee Lamb", "ceedee lamb")],
    "TE": [("Travis Kelce", "travis kelce"),
           ("Sam LaPorta", "sam laporta")],
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

PLOTS = pathlib.Path(__file__).parent / "plots"
PLOTS.mkdir(exist_ok=True)


def fit_and_plot(player_name: str, merge_name: str, pos: str, games_df) -> list[dict]:
    """Fit skew-normal per stat; return one record per (player, stat)."""
    records = []
    stats_list = STATS_BY_POS[pos]
    fig, axes = plt.subplots(2, len(stats_list), figsize=(4 * len(stats_list), 7))
    if len(stats_list) == 1:
        axes = axes.reshape(2, 1)

    for col, stat in enumerate(stats_list):
        values = games_df[stat].to_numpy()
        values = values[~np.isnan(values)]
        if len(values) < 4:
            records.append({"player": player_name, "pos": pos, "stat": stat,
                            "games": len(values), "verdict": "insufficient"})
            continue
        try:
            params = stats.skewnorm.fit(values)
        except Exception as e:
            records.append({"player": player_name, "pos": pos, "stat": stat,
                            "games": len(values), "verdict": f"fit_error: {e}"})
            continue

        # Histogram + fitted density overlay (top row)
        ax = axes[0, col]
        ax.hist(values, bins=min(15, len(values)), density=True, alpha=0.5)
        x = np.linspace(max(0, values.min() - 5), values.max() + 5, 200)
        ax.plot(x, stats.skewnorm.pdf(x, *params), "r-", lw=2)
        ax.set_title(f"{stat}\nn={len(values)}")

        # Q-Q plot (bottom row)
        ax2 = axes[1, col]
        stats.probplot(values, dist=stats.skewnorm, sparams=params, plot=ax2)
        ax2.set_title("Q-Q")
        ax2.get_lines()[1].set_color("r")

        # Verdict: Q-Q residuals. Compute R² of theoretical vs observed.
        (osm, osr), (slope, intercept, r) = stats.probplot(
            values, dist=stats.skewnorm, sparams=params)
        r2 = r ** 2
        verdict = "acceptable" if r2 >= 0.95 else "poor"
        records.append({
            "player": player_name, "pos": pos, "stat": stat,
            "games": len(values), "r2": r2, "verdict": verdict,
            "alpha": params[0], "loc": params[1], "scale": params[2],
        })

    fig.suptitle(f"{player_name} ({pos}) — fits & Q-Q", fontsize=14)
    fig.tight_layout()
    safe = merge_name.replace(" ", "_")
    fig.savefig(PLOTS / f"{pos}_{safe}.png", dpi=100)
    plt.close(fig)
    return records


def main() -> int:
    print("Loading 2024 weekly stats …")
    weekly = nfl.load_player_stats(seasons=[2024]).to_pandas()
    weekly = weekly[weekly["season_type"] == "REG"]

    all_records: list[dict] = []
    for pos, players in PLAYERS.items():
        for name, merge in players:
            pdf = weekly[weekly["player_display_name"].str.lower() == merge]
            if pdf.empty:
                pdf = weekly[weekly["player_name"].str.lower().str.contains(
                    merge.split()[-1], na=False)]  # last-name fallback
            print(f"  {pos} {name}: {len(pdf)} games")
            all_records.extend(fit_and_plot(name, merge, pos, pdf))

    import csv
    csv_path = pathlib.Path(__file__).parent / "fit_results.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
        w.writeheader()
        w.writerows(all_records)

    total = len(all_records)
    acceptable = sum(1 for r in all_records if r.get("verdict") == "acceptable")
    print(f"\nAcceptable fits: {acceptable}/{total} ({100*acceptable/total:.0f}%)")
    print(f"Plots: {PLOTS}/")
    print(f"CSV:   {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

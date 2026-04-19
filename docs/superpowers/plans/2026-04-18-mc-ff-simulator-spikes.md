# Pre-Implementation Spike Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the six pre-implementation validation spikes defined in the MVP design spec §9.1. Each spike has a pass/fail gate. Their outputs (reports, fixtures, demo apps) become inputs to the MVP implementation plan.

**Architecture:** Each spike is a self-contained Python script under `spikes/<id>-<slug>/`. All share a single `spikes/.venv` via `spikes/requirements.txt`. Reports are markdown. Artifacts (HTML fixtures, plots, benchmark JSON) commit alongside the code. A final roll-up `spikes/GATING.md` records the go/no-go verdict per spike.

**Tech Stack:** Python 3.12+, `nflreadpy`, `polars`, `pandas`, `scipy`, `matplotlib`, `lxml` for parsing, FastAPI + Docker + Fly.io CLI for C1, Docker resource limits for C2.

**Related spec:** [`docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md`](../specs/2026-04-18-mc-ff-simulator-mvp-design.md) §9.

**Execution order:** Task 0 first (bootstrap). A1, B1, B2, C1 can run in parallel as independent subagents. A2 depends on A1's fitting approach being validated. C2 can run parallel to C1. Task 7 (gating review) is last and depends on all prior spikes.

---

## File Structure

```
spikes/
├── README.md                        # overview + how to run
├── requirements.txt                 # pinned deps
├── .gitignore                       # .venv/, __pycache__/, *.egg-info
├── GATING.md                        # (Task 7) final go/no-go
│
├── a1-skew-normal-fits/
│   ├── fit.py                       # fit + plot script
│   ├── plots/*.png                  # committed
│   └── report.md
│
├── a2-calibration/
│   ├── backtest.py                  # calibration backtest script
│   ├── coverage.csv
│   └── report.md
│
├── b1-id-resolution/
│   ├── resolve.py                   # prototype resolver
│   ├── hit_rates.csv
│   └── report.md
│
├── b2-parser/
│   ├── parse.py                     # MultiIndex flatten test
│   └── report.md
│
├── c1-deploy/
│   ├── app/main.py                  # minimal FastAPI
│   ├── Dockerfile
│   ├── fly.toml
│   └── report.md
│
└── c2-perf/
    ├── bench.py                     # prototype simulate_player
    ├── Dockerfile
    └── report.md

tests/fixtures/
├── fantasypros_qb.html              # produced by B1
├── fantasypros_rb.html
├── fantasypros_wr.html
└── fantasypros_te.html
```

Root-level files also modified: `.gitignore` (to include `spikes/.venv/`).

---

## Task 0: Bootstrap Spike Infrastructure

**Files:**
- Create: `spikes/README.md`
- Create: `spikes/requirements.txt`
- Create: `spikes/.gitignore`
- Modify: `.gitignore` (root)

- [ ] **Step 1: Create `spikes/` directory tree**

```bash
mkdir -p spikes/{a1-skew-normal-fits,a2-calibration,b1-id-resolution,b2-parser,c1-deploy,c2-perf} tests/fixtures
```

- [ ] **Step 2: Write `spikes/requirements.txt`**

```
nflreadpy==0.1.5
polars==1.17.1
pandas==2.2.3
pyarrow==18.1.0
scipy==1.14.1
numpy==2.1.3
matplotlib==3.10.0
lxml==5.3.0
html5lib==1.1
beautifulsoup4==4.12.3
fastapi==0.115.5
uvicorn[standard]==0.32.1
```

(Versions are current-latest as of 2026-04. Engineer may bump if compatible.)

- [ ] **Step 3: Write `spikes/.gitignore`**

```
.venv/
__pycache__/
*.egg-info/
*.pyc
.pytest_cache/
.ipynb_checkpoints/
```

- [ ] **Step 4: Append venv path to root `.gitignore`**

```bash
echo "spikes/.venv/" >> .gitignore
echo ".DS_Store" >> .gitignore
```

- [ ] **Step 5: Write `spikes/README.md`**

```markdown
# Validation Spikes

Six pre-implementation spikes validate assumptions in the MVP design spec §9.

## Setup

```bash
python3 -m venv spikes/.venv
spikes/.venv/bin/pip install -r spikes/requirements.txt
```

## Running a spike

```bash
cd spikes/<id>-<slug>
../.venv/bin/python <script>.py
```

Each spike produces a `report.md` with pass/fail verdict. `GATING.md` at the top level rolls up.

## Spike directory

| ID | What it validates | Kill criterion |
|---|---|---|
| A1 | Skew-normal fits NFL weekly stats | <50% of (player, stat) pairs show acceptable Q-Q |
| A2 | Mean-shift produces calibrated intervals | Coverage <60% or >95% |
| B1 | Tier 1+3 identity resolution hit rate | <80% resolved |
| B2 | One HTML parser handles QB/RB/WR/TE | Any position needs a 4th strategy |
| C1 | Fly deploy within 512 MB + free credit | Peak RAM >512 MB or cost >$10/mo |
| C2 | `simulate_player` <200 ms on Fly-sized compute | p95 >1 s even at n=1000 |

See [spec §9](../docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md) for full detail.
```

- [ ] **Step 6: Create the venv and install deps**

```bash
python3 -m venv spikes/.venv && spikes/.venv/bin/pip install --upgrade pip && spikes/.venv/bin/pip install -r spikes/requirements.txt
```

Expected: `pip install` completes with no errors. Ignore deprecation warnings.

- [ ] **Step 7: Smoke-test nflreadpy from the new venv**

```bash
spikes/.venv/bin/python -c "import nflreadpy; df = nflreadpy.load_ff_playerids(); print(df.shape)"
```

Expected output: `(12187, 35)` or similar (numbers may drift with source refreshes).

- [ ] **Step 8: Commit**

```bash
git add spikes/README.md spikes/requirements.txt spikes/.gitignore .gitignore
git commit -m "chore: bootstrap spike infrastructure"
```

---

## Task 1: Spike A1 — Skew-Normal Distribution Fit Sanity Check

**Files:**
- Create: `spikes/a1-skew-normal-fits/fit.py`
- Create: `spikes/a1-skew-normal-fits/plots/` (directory, populated by script)
- Create: `spikes/a1-skew-normal-fits/report.md`

Validates [ADR-0004](../../adr/0004-simulation-engine-veterans-only-skew-normal.md). Kill if <50% of pairs show acceptable fit.

- [ ] **Step 1: Pick 10 veteran players covering QB/RB/WR/TE**

Use this roster (edit if any player retires/injury before run):

```python
# spikes/a1-skew-normal-fits/fit.py (top)
PLAYERS = {
    # position → [(display_name, merge_name)]
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
```

- [ ] **Step 2: Write the fit + plot script**

Full content of `spikes/a1-skew-normal-fits/fit.py`:

```python
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
```

- [ ] **Step 3: Run the script**

```bash
spikes/.venv/bin/python spikes/a1-skew-normal-fits/fit.py
```

Expected: prints per-player game counts, then `Acceptable fits: XX/YY (ZZ%)`. Writes plots + CSV.

- [ ] **Step 4: Inspect a few plots visually**

```bash
open spikes/a1-skew-normal-fits/plots/QB_patrick_mahomes.png
open spikes/a1-skew-normal-fits/plots/WR_tyreek_hill.png
open spikes/a1-skew-normal-fits/plots/TE_travis_kelce.png
```

Note: TD counts are often problematic (near-integer Poisson-ish). Flag these in report if visible.

- [ ] **Step 5: Write `spikes/a1-skew-normal-fits/report.md`**

Fill in the actual numbers from the CSV. Template:

```markdown
# Spike A1 Report — Skew-Normal Fit Sanity Check

**Date:** <YYYY-MM-DD>
**Validates:** ADR-0004 (simulation engine — veterans-only, per-stat skew-normal).
**Kill criterion:** <50% of (player, stat) pairs show acceptable fit (Q-Q R² ≥ 0.95).

## Results

- Players sampled: 10 (QB×3, RB×2, WR×3, TE×2)
- Stats fit: <N> total (player, stat) pairs
- Acceptable (R² ≥ 0.95): <X>/<N> = <pct>%
- Poor: <Y>/<N>

### Per-position breakdown

| Position | Pairs | Acceptable | Pct |
|---|---|---|---|
| QB | … | … | … |
| RB | … | … | … |
| WR | … | … | … |
| TE | … | … | … |

### Notable failures (R² < 0.95)

(List 3–5 worst pairs with R² and a one-line observation — usually something like "TD counts cluster at 0,1,2; skew-normal smears mass into negative and gets clamped, producing unrealistic 0-spike.")

## Verdict

- [ ] **PASS** — ≥70% acceptable, no systematic family-level failure
- [ ] **BORDERLINE** — 50–70% acceptable; note cases where skew-normal is shaky but salvageable
- [ ] **FAIL (KILL)** — <50% acceptable, or TD/reception counts universally fail. Design revision required.

## Recommendation

<Plain-text: one of the below, or a variant>
- Skew-normal is fine for all stats. Proceed to implementation as specified.
- Skew-normal fine for continuous (yards) but count stats (TDs, receptions) need a discrete distribution. Recommend updating spec §4.1.1 and ADR-0004 to use `scipy.stats.nbinom` (negative-binomial) for count stats.
- Skew-normal is broadly wrong; investigate alternatives (empirical bootstrap, kernel density).

## Artifacts

- `plots/*.png` — 10 per-player fit + Q-Q panels.
- `fit_results.csv` — every (player, stat) with R² and fit params.
```

- [ ] **Step 6: Commit**

```bash
git add spikes/a1-skew-normal-fits/
git commit -m "chore: run spike A1 skew-normal fit sanity check"
```

---

## Task 2: Spike A2 — Mean-Shift Calibration Backtest

**Files:**
- Create: `spikes/a2-calibration/backtest.py`
- Create: `spikes/a2-calibration/coverage.csv`
- Create: `spikes/a2-calibration/report.md`

**Depends on Task 1** — if A1 killed, A2 either changes distribution family or skips. Validates that mean-shifted historical σ produces calibrated intervals.

**Projection source:** We lack archived 2024 preseason projections. Proxy: use 2023 per-game averages × 17 games as the "projection." This tests the shift logic even though the projection itself is naive. Document the caveat in the report.

- [ ] **Step 1: Write `spikes/a2-calibration/backtest.py`**

```python
"""
Spike A2: Mean-shift calibration backtest.
Hold out 2024; fit on 2021–2023; shift to a 2024 projection proxy
(2023 per-game average × 17); check if actual 2024 season total
lands inside predicted p10–p90.

Kill criterion: coverage rate <60% or >95% across player-stat pairs.
"""
from __future__ import annotations
import csv
import pathlib
import numpy as np
import nflreadpy as nfl
from scipy import stats

N_SAMPLES = 5000
SEED = 42

# Use the same 10-player roster as A1.
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

WEIGHTS = {2023: 0.50, 2022: 0.30, 2021: 0.20}


def fit_shifted(values: np.ndarray, target_mean: float):
    """Fit skew-normal, then shift loc so dist mean == target_mean."""
    params = stats.skewnorm.fit(values)
    alpha, loc, scale = params
    # skew-normal mean = loc + scale * delta * sqrt(2/pi), delta = alpha / sqrt(1+alpha^2)
    delta = alpha / np.sqrt(1 + alpha ** 2)
    current_mean = loc + scale * delta * np.sqrt(2 / np.pi)
    shift = target_mean - current_mean
    return (alpha, loc + shift, scale)


def simulate_season(shifted_params, n_games: int, rng) -> np.ndarray:
    """Sample n_games per simulation, sum, repeat N_SAMPLES times."""
    alpha, loc, scale = shifted_params
    # shape: (N_SAMPLES, n_games)
    samples = stats.skewnorm.rvs(alpha, loc=loc, scale=scale,
                                 size=(N_SAMPLES, n_games),
                                 random_state=rng)
    samples = np.clip(samples, 0, None)
    return samples.sum(axis=1)


def main() -> int:
    print("Loading historical 2021–2024 …")
    hist = nfl.load_player_stats(seasons=[2021, 2022, 2023, 2024]).to_pandas()
    hist = hist[hist["season_type"] == "REG"]

    records = []
    rng = np.random.default_rng(SEED)

    for pos, names in PLAYERS.items():
        for merge in names:
            player_rows = hist[hist["player_display_name"].str.lower() == merge]
            if player_rows.empty:
                player_rows = hist[hist["player_name"].str.lower().str.contains(
                    merge.split()[-1], na=False)]

            train = player_rows[player_rows["season"].isin([2021, 2022, 2023])]
            test = player_rows[player_rows["season"] == 2024]
            test_games = len(test)
            if test_games < 4 or len(train) < 4:
                print(f"  {pos} {merge}: insufficient data, skipping")
                continue

            for stat in STATS_BY_POS[pos]:
                train_vals = train[stat].to_numpy()
                train_vals = train_vals[~np.isnan(train_vals)]
                if len(train_vals) < 4:
                    continue

                # Weighted mean across 2021/2022/2023 per-game averages
                per_season = {
                    y: train[train["season"] == y][stat].mean()
                    for y in [2021, 2022, 2023]
                }
                # 2024 projection proxy: weighted prior-year avg × test_games
                weighted_avg = sum(WEIGHTS[y] * v for y, v in per_season.items()
                                   if not np.isnan(v))
                projection_total = weighted_avg * test_games

                try:
                    shifted = fit_shifted(train_vals, weighted_avg)
                except Exception as e:
                    print(f"    fit error {pos} {merge} {stat}: {e}")
                    continue

                sim_totals = simulate_season(shifted, test_games, rng)
                p10, p50, p90 = np.percentile(sim_totals, [10, 50, 90])
                actual = test[stat].sum()
                inside = p10 <= actual <= p90

                records.append({
                    "pos": pos, "player": merge, "stat": stat,
                    "games_train": len(train_vals),
                    "games_test": test_games,
                    "projection_total": round(projection_total, 2),
                    "p10": round(p10, 2), "p50": round(p50, 2), "p90": round(p90, 2),
                    "actual": round(actual, 2),
                    "inside_p10_p90": inside,
                })

    csv_path = pathlib.Path(__file__).parent / "coverage.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    n = len(records)
    hits = sum(1 for r in records if r["inside_p10_p90"])
    print(f"\nCoverage: {hits}/{n} = {100*hits/n:.0f}% inside p10–p90 (target 80%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the backtest**

```bash
spikes/.venv/bin/python spikes/a2-calibration/backtest.py
```

Expected: prints per-player coverage, then overall `Coverage: XX/YY = ZZ%`.

- [ ] **Step 3: Write `spikes/a2-calibration/report.md`**

```markdown
# Spike A2 Report — Mean-Shift Calibration Backtest

**Date:** <YYYY-MM-DD>
**Validates:** §9.1.2 — mean-shifted historical variance produces calibrated intervals.
**Kill criterion:** coverage <60% or >95%.

## Method

- Train on 2021–2023 regular-season weekly stats, recency weights [0.5, 0.3, 0.2].
- Projection proxy: weighted prior-year per-game avg × 2024 games played (naive; flags need in report below).
- Shift fitted skew-normal mean to projection proxy.
- Sample 5000 season totals (sum of n_games independent samples).
- Check: does actual 2024 season total land inside predicted p10–p90?

## Caveats

- Projection proxy is not a real preseason projection; it's a last-year-average baseline. A real preseason projection (e.g. FantasyPros consensus) would be less lookback-correlated and more faithful to the production system. This test mainly validates the *shift and sample* mechanics, not end-to-end preseason-to-actual calibration.

## Results

| Position | Pairs | Inside p10–p90 | Pct |
|---|---|---|---|
| QB | … | … | … |
| RB | … | … | … |
| WR | … | … | … |
| TE | … | … | … |
| **Total** | **N** | **H** | **P%** |

### Notable outliers (>1σ beyond p90 or <p10)

(Free text: players whose 2024 drastically exceeded or undershot the projection. Discuss whether the miss is a projection-quality problem, a variance problem, or both.)

## Verdict

- [ ] **PASS** — coverage 70–90%.
- [ ] **BORDERLINE** — 60–70% or 90–95%; note bias direction.
- [ ] **FAIL (KILL)** — <60% (overconfident) or >95% (vacuous).

## Recommendation

<One of:>
- Shift + sample approach is well calibrated. Proceed.
- Systematic overconfidence (narrow intervals). Consider inflating σ by <factor> or blending in a projection-source-derived variance.
- Systematic underconfidence. Tighten by reducing recency weight on older years.

## Artifacts

- `coverage.csv` — full per-pair data.
```

- [ ] **Step 4: Commit**

```bash
git add spikes/a2-calibration/
git commit -m "chore: run spike A2 calibration backtest"
```

---

## Task 3: Spike B1 — Identity Resolution Hit-Rate

**Files:**
- Create: `tests/fixtures/fantasypros_{qb,rb,wr,te}.html`
- Create: `spikes/b1-id-resolution/resolve.py`
- Create: `spikes/b1-id-resolution/hit_rates.csv`
- Create: `spikes/b1-id-resolution/report.md`

Validates [ADR-0005](../../adr/0005-identity-resolution-tiers-1-and-3-only.md). Kill if <80% resolved.

- [ ] **Step 1: Harvest FantasyPros HTML for all four positions**

```bash
for pos in qb rb wr te; do
  curl -sL -o tests/fixtures/fantasypros_${pos}.html \
    "https://www.fantasypros.com/nfl/projections/${pos}.php?export=xls"
done
ls -la tests/fixtures/
```

Expected: four HTML files, each ≥40 KB. (They'll be full pages; `pandas.read_html` extracts the projection table.)

- [ ] **Step 2: Write `spikes/b1-id-resolution/resolve.py`**

```python
"""
Spike B1: Identity resolution hit-rate for FantasyPros HTML.
Kill criterion: <80% resolved.
"""
from __future__ import annotations
import csv
import pathlib
import re
import pandas as pd
import nflreadpy as nfl

FIXTURES = pathlib.Path(__file__).parents[2] / "tests" / "fixtures"
POSITIONS = ["qb", "rb", "wr", "te"]

# Known ID columns we look for in Tier 1 (FantasyPros default export has none,
# but we include for completeness — users may hand-augment).
KNOWN_ID_COLS = {
    "fantasypros_id", "espn_id", "yahoo_id", "sleeper_id",
    "cbs_id", "pfr_id", "fantasy_data_id", "rotowire_id", "nfl_id",
}


def normalize_name(name: str) -> str:
    """Apply the same transform nflreadpy uses for merge_name."""
    s = name.lower().strip()
    s = re.sub(r"[.']", "", s)          # strip periods and apostrophes
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", s)  # strip suffixes
    s = re.sub(r"\s+", " ", s)
    return s


def split_name_team(combined: str) -> tuple[str, str]:
    """'Jalen Hurts PHI' → ('Jalen Hurts', 'PHI')."""
    parts = combined.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def load_canonical():
    df = nfl.load_ff_playerids().to_pandas()
    df = df[df["gsis_id"].notna()]
    return df


def resolve_row(csv_row: dict, pos: str, canonical: pd.DataFrame) -> str:
    """Return 'tier1' | 'tier3_single' | 'tier3_ambiguous' | 'unresolved'."""
    # Tier 1
    for col in csv_row:
        if col in KNOWN_ID_COLS and pd.notna(csv_row[col]):
            match = canonical[canonical[col] == csv_row[col]]
            if len(match) >= 1:
                return "tier1"
    # Tier 3
    combined = csv_row.get("player", "")
    name, team = split_name_team(combined)
    merge = normalize_name(name)
    match = canonical[
        (canonical["merge_name"] == merge)
        & (canonical["team"] == team)
        & (canonical["position"] == pos.upper())
    ]
    if len(match) == 1:
        return "tier3_single"
    if len(match) > 1:
        return "tier3_ambiguous"
    return "unresolved"


def main() -> int:
    canonical = load_canonical()
    print(f"Canonical player table: {len(canonical)} rows (gsis_id NOT NULL)")

    outcomes: list[dict] = []
    for pos in POSITIONS:
        html_path = FIXTURES / f"fantasypros_{pos}.html"
        tables = pd.read_html(html_path)
        # FantasyPros projection table is the largest one
        projection = max(tables, key=lambda t: t.shape[0])
        # Flatten MultiIndex if present
        if isinstance(projection.columns, pd.MultiIndex):
            projection.columns = [
                lvl1 if lvl0.startswith("Unnamed") else f"{lvl0}_{lvl1}"
                for lvl0, lvl1 in projection.columns
            ]
        print(f"\n{pos.upper()}: {len(projection)} rows")
        for _, row in projection.iterrows():
            csv_row = {c: row[c] for c in projection.columns}
            # FantasyPros combines name+team under "Player"
            csv_row.setdefault("player", row.get("Player", ""))
            result = resolve_row(csv_row, pos, canonical)
            outcomes.append({"pos": pos.upper(), "row": csv_row["player"],
                             "outcome": result})

    # Summary
    by_pos: dict[str, dict[str, int]] = {}
    for o in outcomes:
        by_pos.setdefault(o["pos"], {}).setdefault(o["outcome"], 0)
        by_pos[o["pos"]][o["outcome"]] += 1

    csv_path = pathlib.Path(__file__).parent / "hit_rates.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pos", "row", "outcome"])
        w.writeheader()
        w.writerows(outcomes)

    print("\n=== Summary ===")
    total_resolved = 0
    total = 0
    for pos, counts in by_pos.items():
        n = sum(counts.values())
        resolved = counts.get("tier1", 0) + counts.get("tier3_single", 0)
        total += n
        total_resolved += resolved
        print(f"  {pos}: {counts} → resolved {resolved}/{n} ({100*resolved/n:.0f}%)")
    print(f"\nOVERALL: {total_resolved}/{total} ({100*total_resolved/total:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run the resolver**

```bash
spikes/.venv/bin/python spikes/b1-id-resolution/resolve.py
```

Expected: prints per-position counts (`{'tier3_single': N, 'tier3_ambiguous': M, 'unresolved': K}`) and overall percentage.

- [ ] **Step 4: Write `spikes/b1-id-resolution/report.md`**

```markdown
# Spike B1 Report — Identity Resolution Hit-Rate

**Date:** <YYYY-MM-DD>
**Validates:** ADR-0005 (Tiers 1 + 3 only).
**Kill criterion:** <80% resolved.

## Results

| Position | Tier 1 | Tier 3 single | Tier 3 ambiguous | Unresolved | Total | Resolved % |
|---|---|---|---|---|---|---|
| QB | … | … | … | … | … | …% |
| RB | … | … | … | … | … | …% |
| WR | … | … | … | … | … | …% |
| TE | … | … | … | … | … | …% |
| **Total** | **…** | **…** | **…** | **…** | **…** | **…%** |

### Unresolved or ambiguous — sample

List 5–10 problematic rows with the CSV "Player" field and a one-line diagnosis (e.g. "name has Jr. suffix", "team abbrev mismatch DET vs DEN", "missing from canonical — rookie").

## Verdict

- [ ] **PASS** — ≥90% resolved.
- [ ] **BORDERLINE** — 80–90%; note the failure modes.
- [ ] **FAIL (KILL)** — <80%.

## Recommendation

<One of:>
- Tier 1+3 sufficient as specified in ADR-0005. Proceed.
- Add normalization rules: <list, e.g. "strip Jr./Sr.", "JAX/JAC → JAX", etc.>.
- Add Tier 2 (jersey number) if FantasyPros starts publishing jersey.
- Consider Tier 4 fuzzy match with disambiguation UI — revise ADR-0005.

## Artifacts

- `hit_rates.csv` — every row with its resolution outcome.
- `tests/fixtures/fantasypros_{qb,rb,wr,te}.html` — committed for downstream use (B2 and MVP tests).
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/fantasypros_*.html spikes/b1-id-resolution/
git commit -m "chore: run spike B1 identity resolution hit-rate + commit FP fixtures"
```

---

## Task 4: Spike B2 — FantasyPros HTML Parser Robustness

**Files:**
- Create: `spikes/b2-parser/parse.py`
- Create: `spikes/b2-parser/report.md`

**Depends on Task 3** (uses its HTML fixtures). Validates that one parser implementation covers QB/RB/WR/TE MultiIndex shapes.

- [ ] **Step 1: Write `spikes/b2-parser/parse.py`**

```python
"""
Spike B2: Verify one parser + mapping table handles all four positional
MultiIndex layouts from FantasyPros HTML.
Kill criterion: any position needs a strategy not in {by_name, by_index,
fantasypros_multi_header}.
"""
from __future__ import annotations
import pathlib
import pandas as pd

FIXTURES = pathlib.Path(__file__).parents[2] / "tests" / "fixtures"

# Canonical stat vocabulary = nflreadpy column names.
# Section × short-code → canonical name (or None = ignored).
FP_SECTION_MAP = {
    ("PASSING", "ATT"): "attempts",
    ("PASSING", "CMP"): "completions",
    ("PASSING", "YDS"): "passing_yards",
    ("PASSING", "TDS"): "passing_tds",
    ("PASSING", "INTS"): "passing_interceptions",
    ("RUSHING", "ATT"): "carries",
    ("RUSHING", "YDS"): "rushing_yards",
    ("RUSHING", "TDS"): "rushing_tds",
    ("RECEIVING", "REC"): "receptions",
    ("RECEIVING", "YDS"): "receiving_yards",
    ("RECEIVING", "TDS"): "receiving_tds",
    ("RECEIVING", "TGT"): "targets",
    ("MISC", "FL"): "rushing_fumbles_lost",
    ("MISC", "FPTS"): None,  # ignored; we compute our own
}


def parse_position(path: pathlib.Path, pos: str):
    tables = pd.read_html(path)
    df = max(tables, key=lambda t: t.shape[0])
    if not isinstance(df.columns, pd.MultiIndex):
        raise AssertionError(f"{pos}: expected MultiIndex columns, got flat")

    mapped = {}
    unmapped = []
    for lvl0, lvl1 in df.columns:
        if lvl0.startswith("Unnamed"):
            continue  # Player column
        key = (lvl0, lvl1)
        if key in FP_SECTION_MAP:
            mapped[(lvl0, lvl1)] = FP_SECTION_MAP[key]
        else:
            unmapped.append(key)
    return mapped, unmapped, df.shape


def main() -> int:
    ok = True
    for pos in ["qb", "rb", "wr", "te"]:
        path = FIXTURES / f"fantasypros_{pos}.html"
        mapped, unmapped, shape = parse_position(path, pos)
        print(f"\n=== {pos.upper()} ({shape[0]} rows, {shape[1]} cols) ===")
        print("Mapped:")
        for k, v in mapped.items():
            print(f"  {k} → {v}")
        if unmapped:
            print("UNMAPPED:")
            for k in unmapped:
                print(f"  {k} !!")
            ok = False
        else:
            print("  (all columns mapped)")

    print("\nPASS" if ok else "\nFAIL — some columns unmapped; update FP_SECTION_MAP")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the parser check**

```bash
spikes/.venv/bin/python spikes/b2-parser/parse.py
```

Expected: per-position column listings + `PASS`. If FAIL, note which `(section, code)` pairs are unmapped.

- [ ] **Step 3: Write `spikes/b2-parser/report.md`**

```markdown
# Spike B2 Report — FantasyPros HTML Parser Robustness

**Date:** <YYYY-MM-DD>
**Validates:** §9.1.4 — one parser handles QB/RB/WR/TE MultiIndex shapes.
**Kill criterion:** any position needs a strategy not in {by_name, by_index, fantasypros_multi_header}.

## Results

| Position | Rows | Columns | All mapped | Unmapped |
|---|---|---|---|---|
| QB | … | … | ✓/✗ | `(section, code), …` |
| RB | … | … | ✓/✗ | … |
| WR | … | … | ✓/✗ | … |
| TE | … | … | ✓/✗ | … |

## Verdict

- [ ] **PASS** — all positions fully covered by the existing map.
- [ ] **FAIL (KILL)** — new strategy required. Describe what's needed.

## Recommendation

<One of:>
- Map table as in `parse.py` is complete. Promote to `api/app/import_pipeline/column_mapper.py` as the canonical `FP_SECTION_MAP`.
- Add these entries to the map: `<(section, code): canonical>` …
- Some positions need fundamentally different handling. Revise spec §4 and ADR-0009.

## Artifacts

- `parse.py` promotable to `api/tests/unit/test_csv_parser_fantasypros.py` after minor edits.
```

- [ ] **Step 4: Commit**

```bash
git add spikes/b2-parser/
git commit -m "chore: run spike B2 parser robustness across positions"
```

---

## Task 5: Spike C1 — Fly Deploy Smoke Test

**Files:**
- Create: `spikes/c1-deploy/app/main.py`
- Create: `spikes/c1-deploy/Dockerfile`
- Create: `spikes/c1-deploy/fly.toml`
- Create: `spikes/c1-deploy/.dockerignore`
- Create: `spikes/c1-deploy/report.md`

Validates [ADR-0002](../../adr/0002-host-backend-on-fly-and-frontend-on-vercel.md) + [ADR-0006](../../adr/0006-sqlite-on-fly-volume-with-nflreadpy-cache.md). Kill if peak RAM >512 MB or cost >$10/mo.

**Prerequisites:** `flyctl` installed (`brew install flyctl`) and authenticated (`fly auth login`).

- [ ] **Step 1: Verify Fly CLI**

```bash
which flyctl && fly auth whoami
```

Expected: CLI path + your account email. If not: `brew install flyctl && fly auth login`.

- [ ] **Step 2: Write `spikes/c1-deploy/app/main.py`**

```python
"""Minimal FastAPI app for Fly smoke test."""
from __future__ import annotations
import os
import pathlib
import time
import resource
from fastapi import FastAPI

app = FastAPI()
DATA = pathlib.Path("/data")
HIST = DATA / "historical"
os.environ.setdefault("NFLREADPY_CACHE_DIR", str(HIST))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_mounted": DATA.is_dir(),
        "historical_seasons": [p.stem for p in HIST.glob("*.parquet")]
                              if HIST.is_dir() else [],
    }


@app.post("/api/seed")
def seed():
    import nflreadpy as nfl
    HIST.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ids = nfl.load_ff_playerids()
    t_ids = time.time() - t0

    stats_times = {}
    for y in [2023, 2024, 2025]:
        t = time.time()
        nfl.load_player_stats(seasons=[y])
        stats_times[y] = round(time.time() - t, 1)

    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS returns bytes, Linux returns KB. Assume Linux on Fly.
    peak_mb = round(peak_kb / 1024, 1)

    return {
        "ids_rows": ids.height,
        "ids_seconds": round(t_ids, 1),
        "stats_times_by_year": stats_times,
        "peak_rss_mb": peak_mb,
        "disk_mb": round(sum(p.stat().st_size for p in HIST.rglob("*"))
                          / 1024 / 1024, 1),
    }
```

- [ ] **Step 3: Write `spikes/c1-deploy/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 4: Copy requirements**

```bash
cp spikes/requirements.txt spikes/c1-deploy/requirements.txt
```

- [ ] **Step 5: Write `spikes/c1-deploy/.dockerignore`**

```
.venv/
__pycache__/
*.pyc
```

- [ ] **Step 6: Launch a new Fly app (interactive; choose defaults)**

```bash
cd spikes/c1-deploy
fly launch --no-deploy --copy-config=false --name=ffsim-spike-c1 --region=iad --yes
```

Expected: generates `fly.toml`. Edit to set VM size + volume. Overwrite `fly.toml` with:

```toml
app = "ffsim-spike-c1"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"

[mounts]
  source = "ffsim_spike_data"
  destination = "/data"
```

- [ ] **Step 7: Create volume + deploy**

```bash
fly volumes create ffsim_spike_data --region iad --size 1 --yes
fly deploy
```

Expected: first deploy takes 2–5 min. Ends with `Visit your newly deployed app at https://ffsim-spike-c1.fly.dev`.

- [ ] **Step 8: Trigger seed and capture metrics**

```bash
curl -X POST https://ffsim-spike-c1.fly.dev/api/seed | tee spikes/c1-deploy/seed_output.json
```

Expected: JSON with `ids_rows`, `ids_seconds`, `stats_times_by_year`, `peak_rss_mb`, `disk_mb`. Takes 60–120 s.

- [ ] **Step 9: Check boot time and monitor RAM**

```bash
fly logs --app ffsim-spike-c1 | head -30
fly metrics --app ffsim-spike-c1
```

Note cold-boot time from logs and peak RAM from the metrics dashboard. Add both to the report.

- [ ] **Step 10: Check projected cost**

```bash
fly billing
```

Note current month-to-date. Estimate monthly at idle + with occasional usage.

- [ ] **Step 11: Write `spikes/c1-deploy/report.md`**

```markdown
# Spike C1 Report — Fly Deploy Smoke

**Date:** <YYYY-MM-DD>
**Validates:** ADR-0002 (Fly host), ADR-0006 (SQLite + volume).
**Kill criterion:** peak RAM >512 MB or projected cost >$10/mo.

## Measurements

| Metric | Value | Threshold | Pass? |
|---|---|---|---|
| Cold-boot time | …s | <90 s | |
| Seed wall time | …s (ids + 3×stats) | — | |
| Peak RSS during seed | …MB | <512 MB | |
| Final volume disk usage | …MB | <200 MB | |
| Month-to-date cost (at deploy) | $… | — | |
| Projected cost at idle | $…/mo | ≤$5 | |
| Projected cost active | $…/mo | ≤$10 | |

## Verdict

- [ ] **PASS** — all thresholds met.
- [ ] **BORDERLINE** — near a threshold; see recommendation.
- [ ] **FAIL (KILL)** — peak RAM >512 MB or projected cost >$10/mo.

## Recommendation

<One of:>
- shared-cpu-1x @ 512 MB is sufficient. Proceed with MVP deploy using this template.
- Bump memory to 1 GB (cost delta: $…/mo). Update ADR-0002 / Risk R2.
- Host choice needs revisiting; see Risk R3.

## Tear-down (after review)

```bash
fly apps destroy ffsim-spike-c1 --yes
fly volumes list  # verify removed
```

## Artifacts

- `seed_output.json` — raw response from /api/seed.
- Dockerfile, fly.toml, app/main.py kept as deploy template for MVP.
```

- [ ] **Step 12: Commit**

```bash
cd ../..
git add spikes/c1-deploy/
git commit -m "chore: run spike C1 Fly deploy smoke"
```

---

## Task 6: Spike C2 — Monte Carlo Performance on Constrained Compute

**Files:**
- Create: `spikes/c2-perf/bench.py`
- Create: `spikes/c2-perf/Dockerfile`
- Create: `spikes/c2-perf/report.md`

Can run in parallel with C1. Validates Requirements v1.2 §7.3. Kill if p95 >1 s even at n=1000.

- [ ] **Step 1: Write `spikes/c2-perf/bench.py`**

```python
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

    # Pick 100 players with most games
    top = (df.groupby("player_id")
             .size()
             .sort_values(ascending=False)
             .head(N_PLAYERS).index)

    stat = "passing_yards"  # pick one per-player for benchmarking
    rng = np.random.default_rng(SEED)

    latencies_5k: list[float] = []
    latencies_1k: list[float] = []
    for pid in top:
        vals = df[df["player_id"] == pid][stat].dropna().to_numpy()
        if len(vals) < 4:
            continue
        target = vals.mean()

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
```

- [ ] **Step 2: Write `spikes/c2-perf/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bench.py .
CMD ["python", "bench.py"]
```

- [ ] **Step 3: Copy requirements**

```bash
cp spikes/requirements.txt spikes/c2-perf/requirements.txt
```

- [ ] **Step 4: Build the constrained image and run**

```bash
cd spikes/c2-perf
docker build -t ffsim-c2-perf .
docker run --rm --memory=512m --cpus=0.25 \
  -v "$(pwd):/out" ffsim-c2-perf \
  sh -c "python bench.py && cp bench_result.json /out/"
```

Expected: prints `{n_samples_5000: {p50_ms, p95_ms, max_ms}, n_samples_1000: {…}}` and writes `bench_result.json` to the host.

Note: first run downloads nflreadpy data inside the container (no volume); that's fine for this bench.

- [ ] **Step 5: Write `spikes/c2-perf/report.md`**

```markdown
# Spike C2 Report — Monte Carlo Performance

**Date:** <YYYY-MM-DD>
**Validates:** Requirements v1.2 §7.3 (<200 ms per player distribution).
**Kill criterion:** p95 >1 s at both n=5000 and n=1000.

## Measurements

Hardware: `--memory=512m --cpus=0.25` (≈ Fly shared-cpu-1x / 512MB).
Benchmark: 100 players × (fit + sample + percentile) on `passing_yards`.

| n_samples | count | p50 (ms) | p95 (ms) | max (ms) |
|---|---|---|---|---|
| 5000 | … | … | … | … |
| 1000 | … | … | … | … |

## Verdict

- [ ] **PASS** — p50 <200 ms and p95 <500 ms at n=5000.
- [ ] **BORDERLINE** — meets threshold at n=1000 but not n=5000. Set default n=1000 and document.
- [ ] **FAIL (KILL)** — p95 >1 s at both settings. Profile and redesign.

## Recommendation

<One of:>
- n=5000 is comfortably within budget. Ship with this default.
- Lower default n to 1000; update spec §5 DistributionResponse default.
- Investigate NumPy/SciPy hotspots (likely `skewnorm.fit` or `skewnorm.rvs`). Consider caching fit params aggressively, or replacing fit with method-of-moments closed form.

## Artifacts

- `bench_result.json` — raw timing output.
```

- [ ] **Step 6: Commit**

```bash
cd ../..
git add spikes/c2-perf/
git commit -m "chore: run spike C2 Monte Carlo perf on constrained compute"
```

---

## Task 7: Roll-Up Gating Review

**Files:**
- Create: `spikes/GATING.md`

Reads every spike report. Writes a one-page go/no-go document for the whole pre-implementation phase.

- [ ] **Step 1: Verify every spike has a report**

```bash
ls spikes/*/report.md
```

Expected: 6 files.

- [ ] **Step 2: Write `spikes/GATING.md`**

```markdown
# Pre-Implementation Gating Review

**Date:** <YYYY-MM-DD>
**Spec reference:** [`docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md`](../docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md) §9.4.

## Per-spike verdicts

| Spike | Verdict | Gate unblocks |
|---|---|---|
| A1 — skew-normal fits | ✓ PASS / ⚠ BORDERLINE / ✗ FAIL | all app code |
| A2 — calibration | ✓ / ⚠ / ✗ | `sim/`, `historical/` beyond stubs |
| B1 — ID resolution hit-rate | ✓ / ⚠ / ✗ | all app code |
| B2 — parser robustness | ✓ / ⚠ / ✗ | all app code |
| C1 — Fly deploy | ✓ / ⚠ / ✗ | all app code |
| C2 — MC perf | ✓ / ⚠ / ✗ | `sim/` final tuning |

## Required design revisions (from any FAIL or BORDERLINE)

<Enumerate. For each, link to the spike report and note which ADR / spec section needs updating. E.g.:

- A1 borderline on TD counts — spike recommends adding negative-binomial support for count stats. Action: new ADR-0012 and update spec §4.1.1. See [A1 report](a1-skew-normal-fits/report.md).
- C1 required 1GB RAM — action: update ADR-0002, Risk R2, and fly.toml template.>

(If all PASS, write "None — proceed to MVP implementation plan.")

## Overall gate

- [ ] **GO** — all PASS or all BORDERLINE/PASS mix accepted. Proceed to MVP implementation planning.
- [ ] **REVISE** — one or more FAIL requires spec/ADR updates before implementation. List actions above.
- [ ] **STOP** — fundamental assumption broken; brainstorm again.

## Next step

<On GO: "Run `superpowers:writing-plans` to produce the MVP implementation plan, referencing spike artifacts in `spikes/*/`.">
```

- [ ] **Step 3: Fill in the table and recommendations by reading each report**

No code here — just consolidated editorial based on the six `report.md` files.

- [ ] **Step 4: Commit**

```bash
git add spikes/GATING.md
git commit -m "docs: pre-implementation gating review"
```

---

## Self-Review

**Spec coverage:**
- ✅ §9.1.1 Spike A1 → Task 1
- ✅ §9.1.2 Spike A2 → Task 2
- ✅ §9.1.3 Spike B1 → Task 3
- ✅ §9.1.4 Spike B2 → Task 4
- ✅ §9.1.5 Spike C1 → Task 5
- ✅ §9.1.6 Spike C2 → Task 6
- ✅ §9.4 Gating rule → Task 7 (rolls up per-spike verdicts into a single go/no-go)
- §9.2 During-implementation validation (walking skeleton, fixture TDD, canary) — these belong in the *MVP* plan, not this spike plan.
- §9.3 Post-MVP validation — belongs in post-MVP follow-up, not this plan.

**Placeholder scan:** no "TBD", no "handle edge cases", no "similar to Task N". Every code block is complete. `<YYYY-MM-DD>` in report templates is a placeholder the engineer fills in at run time — acceptable because it's user-entered data, not code logic.

**Type consistency:** `fit_shifted`, `simulate_season`, `fit_player`, `simulate` — these are one-off names per script, no cross-task references. `FP_SECTION_MAP` in B2 matches the example mapping in spec §4 (`(PASSING, ATT) → "attempts"` etc.).

**Ambiguous/external dependencies called out:**
- A2 uses a proxy projection (2023 per-game avg) — flagged in the script docstring and report template.
- C1 requires `flyctl` installed + authenticated — Step 1 verifies.
- C2 requires Docker installed — implicit; engineer can install if missing.
- B1 depends on FantasyPros `export=xls` URL continuing to return HTML tables — if FP blocks it, Step 1 fails and the task pauses for engineer to source HTML manually.

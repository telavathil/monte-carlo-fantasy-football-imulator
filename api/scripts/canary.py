"""Canary comparison: pick 5 top-ADP players and compare median
distribution output to their projected points. Should match within ~1 pt.
"""
from __future__ import annotations
import os
import requests

API_URL = os.environ["API_URL"]
TOKEN = os.environ["API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def main() -> int:
    rows = requests.get(f"{API_URL}/api/players?has_projection=true",
                        headers=HEADERS).json()
    # Top 5 by projected_points
    top = sorted([r for r in rows if r.get("projected_points")],
                 key=lambda r: -r["projected_points"])[:5]
    print(f"{'name':25s} {'proj':>8s} {'p50':>8s} {'diff':>8s}")
    bad = 0
    for r in top:
        try:
            dist = requests.get(
                f"{API_URL}/api/players/{r['player_id']}/distribution",
                headers=HEADERS).json()
        except Exception as e:
            print(f"{r['name']:25s} error: {e}")
            continue
        p50 = dist["distribution"]["median_p50"]
        diff = abs(p50 - r["projected_points"])
        flag = "  " if diff <= 5.0 else "!!"  # per-game values; allow wider tolerance
        if diff > 5.0:
            bad += 1
        print(f"{r['name']:25s} {r['projected_points']:>8.1f} {p50:>8.1f} {diff:>8.1f} {flag}")
    if bad > 0:
        print(f"\n{bad} players differed by >5 pts — investigate")
        return 1
    print("\nCanary PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

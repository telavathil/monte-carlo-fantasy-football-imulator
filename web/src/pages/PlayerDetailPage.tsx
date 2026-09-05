import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../api/auth";
import type { DistributionResponse } from "../api/types";
import { usePreset } from "../context/PresetContext";
import { Card } from "../components/Card";
import { StatTile } from "../components/StatTile";
import { ErrorState } from "../components/ErrorState";
import { PositionBadge } from "../components/PositionBadge";
import { PresetSelector } from "../components/PresetSelector";
import { Histogram } from "../components/Histogram";
import { statLabel } from "../lib/statLabels";
import { formatPoints } from "../lib/format";

export function PlayerDetailPage() {
  const { id } = useParams();
  const { preset, setPreset } = usePreset();

  const [data, setData] = useState<DistributionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDistribution = useCallback(() => {
    setLoading(true);
    setError(null);
    apiFetch<DistributionResponse>(`/api/players/${id}/distribution`)
      .then((resp) => setData(resp))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load player.");
      })
      .finally(() => setLoading(false));
  }, [id]);

  // Load once on mount, and again whenever the route navigates to a different
  // player — independent of whether PresetContext has resolved its initial
  // GET yet, so the page always shows *something* even if that fetch is slow
  // or fails.
  useEffect(() => {
    fetchDistribution();
  }, [id, fetchDistribution]);

  // A genuine preset *change* must refetch too — the distribution's numbers
  // depend on it. `preset` starts at `null` and resolves asynchronously; that
  // resolution is not a change a user made and must not trigger a redundant
  // second fetch. `presetEverSet` flips exactly once, on the render that
  // first sees a non-null preset; that specific transition is skipped. Every
  // subsequent change is real and refetches.
  const presetEverSet = useRef(false);
  useEffect(() => {
    if (preset === null) return;
    const wasUnset = !presetEverSet.current;
    presetEverSet.current = true;
    if (wasUnset) return;
    fetchDistribution();
  }, [preset, fetchDistribution]);

  const adpText = data?.adp_snake != null ? data.adp_snake.toFixed(1) : "—";

  return (
    <div className="flex flex-col gap-4">
      <Link to="/players" className="text-sm text-muted hover:text-primary">
        ← Players
      </Link>

      {loading ? (
        <Card className="p-4">
          <p className="text-sm text-muted">Loading player…</p>
        </Card>
      ) : error ? (
        <ErrorState title="Couldn't load player" body={error} onRetry={fetchDistribution} />
      ) : data ? (
        <>
          <div className="flex items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-3">
                <h1 className="font-display text-4xl font-bold text-primary">{data.name}</h1>
                <PositionBadge position={data.position} />
              </div>
              <div className="text-sm text-muted">
                {data.position} · {data.team ?? "—"} · ADP {adpText}
              </div>
            </div>
            {preset ? <PresetSelector value={preset} onChange={setPreset} /> : null}
          </div>

          <div className="grid grid-cols-3 gap-4">
            <StatTile label="FLOOR (P10)" value={formatPoints(data.distribution.floor_p10)} />
            <StatTile
              label="MEDIAN (P50)"
              value={formatPoints(data.distribution.median_p50)}
              emphasis
            />
            <StatTile label="CEILING (P90)" value={formatPoints(data.distribution.ceiling_p90)} />
          </div>

          <Card className="p-4">
            <Histogram
              binEdges={data.distribution.histogram.bin_edges}
              counts={data.distribution.histogram.counts}
              floorP10={data.distribution.floor_p10}
              p25={data.distribution.p25}
              medianP50={data.distribution.median_p50}
              p75={data.distribution.p75}
              ceilingP90={data.distribution.ceiling_p90}
            />
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4">
              <h2 className="font-display text-sm font-bold text-primary">Projected stats</h2>
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
                      &nbsp;
                    </th>
                    <th className="text-right text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
                      Mean per game
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.projection.stats).map(([key, value]) => (
                    <tr key={key} className="border-t border-hairline">
                      <td className="py-1.5 text-primary">{statLabel(key)}</td>
                      <td className="tabular py-1.5 text-right text-primary">
                        {value.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="p-4">
              <h2 className="font-display text-sm font-bold text-primary">Model notes</h2>
              <div className="mt-3">
                <div className="tabular text-lg font-semibold text-primary">
                  Sample skew {data.distribution.skewness.toFixed(2)}
                </div>
                <p className="mt-1 text-xs text-muted">
                  Positive values mean a longer upside tail.
                </p>
              </div>
              <p className="mt-4 text-xs text-muted">
                Distributions reflect the uncertainty around the imported projection.
                Calibration to actual season outcomes is approximate; treat intervals as
                informed bounds, not guarantees.
              </p>
            </Card>
          </div>

          <div className="text-xs text-muted">
            Fit from {data.fit.games_used} games · seasons{" "}
            {data.fit.historical_seasons.join("–")}
          </div>
        </>
      ) : null}
    </div>
  );
}

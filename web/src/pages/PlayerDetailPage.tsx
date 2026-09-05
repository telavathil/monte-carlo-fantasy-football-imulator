import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api/auth";
import { Histogram } from "../components/Histogram";

type DistResp = {
  player_id: number;
  gsis_id: string;
  projection: { stats: Record<string, number> };
  scoring_preset: string;
  computed_points: number;
  distribution: {
    n_samples: number;
    floor_p10: number;
    median_p50: number;
    ceiling_p90: number;
    mean: number;
    std: number;
    histogram: { bin_edges: number[]; counts: number[] };
  };
  fit: { fitted_at: string; historical_seasons: number[]; games_used: number };
};

export function PlayerDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<DistResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DistResp>(`/api/players/${id}/distribution`)
      .then(setData).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <pre>{err}</pre>;
  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <h1>Player {data.player_id}</h1>
      <p>Projected points ({data.scoring_preset}): <strong>{data.computed_points.toFixed(1)}</strong></p>
      <p>
        Floor (p10): {data.distribution.floor_p10.toFixed(1)} ·{" "}
        Median: {data.distribution.median_p50.toFixed(1)} ·{" "}
        Ceiling (p90): {data.distribution.ceiling_p90.toFixed(1)}{" "}
        <span style={{ fontSize: "0.8em", color: "#777" }}>(per-game distribution)</span>
      </p>
      <p style={{ fontSize: "0.85em", color: "#555", maxWidth: 600 }}>
        <em>Calibration note:</em> Distributions reflect the uncertainty around the
        imported projection. Calibration to actual season outcomes is approximate;
        treat intervals as informed bounds, not guarantees.
      </p>
      <Histogram
        binEdges={data.distribution.histogram.bin_edges}
        counts={data.distribution.histogram.counts}
      />
      <h3>Projected stats</h3>
      <ul>
        {Object.entries(data.projection.stats).map(([k, v]) => (
          <li key={k}>{k}: {v}</li>
        ))}
      </ul>
      <p style={{ fontSize: "0.8em", color: "#777" }}>
        Fit: {data.fit.games_used} historical games, seasons{" "}
        {data.fit.historical_seasons.join(", ")}
      </p>
    </div>
  );
}

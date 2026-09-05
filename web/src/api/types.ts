export type Preset = "standard" | "half_ppr" | "full_ppr";
export type SummaryStatus = "ok" | "insufficient_history" | "unsupported_position";

export type Histogram = { bin_edges: number[]; counts: number[] };

export type DistributionSummary = {
  status: SummaryStatus;
  floor_p10: number | null;
  p25: number | null;
  median_p50: number | null;
  p75: number | null;
  ceiling_p90: number | null;
  mean: number | null;
  std: number | null;
  skewness: number | null;
  histogram: Histogram | null;
  computed_at: string;
};

export type PlayerRow = {
  player_id: number;
  gsis_id: string;
  name: string;
  team: string | null;
  position: string;
  projected_stats: Record<string, number>;
  projected_points: number | null;
  adp_snake: number | null;
  adp_auction: number | null;
  distribution: DistributionSummary | null;
};

export type DistributionResponse = {
  player_id: number;
  gsis_id: string;
  name: string;
  team: string | null;
  position: string;
  adp_snake: number | null;
  projection: { stats: Record<string, number>; import_batch_id: number };
  scoring_preset: Preset;
  computed_points: number;
  distribution: {
    n_samples: number;
    floor_p10: number;
    p25: number;
    median_p50: number;
    p75: number;
    ceiling_p90: number;
    mean: number;
    std: number;
    skewness: number;
    histogram: Histogram;
  };
  fit: { fitted_at: string; historical_seasons: number[]; games_used: number };
};

export type PrecomputeResult = {
  computed: number;
  done: number;
  total: number;
  remaining: number;
};

export type UnresolvedRow = {
  parsed_name: string | null;
  parsed_team: string | null;
  position: string | null;
  resolution: string;
  csv_row: Record<string, unknown>;
};

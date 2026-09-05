import { BarChart, Bar, XAxis, ReferenceLine, ReferenceArea, ResponsiveContainer } from "recharts";
import { formatPoints } from "../lib/format";

type Props = {
  binEdges: number[];
  counts: number[];
  floorP10: number;
  p25: number;
  medianP50: number;
  p75: number;
  ceilingP90: number;
};

const BAR_FILL = "#FBBF24";
const BAND_FILL = "#818CF8";

/** The bin whose [edge, next edge) range contains `value` (clamped to the last bin). */
function binLabelForValue(bins: { label: string; lo: number; hi: number }[], value: number): string {
  const containing = bins.find((bin) => value >= bin.lo && value < bin.hi);
  return (containing ?? bins[bins.length - 1]).label;
}

function PercentileFlag({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </span>
      <span className="tabular text-xs font-semibold text-primary">{formatPoints(value)}</span>
    </div>
  );
}

export function Histogram({ binEdges, counts, floorP10, p25, medianP50, p75, ceilingP90 }: Props) {
  const bins = counts.map((_, i) => ({
    label: `${binEdges[i].toFixed(0)}-${binEdges[i + 1].toFixed(0)}`,
    lo: binEdges[i],
    hi: binEdges[i + 1],
  }));
  const data = counts.map((count, i) => ({ bin: bins[i].label, count }));

  const floorLabel = binLabelForValue(bins, floorP10);
  const medianLabel = binLabelForValue(bins, medianP50);
  const ceilingLabel = binLabelForValue(bins, ceilingP90);

  return (
    <div>
      <div className="mb-3 flex items-center justify-center gap-6">
        <PercentileFlag label="P10" value={floorP10} />
        <PercentileFlag label="P25" value={p25} />
        <PercentileFlag label="P50" value={medianP50} />
        <PercentileFlag label="P75" value={p75} />
        <PercentileFlag label="P90" value={ceilingP90} />
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 20, right: 8, bottom: 24, left: 8 }}>
          <XAxis
            dataKey="bin"
            tick={{ fontSize: 10, fill: "#7A8699" }}
            axisLine={{ stroke: "#232A36" }}
            tickLine={false}
            label={{
              value: "Fantasy points per game",
              position: "insideBottom",
              offset: -16,
              fill: "#7A8699",
              fontSize: 11,
            }}
          />
          <ReferenceArea
            x1={floorLabel}
            x2={ceilingLabel}
            fill={BAND_FILL}
            fillOpacity={0.15}
            stroke="none"
          />
          <Bar dataKey="count" fill={BAR_FILL} isAnimationActive={false} />
          <ReferenceLine
            x={medianLabel}
            stroke="#F1F5F9"
            strokeDasharray="4 4"
            label={{
              value: formatPoints(medianP50),
              position: "top",
              fill: "#F1F5F9",
              fontSize: 11,
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

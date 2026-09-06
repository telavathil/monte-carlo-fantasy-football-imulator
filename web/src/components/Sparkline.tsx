import type { Histogram } from "../api/types";
import { buildAreaPath, bandBounds } from "../lib/sparkline";
import { formatPoints } from "../lib/format";

type Props = {
  histogram: Histogram;
  floor: number;
  median: number;
  ceiling: number;
  width?: number;
  height?: number;
};

/**
 * Hand-rolled inline SVG distribution shape. Rendered once per player card on the
 * Players list (potentially hundreds of rows), so this deliberately avoids a
 * charting library like recharts in favor of plain SVG built from pre-computed math.
 */
export function Sparkline({
  histogram,
  floor,
  median,
  ceiling,
  width = 220,
  height = 56,
}: Props) {
  const areaPath = buildAreaPath(histogram.counts, width, height);
  const band = bandBounds(histogram.bin_edges, floor, ceiling, width);
  const medianLine = bandBounds(histogram.bin_edges, median, median, width);

  const label = `Distribution: floor ${formatPoints(floor)}, median ${formatPoints(
    median,
  )}, ceiling ${formatPoints(ceiling)} points per game`;

  return (
    <svg
      className="text-accent"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
    >
      <rect
        x={band.x1}
        y={0}
        width={band.x2 - band.x1}
        height={height}
        className="text-violet"
        fill="currentColor"
        opacity={0.12}
      />
      {areaPath ? (
        <path
          d={areaPath}
          fill="currentColor"
          fillOpacity={0.3}
          stroke="currentColor"
          strokeWidth={2}
        />
      ) : null}
      <line
        x1={medianLine.x1}
        x2={medianLine.x1}
        y1={0}
        y2={height}
        stroke="currentColor"
        strokeWidth={1}
        strokeDasharray="2,2"
      />
    </svg>
  );
}

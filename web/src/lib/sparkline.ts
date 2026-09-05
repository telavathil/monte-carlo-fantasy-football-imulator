/** Build a closed SVG area path from histogram bin counts. */
export function buildAreaPath(counts: number[], width: number, height: number): string {
  if (counts.length === 0) return "";
  const peak = Math.max(...counts);
  const scale = peak > 0 ? peak : 1;
  const step = counts.length > 1 ? width / (counts.length - 1) : width;

  const points = counts.map((count, i) => {
    const x = Math.min(i * step, width);
    const y = height - (count / scale) * height;
    return `${round(x)},${round(y)}`;
  });

  return `M0,${round(height)} L${points.join(" L")} L${round(width)},${round(height)} Z`;
}

/** Pixel bounds of a [lo, hi] value range across the histogram's x axis. */
export function bandBounds(
  binEdges: number[],
  lo: number,
  hi: number,
  width: number,
): { x1: number; x2: number } {
  const first = binEdges[0];
  const last = binEdges[binEdges.length - 1];
  const span = last - first;
  if (!Number.isFinite(span) || span <= 0) return { x1: 0, x2: 0 };
  const toX = (value: number) =>
    Math.max(0, Math.min(width, ((value - first) / span) * width));
  return { x1: toX(lo), x2: toX(hi) };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

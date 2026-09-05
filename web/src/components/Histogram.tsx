import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type Props = {
  binEdges: number[];
  counts: number[];
};

export function Histogram({ binEdges, counts }: Props) {
  const data = counts.map((count, i) => ({
    bin: `${binEdges[i].toFixed(0)}-${binEdges[i + 1].toFixed(0)}`,
    count,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <XAxis dataKey="bin" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="count" fill="#5b8def" />
      </BarChart>
    </ResponsiveContainer>
  );
}

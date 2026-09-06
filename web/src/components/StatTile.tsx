import { Card } from "./Card";

type Props = {
  label: string;
  value: string;
  sub?: string;
  emphasis?: boolean;
};

export function StatTile({ label, value, sub, emphasis = false }: Props) {
  return (
    <Card className={emphasis ? "border-accent/40 bg-accent/5 p-4" : "p-4"}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </div>
      <div
        className={`tabular font-display text-4xl font-bold ${
          emphasis ? "text-accent" : "text-primary"
        }`}
      >
        {value}
        <span className="ml-2 text-sm font-normal text-muted">pts / game</span>
      </div>
      {sub ? <div className="mt-1 text-xs text-muted">{sub}</div> : null}
    </Card>
  );
}

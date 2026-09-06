export type PositionFilter = "ALL" | "QB" | "RB" | "WR" | "TE";

const POSITIONS: readonly PositionFilter[] = ["ALL", "QB", "RB", "WR", "TE"];

type Props = {
  value: PositionFilter;
  onChange: (value: PositionFilter) => void;
  counts?: Partial<Record<PositionFilter, number>>;
};

export function PositionTabs({ value, onChange, counts }: Props) {
  return (
    <div className="inline-flex gap-1">
      {POSITIONS.map((position) => {
        const active = position === value;
        const count = counts?.[position];
        return (
          <button
            key={position}
            type="button"
            onClick={() => onChange(position)}
            className={
              active
                ? "rounded-base bg-accent px-3 py-1.5 text-sm font-semibold text-canvas"
                : "rounded-base border border-hairline px-3 py-1.5 text-sm text-muted hover:text-primary"
            }
          >
            {position}
            {count !== undefined ? (
              <span className={active ? "ml-1.5 text-canvas/70" : "ml-1.5 text-ghost"}>
                {count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

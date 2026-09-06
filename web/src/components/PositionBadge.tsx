// This exact mapping resolves a disagreement in the Stitch export's own design-system
// doc — copy it verbatim, do not "fix" or restyle it.
const STYLES: Readonly<Record<string, string>> = {
  QB: "bg-violet/15 text-violet",
  RB: "bg-success/15 text-success",
  WR: "bg-accent/15 text-accent",
  TE: "bg-warn/15 text-warn",
};

type Props = {
  position: string;
};

export function PositionBadge({ position }: Props) {
  const style = STYLES[position] ?? "bg-well text-muted";
  return (
    <span
      className={`rounded-[2px] px-1 py-px text-[10px] font-bold uppercase ${style}`}
    >
      {position}
    </span>
  );
}

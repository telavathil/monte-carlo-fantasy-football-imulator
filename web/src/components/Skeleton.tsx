import { Card } from "./Card";

type Props = {
  className?: string;
};

export function Skeleton({ className = "" }: Props) {
  return <div className={`animate-pulse rounded-base bg-well ${className}`} />;
}

// Mirrors the geometry of the Players list card described in the design spec (§7):
// name + "POS · TEAM · ADP" on the left, a sparkline in the centre, the dominant
// points number on the right, and a footer strip for floor/median/ceiling. Task 14's
// PlayerCard did not exist yet when this was built, so this shape is derived from the
// spec's own prose rather than mirrored from that component.
export function SkeletonPlayerCard() {
  return (
    <Card className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-4">
        <div className="flex w-36 flex-shrink-0 flex-col gap-2">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-20" />
        </div>
        <Skeleton className="h-10 flex-1" />
        <Skeleton className="h-9 w-20 flex-shrink-0" />
      </div>
      <div className="flex gap-4 border-t border-hairline pt-3">
        <Skeleton className="h-3 w-14" />
        <Skeleton className="h-3 w-14" />
        <Skeleton className="h-3 w-14" />
      </div>
    </Card>
  );
}

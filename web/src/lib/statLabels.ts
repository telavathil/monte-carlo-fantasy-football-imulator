/** Canonical nflreadpy stat keys (ADR-0009) to human labels. */
const LABELS: Readonly<Record<string, string>> = {
  passing_yards: "Passing yards",
  passing_tds: "Passing TDs",
  passing_interceptions: "Interceptions",
  rushing_yards: "Rushing yards",
  rushing_tds: "Rushing TDs",
  receiving_yards: "Receiving yards",
  receiving_tds: "Receiving TDs",
  receptions: "Receptions",
  rushing_fumbles_lost: "Fumbles lost",
};

export function statLabel(key: string): string {
  const known = LABELS[key];
  if (known) return known;
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

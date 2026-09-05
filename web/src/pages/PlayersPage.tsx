import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "../api/auth";
import type { PlayerRow } from "../api/types";
import { usePreset } from "../context/PresetContext";
import { useDebounce } from "../hooks/useDebounce";
import { useWarming } from "../hooks/useWarming";
import { SearchInput } from "../components/SearchInput";
import { PositionTabs, type PositionFilter } from "../components/PositionTabs";
import { PlayerCard } from "../components/PlayerCard";
import { SkeletonPlayerCard } from "../components/Skeleton";
import { WarmingPanel } from "../components/WarmingPanel";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";

type SortKey = "projected" | "adp" | "ceiling" | "floor";

const SORT_LABELS: Record<SortKey, string> = {
  projected: "Projected",
  adp: "ADP",
  ceiling: "Ceiling",
  floor: "Floor",
};

/** Sort a copy of rows by the chosen key. Never mutates the input array. */
function sortRows(rows: PlayerRow[], sort: SortKey): PlayerRow[] {
  const byDescending =
    (get: (row: PlayerRow) => number | null) => (a: PlayerRow, b: PlayerRow) =>
      (get(b) ?? -Infinity) - (get(a) ?? -Infinity);
  const byAscending =
    (get: (row: PlayerRow) => number | null) => (a: PlayerRow, b: PlayerRow) =>
      (get(a) ?? Infinity) - (get(b) ?? Infinity);

  switch (sort) {
    case "adp":
      return [...rows].sort(byAscending((row) => row.adp_snake));
    case "ceiling":
      return [...rows].sort(byDescending((row) => row.distribution?.ceiling_p90 ?? null));
    case "floor":
      return [...rows].sort(byDescending((row) => row.distribution?.floor_p10 ?? null));
    case "projected":
    default:
      return [...rows].sort(byDescending((row) => row.projected_points));
  }
}

export function PlayersPage() {
  const { preset } = usePreset();
  const warming = useWarming();

  const [rows, setRows] = useState<PlayerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [position, setPosition] = useState<PositionFilter>("ALL");
  const [sort, setSort] = useState<SortKey>("projected");

  const debouncedQuery = useDebounce(query, 200);

  const fetchRows = useCallback(() => {
    setLoading(true);
    setError(null);
    apiFetch<PlayerRow[]>("/api/players?has_projection=true")
      .then((data) => setRows(data))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load players.");
      })
      .finally(() => setLoading(false));
  }, []);

  // Load once on mount, independent of whether PresetContext has resolved its
  // initial GET yet — the backend already has a real preset configured
  // server-side even if this page doesn't know it yet, and blocking the
  // player list on that fetch would hang the page forever if the config
  // request ever fails.
  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  // The backend scopes each player's projected_points/distribution to
  // whatever scoring preset is currently configured, so a genuine preset
  // *change* must refetch. `preset` starts at `null` and resolves
  // asynchronously (see PresetContext) — that resolution is not a change a
  // user made, so it must not trigger a second, redundant fetch (which would
  // also flash the list back to its loading skeleton right after the first
  // load renders). `presetEverSet` flips exactly once, on the render that
  // first sees a non-null preset; that specific transition is skipped.
  // Every subsequent change is a real one and refetches.
  const presetEverSet = useRef(false);
  useEffect(() => {
    if (preset === null) return;
    const wasUnset = !presetEverSet.current;
    presetEverSet.current = true;
    if (wasUnset) return;
    fetchRows();
  }, [preset, fetchRows]);

  const counts = useMemo<Partial<Record<PositionFilter, number>>>(
    () => ({
      ALL: rows.length,
      QB: rows.filter((row) => row.position === "QB").length,
      RB: rows.filter((row) => row.position === "RB").length,
      WR: rows.filter((row) => row.position === "WR").length,
      TE: rows.filter((row) => row.position === "TE").length,
    }),
    [rows],
  );

  const visibleRows = useMemo(() => {
    const needle = debouncedQuery.trim().toLowerCase();
    const filtered = rows
      .filter((row) => position === "ALL" || row.position === position)
      .filter((row) => needle === "" || row.name.toLowerCase().includes(needle));
    return sortRows(filtered, sort);
  }, [rows, position, debouncedQuery, sort]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="w-72">
          <SearchInput value={query} onChange={setQuery} />
        </div>
        <PositionTabs value={position} onChange={setPosition} counts={counts} />
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as SortKey)}
          className="ml-auto rounded-base border border-hairline bg-well px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
        >
          {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
            <option key={key} value={key}>
              {SORT_LABELS[key]}
            </option>
          ))}
        </select>
      </div>

      {warming ? (
        <>
          <WarmingPanel />
          <div className="flex flex-col gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonPlayerCard key={i} />
            ))}
          </div>
        </>
      ) : loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonPlayerCard key={i} />
          ))}
        </div>
      ) : error ? (
        <ErrorState title="Couldn't load players" body={error} onRetry={fetchRows} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No projections yet"
          body="Import a stat projection CSV to get started"
          actionLabel="Go to Import"
          actionTo="/import"
        />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {visibleRows.map((row) => (
              <PlayerCard key={row.player_id} row={row} onComputed={fetchRows} />
            ))}
          </div>
          <div className="text-xs text-muted">{visibleRows.length} players</div>
        </>
      )}
    </div>
  );
}

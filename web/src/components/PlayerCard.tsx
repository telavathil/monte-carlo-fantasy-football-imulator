import { useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "./Card";
import { PositionBadge } from "./PositionBadge";
import { Sparkline } from "./Sparkline";
import { apiFetch } from "../api/auth";
import { formatPoints } from "../lib/format";
import type { PlayerRow, PrecomputeResult } from "../api/types";

type Props = {
  row: PlayerRow;
  /** Called after a successful "Compute" POST so the parent can refetch the list. */
  onComputed?: () => void;
};

const TERMINAL_MESSAGES: Record<string, string> = {
  insufficient_history: "Not enough career games",
  unsupported_position: "Not modeled yet",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function PlayerCard({ row, onComputed }: Props) {
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<string | null>(null);

  const handleCompute = async (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setComputing(true);
    setComputeError(null);
    try {
      await apiFetch<PrecomputeResult>("/api/players/precompute?limit=1", {
        method: "POST",
      });
      onComputed?.();
    } catch (error) {
      setComputeError(
        error instanceof Error ? error.message : "Failed to compute distribution.",
      );
    } finally {
      setComputing(false);
    }
  };

  const distribution = row.distribution;
  const isOk = distribution?.status === "ok";
  const adpText = row.adp_snake !== null ? row.adp_snake.toFixed(1) : "—";

  return (
    <Link to={`/players/${row.player_id}`} className="block" data-testid="player-card">
      <Card className="flex flex-col gap-4 p-4 transition-colors hover:border-interactive">
        <div className="flex items-center gap-4">
          <div className="flex w-56 flex-shrink-0 items-center gap-3">
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-hairline bg-well font-display text-sm font-semibold text-muted">
              {initials(row.name)}
            </div>
            <div className="flex flex-col gap-1">
              <div className="font-display text-lg font-semibold">{row.name}</div>
              <div className="flex items-center gap-1.5">
                <PositionBadge position={row.position} />
              </div>
              <div className="text-xs text-muted">
                {row.position} · {row.team ?? "—"} · ADP {adpText}
              </div>
            </div>
          </div>

          <div className="flex flex-1 items-center justify-center">
            {isOk && distribution?.histogram ? (
              <Sparkline
                histogram={distribution.histogram}
                floor={distribution.floor_p10 ?? 0}
                median={distribution.median_p50 ?? 0}
                ceiling={distribution.ceiling_p90 ?? 0}
              />
            ) : distribution ? (
              <span className="text-sm text-muted">
                {TERMINAL_MESSAGES[distribution.status] ?? "Not modeled yet"}
              </span>
            ) : (
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted">Not computed</span>
                <button
                  type="button"
                  onClick={handleCompute}
                  disabled={computing}
                  className="rounded-base border border-hairline px-3 py-1.5 text-sm font-semibold text-primary hover:border-interactive disabled:opacity-50"
                >
                  {computing ? "Computing…" : "Compute"}
                </button>
                {computeError ? (
                  <span className="text-xs text-warn">{computeError}</span>
                ) : null}
              </div>
            )}
          </div>

          <div className="flex flex-shrink-0 flex-col items-end">
            <div className="tabular font-display text-4xl font-bold text-accent">
              {formatPoints(row.projected_points)}
            </div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
              pts / game
            </div>
          </div>
        </div>

        <div className="flex gap-6 border-t border-hairline pt-3">
          <FooterStat
            label="Floor"
            value={isOk ? formatPoints(distribution?.floor_p10) : "—"}
          />
          <FooterStat
            label="Median"
            value={isOk ? formatPoints(distribution?.median_p50) : "—"}
          />
          <FooterStat
            label="Ceiling"
            value={isOk ? formatPoints(distribution?.ceiling_p90) : "—"}
          />
        </div>
      </Card>
    </Link>
  );
}

function FooterStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </div>
      <div className="tabular text-sm font-semibold text-primary">{value}</div>
    </div>
  );
}

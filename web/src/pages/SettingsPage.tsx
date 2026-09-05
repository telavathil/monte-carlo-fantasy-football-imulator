import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "../api/auth";
import type { HealthCheck, Preset } from "../api/types";
import { usePreset } from "../context/PresetContext";
import { Card } from "../components/Card";

const PRESET_LABELS: Record<Preset, string> = {
  standard: "Standard",
  half_ppr: "Half PPR",
  full_ppr: "Full PPR",
};

const PRESETS = Object.keys(PRESET_LABELS) as Preset[];

type ConnectionState = {
  ok: boolean;
  message: string;
};

/**
 * `/api/health` always reports `status: "ok"` — there is no server-side
 * degraded-status path. Whether the connection is actually healthy has to be
 * derived here from the individual fields, in priority order: a down
 * database outranks missing historical data, and only when both are fine do
 * we report success (using the real season range rather than a hardcoded
 * one).
 */
function deriveConnectionState(health: HealthCheck): ConnectionState {
  if (!health.db) {
    return { ok: false, message: "Database unreachable." };
  }
  if (!health.historical_ready || health.historical_seasons.length === 0) {
    return { ok: false, message: "No historical data loaded." };
  }
  const seasons = health.historical_seasons;
  const first = seasons[0];
  const last = seasons[seasons.length - 1];
  return {
    ok: true,
    message: `Connected · database ready · seasons ${first}–${last}`,
  };
}

export function SettingsPage() {
  const { preset, setPreset } = usePreset();
  const [connection, setConnection] = useState<ConnectionState | null>(null);

  // The token is baked into the client at build time (Vite env var); there's
  // no backend endpoint to persist a new one against. This field is a local,
  // editable draft so the shape the design calls for is present, without
  // pretending a "Save" click here changes what the running app sends.
  const [tokenDraft, setTokenDraft] = useState(
    () => (import.meta.env.VITE_API_TOKEN as string) ?? "",
  );
  const [tokenSaved, setTokenSaved] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiFetch<HealthCheck>("/api/health")
      .then((health) => {
        if (!cancelled) setConnection(deriveConnectionState(health));
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not reach the server.";
        setConnection({ ok: false, message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-6 text-left">
      <h1 className="font-display text-lg font-semibold text-primary">Settings</h1>

      <Card className="flex flex-col gap-4 p-4">
        <h2 className="font-display text-sm font-semibold text-primary">Connection</h2>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-muted" htmlFor="api-token">
            API token
          </label>
          <div className="flex gap-2">
            <input
              id="api-token"
              type="password"
              value={tokenDraft}
              onChange={(event) => {
                setTokenDraft(event.target.value);
                setTokenSaved(false);
              }}
              className="flex-1 rounded-base border border-hairline bg-well px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setTokenSaved(true)}
              className="rounded-base bg-accent px-3 py-1.5 text-sm font-semibold text-canvas hover:bg-accent/90"
            >
              {tokenSaved ? "Saved" : "Save"}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              connection === null ? "bg-ghost" : connection.ok ? "bg-success" : "bg-danger"
            }`}
          />
          <span className={connection?.ok ? "text-primary" : "text-muted"}>
            {connection ? connection.message : "Checking connection…"}
          </span>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-4">
        <h2 className="font-display text-sm font-semibold text-primary">Scoring</h2>

        <div className="inline-flex w-fit overflow-hidden rounded-base border border-hairline">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPreset(p)}
              className={
                preset === p
                  ? "bg-accent px-3 py-1.5 text-sm font-semibold text-canvas"
                  : "bg-well px-3 py-1.5 text-sm font-semibold text-muted hover:text-primary"
              }
            >
              {PRESET_LABELS[p]}
            </button>
          ))}
        </div>

        <p className="text-xs text-muted">
          Changing this recomputes every player's distribution.
        </p>
      </Card>
    </div>
  );
}

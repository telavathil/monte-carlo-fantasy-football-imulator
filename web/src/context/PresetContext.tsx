import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch } from "../api/auth";
import type { Preset } from "../api/types";

type LeagueConfig = { scoring_preset: Preset; num_teams: number; updated_at: string };

type PresetContextValue = {
  preset: Preset | null;
  setPreset: (next: Preset) => Promise<void>;
};

const PresetContext = createContext<PresetContextValue | null>(null);

/**
 * Owns the single source of truth for the league's scoring preset.
 * AppShell renders the one PresetSelector, sourced from here; any page that
 * needs to read the active preset (to filter/sort by it, or refetch when it
 * changes) calls usePreset() instead of holding its own copy of
 * /api/league/config.
 */
export function PresetProvider({ children }: { children: ReactNode }) {
  const [preset, setPresetState] = useState<Preset | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<LeagueConfig>("/api/league/config")
      .then((cfg) => {
        if (!cancelled) setPresetState(cfg.scoring_preset);
      })
      .catch(() => {
        // Surfaced by whichever page actually needs the config (e.g.
        // PlayersPage's own error state); the selector just stays blank.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setPreset = useCallback(async (next: Preset) => {
    const updated = await apiFetch<LeagueConfig>("/api/league/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scoring_preset: next }),
    });
    setPresetState(updated.scoring_preset);
  }, []);

  return (
    <PresetContext.Provider value={{ preset, setPreset }}>
      {children}
    </PresetContext.Provider>
  );
}

export function usePreset(): PresetContextValue {
  const ctx = useContext(PresetContext);
  if (!ctx) {
    throw new Error("usePreset must be used within a PresetProvider");
  }
  return ctx;
}

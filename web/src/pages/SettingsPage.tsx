import { useEffect, useState } from "react";
import { apiFetch } from "../api/auth";

type Preset = "standard" | "half_ppr" | "full_ppr";
type Config = { scoring_preset: Preset; num_teams: number; updated_at: string };

export function SettingsPage() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Config>("/api/league/config").then(setCfg).catch((e) => setErr(String(e)));
  }, []);

  async function save(preset: Preset) {
    const updated = await apiFetch<Config>("/api/league/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scoring_preset: preset }),
    });
    setCfg(updated);
  }

  if (err) return <pre>{err}</pre>;
  if (!cfg) return <p>Loading…</p>;
  return (
    <div>
      <h1>Settings</h1>
      <p>Scoring preset: <strong>{cfg.scoring_preset}</strong></p>
      <p>
        {(["standard", "half_ppr", "full_ppr"] as Preset[]).map((p) => (
          <button key={p} onClick={() => save(p)} style={{ marginRight: 8 }}>
            {p}
          </button>
        ))}
      </p>
      <p>Teams: {cfg.num_teams} · Updated: {cfg.updated_at}</p>
    </div>
  );
}

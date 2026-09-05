import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/auth";

type Row = {
  player_id: number;
  name: string;
  team: string;
  position: string;
  projected_points: number | null;
  adp_snake: number | null;
};

export function PlayersPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Row[]>("/api/players?has_projection=true")
      .then(setRows).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <pre>{err}</pre>;
  const sortedRows = [...rows].sort(
    (a, b) => (b.projected_points ?? 0) - (a.projected_points ?? 0)
  );
  return (
    <div>
      <h1>Players</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Pos</th><th>Team</th><th>Proj</th><th>ADP</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((r) => (
            <tr key={r.player_id}>
              <td><Link to={`/players/${r.player_id}`}>{r.name}</Link></td>
              <td>{r.position}</td>
              <td>{r.team}</td>
              <td>{r.projected_points?.toFixed(1) ?? "—"}</td>
              <td>{r.adp_snake ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

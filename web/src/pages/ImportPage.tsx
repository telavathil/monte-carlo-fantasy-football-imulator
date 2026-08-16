import { useState } from "react";
import { authHeaders } from "../api/auth";

const API_URL = import.meta.env.VITE_API_URL as string;

export function ImportPage() {
  const [source, setSource] = useState("fantasypros");
  const [position, setPosition] = useState("QB");
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    const fd = new FormData(e.currentTarget);
    const kind = fd.get("kind") as string;
    const endpoint = kind === "adp" ? "/api/imports/adp" : "/api/imports/stats";
    try {
      const resp = await fetch(`${API_URL}${endpoint}`, {
        method: "POST", headers: authHeaders(), body: fd,
      });
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
      setResult(await resp.json());
    } catch (e: any) {
      setErr(String(e));
    }
  }

  return (
    <div>
      <h1>Import</h1>
      <form onSubmit={onSubmit}>
        <p>
          Kind:{" "}
          <select name="kind" defaultValue="stats">
            <option value="stats">Stats</option>
            <option value="adp">ADP</option>
          </select>
        </p>
        <p>
          Source: <input name="source" value={source} onChange={(e) => setSource(e.target.value)} />
        </p>
        <p>
          Position (stats only):{" "}
          <select name="position" value={position} onChange={(e) => setPosition(e.target.value)}>
            {["QB", "RB", "WR", "TE", "K", "DEF"].map((p) => <option key={p}>{p}</option>)}
          </select>
        </p>
        <p><input type="file" name="file" required /></p>
        <button type="submit">Upload</button>
      </form>
      {err && <pre style={{ color: "red" }}>{err}</pre>}
      {result && (
        <div>
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

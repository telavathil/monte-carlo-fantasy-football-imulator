import { useCallback, useRef, useState } from "react";
import { ApiError, apiFetch, authHeaders } from "../api/auth";
import { toUserMessage } from "../api/errors";
import type { ImportBatchResult, PrecomputeResult, UnresolvedRow } from "../api/types";
import { Card } from "../components/Card";
import { ErrorState } from "../components/ErrorState";

const API_URL = import.meta.env.VITE_API_URL as string;
const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"] as const;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Chunked and client-driven: each call is a real request, which also keeps
 * the Fly machine awake while the work runs.
 *
 * The loop must terminate because `status` gives every player a terminal
 * state. As a safety net, if `remaining` ever fails to decrease across two
 * consecutive calls, it stops and throws rather than looping forever.
 */
async function runPrecompute(
  onProgress: (p: PrecomputeResult) => void,
): Promise<void> {
  let lastRemaining = Infinity;
  for (;;) {
    const result = await apiFetch<PrecomputeResult>(
      "/api/players/precompute?limit=25",
      { method: "POST" },
    );
    onProgress(result);
    if (result.remaining === 0) return;
    if (result.remaining >= lastRemaining) {
      throw new Error(
        "Precompute isn't making progress — stopping rather than looping forever.",
      );
    }
    lastRemaining = result.remaining;
  }
}

type ResultTileProps = {
  label: string;
  value: number;
  warn?: boolean;
};

function ResultTile({ label, value, warn = false }: ResultTileProps) {
  return (
    <Card className="p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </div>
      <div
        className={`tabular font-display text-4xl font-bold ${warn ? "text-warn" : "text-primary"}`}
      >
        {value}
      </div>
    </Card>
  );
}

type UploadCardProps = {
  kind: "stats" | "adp";
  title: string;
  onSuccess: (result: ImportBatchResult) => void;
};

function UploadCard({ kind, title, onSuccess }: UploadCardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("fantasypros");
  const [position, setPosition] = useState<string>("QB");
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = (files: FileList | null) => {
    setFile(files?.[0] ?? null);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("source", source);
    if (kind === "stats") formData.append("position", position);

    const endpoint = kind === "stats" ? "/api/imports/stats" : "/api/imports/adp";

    try {
      const resp = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new ApiError(resp.status, toUserMessage(resp.status, body));
      }
      const result = (await resp.json()) as ImportBatchResult;
      setFile(null);
      onSuccess(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-display text-sm font-semibold text-primary">{title}</h2>

      <label
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          handleFiles(event.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-base border border-dashed px-4 py-8 text-center text-sm transition-colors ${
          dragOver ? "border-accent text-accent" : "border-hairline text-muted"
        }`}
      >
        <input
          type="file"
          accept=".csv,.html,.htm"
          className="hidden"
          onChange={(event) => handleFiles(event.target.files)}
        />
        <span>Drop a CSV here, or click to choose a file</span>
        {file ? (
          <span className="text-xs text-primary">
            {file.name} · {formatFileSize(file.size)}
          </span>
        ) : null}
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted" htmlFor={`${kind}-source`}>
          Source
        </label>
        <select
          id={`${kind}-source`}
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="rounded-base border border-hairline bg-well px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
        >
          <option value="fantasypros">fantasypros</option>
        </select>

        {kind === "stats" ? (
          <>
            <label className="text-xs text-muted" htmlFor={`${kind}-position`}>
              Position
            </label>
            <select
              id={`${kind}-position`}
              value={position}
              onChange={(event) => setPosition(event.target.value)}
              className="rounded-base border border-hairline bg-well px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
            >
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </>
        ) : null}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!file || submitting}
          className="ml-auto rounded-base bg-accent px-3 py-1.5 text-sm font-semibold text-canvas hover:bg-accent/90 disabled:opacity-50"
        >
          {submitting ? "Uploading…" : "Upload"}
        </button>
      </div>

      {error ? <p className="text-xs text-warn">{error}</p> : null}
    </Card>
  );
}

export function ImportPage() {
  const [result, setResult] = useState<ImportBatchResult | null>(null);
  const [unresolvedRows, setUnresolvedRows] = useState<UnresolvedRow[]>([]);
  const [unresolvedLoading, setUnresolvedLoading] = useState(false);
  const [unresolvedError, setUnresolvedError] = useState<string | null>(null);

  const [progress, setProgress] = useState<PrecomputeResult | null>(null);
  const [precomputing, setPrecomputing] = useState(false);
  const [precomputeError, setPrecomputeError] = useState<string | null>(null);
  const precomputeRunId = useRef(0);
  const unresolvedRunId = useRef(0);

  const startPrecompute = useCallback(() => {
    const runId = (precomputeRunId.current += 1);
    setPrecomputing(true);
    setPrecomputeError(null);
    runPrecompute((p) => {
      if (precomputeRunId.current === runId) setProgress(p);
    })
      .catch((err) => {
        if (precomputeRunId.current !== runId) return;
        setPrecomputeError(
          err instanceof Error ? err.message : "Failed to compute distributions.",
        );
      })
      .finally(() => {
        if (precomputeRunId.current === runId) setPrecomputing(false);
      });
  }, []);

  const loadUnresolved = useCallback((batchId: number) => {
    const runId = (unresolvedRunId.current += 1);
    setUnresolvedLoading(true);
    setUnresolvedError(null);
    apiFetch<UnresolvedRow[]>(`/api/imports/${batchId}/unresolved`)
      .then((rows) => {
        if (unresolvedRunId.current === runId) setUnresolvedRows(rows);
      })
      .catch((err) => {
        if (unresolvedRunId.current !== runId) return;
        setUnresolvedError(
          err instanceof Error ? err.message : "Failed to load unresolved rows.",
        );
      })
      .finally(() => {
        if (unresolvedRunId.current === runId) setUnresolvedLoading(false);
      });
  }, []);

  const handleImported = useCallback(
    (imported: ImportBatchResult) => {
      setResult(imported);
      setUnresolvedRows([]);
      setUnresolvedError(null);
      setProgress(null);
      setPrecomputeError(null);

      loadUnresolved(imported.import_batch_id);
      startPrecompute();
    },
    [loadUnresolved, startPrecompute],
  );

  const progressPct =
    progress && progress.total > 0
      ? Math.min(100, Math.round((progress.done / progress.total) * 100))
      : 0;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-lg font-semibold text-primary">Import</h1>

      <div className="grid grid-cols-2 gap-4">
        <UploadCard kind="stats" title="Stat projections (CSV)" onSuccess={handleImported} />
        <UploadCard kind="adp" title="ADP (CSV)" onSuccess={handleImported} />
      </div>

      {result ? (
        <div className="grid grid-cols-3 gap-4">
          <ResultTile label="Imported" value={result.total_rows} />
          <ResultTile label="Resolved" value={result.matched_rows} />
          <ResultTile
            label="Unresolved"
            value={result.unresolved_rows}
            warn={result.unresolved_rows > 0}
          />
        </div>
      ) : null}

      {precomputing || (progress && progress.remaining > 0) ? (
        <Card className="flex flex-col gap-2 p-4">
          <div className="text-sm font-semibold text-primary">Computing distributions</div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-well">
            <div
              className="h-full rounded-full bg-accent transition-[width]"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="text-xs text-muted">
            {progress ? `${progress.done} / ${progress.total} players` : "Starting…"}
          </div>
        </Card>
      ) : null}

      {precomputeError ? (
        <ErrorState
          title="Couldn't finish computing distributions"
          body={precomputeError}
          onRetry={startPrecompute}
        />
      ) : null}

      {result ? (
        <Card className="border-l-2 border-l-warn p-4">
          <h2 className="mb-3 font-display text-sm font-semibold text-primary">
            Unresolved players
          </h2>
          {unresolvedError ? (
            <ErrorState
              title="Couldn't load unresolved rows"
              body={unresolvedError}
              onRetry={() => loadUnresolved(result.import_batch_id)}
            />
          ) : unresolvedLoading ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : unresolvedRows.length === 0 ? (
            <p className="text-sm text-muted">No unresolved rows for this import.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-[0.06em] text-muted">
                    <th className="pb-2 pr-4 font-semibold">Name</th>
                    <th className="pb-2 pr-4 font-semibold">Team</th>
                    <th className="pb-2 pr-4 font-semibold">Position</th>
                    <th className="pb-2 font-semibold">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {unresolvedRows.map((row, index) => (
                    <tr key={index} className="border-t border-hairline">
                      <td className="py-2 pr-4 text-primary">{row.parsed_name ?? "—"}</td>
                      <td className="py-2 pr-4 text-muted">{row.parsed_team ?? "—"}</td>
                      <td className="py-2 pr-4 text-muted">{row.position ?? "—"}</td>
                      <td className="py-2 text-muted">{row.resolution}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : null}
    </div>
  );
}

type Detail = { error?: string; message?: string };

function readDetail(body: unknown): Detail | string | undefined {
  if (typeof body !== "object" || body === null) return undefined;
  return (body as { detail?: Detail | string }).detail;
}

/** Turn an HTTP failure into something worth showing a person. */
export function toUserMessage(status: number, body: unknown): string {
  const detail = readDetail(body);

  if (status === 401 || status === 403) {
    return "Check your API token in Settings.";
  }

  if (typeof detail === "object" && detail !== null) {
    if (detail.error === "insufficient_history") {
      return detail.message ?? "Not enough career games to model this player.";
    }
    if (detail.error === "not_supported_mvp") {
      return "Kickers and defenses aren't modeled yet.";
    }
    if (detail.message) return detail.message;
  }

  if (status === 404) {
    if (typeof detail === "string" && detail.includes("projection")) {
      return "No projection imported for this player.";
    }
    return "Not found.";
  }

  if (status >= 500) return "The server hit an error. Try again in a moment.";
  return typeof detail === "string" ? detail : `Request failed (${status}).`;
}

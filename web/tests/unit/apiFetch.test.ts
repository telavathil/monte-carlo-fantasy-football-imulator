import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => {
  vi.stubEnv("VITE_API_URL", "http://api.test");
  vi.stubEnv("VITE_API_TOKEN", "test-token");
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("throws an ApiError carrying a human message, not a raw body", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: { error: "insufficient_history", message: "Only 2 career games" } }),
      { status: 422 },
    )));
    const { apiFetch, ApiError } = await import("../../src/api/auth");
    await expect(apiFetch("/api/players/1/distribution")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.status === 422
        && e.message === "Only 2 career games",
    );
  });

  it("sends the bearer token", async () => {
    const spy = vi.fn(async () => new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const { apiFetch } = await import("../../src/api/auth");
    await apiFetch("/api/players");
    const headers = new Headers(spy.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("signals warming when a request outlives the threshold", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(() => new Promise((resolve) => {
      setTimeout(() => resolve(new Response("[]", { status: 200 })), 5000);
    })));
    const { apiFetch, onWarming } = await import("../../src/api/auth");
    const seen: boolean[] = [];
    onWarming((w) => seen.push(w));
    const pending = apiFetch("/api/players");
    await vi.advanceTimersByTimeAsync(2500);
    expect(seen).toContain(true);
    await vi.advanceTimersByTimeAsync(3000);
    await pending;
    expect(seen.at(-1)).toBe(false);
    vi.useRealTimers();
  });
});

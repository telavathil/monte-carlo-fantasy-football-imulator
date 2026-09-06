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

describe("apiFetch retry", () => {
  it("retries once on a genuine network failure and succeeds", async () => {
    const spy = vi.fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const { apiFetch } = await import("../../src/api/auth");
    const result = await apiFetch("/api/players");
    expect(result).toEqual([]);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("gives up after the retry also fails", async () => {
    const spy = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", spy);
    const { apiFetch, ApiError } = await import("../../src/api/auth");
    await expect(apiFetch("/api/players")).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.status === 0
        && e.message === "Could not reach the server. Check your connection.",
    );
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("never retries an HTTP error response", async () => {
    const spy = vi.fn(async () => new Response(
      JSON.stringify({ detail: "not found" }), { status: 404 },
    ));
    vi.stubGlobal("fetch", spy);
    const { apiFetch, ApiError } = await import("../../src/api/auth");
    await expect(apiFetch("/api/players/999/distribution")).rejects.toBeInstanceOf(ApiError);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("never retries a timeout", async () => {
    vi.useFakeTimers();
    // Mirrors real fetch: never settles on its own, but rejects with an
    // AbortError once the request's AbortSignal fires (a bare `new
    // Promise(() => {})` would ignore the signal and hang the test forever).
    const spy = vi.fn((_url: string, requestInit?: RequestInit) => new Promise((_resolve, reject) => {
      requestInit?.signal?.addEventListener("abort", () => {
        reject(new DOMException("The operation was aborted.", "AbortError"));
      });
    }));
    vi.stubGlobal("fetch", spy);
    const { apiFetch, ApiError } = await import("../../src/api/auth");
    const pending = apiFetch("/api/players");
    // The 30s abort timer fires during the timer advance below, before the
    // `.rejects` assertion attaches its handler — pre-attach a no-op catch
    // so Node doesn't flag the interim gap as an unhandled rejection. The
    // real assertion is still the `expect(pending).rejects.toSatisfy(...)`
    // that follows; this doesn't change what it checks.
    pending.catch(() => {});
    await vi.advanceTimersByTimeAsync(30_000);
    await expect(pending).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.message.includes("took too long"),
    );
    expect(spy).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

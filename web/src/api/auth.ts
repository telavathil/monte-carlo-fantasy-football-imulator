import { toUserMessage } from "./errors";

const TOKEN = import.meta.env.VITE_API_TOKEN as string;
const API_URL = import.meta.env.VITE_API_URL as string;

const TIMEOUT_MS = 30_000;
const WARMING_AFTER_MS = 2_000;

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type WarmingListener = (warming: boolean) => void;

const listeners = new Set<WarmingListener>();
let outstanding = 0;

export function onWarming(cb: WarmingListener): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function emit(warming: boolean): void {
  listeners.forEach((cb) => cb(warming));
}

export function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${TOKEN}` };
}

const MAX_ATTEMPTS = 2;
const RETRY_DELAY_MS = 300;

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const warmingTimer = setTimeout(() => emit(true), WARMING_AFTER_MS);
    outstanding += 1;

    try {
      const resp = await fetch(`${API_URL}${path}`, {
        ...init,
        signal: controller.signal,
        headers: { ...authHeaders(), ...(init.headers || {}) },
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new ApiError(resp.status, toUserMessage(resp.status, body));
      }
      return (await resp.json()) as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError(0, "The server took too long to respond. Try again.");
      }
      // A genuine network-level failure — the shape of error a Fly machine
      // mid-cold-boot produces before its HTTP listener is up. Worth one
      // quick retry before giving up.
      if (attempt === MAX_ATTEMPTS) {
        throw new ApiError(0, "Could not reach the server. Check your connection.");
      }
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    } finally {
      clearTimeout(timeout);
      clearTimeout(warmingTimer);
      outstanding -= 1;
      if (outstanding === 0) emit(false);
    }
  }
  // Unreachable — the loop always returns or throws — but keeps TS satisfied.
  throw new ApiError(0, "Could not reach the server. Check your connection.");
}

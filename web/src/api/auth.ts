const TOKEN = import.meta.env.VITE_API_TOKEN as string;
const API_URL = import.meta.env.VITE_API_URL as string;

export function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${TOKEN}` };
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers || {}) },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}

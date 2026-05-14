const API_BASE = "";

export type ApiSuccess<T> = { success: true; data: T; meta?: Record<string, unknown> };

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body?.error?.message || res.statusText);
  }
  if (body.success === false) {
    throw new Error(body.error?.message || "Request failed");
  }
  return body.data as T;
}

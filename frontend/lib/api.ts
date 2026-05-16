import { messageFromApiBody } from "./api-errors";

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
  let body: unknown = {};
  try {
    body = await res.json();
  } catch {
    body = {};
  }
  if (!res.ok) {
    throw new Error(messageFromApiBody(body, res.statusText));
  }
  const rec = body as Record<string, unknown>;
  if (rec.success === false) {
    throw new Error(messageFromApiBody(body, "Request failed"));
  }
  return rec.data as T;
}

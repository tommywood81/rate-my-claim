import { messageFromApiBody } from "./api-errors";

const API_BASE = "";

export type ApiSuccess<T> = { success: true; data: T; meta?: Record<string, unknown> };

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)rmc_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const csrf = getCsrfToken();
  const needsCsrf = ["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrf;
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(needsCsrf ? { "X-CSRF-Token": csrf } : {}),
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

/** End cookie session: ensure CSRF cookie exists, then revoke refresh + clear auth cookies. */
export async function logoutSession(): Promise<void> {
  if (!getCsrfToken()) {
    await fetch(`${API_BASE}/api/v1/csrf`, { credentials: "include" });
  }
  await apiFetch<Record<string, never>>("/api/v1/auth/logout", { method: "POST" });
}

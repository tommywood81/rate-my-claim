import { messageFromApiBody, parseApiError, type ParsedApiError } from "./api-errors";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, parsed: ParsedApiError) {
    super(parsed.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = parsed.code;
    this.details = parsed.details;
  }
}

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
    throw new ApiRequestError(res.status, parseApiError(body, res.statusText));
  }
  const rec = body as Record<string, unknown>;
  if (rec.success === false) {
    throw new ApiRequestError(400, parseApiError(body, "Request failed"));
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

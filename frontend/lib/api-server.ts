/** Server-side fetch helpers for SSR pages. */

const base = () => process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

export async function serverGet<T>(path: string, init?: RequestInit): Promise<T | null> {
  const res = await fetch(`${base()}${path}`, init);
  if (!res.ok) return null;
  const body = await res.json();
  return body.data as T;
}

export async function serverGetEnvelope<T>(
  path: string,
  init?: RequestInit,
): Promise<{ data: T; meta: Record<string, unknown> }> {
  const res = await fetch(`${base()}${path}`, init);
  if (!res.ok) return { data: [] as T, meta: {} };
  const body = await res.json();
  return { data: (body.data ?? []) as T, meta: (body.meta ?? {}) as Record<string, unknown> };
}

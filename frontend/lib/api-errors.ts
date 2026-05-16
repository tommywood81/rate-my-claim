/** Normalize error messages from API JSON (envelope or FastAPI detail). */

export function messageFromApiBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }
  const b = body as Record<string, unknown>;
  const err = b.error;
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  const detail = b.detail;
  if (detail && typeof detail === "object" && "error" in detail) {
    const inner = (detail as { error?: { message?: string } }).error;
    if (inner?.message) {
      return inner.message;
    }
  }
  if (typeof detail === "string") {
    return detail;
  }
  return fallback;
}

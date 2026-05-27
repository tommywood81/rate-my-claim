/** Normalize error messages from API JSON (envelope or FastAPI detail). */

export type ParsedApiError = {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
};

function envelopeFromRecord(b: Record<string, unknown>): ParsedApiError | null {
  const err = b.error;
  if (err && typeof err === "object" && "message" in err) {
    const e = err as { message: unknown; code?: string; details?: Record<string, unknown> };
    return {
      message: String(e.message),
      code: e.code,
      details: e.details,
    };
  }
  return null;
}

export function parseApiError(body: unknown, fallback: string): ParsedApiError {
  if (!body || typeof body !== "object") {
    return { message: fallback };
  }
  const b = body as Record<string, unknown>;
  const top = envelopeFromRecord(b);
  if (top) {
    return top;
  }
  const detail = b.detail;
  if (detail && typeof detail === "object") {
    const inner = envelopeFromRecord(detail as Record<string, unknown>);
    if (inner) {
      return inner;
    }
  }
  if (typeof detail === "string") {
    return { message: detail };
  }
  return { message: fallback };
}

export function messageFromApiBody(body: unknown, fallback: string): string {
  return parseApiError(body, fallback).message;
}

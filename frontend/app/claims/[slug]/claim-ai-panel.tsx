"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch } from "@/lib/api";

export function ClaimAiAnalysisPanel({ slug }: { slug: string }) {
  const router = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onGenerate() {
    setErr(null);
    setLoading(true);
    try {
      await apiFetch(`/api/v1/claims/${encodeURIComponent(slug)}/ai-analysis`, {
        method: "POST",
      });
      router.refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-3 space-y-2 border-t border-dashed border-[var(--border)] pt-3">
      <p className="text-xs text-[var(--muted)]">
        Moderators: generate a non-canonical structured verdict from evidence on this claim (calls your configured AI
        provider). Sign in from this origin if the button returns an error.
      </p>
      <button
        type="button"
        className="rounded border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-medium hover:bg-[var(--card)] disabled:opacity-60"
        onClick={onGenerate}
        disabled={loading}
      >
        {loading ? "Running…" : "Generate AI analysis"}
      </button>
      {err && <p className="text-xs text-red-700">{err}</p>}
    </div>
  );
}

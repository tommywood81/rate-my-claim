"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ModerationRowTokenHint,
  ModerationTokenEstimator,
} from "@/components/moderation-token-estimator";
import { apiFetch } from "@/lib/api";

type Pending = {
  id: string;
  raw_claim_text: string;
  processing_status: string;
  error_message?: string | null;
  ai_summary?: string | null;
  duplicate_candidate_ids?: string[] | null;
  duplicate_hints?: { id: string; slug?: string | null; title?: string | null }[] | null;
  source_urls?: string[] | null;
  public_slug?: string | null;
  created_at: string;
};

type LoadState = "loading" | "authorized" | "forbidden" | "error";

const PIPELINE = new Set([
  "submitted",
  "embedding",
  "duplicate_check",
  "canonicalizing",
  "enriching",
]);

export default function ModerationPage() {
  const [rows, setRows] = useState<Pending[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [refreshing, setRefreshing] = useState(false);

  const loadQueue = useCallback(async () => {
    const data = await apiFetch<Pending[]>("/api/v1/moderation/pending-claims?limit=30");
    setRows(data);
    setLoadState("authorized");
    setErr(null);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await loadQueue();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to load queue";
        setErr(msg);
        const lower = msg.toLowerCase();
        if (lower.includes("forbidden") || lower === "403") {
          setLoadState("forbidden");
        } else {
          setLoadState("error");
        }
      }
    })();
  }, [loadQueue]);

  useEffect(() => {
    if (loadState !== "authorized") {
      return;
    }
    const busy = rows.some((r) => PIPELINE.has(r.processing_status));
    if (!busy) {
      return;
    }
    const id = setInterval(() => {
      void (async () => {
        try {
          await loadQueue();
        } catch {
          /* ignore transient errors while polling */
        }
      })();
    }, 8000);
    return () => clearInterval(id);
  }, [loadState, rows, loadQueue]);

  async function onRefresh() {
    setRefreshing(true);
    setErr(null);
    try {
      await loadQueue();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function act(
    id: string,
    action: "approve_claim" | "reject_claim" | "request_revision",
    remove = true,
  ) {
    setErr(null);
    try {
      await apiFetch("/api/v1/moderation/actions", {
        method: "POST",
        body: JSON.stringify({
          action_type: action,
          target_type: "pending_claim",
          target_id: id,
          explanation:
            action === "approve_claim"
              ? "Approved via UI"
              : action === "reject_claim"
                ? "Rejected via UI"
                : "Revision requested via UI",
        }),
      });
      if (remove) {
        setRows((r) => r.filter((x) => x.id !== id));
      } else {
        await loadQueue();
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function reprocess(id: string) {
    setErr(null);
    try {
      await apiFetch(`/api/v1/moderation/pending-claims/${id}/reprocess`, { method: "POST" });
      await loadQueue();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Reprocess failed");
    }
  }

  const canApprove = (p: Pending) => p.processing_status === "awaiting_moderation";
  const canRevise = (p: Pending) => p.processing_status === "awaiting_moderation";
  const canReprocess = (p: Pending) =>
    p.processing_status === "failed" ||
    p.processing_status === "revision_requested" ||
    p.processing_status === "awaiting_moderation";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="owid-kicker">Moderation</p>
        <h1 className="owid-page-heading text-3xl">Review queue</h1>
        {loadState === "authorized" && (
          <button
            type="button"
            className="rounded border border-[var(--border)] bg-white px-3 py-1.5 text-xs font-medium hover:bg-[var(--card)] disabled:opacity-60"
            onClick={onRefresh}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        )}
      </div>
      {loadState === "forbidden" && (
        <p className="text-sm text-[var(--muted)]">
          This page needs a moderator or admin.{" "}
          <a href="/login?next=/moderation" className="font-medium text-[var(--accent)] hover:underline">
            Sign in
          </a>{" "}
          with <code className="text-xs">seed_moderator</code> or <code className="text-xs">seed_admin</code>, then
          reload.
        </p>
      )}
      {loadState === "authorized" && (
        <>
          <p className="text-sm text-[var(--muted)]">
            Submissions appear here as soon as they are queued. <strong>Approve</strong> is only available when the
            background worker has finished enrichment and status is{" "}
            <code className="text-xs">awaiting_moderation</code>. You can <strong>Reject</strong> earlier if needed. If
            a row stays in <code className="text-xs">submitted</code> or <code className="text-xs">failed</code>, check
            that the Celery worker is running and that <code className="text-xs">OPENAI_API_KEY</code> is set for AI
            steps.
          </p>
          <ModerationTokenEstimator
            rows={rows.map((p) => ({
              id: p.id,
              rawClaimText: p.raw_claim_text,
              sourceUrlCount: p.source_urls?.length ?? 0,
              processingStatus: p.processing_status,
            }))}
          />
        </>
      )}
      {err && <p className="text-sm text-red-700">{err}</p>}
      <ul className="divide-y divide-[var(--border)] rounded border border-[var(--border)] bg-[var(--card)]">
        {loadState === "authorized" && rows.length === 0 && (
          <li className="px-4 py-6 text-sm text-[var(--muted)]">No active submissions in the pipeline.</li>
        )}
        {rows.map((p) => (
          <li key={p.id} className="space-y-2 px-4 py-3">
            <p className="text-xs text-[var(--muted)]">
              {p.id} · <span className="font-medium text-[var(--fg)]">{p.processing_status}</span> ·{" "}
              {new Date(p.created_at).toLocaleString()}
              {p.public_slug && (
                <>
                  {" · "}
                  <Link href={`/claims/${p.public_slug}`} className="text-[var(--accent)] hover:underline">
                    View live claim
                  </Link>
                </>
              )}
              {" · "}
              <ModerationRowTokenHint
                rawClaimText={p.raw_claim_text}
                sourceUrlCount={p.source_urls?.length ?? 0}
              />
            </p>
            <p className="text-sm">{p.raw_claim_text}</p>
            {p.ai_summary && (
              <p className="text-xs text-[var(--muted)]">
                <span className="font-medium">AI summary:</span> {p.ai_summary}
              </p>
            )}
            {p.duplicate_hints && p.duplicate_hints.length > 0 && (
              <p className="text-xs text-[var(--muted)]">
                <span className="font-medium">Possible duplicates:</span>{" "}
                {p.duplicate_hints.slice(0, 3).map((hint, i) => (
                  <span key={hint.id}>
                    {i > 0 ? "; " : ""}
                    {hint.slug ? (
                      <Link href={`/claims/${hint.slug}`} className="text-[var(--accent)] hover:underline">
                        {hint.title || hint.slug}
                      </Link>
                    ) : (
                      hint.title || hint.id
                    )}
                  </span>
                ))}
                {p.duplicate_hints.length > 3 ? "…" : ""}
              </p>
            )}
            {p.error_message && (
              <p className="rounded border border-red-200 bg-red-50 px-2 py-1 font-mono text-xs text-red-900">
                {p.error_message}
              </p>
            )}
            {PIPELINE.has(p.processing_status) && (
              <p className="text-xs text-[var(--muted)]">Background enrichment in progress — list auto-refreshes.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs enabled:hover:bg-[var(--card)] disabled:cursor-not-allowed disabled:opacity-45"
                onClick={() => act(p.id, "approve_claim")}
                disabled={!canApprove(p)}
                title={canApprove(p) ? undefined : "Wait until status is awaiting_moderation"}
              >
                Mark reviewed
              </button>
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs hover:bg-[var(--card)]"
                onClick={() => act(p.id, "reject_claim")}
              >
                Reject
              </button>
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs hover:bg-[var(--card)] disabled:opacity-45"
                onClick={() => act(p.id, "request_revision", false)}
                disabled={!canRevise(p)}
                title={canRevise(p) ? undefined : "Available when awaiting_moderation"}
              >
                Request revision
              </button>
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs hover:bg-[var(--card)] disabled:opacity-45"
                onClick={() => reprocess(p.id)}
                disabled={!canReprocess(p)}
                title={canReprocess(p) ? undefined : "Re-run enrichment after failed or revision"}
              >
                Re-run enrichment
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

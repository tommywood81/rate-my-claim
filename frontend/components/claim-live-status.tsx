"use client";

import { useCallback, useEffect, useState } from "react";

import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { apiFetch } from "@/lib/api";
import type { ClaimDetail } from "@/lib/types";

const TERMINAL = new Set(["completed", "rejected", "failed"]);

type Props = {
  slug: string;
  initial: ClaimDetail;
};

export function ClaimLiveStatus({ slug, initial }: Props) {
  const [detail, setDetail] = useState(initial);

  const refresh = useCallback(async () => {
    try {
      const next = await apiFetch<ClaimDetail>(`/api/v1/claims/${encodeURIComponent(slug)}`);
      setDetail(next);
    } catch {
      /* keep last good state */
    }
  }, [slug]);

  useEffect(() => {
    setDetail(initial);
  }, [initial]);

  useEffect(() => {
    const proc = detail.processing_status;
    if (!proc || TERMINAL.has(proc)) {
      return;
    }
    const id = setInterval(() => {
      void refresh();
    }, 8000);
    return () => clearInterval(id);
  }, [detail.processing_status, refresh]);

  const processing = detail.processing_status && !TERMINAL.has(detail.processing_status);

  return (
    <section
      className="space-y-3 rounded-lg border border-[var(--accent)]/25 bg-[var(--card)] p-4"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-[var(--fg)]">
          {processing ? "Research in progress" : "Live claim"}
          {detail.visibility_label ? (
            <span className="ml-2 rounded-full border border-[var(--border)] bg-white px-2 py-0.5 text-xs font-normal text-[var(--muted)]">
              {detail.visibility_label}
            </span>
          ) : null}
        </p>
        {detail.pipeline_stage_label && (
          <p className="text-xs text-[var(--muted)]">Current: {detail.pipeline_stage_label}</p>
        )}
      </div>
      {processing && (
        <>
          <ClaimPipelineStepper currentKey={detail.pipeline_stage_key} />
          <p className="text-xs text-[var(--muted)]">
            This page updates as enrichment runs. Moderators may refine the claim at any time; visibility is not
            blocked by review.
          </p>
        </>
      )}
      {!processing && detail.moderation_reviewed && (
        <p className="text-xs text-[var(--muted)]">
          A moderator has reviewed this claim. Scores and evidence may still evolve.
        </p>
      )}
      {detail.live_ai_summary && (
        <div className="rounded border border-dashed border-[var(--border)] bg-[#faf9f6] p-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Evolving research summary
          </p>
          <p className="mt-2 leading-relaxed text-[var(--fg)]">{detail.live_ai_summary}</p>
        </div>
      )}
    </section>
  );
}

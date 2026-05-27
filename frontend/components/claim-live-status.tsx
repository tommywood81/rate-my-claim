"use client";

import { useCallback, useEffect, useState } from "react";

import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { apiFetch } from "@/lib/api";
import { isAssessmentComplete } from "@/lib/research-pipeline-ux";
import type { ClaimDetail } from "@/lib/types";

const ACTIVE = new Set(["submitted", "embedding", "duplicate_check", "canonicalizing", "enriching"]);

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
    if (!proc || !ACTIVE.has(proc)) {
      return;
    }
    const id = setInterval(() => {
      void refresh();
    }, 8000);
    return () => clearInterval(id);
  }, [detail.processing_status, refresh]);

  const checking = detail.processing_status && ACTIVE.has(detail.processing_status);
  const assessed = isAssessmentComplete(detail);

  return (
    <section
      className="space-y-3 rounded-lg border border-[var(--accent)]/25 bg-[var(--card)] p-4"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-[var(--fg)]">
          {checking ? "Assessing…" : assessed ? "Live — assessment complete" : "Live record"}
          {detail.visibility_label ? (
            <span className="ml-2 rounded-full border border-[var(--border)] bg-white px-2 py-0.5 text-xs font-normal text-[var(--muted)]">
              {detail.visibility_label}
            </span>
          ) : null}
        </p>
        {detail.pipeline_stage_label && (
          <p className="text-xs text-[var(--muted)]">{detail.pipeline_stage_label}</p>
        )}
      </div>
      {checking && (
        <>
          <ClaimPipelineStepper currentKey={detail.pipeline_stage_key} />
          <p className="text-xs text-[var(--muted)]">
            Assessment runs in the background. This block updates as truth status and evidence evolve.
          </p>
        </>
      )}
      {assessed && (
        <p className="text-xs text-[var(--muted)]">
          From the claim library — not human editorial sign-off. Records can be updated, disputed, or overturned as new
          sources are added to the library.
        </p>
      )}
      {detail.live_ai_summary && (
        <div className="rounded border border-dashed border-[var(--border)] bg-[#faf9f6] p-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Research summary</p>
          <p className="mt-2 leading-relaxed text-[var(--fg)]">{detail.live_ai_summary}</p>
        </div>
      )}
    </section>
  );
}

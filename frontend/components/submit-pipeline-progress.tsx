"use client";

import { useEffect, useState } from "react";

import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { ResearchPipelineProgress } from "@/components/research-pipeline-progress";
import { SubmitClaimResultsPanel } from "@/components/submit-claim-results";
import {
  PIPELINE_STAGES,
  buildSubmitOutcomes,
  claimPollingHint,
  isAssessmentComplete,
  isPipelineInFlight,
  pipelineAgentState,
  pipelineStageIndex,
  processingStatusToStageKey,
  submitActiveStageMessage,
  type SubmitTrackContext,
} from "@/lib/research-pipeline-ux";
import type { ClaimDetail } from "@/lib/types";

type Props = {
  slug: string;
  processingStatus: string | null | undefined;
  pipelineStageKey: string | null | undefined;
  claimDetail: ClaimDetail | null;
  elapsedSec: number;
  trackCtx: SubmitTrackContext;
  duplicateCount?: number;
  canonicalCandidate?: string | null;
  errorMessage?: string | null;
};

export function SubmitPipelineProgress({
  slug,
  processingStatus,
  pipelineStageKey,
  claimDetail,
  elapsedSec,
  trackCtx,
  duplicateCount,
  canonicalCandidate,
  errorMessage,
}: Props) {
  const [pipelineOpen, setPipelineOpen] = useState(true);
  const stageKey = pipelineStageKey ?? processingStatusToStageKey(processingStatus);
  const stageIdx = pipelineStageIndex(stageKey);
  const agent = pipelineAgentState(processingStatus);
  const activeLine = submitActiveStageMessage(processingStatus, trackCtx);
  const outcomes = buildSubmitOutcomes(claimDetail, {
    duplicateCount,
    canonicalCandidate,
    errorMessage,
  });
  const hint = claimPollingHint(elapsedSec, processingStatus);
  const inFlight = isPipelineInFlight(processingStatus);
  const complete = isAssessmentComplete(claimDetail);
  const showExpandedPipeline = inFlight && pipelineOpen;

  useEffect(() => {
    if (complete) setPipelineOpen(false);
  }, [complete]);

  return (
    <div className="space-y-0">
      <div className="rounded border border-[var(--accent)]/30 bg-[var(--accent-soft)]/40 p-4 sm:p-5">
        <div className="space-y-1">
          <p className="owid-kicker text-[var(--accent-dark)]">One claim. One page.</p>
          <p className="text-sm font-medium text-[var(--fg)]">
            {complete
              ? "Assessment finished — your verdict and evidence are below."
              : "Your living record is public. Results stream in here as the assessment runs — no need to leave this page."}
          </p>
        </div>

        {complete ? (
          <button
            type="button"
            className="mt-4 flex w-full items-center justify-between gap-2 rounded border border-[var(--border)] bg-white/70 px-3 py-2 text-left text-sm text-[var(--fg)] hover:bg-white"
            aria-expanded={pipelineOpen}
            onClick={() => setPipelineOpen((v) => !v)}
          >
            <span>
              Completed in {elapsedSec}s
              {agent.overallPercent >= 100 ? " · 100% assessed" : ""}
            </span>
            <span className="text-xs font-medium text-[var(--accent)]">
              {pipelineOpen ? "Hide steps" : "Show steps"}
            </span>
          </button>
        ) : null}

        {showExpandedPipeline && (
          <div className="mt-4 space-y-4">
            <ClaimPipelineStepper
              currentKey={stageKey ?? "received"}
              pulsing={Boolean(processingStatus && inFlight)}
              layout="vertical"
            />

            <p className="text-sm text-[var(--fg)]">{activeLine}</p>

            {PIPELINE_STAGES[stageIdx]?.hint && (
              <p className="text-xs text-[var(--muted)]" title="What this step means">
                {PIPELINE_STAGES[stageIdx].hint}
              </p>
            )}

            <ResearchPipelineProgress
              processingStatus={processingStatus}
              elapsedSec={elapsedSec}
              pollingHint={hint}
              compact
            />

            {outcomes.length > 0 && (
              <ul className="space-y-1.5 border-t border-[var(--border)] pt-3 text-sm" aria-label="Progress">
                {outcomes.map((o) => (
                  <li key={o.id} className="flex gap-2 text-[var(--muted)]">
                    <span className="text-[var(--accent)]" aria-hidden>
                      ✓
                    </span>
                    <span>{o.text}</span>
                  </li>
                ))}
              </ul>
            )}

            <p className="text-xs text-[var(--muted)]">
              {elapsedSec}s elapsed
              {agent.overallPercent > 0 && agent.overallPercent < 100
                ? ` · ~${agent.overallPercent}% through`
                : ""}
            </p>
          </div>
        )}

        {complete && pipelineOpen && (
          <div className="mt-4 space-y-3 border-t border-[var(--border)] pt-4">
            <ClaimPipelineStepper currentKey={stageKey ?? "assessed"} pulsing={false} layout="vertical" />
            {outcomes.length > 0 && (
              <ul className="space-y-1.5 text-sm text-[var(--muted)]">
                {outcomes.map((o) => (
                  <li key={o.id} className="flex gap-2">
                    <span className="text-[var(--accent)]" aria-hidden>
                      ✓
                    </span>
                    <span>{o.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <SubmitClaimResultsPanel
        slug={slug}
        detail={claimDetail}
        elapsedSec={elapsedSec}
        inFlight={inFlight}
      />
    </div>
  );
}

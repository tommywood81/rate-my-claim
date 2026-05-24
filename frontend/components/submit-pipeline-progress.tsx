"use client";

import Link from "next/link";

import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { ResearchPipelineProgress } from "@/components/research-pipeline-progress";
import {
  PIPELINE_STAGES,
  buildSubmitOutcomes,
  claimPollingHint,
  pipelineAgentState,
  pipelineStageIndex,
  processingStatusToStageKey,
  submitActiveStageMessage,
  type SubmitOutcome,
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
  const stageKey = pipelineStageKey ?? processingStatusToStageKey(processingStatus);
  const stageIdx = pipelineStageIndex(stageKey);
  const agent = pipelineAgentState(processingStatus);
  const activeLine = submitActiveStageMessage(processingStatus, trackCtx);
  const outcomes: SubmitOutcome[] = buildSubmitOutcomes(claimDetail, {
    duplicateCount,
    canonicalCandidate,
    errorMessage,
  });
  const hint = claimPollingHint(elapsedSec, processingStatus);
  const claimHref = `/claims/${encodeURIComponent(slug)}?submitted=1`;

  return (
    <div className="space-y-4 rounded border border-[var(--accent)]/30 bg-[var(--accent-soft)]/40 p-4 sm:p-5">
      <div className="space-y-1">
        <p className="owid-kicker text-[var(--accent-dark)]">One claim. One page.</p>
        <p className="text-sm font-medium text-[var(--fg)]">
          Your living record is already public. Sources, counterpoints, and truth status fill in as the assessment
          runs — this page keeps updating.
        </p>
      </div>

      <ClaimPipelineStepper
        currentKey={stageKey ?? "received"}
        pulsing={Boolean(processingStatus && !["awaiting_moderation", "completed", "failed"].includes(processingStatus))}
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
        <ul className="space-y-1.5 border-t border-[var(--border)] pt-3 text-sm" aria-label="Research outcomes">
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

      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border)] pt-3">
        <Link href={claimHref} className="owid-btn-primary text-sm no-underline">
          Open claim page
        </Link>
        <span className="text-xs text-[var(--muted)]">
          {elapsedSec}s elapsed
          {agent.overallPercent > 0 && agent.overallPercent < 100 ? ` · ~${agent.overallPercent}% through` : ""}
        </span>
      </div>
    </div>
  );
}
